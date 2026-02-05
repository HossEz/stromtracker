# Electricity Tracker Bot

A Telegram bot for tracking appliance electricity costs in Norway using real-time spot prices.

## What it does

You register appliances (e.g., a 1000W heater). When you turn it on, you tell the bot.
When you turn it off, you tell the bot. It calculates the exact cost using hour-by-hour
spot prices from hvakosterstrommen.no.

This is useful if you want to know what a specific appliance costs to run.

## Limitations

- **Spot prices only:** It uses the "Energiledd" (per-kWh fee). It does NOT track the
  "Kapasitetsledd" (monthly capacity fee based on peak usage). Your actual bill may be higher.
- **Fixed cost is simplified:** The default fixed cost is 1.0 kr/kWh. You must adjust
  `/set_fastkost` to match your actual grid rent if you want accurate results.
- **API dependency:** If hvakosterstrommen.no is down, the bot uses a hardcoded fallback
  price of 1.50 kr/kWh and will warn you.

## Setup

1. Get a bot token from [@BotFather](https://t.me/BotFather) on Telegram.
2. Create a `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
3. Run:
   - Windows: `start.bat`
   - Linux/macOS: `./start.sh`

## Commands

| Command | Description |
|---------|-------------|
| `/add [name] [low] [high]` | Add appliance (e.g., `/add Heater 750 1500`) |
| `/use` | Start tracking (shows buttons) |
| `/stop` | End session, show cost |
| `/mnd` | Monthly summary |
| `/config` | View settings |
| `/set_fastkost [kr]` | Set fixed cost per kWh |
| `/set_region [NO1-NO5]` | Set price region |
| `/help` | Full command list |

## How cost is calculated

```
kWh = hours × (watts / 1000)
Spot cost = kWh × spot price (includes 25% MVA)
Fixed cost = kWh × fixed cost
Total = Spot cost + Fixed cost
```

Prices are fetched per-hour from hvakosterstrommen.no, which sources from Nord Pool.

---

Data source: hvakosterstrommen.no
