@echo off
REM Electricity Tracker Bot - Windows Start Script

echo ========================================
echo Electricity Tracker Bot
echo ========================================

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Navigate to script directory
cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Check for .env file
if not exist ".env" (
    echo.
    echo ERROR: .env file not found!
    echo.
    echo Create a .env file with:
    echo TELEGRAM_BOT_TOKEN=your_bot_token_here
    echo.
    echo Get a token from @BotFather on Telegram.
    echo.
    pause
    exit /b 1
)

REM Run the bot
echo.
echo Starting bot...
echo.
python main.py

pause
