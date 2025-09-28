import os
from typing import List

class Config:
    def __init__(self):
        # Bot token from environment variable or hardcoded
        self.BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
        
        # Admin user IDs (comma separated in env, or list)
        admin_ids = os.getenv('ADMIN_IDS', '123456789')
        self.ADMIN_IDS = [int(id.strip()) for id in admin_ids.split(',')]
        
        # Bot settings
        self.MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2GB (Telegram's limit)
        self.SUPPORTED_TYPES = ['document', 'photo', 'video', 'audio']
        
        # Storage settings
        self.STORAGE_FILE = os.getenv('STORAGE_FILE', 'data.json')
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration"""
        if self.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            raise ValueError("Please set your BOT_TOKEN in environment variables or config.py")
        
        if not self.ADMIN_IDS:
            raise ValueError("Please set at least one ADMIN_ID")
        
        print(f"✅ Configuration loaded:")
        print(f"   🤖 Bot token: {'Set' if self.BOT_TOKEN else 'Missing'}")
        print(f"   👑 Admin IDs: {len(self.ADMIN_IDS)}")
        print(f"   💾 Storage: {self.STORAGE_FILE}")
