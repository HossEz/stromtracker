"""
Telegram bot command handlers for the Electricity Tracker.
"""

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from database.models import (
    init_database,
    add_apparat,
    get_apparat,
    get_all_apparater,
    delete_apparat,
    start_session,
    get_active_session,
    end_session,
    cancel_session,
    get_user_settings,
    update_user_setting,
    get_session_history,
    clear_sessions,
)
from core.calculator import calculate_session_cost, estimate_current_cost, calculate_watt, format_duration
from core.price_api import get_current_price, format_region_name, VALID_REGIONS, NORWAY_TZ
from core.alerts import check_budget_alert, check_runtime_alert, get_monthly_summary
from bot.keyboards import get_watt_mode_keyboard, get_region_keyboard, get_confirm_keyboard, get_appliance_keyboard, get_session_action_keyboard

logger = logging.getLogger(__name__)

# Month names in English
MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


# ============ Helper Functions ============

def get_user_id(update: Update) -> int:
    """Get user ID from update."""
    return update.effective_user.id


async def send_message(update: Update, text: str, **kwargs) -> None:
    """Send a message, handling both regular updates and callback queries."""
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", **kwargs)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", **kwargs)


# ============ Command Handlers ============

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - Welcome message."""
    user_id = get_user_id(update)
    settings = get_user_settings(user_id)  # Ensures user is created
    
    text = """👋 *Welcome to Electricity Tracker!*

Track your appliance energy usage and costs with real-time Norwegian spot prices.

*Quick Start:*
1️⃣ /add Heater 750 1500 - Add an appliance
2️⃣ /use Heater - Start tracking
3️⃣ /stop - End session and see costs

*Settings:*
• /set\_fastkost 1 - Set fixed cost/kWh
• /set\_region NO1 - Set price region
• /budget 200 - Set monthly budget

Type /help for all commands.

_Prices from hvakosterstrommen.no_"""
    
    await send_message(update, text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - Full help with formulas."""
    text = """📖 *Electricity Tracker Help*

*Appliance Commands:*
• /add \[name] \[low] \[high] - Add appliance
• /list - Show all appliances
• /delete \[name] - Remove appliance

*Tracking Commands:*
• /use \[name] - Start tracking
• /stop - End session, show costs
• /cancel - Cancel without recording
• /status - Current runtime and estimate

*Reports:*
• /mnd - Monthly summary
• /history - Recent sessions

*Settings:*
• /set\_fastkost \[kr] - Fixed cost/kWh
• /set\_region \[NO1-NO5] - Price region
• /budget \[kr] - Monthly budget
• /set\_periode \[day] - Billing start day

*Cost Formula:*
kWh = hours x (watts / 1000)
Spot = kWh x spot price (+ 25% MVA)
Fixed = kWh x fastkost
Total = Spot + Fixed

*Example (2h @ 1125W avg):*
• kWh = 2 x 1.125 = 2.25 kWh
• Spot = 2.25 x 1.21 = 2.72 kr
• Fixed = 2.25 x 1.0 = 2.25 kr
• Total = 6.77 kr"""
    
    await send_message(update, text)


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add command - Add a new appliance."""
    user_id = get_user_id(update)
    
    if len(context.args) < 3:
        await send_message(update, "❌ Usage: /add \[name] \[low] \[high]\n\nExample: /add Jula 750 1500")
        return
    
    name = context.args[0]
    try:
        low_watt = int(context.args[1])
        high_watt = int(context.args[2])
    except ValueError:
        await send_message(update, "❌ Wattage must be numbers.\n\nExample: /add Jula 750 1500")
        return
    
    if low_watt <= 0 or high_watt <= 0:
        await send_message(update, "❌ Wattage must be positive numbers.")
        return
    
    if low_watt > high_watt:
        low_watt, high_watt = high_watt, low_watt  # Swap if reversed
    
    success = add_apparat(user_id, name, low_watt, high_watt)
    
    if success:
        avg_watt = (low_watt + high_watt) // 2
        await send_message(update, f"✅ *{name}* added!\n\n🔋 Low: {low_watt}W\n⚡ High: {high_watt}W\n📊 Avg: {avg_watt}W\n\nUse `/use {name}` to start tracking.")
    else:
        await send_message(update, f"❌ Appliance *{name}* already exists.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command - Show all appliances."""
    user_id = get_user_id(update)
    apparater = get_all_apparater(user_id)
    
    if not apparater:
        await send_message(update, "📋 No appliances registered.\n\nAdd one with /add \[name] \[low] \[high]")
        return
    
    lines = ["📋 *Your Appliances:*\n"]
    for a in apparater:
        avg = (a["low_watt"] + a["high_watt"]) // 2
        lines.append(f"• *{a['name']}*: {a['low_watt']}W / {a['high_watt']}W (avg {avg}W)")
    
    await send_message(update, "\n".join(lines))


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete command - Remove an appliance."""
    user_id = get_user_id(update)
    
    if not context.args:
        # Show appliances as buttons
        apparater = get_all_apparater(user_id)
        if not apparater:
            await send_message(update, "📋 No appliances to delete.")
            return
        
        await send_message(update, "🗑️ *Select appliance to delete:*", reply_markup=get_appliance_keyboard(apparater, "delete"))
        return
    
    name = context.args[0]
    success = delete_apparat(user_id, name)
    
    if success:
        await send_message(update, f"🗑️ *{name}* deleted.")
    else:
        await send_message(update, f"❌ Appliance *{name}* not found.")


async def cmd_use(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /use command - Start tracking an appliance."""
    user_id = get_user_id(update)
    
    # Check for existing active session
    active = get_active_session(user_id)
    if active:
        await send_message(update, f"⚠️ Already tracking *{active['apparat_name']}*.\n\nUse `/stop` to end or `/cancel` to abort.")
        return
    
    if not context.args:
        # Show list of appliances as buttons
        apparater = get_all_apparater(user_id)
        if not apparater:
            await send_message(update, "❌ No appliances registered.\n\nAdd one with /add \[name] \[low] \[high]")
            return
        
        await send_message(update, "⚡ *Select appliance to track:*", reply_markup=get_appliance_keyboard(apparater, "use"))
        return
    
    name = context.args[0]
    apparat = get_apparat(user_id, name)
    
    if not apparat:
        await send_message(update, f"❌ Appliance *{name}* not found.\n\nUse `/list` to see your appliances.")
        return
    
    # Get current spot price for display
    settings = get_user_settings(user_id)
    region = settings.get("region", "NO1")
    current_price = await get_current_price(region)
    price_text = f"{current_price:.4f} kr/kWh" if current_price else "unavailable"
    
    avg_watt = (apparat["low_watt"] + apparat["high_watt"]) // 2
    
    text = f"""⚡ *Start tracking: {name}*

Select power mode:
🔋 Low: {apparat['low_watt']}W
⚡ High: {apparat['high_watt']}W  
📊 Avg: {avg_watt}W

Current spot price ({region}): {price_text}
Fixed cost: {settings.get('fixed_cost_nok', 1.0):.2f} kr/kWh"""
    
    await send_message(update, text, reply_markup=get_watt_mode_keyboard(name))


async def callback_watt_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle watt mode selection callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id(update)
    data = query.data.split(":")
    
    if len(data) != 3 or data[0] != "watt":
        return
    
    mode, apparat_name = data[1], data[2]
    
    if mode == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return
    
    apparat = get_apparat(user_id, apparat_name)
    if not apparat:
        await query.edit_message_text(f"❌ Appliance *{apparat_name}* not found.", parse_mode="Markdown")
        return
    
    # Calculate actual watt based on mode
    actual_watt = calculate_watt(apparat["low_watt"], apparat["high_watt"], mode)
    
    # Start the session
    session_id = start_session(user_id, apparat["id"], mode, actual_watt)
    
    # Get current spot price
    settings = get_user_settings(user_id)
    region = settings.get("region", "NO1")
    current_price = await get_current_price(region)
    price_text = f"{current_price:.4f} kr/kWh" if current_price else "fetching..."
    
    mode_emoji = {"low": "🔋", "high": "⚡", "avg": "📊"}[mode]
    
    text = f"""✅ *Session started!*

📟 *{apparat_name}* @ {actual_watt}W ({mode_emoji} {mode})
⏱ Started: {datetime.now(NORWAY_TZ).strftime('%H:%M')}
💡 Spot price ({region}): {price_text}"""
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_session_action_keyboard())


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command - End session and calculate costs."""
    user_id = get_user_id(update)
    session = get_active_session(user_id)
    
    if not session:
        await send_message(update, "❌ No active session.\n\nStart one with `/use [appliance]`")
        return
    
    # Get user settings
    settings = get_user_settings(user_id)
    region = settings.get("region", "NO1")
    fixed_cost = settings.get("fixed_cost_nok", 1.0)
    
    # Parse start time
    start_time = datetime.fromisoformat(session["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=NORWAY_TZ)
    end_time = datetime.now(NORWAY_TZ)
    
    # Calculate costs
    result = await calculate_session_cost(
        start_time, end_time,
        session["actual_watt"],
        fixed_cost,
        region
    )
    
    # Save session
    end_session(
        session["id"],
        result["kwh"],
        result["spot_cost"],
        result["fixed_cost"],
        result["total_cost"]
    )
    
    # Get monthly summary
    now = datetime.now(NORWAY_TZ)
    summary = get_monthly_summary(user_id, now.year, now.month)
    
    mode_emoji = {"low": "🔋", "high": "⚡", "avg": "📊"}[session["watt_mode"]]
    duration_str = format_duration(result["hours"])
    
    text = f"""✅ *Session ended: {session['apparat_name']}*

⏱ Duration: {duration_str} ({mode_emoji} {session['watt_mode']})
⚡ Consumption: {result['kwh']:.2f} kWh @ {session['actual_watt']}W

💰 *Cost breakdown:*
   Spot ({region}): {result['avg_spot_price']:.2f} kr/kWh → {result['spot_cost']:.2f} kr
   Fixed: {fixed_cost:.2f} kr/kWh → {result['fixed_cost']:.2f} kr
   ─────────────────────
   *Total: {result['total_cost']:.2f} kr*

📊 *{MONTH_NAMES[now.month]} total:* {summary['total_kwh']:.2f} kWh / {summary['total_cost']:.2f} kr ({summary['session_count']} sessions)"""
    
    # Add budget info if set
    if summary["budget"]:
        text += f"\n💼 Budget: {summary['remaining']:.2f} kr remaining of {summary['budget']:.2f} kr"
    
    await send_message(update, text)
    
    # Check for budget alert
    alert = await check_budget_alert(user_id)
    if alert:
        await send_message(update, alert)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command - Cancel session without recording."""
    user_id = get_user_id(update)
    session = get_active_session(user_id)
    
    if not session:
        await send_message(update, "❌ No active session to cancel.")
        return
    
    cancel_session(session["id"])
    
    start_time = datetime.fromisoformat(session["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=NORWAY_TZ)
    duration = datetime.now(NORWAY_TZ) - start_time
    hours = duration.total_seconds() / 3600
    
    await send_message(update, f"🚫 *Session cancelled*\n\n{session['apparat_name']} ({format_duration(hours)}) - not recorded.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - Show current session status."""
    user_id = get_user_id(update)
    session = get_active_session(user_id)
    
    if not session:
        await send_message(update, "📊 No active session.\n\nStart one with `/use [appliance]`")
        return
    
    # Get user settings
    settings = get_user_settings(user_id)
    region = settings.get("region", "NO1")
    fixed_cost = settings.get("fixed_cost_nok", 1.0)
    
    # Parse start time
    start_time = datetime.fromisoformat(session["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=NORWAY_TZ)
    
    # Estimate current cost
    result = await estimate_current_cost(
        start_time,
        session["actual_watt"],
        fixed_cost,
        region
    )
    
    mode_emoji = {"low": "🔋", "high": "⚡", "avg": "📊"}[session["watt_mode"]]
    duration_str = format_duration(result["hours"])
    
    text = f"""📊 *Active Session*

📟 *{session['apparat_name']}* @ {session['actual_watt']}W ({mode_emoji})
⏱ Running: {duration_str}
⚡ Current: {result['kwh']:.3f} kWh

💰 *Estimated cost so far:*
   Spot ({region}): {result['spot_cost']:.2f} kr
   Fixed: {result['fixed_cost']:.2f} kr
   *Total: {result['total_cost']:.2f} kr*

Use `/stop` to end or `/cancel` to abort."""
    
    await send_message(update, text)
    
    # Check for runtime alert
    alert = await check_runtime_alert(user_id)
    if alert:
        await send_message(update, alert)


async def cmd_mnd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mnd command - Show monthly summary. Optional: /mnd [month] or /mnd [month] [year]"""
    user_id = get_user_id(update)
    now = datetime.now(NORWAY_TZ)
    
    # Parse optional month/year arguments
    year = now.year
    month = now.month
    
    if context.args:
        try:
            month = int(context.args[0])
            if month < 1 or month > 12:
                await send_message(update, "❌ Month must be 1-12.")
                return
            if len(context.args) > 1:
                year = int(context.args[1])
        except ValueError:
            await send_message(update, "❌ Usage: /mnd or /mnd \\[month] or /mnd \\[month] \\[year]\\n\\nExample: /mnd 2 (February) or /mnd 12 2025")
            return
    
    summary = get_monthly_summary(user_id, year, month)
    region_name = format_region_name(summary["region"])
    
    # Show if viewing past month
    is_current = (year == now.year and month == now.month)
    month_label = f"{MONTH_NAMES[month]} {year}" + (" *(current)*" if is_current else "")
    
    text = f"""📅 *{month_label}* ({summary['region']} - {region_name})

📊 Sessions: {summary['session_count']}
⚡ Usage: {summary['total_kwh']:.2f} kWh
💰 Total: {summary['total_cost']:.2f} kr
   • Spot: {summary['spot_cost']:.2f} kr
   • Fixed: {summary['fixed_cost']:.2f} kr
📈 Average: {summary['avg_price_per_kwh']:.2f} kr/kWh"""
    
    if summary["budget"] and is_current:
        percentage = ((summary["budget"] - summary["remaining"]) / summary["budget"]) * 100
        text += f"\n\n💼 *Budget:* {summary['remaining']:.2f} kr remaining of {summary['budget']:.2f} kr ({percentage:.0f}% used)"
    
    text += "\n\n_Prices from hvakosterstrommen.no_"
    
    await send_message(update, text)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command - Show recent sessions."""
    user_id = get_user_id(update)
    sessions = get_session_history(user_id, limit=10)
    
    if not sessions:
        await send_message(update, "📜 No session history yet.\n\nStart tracking with `/use [appliance]`")
        return
    
    lines = ["📜 *Recent Sessions:*\n"]
    
    for s in sessions:
        end_time = datetime.fromisoformat(s["end_time"])
        date_str = end_time.strftime("%d/%m %H:%M")
        lines.append(f"• {date_str} - *{s['apparat_name']}*: {s['kwh']:.2f} kWh, {s['total_cost_nok']:.2f} kr")
    
    await send_message(update, "\n".join(lines))


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /budget command - Set monthly budget."""
    user_id = get_user_id(update)
    
    if not context.args:
        settings = get_user_settings(user_id)
        budget = settings.get("budget_nok")
        if budget:
            summary = get_monthly_summary(user_id)
            await send_message(update, f"💼 *Budget:* {budget:.2f} kr\n\nRemaining: {summary['remaining']:.2f} kr\n\nSet new budget: `/budget [kr]`")
        else:
            await send_message(update, "💼 No budget set.\n\nSet one: `/budget [kr]`")
        return
    
    try:
        budget = float(context.args[0])
    except ValueError:
        await send_message(update, "❌ Invalid amount. Use: `/budget 200`")
        return
    
    if budget <= 0:
        update_user_setting(user_id, budget_nok=None)
        await send_message(update, "💼 Budget disabled.")
    else:
        update_user_setting(user_id, budget_nok=budget)
        await send_message(update, f"✅ Budget set to *{budget:.2f} kr* per month.")


async def cmd_set_fastkost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_fastkost command - Set fixed cost per kWh."""
    user_id = get_user_id(update)
    
    if not context.args:
        settings = get_user_settings(user_id)
        fixed = settings.get("fixed_cost_nok", 1.0)
        await send_message(update, f"⚙️ *Fixed cost:* {fixed:.2f} kr/kWh\n\n(Includes nettleie, avgifter, MVA)\n\nChange: `/set_fastkost [kr]`")
        return
    
    try:
        cost = float(context.args[0])
    except ValueError:
        await send_message(update, "❌ Invalid amount. Use: `/set_fastkost 1`")
        return
    
    if cost < 0:
        await send_message(update, "❌ Cost cannot be negative.")
        return
    
    update_user_setting(user_id, fixed_cost_nok=cost)
    await send_message(update, f"✅ Fixed cost set to *{cost:.2f} kr/kWh*\n\n⚠️ _Adjust this based on your electricity bill (nettleie + avgifter + MVA)_")


async def cmd_set_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_region command - Set price region."""
    user_id = get_user_id(update)
    
    if not context.args:
        settings = get_user_settings(user_id)
        current = settings.get("region", "NO1")
        await send_message(update, f"🗺️ Current region: *{current}* ({format_region_name(current)})\n\nChange region:", reply_markup=get_region_keyboard())
        return
    
    region = context.args[0].upper()
    if region not in VALID_REGIONS:
        await send_message(update, f"❌ Invalid region. Choose: {', '.join(sorted(VALID_REGIONS))}")
        return
    
    update_user_setting(user_id, region=region)
    await send_message(update, f"✅ Region set to *{region}* ({format_region_name(region)})")


async def callback_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle region selection callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id(update)
    data = query.data.split(":")
    
    if len(data) != 2 or data[0] != "region":
        return
    
    region = data[1]
    update_user_setting(user_id, region=region)
    
    await query.edit_message_text(f"✅ Region set to *{region}* ({format_region_name(region)})", parse_mode="Markdown")


async def cmd_set_periode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_periode command - Set billing period start day."""
    user_id = get_user_id(update)
    
    if not context.args:
        settings = get_user_settings(user_id)
        day = settings.get("period_start_day", 1)
        await send_message(update, f"📆 Billing period starts on day *{day}* of each month.\n\nChange: `/set_periode [day]` (1-28)")
        return
    
    try:
        day = int(context.args[0])
    except ValueError:
        await send_message(update, "❌ Invalid day. Use: `/set_periode 5`")
        return
    
    if day < 1 or day > 28:
        await send_message(update, "❌ Day must be between 1 and 28.")
        return
    
    update_user_setting(user_id, period_start_day=day)
    await send_message(update, f"✅ Billing period now starts on day *{day}* of each month.")


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /config command - Show all current settings."""
    user_id = get_user_id(update)
    settings = get_user_settings(user_id)
    apparater = get_all_apparater(user_id)
    
    region = settings.get("region", "NO1")
    fixed_cost = settings.get("fixed_cost_nok", 1.0)
    budget = settings.get("budget_nok")
    period_day = settings.get("period_start_day", 1)
    max_duration = settings.get("max_duration_hours", 0)
    
    text = f"""⚙️ *Your Configuration*

*Region:* {region} ({format_region_name(region)})
*Fixed cost:* {fixed_cost:.2f} kr/kWh
*Budget:* {f'{budget:.2f} kr/month' if budget else 'Not set'}
*Billing period:* Day {period_day} of each month
*Auto-stop:* {f'After {max_duration}h' if max_duration > 0 else 'Disabled'}

*Appliances:* {len(apparater)} registered"""
    
    if apparater:
        text += "\n"
        for a in apparater:
            text += f"\n• {a['name']} ({a['low_watt']}W / {a['high_watt']}W)"
    
    text += "\n\n_Use /help to see how to change settings_"
    
    await send_message(update, text)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command - Clear session history."""
    user_id = get_user_id(update)
    sessions = get_session_history(user_id, limit=100)
    
    if not sessions:
        await send_message(update, "🗑️ No sessions to clear.")
        return
    
    # Calculate totals for confirmation
    total_kwh = sum(s.get("kwh", 0) or 0 for s in sessions)
    total_cost = sum(s.get("total_cost_nok", 0) or 0 for s in sessions)
    
    text = f"""⚠️ *Clear all session history?*

This will delete *{len(sessions)} sessions*:
• {total_kwh:.2f} kWh total
• {total_cost:.2f} kr total

_This cannot be undone!_"""
    
    await send_message(update, text, reply_markup=get_confirm_keyboard("clear", "all"))


async def callback_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle clear confirmation callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id(update)
    data = query.data.split(":")
    
    if len(data) != 3 or data[0] != "confirm":
        return
    
    action, item = data[1], data[2]
    
    if action == "cancel":
        await query.edit_message_text("❌ Cancelled. Sessions kept.")
        return
    
    if action == "clear":
        deleted = clear_sessions(user_id)
        await query.edit_message_text(f"✅ Cleared *{deleted} sessions*.\n\nStarting fresh!", parse_mode="Markdown")


async def callback_appliance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle appliance selection from button."""
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id(update)
    data = query.data.split(":")
    
    if len(data) != 3 or data[0] != "app":
        return
    
    action, name = data[1], data[2]
    
    if action == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return
    
    if action == "use":
        # Get appliance and show watt mode selection
        apparat = get_apparat(user_id, name)
        if not apparat:
            await query.edit_message_text(f"❌ Appliance *{name}* not found.", parse_mode="Markdown")
            return
        
        # Get current spot price for display
        settings = get_user_settings(user_id)
        region = settings.get("region", "NO1")
        current_price = await get_current_price(region)
        price_text = f"{current_price:.4f} kr/kWh" if current_price else "unavailable"
        
        avg_watt = (apparat["low_watt"] + apparat["high_watt"]) // 2
        
        text = f"""⚡ *Start tracking: {name}*

Select power mode:
🔋 Low: {apparat['low_watt']}W
⚡ High: {apparat['high_watt']}W  
📊 Avg: {avg_watt}W

Current spot price ({region}): {price_text}
Fixed cost: {settings.get('fixed_cost_nok', 1.0):.2f} kr/kWh"""
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_watt_mode_keyboard(name))
    
    elif action == "delete":
        success = delete_apparat(user_id, name)
        if success:
            await query.edit_message_text(f"🗑️ *{name}* deleted.", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ Appliance *{name}* not found.", parse_mode="Markdown")


async def callback_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle session action buttons (stop/status/cancel)."""
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id(update)
    data = query.data.split(":")
    
    if len(data) != 2 or data[0] != "session":
        return
    
    action = data[1]
    session = get_active_session(user_id)
    
    if not session:
        await query.edit_message_text("❌ No active session.")
        return
    
    if action == "stop":
        # Get user settings
        settings = get_user_settings(user_id)
        region = settings.get("region", "NO1")
        fixed_cost = settings.get("fixed_cost_nok", 1.0)
        
        # Parse start time
        start_time = datetime.fromisoformat(session["start_time"])
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=NORWAY_TZ)
        end_time = datetime.now(NORWAY_TZ)
        
        # Calculate costs
        result = await calculate_session_cost(
            start_time, end_time,
            session["actual_watt"],
            fixed_cost,
            region
        )
        
        # Save session
        end_session(
            session["id"],
            result["kwh"],
            result["spot_cost"],
            result["fixed_cost"],
            result["total_cost"]
        )
        
        # Get monthly summary
        now = datetime.now(NORWAY_TZ)
        summary = get_monthly_summary(user_id, now.year, now.month)
        
        mode_emoji = {"low": "🔋", "high": "⚡", "avg": "📊"}[session["watt_mode"]]
        duration_str = format_duration(result["hours"])
        
        text = f"""✅ *Session ended: {session['apparat_name']}*

⏱ Duration: {duration_str} ({mode_emoji} {session['watt_mode']})
⚡ Consumption: {result['kwh']:.2f} kWh

💰 *Cost:*
   Spot: {result['spot_cost']:.2f} kr
   Fixed: {result['fixed_cost']:.2f} kr
   *Total: {result['total_cost']:.2f} kr*

📊 *{MONTH_NAMES[now.month]}:* {summary['total_kwh']:.2f} kWh / {summary['total_cost']:.2f} kr"""
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif action == "status":
        # Get user settings
        settings = get_user_settings(user_id)
        region = settings.get("region", "NO1")
        fixed_cost = settings.get("fixed_cost_nok", 1.0)
        
        # Parse start time
        start_time = datetime.fromisoformat(session["start_time"])
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=NORWAY_TZ)
        
        # Estimate current cost
        result = await estimate_current_cost(
            start_time,
            session["actual_watt"],
            fixed_cost,
            region
        )
        
        mode_emoji = {"low": "🔋", "high": "⚡", "avg": "📊"}[session["watt_mode"]]
        duration_str = format_duration(result["hours"])
        
        text = f"""📊 *Active Session*

📟 *{session['apparat_name']}* @ {session['actual_watt']}W ({mode_emoji})
⏱ Running: {duration_str}
⚡ Current: {result['kwh']:.3f} kWh

💰 *Estimated:* {result['total_cost']:.2f} kr"""
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_session_action_keyboard())
    
    elif action == "cancel":
        cancel_session(session["id"])
        await query.edit_message_text(f"🚫 *Session cancelled*\n\n{session['apparat_name']} - not recorded.", parse_mode="Markdown")


# ============ Setup ============

def setup_handlers(application: Application) -> None:
    """Register all command and callback handlers."""
    # Command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("list", cmd_list))
    application.add_handler(CommandHandler("delete", cmd_delete))
    application.add_handler(CommandHandler("use", cmd_use))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("mnd", cmd_mnd))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("budget", cmd_budget))
    application.add_handler(CommandHandler("set_fastkost", cmd_set_fastkost))
    application.add_handler(CommandHandler("set_region", cmd_set_region))
    application.add_handler(CommandHandler("set_periode", cmd_set_periode))
    application.add_handler(CommandHandler("config", cmd_config))
    application.add_handler(CommandHandler("clear", cmd_clear))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(callback_watt_mode, pattern=r"^watt:"))
    application.add_handler(CallbackQueryHandler(callback_region, pattern=r"^region:"))
    application.add_handler(CallbackQueryHandler(callback_clear, pattern=r"^confirm:"))
    application.add_handler(CallbackQueryHandler(callback_appliance, pattern=r"^app:"))
    application.add_handler(CallbackQueryHandler(callback_session, pattern=r"^session:"))


async def set_commands(application: Application) -> None:
    """Set bot commands for the command menu."""
    commands = [
        BotCommand("start", "Welcome & quick start"),
        BotCommand("help", "Full help & formulas"),
        BotCommand("add", "Add appliance [name] [low] [high]"),
        BotCommand("list", "List all appliances"),
        BotCommand("delete", "Delete appliance [name]"),
        BotCommand("use", "Start tracking [name]"),
        BotCommand("stop", "End session, show costs"),
        BotCommand("cancel", "Cancel without recording"),
        BotCommand("status", "Current session status"),
        BotCommand("mnd", "Monthly summary"),
        BotCommand("history", "Recent sessions"),
        BotCommand("budget", "Set/view budget [kr]"),
        BotCommand("set_fastkost", "Set fixed cost [kr/kWh]"),
        BotCommand("set_region", "Set price region [NO1-5]"),
        BotCommand("set_periode", "Set billing period [day]"),
        BotCommand("config", "View all settings"),
        BotCommand("clear", "Clear session history"),
    ]
    await application.bot.set_my_commands(commands)
