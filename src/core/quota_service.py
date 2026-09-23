r"""Google Cloud Code Quota Inspection Engine.
Direct line-by-line refactor of E:\GitHub\Antigravity-Manager\src-tauri\src\modules\quota.rs.
Inspects:
1. loadCodeAssist (Subscription tier: FREE, PRO, ULTRA)
2. fetchAvailableModels (Remaining fractions, reset timers, deprecated model mappings)
3. retrieveUserQuotaSummary (Rolling 5-hour and 7-day weekly quota buckets)
Zero regex used.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

# Upstream Cloud Code endpoints with failover (Sandbox -> Daily -> Prod)
LOAD_PROJECT_ENDPOINTS = [
    "https://daily-cloudcode-pa.sandbox.googleapis.com/v1internal:loadCodeAssist",
    "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
    "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
]

QUOTA_API_ENDPOINTS = [
    "https://daily-cloudcode-pa.sandbox.googleapis.com/v1internal:fetchAvailableModels",
    "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
    "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
]

QUOTA_SUMMARY_ENDPOINTS = [
    "https://daily-cloudcode-pa.sandbox.googleapis.com/v1internal:retrieveUserQuotaSummary",
    "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary",
    "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary",
]

NATIVE_OAUTH_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class QuotaService:
    """Production-grade quota service ported directly from quota.rs."""

    @staticmethod
    async def fetch_project_and_tier(access_token: str) -> Tuple[Optional[str], str]:
        """Fetch project_id and authoritative subscription tier via loadCodeAssist.
        Port of quota.rs:157-262.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": NATIVE_OAUTH_USER_AGENT,
        }
        body = {"metadata": {"ideType": "ANTIGRAVITY"}}

        async with httpx.AsyncClient(timeout=15.0) as client:
            for ep_url in LOAD_PROJECT_ENDPOINTS:
                try:
                    resp = await client.post(ep_url, headers=headers, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        project_id = data.get("cloudaicompanionProject")

                        # Tier resolution priority (quota.rs:187-224)
                        paid_tier = data.get("paidTier") or {}
                        current_tier = data.get("currentTier") or {}
                        raw_tier = paid_tier.get("id") or paid_tier.get("name") or current_tier.get("id") or current_tier.get("name") or "free-tier"

                        raw_lower = raw_tier.lower()
                        if "ultra" in raw_lower:
                            tier = "ULTRA"
                        elif "pro" in raw_lower:
                            tier = "PRO"
                        else:
                            tier = "FREE"

                        return project_id, tier
                except Exception:
                    continue

        return None, "FREE"

    @staticmethod
    async def fetch_quota_summary(access_token: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch 5h and weekly quota bucket summaries via retrieveUserQuotaSummary.
        Port of quota.rs:541-550.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": NATIVE_OAUTH_USER_AGENT,
        }
        body = {"project": project_id} if project_id else {}

        async with httpx.AsyncClient(timeout=15.0) as client:
            for ep_url in QUOTA_SUMMARY_ENDPOINTS:
                try:
                    resp = await client.post(ep_url, headers=headers, json=body)
                    if resp.status_code == 200:
                        return resp.json().get("groups", [])
                except Exception:
                    continue
        return []

    @classmethod
    async def fetch_full_quota(cls, access_token: str, cached_project_id: Optional[str] = None) -> Dict[str, Any]:
        """Unified entry point for full quota inspection.
        Port of quota.rs:274-535.
        """
        # 1. Fetch Tier & Project ID
        fresh_project_id, tier = await cls.fetch_project_and_tier(access_token)
        project_id = fresh_project_id or cached_project_id

        # 2. Fetch Available Models
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": NATIVE_OAUTH_USER_AGENT,
        }
        body = {"project": project_id} if project_id else {}

        models_list: List[Dict[str, Any]] = []
        is_forbidden = False

        async with httpx.AsyncClient(timeout=15.0) as client:
            for ep_url in QUOTA_API_ENDPOINTS:
                try:
                    resp = await client.post(ep_url, headers=headers, json=body)
                    if resp.status_code == 403:
                        is_forbidden = True
                        break

                    if resp.status_code == 200:
                        data = resp.json()
                        raw_models = data.get("models", {})

                        for name, info in raw_models.items():
                            name_lower = name.lower()
                            # Filter only relevant chat & image models (quota.rs:397-402)
                            if (
                                name_lower.startswith("gemini")
                                or name_lower.startswith("claude")
                                or name_lower.startswith("gpt")
                                or name_lower.startswith("image")
                            ):
                                q_info = info.get("quotaInfo") or {}
                                fraction = q_info.get("remainingFraction", 1.0)
                                percentage = int(round(fraction * 100)) if fraction is not None else 100
                                reset_time = q_info.get("resetTime", "")

                                models_list.append({
                                    "name": name,
                                    "display_name": info.get("displayName", name),
                                    "percentage": percentage,
                                    "reset_time": reset_time,
                                    "supports_thinking": info.get("supportsThinking", False),
                                })
                        break
                except Exception:
                    continue

        # 3. Fuse Real 5h and Weekly Rolling Buckets (quota.rs:444-512)
        summary_groups = await cls.fetch_quota_summary(access_token, project_id)
        if summary_groups and models_list:
            for model in models_list:
                m_name = model["name"].lower()
                is_gemini = m_name.startswith("gemini")
                is_claude_gpt = m_name.startswith("claude") or m_name.startswith("gpt")

                for group in summary_groups:
                    g_name = (group.get("displayName") or "").lower()
                    matches = False
                    if is_claude_gpt and ("claude" in g_name or "gpt" in g_name or "3p" in g_name):
                        matches = True
                    elif is_gemini and ("gemini" in g_name or ("claude" not in g_name and "gpt" not in g_name)):
                        matches = True

                    if matches:
                        buckets = group.get("buckets", [])
                        b_5h = None
                        b_week = None
                        for b in buckets:
                            w = (b.get("window") or "").lower()
                            bid = (b.get("bucketId") or "").lower()
                            if "5h" in w or "5h" in bid or "hour" in w:
                                b_5h = b
                            if "week" in w or "week" in bid or "7d" in w:
                                b_week = b

                        chosen = None
                        if b_5h and b_week:
                            w_frac = b_week.get("remainingFraction", 1.0)
                            h_frac = b_5h.get("remainingFraction", 1.0)
                            if w_frac <= 0.001:
                                chosen = b_week
                            elif h_frac <= w_frac:
                                chosen = b_5h
                            else:
                                chosen = b_week
                        elif b_5h:
                            chosen = b_5h
                        elif b_week:
                            chosen = b_week
                        elif buckets:
                            chosen = buckets[0]

                        if chosen:
                            frac = chosen.get("remainingFraction", 1.0)
                            model["percentage"] = int(round(frac * 100))
                            if chosen.get("resetTime"):
                                model["reset_time"] = chosen["resetTime"]
                        break

        # Calculate primary Flash and Pro levels
        flash_pct = 100
        pro_pct = 100
        flash_reset = ""
        pro_reset = ""

        for m in models_list:
            m_name = m["name"].lower()
            if "flash" in m_name and "gemini" in m_name:
                flash_pct = m["percentage"]
                flash_reset = m["reset_time"]
            elif "pro" in m_name and "gemini" in m_name:
                pro_pct = m["percentage"]
                pro_reset = m["reset_time"]

        return {
            "tier": tier,
            "project_id": project_id,
            "is_forbidden": is_forbidden,
            "flash_percentage": flash_pct,
            "flash_reset": flash_reset,
            "pro_percentage": pro_pct,
            "pro_reset": pro_reset,
            "models": models_list,
            "last_updated": int(time.time()),
        }
