# bot/utils.py
# Contains helper functions like progress callbacks and byte converters.

import time
import logging
import asyncio
from pyrogram.types import Message

LOGGER = logging.getLogger(__name__)
# This dictionary will store the last time a progress update was sent for a message
progress_tracker = {}

def humanbytes(size):
    """Converts bytes to a human-readable format."""
    if not size:
        return "0B"
    size = int(size)
    power = 2 ** 10
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels) -1 :
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

async def progress_callback(current, total, message: Message, start_time):
    """Updates the user on the progress of a download from Telegram."""
    now = time.time()
    # Debounce updates to avoid hitting Telegram API rate limits (at most once every 2 seconds)
    if message.id in progress_tracker and (now - progress_tracker[message.id]) < 2:
        return
    progress_tracker[message.id] = now

    elapsed_time = now - start_time
    speed = current / elapsed_time if elapsed_time > 0 else 0
    percentage = current * 100 / total
    
    # Simple visual progress bar
    bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
    
    progress_text = (
        f"**Downloading from Telegram...**\n"
        f"[{bar}]\n"
        f"**Progress:** {percentage:.2f}%\n"
        f"**Size:** {humanbytes(current)} / {humanbytes(total)}\n"
        f"**Speed:** {humanbytes(speed)}/s"
    )

    try:
        await message.edit_text(progress_text)
    except Exception as e:
        LOGGER.warning(f"Failed to edit progress message: {e}")

# Boto3 progress tracking class
class BotoProgress:
    """A callable class for tracking Boto3 upload progress."""
    def __init__(self, message, total_size, start_time):
        self._message = message
        self._seen_so_far = 0
        self._lock = asyncio.Lock()
        self._total_size = total_size
        self._start_time = start_time
        self._last_update_time = 0

    async def __call__(self, bytes_amount):
        """The callback method invoked by Boto3."""
        async with self._lock:
            self._seen_so_far += bytes_amount
            now = time.time()
            
            # Debounce updates
            if now - self._last_update_time < 2:
                return

            self._last_update_time = now
            percentage = (self._seen_so_far / self._total_size) * 100
            elapsed_time = now - self._start_time
            speed = self._seen_so_far / elapsed_time if elapsed_time > 0 else 0
            bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))

            text = (
                f"**Uploading to Wasabi...**\n"
                f"[{bar}]\n"
                f"**Progress:** {percentage:.2f}%\n"
                f"**Size:** {humanbytes(self._seen_so_far)} / {humanbytes(self._total_size)}\n"
                f"**Speed:** {humanbytes(speed)}/s"
            )
            try:
                await self._message.edit_text(text)
            except Exception as e:
                LOGGER.warning(f"Boto progress update failed: {e}")
