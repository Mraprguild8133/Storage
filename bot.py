import os
import asyncio
import logging
from typing import Optional
from datetime import datetime

from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode, MessageMediaType
from pyrogram.errors import RPCError

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class Config:
    def __init__(self):
        self.API_ID = self.get_env_int("API_ID")
        self.API_HASH = self.get_env_str("API_HASH")
        self.BOT_TOKEN = self.get_env_str("BOT_TOKEN")
        
        # Wasabi config (optional for basic testing)
        self.WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY")
        self.WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY")
        self.WASABI_BUCKET = os.getenv("WASABI_BUCKET")
        self.WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
        self.WASABI_ENDPOINT = f"https://s3.{self.WASABI_REGION}.wasabisys.com"
        
        self.MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
    
    def get_env_int(self, key: str) -> int:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing environment variable: {key}")
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Invalid integer for {key}: {value}")
    
    def get_env_str(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing environment variable: {key}")
        return value
    
    def validate_config(self):
        """Validate all required configuration"""
        required_vars = ["API_ID", "API_HASH", "BOT_TOKEN"]
        for var in required_vars:
            if not getattr(self, var):
                raise ValueError(f"Missing required configuration: {var}")
        
        logger.info("✅ Configuration validated successfully")
        logger.info(f"🤖 Bot Token: {self.BOT_TOKEN[:10]}...")
        logger.info(f"🌐 API ID: {self.API_ID}")

try:
    config = Config()
    config.validate_config()
except Exception as e:
    logger.error(f"❌ Configuration error: {e}")
    exit(1)

# Initialize Pyrogram Client
try:
    app = Client(
        "wasabi_file_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        parse_mode=ParseMode.MARKDOWN,
        sleep_threshold=30
    )
    logger.info("✅ Pyrogram client initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Pyrogram client: {e}")
    exit(1)

# Initialize Wasabi client (if credentials available)
if all([config.WASABI_ACCESS_KEY, config.WASABI_SECRET_KEY, config.WASABI_BUCKET]):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=config.WASABI_ACCESS_KEY,
            aws_secret_access_key=config.WASABI_SECRET_KEY,
            endpoint_url=config.WASABI_ENDPOINT,
            region_name=config.WASABI_REGION
        )
        logger.info("✅ Wasabi client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Wasabi client: {e}")
        s3_client = None
else:
    logger.warning("⚠️ Wasabi credentials not found - file storage disabled")
    s3_client = None

# Create necessary directories
os.makedirs("downloads", exist_ok=True)

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    try:
        logger.info(f"👤 Start command from user {message.from_user.id}")
        
        welcome_text = """
🤖 **Wasabi File Storage Bot**

I can help you store files in Wasabi cloud storage and generate streaming links.

**Commands:**
/start - Show this message
/help - Get help
/stats - Bot statistics
/upload - Upload a file

**Features:**
• Upload files up to 4GB
• Instant streaming links
• MX Player support
• Real-time progress

Just send me any file to get started!
        """
        
        await message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📁 Upload File", callback_data="upload_help")
            ]])
        )
    except RPCError as e:
        logger.error(f"RPCError in start_command: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in start_command: {e}")

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    try:
        help_text = """
🆘 **Help Guide**

**How to use:**
1. Send me any file (document, video, audio)
2. I'll upload it to Wasabi storage
3. You'll get instant streaming links
4. Use MX Player links for Android streaming

**Supported files:**
• Documents (PDF, ZIP, etc.)
• Videos (MP4, AVI, MKV, etc.)
• Audio (MP3, WAV, etc.)
• Images (JPG, PNG, etc.)

**Max file size:** 4GB

**Issues?**
If the bot doesn't respond, try:
• Sending /start again
• Checking your internet connection
• Contacting the bot administrator
        """
        await message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Error in help_command: {e}")

@app.on_message(filters.command("stats"))
async def stats_command(client: Client, message: Message):
    """Handle /stats command"""
    try:
        user = message.from_user
        stats_text = f"""
📊 **Bot Statistics**

**User Info:**
ID: `{user.id}`
Name: {user.first_name}
Username: @{user.username if user.username else 'N/A'}

**Bot Info:**
Max File Size: 4GB
Storage: {'Wasabi Cloud' if s3_client else 'Disabled'}
Status: ✅ Online
        """
        await message.reply_text(stats_text)
    except Exception as e:
        logger.error(f"Error in stats_command: {e}")

@app.on_message(filters.media & filters.private)
async def handle_file_upload(client: Client, message: Message):
    """Handle file uploads"""
    try:
        logger.info(f"📥 Received file from user {message.from_user.id}")
        
        if not s3_client:
            await message.reply_text("❌ File storage is currently disabled. Please contact administrator.")
            return
        
        # Get file info based on media type
        if message.media == MessageMediaType.DOCUMENT:
            file_name = message.document.file_name
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
        elif message.media == MessageMediaType.VIDEO:
            file_name = message.video.file_name or f"video_{message.id}.mp4"
            file_size = message.video.file_size
            mime_type = "video/mp4"
        elif message.media == MessageMediaType.AUDIO:
            file_name = message.audio.file_name or f"audio_{message.id}.mp3"
            file_size = message.audio.file_size
            mime_type = "audio/mpeg"
        elif message.media == MessageMediaType.PHOTO:
            file_name = f"photo_{message.id}.jpg"
            file_size = None  # Photos don't have file_size attribute
            mime_type = "image/jpeg"
        else:
            await message.reply_text("❌ Unsupported media type.")
            return
        
        # Check file size if available
        if file_size and file_size > config.MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ File too large! Maximum size is 4GB.\n"
                f"Your file: {file_size / (1024**3):.2f}GB"
            )
            return
        
        # Send initial processing message
        processing_msg = await message.reply_text(
            f"📥 **Processing File**\n\n"
            f"**Name:** `{file_name}`\n"
            f"**Size:** {file_size / (1024**2):.2f} MB\n"
            f"**Type:** {mime_type}\n\n"
            f"⏳ Downloading..."
        )
        
        # Download file
        download_path = await message.download(
            file_name=f"downloads/{message.id}_{file_name}"
        )
        
        await processing_msg.edit_text("📤 Uploading to Wasabi...")
        
        # Generate S3 key
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"telegram_files/{message.from_user.id}/{timestamp}_{file_name}"
        
        # Upload to Wasabi
        try:
            s3_client.upload_file(download_path, config.WASABI_BUCKET, s3_key)
            
            # Generate streaming URL
            streaming_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': config.WASABI_BUCKET, 'Key': s3_key},
                ExpiresIn=604800  # 7 days
            )
            
            # Create success message
            success_text = f"""
✅ **File Uploaded Successfully!**

**File:** `{file_name}`
**Size:** {file_size / (1024**2):.2f} MB
**Storage:** Wasabi Cloud

**Streaming Links:**
            """
            
            await processing_msg.edit_text(
                success_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 Direct Link", url=streaming_url)],
                    [InlineKeyboardButton("🎬 MX Player", 
                     url=f"intent://{streaming_url.split('//')[1]}#Intent;package=com.mxtech.videoplayer.ad;scheme=https;end")],
                    [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_{streaming_url}")]
                ])
            )
            
            # Cleanup
            os.remove(download_path)
            
        except ClientError as e:
            await processing_msg.edit_text(f"❌ Wasabi upload failed: {str(e)}")
            if os.path.exists(download_path):
                os.remove(download_path)
                
    except RPCError as e:
        logger.error(f"RPCError in handle_file_upload: {e}")
        await message.reply_text("❌ Telegram API error. Please try again.")
    except Exception as e:
        logger.error(f"Unexpected error in handle_file_upload: {e}")
        await message.reply_text("❌ An unexpected error occurred. Please try again.")

@app.on_callback_query(filters.regex(r"copy_.+"))
async def handle_copy_callback(client, callback_query):
    """Handle copy link callback"""
    try:
        url = callback_query.data.replace("copy_", "")
        await callback_query.answer("📋 Link copied to clipboard!", show_alert=True)
        # Note: Actual clipboard copying requires additional setup
    except Exception as e:
        logger.error(f"Error in handle_copy_callback: {e}")

@app.on_callback_query(filters.regex(r"upload_help"))
async def handle_upload_help(client, callback_query):
    """Handle upload help callback"""
    try:
        await callback_query.message.edit_text(
            "📁 **How to Upload**\n\n"
            "Simply send me any file:\n"
            "1. Go to chat\n"
            "2. Click attachment (📎)\n"
            "3. Choose file\n"
            "4. Send it to me\n\n"
            "I'll handle the rest!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")
            ]])
        )
    except Exception as e:
        logger.error(f"Error in handle_upload_help: {e}")

@app.on_callback_query(filters.regex(r"back_to_start"))
async def handle_back_to_start(client, callback_query):
    """Handle back to start callback"""
    try:
        await start_command(client, callback_query.message)
    except Exception as e:
        logger.error(f"Error in handle_back_to_start: {e}")

async def main():
    """Main function to start the bot"""
    try:
        logger.info("🚀 Starting Wasabi File Storage Bot...")
        
        await app.start()
        
        # Get bot info
        me = await app.get_me()
        logger.info(f"✅ Bot started successfully: @{me.username}")
        logger.info(f"🔗 Bot link: https://t.me/{me.username}")
        
        # Send startup notification
        try:
            await app.send_message(
                chat_id=me.id,  # Send to bot's own chat
                text="🤖 **Bot Started Successfully!**\n\n"
                     f"**Username:** @{me.username}\n"
                     f"**ID:** {me.id}\n"
                     f"**Time:** {datetime.now()}"
            )
        except:
            pass  # Ignore if can't send to self
        
        # Wait for events
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
    finally:
        logger.info("🛑 Stopping bot...")
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
