# bot/s3_client.py
# Manages the Boto3 client for Wasabi and related S3 operations.

import logging
import boto3
from uuid import uuid4
from botocore.exceptions import NoCredentialsError, ClientError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Import configuration from the root config file
from config import (
    WASABI_ACCESS_KEY,
    WASABI_SECRET_KEY,
    WASABI_BUCKET,
    WASABI_REGION,
)

LOGGER = logging.getLogger(__name__)

# --- In-memory Database ---
# A simple dictionary to store file metadata.
# Format: { "file_id": {"name": "filename.mp4", "size": 12345, "s3_key": "unique_s3_key"} }
file_db = {}
s3_client = None

# --- Wasabi S3 Client Initialization ---
try:
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
        aws_access_key_id=WASABI_ACCESS_KEY,
        aws_secret_access_key=WASABI_SECRET_KEY,
        region_name=WASABI_REGION
    )
    LOGGER.info("Boto3 S3 client initialized successfully for Wasabi.")
except Exception as e:
    LOGGER.error(f"Failed to initialize Boto3 client: {e}")

def test_s3_connection():
    """Tests the connection to the Wasabi bucket and returns a status message."""
    if not s3_client:
        return "❌ **Error:** S3 client is not initialized. Check your configuration."
        
    try:
        s3_client.head_bucket(Bucket=WASABI_BUCKET)
        return f"✅ **Success!**\nConnection to bucket `{WASABI_BUCKET}` in region `{WASABI_REGION}` is working."
    except NoCredentialsError:
        return "❌ **Error:** Credentials not available. Check your `WASABI_ACCESS_KEY` and `WASABI_SECRET_KEY`."
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return f"❌ **Error:** Bucket `{WASABI_BUCKET}` not found."
        elif e.response['Error']['Code'] == '403':
            return f"❌ **Error:** Access denied to bucket `{WASABI_BUCKET}`. Check your key permissions."
        else:
            return f"❌ **An unknown S3 error occurred:**\n`{e}`"
    except Exception as e:
        return f"❌ **An unexpected error occurred:**\n`{e}`"

def generate_links_and_markup(file_id: str):
    """Helper to generate pre-signed URLs and keyboard markup."""
    if file_id not in file_db:
        return "File not found.", None

    s3_key = file_db[file_id]['s3_key']
    file_name = file_db[file_id]['name']

    try:
        # Generate a pre-signed URL valid for 1 hour (3600 seconds)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': WASABI_BUCKET, 'Key': s3_key},
            ExpiresIn=3600
        )
        
        # Player-specific links
        mx_player_link = f"intent:{presigned_url}#Intent;package=com.mxtech.videoplayer.ad;end"
        vlc_link = f"vlc://{presigned_url}"

        response_text = (
            f"**Links for:** `{file_name}`\n"
            f"**File ID:** `{file_id}`\n\n"
            "Links are valid for **1 hour**."
        )

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Direct Download", url=presigned_url)],
            [
                InlineKeyboardButton("▶️ MX Player", url=mx_player_link),
                InlineKeyboardButton("🟠 VLC", url=vlc_link)
            ],
            [InlineKeyboardButton("🌐 Open in Web Player", url=presigned_url)]
        ])

        return response_text, markup

    except Exception as e:
        LOGGER.error(f"Failed to generate presigned URL for {s3_key}: {e}")
        return f"❌ **Error:** Could not generate link for `{file_id}`.", None
