"""
Price API module for fetching NO1-NO5 spot prices from hvakosterstrommen.no.
Includes caching to minimize API calls.
"""

import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from database.models import cache_prices, get_cached_prices

logger = logging.getLogger(__name__)

# Norwegian timezone
NORWAY_TZ = ZoneInfo("Europe/Oslo")

# API base URL
API_BASE = "https://www.hvakosterstrommen.no/api/v1/prices"

# Valid regions
VALID_REGIONS = {"NO1", "NO2", "NO3", "NO4", "NO5"}

# MVA rate (25% for all regions except NO4)
MVA_RATE = 0.25
MVA_EXEMPT_REGIONS = {"NO4"}  # Nord-Norge is exempt from MVA


async def fetch_daily_prices(date: datetime, region: str = "NO1") -> Optional[dict[int, float]]:
    """
    Fetch all hourly prices for a specific date and region.
    Returns dict of hour (0-23) -> price in NOK/kWh (with MVA added).
    
    Prices are cached to avoid repeated API calls.
    """
    if region not in VALID_REGIONS:
        logger.error(f"Invalid region: {region}. Must be one of {VALID_REGIONS}")
        return None
    
    date_str = date.strftime("%Y-%m-%d")
    
    # Check cache first
    cached = get_cached_prices(date_str, region)
    if cached:
        logger.debug(f"Using cached prices for {date_str} {region}")
        return cached
    
    # Fetch from API
    url = f"{API_BASE}/{date.strftime('%Y')}/{date.strftime('%m-%d')}_{region}.json"
    logger.info(f"Fetching prices from: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.error(f"API returned status {response.status}")
                    return None
                
                data = await response.json()
    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")
        return None
    
    # Parse response and add MVA
    prices = {}
    mva_multiplier = 1.0 if region in MVA_EXEMPT_REGIONS else (1 + MVA_RATE)
    
    for entry in data:
        # Parse the hour from time_start
        time_start = datetime.fromisoformat(entry["time_start"])
        hour = time_start.hour
        
        # Get price and add MVA
        price_raw = entry["NOK_per_kWh"]
        price_with_mva = price_raw * mva_multiplier
        prices[hour] = round(price_with_mva, 5)
    
    # Cache the prices
    cache_prices(date_str, region, list(prices.items()))
    logger.info(f"Cached {len(prices)} hourly prices for {date_str} {region}")
    
    return prices


async def get_current_price(region: str = "NO1") -> Optional[float]:
    """
    Get the current hour's spot price in NOK/kWh (with MVA).
    """
    now = datetime.now(NORWAY_TZ)
    prices = await fetch_daily_prices(now, region)
    
    if not prices:
        return None
    
    current_hour = now.hour
    return prices.get(current_hour)


async def get_price_for_hour(dt: datetime, region: str = "NO1") -> Optional[float]:
    """
    Get the spot price for a specific datetime.
    """
    # Ensure datetime is in Norwegian timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=NORWAY_TZ)
    else:
        dt = dt.astimezone(NORWAY_TZ)
    
    prices = await fetch_daily_prices(dt, region)
    
    if not prices:
        return None
    
    return prices.get(dt.hour)


async def get_prices_for_period(start: datetime, end: datetime, region: str = "NO1") -> list[tuple[datetime, float]]:
    """
    Get all hourly prices for a time period.
    Returns list of (datetime, price) tuples for each hour.
    
    Used for accurate hour-by-hour cost calculation.
    """
    # Ensure datetimes are in Norwegian timezone
    if start.tzinfo is None:
        start = start.replace(tzinfo=NORWAY_TZ)
    else:
        start = start.astimezone(NORWAY_TZ)
    
    if end.tzinfo is None:
        end = end.replace(tzinfo=NORWAY_TZ)
    else:
        end = end.astimezone(NORWAY_TZ)
    
    prices_list = []
    current = start.replace(minute=0, second=0, microsecond=0)
    
    while current < end:
        price = await get_price_for_hour(current, region)
        if price is not None:
            prices_list.append((current, price))
        current += timedelta(hours=1)
    
    return prices_list


def format_region_name(region: str) -> str:
    """Get human-readable name for a region."""
    names = {
        "NO1": "Oslo / Øst-Norge",
        "NO2": "Kristiansand / Sør-Norge",
        "NO3": "Trondheim / Midt-Norge",
        "NO4": "Tromsø / Nord-Norge",
        "NO5": "Bergen / Vest-Norge"
    }
    return names.get(region, region)
