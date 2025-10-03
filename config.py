import os
import sys
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        # Telegram API Configuration
        self.API_ID = self.get_env_int("API_ID")
        self.API_HASH = self.get_env("API_HASH")
        self.BOT_TOKEN = self.get_env("BOT_TOKEN")
        
        # Wasabi Configuration
        self.WASABI_ACCESS_KEY = self.get_env("WASABI_ACCESS_KEY")
        self.WASABI_SECRET_KEY = self.get_env("WASABI_SECRET_KEY")
        self.WASABI_BUCKET = self.get_env("WASABI_BUCKET")
        self.WASABI_REGION = os.getenv("WASABI_REGION", "us-east-1")
        self.WASABI_ENDPOINT = f"https://s3.{self.WASABI_REGION}.wasabisys.com"
        
        # Telegram Channel for Backup (Optional)
        self.BACKUP_CHANNEL = os.getenv("BACKUP_CHANNEL", "")
        
        # File Size Limits (4GB in bytes)
        self.MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
        
        # Chunk size for uploads (10MB)
        self.CHUNK_SIZE = 10 * 1024 * 1024
    
    def get_env(self, key):
        """Get environment variable or raise error"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"❌ Missing required environment variable: {key}")
        return value
    
    def get_env_int(self, key):
        """Get environment variable as integer"""
        value = self.get_env(key)
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"❌ {key} must be an integer")

# Create config instance
try:
    config = Config()
    print("✅ Configuration loaded successfully!")
except ValueError as e:
    print(e)
    sys.exit(1)
