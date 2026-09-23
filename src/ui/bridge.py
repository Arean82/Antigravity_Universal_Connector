import sys
import json
import asyncio
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Slot, Signal
from src.core.database import db
from src.core.vscdb_importer import VscdbImporter
from src.core.account_manager import AccountManager
from src.core.quota_service import QuotaService
from src.core.keyring_service import KeyringService
from src.core.process_supervisor import ProcessSupervisor
from src.proxy.server import LocalProxyServer

DEFAULT_APP_CONFIG = {
    "language": "en",
    "theme": "system",
    "auto_refresh": True,
    "refresh_interval": 15,
    "auto_sync": False,
    "sync_interval": 5,
    "default_export_path": None,
    "antigravity_executable": None,
    "antigravity_ide_executable": None,
    "antigravity_cli_executable": None,
    "antigravity_args": None,
    "auto_launch": False,
    "auto_check_update": False,
    "update_check_interval": 24,
    "accounts_page_size": 0,
    "hidden_menu_items": [],
    "scheduled_warmup": {
        "enabled": False,
        "monitored_models": ["gemini-3-flash", "claude", "gemini-3-pro-high", "gemini-3.1-flash-image"]
    },
    "quota_protection": {
        "enabled": False,
        "threshold_percentage": 10,
        "monitored_models": ["claude", "gemini-3-pro-high", "gemini-3-flash", "gemini-3.1-flash-image"]
    },
    "pinned_quota_models": {
        "models": ["gemini-3-pro-high", "gemini-3-flash", "gemini-3.1-flash-image", "claude-sonnet-4-6-thinking"]
    },
    "circuit_breaker": {
        "enabled": True,
        "backoff_steps": [60, 300, 1800, 7200],
        "lock_on_zero_quota": False
    },
    "proxy": {
        "enabled": False,
        "allow_lan_access": False,
        "auth_mode": "off",
        "port": 8045,
        "api_key": "sk-antigravity-local",
        "auto_start": False,
        "request_timeout": 60,
        "enable_logging": True,
        "capture_health_logs": False,
        "log_retention": {
            "max_body_age_hours": 24,
            "max_storage_gb": 2,
            "max_rows": 10000
        },
        "upstream_proxy": {
            "enabled": False,
            "url": ""
        },
        "thinking_budget": {
            "control_source": "gateway",
            "flash_mode": "default",
            "pro_mode": "default",
            "claude_mode": "default"
        }
    },
    "cloudflared": {
        "enabled": False,
        "domain": "",
        "token": ""
    },
    "lightweight_mode": False
}

class BackendBridge(QObject):
    """
    QObject exposed via QWebChannel to JavaScript.
    Handles all IPC requests from the frontend Vue/React interface.
    """
    accountSwitched = Signal(str)
    quotaUpdated = Signal(str)
    proxyStatusChanged = Signal(bool, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proxy_server: Optional[LocalProxyServer] = None
        self.proxy_task = None
        self.config = dict(DEFAULT_APP_CONFIG)
        self._load_config_from_db()

    def _load_config_from_db(self):
        try:
            saved = db.get_setting("app_config")
            if saved:
                saved_cfg = json.loads(saved)
                if isinstance(saved_cfg, dict):
                    self.config.update(saved_cfg)
        except Exception as e:
            print(f"Error loading config from SQLite: {e}")

    @Slot(result=str)
    def load_config(self) -> str:
        """Returns application configuration matching AppConfig schema."""
        return json.dumps(self.config)

    @Slot(str, result=str)
    def save_config(self, config_json: str) -> str:
        try:
            new_cfg = json.loads(config_json)
            self.config.update(new_cfg)
            db.set_setting("app_config", json.dumps(self.config))
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(str, result=str)
    def save_last_route(self, route: str) -> str:
        try:
            if route:
                db.set_setting("last_active_route", route)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(result=str)
    def get_last_route(self) -> str:
        try:
            route = db.get_setting("last_active_route", "/")
            return json.dumps({"route": route or "/"})
        except Exception:
            return json.dumps({"route": "/"})

    @Slot(result=str)
    def is_debug_console_enabled(self) -> str:
        return json.dumps(False)

    @Slot(result=str)
    def list_accounts(self) -> str:
        accounts = db.list_accounts()
        current_id = None
        normalized = []
        for a in accounts:
            acc_id = str(a.get("id") or "")
            is_active = bool(a.get("is_active"))
            status = "active" if is_active else "inactive"
            if is_active and not current_id:
                current_id = acc_id
            normalized.append({
                "id": acc_id,
                "email": a.get("email") or "",
                "name": a.get("name") or a.get("email") or "",
                "picture": a.get("picture") or "",
                "status": status,
                "is_active": is_active,
                "subscription_tier": a.get("subscription_tier") or "FREE",
                "quota": a.get("quota") or {},
                "created_at": a.get("created_at") or 0,
                "last_refreshed": a.get("last_refreshed") or 0
            })
        return json.dumps({
            "accounts": normalized,
            "current_account_id": current_id
        })

    @Slot(result=str)
    def get_current_account(self) -> str:
        accounts = db.list_accounts()
        for a in accounts:
            if a.get("is_active"):
                return json.dumps({
                    "id": str(a.get("id") or ""),
                    "email": a.get("email") or "",
                    "name": a.get("name") or a.get("email") or "",
                    "picture": a.get("picture") or "",
                    "status": "active",
                    "is_active": True,
                    "subscription_tier": a.get("subscription_tier") or "FREE",
                    "quota": a.get("quota") or {}
                })
        return json.dumps(None)

    @Slot(str, str, result=str)
    def add_account(self, email: str, refresh_token: str) -> str:
        """Add an account via refresh token."""
        try:
            loop = asyncio.get_event_loop()
            token_data = loop.run_until_complete(AccountManager.refresh_access_token(refresh_token))
            access_token = token_data.get("access_token", "")
            expires_in = token_data.get("expires_in", 3600)
            
            user_info = {}
            if access_token:
                try:
                    user_info = loop.run_until_complete(AccountManager.get_user_info(access_token))
                except Exception:
                    pass
            
            resolved_email = email or user_info.get("email") or "account@gmail.com"
            name = user_info.get("name", resolved_email)
            picture = user_info.get("picture", "")
            
            quota_data = {}
            if access_token:
                try:
                    quota_data = QuotaService.inspect_quota(access_token)
                except Exception:
                    pass

            import time
            account = db.add_or_update_account(
                email=resolved_email,
                name=name,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=int(time.time()) + expires_in,
                picture_url=picture,
                quota_data=quota_data
            )
            return json.dumps(account)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @Slot(str, result=str)
    def delete_account(self, account_id: str) -> str:
        db.delete_account(account_id)
        return json.dumps({"success": True})

    @Slot(result=str)
    def import_from_vscdb(self) -> str:
        try:
            acc = VscdbImporter.import_live_antigravity_account()
            if acc:
                return json.dumps({"success": True, "account": acc})
            return json.dumps({"success": False, "error": "No Antigravity tokens found in local database"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(str, result=str)
    def switch_account(self, account_id: str) -> str:
        accounts = db.list_accounts()
        target = next((a for a in accounts if a["id"] == account_id), None)
        if not target:
            return json.dumps({"success": False, "error": "Account not found"})

        KeyringService.write_credential(
            target["access_token"],
            target["refresh_token"],
            target["expiry_timestamp"]
        )

        success, msg = ProcessSupervisor.restart_antigravity()
        self.accountSwitched.emit(account_id)
        return json.dumps({"success": success, "message": msg})

    @Slot(str, result=str)
    def fetch_account_quota(self, account_id: str) -> str:
        accounts = db.list_accounts()
        target = next((a for a in accounts if a["id"] == account_id), None)
        if not target:
            return json.dumps({"success": False, "error": "Account not found"})

        access_token = AccountManager.get_active_token(account_id)
        if not access_token:
            return json.dumps({"success": False, "error": "Failed to obtain valid access token"})

        quota = QuotaService.inspect_quota(access_token)
        self.quotaUpdated.emit(account_id)
        return json.dumps(quota)

    @Slot(result=str)
    def get_proxy_status(self) -> str:
        is_running = self.proxy_server is not None
        port = self.proxy_server.port if self.proxy_server else 8045
        accounts = db.list_accounts()
        active_count = len([a for a in accounts if a.get("is_active")])
        return json.dumps({
            "running": is_running,
            "port": port,
            "base_url": f"http://127.0.0.1:{port}",
            "active_accounts": active_count
        })

    @Slot(int, result=str)
    def start_proxy(self, port: int = 8045) -> str:
        if self.proxy_server and self.proxy_server.server and not getattr(self.proxy_server.server, "should_exit", False):
            return json.dumps({"success": True, "message": "Proxy already running", "port": self.proxy_server.port})

        if self.proxy_server:
            self.proxy_server.stop()

        self.proxy_server = LocalProxyServer(port=port)
        self.proxy_server.start()
        self.proxyStatusChanged.emit(True, port)
        return json.dumps({"success": True, "port": port})

    @Slot(result=str)
    def stop_proxy(self) -> str:
        if not self.proxy_server:
            return json.dumps({"success": True, "message": "Proxy not running"})

        self.proxy_server.stop()
        self.proxy_server = None
        self.proxyStatusChanged.emit(False, 0)
        return json.dumps({"success": True})
