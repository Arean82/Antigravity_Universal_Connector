import os
import json
import sqlite3
import uuid
import time
from typing import Dict, Any, List, Optional

class DeviceService:
    """
    Generates, binds, and synchronizes virtual device profiles.
    Ported directly from src-tauri/src/modules/device.rs.
    """

    @staticmethod
    def generate_device_profile() -> Dict[str, str]:
        """
        Synthesizes a reproducible, compliant VS Code device fingerprint.
        """
        return {
            "machine_id": uuid.uuid4().hex + uuid.uuid4().hex[:32], # 64 hex chars
            "mac_machine_id": uuid.uuid4().hex + uuid.uuid4().hex[:32],
            "dev_device_id": str(uuid.uuid4()),
            "sqm_id": "{" + str(uuid.uuid4()).upper() + "}"
        }

    @classmethod
    def sync_to_storage_json(cls, storage_path: str, profile: Dict[str, str]) -> bool:
        """
        Writes device profile keys to storage.json.
        """
        if not os.path.exists(storage_path):
            return False

        try:
            with open(storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "telemetry" not in data or not isinstance(data["telemetry"], dict):
                data["telemetry"] = {}

            data["telemetry"]["machineId"] = profile["machine_id"]
            data["telemetry"]["macMachineId"] = profile["mac_machine_id"]
            data["telemetry"]["devDeviceId"] = profile["dev_device_id"]
            data["telemetry"]["sqmId"] = profile["sqm_id"]

            data["storage.serviceMachineId"] = profile["dev_device_id"]

            with open(storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            return True
        except Exception:
            return False

    @classmethod
    def sync_to_state_db(cls, db_path: str, service_machine_id: str) -> bool:
        """
        Writes telemetry.serviceMachineId into state.vscdb ItemTable.
        """
        if not os.path.exists(db_path):
            return False

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO ItemTable (key, value)
            VALUES (?, ?)
            """, ("telemetry.serviceMachineId", service_machine_id))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
