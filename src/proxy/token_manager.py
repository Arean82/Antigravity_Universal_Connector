import time
from typing import Dict, Any, Optional, List
from enum import Enum

class RateLimitReason(Enum):
    MODEL_CAPACITY_EXHAUSTED = "ModelCapacityExhausted"
    RATE_LIMIT_EXCEEDED = "RateLimitExceeded"
    QUOTA_EXHAUSTED = "QuotaExhausted"
    UNKNOWN = "Unknown"

class TokenManager:
    """
    Manages accounts, sticky sessions, 429 error classification, and transparent failover.
    Ported directly from src-tauri/src/proxy/token_manager.rs.
    """
    def __init__(self):
        # account_id -> cooldown_until_timestamp
        self.cooldowns: Dict[str, Dict[str, float]] = {}
        # session_id -> account_id
        self.sticky_sessions: Dict[str, str] = {}
        self.rr_index = 0

    @staticmethod
    def classify_rate_limit(error_body: str) -> RateLimitReason:
        body = error_body.lower()
        generic_exhausted = "resource has been exhausted" in body or "resource_exhausted" in body
        explicit_quota = any(x in body for x in [
            "quota_exhausted", "quotaresetdelay", "quota reset", "quota limit", "per day", "daily quota", "credits"
        ])

        if "model_capacity" in body:
            return RateLimitReason.MODEL_CAPACITY_EXHAUSTED
        elif "per minute" in body or "rate limit" in body or "too many requests" in body or (generic_exhausted and not explicit_quota):
            return RateLimitReason.RATE_LIMIT_EXCEEDED
        elif explicit_quota or "exhausted" in body or "quota" in body:
            return RateLimitReason.QUOTA_EXHAUSTED
        return RateLimitReason.UNKNOWN

    def report_rate_limit(self, account_id: str, model: str, reason: RateLimitReason, cooldown_seconds: float = 60.0):
        if account_id not in self.cooldowns:
            self.cooldowns[account_id] = {}
        self.cooldowns[account_id][model] = time.time() + cooldown_seconds

    def is_cooling_down(self, account_id: str, model: str) -> bool:
        if account_id in self.cooldowns and model in self.cooldowns[account_id]:
            if time.time() < self.cooldowns[account_id][model]:
                return True
        return False

    def select_best_account(self, accounts: List[Dict[str, Any]], model: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Selects an available, healthy account. Supports sticky session affinity.
        """
        if not accounts:
            return None

        # Check sticky session first
        if session_id and session_id in self.sticky_sessions:
            assigned_id = self.sticky_sessions[session_id]
            for acc in accounts:
                if acc["id"] == assigned_id and not self.is_cooling_down(assigned_id, model):
                    return acc

        # Otherwise find first healthy account via Round Robin
        available = [a for a in accounts if not self.is_cooling_down(a["id"], model)]
        if not available:
            # Fall back to any account if all are throttled
            return accounts[0]

        self.rr_index = (self.rr_index + 1) % len(available)
        selected = available[self.rr_index]

        if session_id:
            self.sticky_sessions[session_id] = selected["id"]

        return selected
