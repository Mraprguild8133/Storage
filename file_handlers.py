import os
import uuid
import logging
from datetime import datetime
from pyrogram.types import Message
from config import config
from wasabi_client import wasabi_client
from database import db
from keyboards import get_file_options_keyboard

logger = logging.getLogger(__name__)

class FileHandler:
    @staticmethod
    async def handle_file_upload(client, message: Message):
        """Handle file upload from Telegram"""
        user_id = message.from_user.id
        
        try:
            # Check if message contains a file
            if (message.document or message.video or message.audio or 
                message.photo or message.voice):
                
                # Send initial progress message
                progress_msg = await message.reply("📤 Starting upload...")
                
                # Determine file type and get file details
                if message.document:
                    file = message.document
                    file_type = "document"
                elif message.video:
                    file = message.video
                    file_type = "video"
                elif message.audio:
                    file = message.audio
                    file_type = "audio"
                elif message.photo:
                    file = message.photo
                    file_type = "photo"
                elif message.voice:
                    file = message.voice
                    file_type = "voice"
                else:
                    await progress_msg.edit_text("❌ Unsupported file type")
                    return
                
                # Check file size
                if file.file_size > config.MAX_FILE_SIZE:
                    await progress_msg.edit_text(
                        f"❌ File too large. Maximum size is 4GB. "
                        f"Your file: {file.file_size / (1024**3):.2f}GB"
                    )
                    return
                
                # Generate unique file ID
                file_id = str(uuid.uuid4())[:8]
                
                # Download file from Telegram
                temp_path = f"temp_{file_id}_{file.file_name}"
                
                # Download with progress
                await client.download_media(
                    message,
                    file_name=temp_path,
                    progress=FileHandler.upload_progress,
                    progress_args=(progress_msg, file.file_size, "Downloading")
                )
                
                # Update progress message
                await progress_msg.edit_text("☁️ Uploading to Wasabi Cloud...")
                
                # Upload to Wasabi
                wasabi_key = f"{user_id}/{file_id}_{file.file_name}"
                upload_result = await wasabi_client.upload_file(temp_path, wasabi_key)
                
                if not upload_result['success']:
                    await progress_msg.edit_text(f"❌ Wasabi upload failed: {upload_result['error']}")
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return
                
                # Store file info in database
                file_data = {
                    'file_id': file_id,
                    'file_name': file.file_name,
                    'file_size': file.file_size,
                    'wasabi_key': wasabi_key,
                    'telegram_file_id': file.file_id,
                    'mime_type': getattr(file, 'mime_type', 'application/octet-stream'),
                    'user_id': user_id
                }
                
                db.add_file(file_data)
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                # Send success message with file options
                file_size_mb = file.file_size / (1024 * 1024)
                success_text = (
                    f"✅ **File Uploaded Successfully!**\n\n"
                    f"📁 **File Name:** `{file.file_name}`\n"
                    f"📊 **File Size:** {file_size_mb:.2f} MB\n"
                    f"🆔 **File ID:** `{file_id}`\n"
                    f"☁️ **Storage:** Wasabi Cloud\n\n"
                    f"Choose an option below:"
                )
                
                await progress_msg.edit_text(
                    success_text,
                    reply_markup=get_file_options_keyboard(file_id)
                )
                
            else:
                await message.reply("❌ Please send a file to upload.")
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await message.reply(f"❌ Upload failed: {str(e)}")
    
    @staticmethod
    async def upload_progress(current, total, progress_msg, file_size, action):
        """Update upload progress"""
        try:
            percentage = (current / total) * 100
            progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
            
            text = (
                f"📤 {action}...\n\n"
                f"📊 Progress: {percentage:.1f}%\n"
                f"📦 {progress_bar}\n"
                f"💾 {current / (1024*1024):.1f}MB / {total / (1024*1024):.1f}MB"
            )
            
            await progress_msg.edit_text(text)
        except Exception as e:
            logger.error(f"Progress update error: {e}")
    
    @staticmethod
    async def handle_file_download(client, message: Message, file_id):
        """Handle file download by file_id"""
        try:
            # Get file info from database
            file_info = db.get_file(file_id)
            
            if not file_info:
                await message.reply("❌ File not found.")
                return
            
            progress_msg = await message.reply("📥 Preparing download...")
            
            # Generate presigned URL
            url_result = await wasabi_client.generate_presigned_url(file_info['wasabi_key'])
            
            if not url_result['success']:
                await progress_msg.edit_text(f"❌ Failed to generate download URL: {url_result['error']}")
                return
            
            download_url = url_result['url']
            file_size_mb = file_info['file_size'] / (1024 * 1024)
            
            response_text = (
                f"📥 **Download Ready**\n\n"
                f"📁 **File:** `{file_info['file_name']}`\n"
                f"📊 **Size:** {file_size_mb:.2f} MB\n\n"
                f"🔗 **Download Link:**\n`{download_url}`\n\n"
                f"⚠️ *Link expires in 7 days*"
            )
            
            await progress_msg.edit_text(
                response_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Direct Download", url=download_url)]
                ])
            )
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await message.reply(f"❌ Download failed: {str(e)}")
    
    @staticmethod
    async def handle_file_stream(client, message: Message, file_id):
        """Handle file streaming by file_id"""
        try:
            # Get file info from database
            file_info = db.get_file(file_id)
            
            if not file_info:
                await message.reply("❌ File not found.")
                return
            
            progress_msg = await message.reply("🔄 Generating streaming link...")
            
            # Generate presigned URL for streaming
            url_result = await wasabi_client.generate_presigned_url(file_info['wasabi_key'])
            
            if not url_result['success']:
                await progress_msg.edit_text(f"❌ Failed to generate streaming URL: {url_result['error']}")
                return
            
            stream_url = url_result['url']
            file_size_mb = file_info['file_size'] / (1024 * 1024)
            
            response_text = (
                f"📺 **Streaming Ready**\n\n"
                f"📁 **File:** `{file_info['file_name']}`\n"
                f"📊 **Size:** {file_size_mb:.2f} MB\n"
                f"🎬 **Supported Players:** MX Player, VLC, Browser\n\n"
                f"Choose your preferred player:"
            )
            
            from keyboards import get_streaming_keyboard
            await progress_msg.edit_text(
                response_text,
                reply_markup=get_streaming_keyboard(file_id, stream_url)
            )
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            await message.reply(f"❌ Streaming failed: {str(e)}")
    
    @staticmethod
    async def handle_file_list(client, message: Message):
        """List all user files"""
        try:
            user_id = message.from_user.id
            files = db.list_files(user_id=user_id, limit=20)
            
            if not files:
                await message.reply("📭 No files found. Upload your first file using /upload")
                return
            
            response_text = "📋 **Your Files**\n\n"
            
            for i, file in enumerate(files, 1):
                file_size_mb = file['file_size'] / (1024 * 1024)
                upload_date = file['upload_date'][:10]  # Get only date part
                
                response_text += (
                    f"{i}. `{file['file_id']}` - **{file['file_name']}**\n"
                    f"   📊 {file_size_mb:.1f}MB • 📅 {upload_date}\n\n"
                )
            
            response_text += "\nUse `/download <file_id>` or `/stream <file_id>` to access files."
            
            await message.reply(response_text)
            
        except Exception as e:
            logger.error(f"List files error: {e}")
            await message.reply(f"❌ Failed to list files: {str(e)}")
