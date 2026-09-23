r"""Account Manager and OAuth Loopback Service.
Direct line-by-line refactor of E:\GitHub\Antigravity-Manager\src-tauri\src\modules\oauth.rs,
oauth_server.rs, and db.rs.
Contains:
1. Built-in Google OAuth Credentials (CLIENT_ID, CLIENT_SECRET)
2. Ephemeral Loopback Listener on Port 0
3. 1-Click Import from local Antigravity state.vscdb
4. Active Account Switching with Protobuf State Injection
Zero regex used.
"""

from __future__ import annotations
import asyncio
import base64
import http.server
import json
import os
import socket
import sqlite3
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from .database import db
from .quota_service import QuotaService, NATIVE_OAUTH_USER_AGENT
from .vscdb_importer import find_active_db_path, extract_oauth_state_from_db
from .protobuf_codec import (
    create_oauth_info,
    create_unified_state_entry,
    create_unified_topic_entry,
    remove_unified_topic_entry,
    create_minimal_user_status_payload,
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = " ".join([
    "openid",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
])


def get_oauth_credentials() -> Tuple[str, str]:
    """Retrieve Google OAuth Client ID and Secret with multi-tier resolution:
    1. Environment variables: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
       or ANTIGRAVITY_CLIENT_ID / ANTIGRAVITY_CLIENT_SECRET
    2. Local persistent app_settings in database
    3. Error raised if not configured when starting custom OAuth login
    """
    client_id = (
        os.environ.get("GOOGLE_CLIENT_ID")
        or os.environ.get("ANTIGRAVITY_CLIENT_ID")
        or db.get_setting("google_client_id")
    )
    client_secret = (
        os.environ.get("GOOGLE_CLIENT_SECRET")
        or os.environ.get("ANTIGRAVITY_CLIENT_SECRET")
        or db.get_setting("google_client_secret")
    )

    if not client_id or not client_secret:
        raise ValueError(
            "Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET environment variables or configure them in settings."
        )

    return client_id.strip(), client_secret.strip()


class EphemeralOAuthServer:
    """Ephemeral loopback server on port 0 for Google OAuth callback.
    Port of oauth_server.rs:76-180.
    """

    def __init__(self):
        self.server: Optional[http.server.HTTPServer] = None
        self.port: int = 0
        self.auth_code: Optional[str] = None
        self.error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self.done_event = threading.Event()

    def start(self) -> int:
        parent = self

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress default server logs

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/oauth-callback":
                    params = urllib.parse.parse_qs(parsed.query)
                    if "code" in params:
                        parent.auth_code = params["code"][0]
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        html = (
                            "<html><body style='font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #f8fafc;'>"
                            "<h1 style='color: #10b981;'>&#x2705; Authorization Successful!</h1>"
                            "<p style='color: #94a3b8;'>You can close this window and return to Antigravity Universal Connector.</p>"
                            "<script>setTimeout(function() { window.close(); }, 2500);</script>"
                            "</body></html>"
                        )
                        self.wfile.write(html.encode("utf-8"))
                    else:
                        parent.error = params.get("error", ["Unknown error"])[0]
                        self.send_response(400)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(b"<h1>Authorization Failed</h1>")
                    parent.done_event.set()
                else:
                    self.send_response(404)
                    self.end_headers()

        # Bind to 127.0.0.1:0 for ephemeral port allocation
        self.server = http.server.HTTPServer(("127.0.0.1", 0), CallbackHandler)
        self.port = self.server.server_port
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def wait_for_code(self, timeout: float = 120.0) -> Optional[str]:
        self.done_event.wait(timeout)
        self.shutdown()
        return self.auth_code

    def shutdown(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None


class AccountManager:
    """Core account and session rotation manager."""

    @classmethod
    async def exchange_code_for_token(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens against Google OAuth.
        Port of oauth.rs:369-450.
        """
        client_id, client_secret = get_oauth_credentials()
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"User-Agent": NATIVE_OAUTH_USER_AGENT}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(TOKEN_URL, data=payload, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Token exchange failed: {resp.text}")
            return resp.json()

    @classmethod
    async def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """Refresh Google access token using refresh_token.
        Port of oauth.rs:513-584.
        """
        client_id, client_secret = get_oauth_credentials()
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        headers = {"User-Agent": NATIVE_OAUTH_USER_AGENT}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(TOKEN_URL, data=payload, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Refresh failed: {resp.text}")
            return resp.json()

    @classmethod
    async def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """Fetch Google profile details (email, name, picture).
        Port of oauth.rs:676-703.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": NATIVE_OAUTH_USER_AGENT,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(USERINFO_URL, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Failed to fetch user info: {resp.text}")
            return resp.json()

    @classmethod
    async def import_from_antigravity_db(cls) -> Dict[str, Any]:
        """1-Click Local Import directly from Antigravity's state.vscdb.
        Port of migration.rs:376-382 and migration.rs:422-505.
        """
        db_path = find_active_db_path()
        if not db_path:
            raise FileNotFoundError("Antigravity database (state.vscdb) not found on system")

        state = extract_oauth_state_from_db(db_path)
        refresh_token = state["refresh_token"]

        # Refresh token to verify validity and fetch user profile
        token_data = await cls.refresh_access_token(refresh_token)
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        user_info = await cls.get_user_info(access_token)

        email = user_info.get("email", "unknown@gmail.com")
        name = user_info.get("name", email)
        picture = user_info.get("picture", "")

        # Fetch initial quota
        quota_data = await QuotaService.fetch_full_quota(access_token, state.get("project_id"))

        # Save to database
        account = db.add_or_update_account(
            email=email,
            name=name,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(time.time()) + expires_in,
            picture_url=picture,
            quota_data=quota_data,
        )
        return account

    @classmethod
    def prepare_oauth_login(cls) -> Tuple[str, EphemeralOAuthServer]:
        """Start loopback listener and build authorization URL.
        Port of oauth_server.rs:47-142.
        """
        client_id, _ = get_oauth_credentials()
        server = EphemeralOAuthServer()
        port = server.start()
        redirect_uri = f"http://127.0.0.1:{port}/oauth-callback"

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
        return url, server

    @classmethod
    async def finish_oauth_login(cls, code: str, port: int) -> Dict[str, Any]:
        """Exchange callback code and persist new account."""
        redirect_uri = f"http://127.0.0.1:{port}/oauth-callback"
        token_resp = await cls.exchange_code_for_token(code, redirect_uri)

        access_token = token_resp["access_token"]
        refresh_token = token_resp.get("refresh_token")
        if not refresh_token:
            raise ValueError("Google did not return a refresh token. Re-authorization required.")

        expires_in = token_resp.get("expires_in", 3600)
        user_info = await cls.get_user_info(access_token)
        email = user_info.get("email", "")
        name = user_info.get("name", email)
        picture = user_info.get("picture", "")

        quota_data = await QuotaService.fetch_full_quota(access_token)

        account = db.add_or_update_account(
            email=email,
            name=name,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(time.time()) + expires_in,
            picture_url=picture,
            quota_data=quota_data,
        )
        return account

    @classmethod
    async def switch_active_account(cls, account_id: str) -> None:
        """Switch active account and inject protobuf session into Antigravity state.vscdb.
        Port of db.rs:103-221 and account_service.rs:94-100.
        """
        acc = db.get_account(account_id)
        if not acc:
            raise ValueError(f"Account {account_id} not found")

        # 1. Ensure access token is fresh
        now = int(time.time())
        if acc["expires_at"] <= now + 300:
            token_resp = await cls.refresh_access_token(acc["refresh_token"])
            access_token = token_resp["access_token"]
            expires_in = token_resp.get("expires_in", 3600)
            db.update_tokens(account_id, access_token, acc["refresh_token"], now + expires_in)
            acc["access_token"] = access_token
            acc["expires_at"] = now + expires_in

        # 2. Inject session into Antigravity state.vscdb
        db_path = find_active_db_path()
        if db_path and db_path.exists():
            cls._inject_into_vscdb(
                db_path=db_path,
                access_token=acc["access_token"],
                refresh_token=acc["refresh_token"],
                expiry=acc["expires_at"],
                email=acc["email"],
            )

        # 3. Mark active in local DB
        db.set_active_account(account_id)

    @classmethod
    def _inject_into_vscdb(cls, db_path: Path, access_token: str, refresh_token: str, expiry: int, email: str) -> None:
        """Encode Protobuf OAuthTokenInfo and write to Antigravity ItemTable.
        Port of db.rs:146-221.
        """
        oauth_info_blob = create_oauth_info(
            access_token=access_token,
            refresh_token=refresh_token,
            expiry=expiry,
            is_gcp_tos=False,
            email=email,
        )

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        try:
            # Read current topic if exists
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.oauthToken'")
            row = cursor.fetchone()
            current_topic = b""
            if row and row[0]:
                try:
                    current_topic = base64.b64decode(row[0])
                except Exception:
                    pass

            # Remove old sentinel entry and append new entry
            cleaned_topic = remove_unified_topic_entry(current_topic, "oauthTokenInfoSentinelKey")
            new_entry = create_unified_topic_entry("oauthTokenInfoSentinelKey", oauth_info_blob)
            final_topic = cleaned_topic + new_entry
            final_b64 = base64.b64encode(final_topic).decode("ascii")

            # Write oauthToken
            cursor.execute(
                "INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('antigravityUnifiedStateSync.oauthToken', ?)",
                (final_b64,),
            )

            # Write user status
            status_payload = create_minimal_user_status_payload(email)
            status_entry_b64 = create_unified_state_entry("userStatusSentinelKey", status_payload)
            cursor.execute(
                "INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('antigravityUnifiedStateSync.userStatus', ?)",
                (status_entry_b64,),
            )

            # Set onboarding flag & clear stale legacy key
            cursor.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('antigravityOnboarding', 'true')")
            cursor.execute("DELETE FROM ItemTable WHERE key = 'jetskiStateSync.agentManagerInitState'")

            conn.commit()
        finally:
            conn.close()
