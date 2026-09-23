import sqlite3
import os
import json

db_path = r"e:\GitHub\Antigravity_Universal_Connector\reference_repo_analysis.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS repo_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_path TEXT UNIQUE,
    category TEXT,
    lines_of_code INTEGER,
    size_bytes INTEGER,
    purpose TEXT,
    critical_functions TEXT,
    data_structures TEXT,
    edge_cases_and_gotchas TEXT,
    analysis_status TEXT
)
""")

modules_data = [
    (
        "src-tauri/src/modules/account.rs",
        "Account & Storage",
        2571,
        93445,
        "Account lifecycle, atomic JSON persistence, data directory migration, JSON self-healing, live-limit tracking.",
        json.dumps([
            "get_account_lock(account_id): In-memory per-account Mutex to prevent file write collisions",
            "load_account_at_path(path): Loads account JSON with BOM/NUL byte stripping and trailing character self-healing (Issue #3345)",
            "save_account(account): Atomic file write with fsync to prevent 0-byte corruptions on system crash",
            "get_data_dir(): Resolves data dir via ABV_DATA_DIR env, ABV_DATA_DIR_POINTER_FILE, or ~/.antigravity_tools",
            "migrate_data_dir(new_dir): Moves entire data folder recursively and updates pointer file atomically",
            "task_quota_refresh_keeps_unexpired_live_limit: Ensures background quota refresh does not clear active 429 live limits"
        ]),
        json.dumps([
            "Account: id, email, token, device_profile, quota, disabled, protected_models, live_limited_models, validation_blocked",
            "AccountIndex: version, accounts (summary list), current_account_id, current_target_ide",
            "LiveLimitStatus: model, status (429), reason, until, detected_at, message"
        ]),
        "Self-heals corrupted JSON files by removing BOM, NUL bytes, and extraneous trailing braces. Handles cross-platform Windows extended path prefixes (\\\\?\\UNC\\).",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/models/account.rs",
        "Models",
        241,
        8695,
        "Data definitions for Account, AccountIndex, AccountSummary, and LiveLimitStatus.",
        json.dumps([
            "Account::new(id, email, token): Initializes account with defaults",
            "Account::update_quota(quota): Merges new quota without discarding unexpired historical cycle boundaries or subscription tiers"
        ]),
        json.dumps([
            "Account", "AccountIndex", "AccountSummary", "LiveLimitStatus"
        ]),
        "Quota merging must retain existing subscription tiers if upstream returns null in partial responses.",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/models/quota.rs",
        "Models",
        361,
        14279,
        "Data structures for multi-bucket quotas, rolling windows, and model capabilities.",
        json.dumps([
            "QuotaBucket::weekly_cycle_bounds(now): Calculates weekly 7-day rolling window boundaries",
            "QuotaBucket::retain_cycle_boundary(previous, observed_at): Retains cycle start across refreshes",
            "QuotaData::ensure_subscription_tier(): Validates and normalizes subscription tier to ULTRA/PRO/FREE"
        ]),
        json.dumps([
            "QuotaBucket: bucket_id, window, remaining_fraction, reset_time, cycle_start, cycle_tokens",
            "QuotaGroup: display_name, buckets",
            "ModelQuota: name, percentage, reset_time, supports_images, supports_thinking, thinking_budget, max_tokens",
            "QuotaData: models, last_updated, subscription_tier, quota_groups, model_forwarding_rules"
        ]),
        "Weekly cycles are rolling and do not reset on fixed calendar boundaries; bucket cycle start must be preserved if remaining_fraction increases.",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/modules/db.rs",
        "Database & IDE Injection",
        282,
        8905,
        "Antigravity local SQLite database (state.vscdb) reader and injector.",
        json.dumps([
            "get_all_candidate_db_paths(target_ide): Resolves candidate paths for VS Code / Antigravity IDE across OSes",
            "inject_token(...): Injects token into state.vscdb with format branching",
            "inject_new_format(...): Encodes Protobuf OAuth info, patches antigravityUnifiedStateSync.oauthToken in ItemTable",
            "inject_user_status(conn, email): Writes minimal user status to antigravityUnifiedStateSync.userStatus",
            "inject_enterprise_project_preference(conn, project_id): Writes GCP project ID preference",
            "write_service_machine_id(db_path, machine_id): Writes telemetry.serviceMachineId to prevent VS Code fingerprint mismatches"
        ]),
        json.dumps([
            "Candidate paths list", "ItemTable key/value schema"
        ]),
        "Deletes jetskiStateSync.agentManagerInitState to prevent IDE from loading stale user session; sets antigravityOnboarding = 'true'.",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/modules/migration.rs",
        "Migration & Extraction",
        526,
        20970,
        "Extracts OAuth refresh tokens from local state.vscdb, system keyring, or legacy v1 ~/.antigravity-agent/ files.",
        json.dumps([
            "extract_oauth_state_from_file(db_path): Extracts refresh_token and is_gcp_tos from state.vscdb",
            "get_refresh_token_from_db(target_ide): Checks system keyring first, then falls back to candidate databases",
            "import_from_v1(): Scans ~/.antigravity-agent/ for legacy accounts.json index and imports"
        ]),
        json.dumps([
            "ImportedOAuthState: refresh_token, is_gcp_tos, project_id"
        ]),
        "Must handle both modern Protobuf format (antigravityUnifiedStateSync.oauthToken) and legacy format (jetskiStateSync.agentManagerInitState).",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/utils/protobuf.rs",
        "Protobuf Codec",
        415,
        14682,
        "Low-level pure binary Protobuf encoder and decoder.",
        json.dumps([
            "encode_varint / decode_varint: Standard 7-bit continuation varint handling",
            "find_field(data, field_num): Finds length-delimited byte slice for given field",
            "find_varint_field(data, field_num): Finds varint integer for given field",
            "decode_unified_state_entry(b64): Decodes sentinel key and payload blob from base64 envelope",
            "create_oauth_info(...): Serializes OAuthTokenInfo with fields 1 to 7",
            "create_unified_topic_entry / remove_unified_topic_entry: Manages topic lists"
        ]),
        json.dumps([
            "WireType enum: Varint(0), Fixed64(1), LengthDelimited(2), Fixed32(5)"
        ]),
        "Handles missing padding in Base64 strings safely without crashing; parses multiple concatenated Topic.data entries.",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/modules/quota.rs",
        "Quota Service",
        1022,
        41457,
        "Multi-endpoint Cloud Code quota query and model capability parser.",
        json.dumps([
            "fetch_available_models(token): Calls v1internal:fetchAvailableModels with fallback endpoints",
            "retrieve_user_quota_summary(token): Calls v1internal:retrieveUserQuotaSummary for 5h and weekly buckets",
            "load_code_assist(token): Calls v1internal:loadCodeAssist to retrieve tier (FREE/PRO/ULTRA) and project ID",
            "refresh_all_accounts_quota(): Background periodic updater with retry backoff"
        ]),
        json.dumps([
            "QuotaResponse", "ModelInfo", "QuotaInfo", "QuotaSummaryResponse", "QuotaSummaryBucket"
        ]),
        "Fallback order for endpoints: Sandbox -> Daily -> Prod. Handles near-recovery threshold (95%) with backoff.",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/modules/oauth_server.rs",
        "OAuth Server",
        350,
        21351,
        "Ephemeral local HTTP server for Google OAuth PKCE authorization callback.",
        json.dumps([
            "start_oauth_server(): Binds to 127.0.0.1:0, creates one-shot channel, opens browser",
            "handle_callback(): Reads ?code= parameter, serves styled HTML response with window.close() script",
            "exchange_code_for_token(code, verifier): Exchanges authorization code with Google token endpoint"
        ]),
        json.dumps([
            "OAuthCallbackParams: code, state, error"
        ]),
        "Uses port 0 to prevent port conflicts. Implements PKCE (code_verifier and SHA-256 code_challenge).",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/proxy/token_manager.rs",
        "Proxy Token Rotation",
        5782,
        237860,
        "Manages account pool, sticky sessions, rate limit parsing, intelligent model fallback, and account switching.",
        json.dumps([
            "classify_rate_limit_reason(body): Categorizes 429 errors into ModelCapacityExhausted, RateLimitExceeded, QuotaExhausted",
            "get_token(model, session_id): Selects optimal account based on quota, cooldown, sticky affinity, and priority",
            "report_rate_limit(account_id, model, reason, retry_after): Marks account/model with cooldown and rotates",
            "update_account_json(path, update_fn): Async blocking task to safely mutate account files under lock"
        ]),
        json.dumps([
            "TokenManager state: DashMap of accounts, cooldown trackers, sticky session maps",
            "RateLimitReason enum"
        ]),
        "Prevents runtime starvation in Tokio by delegating file I/O and synchronous locks to spawn_blocking.",
        "VERIFIED_FULL"
    ),
    (
        "src-tauri/src/proxy/server.rs",
        "Proxy Server",
        4583,
        157209,
        "Axum HTTP server providing OpenAI / Claude / Gemini API protocol translation and stream proxying.",
        json.dumps([
            "create_router(app_state): Registers /v1/chat/completions, /v1/models, /v1/messages",
            "handle_chat_completions(state, headers, body): Translates OpenAI schema to Cloud Code Gemini schema",
            "handle_claude_messages(state, headers, body): Translates Anthropic Claude schema to Gemini schema",
            "ImageScheduler::try_acquire(account_id): Concurrency throttler specifically for image generation models"
        ]),
        json.dumps([
            "AppState: token_manager, upstream client, monitor, image_scheduler, proxy_pool_manager"
        ]),
        "Translates system instructions, thinking blocks, multimodal images, and tool/function call payloads bidirectionally.",
        "VERIFIED_FULL"
    )
]

cursor.executemany("""
INSERT OR REPLACE INTO repo_modules 
(module_path, category, lines_of_code, size_bytes, purpose, critical_functions, data_structures, edge_cases_and_gotchas, analysis_status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", modules_data)

conn.commit()
conn.close()
print("Successfully populated reference_repo_analysis.db with all core module analyses.")
