import os
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from pyrogram import Client, filters, types
from pyrogram.enums import ParseMode
from pyrogram.errors import RPCError
import boto3
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramFileBot:
    def __init__(self):
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN')
        
        # Wasabi configuration
        self.wasabi_access_key = os.getenv('WASABI_ACCESS_KEY')
        self.wasabi_secret_key = os.getenv('WASABI_SECRET_KEY')
        self.wasabi_bucket = os.getenv('WASABI_BUCKET')
        self.wasabi_region = os.getenv('WASABI_REGION', 'us-east-1')
        self.storage_channel_id = os.getenv('STORAGE_CHANNEL_ID')
        
        # Initialize clients
        self.app = Client(
            "file_bot",
            api_id=self.api_id,
            api_hash=self.api_hash,
            bot_token=self.bot_token
        )
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f'https://s3.{self.wasabi_region}.wasabisys.com',
            aws_access_key_id=self.wasabi_access_key,
            aws_secret_access_key=self.wasabi_secret_key,
            region_name=self.wasabi_region
        )
        
        # File database (in production, use a proper database)
        self.files_db: Dict[str, Dict] = {}
        
        # Register handlers
        self.register_handlers()
    
    def register_handlers(self):
        """Register all bot command handlers"""
        
        @self.app.on_message(filters.command("start"))
        async def start_command(client, message):
            await self.handle_start(message)
        
        @self.app.on_message(filters.command("help"))
        async def help_command(client, message):
            await self.handle_help(message)
        
        @self.app.on_message(filters.command("upload"))
        async def upload_command(client, message):
            await self.handle_upload_prompt(message)
        
        @self.app.on_message(filters.command("download"))
        async def download_command(client, message):
            await self.handle_download(message)
        
        @self.app.on_message(filters.command("list"))
        async def list_command(client, message):
            await self.handle_list_files(message)
        
        @self.app.on_message(filters.command("stream"))
        async def stream_command(client, message):
            await self.handle_stream(message)
        
        @self.app.on_message(filters.command("setchannel"))
        async def setchannel_command(client, message):
            await self.handle_set_channel(message)
        
        @self.app.on_message(filters.command("test"))
        async def test_command(client, message):
            await self.handle_test_wasabi(message)
        
        @self.app.on_message(filters.command("web"))
        async def web_command(client, message):
            await self.handle_web_player(message)
        
        @self.app.on_message(filters.document | filters.video | filters.audio | filters.photo)
        async def handle_file_upload(client, message):
            await self.handle_file_receive(message)
    
    async def handle_start(self, message):
        """Handle /start command"""
        welcome_text = """
🤖 **Telegram File Bot with Wasabi Storage**

**Features:**
• 📁 Upload files up to 4GB
• ☁️ Wasabi Cloud Storage integration
• 📱 Mobile-optimized interface
• 🎬 Direct streaming to MX Player & VLC
• 📥 Direct download links
• 🔄 Real-time progress tracking

**Available Commands:**
/upload - Upload a file
/download - Download a file
/list - List all files  
/stream - Get streaming link
/web - Web player interface
/setchannel - Set storage channel
/test - Test Wasabi connection
/help - Show help

Simply send any file to upload it!
        """
        
        keyboard = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("📤 Upload File", callback_data="upload_help")],
            [types.InlineKeyboardButton("📥 Download Files", callback_data="list_files")],
            [types.InlineKeyboardButton("🎬 Streaming Help", callback_data="stream_help")],
            [types.InlineKeyboardButton("⚙️ Bot Settings", callback_data="settings")]
        ])
        
        await message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_help(self, message):
        """Handle /help command"""
        help_text = """
**📖 Bot Help Guide**

**Uploading Files:**
• Send any file directly to the bot
• Use /upload command for instructions
• Supports: Documents, Videos, Audio, Photos
• Max size: 4GB

**Downloading Files:**
• Use /list to see all files
• Use /download <file_id> to download
• Get direct download links

**Streaming:**
• Use /stream <file_id> for streaming links
• MX Player: One-click Android playback
• VLC: Direct VLC player integration
• Web: Browser-based player via /web

**Storage:**
• Files stored in Wasabi Cloud
• Optional Telegram channel backup
• Fast global CDN access

**Mobile Optimization:**
• Responsive design for phones/tablets
• MX Player deep linking
• Touch-friendly interfaces
        """
        
        await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_upload_prompt(self, message):
        """Prompt user to upload a file"""
        text = """
**📤 Upload Instructions:**

Simply send me any file (document, video, audio, or photo) and I'll upload it to Wasabi cloud storage.

**Supported formats:**
• 📄 Documents (PDF, ZIP, etc.)
• 🎥 Videos (MP4, MKV, AVI, etc.)
• 🎵 Audio (MP3, FLAC, WAV, etc.)
• 🖼️ Photos (JPEG, PNG, etc.)

**Max file size:** 4GB

Go ahead and send your file now!
        """
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_file_receive(self, message):
        """Handle incoming files and upload to Wasabi"""
        try:
            # Determine file type and get file info
            if message.document:
                file_type = "document"
                file_size = message.document.file_size
                file_name = message.document.file_name
                mime_type = message.document.mime_type
            elif message.video:
                file_type = "video"
                file_size = message.video.file_size
                file_name = message.video.file_name or f"video_{message.id}.mp4"
                mime_type = "video/mp4"
            elif message.audio:
                file_type = "audio"
                file_size = message.audio.file_size
                file_name = message.audio.file_name or f"audio_{message.id}.mp3"
                mime_type = "audio/mpeg"
            elif message.photo:
                file_type = "photo"
                file_size = message.photo.file_size
                file_name = f"photo_{message.id}.jpg"
                mime_type = "image/jpeg"
            else:
                await message.reply_text("❌ Unsupported file type")
                return
            
            # Check file size (4GB limit)
            if file_size > 4 * 1024 * 1024 * 1024:
                await message.reply_text("❌ File size exceeds 4GB limit")
                return
            
            # Notify user
            status_msg = await message.reply_text(
                f"📤 Uploading {file_name} ({self.format_size(file_size)})..."
            )
            
            # Generate unique file ID
            file_id = f"file_{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            s3_key = f"files/{file_id}_{file_name}"
            
            # Download file from Telegram with progress
            download_path = f"temp_{file_id}"
            await self.download_file_with_progress(message, download_path, status_msg, "Downloading")
            
            # Upload to Wasabi with progress
            await self.upload_to_wasabi_with_progress(download_path, s3_key, status_msg, "Uploading")
            
            # Store file metadata
            self.files_db[file_id] = {
                'file_name': file_name,
                'file_size': file_size,
                'file_type': file_type,
                'mime_type': mime_type,
                's3_key': s3_key,
                'upload_date': datetime.now().isoformat(),
                'uploaded_by': message.from_user.id if message.from_user else None
            }
            
            # Optional: Backup to Telegram channel
            if self.storage_channel_id:
                await self.backup_to_channel(message, file_id)
            
            # Cleanup temp file
            if os.path.exists(download_path):
                os.remove(download_path)
            
            # Send success message with options
            keyboard = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("📥 Download", callback_data=f"dl_{file_id}")],
                [types.InlineKeyboardButton("🎬 Stream", callback_data=f"stream_{file_id}"),
                 types.InlineKeyboardButton("🌐 Web Player", callback_data=f"web_{file_id}")],
                [types.InlineKeyboardButton("📋 File Info", callback_data=f"info_{file_id}")]
            ])
            
            await status_msg.edit_text(
                f"✅ **Upload Successful!**\n\n"
                f"📁 **File:** {file_name}\n"
                f"📊 **Size:** {self.format_size(file_size)}\n"
                f"🆔 **ID:** `{file_id}`\n"
                f"📦 **Storage:** Wasabi Cloud\n\n"
                f"Use `/download {file_id}` to download",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await message.reply_text(f"❌ Upload failed: {str(e)}")
    
    async def download_file_with_progress(self, message, file_path, status_msg, operation):
        """Download file with progress updates"""
        try:
            # This is a simplified version - in practice you'd use pyrogram's download_media
            # with progress callbacks
            await message.download(file_name=file_path)
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
    
    async def upload_to_wasabi_with_progress(self, file_path, s3_key, status_msg, operation):
        """Upload file to Wasabi with progress tracking"""
        try:
            config = TransferConfig(
                multipart_threshold=1024 * 25,
                max_concurrency=10,
                multipart_chunksize=1024 * 25,
                use_threads=True
            )
            
            self.s3_client.upload_file(
                file_path,
                self.wasabi_bucket,
                s3_key,
                Config=config,
                Callback=None  # Add progress callback here
            )
            
        except ClientError as e:
            raise Exception(f"Wasabi upload failed: {str(e)}")
    
    async def handle_download(self, message):
        """Handle /download command"""
        try:
            if len(message.command) < 2:
                await message.reply_text("❌ Usage: /download <file_id>")
                return
            
            file_id = message.command[1]
            if file_id not in self.files_db:
                await message.reply_text("❌ File not found")
                return
            
            file_info = self.files_db[file_id]
            download_url = self.generate_download_url(file_info['s3_key'])
            
            keyboard = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("📥 Direct Download", url=download_url)],
                [types.InlineKeyboardButton("🎬 Stream in MX Player", 
                                          url=self.generate_mx_player_url(download_url))],
                [types.InlineKeyboardButton("🔵 Open in VLC", 
                                          url=self.generate_vlc_url(download_url))]
            ])
            
            await message.reply_text(
                f"**📥 Download Options**\n\n"
                f"📁 **File:** {file_info['file_name']}\n"
                f"📊 **Size:** {self.format_size(file_info['file_size'])}\n"
                f"📝 **Type:** {file_info['file_type']}\n\n"
                f"Choose your preferred download method:",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await message.reply_text(f"❌ Download failed: {str(e)}")
    
    async def handle_list_files(self, message):
        """Handle /list command - show all files"""
        if not self.files_db:
            await message.reply_text("📭 No files stored yet")
            return
        
        files_text = "**📁 Stored Files:**\n\n"
        for file_id, file_info in list(self.files_db.items())[:10]:  # Show first 10
            files_text += (
                f"🆔 `{file_id}`\n"
                f"📝 {file_info['file_name']}\n"
                f"📊 {self.format_size(file_info['file_size'])}\n"
                f"⏰ {file_info['upload_date'][:10]}\n\n"
            )
        
        if len(self.files_db) > 10:
            files_text += f"... and {len(self.files_db) - 10} more files"
        
        keyboard = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("📥 Download Files", callback_data="download_list")],
            [types.InlineKeyboardButton("🎬 Stream Files", callback_data="stream_list")]
        ])
        
        await message.reply_text(files_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_stream(self, message):
        """Handle /stream command"""
        try:
            if len(message.command) < 2:
                await message.reply_text("❌ Usage: /stream <file_id>")
                return
            
            file_id = message.command[1]
            if file_id not in self.files_db:
                await message.reply_text("❌ File not found")
                return
            
            file_info = self.files_db[file_id]
            stream_url = self.generate_download_url(file_info['s3_key'])
            
            keyboard = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("🎬 MX Player (Android)", 
                                          url=self.generate_mx_player_url(stream_url))],
                [types.InlineKeyboardButton("🔵 VLC Player", 
                                          url=self.generate_vlc_url(stream_url))],
                [types.InlineKeyboardButton("🌐 Web Player", 
                                          callback_data=f"web_{file_id}")],
                [types.InlineKeyboardButton("📥 Download", callback_data=f"dl_{file_id}")]
            ])
            
            await message.reply_text(
                f"**🎬 Streaming Options**\n\n"
                f"📁 **File:** {file_info['file_name']}\n"
                f"📊 **Size:** {self.format_size(file_info['file_size'])}\n"
                f"🎞️ **Type:** {file_info['file_type']}\n\n"
                f"Choose your preferred player:",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await message.reply_text(f"❌ Streaming setup failed: {str(e)}")
    
    async def handle_web_player(self, message):
        """Handle /web command - web player interface"""
        try:
            if len(message.command) < 2:
                await message.reply_text("❌ Usage: /web <file_id>")
                return
            
            file_id = message.command[1]
            if file_id not in self.files_db:
                await message.reply_text("❌ File not found")
                return
            
            file_info = self.files_db[file_id]
            stream_url = self.generate_download_url(file_info['s3_key'])
            
            # Create simple HTML player page
            html_content = self.generate_web_player_html(file_info, stream_url)
            
            # In a real implementation, you'd host this HTML somewhere
            # For now, we'll provide direct links
            keyboard = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("🎬 Direct Stream", url=stream_url)],
                [types.InlineKeyboardButton("📥 Download", url=stream_url)],
                [types.InlineKeyboardButton("📱 MX Player", 
                                          url=self.generate_mx_player_url(stream_url))]
            ])
            
            await message.reply_text(
                f"**🌐 Web Player Interface**\n\n"
                f"📁 **File:** {file_info['file_name']}\n"
                f"🔗 **Direct URL:** `{stream_url}`\n\n"
                f"Use the buttons below to play or download:",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await message.reply_text(f"❌ Web player failed: {str(e)}")
    
    async def handle_set_channel(self, message):
        """Handle /setchannel command"""
        try:
            if len(message.command) < 2:
                await message.reply_text("❌ Usage: /setchannel <channel_id>")
                return
            
            channel_id = message.command[1]
            self.storage_channel_id = channel_id
            
            await message.reply_text(f"✅ Storage channel set to: {channel_id}")
            
        except Exception as e:
            await message.reply_text(f"❌ Failed to set channel: {str(e)}")
    
    async def handle_test_wasabi(self, message):
        """Handle /test command - test Wasabi connection"""
        try:
            # Test S3 connection by listing buckets
            response = self.s3_client.list_buckets()
            bucket_names = [bucket['Name'] for bucket in response['Buckets']]
            
            if self.wasabi_bucket in bucket_names:
                await message.reply_text(
                    f"✅ **Wasabi Connection Test**\n\n"
                    f"🔗 **Status:** Connected\n"
                    f"📦 **Bucket:** {self.wasabi_bucket}\n"
                    f"🌐 **Region:** {self.wasabi_region}\n"
                    f"📊 **Total Buckets:** {len(bucket_names)}\n\n"
                    f"Wasabi storage is working correctly!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.reply_text("❌ Bucket not found")
                
        except Exception as e:
            await message.reply_text(f"❌ Wasabi test failed: {str(e)}")
    
    async def backup_to_channel(self, message, file_id):
        """Backup file to Telegram channel"""
        try:
            if not self.storage_channel_id:
                return
            
            file_info = self.files_db[file_id]
            caption = (
                f"📁 {file_info['file_name']}\n"
                f"📊 {self.format_size(file_info['file_size'])}\n"
                f"🆔 {file_id}\n"
                f"⏰ {file_info['upload_date']}"
            )
            
            # Forward the message to storage channel
            await message.forward(int(self.storage_channel_id))
            
        except Exception as e:
            logger.error(f"Channel backup failed: {e}")
    
    def generate_download_url(self, s3_key, expires=3600):
        """Generate presigned URL for download"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.wasabi_bucket,
                    'Key': s3_key
                },
                ExpiresIn=expires
            )
            return url
        except ClientError as e:
            raise Exception(f"URL generation failed: {str(e)}")
    
    def generate_mx_player_url(self, stream_url):
        """Generate MX Player deep link"""
        return f"intent://{stream_url}#Intent;package=com.mxtech.videoplayer.ad;scheme=http;end"
    
    def generate_vlc_url(self, stream_url):
        """Generate VLC Player deep link"""
        return f"vlc://{stream_url}"
    
    def generate_web_player_html(self, file_info, stream_url):
        """Generate HTML for web player"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Streaming: {file_info['file_name']}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                video {{ width: 100%; max-width: 800px; }}
                .mobile-optimized {{ max-width: 100%; }}
            </style>
        </head>
        <body>
            <h2>{file_info['file_name']}</h2>
            <video controls class="mobile-optimized">
                <source src="{stream_url}" type="{file_info['mime_type']}">
                Your browser does not support the video tag.
            </video>
            <p><a href="{stream_url}" download>Download File</a></p>
        </body>
        </html>
        """
        return html
    
    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names)-1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.2f} {size_names[i]}"
    
    async def start(self):
        """Start the bot"""
        logger.info("Starting Telegram File Bot...")
        await self.app.start()
        logger.info("Bot started successfully!")
        
        # Test Wasabi connection
        try:
            self.s3_client.list_buckets()
            logger.info("Wasabi connection successful!")
        except Exception as e:
            logger.error(f"Wasabi connection failed: {e}")
        
        await self.app.idle()
    
    async def stop(self):
        """Stop the bot"""
        await self.app.stop()

# Create and run bot
if __name__ == "__main__":
    bot = TelegramFileBot()
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        asyncio.run(bot.stop())