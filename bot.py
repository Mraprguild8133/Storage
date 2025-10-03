import os
import asyncio
import aiofiles
from typing import Optional
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import MessageMediaType

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from config import config

# Initialize Telegram Bot
app = Client(
    "wasabi_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Initialize Wasabi S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=config.WASABI_ACCESS_KEY,
    aws_secret_access_key=config.WASABI_SECRET_KEY,
    endpoint_url=config.WASABI_ENDPOINT,
    region_name=config.WASABI_REGION,
    config=BotoConfig(signature_version='s3v4')
)

class ProgressTracker:
    def __init__(self, message: Message, operation: str):
        self.message = message
        self.operation = operation
        self.last_update = 0
        
    async def progress_callback(self, current, total):
        # Update progress every 5% or 10MB
        if current == total or (current - self.last_update) >= (total * 0.05) or (current - self.last_update) >= (10 * 1024 * 1024):
            percentage = (current / total) * 100
            progress_bar = self._create_progress_bar(percentage)
            
            try:
                await self.message.edit_text(
                    f"**{self.operation} Progress**\n"
                    f"{progress_bar} {percentage:.1f}%\n"
                    f"`{self._format_size(current)} / {self._format_size(total)}`"
                )
            except:
                pass
            
            self.last_update = current
    
    def _create_progress_bar(self, percentage: float, length: int = 20) -> str:
        filled = int(length * percentage // 100)
        empty = length - filled
        return "█" * filled + "░" * empty
    
    def _format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Start command handler"""
    await message.reply_text(
        "🤖 **Wasabi File Storage Bot**\n\n"
        "Send me any file and I'll upload it to Wasabi storage "
        "and provide you with a streaming link compatible with MX Player!\n\n"
        "**Features:**\n"
        "• Upload files up to 4GB\n"
        "• Instant streaming links\n"
        "• MX Player support\n"
        "• Real-time progress tracking\n\n"
        "Just send me a file to get started!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📁 Upload File", switch_inline_query_current_chat="")
        ]])
    )

@app.on_message(filters.media & filters.private)
async def handle_media(client: Client, message: Message):
    """Handle media files and upload to Wasabi"""
    
    if not message.media:
        await message.reply_text("❌ Please send a file to upload.")
        return
    
    # Get file information
    if message.media == MessageMediaType.DOCUMENT:
        file_name = message.document.file_name
        file_size = message.document.file_size
        mime_type = message.document.mime_type
    elif message.media == MessageMediaType.VIDEO:
        file_name = message.video.file_name or f"video_{message.id}.mp4"
        file_size = message.video.file_size
        mime_type = "video/mp4"
    elif message.media == MessageMediaType.AUDIO:
        file_name = message.audio.file_name or f"audio_{message.id}.mp3"
        file_size = message.audio.file_size
        mime_type = "audio/mpeg"
    else:
        await message.reply_text("❌ Unsupported media type. Please send a document, video, or audio file.")
        return
    
    # Check file size
    if file_size > config.MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ File size exceeds 4GB limit.\n"
            f"Your file: {file_size / (1024**3):.2f}GB"
        )
        return
    
    # Initial processing message
    status_msg = await message.reply_text(
        f"📥 **Processing File**\n"
        f"**Name:** `{file_name}`\n"
        f"**Size:** {file_size / (1024**2):.2f} MB\n"
        f"**Type:** {mime_type}\n\n"
        f"⏳ Downloading from Telegram..."
    )
    
    try:
        # Initialize progress tracker
        progress = ProgressTracker(status_msg, "Download")
        
        # Download file from Telegram
        download_path = await message.download(
            file_name=f"downloads/{message.id}_{file_name}",
            progress=progress.progress_callback,
            progress_args=(file_size,)
        )
        
        await status_msg.edit_text("📤 Uploading to Wasabi Storage...")
        
        # Generate unique key for S3
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"telegram_files/{message.from_user.id}/{timestamp}_{file_name}"
        
        # Upload to Wasabi with progress
        upload_progress = ProgressTracker(status_msg, "Upload")
        
        await upload_to_wasabi(
            download_path,
            config.WASABI_BUCKET,
            s3_key,
            upload_progress
        )
        
        # Generate streaming URL
        streaming_url = generate_streaming_url(config.WASABI_BUCKET, s3_key)
        
        # Create MX Player deep link
        mx_player_url = f"intent://{streaming_url.split('//')[1]}#Intent;package=com.mxtech.videoplayer.ad;scheme=https;end"
        
        # Send success message with links
        await status_msg.edit_text(
            f"✅ **File Uploaded Successfully!**\n\n"
            f"**File:** `{file_name}`\n"
            f"**Size:** {file_size / (1024**2):.2f} MB\n\n"
            f"**Streaming Links:**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Direct Link", url=streaming_url)],
                [InlineKeyboardButton("🎬 MX Player", url=mx_player_url)],
                [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_{streaming_url}")]
            ])
        )
        
        # Clean up local file
        os.remove(download_path)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")
        
        # Clean up on error
        try:
            if 'download_path' in locals() and os.path.exists(download_path):
                os.remove(download_path)
        except:
            pass

async def upload_to_wasabi(file_path: str, bucket: str, key: str, progress_tracker: ProgressTracker):
    """Upload file to Wasabi storage with progress tracking"""
    
    file_size = os.path.getsize(file_path)
    
    # For large files, use multipart upload
    if file_size > config.CHUNK_SIZE:
        await multipart_upload(file_path, bucket, key, progress_tracker)
    else:
        # Single part upload for smaller files
        async with aiofiles.open(file_path, 'rb') as file:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: s3_client.upload_fileobj(
                    file,
                    bucket,
                    key,
                    Callback=lambda bytes_transferred: asyncio.create_task(
                        progress_tracker.progress_callback(bytes_transferred, file_size)
                    )
                )
            )

async def multipart_upload(file_path: str, bucket: str, key: str, progress_tracker: ProgressTracker):
    """Handle multipart upload for large files"""
    
    file_size = os.path.getsize(file_path)
    
    # Create multipart upload
    mpu = s3_client.create_multipart_upload(
        Bucket=bucket,
        Key=key
    )
    upload_id = mpu['UploadId']
    
    try:
        parts = []
        part_number = 1
        uploaded_bytes = 0
        
        async with aiofiles.open(file_path, 'rb') as file:
            while True:
                chunk = await file.read(config.CHUNK_SIZE)
                if not chunk:
                    break
                
                # Upload part
                part = s3_client.upload_part(
                    Bucket=bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk
                )
                
                parts.append({
                    'PartNumber': part_number,
                    'ETag': part['ETag']
                })
                
                uploaded_bytes += len(chunk)
                await progress_tracker.progress_callback(uploaded_bytes, file_size)
                
                part_number += 1
        
        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )
        
    except Exception as e:
        # Abort upload on error
        s3_client.abort_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id
        )
        raise e

def generate_streaming_url(bucket: str, key: str) -> str:
    """Generate streaming URL for the file"""
    
    try:
        # Generate presigned URL that expires in 7 days
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key
            },
            ExpiresIn=604800  # 7 days
        )
        return url
    except ClientError as e:
        raise Exception(f"Failed to generate streaming URL: {str(e)}")

@app.on_callback_query(filters.regex(r"copy_.+"))
async def handle_copy_callback(client: Client, callback_query):
    """Handle copy link callback"""
    url = callback_query.data.replace("copy_", "")
    
    # In a real implementation, you might want to copy to clipboard
    # For now, we'll just show the URL
    await callback_query.answer(f"Link: {url}", show_alert=True)

@app.on_message(filters.command("stats"))
async def stats_command(client: Client, message: Message):
    """Show bot statistics"""
    user = message.from_user
    await message.reply_text(
        f"📊 **Bot Statistics**\n\n"
        f"**User ID:** `{user.id}`\n"
        f"**Name:** {user.first_name}\n"
        f"**Username:** @{user.username if user.username else 'N/A'}\n\n"
        f"**Max File Size:** 4GB\n"
        f"**Storage:** Wasabi Cloud\n"
        f"**Streaming:** MX Player Supported"
    )

async def main():
    """Main function to start the bot"""
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    print("🤖 Starting Wasabi File Storage Bot...")
    await app.start()
    print("✅ Bot started successfully!")
    
    # Get bot info
    me = await app.get_me()
    print(f"👤 Bot: @{me.username}")
    print("🚀 Bot is running...")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
