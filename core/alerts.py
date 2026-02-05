"""
Alert system for budget warnings and runtime notifications.
"""

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from database.models import get_monthly_sessions, get_user_settings, get_active_session
from core.calculator import estimate_current_cost, NORWAY_TZ

import logging

logger = logging.getLogger(__name__)


async def check_budget_alert(user_id: int) -> Optional[str]:
    """
    Check if user is approaching or exceeding budget.
    Returns alert message if triggered, None otherwise.
    """
    settings = get_user_settings(user_id)
    budget = settings.get("budget_nok")
    
    if not budget or budget <= 0:
        return None
    
    # Get current month's total
    now = datetime.now(NORWAY_TZ)
    sessions = get_monthly_sessions(user_id, now.year, now.month, settings.get("period_start_day", 1))
    
    total_cost = sum(s.get("total_cost_nok", 0) or 0 for s in sessions)
    percentage = (total_cost / budget) * 100
    
    if percentage >= 100:
        return f"⚠️ **Budget exceeded!** {total_cost:.2f} kr / {budget:.2f} kr ({percentage:.0f}%)"
    elif percentage >= 80:
        remaining = budget - total_cost
        return f"⚠️ **Budget warning:** {percentage:.0f}% used. {remaining:.2f} kr remaining."
    
    return None


async def check_runtime_alert(user_id: int) -> Optional[str]:
    """
    Check if active session has been running too long.
    Returns alert message if running > 2 hours, None otherwise.
    """
    session = get_active_session(user_id)
    
    if not session:
        return None
    
    start_time = datetime.fromisoformat(session["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=NORWAY_TZ)
    
    now = datetime.now(NORWAY_TZ)
    duration = now - start_time
    hours = duration.total_seconds() / 3600
    
    if hours >= 2:
        apparat_name = session.get("apparat_name", "Unknown")
        return f"⏰ **Long session:** {apparat_name} has been running for {hours:.1f} hours. Use /stop when done or /cancel to abort."
    
    return None


async def check_max_duration(user_id: int) -> Optional[str]:
    """
    Check if session exceeds max duration setting (auto-stop warning).
    Returns message if max duration reached and enabled.
    """
    settings = get_user_settings(user_id)
    max_hours = settings.get("max_duration_hours", 0)
    
    if not max_hours or max_hours <= 0:
        return None  # Feature disabled
    
    session = get_active_session(user_id)
    if not session:
        return None
    
    start_time = datetime.fromisoformat(session["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=NORWAY_TZ)
    
    now = datetime.now(NORWAY_TZ)
    duration = now - start_time
    hours = duration.total_seconds() / 3600
    
    if hours >= max_hours:
        apparat_name = session.get("apparat_name", "Unknown")
        return f"🛑 **Max duration reached:** {apparat_name} has been running for {hours:.1f}h (limit: {max_hours}h). Session should be stopped."
    
    return None


def get_monthly_summary(user_id: int, year: Optional[int] = None, month: Optional[int] = None) -> dict:
    """
    Get monthly summary statistics.
    """
    now = datetime.now(NORWAY_TZ)
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    settings = get_user_settings(user_id)
    sessions = get_monthly_sessions(user_id, year, month, settings.get("period_start_day", 1))
    
    total_kwh = sum(s.get("kwh", 0) or 0 for s in sessions)
    total_cost = sum(s.get("total_cost_nok", 0) or 0 for s in sessions)
    total_spot = sum(s.get("spot_cost_nok", 0) or 0 for s in sessions)
    total_fixed = sum(s.get("fixed_cost_nok", 0) or 0 for s in sessions)
    
    avg_price = total_cost / total_kwh if total_kwh > 0 else 0
    
    budget = settings.get("budget_nok")
    remaining = budget - total_cost if budget else None
    
    return {
        "year": year,
        "month": month,
        "session_count": len(sessions),
        "total_kwh": round(total_kwh, 2),
        "total_cost": round(total_cost, 2),
        "spot_cost": round(total_spot, 2),
        "fixed_cost": round(total_fixed, 2),
        "avg_price_per_kwh": round(avg_price, 2),
        "budget": budget,
        "remaining": round(remaining, 2) if remaining is not None else None,
        "region": settings.get("region", "NO1")
    }
