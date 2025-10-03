# config.py
# Handles loading and validating environment variables.

import os
import logging

LOGGER = logging.getLogger(__name__)

# Load environment variables from the system
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WASABI_ACCESS_KEY = os.environ.get("WASABI_ACCESS_KEY")
WASABI_SECRET_KEY = os.environ.get("WASABI_SECRET_KEY")
WASABI_BUCKET = os.environ.get("WASABI_BUCKET")
WASABI_REGION = os.environ.get("WASABI_REGION")

# --- Validation ---
# A list of variables that are essential for the bot to run
REQUIRED_VARS = [
    "API_ID", "API_HASH", "BOT_TOKEN", "WASABI_ACCESS_KEY",
    "WASABI_SECRET_KEY", "WASABI_BUCKET", "WASABI_REGION"
]

# Check for any missing essential variables
missing_vars = [var for var in REQUIRED_VARS if not globals().get(var)]

if missing_vars:
    error_message = f"Missing required environment variables: {', '.join(missing_vars)}"
    LOGGER.critical(error_message)
    # This will stop the bot from starting if a critical variable is missing
    raise ValueError(error_message)
