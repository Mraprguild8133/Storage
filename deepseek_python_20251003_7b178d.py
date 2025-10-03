import os
import time
import math
import asyncio
import logging
import base64
import threading
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask, render_template, jsonify

# Import configuration
from config import config

# --- Configuration ---
# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Use configuration from config module
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
WASABI_ACCESS_KEY = config.WASABI_ACCESS_KEY
WASABI_SECRET_KEY = config.WASABI_SECRET_KEY
WASABI_BUCKET = config.WASABI_BUCKET
WASABI_REGION = config.WASABI_REGION
ADMIN_ID = config.ADMIN_ID
FLASK_HOST = getattr(config, 'FLASK_HOST', '0.0.0.0')
FLASK_PORT = getattr(config, 'FLASK_PORT', 8000)

# --- Persistence for Authorized Users ---
class UserManager:
    def __init__(self, filename="allowed_users.json"):
        self.filename = filename
        self.load_users()
    
    def load_users(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    import json
                    data = json.load(f)
                    self.allowed_users = set(data.get('allowed_users', [ADMIN_ID]))
            else:
                self.allowed_users = {ADMIN_ID}
                self.save_users()
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            self.allowed_users = {ADMIN_ID}
    
    def save_users(self):
        try:
            with open(self.filename, 'w') as f:
                import json
                json.dump({'allowed_users': list(self.allowed_users)}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def add_user(self, user_id):
        self.allowed_users.add(user_id)
        self.save_users()
    
    def remove_user(self, user_id):
        if user_id in self.allowed_users:
            self.allowed_users.remove(user_id)
            self.save_users()
    
    def is_authorized(self, user_id):
        return user_id in self.allowed_users
    
    def get_all_users(self):
        return list(self.allowed_users)

# Initialize user manager
user_manager = UserManager()

# --- Rate Limiter ---
class RateLimiter:
    def __init__(self):
        self.user_uploads = defaultdict(list)
    
    def is_limited(self, user_id, max_uploads=10, time_window=3600):
        now = datetime.now()
        # Remove old entries
        self.user_uploads[user_id] = [
            timestamp for timestamp in self.user_uploads[user_id]
            if now - timestamp < timedelta(seconds=time_window)
        ]
        
        # Check if user exceeds limit
        if len(self.user_uploads[user_id]) >= max_uploads:
            return True
        
        # Add current upload
        self.user_uploads[user_id].append(now)
        return False
    
    def get_remaining_uploads(self, user_id, max_uploads=10, time_window=3600):
        now = datetime.now()
        self.user_uploads[user_id] = [
            timestamp for timestamp in self.user_uploads[user_id]
            if now - timestamp < timedelta(seconds=time_window)
        ]
        return max(0, max_uploads - len(self.user_uploads[user_id]))

# Initialize rate limiter
rate_limiter = RateLimiter()

# --- Flask Application ---
flask_app = Flask(__name__, template_folder="templates")

@flask_app.route("/")
def index():
    return render_template("index.html")

@flask_app.route("/player/<media_type>/<encoded_url>")
def player(media_type, encoded_url):
    try:
        # Add padding if needed
        padding = 4 - (len(encoded_url) % 4)
        if padding != 4:
            encoded_url += '=' * padding
        media_url = base64.urlsafe_b64decode(encoded_url).decode()
        return render_template("player.html", media_type=media_type, media_url=media_url)
    except Exception as e:
        return f"Error decoding URL: {str(e)}", 400

@flask_app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

def run_flask():
    logger.info(f"Starting Flask server on {FLASK_HOST}:{FLASK_PORT}")
    flask_app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)

# --- Bot & Wasabi Client Initialization ---
app = Client("wasabi_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Boto3 S3 client for Wasabi
try:
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
        aws_access_key_id=WASABI_ACCESS_KEY,
        aws_secret_access_key=WASABI_SECRET_KEY,
        region_name=WASABI_REGION,
        config=boto3.session.Config(
            s3={'addressing_style': 'virtual'},
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
    )
    # Test connection
    s3_client.head_bucket(Bucket=WASABI_BUCKET)
    logger.info("Successfully connected to Wasabi.")
except Exception as e:
    logger.error(f"Failed to connect to Wasabi: {e}")
    s3_client = None

# --- Helpers & Decorators ---
def is_admin(func):
    """Decorator to check if the user is the admin."""
    @wraps(func)
    async def wrapper(client, message):
        if message.from_user.id == ADMIN_ID:
            await func(client, message)
        else:
            await message.reply_text("⛔️ Access denied. This command is for the admin only.")
    return wrapper

def is_authorized(func):
    """Decorator to check if the user is authorized."""
    @wraps(func)
    async def wrapper(client, message):
        if user_manager.is_authorized(message.from_user.id):
            await func(client, message)
        else:
            await message.reply_text("⛔️ You are not authorized to use this bot. Contact the admin.")
    return wrapper

def humanbytes(size):
    """Converts bytes to a human-readable format."""
    if not size:
        return "0B"
    size = int(size)
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels) -1 :
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def get_file_type(mime_type, file_name):
    """Determine file type for player."""
    if mime_type.startswith('video/'):
        return 'video'
    elif mime_type.startswith('audio/'):
        return 'audio'
    elif mime_type.startswith('image/'):
        return 'image'
    else:
        # Fallback based on file extension
        ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        if ext in ['mp4', 'mkv', 'avi', 'mov', 'webm']:
            return 'video'
        elif ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a']:
            return 'audio'
        elif ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
            return 'image'
        else:
            return 'file'

# --- Progress Callback Management ---
last_update_time = {}

async def progress_callback(current, total, message, status):
    """Updates the progress message in Telegram."""
    chat_id = message.chat.id
    message_id = message.id
    
    # Throttle updates to avoid hitting Telegram API limits
    now = time.time()
    if (now - last_update_time.get(message_id, 0)) < 2 and current != total:
        return
    last_update_time[message_id] = now

    percentage = current * 100 / total
    progress_bar = "[{0}{1}]".format(
        '█' * int(percentage / 5),
        ' ' * (20 - int(percentage / 5))
    )
    
    details = (
        f"**{status}**\n"
        f"`{progress_bar}`\n"
        f"**Progress:** {percentage:.2f}%\n"
        f"**Done:** {humanbytes(current)}\n"
        f"**Total:** {humanbytes(total)}"
    )
    
    try:
        await app.edit_message_text(chat_id, message_id, text=details)
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")

# --- Enhanced S3 Operations ---
async def handle_s3_operation(operation, *args, **kwargs):
    """Generic S3 operation handler with error management"""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, operation, *args, **kwargs)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            raise Exception(f"Bucket {WASABI_BUCKET} does not exist")
        elif error_code == 'AccessDenied':
            raise Exception("Access denied to Wasabi bucket")
        elif error_code == 'InvalidAccessKeyId':
            raise Exception("Invalid Wasabi access credentials")
        else:
            raise Exception(f"S3 operation failed: {error_code}")

async def upload_to_wasabi(file_path, file_name, status_message):
    """Upload file to Wasabi with retry logic and progress tracking."""
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            loop = asyncio.get_event_loop()
            
            class ProgressTracker:
                def __init__(self):
                    self.uploaded = 0
                    self.file_size = os.path.getsize(file_path)
                
                def __call__(self, bytes_amount):
                    self.uploaded += bytes_amount
                    # Schedule progress update in the main thread
                    asyncio.run_coroutine_threadsafe(
                        progress_callback(
                            self.uploaded, 
                            self.file_size, 
                            status_message, 
                            f"Uploading... (Attempt {attempt + 1}/{max_retries})"
                        ),
                        loop
                    )
            
            progress_tracker = ProgressTracker()
            
            await loop.run_in_executor(
                None,
                lambda: s3_client.upload_file(
                    file_path,
                    WASABI_BUCKET,
                    file_name,
                    Callback=progress_tracker
                )
            )
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.warning(f"Upload attempt {attempt + 1} failed: {error_code}")
            
            if attempt == max_retries - 1:  # Last attempt
                raise e
                
            # Exponential backoff
            delay = base_delay * (2 ** attempt)
            await status_message.edit_text(
                f"⚠️ Upload failed (attempt {attempt + 1}/{max_retries}). "
                f"Retrying in {delay} seconds..."
            )
            await asyncio.sleep(delay)
    
    return False

async def generate_presigned_url(file_name):
    """Generate presigned URL with error handling."""
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': WASABI_BUCKET, 'Key': file_name},
            ExpiresIn=604800  # 7 days
        )
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None

async def get_bucket_stats():
    """Get basic bucket statistics."""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: s3_client.list_objects_v2(Bucket=WASABI_BUCKET, MaxKeys=1000)
        )
        
        total_size = 0
        total_files = 0
        
        if 'Contents' in response:
            for obj in response['Contents']:
                total_size += obj['Size']
                total_files += 1
        
        return {
            'total_files': total_files,
            'total_size': total_size,
            'human_size': humanbytes(total_size)
        }
    except Exception as e:
        logger.error(f"Error getting bucket stats: {e}")
        return None

# --- Bot Command Handlers ---
@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_auth = user_manager.is_authorized(user_id)
    
    welcome_text = (
        f"👋 **Welcome to Wasabi Storage Bot!**\n\n"
        f"**Your User ID:** `{user_id}`\n"
        f"**Status:** {'✅ Authorized' if is_auth else '❌ Not authorized'}\n\n"
    )
    
    if is_auth:
        welcome_text += (
            "**Available Commands:**\n"
            "• Just send me any file to upload it to Wasabi\n"
            "• `/stats` - Check bot statistics\n"
            "• `/help` - Show this help message\n\n"
            "**Rate Limit:** 10 uploads per hour\n"
            "**Max File Size:** 4GB"
        )
    else:
        welcome_text += (
            "To use this bot, you need to be authorized by the admin.\n"
            "Contact the admin with your User ID to get access."
        )
    
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    help_text = (
        "🤖 **Wasabi Storage Bot Help**\n\n"
        "**For Authorized Users:**\n"
        "• Send any file (document, video, audio) to upload to Wasabi\n"
        "• Get a shareable link with web player\n\n"
        "**For Admin:**\n"
        "• `/adduser <user_id>` - Add authorized user\n"
        "• `/removeuser <user_id>` - Remove user\n"
        "• `/listusers` - Show authorized users\n"
        "• `/stats` - Bot and storage statistics\n"
        "• `/broadcast <message>` - Broadcast message to all users\n\n"
        "**General Commands:**\n"
        "• `/start` - Start the bot\n"
        "• `/help` - Show this help\n\n"
        "**Features:**\n"
        "• Progress tracking for uploads\n"
        "• Web player for media files\n"
        "• Rate limiting (10 uploads/hour)\n"
        "• Support for files up to 4GB"
    )
    await message.reply_text(help_text)

@app.on_message(filters.command("adduser"))
@is_admin
async def add_user_handler(client: Client, message: Message):
    try:
        user_id_to_add = int(message.text.split(" ", 1)[1])
        if user_manager.is_authorized(user_id_to_add):
            await message.reply_text(f"ℹ️ User `{user_id_to_add}` is already authorized.")
        else:
            user_manager.add_user(user_id_to_add)
            await message.reply_text(f"✅ User `{user_id_to_add}` has been added successfully.")
            
            # Notify the user if possible
            try:
                await client.send_message(
                    user_id_to_add,
                    "🎉 **You've been authorized to use Wasabi Storage Bot!**\n\n"
                    "You can now upload files by sending them to this bot. "
                    "Use /help to see available commands."
                )
            except Exception as e:
                logger.warning(f"Could not notify user {user_id_to_add}: {e}")
                
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** /adduser `<user_id>`")

@app.on_message(filters.command("removeuser"))
@is_admin
async def remove_user_handler(client: Client, message: Message):
    try:
        user_id_to_remove = int(message.text.split(" ", 1)[1])
        if user_id_to_remove == ADMIN_ID:
            await message.reply_text("🚫 You cannot remove the admin.")
            return
        
        if user_manager.is_authorized(user_id_to_remove):
            user_manager.remove_user(user_id_to_remove)
            await message.reply_text(f"🗑 User `{user_id_to_remove}` has been removed.")
        else:
            await message.reply_text("🤷 User not found in the authorized list.")
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** /removeuser `<user_id>`")
        
@app.on_message(filters.command("listusers"))
@is_admin
async def list_users_handler(client: Client, message: Message):
    users = user_manager.get_all_users()
    user_list = "\n".join([f"- `{user_id}`" for user_id in users])
    await message.reply_text(f"👥 **Authorized Users ({len(users)}):**\n{user_list}")

@app.on_message(filters.command("stats"))
@is_authorized
async def stats_handler(client: Client, message: Message):
    """Show bot statistics"""
    # Get bucket stats
    bucket_stats = await get_bucket_stats()
    
    # Get rate limit info
    remaining_uploads = rate_limiter.get_remaining_uploads(message.from_user.id)
    
    stats_text = (
        f"📊 **Bot Statistics**\n\n"
        f"**🤖 Bot Info:**\n"
        f"• Authorized users: {len(user_manager.get_all_users())}\n"
        f"• Wasabi connected: {'✅' if s3_client else '❌'}\n"
        f"• Flask server: {FLASK_HOST}:{FLASK_PORT}\n\n"
        f"**💾 Storage Info:**\n"
        f"• Bucket: {WASABI_BUCKET}\n"
        f"• Region: {WASABI_REGION}\n"
    )
    
    if bucket_stats:
        stats_text += (
            f"• Total files: {bucket_stats['total_files']}\n"
            f"• Total size: {bucket_stats['human_size']}\n"
        )
    
    stats_text += f"\n**👤 Your Info:**\n• Remaining uploads (this hour): {remaining_uploads}/10"
    
    await message.reply_text(stats_text)

@app.on_message(filters.command("broadcast"))
@is_admin
async def broadcast_handler(client: Client, message: Message):
    """Broadcast message to all authorized users"""
    try:
        broadcast_text = message.text.split(" ", 1)[1]
        users = user_manager.get_all_users()
        successful = 0
        failed = 0
        
        status_msg = await message.reply_text(f"📢 Broadcasting to {len(users)} users...")
        
        for user_id in users:
            try:
                await client.send_message(
                    user_id,
                    f"📢 **Broadcast from Admin**\n\n{broadcast_text}"
                )
                successful += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {user_id}: {e}")
                failed += 1
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.1)
        
        await status_msg.edit_text(
            f"📊 **Broadcast Complete**\n\n"
            f"✅ Successful: {successful}\n"
            f"❌ Failed: {failed}\n"
            f"📨 Total: {len(users)}"
        )
        
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** /broadcast `<message>`")

# --- File Handling Logic ---
@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
@is_authorized
async def file_handler(client: Client, message: Message):
    if not s3_client:
        await message.reply_text("❌ **Error:** Wasabi client is not initialized. Check server logs.")
        return

    # Check rate limit
    if rate_limiter.is_limited(message.from_user.id):
        remaining = rate_limiter.get_remaining_uploads(message.from_user.id)
        await message.reply_text(
            f"🚫 **Rate limit exceeded!**\n\n"
            f"You can upload {remaining} more files in the next hour.\n"
            f"Please wait before uploading more files."
        )
        return

    # Get file information
    if message.document:
        media = message.document
        mime_type = media.mime_type or 'application/octet-stream'
    elif message.video:
        media = message.video
        mime_type = 'video/mp4'
    elif message.audio:
        media = message.audio
        mime_type = 'audio/mpeg'
    elif message.photo:
        media = message.photo
        mime_type = 'image/jpeg'
    else:
        await message.reply_text("❌ Unsupported file type.")
        return

    file_name = getattr(media, 'file_name', None)
    if not file_name:
        # Generate filename for photos
        if message.photo:
            file_ext = '.jpg'
        else:
            file_ext = '.bin'
        file_name = f"telegram_{message.id}{file_ext}"
    
    file_size = media.file_size
    
    # Telegram's limit for bots is 2GB for download, 4GB for upload with MTProto API
    if file_size > 4 * 1024 * 1024 * 1024:
        await message.reply_text("❌ **Error:** File is larger than 4GB, which is not supported.")
        return

    status_message = await message.reply_text("🚀 Preparing to process your file...")
    
    # Create unique file path to avoid conflicts
    timestamp = int(time.time())
    safe_filename = f"{timestamp}_{file_name}"
    file_path = f"./downloads/{safe_filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        # 1. Download from Telegram
        await client.download_media(
            message=message,
            file_name=file_path,
            progress=progress_callback,
            progress_args=(status_message, "Downloading...")
        )
        await status_message.edit_text("✅ Download complete. Starting upload to Wasabi...")

        # 2. Upload to Wasabi
        await upload_to_wasabi(file_path, safe_filename, status_message)
        await status_message.edit_text("✅ Upload complete. Generating shareable link...")
        
        # 3. Generate a pre-signed URL (valid for 7 days)
        presigned_url = await generate_presigned_url(safe_filename)
        
        if presigned_url:
            # Determine media type for player
            media_type = get_file_type(mime_type, file_name)
            
            # Encode URL for web player
            encoded_url = base64.urlsafe_b64encode(presigned_url.encode()).decode().rstrip('=')
            
            # Generate web player URL
            web_player_url = f"http://{FLASK_HOST}:{FLASK_PORT}/player/{media_type}/{encoded_url}"
            
            final_message = (
                f"✅ **File Uploaded Successfully!**\n\n"
                f"**File:** `{file_name}`\n"
                f"**Type:** {media_type.title()}\n"
                f"**Size:** {humanbytes(file_size)}\n"
                f"**Stored as:** `{safe_filename}`\n\n"
                f"**🔗 Direct Link (7 days):**\n`{presigned_url}`\n\n"
                f"**🎬 Web Player:**\n{web_player_url}"
            )
            await status_message.edit_text(final_message, disable_web_page_preview=True)
        else:
            await status_message.edit_text(
                f"✅ **File Uploaded Successfully!**\n\n"
                f"**File:** `{file_name}`\n"
                f"**Size:** {humanbytes(file_size)}\n"
                f"**Stored as:** `{safe_filename}`\n"
                f"⚠️ *Could not generate shareable link*"
            )

    except Exception as e:
        logger.error(f"An error occurred during file processing: {e}", exc_info=True)
        await status_message.edit_text(f"❌ **Upload failed:**\n`{str(e)}`")
    finally:
        # 4. Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up local file: {file_path}")
        if status_message.id in last_update_time:
             del last_update_time[status_message.id]

# --- Error Handler ---
@app.on_message(filters.command("reload"))
@is_admin
async def reload_handler(client: Client, message: Message):
    """Reload user data from disk"""
    user_manager.load_users()
    await message.reply_text("✅ User data reloaded from disk.")

# --- Main Execution ---
async def main():
    """Main function to run both Flask and Telegram bot"""
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server thread started")
    
    # Start the Telegram bot
    logger.info("Starting Telegram bot...")
    await app.start()
    
    # Get bot info
    bot_info = await app.get_me()
    logger.info(f"Bot started successfully: @{bot_info.username}")
    
    # Send startup notification to admin
    try:
        await app.send_message(
            ADMIN_ID,
            f"🤖 **Bot Started Successfully**\n\n"
            f"**Bot:** @{bot_info.username}\n"
            f"**Flask:** {FLASK_HOST}:{FLASK_PORT}\n"
            f"**Wasabi:** {'✅ Connected' if s3_client else '❌ Disconnected'}\n"
            f"**Users:** {len(user_manager.get_all_users())} authorized\n"
            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        logger.warning(f"Could not send startup message to admin: {e}")
    
    # Keep the bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        # Ensure proper cleanup
        if app.is_connected:
            asyncio.run(app.stop())
        logger.info("Bot has stopped completely.")