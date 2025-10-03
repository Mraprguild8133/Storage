# setup_session.py
import os
from pyrogram import Client
from config import config

async def create_session():
    """Create a new Pyrogram session"""
    print("🔧 Setting up Pyrogram session...")
    
    async with Client(
        "file_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True
    ) as app:
        # Test the connection
        me = await app.get_me()
        print(f"✅ Bot authorized successfully as: {me.first_name} (@{me.username})")
        
        # The session will be saved automatically
        print("✅ Session created successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(create_session())
