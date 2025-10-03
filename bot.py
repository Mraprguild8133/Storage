import asyncio
import logging
import sys
from telegram_bot import TelegramFileBot

async def main():
    """Main function to start the bot"""
    try:
        bot = TelegramFileBot()
        await bot.start()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logging.error(f"❌ Bot error: {e}")
        print(f"❌ Failed to start bot: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Check if all environment variables are set correctly")
        print("2. Verify your Telegram API credentials")
        print("3. Ensure your bot token is valid")
        print("4. Check your internet connection")
    finally:
        if 'bot' in locals():
            await bot.stop()
        print("👋 Goodbye!")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("🤖 Starting Telegram File Storage Bot...")
    asyncio.run(main())
