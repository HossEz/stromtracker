#!/bin/bash
# Electricity Tracker Bot - Linux/macOS Start Script

echo "========================================"
echo "Electricity Tracker Bot"
echo "========================================"

# Navigate to script directory
cd "$(dirname "$0")"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "ERROR: .env file not found!"
    echo ""
    echo "Create a .env file with:"
    echo "TELEGRAM_BOT_TOKEN=your_bot_token_here"
    echo ""
    echo "Get a token from @BotFather on Telegram."
    echo ""
    exit 1
fi

# Run the bot
echo ""
echo "Starting bot..."
echo ""
python main.py
