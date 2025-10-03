import logging
import os
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import SessionPasswordNeeded
from config import config
from wasabi_client import wasabi_client
from database import db
from file_handlers import FileHandler
from keyboards import (
    get_main_keyboard, 
    get_file_options_keyboard,
    get_confirmation_keyboard
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramFileBot:
    def __init__(self):
        # Check if session file exists, if not we'll create it
        self.session_name = "file_bot_session"
        
        self.app = Client(
            self.session_name,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workers=100,
            sleep_threshold=60
        )
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup message and callback handlers"""
        
        # Start command
        @self.app.on_message(filters.command("start"))
        async def start_command(client, message: Message):
            welcome_text = (
                "🤖 **Welcome to File Storage Bot!**\n\n"
                "**Features:**\n"
                "✅ Store files up to 4GB\n"
                "✅ Wasabi Cloud Storage\n"
                "✅ Direct streaming links\n"
                "✅ MX Player & VLC support\n"
                "✅ Mobile optimized\n\n"
                "**Available Commands:**\n"
                "📤 /upload - Upload a file\n"
                "📥 /download <id> - Download file\n"
                "📺 /stream <id> - Stream file\n"
                "📋 /list - List your files\n"
                "🔄 /test - Test Wasabi connection\n"
                "🌐 /web <id> - Web player link\n"
                "ℹ️ /help - Show help\n\n"
                "**Quick Start:** Just send me any file to upload!"
            )
            
            await message.reply_text(
                welcome_text,
                reply_markup=get_main_keyboard()
            )
        
        # Upload command
        @self.app.on_message(filters.command("upload"))
        async def upload_command(client, message: Message):
            await message.reply("📤 Please send the file you want to upload...")
        
        # Download command
        @self.app.on_message(filters.command("download"))
        async def download_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply("❌ Please provide file ID. Usage: `/download <file_id>`")
                return
            
            file_id = message.command[1]
            await FileHandler.handle_file_download(client, message, file_id)
        
        # Stream command
        @self.app.on_message(filters.command("stream"))
        async def stream_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply("❌ Please provide file ID. Usage: `/stream <file_id>`")
                return
            
            file_id = message.command[1]
            await FileHandler.handle_file_stream(client, message, file_id)
        
        # List command
        @self.app.on_message(filters.command("list"))
        async def list_command(client, message: Message):
            await FileHandler.handle_file_list(client, message)
        
        # Test command
        @self.app.on_message(filters.command("test"))
        async def test_command(client, message: Message):
            test_result = await wasabi_client.test_connection()
            
            if test_result['success']:
                await message.reply("✅ **Wasabi Connection Test**\n\nConnection successful! All systems operational.")
            else:
                await message.reply(f"❌ **Wasabi Connection Test**\n\nConnection failed: {test_result['error']}")
        
        # Web player command
        @self.app.on_message(filters.command("web"))
        async def web_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply("❌ Please provide file ID. Usage: `/web <file_id>`")
                return
            
            file_id = message.command[1]
            file_info = db.get_file(file_id)
            
            if not file_info:
                await message.reply("❌ File not found.")
                return
            
            url_result = await wasabi_client.generate_presigned_url(file_info['wasabi_key'])
            
            if url_result['success']:
                # Simple HTML player URL (you can replace with your own web player)
                web_url = f"https://player.url.net/?url={url_result['url']}"
                await message.reply(
                    f"🌐 **Web Player**\n\n"
                    f"Click below to open web player:\n{web_url}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌐 Open Web Player", url=web_url)]
                    ])
                )
            else:
                await message.reply("❌ Failed to generate web player link.")
        
        # Help command
        @self.app.on_message(filters.command("help"))
        async def help_command(client, message: Message):
            help_text = (
                "🤖 **File Storage Bot Help**\n\n"
                "**Basic Usage:**\n"
                "1. Send any file to upload automatically\n"
                "2. Use /upload command for manual upload\n"
                "3. Use /list to see your uploaded files\n"
                "4. Use /download <id> or /stream <id> to access files\n\n"
                "**Supported File Types:**\n"
                "📄 Documents (PDF, DOC, etc.)\n"
                "🎬 Videos (MP4, MKV, AVI, etc.)\n"
                "🎵 Audio (MP3, WAV, etc.)\n"
                "🖼️ Images (JPG, PNG, etc.)\n\n"
                "**Streaming Support:**\n"
                "🎬 MX Player (Android)\n"
                "🔵 VLC Player (All platforms)\n"
                "🌐 Web Browser\n\n"
                "**File Size Limit:** 4GB\n"
                "**Storage:** Wasabi Cloud (Secure & Reliable)"
            )
            
            await message.reply(help_text)
        
        # Handle file messages (automatic upload)
        @self.app.on_message(
            filters.document | filters.video | filters.audio | 
            filters.photo | filters.voice
        )
        async def handle_file_message(client, message: Message):
            await FileHandler.handle_file_upload(client, message)
        
        # Callback query handler
        @self.app.on_callback_query()
        async def handle_callback(client, callback_query: CallbackQuery):
            data = callback_query.data
            user_id = callback_query.from_user.id
            
            try:
                if data.startswith("download_"):
                    file_id = data.replace("download_", "")
                    await FileHandler.handle_file_download(client, callback_query.message, file_id)
                
                elif data.startswith("stream_"):
                    file_id = data.replace("stream_", "")
                    await FileHandler.handle_file_stream(client, callback_query.message, file_id)
                
                elif data.startswith("mxplayer_"):
                    file_id = data.replace("mxplayer_", "")
                    file_info = db.get_file(file_id)
                    
                    if file_info:
                        url_result = await wasabi_client.generate_presigned_url(file_info['wasabi_key'])
                        if url_result['success']:
                            mx_url = f"intent://{url_result['url']}#Intent;package=com.mxtech.videoplayer.ad;scheme=http;end"
                            await callback_query.message.reply(
                                f"🎬 **MX Player**\n\nClick below to open in MX Player:",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("🎬 Open in MX Player", url=mx_url)]
                                ])
                            )
                
                elif data.startswith("vlc_"):
                    file_id = data.replace("vlc_", "")
                    file_info = db.get_file(file_id)
                    
                    if file_info:
                        url_result = await wasabi_client.generate_presigned_url(file_info['wasabi_key'])
                        if url_result['success']:
                            vlc_url = f"vlc://{url_result['url']}"
                            await callback_query.message.reply(
                                f"🔵 **VLC Player**\n\nClick below to open in VLC:",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("🔵 Open in VLC", url=vlc_url)]
                                ])
                            )
                
                elif data.startswith("delete_"):
                    file_id = data.replace("delete_", "")
                    file_info = db.get_file(file_id)
                    
                    if file_info and file_info['user_id'] == user_id:
                        await callback_query.message.edit_text(
                            f"🗑️ **Delete File**\n\n"
                            f"Are you sure you want to delete:\n`{file_info['file_name']}`?",
                            reply_markup=get_confirmation_keyboard(file_id)
                        )
                
                elif data.startswith("confirm_delete_"):
                    file_id = data.replace("confirm_delete_", "")
                    file_info = db.get_file(file_id)
                    
                    if file_info and file_info['user_id'] == user_id:
                        # Delete from Wasabi
                        await wasabi_client.delete_file(file_info['wasabi_key'])
                        # Delete from database
                        db.delete_file(file_id)
                        
                        await callback_query.message.edit_text(
                            f"✅ **File Deleted**\n\n`{file_info['file_name']}` has been permanently deleted."
                        )
                
                elif data.startswith("cancel_delete_"):
                    file_id = data.replace("cancel_delete_", "")
                    file_info = db.get_file(file_id)
                    
                    if file_info:
                        await callback_query.message.edit_text(
                            f"❌ **Deletion Cancelled**\n\n`{file_info['file_name']}` was not deleted.",
                            reply_markup=get_file_options_keyboard(file_id)
                        )
                
                await callback_query.answer()
                
            except Exception as e:
                logger.error(f"Callback error: {e}")
                await callback_query.answer("❌ An error occurred", show_alert=True)
    
    async def start(self):
        """Start the bot"""
        logger.info("Starting Telegram File Bot...")
        
        # Test Wasabi connection first
        logger.info("Testing Wasabi connection...")
        test_result = await wasabi_client.test_connection()
        if test_result['success']:
            logger.info("✅ Wasabi connection successful")
        else:
            logger.error(f"❌ Wasabi connection failed: {test_result['error']}")
            return
        
        # Start the bot
        logger.info("Starting Telegram bot...")
        await self.app.start()
        
        # Get bot info to confirm it's working
        me = await self.app.get_me()
        logger.info(f"✅ Bot started successfully as: {me.first_name} (@{me.username})")
        
        # Keep the bot running
        await self.app.idle()
    
    async def stop(self):
        """Stop the bot"""
        await self.app.stop()
        logger.info("Bot stopped.")
