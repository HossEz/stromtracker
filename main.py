#!/usr/bin/env python3
"""
Electricity Tracker Telegram Bot
Tracks appliance energy usage and costs using Norwegian spot prices.

Run with: python main.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import Application

from database.models import init_database
from bot.handlers import setup_handlers, set_commands


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("stromtracker.log", encoding="utf-8"),
    ]
)

# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from .env file."""
    # Load .env from project root
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env file!")
        logger.error("Create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
        sys.exit(1)
    
    return {"token": token}


async def post_init(application: Application) -> None:
    """Post-initialization hook - set bot commands."""
    await set_commands(application)
    logger.info("Bot commands registered")


def main() -> None:
    """Start the bot."""
    logger.info("=" * 50)
    logger.info("Electricity Tracker Bot starting...")
    logger.info("=" * 50)
    
    # Load configuration
    config = load_config()
    logger.info("Configuration loaded")
    
    # Initialize database
    init_database()
    logger.info("Database initialized")
    
    # Create application
    application = (
        Application.builder()
        .token(config["token"])
        .post_init(post_init)
        .build()
    )
    
    # Setup handlers
    setup_handlers(application)
    logger.info("Handlers registered")
    
    # Start the bot
    logger.info("Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
