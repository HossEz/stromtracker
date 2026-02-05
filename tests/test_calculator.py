"""
Unit tests for the cost calculator module.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from core.calculator import calculate_watt, format_duration


NORWAY_TZ = ZoneInfo("Europe/Oslo")


class TestCalculateWatt:
    """Tests for watt calculation based on mode."""
    
    def test_low_mode(self):
        """Test low power mode returns low wattage."""
        assert calculate_watt(750, 1500, "low") == 750
    
    def test_high_mode(self):
        """Test high power mode returns high wattage."""
        assert calculate_watt(750, 1500, "high") == 1500
    
    def test_avg_mode(self):
        """Test average mode returns mean of low and high."""
        assert calculate_watt(750, 1500, "avg") == 1125
    
    def test_avg_mode_odd_numbers(self):
        """Test average with odd result (integer division)."""
        assert calculate_watt(100, 201, "avg") == 150  # (100+201)//2 = 150
    
    def test_same_low_high(self):
        """Test when low and high are the same."""
        assert calculate_watt(1000, 1000, "low") == 1000
        assert calculate_watt(1000, 1000, "high") == 1000
        assert calculate_watt(1000, 1000, "avg") == 1000


class TestFormatDuration:
    """Tests for duration formatting."""
    
    def test_only_hours(self):
        """Test formatting whole hours."""
        assert format_duration(2.0) == "2h"
        assert format_duration(1.0) == "1h"
    
    def test_only_minutes(self):
        """Test formatting minutes only."""
        assert format_duration(0.5) == "30m"
        assert format_duration(0.25) == "15m"
    
    def test_hours_and_minutes(self):
        """Test formatting hours and minutes."""
        assert format_duration(1.5) == "1h 30m"
        assert format_duration(2.25) == "2h 15m"
    
    def test_zero(self):
        """Test zero duration."""
        assert format_duration(0) == "0m"
    
    def test_small_duration(self):
        """Test very small duration."""
        assert format_duration(0.016667) == "1m"  # ~1 minute


class TestCostCalculation:
    """Tests for cost calculation logic (unit tests without API)."""
    
    def test_basic_cost_formula(self):
        """Test the basic cost formula: kWh = hours * (watts/1000)."""
        # 2 hours at 1000W = 2 kWh
        hours = 2.0
        watts = 1000
        kwh = hours * (watts / 1000)
        assert kwh == 2.0
        
        # 1.5 hours at 1500W = 2.25 kWh
        hours = 1.5
        watts = 1500
        kwh = hours * (watts / 1000)
        assert kwh == 2.25
    
    def test_cost_with_spot_and_fixed(self):
        """Test total cost = spot_cost + fixed_cost."""
        kwh = 2.25
        spot_price = 1.21  # NOK/kWh
        fixed_cost = 1.80  # NOK/kWh
        
        spot_cost = kwh * spot_price
        fixed_cost_total = kwh * fixed_cost
        total = spot_cost + fixed_cost_total
        
        assert round(spot_cost, 2) == 2.72
        assert round(fixed_cost_total, 2) == 4.05
        assert round(total, 2) == 6.77
    
    def test_mva_calculation(self):
        """Test 25% MVA is applied correctly."""
        raw_price = 1.48  # From API (without MVA)
        mva_rate = 0.25
        price_with_mva = raw_price * (1 + mva_rate)
        
        assert round(price_with_mva, 2) == 1.85
