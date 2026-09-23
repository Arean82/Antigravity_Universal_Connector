"""FastAPI Local REST Service for Accounts, Auth, and Quota endpoints.
Used by the PySide6 desktop interface and local services.
Runs completely offline with zero external CDNs.
Zero regex used.
"""

from __future__ import annotations
import asyncio
import webbrowser
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import db
from .account_manager import AccountManager
from .quota_service import QuotaService

app = FastAPI(title="Antigravity Universal Connector Core")
auth_app = app

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active OAuth listener reference
active_oauth_server = None


@app.get("/api/accounts")
async def get_accounts():
    """Return all accounts, current active account, and quota summaries."""
    accounts = db.list_accounts()
    active_acc = db.get_active_account()
    return {
        "accounts": accounts,
        "active_account_id": active_acc["id"] if active_acc else None,
    }


@app.post("/api/accounts/import-local")
async def import_local_account():
    """1-Click import from Antigravity's local state.vscdb."""
    try:
        account = await AccountManager.import_from_antigravity_db()
        return {"status": "success", "account": account}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/auth/login-url")
@app.post("/api/auth/start-oauth")
async def start_oauth_flow():
    """Start ephemeral loopback listener and open Google OAuth login in browser."""
    global active_oauth_server
    try:
        url, server = AccountManager.prepare_oauth_login()
        active_oauth_server = server

        # Open in system default browser
        webbrowser.open(url)

        # Run loopback wait in background task
        async def wait_code_task():
            global active_oauth_server
            loop = asyncio.get_event_loop()
            code = await loop.run_in_executor(None, server.wait_for_code)
            if code:
                try:
                    await AccountManager.finish_oauth_login(code, server.port)
                except Exception as ex:
                    print(f"OAuth finish error: {ex}")
            active_oauth_server = None

        asyncio.create_task(wait_code_task())
        return {
            "status": "started",
            "port": server.port,
            "auth_url": url,
            "url": url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SwitchRequest(BaseModel):
    account_id: str


@app.post("/api/accounts/switch")
async def switch_account(req: SwitchRequest):
    """Switch active account and inject protobuf session into Antigravity."""
    try:
        await AccountManager.switch_active_account(req.account_id)
        return {"status": "success", "active_account_id": req.account_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class RefreshRequest(BaseModel):
    account_id: str


@app.post("/api/accounts/refresh-quota")
async def refresh_quota(req: RefreshRequest):
    """Fetch updated quota for an account from Cloud Code."""
    acc = db.get_account(req.account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        # Refresh access token
        token_data = await AccountManager.refresh_access_token(acc["refresh_token"])
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        now = int(asyncio.get_event_loop().time())
        db.update_tokens(acc["id"], access_token, acc["refresh_token"], now + expires_in)

        # Fetch quota
        quota_data = await QuotaService.fetch_full_quota(access_token)
        db.update_quota(acc["id"], quota_data)
        return {"status": "success", "quota": quota_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class DeleteRequest(BaseModel):
    account_id: str


@app.post("/api/accounts/delete")
async def delete_account(req: DeleteRequest):
    """Delete an account from the local database."""
    db.delete_account(req.account_id)
    return {"status": "success"}
