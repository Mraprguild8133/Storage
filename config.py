import os

class Config:
    """Configuration class for environment variables"""
    
    # Telegram API
    API_ID = os.environ.get("API_ID")
    API_HASH = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    
    # Wasabi Configuration
    WASABI_ACCESS_KEY = os.environ.get("WASABI_ACCESS_KEY")
    WASABI_SECRET_KEY = os.environ.get("WASABI_SECRET_KEY")
    WASABI_BUCKET = os.environ.get("WASABI_BUCKET")
    WASABI_REGION = os.environ.get("WASABI_REGION")
    
    # Admin Configuration
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

WEB_SERVER_URL=http://your-domain.com:8000  # Or your server IP

# Create config instance
config = Config()
