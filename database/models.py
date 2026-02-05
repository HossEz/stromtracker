"""
Database models and schema for the Electricity Tracker Bot.
Uses SQLite for persistent storage.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Database file path (same directory as this module's parent)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stromtracker.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    """Initialize the database with all required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Appliances table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apparater (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            low_watt INTEGER NOT NULL,
            high_watt INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name COLLATE NOCASE)
        )
    """)
    
    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            apparat_id INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            watt_mode TEXT NOT NULL,
            actual_watt INTEGER NOT NULL,
            kwh REAL,
            spot_cost_nok REAL,
            fixed_cost_nok REAL,
            total_cost_nok REAL,
            cancelled BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (apparat_id) REFERENCES apparater(id)
        )
    """)
    
    # User settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            fixed_cost_nok REAL DEFAULT 1.0,
            budget_nok REAL,
            period_start_day INTEGER DEFAULT 1,
            region TEXT DEFAULT 'NO1',
            max_duration_hours INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Price cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            date TEXT NOT NULL,
            region TEXT NOT NULL,
            hour INTEGER NOT NULL,
            price_nok REAL NOT NULL,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, region, hour)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


# ============ Appliance Operations ============

def add_apparat(user_id: int, name: str, low_watt: int, high_watt: int) -> bool:
    """Add a new appliance for a user. Returns True on success, False if exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO apparater (user_id, name, low_watt, high_watt) VALUES (?, ?, ?, ?)",
            (user_id, name, low_watt, high_watt)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_apparat(user_id: int, name: str) -> Optional[dict]:
    """Get an appliance by name for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM apparater WHERE user_id = ? AND name = ? COLLATE NOCASE",
        (user_id, name)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_apparater(user_id: int) -> list[dict]:
    """Get all appliances for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM apparater WHERE user_id = ? ORDER BY name",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_apparat(user_id: int, name: str) -> bool:
    """Delete an appliance. Returns True if deleted, False if not found."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM apparater WHERE user_id = ? AND name = ? COLLATE NOCASE",
        (user_id, name)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ============ Session Operations ============

def start_session(user_id: int, apparat_id: int, watt_mode: str, actual_watt: int) -> int:
    """Start a new tracking session. Returns the session ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO sessions (user_id, apparat_id, start_time, watt_mode, actual_watt)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, apparat_id, datetime.now().isoformat(), watt_mode, actual_watt)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_active_session(user_id: int) -> Optional[dict]:
    """Get the active (non-ended) session for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT s.*, a.name as apparat_name, a.low_watt, a.high_watt
           FROM sessions s
           JOIN apparater a ON s.apparat_id = a.id
           WHERE s.user_id = ? AND s.end_time IS NULL AND s.cancelled = FALSE""",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def end_session(session_id: int, kwh: float, spot_cost: float, fixed_cost: float, total_cost: float) -> None:
    """End a session with calculated costs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE sessions 
           SET end_time = ?, kwh = ?, spot_cost_nok = ?, fixed_cost_nok = ?, total_cost_nok = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), kwh, spot_cost, fixed_cost, total_cost, session_id)
    )
    conn.commit()
    conn.close()


def cancel_session(session_id: int) -> None:
    """Cancel an active session without recording costs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET cancelled = TRUE, end_time = ? WHERE id = ?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()
    conn.close()


def get_monthly_sessions(user_id: int, year: int, month: int, period_start_day: int = 1) -> list[dict]:
    """Get all completed sessions for a billing period."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate period start and end dates
    from datetime import date
    from calendar import monthrange
    
    if period_start_day == 1:
        # Standard calendar month
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)
    else:
        # Custom period: starts on period_start_day of previous month
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year
        start_date = date(prev_year, prev_month, period_start_day)
        end_date = date(year, month, period_start_day - 1) if period_start_day > 1 else date(year, month, monthrange(year, month)[1])
    
    cursor.execute(
        """SELECT s.*, a.name as apparat_name
           FROM sessions s
           JOIN apparater a ON s.apparat_id = a.id
           WHERE s.user_id = ? 
           AND s.end_time IS NOT NULL 
           AND s.cancelled = FALSE
           AND date(s.end_time) BETWEEN ? AND ?
           ORDER BY s.end_time DESC""",
        (user_id, start_date.isoformat(), end_date.isoformat())
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session_history(user_id: int, limit: int = 10) -> list[dict]:
    """Get recent session history for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT s.*, a.name as apparat_name
           FROM sessions s
           JOIN apparater a ON s.apparat_id = a.id
           WHERE s.user_id = ? AND s.end_time IS NOT NULL AND s.cancelled = FALSE
           ORDER BY s.end_time DESC
           LIMIT ?""",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clear_sessions(user_id: int, month: Optional[int] = None, year: Optional[int] = None) -> int:
    """
    Clear sessions for a user.
    If month/year provided, clear only that month. Otherwise clear all.
    Returns number of sessions deleted.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if month and year:
        # Clear specific month
        from datetime import date
        from calendar import monthrange
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)
        
        cursor.execute(
            """DELETE FROM sessions 
               WHERE user_id = ? AND date(end_time) BETWEEN ? AND ?""",
            (user_id, start_date.isoformat(), end_date.isoformat())
        )
    else:
        # Clear all sessions
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


# ============ User Settings Operations ============

def get_user_settings(user_id: int) -> dict:
    """Get or create user settings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        # Create default settings
        cursor.execute(
            "INSERT INTO user_settings (user_id) VALUES (?)",
            (user_id,)
        )
        conn.commit()
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    
    conn.close()
    return dict(row)


def update_user_setting(user_id: int, **kwargs) -> None:
    """Update user settings. Pass any settings as keyword arguments."""
    # Ensure user exists
    get_user_settings(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for key, value in kwargs.items():
        if key in ('fixed_cost_nok', 'budget_nok', 'period_start_day', 'region', 'max_duration_hours'):
            cursor.execute(
                f"UPDATE user_settings SET {key} = ? WHERE user_id = ?",
                (value, user_id)
            )
    
    conn.commit()
    conn.close()


# ============ Price Cache Operations ============

def cache_prices(date: str, region: str, prices: list[tuple[int, float]]) -> None:
    """Cache hourly prices for a date and region."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for hour, price in prices:
        cursor.execute(
            """INSERT OR REPLACE INTO price_cache (date, region, hour, price_nok, cached_at)
               VALUES (?, ?, ?, ?, ?)""",
            (date, region, hour, price, datetime.now().isoformat())
        )
    
    conn.commit()
    conn.close()


def get_cached_prices(date: str, region: str) -> Optional[dict[int, float]]:
    """Get cached prices for a date and region. Returns dict of hour -> price."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT hour, price_nok FROM price_cache WHERE date = ? AND region = ?",
        (date, region)
    )
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return None
    
    return {row['hour']: row['price_nok'] for row in rows}
