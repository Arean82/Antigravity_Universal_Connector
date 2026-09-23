import ctypes
from ctypes import wintypes
import json
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Windows Advapi32 Credential Types
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2

class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]

class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.c_char_p),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]

class KeyringService:
    TARGET_NAME = "gemini:antigravity"
    USER_NAME = "antigravity"

    @classmethod
    def write_credential(cls, access_token: str, refresh_token: str, expiry_timestamp: int) -> bool:
        """
        Injects Google OAuth tokens directly into Windows Credential Manager.
        Replicates exact logic from src-tauri/src/modules/integration.rs:386-463.
        """
        if sys.platform != "win32":
            return False

        # Format ISO 8601 RFC3339 with microsecond precision
        dt = datetime.fromtimestamp(expiry_timestamp, tz=timezone.utc)
        expiry_str = dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        payload = {
            "token": {
                "access_token": access_token,
                "token_type": "Bearer",
                "refresh_token": refresh_token,
                "expiry": expiry_str
            },
            "auth_method": "consumer"
        }
        raw_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        advapi32 = ctypes.windll.advapi32

        # 1. Delete prior credential to prevent stale handle lock
        cls.delete_credential()

        # 2. Write new CREDENTIALW
        cred = CREDENTIALW()
        cred.Flags = 0
        cred.Type = CRED_TYPE_GENERIC
        cred.TargetName = cls.TARGET_NAME
        cred.Comment = None
        cred.LastWritten = FILETIME(0, 0)
        cred.CredentialBlobSize = len(raw_json)
        cred.CredentialBlob = raw_json
        cred.Persist = CRED_PERSIST_LOCAL_MACHINE
        cred.AttributeCount = 0
        cred.Attributes = None
        cred.TargetAlias = None
        cred.UserName = cls.USER_NAME

        res = advapi32.CredWriteW(ctypes.byref(cred), 0)
        return bool(res)

    @classmethod
    def delete_credential(cls) -> bool:
        if sys.platform != "win32":
            return False
        advapi32 = ctypes.windll.advapi32
        res = advapi32.CredDeleteW(cls.TARGET_NAME, CRED_TYPE_GENERIC, 0)
        return bool(res)

    @classmethod
    def read_credential(cls) -> Optional[Dict[str, Any]]:
        """
        Reads raw credential from Windows Credential Manager.
        """
        if sys.platform != "win32":
            return None
        advapi32 = ctypes.windll.advapi32
        pcred = ctypes.POINTER(CREDENTIALW)()
        res = advapi32.CredReadW(cls.TARGET_NAME, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred))
        if not res:
            return None
        try:
            blob = ctypes.string_at(pcred.contents.CredentialBlob, pcred.contents.CredentialBlobSize)
            return json.loads(blob.decode('utf-8'))
        except Exception:
            return None
        finally:
            advapi32.CredFree(pcred)
