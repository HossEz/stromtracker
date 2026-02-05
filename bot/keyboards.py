"""
Inline keyboards for Telegram bot interactions.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_watt_mode_keyboard(apparat_name: str) -> InlineKeyboardMarkup:
    """
    Create keyboard for selecting watt mode (Low/High/Avg).
    The callback data includes the apparat name for context.
    """
    keyboard = [
        [
            InlineKeyboardButton("🔋 Low", callback_data=f"watt:low:{apparat_name}"),
            InlineKeyboardButton("⚡ High", callback_data=f"watt:high:{apparat_name}"),
            InlineKeyboardButton("📊 Avg", callback_data=f"watt:avg:{apparat_name}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"watt:cancel:{apparat_name}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard(action: str, item_name: str) -> InlineKeyboardMarkup:
    """
    Create a confirmation keyboard for destructive actions.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm:{action}:{item_name}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"confirm:cancel:{item_name}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_region_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for selecting price region.
    """
    keyboard = [
        [
            InlineKeyboardButton("NO1 - Øst", callback_data="region:NO1"),
            InlineKeyboardButton("NO2 - Sør", callback_data="region:NO2"),
        ],
        [
            InlineKeyboardButton("NO3 - Midt", callback_data="region:NO3"),
            InlineKeyboardButton("NO4 - Nord", callback_data="region:NO4"),
        ],
        [
            InlineKeyboardButton("NO5 - Vest", callback_data="region:NO5"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_appliance_keyboard(apparater: list, action: str = "use") -> InlineKeyboardMarkup:
    """
    Create keyboard for selecting an appliance.
    action: 'use' or 'delete'
    """
    keyboard = []
    # 2 appliances per row for mobile
    row = []
    for a in apparater:
        name = a["name"]
        avg = (a["low_watt"] + a["high_watt"]) // 2
        row.append(InlineKeyboardButton(f"{name} ({avg}W)", callback_data=f"app:{action}:{name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"app:cancel:")])
    return InlineKeyboardMarkup(keyboard)


def get_session_action_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for active session actions.
    """
    keyboard = [
        [
            InlineKeyboardButton("🛑 Stop", callback_data="session:stop"),
            InlineKeyboardButton("📊 Status", callback_data="session:status"),
        ],
        [
            InlineKeyboardButton("❌ Cancel session", callback_data="session:cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
