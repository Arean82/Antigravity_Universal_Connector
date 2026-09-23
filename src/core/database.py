"""SQLite Database Engine for Google Accounts & Quota Storage.
Provides persistent, thread-safe storage for accounts, OAuth tokens, and live quota telemetry
with guaranteed resource cleanup on all operating systems.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from platformdirs import user_data_dir

APP_NAME = "AntigravityUniversalConnector"
APP_AUTHOR = "Antigravity"


class Database:
    """Manages SQLite persistence for Google accounts and quota telemetry."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.db_path = db_path
        else:
            data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "accounts_data.db"

        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()

            # Google Accounts & Quotas Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                picture TEXT DEFAULT '',
                refresh_token TEXT NOT NULL,
                access_token TEXT DEFAULT '',
                expires_at REAL DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                subscription_tier TEXT DEFAULT 'FREE',
                quota_json TEXT DEFAULT '{}',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                last_refreshed REAL DEFAULT 0
            );
            """)

            # Application Settings / Config Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL DEFAULT (strftime('%s', 'now'))
            );
            """)

    def set_setting(self, key: str, value: str) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, strftime('%s', 'now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value),
            )

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def add_or_update_account(
        self,
        email: str,
        refresh_token: str,
        access_token: str = "",
        expires_at: float = 0,
        name: str = "",
        picture: str = "",
    ) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO accounts (email, name, picture, refresh_token, access_token, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(email) DO UPDATE SET
                    refresh_token = excluded.refresh_token,
                    access_token = excluded.access_token,
                    expires_at = excluded.expires_at,
                    name = CASE WHEN excluded.name != '' THEN excluded.name ELSE accounts.name END,
                    picture = CASE WHEN excluded.picture != '' THEN excluded.picture ELSE accounts.picture END
                """,
                (email, name, picture, refresh_token, access_token, expires_at),
            )
            # If this is the first/only account, automatically activate it
            cursor.execute("SELECT COUNT(*) FROM accounts")
            if cursor.fetchone()[0] == 1:
                cursor.execute("UPDATE accounts SET is_active = 1 WHERE email = ?", (email,))

    def update_account_quota(self, email: str, quota_data: Dict[str, Any], subscription_tier: str = "FREE") -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE accounts
                SET quota_json = ?, subscription_tier = ?, last_refreshed = ?
                WHERE email = ?
                """,
                (json.dumps(quota_data), subscription_tier, time.time(), email),
            )

    def get_accounts(self) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts ORDER BY is_active DESC, id ASC")
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                acc = dict(row)
                try:
                    acc["quota"] = json.loads(acc.get("quota_json") or "{}")
                except Exception:
                    acc["quota"] = {}
                results.append(acc)
            return results

    def get_account_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                acc = dict(row)
                try:
                    acc["quota"] = json.loads(acc.get("quota_json") or "{}")
                except Exception:
                    acc["quota"] = {}
                return acc
            return None

    def set_active_account(self, email: str) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET is_active = 0")
            cursor.execute("UPDATE accounts SET is_active = 1 WHERE email = ?", (email,))

    def delete_account(self, email: str) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE email = ?", (email,))
            # If the deleted account was active, activate the first available account
            cursor.execute("SELECT email FROM accounts LIMIT 1")
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE accounts SET is_active = 1 WHERE email = ?", (row["email"],))    # Convenience aliases for cross-layer consistency
    list_accounts = get_accounts
    add_account = add_or_update_account


# Global database instance
db = Database()

