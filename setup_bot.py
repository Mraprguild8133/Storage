# setup_bot.py
import asyncio
import os
from pyrogram import Client
from config import config

async def setup_bot():
    """Setup and test the bot configuration"""
    print("🔧 Setting up Telegram File Bot...")
    
    # Test configuration
    print("✅ Configuration loaded successfully!")
    print(f"🤖 Bot Token: {config.BOT_TOKEN[:10]}...")
    print(f"🌐 API ID: {config.API_ID}")
    print(f"🔑 API Hash: {config.API_HASH[:10]}...")
    print(f"☁️ Wasabi Bucket: {config.WASABI_BUCKET}")
    
    # Test Telegram connection
    print("\n🔗 Testing Telegram connection...")
    try:
        async with Client(
            "file_bot_session",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True
        ) as app:
            me = await app.get_me()
            print(f"✅ Telegram connection successful!")
            print(f"   Bot: {me.first_name} (@{me.username})")
            print(f"   ID: {me.id}")
    except Exception as e:
        print(f"❌ Telegram connection failed: {e}")
        return False
    
    # Test Wasabi connection
    print("\n☁️ Testing Wasabi connection...")
    from wasabi_client import wasabi_client
    test_result = await wasabi_client.test_connection()
    if test_result['success']:
        print("✅ Wasabi connection successful!")
    else:
        print(f"❌ Wasabi connection failed: {test_result['error']}")
        return False
    
    print("\n🎉 All tests passed! The bot is ready to run.")
    print("🚀 Start the bot with: python bot.py")
    return True

if __name__ == "__main__":
    asyncio.run(setup_bot())
