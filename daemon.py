import asyncio
import logging
import sys
from datetime import datetime
from main import bot, dp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'bot_logs_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)

logger = logging.getLogger(__name__)

async def start_bot():
    """
    Start the bot and handle graceful shutdown
    """
    try:
        logger.info("Starting bot...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Critical error occurred: {e}")
        sys.exit(1)
    finally:
        logger.info("Shutting down...")
        await bot.session.close()
        await dp.storage.close()

if __name__ == "__main__":
    try:
        logger.info("Initializing bot daemon...")
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        sys.exit(1) 