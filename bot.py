import os
import logging
import asyncio
import signal
import sys
from typing import Dict, List, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.error import TelegramError, BadRequest, NetworkError

from config import Config
from storage import Storage
from wasabi_storage import WasabiStorage

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FileSharingBot:
    def __init__(self):
        self.config = Config()
        self.storage = Storage()
        self.wasabi = WasabiStorage()
        
        # Initialize application with connection pool settings for production
        self.application = (
            Application.builder()
            .token(self.config.BOT_TOKEN)
            .pool_timeout(30)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )
        
        self.setup_handlers()
        self.setup_error_handlers()
        
        # Store temporary data for file handling
        self.temp_data = {}

    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("myfiles", self.my_files_command))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.application.add_handler(CommandHandler("delete", self.delete_command))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))

        # Message handlers
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        self.application.add_handler(MessageHandler(filters.AUDIO, self.handle_audio))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^file_"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^page_"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^delete_"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^confirm_"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^cancel_"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^admin_"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^start$"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^help$"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^upload_help$"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^stats$"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^broadcast_menu$"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback, pattern="^admin_panel$"))

    def setup_error_handlers(self):
        # Add error handler
        self.application.add_error_handler(self.error_handler)

    async def error_handler(self, update: Update, context: CallbackContext):
        """Handle errors in the telegram bot."""
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
        
        try:
            # Notify user about the error
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
        except Exception as e:
            logger.error(f"Error in error handler: {e}")

    async def start_command(self, update: Update, context: CallbackContext):
        try:
            user = update.effective_user
            user_id = user.id
            
            # Check if it's a deep link for file sharing
            if context.args:
                file_id = context.args[0].replace('file_', '')
                file_data = self.storage.get_file(file_id)
                
                if file_data:
                    await self.send_file_to_user(update, context, file_data)
                    return
            
            welcome_text = f"""
👋 **Welcome {user.first_name}!**

🤖 **File Sharing Bot** - Your personal file hosting service

📁 **Supported Files:**
• Documents (PDF, ZIP, TXT, etc.)
• Photos (JPEG, PNG, etc.)
• Videos (MP4, AVI, etc.)
• Audio files (MP3, etc.)

⚡ **Features:**
• Permanent file storage with Wasabi Cloud
• Shareable links
• File management
• Admin controls
• No size limits (Telegram limits apply)

📋 **Available Commands:**
/start - Show this welcome message
/help - Detailed help guide
/myfiles - List your uploaded files
/search - Search your files
/delete - Remove your files

👨‍💼 **Admin Commands:**
/stats - Bot statistics
/broadcast - Send message to all users
/admin - Admin panel

🚀 **Get Started:** Simply send me any file!
            """
            
            keyboard = [
                [InlineKeyboardButton("📤 Upload File", callback_data="upload_help")],
                [InlineKeyboardButton("📋 My Files", callback_data="page_0")],
                [InlineKeyboardButton("🆘 Help", callback_data="help")]
            ]
            
            if user_id in self.config.ADMIN_IDS:
                keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await self.send_error_message(update, "start")

    async def help_command(self, update: Update, context: CallbackContext):
        try:
            help_text = """
📖 **Help Guide**

📤 **Uploading Files:**
Simply send any file (document, photo, video, audio) to the bot. 
You can add a caption to describe your file.

📁 **Managing Files:**
• Use /myfiles to view all your uploaded files
• Use /search to find specific files
• Use /delete to remove files

🔗 **Sharing Files:**
After uploading, you'll get a shareable link that anyone can use to download the file.

☁️ **Cloud Storage:**
• Files are stored in Wasabi Cloud Storage
• Permanent storage with fast access
• Secure and reliable

👨‍💼 **Admin Features** (for bot admins):
• View statistics with /stats
• Broadcast messages with /broadcast
• Manage all files in admin panel

⚙️ **Tips:**
• Files are stored permanently in cloud
• Share links never expire
• No registration required
• Fast download speeds

📝 **Examples:**
• Send a PDF file → Get shareable link
• Send a photo → Get direct link
• Send a video → Get streaming link
            """
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Start", callback_data="start")],
                [InlineKeyboardButton("📤 Upload Now", callback_data="upload_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await self.send_error_message(update, "help")

    async def handle_document(self, update: Update, context: CallbackContext):
        await self.handle_file_upload(update, context, "document")

    async def handle_photo(self, update: Update, context: CallbackContext):
        await self.handle_file_upload(update, context, "photo")

    async def handle_video(self, update: Update, context: CallbackContext):
        await self.handle_file_upload(update, context, "video")

    async def handle_audio(self, update: Update, context: CallbackContext):
        await self.handle_file_upload(update, context, "audio")

    async def handle_text(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            text = update.message.text
            
            # Check if user is setting caption for a file
            if user_id in self.temp_data and 'pending_caption' in self.temp_data[user_id]:
                file_data = self.temp_data[user_id]['pending_caption']
                
                if text.strip() == '-':
                    file_data['caption'] = f"Shared via File Bot"
                else:
                    file_data['caption'] = text
                
                await self.finalize_file_upload(update, context, file_data)
                del self.temp_data[user_id]['pending_caption']
                return
            
            await update.message.reply_text("📁 Send me any file to upload and get a shareable link!")
            
        except Exception as e:
            logger.error(f"Error handling text: {e}")
            await update.message.reply_text("❌ Error processing your request. Please try again.")

    async def handle_file_upload(self, update: Update, context: CallbackContext, file_type: str):
        try:
            user_id = update.effective_user.id
            message = update.message
            
            # Get file information based on type
            if file_type == "document":
                file_obj = message.document
                file_id = file_obj.file_id
                file_name = file_obj.file_name or "Document"
                mime_type = file_obj.mime_type or "application/octet-stream"
            elif file_type == "photo":
                file_obj = message.photo[-1]
                file_id = file_obj.file_id
                file_name = f"photo_{file_id}.jpg"
                mime_type = "image/jpeg"
            elif file_type == "video":
                file_obj = message.video
                file_id = file_obj.file_id
                file_name = file_obj.file_name or f"video_{file_id}.mp4"
                mime_type = getattr(file_obj, 'mime_type', 'video/mp4')
            elif file_type == "audio":
                file_obj = message.audio
                file_id = file_obj.file_id
                file_name = file_obj.file_name or f"audio_{file_id}.mp3"
                mime_type = getattr(file_obj, 'mime_type', 'audio/mpeg')
            else:
                return

            # Download file from Telegram
            progress_msg = await message.reply_text("📥 Downloading file from Telegram...")
            
            try:
                # Download file
                file = await context.bot.get_file(file_id)
                file_path = f"temp_{file_id}_{file_name}"
                await file.download_to_drive(file_path)
                
                await progress_msg.edit_text("☁️ Uploading to Wasabi Cloud Storage...")
                
                # Upload to Wasabi
                wasabi_url = await self.wasabi.upload_file(file_path, file_name)
                
                if not wasabi_url:
                    await progress_msg.edit_text("❌ Error uploading file to cloud storage.")
                    return
                
                # Prepare file data
                file_data = {
                    'file_id': file_id,
                    'wasabi_url': wasabi_url,
                    'name': file_name,
                    'type': file_type,
                    'mime_type': mime_type,
                    'user_id': user_id,
                    'user_name': update.effective_user.first_name,
                    'upload_time': datetime.now().isoformat(),
                    'caption': message.caption or "",
                    'file_size': getattr(file_obj, 'file_size', 0),
                    'telegram_file_id': file_id  # Keep original for compatibility
                }

                # Clean up temp file
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                await progress_msg.delete()

                # Ask for caption if not provided
                if not message.caption:
                    if user_id not in self.temp_data:
                        self.temp_data[user_id] = {}
                    self.temp_data[user_id]['pending_caption'] = file_data
                    
                    await message.reply_text(
                        "📝 Would you like to add a caption for this file? "
                        "Please send your caption text now, or send '-' to skip."
                    )
                    return

                await self.finalize_file_upload(update, context, file_data)

            except Exception as e:
                logger.error(f"Error downloading/uploading file: {e}")
                await progress_msg.edit_text("❌ Error processing file. Please try again.")

        except Exception as e:
            logger.error(f"Error handling file upload: {e}")
            await update.message.reply_text("❌ Error uploading file. Please try again.")

    async def finalize_file_upload(self, update: Update, context: CallbackContext, file_data: Dict):
        try:
            user_id = update.effective_user.id
            message = update.message if update.message else update.callback_query.message
            
            # Store file data
            success = self.storage.add_file(file_data)
            if not success:
                await message.reply_text("❌ Error storing file data. Please try again.")
                return
            
            # Generate shareable link
            bot_username = (await self.application.bot.get_me()).username
            share_url = f"https://t.me/{bot_username}?start=file_{file_data['file_id']}"
            
            # Prepare response message
            file_size = self.format_size(file_data.get('file_size', 0))
            upload_time = datetime.fromisoformat(file_data['upload_time']).strftime("%Y-%m-%d %H:%M:%S")
            
            response_text = f"""
✅ **File Uploaded Successfully!**

📁 **File Name:** `{file_data['name']}`
📝 **Caption:** {file_data['caption']}
📊 **Type:** {file_data['type'].title()}
📦 **Size:** {file_size}
🕒 **Uploaded:** {upload_time}
☁️ **Storage:** Wasabi Cloud

🔗 **Shareable Link:**
`{share_url}`

🌐 **Direct Download:**
`{file_data['wasabi_url']}`
            """
            
            keyboard = [
                [InlineKeyboardButton("🔗 Share File", url=share_url)],
                [InlineKeyboardButton("📋 My Files", callback_data="page_0"),
                 InlineKeyboardButton("🔄 Upload More", callback_data="upload_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error finalizing upload: {e}")
            await update.message.reply_text("❌ Error processing file. Please try again.")

    async def my_files_command(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            await self.show_user_files(update, user_id, 0)
        except Exception as e:
            logger.error(f"Error in my_files command: {e}")
            await self.send_error_message(update, "my_files")

    async def show_user_files(self, update: Update, user_id: int, page: int):
        try:
            user_files = self.storage.get_user_files(user_id)
            
            if not user_files:
                text = "📭 You haven't uploaded any files yet.\n\nSend me a file to get started!"
                keyboard = [[InlineKeyboardButton("📤 Upload File", callback_data="upload_help")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if update.callback_query:
                    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(text, reply_markup=reply_markup)
                return
            
            # Pagination
            items_per_page = 5
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            page_files = user_files[start_idx:end_idx]
            
            total_pages = (len(user_files) + items_per_page - 1) // items_per_page
            text = f"📁 **Your Files**\nPage {page + 1}/{total_pages}\n\n"
            
            keyboard = []
            for i, file_data in enumerate(page_files, 1):
                if file_data:
                    file_num = start_idx + i
                    text += f"{file_num}. **{file_data['name']}**\n"
                    text += f"   📝 {file_data['caption'][:30]}...\n"
                    text += f"   📊 {self.format_size(file_data.get('file_size', 0))}\n"
                    text += f"   ☁️ Wasabi Storage\n\n"
                    
                    keyboard.append([
                        InlineKeyboardButton(f"📄 {file_num}", callback_data=f"file_{file_data['file_id']}"),
                        InlineKeyboardButton("❌ Delete", callback_data=f"delete_{file_data['file_id']}")
                    ])
            
            # Navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page-1}"))
            if end_idx < len(user_files):
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="start")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error showing user files: {e}")
            await self.send_error_message(update, "show_files")

    async def delete_command(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            if context.args:
                file_id = context.args[0]
                file_data = self.storage.get_file(file_id)
                
                if file_data and file_data['user_id'] == user_id:
                    await self.confirm_delete(update, file_data)
                    return
                else:
                    await update.message.reply_text("❌ File not found or you don't have permission to delete it.")
                    return
            
            await self.show_user_files(update, user_id, 0)
            
        except Exception as e:
            logger.error(f"Error in delete command: {e}")
            await self.send_error_message(update, "delete")

    async def search_command(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            
            if not context.args:
                await update.message.reply_text("Usage: /search <filename or caption>")
                return
            
            query = " ".join(context.args).lower()
            results = self.storage.search_files(user_id, query)
            
            if not results:
                await update.message.reply_text("🔍 No files found matching your search.")
                return
            
            text = f"🔍 **Search Results for '{query}'**\n\n"
            keyboard = []
            
            for i, file_data in enumerate(results, 1):
                text += f"{i}. **{file_data['name']}**\n"
                text += f"   📝 {file_data['caption'][:30]}...\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(f"📄 {i}", callback_data=f"file_{file_data['file_id']}"),
                    InlineKeyboardButton("❌ Delete", callback_data=f"delete_{file_data['file_id']}")
                ])
            
            keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="start")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in search command: {e}")
            await self.send_error_message(update, "search")

    async def stats_command(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            
            if user_id not in self.config.ADMIN_IDS:
                await update.message.reply_text("❌ This command is for admins only.")
                return
            
            stats = self.storage.get_stats()
            wasabi_stats = await self.wasabi.get_storage_stats()
            
            text = f"""
📊 **Bot Statistics**

👥 **Users:** {stats['total_users']}
📁 **Total Files:** {stats['total_files']}
💾 **Total Size:** {self.format_size(stats['total_size'])}

☁️ **Wasabi Storage:**
• Bucket: {wasabi_stats.get('bucket_name', 'N/A')}
• Region: {wasabi_stats.get('region', 'N/A')}
• Objects: {wasabi_stats.get('object_count', 0)}
• Storage Used: {self.format_size(wasabi_stats.get('total_size', 0))}

📋 **Files by Type:**
"""
            for file_type, count in stats['files_by_type'].items():
                text += f"• {file_type.title()}: {count}\n"
            
            text += f"\n🕒 **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await self.send_error_message(update, "stats")

    async def broadcast_command(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            
            if user_id not in self.config.ADMIN_IDS:
                await update.message.reply_text("❌ This command is for admins only.")
                return
            
            if not context.args:
                await update.message.reply_text("Usage: /broadcast <message>")
                return
            
            message_text = " ".join(context.args)
            broadcast_text = f"""
📢 **Announcement**

{message_text}

---
_Sent via File Sharing Bot_
            """
            
            sent_count = 0
            failed_count = 0
            users = self.storage.get_all_users()
            
            progress_msg = await update.message.reply_text("📤 Starting broadcast...")
            
            for user_id in users:
                try:
                    await context.bot.send_message(chat_id=user_id, text=broadcast_text, parse_mode='Markdown')
                    sent_count += 1
                    
                    # Update progress every 10 messages
                    if sent_count % 10 == 0:
                        await progress_msg.edit_text(f"📤 Sent to {sent_count} users...")
                    
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send to user {user_id}: {e}")
            
            await progress_msg.edit_text(
                f"📊 **Broadcast Completed!**\n\n"
                f"✅ Success: {sent_count}\n"
                f"❌ Failed: {failed_count}\n"
                f"📨 Total: {sent_count + failed_count}"
            )
            
        except Exception as e:
            logger.error(f"Error in broadcast command: {e}")
            await self.send_error_message(update, "broadcast")

    async def admin_command(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            
            if user_id not in self.config.ADMIN_IDS:
                await update.message.reply_text("❌ This command is for admins only.")
                return
            
            stats = self.storage.get_stats()
            wasabi_stats = await self.wasabi.get_storage_stats()
            
            text = f"""
👨‍💼 **Admin Panel**

📊 **Statistics:**
• Users: {stats['total_users']}
• Files: {stats['total_files']}
• Storage: {self.format_size(stats['total_size'])}

☁️ **Wasabi Storage:**
• Objects: {wasabi_stats.get('object_count', 0)}
• Used: {self.format_size(wasabi_stats.get('total_size', 0))}

⚡ **Quick Actions:**
"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Statistics", callback_data="stats")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu")],
                [InlineKeyboardButton("🏠 Home", callback_data="start")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in admin command: {e}")
            await self.send_error_message(update, "admin")

    async def send_file_to_user(self, update: Update, context: CallbackContext, file_data: Dict):
        """Send file to user when they use share link"""
        try:
            caption = f"""
📁 **{file_data['name']}**

{file_data['caption']}

💾 Size: {self.format_size(file_data.get('file_size', 0))}
🕒 Uploaded: {datetime.fromisoformat(file_data['upload_time']).strftime('%Y-%m-%d')}
👤 By: {file_data['user_name']}
☁️ Storage: Wasabi Cloud

🔗 Shared via File Sharing Bot
            """
            
            # Send the Wasabi URL as a message since we can't send files from URLs directly
            download_text = f"""
📥 **Download File**

📁 **File Name:** {file_data['name']}
📝 **Caption:** {file_data['caption']}

🔗 **Direct Download Link:**
{file_data['wasabi_url']}

💡 *Click the link above to download the file*
            """
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=download_text,
                parse_mode='Markdown'
            )
                
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await update.message.reply_text("❌ Error accessing file. It may have been deleted.")

    async def confirm_delete(self, update: Update, file_data: Dict):
        try:
            text = f"""
🗑️ **Confirm Delete**

Are you sure you want to delete this file?

📁 **File:** {file_data['name']}
📝 **Caption:** {file_data['caption']}
☁️ **Storage:** Wasabi Cloud

This action will delete the file from cloud storage and cannot be undone!
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_{file_data['file_id']}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{file_data['file_id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in confirm delete: {e}")
            await self.send_error_message(update, "confirm_delete")

    async def button_callback(self, update: Update, context: CallbackContext):
        try:
            query = update.callback_query
            user_id = query.from_user.id
            data = query.data
            
            await query.answer()
            
            if data == "start":
                await self.start_command(update, context)
            
            elif data == "help":
                await self.help_command(update, context)
            
            elif data == "upload_help":
                await query.edit_message_text(
                    "📤 **How to Upload:**\n\n"
                    "1. Send any file (document, photo, video, audio)\n"
                    "2. Add a caption if needed\n"
                    "3. Get your shareable link!\n\n"
                    "☁️ **Files are stored in Wasabi Cloud Storage**\n\n"
                    "Try it now - send me a file!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Back", callback_data="start")]
                    ]),
                    parse_mode='Markdown'
                )
            
            elif data.startswith("page_"):
                page = int(data.split("_")[1])
                await self.show_user_files(update, user_id, page)
            
            elif data.startswith("file_"):
                file_id = data.split("_")[1]
                file_data = self.storage.get_file(file_id)
                if file_data:
                    await self.send_file_to_user(update, context, file_data)
            
            elif data.startswith("delete_"):
                file_id = data.split("_")[1]
                file_data = self.storage.get_file(file_id)
                if file_data and file_data['user_id'] == user_id:
                    await self.confirm_delete(update, file_data)
            
            elif data.startswith("confirm_"):
                file_id = data.split("_")[1]
                file_data = self.storage.get_file(file_id)
                
                if file_data and (file_data['user_id'] == user_id or user_id in self.config.ADMIN_IDS):
                    # Delete from Wasabi first
                    if 'wasabi_url' in file_data:
                        await self.wasabi.delete_file(file_data['name'])
                    
                    # Then delete from local storage
                    success = self.storage.delete_file(file_id)
                    if success:
                        await query.edit_message_text("✅ File deleted successfully from cloud storage!")
                    else:
                        await query.edit_message_text("❌ Error deleting file from database.")
                else:
                    await query.edit_message_text("❌ File not found or no permission to delete.")
            
            elif data.startswith("cancel_"):
                await query.edit_message_text("❌ Deletion cancelled.")
            
            elif data == "admin_panel":
                await self.admin_command(update, context)
            
            elif data == "stats":
                await self.stats_command(update, context)
            
            elif data == "broadcast_menu":
                await query.edit_message_text(
                    "📢 **Broadcast Message**\n\n"
                    "Use /broadcast <message> to send a message to all users.\n\n"
                    "Example:\n"
                    "`/broadcast New features added! Check /help for details.`",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
                    ]),
                    parse_mode='Markdown'
                )
                    
        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            await self.send_error_message(update, "button_callback")

    async def send_error_message(self, update: Update, command: str):
        """Send generic error message"""
        try:
            error_text = "❌ An error occurred while processing your request. Please try again."
            
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            elif update.message:
                await update.message.reply_text(error_text)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")

    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"

    def run(self):
        """Start the bot"""
        logger.info("Starting File Sharing Bot with Wasabi Storage...")
        print("🤖 File Sharing Bot is starting...")
        print("☁️  Wasabi Cloud Storage integrated")
        print("✅ Error handlers configured")
        print("🚀 Bot is ready!")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print(f"Received signal {signum}, shutting down gracefully...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            self.application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            print(f"❌ Error starting bot: {e}")

def main():
    """Main function to start the bot"""
    try:
        bot = FileSharingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    main()
