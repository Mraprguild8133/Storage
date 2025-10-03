# bot/handlers.py
# Contains all the Pyrogram message and callback handlers for the bot.

import os
import time
import logging
from uuid import uuid4
import asyncio

from config import config 
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)

from bot import app
from bot.s3_client import s3_client, file_db, generate_links_and_markup, test_s3_connection
from bot.utils import humanbytes, progress_callback, BotoProgress
from config import WASABI_BUCKET

LOGGER = logging.getLogger(__name__)

# --- Command Handlers ---

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Handles the /start command."""
    welcome_text = (
        "**Welcome to the Wasabi File Storage Bot!**\n\n"
        "I can help you upload, store, and share files up to 4GB using Wasabi cloud storage.\n\n"
        "**Features:**\n"
        "✅ 4GB File Support\n"
        "☁️ Wasabi Cloud Integration\n"
        "🔗 Streaming & Direct Download Links\n"
        "📱 MX Player & VLC Integration\n\n"
        "To get started, simply send me any file. Use /help to see all available commands."
    )
    await message.reply_text(welcome_text, quote=True)

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Handles the /help command."""
    help_text = (
        "**Available Commands:**\n\n"
        "`/start` - Show the welcome message.\n"
        "`/list` - List all your stored files.\n"
        "`/download <file_id>` - Get a direct download link.\n"
        "`/stream <file_id>` - Get streaming links for players.\n"
        "`/web <file_id>` - Get a web player link.\n"
        "`/test` - Test the connection to your Wasabi bucket.\n"
        "`/help` - Show this help message.\n\n"
        "**To upload, simply send any file to this chat.**"
    )
    await message.reply_text(help_text, quote=True)

@app.on_message(filters.command("test"))
async def test_command(client, message: Message):
    """Tests the connection to the Wasabi bucket."""
    status_message = test_s3_connection()
    await message.reply_text(status_message, quote=True)

@app.on_message(filters.command("list"))
async def list_command(client, message: Message):
    """Lists all stored files."""
    if not file_db:
        await message.reply_text("You haven't uploaded any files yet.", quote=True)
        return
        
    response = "**Your Stored Files:**\n\n"
    for file_id, data in file_db.items():
        response += f"📄 **{data['name']}**\n"
        response += f"   - **Size:** {humanbytes(data['size'])}\n"
        response += f"   - **ID:** `{file_id}`\n\n"
        
    await message.reply_text(response, quote=True)

@app.on_message(filters.command(["download", "stream", "web"]))
async def get_links_command(client, message: Message):
    """Handles /download, /stream, and /web commands."""
    try:
        file_id = message.command[1]
    except IndexError:
        await message.reply_text(f"Please provide a File ID. Usage: `/{message.command[0]} <file_id>`", quote=True)
        return

    response_text, markup = generate_links_and_markup(file_id)
    await message.reply_text(response_text, reply_markup=markup, quote=True, disable_web_page_preview=True)

# --- File Upload Handler ---

@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def upload_handler(client, message: Message):
    """Handles all incoming files for upload."""
    if not s3_client:
        await message.reply_text("❌ **Upload Failed:** S3 client is not initialized. Please contact the bot admin.", quote=True)
        return

    media = message.document or message.video or message.audio or message.photo
    if not media:
        await message.reply_text("Unsupported file type.", quote=True)
        return

    # Use a unique temporary local filename
    local_file_path = f"downloads/{uuid4()}"
    file_name = getattr(media, 'file_name', f"file_{uuid4().hex}")
    file_size = media.file_size
    s3_key = f"{message.chat.id}/{uuid4().hex}/{file_name}"  # Unique key for S3

    status_message = await message.reply_text(f"📥 Starting download for `{file_name}`...", quote=True)
    
    start_time = time.time()
    
    try:
        # 1. Download from Telegram
        await app.download_media(
            message,
            file_name=local_file_path,
            progress=progress_callback,
            progress_args=(status_message, start_time)
        )
            
        await status_message.edit_text("☁️ Download complete. Now uploading to Wasabi...")
        
        # 2. Upload to Wasabi
        boto_progress = BotoProgress(status_message, file_size, time.time())
        
        with open(local_file_path, 'rb') as f:
            s3_client.upload_fileobj(
                f,
                WASABI_BUCKET,
                s3_key,
                Callback=lambda bytes_sent: asyncio.run(boto_progress(bytes_sent))
            )

        # 3. Clean up and store metadata
        os.remove(local_file_path)
        file_id = str(uuid4().hex[:8]) # Generate a user-friendly file ID
        file_db[file_id] = {"name": file_name, "size": file_size, "s3_key": s3_key}

        await status_message.edit_text(
            f"✅ **Upload Complete!**\n\n"
            f"**File Name:** `{file_name}`\n"
            f"**File Size:** {humanbytes(file_size)}\n"
            f"**File ID:** `{file_id}`\n\n"
            "Use this ID with `/download` or `/stream`.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Get Links", callback_data=f"links_{file_id}")]
            ])
        )

    except Exception as e:
        LOGGER.error(f"Upload failed for {file_name}: {e}")
        await status_message.edit_text(f"❌ **Upload Failed:** An error occurred.\n`{e}`")
        if os.path.exists(local_file_path):
            os.remove(local_file_path)

# --- Callback Query Handler ---

@app.on_callback_query(filters.regex(r"^links_"))
async def links_callback(client, callback_query: CallbackQuery):
    """Handles the 'Get Links' button callback."""
    file_id = callback_query.data.split("_")[1]
    response_text, markup = generate_links_and_markup(file_id)
    
    if markup:
        await callback_query.message.reply_text(
            response_text, 
            reply_markup=markup, 
            quote=True, 
            disable_web_page_preview=True
        )
        await callback_query.answer() # Acknowledge the callback
    else:
        await callback_query.answer(response_text, show_alert=True)
