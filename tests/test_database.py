"""
Tests for database operations.
"""

import pytest
import os
import tempfile
from datetime import datetime

# Override DB path before importing models
import database.models as models


@pytest.fixture(autouse=True)
def temp_database():
    """Use a temporary database for each test."""
    # Create temp file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Override the DB path
    original_path = models.DB_PATH
    models.DB_PATH = path
    
    # Initialize the database
    models.init_database()
    
    yield path
    
    # Cleanup
    models.DB_PATH = original_path
    try:
        os.unlink(path)
    except:
        pass


class TestApparatOperations:
    """Tests for appliance CRUD operations."""
    
    def test_add_apparat(self):
        """Test adding a new appliance."""
        success = models.add_apparat(123, "Heater", 750, 1500)
        assert success is True
    
    def test_add_duplicate_apparat(self):
        """Test adding duplicate appliance fails."""
        models.add_apparat(123, "Heater", 750, 1500)
        success = models.add_apparat(123, "Heater", 500, 1000)
        assert success is False
    
    def test_add_apparat_case_insensitive(self):
        """Test appliance names are case-insensitive."""
        models.add_apparat(123, "Heater", 750, 1500)
        success = models.add_apparat(123, "heater", 500, 1000)
        assert success is False
    
    def test_get_apparat(self):
        """Test retrieving an appliance."""
        models.add_apparat(123, "Heater", 750, 1500)
        apparat = models.get_apparat(123, "Heater")
        
        assert apparat is not None
        assert apparat["name"] == "Heater"
        assert apparat["low_watt"] == 750
        assert apparat["high_watt"] == 1500
    
    def test_get_apparat_case_insensitive(self):
        """Test retrieving appliance is case-insensitive."""
        models.add_apparat(123, "Heater", 750, 1500)
        apparat = models.get_apparat(123, "HEATER")
        assert apparat is not None
    
    def test_get_nonexistent_apparat(self):
        """Test retrieving non-existent appliance returns None."""
        apparat = models.get_apparat(123, "DoesNotExist")
        assert apparat is None
    
    def test_get_all_apparater(self):
        """Test getting all appliances for a user."""
        models.add_apparat(123, "Heater", 750, 1500)
        models.add_apparat(123, "Fan", 50, 100)
        models.add_apparat(456, "Other", 100, 200)  # Different user
        
        apparater = models.get_all_apparater(123)
        assert len(apparater) == 2
        names = [a["name"] for a in apparater]
        assert "Heater" in names
        assert "Fan" in names
    
    def test_delete_apparat(self):
        """Test deleting an appliance."""
        models.add_apparat(123, "Heater", 750, 1500)
        success = models.delete_apparat(123, "Heater")
        assert success is True
        
        apparat = models.get_apparat(123, "Heater")
        assert apparat is None
    
    def test_delete_nonexistent_apparat(self):
        """Test deleting non-existent appliance returns False."""
        success = models.delete_apparat(123, "DoesNotExist")
        assert success is False


class TestSessionOperations:
    """Tests for session operations."""
    
    def test_start_session(self):
        """Test starting a session."""
        models.add_apparat(123, "Heater", 750, 1500)
        apparat = models.get_apparat(123, "Heater")
        
        session_id = models.start_session(123, apparat["id"], "avg", 1125)
        assert session_id is not None
        assert session_id > 0
    
    def test_get_active_session(self):
        """Test retrieving active session."""
        models.add_apparat(123, "Heater", 750, 1500)
        apparat = models.get_apparat(123, "Heater")
        models.start_session(123, apparat["id"], "high", 1500)
        
        session = models.get_active_session(123)
        assert session is not None
        assert session["watt_mode"] == "high"
        assert session["actual_watt"] == 1500
        assert session["apparat_name"] == "Heater"
    
    def test_no_active_session(self):
        """Test no active session returns None."""
        session = models.get_active_session(123)
        assert session is None
    
    def test_end_session(self):
        """Test ending a session."""
        models.add_apparat(123, "Heater", 750, 1500)
        apparat = models.get_apparat(123, "Heater")
        session_id = models.start_session(123, apparat["id"], "avg", 1125)
        
        models.end_session(session_id, 2.25, 2.72, 4.05, 6.77)
        
        # No longer active
        session = models.get_active_session(123)
        assert session is None
    
    def test_cancel_session(self):
        """Test cancelling a session."""
        models.add_apparat(123, "Heater", 750, 1500)
        apparat = models.get_apparat(123, "Heater")
        session_id = models.start_session(123, apparat["id"], "avg", 1125)
        
        models.cancel_session(session_id)
        
        # No longer active
        session = models.get_active_session(123)
        assert session is None


class TestUserSettings:
    """Tests for user settings operations."""
    
    def test_get_default_settings(self):
        """Test default settings are created."""
        settings = models.get_user_settings(123)
        
        assert settings["user_id"] == 123
        assert settings["fixed_cost_nok"] == 1.8
        assert settings["region"] == "NO1"
        assert settings["period_start_day"] == 1
        assert settings["max_duration_hours"] == 0
    
    def test_update_setting(self):
        """Test updating user settings."""
        models.get_user_settings(123)  # Create user
        
        models.update_user_setting(123, fixed_cost_nok=2.0, region="NO5")
        
        settings = models.get_user_settings(123)
        assert settings["fixed_cost_nok"] == 2.0
        assert settings["region"] == "NO5"
    
    def test_update_budget(self):
        """Test setting budget."""
        models.get_user_settings(123)
        models.update_user_setting(123, budget_nok=200.0)
        
        settings = models.get_user_settings(123)
        assert settings["budget_nok"] == 200.0
