import sqlite3
import json

db_path = r"e:\GitHub\Antigravity_Universal_Connector\reference_repo_analysis.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

modules = [
    ("src-tauri/src/modules/integration.rs", "System Integration", 1103, 41259,
     "Orchestrates account switching, process shutdown/relaunch, and OS-level Keyring/Keychain injection (Windows CredWriteW, macOS security, Linux secret-tool).",
     json.dumps([
         "resolve_effective_target: Disambiguates between native Antigravity, Antigravity IDE, Cursor, and agy CLI",
         "on_account_switch: Closes running instances, takes path snapshot, injects credentials, and relaunches with sanitized args",
         "write_to_system_keyring: Injects RFC3339 formatted JSON token directly into Win32 Credential Manager (advapi32.dll), macOS Keychain, or Linux Secret Service",
         "CredWriteW (Windows): Direct Win32 API FFI call to write CRED_TYPE_GENERIC 'gemini:antigravity' credential"
     ]),
     json.dumps([
         "KeyringPayload: token { access_token, token_type, refresh_token, expiry }, auth_method: 'consumer'",
         "CREDENTIALW struct: Win32 native struct for Advapi32 CredWriteW"
     ]),
     "On Linux GNOME, writes to both 'login' and 'default' collections to prevent agy CLI credential forks. On Windows, calls CredDeleteW before CredWriteW to ensure zero stale handles.",
     "VERIFIED_FULL"),

    ("src-tauri/src/modules/version.rs", "Version Detection", 330, 10832,
     "Cross-platform binary version extractor without launching GUI or spawning subprocesses.",
     json.dumps([
         "get_antigravity_version_with_path: Dispatches platform-specific inspection",
         "get_version_windows: Uses native Win32 version.dll (GetFileVersionInfoSizeW, GetFileVersionInfoW, VerQueryValueW) to read VsFixedFileInfo directly from binary PE headers",
         "get_version_macos: Parses Info.plist CFBundleShortVersionString without running app",
         "get_version_linux: Inspects resources/app/package.json to avoid launching Electron GUI"
     ]),
     json.dumps([
         "AntigravityVersion { short_version, bundle_version }",
         "VsFixedFileInfo: Win32 PE version header struct"
     ]),
     "Zero subprocess invocation on Windows prevents hanging or anti-virus popup triggers; reads raw PE header.",
     "VERIFIED_FULL")
]

cur.executemany("""
INSERT OR REPLACE INTO repo_modules 
(module_path, category, lines_of_code, size_bytes, purpose, critical_functions, data_structures, edge_cases_and_gotchas, analysis_status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", modules)

conn.commit()
conn.close()
print("Updated reference_repo_analysis.db with integration.rs and version.rs details.")
