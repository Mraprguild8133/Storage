# main.py
# Main entry point for the Telegram File Bot.

import asyncio
import logging
from bot import app

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)

async def main():
    """Starts the bot client and runs it indefinitely."""
    LOGGER.info("Bot starting...")
    try:
        await app.start()
        LOGGER.info("Bot is running!")
        # Keep the main coroutine alive
        await asyncio.Event().wait()
    except Exception as e:
        LOGGER.critical(f"Bot exited with a critical error: {e}")
    finally:
        await app.stop()
        LOGGER.info("Bot stopped.")

if __name__ == "__main__":
    try:
        # Import handlers to ensure they are registered with the client
        from bot import handlers
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped by user.")
