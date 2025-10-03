import os
import time
import math
import asyncio
import logging
import mimetypes
import hashlib
from functools import wraps
from urllib.parse import quote, urlparse

import boto3
from botocore.exceptions import ClientError
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

# Import configuration
from config import config

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
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

# Auto-detect streaming domains based on Wasabi region
STREAMING_DOMAINS = {
    'us-east-1': [
        f"https://s3.us-east-1.wasabisys.com/{WASABI_BUCKET}",
        f"https://{WASABI_BUCKET}.s3.us-east-1.wasabisys.com"
    ],
    'us-east-2': [
        f"https://s3.us-east-2.wasabisys.com/{WASABI_BUCKET}",
        f"https://{WASABI_BUCKET}.s3.us-east-2.wasabisys.com"
    ],
    'us-central-1': [
        f"https://s3.us-central-1.wasabisys.com/{WASABI_BUCKET}",
        f"https://{WASABI_BUCKET}.s3.us-central-1.wasabisys.com"
    ],
    'us-west-1': [
        f"https://s3.us-west-1.wasabisys.com/{WASABI_BUCKET}",
        f"https://{WASABI_BUCKET}.s3.us-west-1.wasabisys.com"
    ],
    'eu-central-1': [
        f"https://s3.eu-central-1.wasabisys.com/{WASABI_BUCKET}",
        f"https://{WASABI_BUCKET}.s3.eu-central-1.wasabisys.com"
    ],
}

# Fallback domains if region not found
DEFAULT_STREAMING_DOMAINS = [
    f"https://s3.{WASABI_REGION}.wasabisys.com/{WASABI_BUCKET}",
    f"https://{WASABI_BUCKET}.s3.{WASABI_REGION}.wasabisys.com"
]

ALLOWED_USERS = {ADMIN_ID}

# Store file information for callback handling
file_store = {}

# Initialize S3 client
s3_client = None

# --- Bot Initialization ---
try:
    app = Client(
        "wasabi_bot", 
        api_id=API_ID, 
        api_hash=API_HASH, 
        bot_token=BOT_TOKEN,
        workers=3,
        sleep_threshold=60
    )
    logger.info("Pyrogram client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Pyrogram client: {e}")
    raise

# --- Initialize S3 Client ---
def init_s3_client():
    global s3_client
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
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Wasabi: {e}")
        s3_client = None
        return False

# --- Helpers & Decorators ---
def is_admin(func):
    @wraps(func)
    async def wrapper(client, message):
        if message.from_user.id == ADMIN_ID:
            await func(client, message)
        else:
            await message.reply_text("⛔️ Access denied. This command is for the admin only.")
    return wrapper

def is_authorized(func):
    @wraps(func)
    async def wrapper(client, message):
        if message.from_user.id in ALLOWED_USERS:
            await func(client, message)
        else:
            await message.reply_text("⛔️ You are not authorized to use this bot. Contact the admin.")
    return wrapper

def humanbytes(size):
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

def get_streamable_domains():
    """Get streaming domains for current region"""
    return STREAMING_DOMAINS.get(WASABI_REGION, DEFAULT_STREAMING_DOMAINS)

def is_streamable_file(filename):
    """Check if file type is streamable"""
    streamable_extensions = {
        'video': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'],
        'audio': ['.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg', '.wma', '.opus'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        'document': ['.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx']
    }
    
    ext = os.path.splitext(filename)[1].lower()
    for file_type, extensions in streamable_extensions.items():
        if ext in extensions:
            return file_type
    return None

def generate_direct_links(filename):
    """Generate direct streaming links for different domains"""
    domains = get_streamable_domains()
    encoded_filename = quote(filename)
    
    direct_links = []
    for domain in domains:
        direct_link = f"{domain}/{encoded_filename}"
        direct_links.append(direct_link)
    
    return direct_links

def generate_online_player_links(filename, file_type):
    """Generate links for online players"""
    encoded_filename = quote(filename)
    domains = get_streamable_domains()
    primary_domain = domains[0]
    direct_url = f"{primary_domain}/{encoded_filename}"
    
    players = {}
    
    if file_type == 'video':
        players = {
            "🎬 Direct Play": direct_url,
            "📱 VLC": f"vlc://{direct_url}",
            "🔗 Download": direct_url,
        }
    elif file_type == 'audio':
        players = {
            "🎵 Direct Play": direct_url,
            "🔗 Download": direct_url,
        }
    elif file_type == 'image':
        players = {
            "🖼️ View Image": direct_url,
        }
    elif file_type == 'document':
        players = {
            "📄 View Online": direct_url,
            "🔗 Download": direct_url,
        }
    
    return players

def generate_file_hash(filename):
    """Generate short hash for callback data"""
    return hashlib.md5(filename.encode()).hexdigest()[:8]

def create_streaming_keyboard(file_hash, filename, file_type):
    """Create inline keyboard with streaming options"""
    players = generate_online_player_links(filename, file_type)
    keyboard = []
    
    for player_name, player_url in players.items():
        keyboard.append([InlineKeyboardButton(player_name, url=player_url)])
    
    # Add copy links button with short hash
    keyboard.append([InlineKeyboardButton("📋 Copy All Links", callback_data=f"links_{file_hash}")])
    
    return InlineKeyboardMarkup(keyboard)

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
async def upload_to_wasabi(file_path, file_name, status_message):
    """Upload file to Wasabi with retry logic and progress tracking."""
    if not s3_client:
        raise Exception("Wasabi client not initialized")
        
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

# --- Bot Command Handlers ---
@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    logger.info(f"Start command received from user {message.from_user.id}")
    await message.reply_text(
        f"👋 Welcome!\n\n"
        f"**Wasabi Storage Bot** 📦\n\n"
        f"• Upload files to Wasabi cloud storage\n"
        f"• Generate direct streaming links\n"
        f"• Online player options for media files\n"
        f"• Fast and secure file sharing\n\n"
        f"Your User ID: `{message.from_user.id}`\n\n"
        f"Just send me any file to get started!\n\n"
        f"**Bot Status:** {'✅ Connected' if s3_client else '❌ Wasabi Not Connected'}"
    )

@app.on_message(filters.command("ping"))
async def ping_handler(client: Client, message: Message):
    """Simple ping command to test if bot is responsive"""
    start_time = time.time()
    msg = await message.reply_text("🏓 Pong!")
    end_time = time.time()
    response_time = round((end_time - start_time) * 1000, 2)
    
    await msg.edit_text(
        f"🏓 **Pong!**\n"
        f"**Response Time:** {response_time}ms\n"
        f"**Wasabi Status:** {'✅ Connected' if s3_client else '❌ Disconnected'}\n"
        f"**Bot Uptime:** {time.time() - start_time:.2f}s"
    )

@app.on_message(filters.command("status"))
async def status_handler(client: Client, message: Message):
    """Check bot status"""
    status_text = (
        f"🤖 **Bot Status**\n\n"
        f"**Pyrogram:** ✅ Connected\n"
        f"**Wasabi S3:** {'✅ Connected' if s3_client else '❌ Disconnected'}\n"
        f"**Authorized Users:** {len(ALLOWED_USERS)}\n"
        f"**Stored Files Info:** {len(file_store)}\n"
        f"**Bucket:** {WASABI_BUCKET}\n"
        f"**Region:** {WASABI_REGION}\n\n"
        f"**Commands:**\n"
        f"• /start - Start bot\n"
        f"• /ping - Test response\n"
        f"• /status - This message\n"
        f"• /streaminfo - Streaming info\n"
        f"• Send any file to upload"
    )
    await message.reply_text(status_text)

@app.on_message(filters.command("streaminfo"))
async def stream_info_handler(client: Client, message: Message):
    """Show streaming information"""
    domains = get_streamable_domains()
    domains_text = "\n".join([f"• `{domain}`" for domain in domains])
    
    await message.reply_text(
        f"🌐 **Streaming Information**\n\n"
        f"**Region:** `{WASABI_REGION}`\n"
        f"**Bucket:** `{WASABI_BUCKET}`\n\n"
        f"**Available Domains:**\n{domains_text}\n\n"
        f"**Supported Formats:**\n"
        f"• Video: MP4, MKV, AVI, MOV, WebM\n"
        f"• Audio: MP3, M4A, WAV, FLAC, AAC\n"
        f"• Images: JPG, PNG, GIF, WebP\n"
        f"• Documents: PDF, DOC, PPT, TXT"
    )

@app.on_message(filters.command("adduser"))
@is_admin
async def add_user_handler(client: Client, message: Message):
    try:
        user_id_to_add = int(message.text.split(" ", 1)[1])
        ALLOWED_USERS.add(user_id_to_add)
        await message.reply_text(f"✅ User `{user_id_to_add}` has been added successfully.")
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
        if user_id_to_remove in ALLOWED_USERS:
            ALLOWED_USERS.remove(user_id_to_remove)
            await message.reply_text(f"🗑 User `{user_id_to_remove}` has been removed.")
        else:
            await message.reply_text("🤷 User not found in the authorized list.")
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** /removeuser `<user_id>`")
        
@app.on_message(filters.command("listusers"))
@is_admin
async def list_users_handler(client: Client, message: Message):
    user_list = "\n".join([f"- `{user_id}`" for user_id in ALLOWED_USERS])
    await message.reply_text(f"👥 **Authorized Users:**\n{user_list}")

@app.on_message(filters.command("stats"))
@is_admin
async def stats_handler(client: Client, message: Message):
    """Show bot statistics"""
    domains = get_streamable_domains()
    stats_text = (
        f"🤖 **Bot Statistics**\n"
        f"• Authorized users: {len(ALLOWED_USERS)}\n"
        f"• Wasabi connected: {'✅' if s3_client else '❌'}\n"
        f"• Bucket: {WASABI_BUCKET}\n"
        f"• Region: {WASABI_REGION}\n"
        f"• Streaming domains: {len(domains)}\n"
        f"• Stored files: {len(file_store)}\n"
        f"• Storage: Wasabi Cloud"
    )
    await message.reply_text(stats_text)

@app.on_message(filters.command("cleanup"))
@is_admin
async def manual_cleanup_handler(client: Client, message: Message):
    """Manual cleanup of file store"""
    initial_count = len(file_store)
    
    # Remove entries older than 1 hour
    current_time = time.time()
    expired_entries = []
    
    for file_hash, file_data in file_store.items():
        if current_time - file_data['timestamp'] > 3600:  # 1 hour
            expired_entries.append(file_hash)
    
    for file_hash in expired_entries:
        del file_store[file_hash]
    
    await message.reply_text(
        f"🧹 **Cleanup Complete**\n"
        f"• Removed entries: {len(expired_entries)}\n"
        f"• Remaining entries: {len(file_store)}\n"
        f"• Total cleaned: {initial_count - len(file_store)}"
    )

# --- Callback Query Handler ---
@app.on_callback_query(filters.regex(r"^links_"))
async def copy_links_callback(client, callback_query):
    """Handle copy links callback"""
    file_hash = callback_query.data.replace("links_", "")
    
    # Find filename from stored data
    filename = None
    file_type = None
    for stored_hash, stored_data in file_store.items():
        if stored_hash == file_hash:
            filename = stored_data.get('filename')
            file_type = stored_data.get('file_type')
            break
    
    if not filename:
        await callback_query.answer("File information not found or expired", show_alert=True)
        return
    
    direct_links = generate_direct_links(filename)
    players = generate_online_player_links(filename, file_type)
    
    links_text = "🔗 **All Available Links:**\n\n"
    
    # Add direct links
    links_text += "**Direct Links:**\n"
    for i, link in enumerate(direct_links[:3], 1):  # Limit to 3 links
        links_text += f"{i}. `{link}`\n"
    
    # Add player links
    links_text += "\n**Online Players:**\n"
    for player_name, player_url in players.items():
        links_text += f"• {player_name}: `{player_url}`\n"
    
    # Clean up old stored data (keep only last 100 entries)
    if len(file_store) > 100:
        oldest_key = next(iter(file_store))
        del file_store[oldest_key]
    
    try:
        # Send as a separate message
        await callback_query.message.reply_text(links_text)
        await callback_query.answer("📋 Links sent in chat!")
    except Exception as e:
        logger.error(f"Failed to send links: {e}")
        await callback_query.answer("❌ Failed to send links", show_alert=True)

# --- File Handling Logic ---
@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
@is_authorized
async def file_handler(client: Client, message: Message):
    if not s3_client:
        await message.reply_text("❌ **Error:** Wasabi client is not initialized. Check server logs.")
        return

    # Get file information
    if message.document:
        media = message.document
        file_name = media.file_name
    elif message.video:
        media = message.video
        file_name = media.file_name or f"video_{int(time.time())}.mp4"
    elif message.audio:
        media = message.audio
        file_name = media.file_name or f"audio_{int(time.time())}.mp3"
    elif message.photo:
        media = message.photo
        file_name = f"photo_{int(time.time())}.jpg"
    else:
        await message.reply_text("❌ Unsupported file type.")
        return

    file_size = media.file_size
    
    # Check file size limit
    if file_size and file_size > 4 * 1024 * 1024 * 1024:
        await message.reply_text("❌ **Error:** File is larger than 4GB, which is not supported.")
        return

    status_message = await message.reply_text("🚀 Preparing to process your file...")
    
    # Create unique file path
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
        await status_message.edit_text("✅ Upload complete. Generating streaming links...")
        
        # 3. Check if file is streamable
        file_type = is_streamable_file(file_name)
        
        if file_type:
            # Generate file hash for callback data
            file_hash = generate_file_hash(safe_filename)
            
            # Store file information
            file_store[file_hash] = {
                'filename': safe_filename,
                'original_name': file_name,
                'file_type': file_type,
                'timestamp': time.time()
            }
            
            # Clean up old entries if store gets too large
            if len(file_store) > 150:
                # Remove oldest 50 entries
                sorted_entries = sorted(file_store.items(), key=lambda x: x[1]['timestamp'])
                for i in range(min(50, len(sorted_entries))):
                    del file_store[sorted_entries[i][0]]
                logger.info(f"Cleaned up 50 old file store entries")
            
            # Create message with streaming options
            stream_message = (
                f"🎉 **File Uploaded Successfully!**\n\n"
                f"**File:** `{file_name}`\n"
                f"**Type:** {file_type.title()}\n"
                f"**Size:** {humanbytes(file_size)}\n"
                f"**Stored as:** `{safe_filename}`\n\n"
                f"**Streaming Ready!** 🌐\n"
                f"Choose your preferred option below:"
            )
            
            # Create inline keyboard with streaming options
            keyboard = create_streaming_keyboard(file_hash, safe_filename, file_type)
            
            await status_message.edit_text(stream_message, reply_markup=keyboard)
            
        else:
            # For non-streamable files, generate presigned URL
            presigned_url = await generate_presigned_url(safe_filename)
            if presigned_url:
                final_message = (
                    f"✅ **File Uploaded Successfully!**\n\n"
                    f"**File:** `{file_name}`\n"
                    f"**Size:** {humanbytes(file_size)}\n"
                    f"**Stored as:** `{safe_filename}`\n"
                    f"**Download Link (7 days):**\n"
                    f"`{presigned_url}`"
                )
                await status_message.edit_text(final_message, disable_web_page_preview=True)
            else:
                await status_message.edit_text(
                    f"✅ **File Uploaded Successfully!**\n\n"
                    f"**File:** `{file_name}`\n"
                    f"**Size:** {humanbytes(file_size)}\n"
                    f"**Stored as:** `{safe_filename}`\n"
                    f"⚠️ *Could not generate download link*"
                )

    except Exception as e:
        logger.error(f"An error occurred during file processing: {e}", exc_info=True)
        await status_message.edit_text(f"❌ **Upload failed:**\n`{str(e)}`")
    finally:
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up local file: {file_path}")
        if status_message.id in last_update_time:
             del last_update_time[status_message.id]

# --- Startup Handler ---
@app.on_message(filters.command("init"))
async def init_handler(client: Client, message: Message):
    """Initialize bot and start background tasks"""
    await message.reply_text("🤖 Bot is running and ready!")

# --- Main Execution ---
async def main():
    """Main function to start the bot"""
    logger.info("Starting Wasabi Bot...")
    
    # Initialize S3 client
    if not init_s3_client():
        logger.warning("Wasabi S3 client initialization failed, but continuing with bot startup...")
    
    # Start the bot
    await app.start()
    logger.info("Bot started successfully!")
    
    # Get bot info
    bot = await app.get_me()
    logger.info(f"Bot @{bot.username} is now running!")
    
    # Send startup message
    try:
        await app.send_message(
            ADMIN_ID, 
            f"🤖 **Bot Started Successfully!**\n"
            f"**Bot:** @{bot.username}\n"
            f"**Wasabi:** {'✅ Connected' if s3_client else '❌ Disconnected'}\n"
            f"**Time:** {time.ctime()}"
        )
    except Exception as e:
        logger.warning(f"Could not send startup message to admin: {e}")
    
    # Wait until stopped
    await idle()
    
    # Stop the bot
    await app.stop()
    logger.info("Bot stopped successfully!")

if __name__ == "__main__":
    try:
        # Create downloads directory if it doesn't exist
        os.makedirs("./downloads", exist_ok=True)
        
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed with error: {e}")
        raise
