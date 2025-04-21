import os
from bot import setup_bot
from config import DISCORD_TOKEN, logger

def main():
    """Main entry point for the Discord bot"""
    bot = setup_bot()
    
    try:
        logger.info("Starting JustFF bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        
if __name__ == "__main__":
    main()