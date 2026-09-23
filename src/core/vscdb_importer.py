r"""Direct local Antigravity database importer.
Direct line-by-line refactor of E:\GitHub\Antigravity-Manager\src-tauri\src\modules\migration.rs
and db.rs.
Extracts the logged-in Google refresh token from state.vscdb without browser login.
"""

from __future__ import annotations
import os
import sqlite3
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any

from .protobuf_codec import (
    decode_unified_state_entry,
    find_field,
    find_varint_field,
)


def get_all_candidate_db_paths() -> List[Path]:
    """Find all potential Antigravity state.vscdb paths across Windows/macOS/Linux.
    Port of db.rs:18-86.
    """
    paths: List[Path] = []
    folder_names = ["Antigravity", "Antigravity IDE"]

    # Windows APPDATA
    appdata = os.environ.get("APPDATA")
    if appdata:
        for folder in folder_names:
            paths.append(Path(appdata) / folder / "User" / "globalStorage" / "state.vscdb")

    # macOS ~/Library/Application Support
    home = Path.home()
    for folder in folder_names:
        paths.append(home / "Library" / "Application Support" / folder / "User" / "globalStorage" / "state.vscdb")

    # Linux ~/.config
    for folder in folder_names:
        paths.append(home / ".config" / folder / "User" / "globalStorage" / "state.vscdb")

    return paths


def find_active_db_path() -> Optional[Path]:
    """Return the first existing state.vscdb path."""
    for p in get_all_candidate_db_paths():
        if p.exists():
            return p
    return None


def extract_oauth_state_from_db(db_path: Path) -> Dict[str, Any]:
    """Extract refresh_token, is_gcp_tos, and enterprise project_id from state.vscdb.
    Port of migration.rs:422-505.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # Use URI read-only connection to avoid SQLite locking collisions with running IDE
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()

    try:
        # 1. Try new format (>= 1.16.5): antigravityUnifiedStateSync.oauthToken
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.oauthToken'")
        row = cursor.fetchone()

        if row and row[0]:
            outer_b64 = row[0]
            sentinel_key, oauth_info_blob = decode_unified_state_entry(
                outer_b64, target_sentinel="oauthTokenInfoSentinelKey"
            )
            if sentinel_key != "oauthTokenInfoSentinelKey":
                raise ValueError(f"Unexpected sentinel key: {sentinel_key}")

            # Field 3 in OAuthInfo: refresh_token
            refresh_bytes = find_field(oauth_info_blob, 3)
            if not refresh_bytes:
                raise ValueError("Refresh Token not found in OAuthInfo (Field 3)")

            refresh_token = refresh_bytes.decode("utf-8")
            is_gcp_tos_val = find_varint_field(oauth_info_blob, 6)
            is_gcp_tos = True if is_gcp_tos_val is None or is_gcp_tos_val != 0 else False

            # Extract enterprise project ID if present
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.enterprisePreferences'")
            pref_row = cursor.fetchone()
            project_id = None
            if pref_row and pref_row[0]:
                try:
                    pref_sentinel, pref_payload = decode_unified_state_entry(pref_row[0])
                    if pref_sentinel == "enterpriseGcpProjectId":
                        pid_bytes = find_field(pref_payload, 3)
                        if pid_bytes:
                            project_id = pid_bytes.decode("utf-8").strip() or None
                except Exception:
                    pass

            return {
                "refresh_token": refresh_token,
                "is_gcp_tos": is_gcp_tos,
                "project_id": project_id,
            }

        # 2. Try legacy format (< 1.16.5): jetskiStateSync.agentManagerInitState
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'jetskiStateSync.agentManagerInitState'")
        legacy_row = cursor.fetchone()
        if legacy_row and legacy_row[0]:
            blob = base64.b64decode(legacy_row[0])
            oauth_data = find_field(blob, 6)
            if oauth_data:
                refresh_bytes = find_field(oauth_data, 3)
                if refresh_bytes:
                    return {
                        "refresh_token": refresh_bytes.decode("utf-8"),
                        "is_gcp_tos": True,
                        "project_id": None,
                    }

        raise ValueError("No OAuth credentials found in Antigravity state.vscdb")
    finally:
        conn.close()


class VscdbImporter:
    """Wrapper class providing static helper methods for 1-click import."""
    get_all_candidate_db_paths = staticmethod(get_all_candidate_db_paths)
    find_active_db_path = staticmethod(find_active_db_path)
    extract_oauth_state_from_db = staticmethod(extract_oauth_state_from_db)

    @classmethod
    def import_live_antigravity_account(cls) -> Optional[Dict[str, Any]]:
        db_path = cls.find_active_db_path()
        if not db_path:
            return None
        return cls.extract_oauth_state_from_db(db_path)


