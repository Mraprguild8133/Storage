import os

class Config:
    def __init__(self):
        # Bot Token from environment variable (required for Render)
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        
        if not self.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN environment variable is required!")
        
        # Admin IDs - replace with your Telegram user ID
        # Get your user ID from @userinfobot on Telegram
        admin_ids = os.getenv('ADMIN_IDS', '')  # Comma-separated list
        if admin_ids:
            self.ADMIN_IDS = [int(id.strip()) for id in admin_ids.split(',')]
        else:
            self.ADMIN_IDS = []  # Default to empty if not set
        
        # Other configuration options
        self.MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        self.SUPPORTED_TYPES = ['document', 'photo', 'video', 'audio']
        
        # Render-specific settings
        self.PORT = int(os.getenv('PORT', 10000))
