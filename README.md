# Electricity Tracker Bot

A specialized Telegram bot for tracking electricity consumption and costs in Norway using real-time hourly spot prices from `hvakosterstrommen.no`.

## Features

- **Real-time Spot Prices:** Automatically fetches NO1-NO5 prices (includes 25% MVA).
- **Accurate Calculation:** Hour-by-hour cost calculation for precise session totals.
- **Mobile Friendly:** Fully button-driven interface—no typing required to start/stop.
- **Monthly Budgeting:** Set a budget and get alerts as you approach your limit.
- **History & Reports:** View recent sessions and monthly summaries.
- **Customizable:** Adjust fixed costs (nettleie), billing periods, and price regions.

## Quick Start

### 1. Prerequisites
- Python 3.10+
- A Telegram Bot Token (get it from [@BotFather](https://t.me/BotFather))

### 2. Setup
1. Clone this repository.
2. Create a `.env` file in the root folder (or just rename `.env.example`):
   ```env
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
3. Run the launcher:
   - **Windows:** Double-click `start.bat`
   - **Linux/macOS:** `chmod +x start.sh && ./start.sh`

## Commands

- `/start` - Welcome and quick start guide.
- `/add` - Add a new appliance (e.g., `/add Heater 750 1500`).
- `/use` - Pick an appliance and start tracking.
- `/status` - Check current session runtime and estimated cost.
- `/stop` - End session and see the cost breakdown.
- `/mnd` - View monthly summary.
- `/config` - See all your current settings.
- `/help` - Full command list and cost formulas.

## How it calculates
Costs are calculated using the formula:
`Total = (kWh × Spot Price with MVA) + (kWh × Fixed Cost)`

*Fixed cost includes your local nettleie, taxes, and fees (default 1 kr/kWh).*

---
_Data provided by [hvakosterstrommen.no](https://www.hvakosterstrommen.no/)_
