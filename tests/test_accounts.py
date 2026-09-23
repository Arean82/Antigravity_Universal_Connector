"""Enterprise Unit Tests for Phase 1: Google Accounts & Quotas Engine.
Validates SQLite database persistence, REST API responses, and account rotation.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from src.core.auth_server import auth_app
from src.core.database import Database


class TestAccountsPhase1(unittest.TestCase):
    """Test suite for Phase 1 Google Accounts & Quotas functionality."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_accounts.db"
        self.db = Database(self.db_path)
        self.client = TestClient(auth_app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_retrieve_account(self):
        """Verify account addition and default active status for first account."""
        self.db.add_or_update_account(
            email="developer@example.com",
            refresh_token="mock_refresh_token_123",
            access_token="mock_access_token_456",
            expires_at=9999999999,
            name="Test Developer",
            picture="https://example.com/avatar.jpg",
        )

        accounts = self.db.get_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["email"], "developer@example.com")
        self.assertEqual(accounts[0]["name"], "Test Developer")
        self.assertEqual(accounts[0]["is_active"], 1)

    def test_switch_active_account(self):
        """Verify switching active accounts in the database."""
        self.db.add_or_update_account(email="user1@example.com", refresh_token="tok1")
        self.db.add_or_update_account(email="user2@example.com", refresh_token="tok2")

        accounts = self.db.get_accounts()
        self.assertEqual(len(accounts), 2)

        # Switch active to user2
        self.db.set_active_account("user2@example.com")
        updated = self.db.get_accounts()

        active = [a for a in updated if a["is_active"] == 1]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["email"], "user2@example.com")

    def test_update_quota_telemetry(self):
        """Verify updating and persisting quota telemetry in SQLite."""
        self.db.add_or_update_account(email="quota_user@example.com", refresh_token="tok")

        mock_quota = {
            "models": [
                {"name": "gemini-2.5-flash", "percentage": 85, "reset_time": "2026-09-23T18:00:00Z"},
                {"name": "gemini-2.5-pro", "percentage": 60, "reset_time": "2026-09-23T20:00:00Z"},
            ],
            "subscription_tier": "PRO",
            "last_updated": 1727090000,
        }

        self.db.update_account_quota("quota_user@example.com", mock_quota, subscription_tier="PRO")
        acc = self.db.get_account_by_email("quota_user@example.com")

        self.assertIsNotNone(acc)
        self.assertEqual(acc["subscription_tier"], "PRO")
        self.assertEqual(len(acc["quota"]["models"]), 2)
        self.assertEqual(acc["quota"]["models"][0]["percentage"], 85)

    def test_delete_account(self):
        """Verify account deletion and automatic fallback for active status."""
        self.db.add_or_update_account(email="acc1@example.com", refresh_token="t1")
        self.db.add_or_update_account(email="acc2@example.com", refresh_token="t2")

        self.db.delete_account("acc1@example.com")
        remaining = self.db.get_accounts()

        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["email"], "acc2@example.com")
        self.assertEqual(remaining[0]["is_active"], 1)

    def test_rest_api_login_url(self):
        """Verify /api/auth/login-url endpoint returns valid Google consent link."""
        resp = self.client.get("/api/auth/login-url")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("url", data)
        self.assertTrue(data["url"].startswith("https://accounts.google.com/o/oauth2/v2/auth"))
        self.assertIn("client_id=", data["url"])
        self.assertIn("redirect_uri=", data["url"])


if __name__ == "__main__":
    unittest.main()
