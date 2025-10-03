# bot/__init__.py
# Initializes the Pyrogram client instance.

import logging
from pyrogram import Client
from config import config

LOGGER = logging.getLogger(__name__)

# Initialize the main Pyrogram client instance
# This 'app' instance will be imported by other modules (like handlers)
# to register callbacks.
if all([config]):
    app = Client(
        "wasabi_file_bot",
        api_id=int(API_ID),
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )
else:
    LOGGER.warning("Bot client not initialized due to missing API credentials.")
    app = None
