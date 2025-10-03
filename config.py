import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API Configuration
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # Wasabi Configuration
    WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY", "")
    WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY", "")
    WASABI_BUCKET = os.getenv("WASABI_BUCKET", "")
    WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
    WASABI_ENDPOINT = f"https://s3.{WASABI_REGION}.wasabisys.com"
    
    # Telegram Channel for Backup (Optional)
    BACKUP_CHANNEL = os.getenv("BACKUP_CHANNEL", "")
    
    # File Size Limits (4GB in bytes)
    MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
    
    # Chunk size for uploads (10MB)
    CHUNK_SIZE = 10 * 1024 * 1024

config = Config()
