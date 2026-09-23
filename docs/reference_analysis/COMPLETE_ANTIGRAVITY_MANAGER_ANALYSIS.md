# Complete Architectural & Implementation Analysis: Antigravity-Manager

This document provides a verified, comprehensive, file-by-file breakdown of `E:\GitHub\Antigravity-Manager`. All data structures, binary encoding schemes, APIs, and edge cases have been extracted and recorded in SQLite (`reference_repo_analysis.db`).

---

## 1. Account Persistence & Storage Architecture

### File: `src-tauri/src/modules/account.rs` & `src-tauri/src/models/account.rs`
- **Data Directory Hierarchy**:
  - Root: Determined by precedence:
    1. Environment variable `ABV_DATA_DIR`
    2. Pointer file (`~/.antigravity_tools_location` or `ABV_DATA_DIR_POINTER_FILE`)
    3. Default directory `~/.antigravity_tools/`
  - Subdirectories:
    - `accounts/`: Stores per-account JSON files (`<account_id>.json`).
    - `accounts.json`: Index file containing array of `AccountSummary`, `current_account_id`, and `current_target_ide`.
- **Concurrency & Atomic Locking**:
  - `ACCOUNT_FILE_LOCKS`: An in-memory `Lazy<Mutex<HashMap<String, Arc<Mutex<()>>>>>` providing granular per-account file locks.
  - Disk operations in Tokio are delegated via `tokio::task::spawn_blocking` to prevent runtime starvation.
- **Resilience & Self-Healing Logic**:
  - **BOM & NUL Stripping**: Automatically detects and strips UTF-8 BOM (`0xEF, 0xBB, 0xBF`) and NUL byte prefixes (`0x00`) from corrupted index files.
  - **Trailing Syntax Self-Healing (Issue #3345)**: If a JSON file has stray characters or closing braces appended to the end, it extracts the largest valid JSON substring, validates it, and rewrites the file clean.
  - **Atomic File Writing**: Creates a `.tmp` file and performs an atomic rename/replace with sync to disk.
- **Live Limit Tracking (`LiveLimitStatus`)**:
  - When upstream returns HTTP 429 (`QUOTA_EXHAUSTED` or `RATE_LIMIT_EXCEEDED`), the error payload is parsed for `quotaResetDelay` (e.g. `2h` or `7200s`).
  - Active 429 locks are cached in `account.live_limited_models` and **are preserved** across background quota refreshes to avoid sending traffic to locked models.

---

## 2. Antigravity IDE Local SQLite Database Injection

### File: `src-tauri/src/modules/db.rs`
- **Target Database**: `%APPDATA%\Antigravity\User\globalStorage\state.vscdb` (Windows) or `~/Library/Application Support/Antigravity/User/globalStorage/state.vscdb` (macOS).
- **Table Schema**: SQLite table `ItemTable (key TEXT PRIMARY KEY, value TEXT)`.
- **Target Keys & Binary Envelopes**:
  1. `antigravityUnifiedStateSync.oauthToken`:
     - Base64-encoded Protobuf envelope.
     - Contains entries identified by Sentinel Keys.
     - Sentinel Key: `oauthTokenInfoSentinelKey`.
     - Payload: Protobuf serialized `OAuthTokenInfo` containing:
       - Field 1: Access Token (String)
       - Field 2: Token Type (`Bearer`)
       - Field 3: Refresh Token (String)
       - Field 4: Expiration Timestamp (Varint)
       - Field 5: ID Token (String)
       - Field 6: `is_gcp_tos` acceptance flag (Varint 0 or 1)
       - Field 7: User Email (String)
  2. `antigravityUnifiedStateSync.userStatus`:
     - Sentinel Key: `userStatusSentinelKey` with minimal user status payload.
  3. `antigravityUnifiedStateSync.enterprisePreferences`:
     - Sentinel Key: `enterpriseGcpProjectId` holding the selected Google Cloud Project ID.
  4. `antigravityOnboarding`:
     - Set to `"true"` to suppress the IDE welcome/login wizard.
  5. `jetskiStateSync.agentManagerInitState`:
     - **Explicitly deleted** to prevent the IDE from reading stale legacy cached user IDs.
  6. `telemetry.serviceMachineId`:
     - Written to prevent VS Code workspace fingerprint invalidations.

---

## 3. Session Extraction & 1-Click Migration

### File: `src-tauri/src/modules/migration.rs`
- **Modern Extraction (`extract_oauth_state_from_file`)**:
  1. Opens `state.vscdb`.
  2. Reads `antigravityUnifiedStateSync.oauthToken`.
  3. Decodes Base64 to binary bytes.
  4. Parses Protobuf wire format looking for Sentinel Key `oauthTokenInfoSentinelKey`.
  5. Unpacks the inner payload and extracts Field 3 (Google Refresh Token `1//...`).
  6. Checks Field 6 for GCP TOS status.
  7. Reads `enterprisePreferences` to detect any bound GCP project.
- **Legacy Fallback**:
  - Reads `jetskiStateSync.agentManagerInitState`, decodes Base64, and extracts Field 6 (OAuth blob) -> Field 3.

---

## 4. Binary Protobuf Codec Engine

### File: `src-tauri/src/utils/protobuf.rs`
- **Pure Handcrafted Codec**: Operates without generated `.proto` stubs.
- **Wire Types Supported**:
  - `0`: Varint (7-bit continuation encoding with `0x80` MSB).
  - `1`: 64-bit fixed (little-endian).
  - `2`: Length-delimited (strings, bytes, embedded messages).
  - `5`: 32-bit fixed (little-endian).
- **Robustness Features**:
  - Safe Base64 decoding: Automatically calculates missing `=` padding before decoding.
  - Multi-topic unwrapping: Traverses nested length-delimited envelopes without memory allocations.

---

## 5. Quota Inspection & Model Capabilities

### File: `src-tauri/src/modules/quota.rs` & `src-tauri/src/models/quota.rs`
- **Endpoint Hierarchy (Fallback: Sandbox -> Daily -> Prod)**:
  - `https://daily-cloudcode-pa.sandbox.googleapis.com/v1internal`
  - `https://daily-cloudcode-pa.googleapis.com/v1internal`
  - `https://cloudcode-pa.googleapis.com/v1internal`
- **Three-Tier Endpoint Architecture**:
  1. **`loadCodeAssist`**:
     - Retreives subscription tier (`FREE`, `PRO`, or `ULTRA`) and default project ID (`cloudaicompanionProject`).
  2. **`fetchAvailableModels`**:
     - Returns available model identifiers (`gemini-2.5-pro`, `gemini-2.5-flash`, `claude-3-7-sonnet`, etc.).
     - Supplies model capabilities (`supportsImages`, `supportsThinking`, `thinkingBudget`, `maxTokens`, `supportedMimeTypes`).
     - Contains `remainingFraction` (0.0 to 1.0) and ISO 8601 `resetTime`.
  3. **`retrieveUserQuotaSummary`**:
     - Provides grouped quota buckets (`gemini-weekly`, `gemini-5h`, `3p-weekly`, `3p-5h`).
     - Models 7-day rolling cycles (`cycle_start` to `reset_time`).
     - Retains earlier cycle boundaries across refreshes to guarantee accurate historical usage reporting.

---

## 6. Proxy Server & Intelligent Token Rotation

### File: `src-tauri/src/proxy/server.rs` & `src-tauri/src/proxy/token_manager.rs`
- **Axum High-Performance Proxy**:
  - Serves `/v1/chat/completions`, `/v1/models`, and `/v1/messages`.
  - Translates OpenAI / Claude JSON formats into Google Cloud Code internal Gemini payloads.
- **Token Management & Load Balancing**:
  - `TokenManager`: In-memory thread-safe cache (`DashMap`) holding all authenticated accounts.
  - **Rate Limit Parsing**: Classifies 429 error bodies into:
    - `ModelCapacityExhausted`: Temporary upstream server load (short cooldown).
    - `RateLimitExceeded`: Requests-per-minute (RPM) exceeded (medium cooldown).
    - `QuotaExhausted`: Daily/weekly bucket depleted (cooldown until `resetTime`).
  - **Account Rotation**: When a request fails with 429 on Account A, the proxy instantly flags Account A for that model, acquires a healthy Account B from the pool, and completes the request with zero client-visible interruption.
  - **Image Scheduler**: Specialized concurrency semaphore (`ImageScheduler`) dedicated to image generation requests to avoid hitting Google's strict concurrent image limits.
