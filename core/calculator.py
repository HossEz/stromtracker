"""
Cost calculation module for electricity usage tracking.
Implements hour-by-hour accurate pricing.
"""

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from core.price_api import get_prices_for_period, get_current_price, NORWAY_TZ

import logging

logger = logging.getLogger(__name__)


def calculate_watt(low_watt: int, high_watt: int, mode: str) -> int:
    """
    Calculate actual wattage based on mode.
    
    Args:
        low_watt: Low power setting (e.g., 750W)
        high_watt: High power setting (e.g., 1500W)
        mode: 'low', 'high', or 'avg'
    
    Returns:
        Actual wattage to use for calculations
    """
    if mode == "low":
        return low_watt
    elif mode == "high":
        return high_watt
    else:  # avg
        return (low_watt + high_watt) // 2


async def calculate_session_cost(
    start_time: datetime,
    end_time: datetime,
    watt: int,
    fixed_cost_per_kwh: float,
    region: str = "NO1"
) -> dict:
    """
    Calculate the cost of a session using hour-by-hour spot prices.
    
    This provides accurate calculations for sessions spanning multiple hours
    with varying electricity prices.
    
    Args:
        start_time: Session start datetime
        end_time: Session end datetime
        watt: Power consumption in watts
        fixed_cost_per_kwh: Fixed cost (nettleie + avgifter) per kWh with MVA
        region: Price region (NO1-NO5)
    
    Returns:
        dict with:
            - hours: Total duration in hours
            - kwh: Total energy consumption
            - spot_cost: Cost from spot prices
            - fixed_cost: Cost from fixed charges
            - total_cost: Total cost
            - avg_spot_price: Average spot price for the session
            - hourly_breakdown: List of hourly calculations (for detailed view)
    """
    # Ensure times are in Norwegian timezone
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=NORWAY_TZ)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=NORWAY_TZ)
    
    duration = end_time - start_time
    total_hours = duration.total_seconds() / 3600
    
    if total_hours <= 0:
        return {
            "hours": 0,
            "kwh": 0,
            "spot_cost": 0,
            "fixed_cost": 0,
            "total_cost": 0,
            "avg_spot_price": 0,
            "hourly_breakdown": []
        }
    
    # Get hourly prices for the period
    hourly_prices = await get_prices_for_period(start_time, end_time, region)
    
    if not hourly_prices:
        # Fallback: use current price for entire session
        current_price = await get_current_price(region)
        if current_price is None:
            current_price = 1.5  # Emergency fallback price
            logger.warning("Using emergency fallback price of 1.5 NOK/kWh")
        
        kwh = total_hours * (watt / 1000)
        spot_cost = kwh * current_price
        fixed_cost = kwh * fixed_cost_per_kwh
        
        return {
            "hours": round(total_hours, 2),
            "kwh": round(kwh, 4),
            "spot_cost": round(spot_cost, 2),
            "fixed_cost": round(fixed_cost, 2),
            "total_cost": round(spot_cost + fixed_cost, 2),
            "avg_spot_price": round(current_price, 4),
            "hourly_breakdown": []
        }
    
    # Calculate cost for each hour
    breakdown = []
    total_spot_cost = 0
    total_kwh = 0
    
    for i, (hour_start, price) in enumerate(hourly_prices):
        # Calculate how much of this hour was used
        hour_end = hour_start + timedelta(hours=1)
        
        # Clip to session boundaries
        actual_start = max(hour_start, start_time)
        actual_end = min(hour_end, end_time)
        
        # Calculate fraction of hour used
        hour_fraction = (actual_end - actual_start).total_seconds() / 3600
        
        if hour_fraction <= 0:
            continue
        
        # Calculate consumption and cost for this hour
        hour_kwh = hour_fraction * (watt / 1000)
        hour_spot_cost = hour_kwh * price
        
        total_kwh += hour_kwh
        total_spot_cost += hour_spot_cost
        
        breakdown.append({
            "hour": hour_start.strftime("%H:%M"),
            "fraction": round(hour_fraction, 2),
            "price": round(price, 4),
            "kwh": round(hour_kwh, 4),
            "cost": round(hour_spot_cost, 2)
        })
    
    # Calculate fixed cost based on total kWh
    total_fixed_cost = total_kwh * fixed_cost_per_kwh
    
    # Calculate average spot price
    avg_spot_price = total_spot_cost / total_kwh if total_kwh > 0 else 0
    
    return {
        "hours": round(total_hours, 2),
        "kwh": round(total_kwh, 4),
        "spot_cost": round(total_spot_cost, 2),
        "fixed_cost": round(total_fixed_cost, 2),
        "total_cost": round(total_spot_cost + total_fixed_cost, 2),
        "avg_spot_price": round(avg_spot_price, 4),
        "hourly_breakdown": breakdown
    }


async def estimate_current_cost(
    start_time: datetime,
    watt: int,
    fixed_cost_per_kwh: float,
    region: str = "NO1"
) -> dict:
    """
    Estimate the current running cost of an active session.
    Uses the same hour-by-hour calculation.
    """
    now = datetime.now(NORWAY_TZ)
    return await calculate_session_cost(start_time, now, watt, fixed_cost_per_kwh, region)


def format_duration(hours: float) -> str:
    """Format duration in hours to human-readable string."""
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    
    if h == 0:
        return f"{m}m"
    elif m == 0:
        return f"{h}h"
    else:
        return f"{h}h {m}m"
