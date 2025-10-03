import asyncio
import logging
from telegram_bot import TelegramFileBot

async def main():
    """Main function to start the bot"""
    try:
        bot = TelegramFileBot()
        await bot.start()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        logging.error(f"Bot error: {e}")
    finally:
        if 'bot' in locals():
            await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
