<div align="center">

# ⚡ Antigravity Universal Connector
### Enterprise-Grade AI Model Gateway, Telemetry Engine & Multi-Account Orchestrator for Google Antigravity

[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue?style=for-the-badge&logo=windows&logoColor=white)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt_6.6+-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://qt.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async_Engine-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5_Indexed-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Zero ASAR Hack](https://img.shields.io/badge/Architecture-100%25_Non--Invasive-success?style=for-the-badge)](https://github.com)

<p align="center">
  <b>A unified, robust desktop architecture bridging Google Antigravity with external AI providers, real-time quota telemetry, automated OAuth lifecycle orchestration, and sub-millisecond full-text interaction search.</b>
</p>

[Architectural Overview](#-architectural-overview) •
[Enterprise Standards](#-enterprise-standards) •
[Core Capabilities](#-core-capabilities) •
[Phased Roadmap](#-phased-execution-roadmap) •
[Directory Topology](#-directory-topology) •
[Installation & Prerequisites](#-installation--prerequisites) •
[Protocol Specification](#-protocol--wire-specification) •
[Verification & Quality Assurance](#-verification--quality-assurance)

</div>

---

## 🏛️ Architectural Overview

**Antigravity Universal Connector** solves the structural limitations of model routing and multi-tenancy in Google Antigravity without invasive binary modifications, runtime DOM tampering, or ASAR package repacking. 

Prior community approaches attempted to modify Antigravity's internal Electron `preload.ts` or inject React components directly into internal settings views. Under modern Chromium Content Security Policies (CSP) and framework reconciliation cycles, such modifications result in catastrophic initialization failures (**the "blank white screen" failure mode**).

Antigravity Universal Connector implements a **strict separation of concerns**:
- **Application Boundary Isolation**: The Antigravity IDE runs unmodified. Network calls are cleanly routed at the Language Server transport level to a high-speed local proxy gateway (`127.0.0.1:50999`).
- **Zero-Tampering Ingress/Egress**: Standard Google Gemini requests pass through upstream to `daily-cloudcode-pa.googleapis.com` with zero byte mutations and negligible sub-millisecond latency overhead.
- **Dynamic Protocol Transcoding**: The custom model slot (`⚡ Universal Connector`) dynamically translates Cloud Code internal protocol payloads (`v1internal:streamGenerateContent`) into standard OpenAI/Ollama schemas, executing streaming SSE transformations and extracting reasoning/thinking tokens (`<think>` / `reasoning_content`) on the fly.
- **Independent Native Execution**: A standalone desktop subsystem (PySide6 + SQLite FTS5) provides dedicated UI frames, persistent encrypted configuration, real-time balance tracking, and system tray management.

```
+=============================================================================================================+
|                                              ANTIGRAVITY IDE                                                |
|                                                                                                             |
|   Selected Model Route:                                                                                     |
|   ├── [ Gemini 2.5 Pro ] -------- (Pass-through untouched) -------> Google Cloud Code Upstream             |
|   ├── [ Gemini 2.5 Flash ] ------ (Pass-through untouched) -------> (daily-cloudcode-pa.googleapis.com)     |
|   └── [ ⚡ Universal Connector ] - (Diverted via transport) ------+                                         |
+===================================================================|=========================================+
                                                                    |
                                        Loopback Transport (:50999) |
                                                                    v
+=============================================================================================================+
|                                  ANTIGRAVITY UNIVERSAL CONNECTOR (ONE APP)                                  |
|                                                                                                             |
|  +----------------------------------------------------+  +-----------------------------------------------+  |
|  |           MODULE 1: ACCOUNTS & QUOTA CORE          |  |       MODULE 2: UNIVERSAL MODEL SWITCHER      |  |
|  |             (Webview / Cleaned Core)               |  |           (PySide6 Native Desktop Shell)      |  |
|  +----------------------------------------------------+  +-----------------------------------------------+  |
|  | • Multi-Account Matrix Management                  |  | • Top Menubar (Pure Python Dynamic Engine)    |  |
|  | • Loopback OAuth Redirect Engine (:8888)           |  | • Windows/macOS/Linux Native System Tray      |  |
|  | • Daily Quota Telemetry (Gemini Flash & Pro)       |  | • Declarative Layouts (.ui XML via UIC)       |  |
|  | • Atomic SQLite state.vscdb Token Injection        |  | • 3-Field Unified Model Entry Contract        |  |
|  | • [Stripped: 0% 3rd-Party Relays / Clutter]        |  | • Live Balance & Telemetry (OpenRouter, etc.) |  |
|  +----------------------------------------------------+  +-----------------------------------------------+  |
|                                                                                          |                  |
|  +---------------------------------------------------------------------------------------+---------------+  |
|  |                                  HIGH-PERFORMANCE DATA & TRANSCODING ENGINE                           |  |
|  | • Protocol Transcoder: Cloud Code v1internal <===========> OpenAI / Anthropic / Ollama Wire Format    |  |
|  | • SSE Stream Processor: Real-time chunk framing, tool call aggregation, and <think> token demuxing    |  |
|  | • SQLite FTS5 Engine: Sub-millisecond BM25 full-text indexing across prompts, tool calls, and tokens  |  |
|  +---------------------------------------------------------------------------------------+---------------+  |
+==========================================================================================|==================+
                                                                                           |
                                              Dynamic Routing via Active Provider Profile  |
                                                                                           |
                  +--------------------------+-----------------------+---------------------+
                  |                          |                       |                     |
                  v                          v                       v                     v
          [  OPENROUTER API  ]       [  OLLAMA (LOCAL)  ]    [  DEEPSEEK DIRECT  ]  [   NVIDIA NIM   ]
          (100+ Cloud Models)       (http://127.0.0.1:11434) (api.deepseek.com)    (integrate.api.nvidia)
```

---

## 💎 Enterprise Standards

Antigravity Universal Connector is engineered to meet strict corporate and enterprise development criteria:

| Standard | Implementation Architecture |
| :--- | :--- |
| **Zero Code Injection** | No runtime hooking of Electron processes; no ASAR archive modification; zero risk of rendering webview corruption or CSP violation crashes. |
| **Strict Data Privacy** | All prompt histories, interaction logs, and OAuth tokens reside strictly in a local SQLite database on the client workstation. Zero telemetry phone-home. |
| **Sub-Millisecond Search** | Embedded SQLite with Full-Text Search 5 (`FTS5`) using BM25 ranking algorithm for real-time prompt, tool call, and error diagnostic auditing. |
| **Thread-Safe Concurrency** | Dedicated background execution threads for the FastAPI proxy gateway and OAuth redirect server, fully decoupled from the Qt GUI main thread. |
| **Resilient Token Storage** | AES-256-GCM encrypted persistence for provider API keys, utilizing OS platform standards (`%APPDATA%`, `~/Library/Application Support`, `~/.config`). |
| **Deterministic Fallback** | Instantaneous 1-click restore mechanism for Antigravity's transport layer with verified pristine `.bak` file validation. |

---

## 🌟 Core Capabilities

### 1. Unified 3-Field Provider Contract
Every external LLM provider connects through a standardized, consistent contract:
- **Base URL**: Upstream endpoint (e.g., `https://openrouter.ai/api/v1`, `http://127.0.0.1:11434/v1`, `https://api.deepseek.com/v1`, `https://integrate.api.nvidia.com/v1`).
- **API Key**: Securely obfuscated credential storage with interactive verification.
- **Model Selector**: An editable, searchable `QComboBox` coupled with a `[Fetch Models]` action that queries upstream `/v1/models` catalog endpoints asynchronously, while permitting manual typed model slugs.

### 2. Live Balance & Financial Telemetry
Real-time visibility into usage and account reserves:
- **OpenRouter**: Native credit balance querying (`/api/v1/auth/key`), usage tracking, and rate limit visibility.
- **DeepSeek**: Direct balance verification (`/user/balance`) across granted and topped-up currency allocations.
- **Ollama**: Real-time VRAM allocation and active model footprint auditing.
- **Per-Turn Cost Ledger**: Automatic token computation (prompt + completion) and cost estimation per conversation turn.

### 3. Google OAuth & Quota Orchestration
- **Loopback OAuth Server**: Captures browser authorization codes securely on `127.0.0.1:8888`.
- **Atomic State Synchronization**: Injects refreshed session tokens directly into Antigravity's SQLite storage (`state.vscdb`) under `antigravityUnifiedStateSync.oauthToken`.
- **Telemetry Visuals**: Daily quota monitors for official Gemini 2.5 Flash and Pro allotments.
- **Cleaned Topology**: Completely stripped of third-party API relaying, advertisement links, or secondary proxy layers.

### 4. High-Performance SQLite FTS5 Search
- Real-time indexing of all conversation turns, system instructions, tool definitions, tool responses, token consumption, and network latencies.
- Instant search across thousands of past programming interactions with millisecond query response times.

---

## 🗺️ Phased Execution Roadmap

To ensure zero downtime, deterministic verification, and maintainability, delivery is partitioned into two distinct phases:

```
+=============================================================================================+
|                       PHASE 1: STRIPPED-DOWN ANTIGRAVITY-MANAGER CORE                       |
|                                                                                             |
|  [x] Complete isolation of Google Account Matrix & Token Management                         |
|  [x] Standardized Browser OAuth Loopback Flow (Port 8888)                                   |
|  [x] Official Gemini 2.5 Flash & Pro Daily Quota Telemetry Tracking                         |
|  [x] Cleanse: Complete elimination of 3rd-party API relay code and sponsor clutter          |
|  [x] Atomic synchronization to Antigravity state.vscdb                                      |
+=============================================================================================+
                                               │
                                               ▼ (Verified & Validated)
+=============================================================================================+
|                       PHASE 2: DEDICATED PYSIDE6 MODEL SWITCHER & FTS5                      |
|                                                                                             |
|  [ ] Dedicated PySide6 Desktop Shell with Declarative Qt .ui Layouts                        |
|  [ ] Pure Python Dynamic Menubar & System Tray Context Menu Controller (menus.py)           |
|  [ ] 3-Field Unified Model Entry with Async [Fetch Models] Catalog Querying                 |
|  [ ] Live Financial Telemetry & Account Balance Watchers (OpenRouter, DeepSeek, Ollama)     |
|  [ ] Embedded SQLite FTS5 Full-Text Search Engine with BM25 Ranking                         |
|  [ ] Local Cloud Code Protocol Proxy on 127.0.0.1:50999                                     |
|  [ ] Safe 1-Click Antigravity Transport Integrator with Automated Backup Verification       |
+=============================================================================================+
```

---

## 📂 Directory Topology

```
Antigravity_Universal_Connector/
│
├── .git/                                   # Source control tracking
├── AGENTS.md                               # Project operational directives & quality rules
├── LICENSE                                 # Legal licensing agreement
├── README.md                               # Platinum-grade enterprise documentation
├── requirements.txt                        # Pinned dependencies
│
├── assets/                                 # Binary UI and branding assets
│   ├── icon.ico                            # High-resolution Windows application & tray icon
│   └── icon.png                            # Cross-platform application branding
│
├── scripts/                                # Build, compilation, and automation toolchain
│   ├── compile_ui.py                       # Automated pyside6-uic build tool
│   ├── build_windows.ps1                   # Production PyInstaller Windows packaging
│   ├── build_macos.sh                      # Production macOS bundle packaging
│   └── build_linux.sh                      # Production Linux executable packaging
│
├── src/                                    # Application source tree
│   ├── __init__.py
│   ├── main.py                             # Master entrypoint & process orchestrator
│   │
│   ├── core/                               # Core processing & data engine
│   │   ├── __init__.py
│   │   ├── config.py                       # Cross-platform persistent configuration (platformdirs)
│   │   ├── database.py                     # SQLite FTS5 search & account data store
│   │   ├── proxy_server.py                 # FastAPI proxy engine listening on 127.0.0.1:50999
│   │   ├── translator.py                   # Bidirectional Cloud Code v1internal <-> OpenAI transcoder
│   │   ├── streaming.py                    # SSE stream parser with reasoning/thinking demuxer
│   │   ├── auth_server.py                  # Loopback OAuth callback listener on 127.0.0.1:8888
│   │   ├── account_manager.py              # Antigravity state.vscdb database injector
│   │   ├── balance_checker.py              # Upstream financial balance & credit monitor
│   │   └── model_fetcher.py                # Async /v1/models catalog discovery utility
│   │
│   ├── gui/                                # Dedicated PySide6 desktop interface
│   │   ├── __init__.py
│   │   ├── model_switcher_window.py        # Controller for dedicated Model Switcher window
│   │   ├── provider_dialog.py              # Controller for provider config popup dialog
│   │   ├── test_dialog.py                  # Controller for latency & connection test popup
│   │   ├── tray.py                         # Native OS System Tray controller
│   │   ├── menus.py                        # Pure Python dynamic menubar & context menu builder
│   │   │
│   │   ├── ui/                             # Declarative Qt Designer .ui XML definitions
│   │   │   ├── model_switcher.ui           # Main model switcher interface layout
│   │   │   ├── provider_dialog.ui          # 3-field model entry configuration popup
│   │   │   ├── test_dialog.ui              # Latency & diagnostics test popup
│   │   │   ├── model_card.ui               # Model telemetry & status card widget
│   │   │   └── search_view.ui              # SQLite FTS5 search view & results table
│   │   │
│   │   ├── generated/                      # Compiled Python UI classes (pyside6-uic output)
│   │   │   ├── __init__.py
│   │   │   ├── ui_model_switcher.py
│   │   │   ├── ui_provider_dialog.py
│   │   │   ├── ui_test_dialog.py
│   │   │   ├── ui_model_card.py
│   │   │   └── ui_search_view.py
│   │   │
│   │   └── styles/                         # High-contrast developer styling
│   │       ├── __init__.py
│   │       └── dark_theme.qss              # Custom Qt stylesheet for native frames
│   │
│   ├── accounts_view/                      # Cleaned Google Accounts & Quotas subsystem
│   │   ├── index.html                      # Minimalist, high-performance accounts view
│   │   ├── css/
│   │   │   └── style.css                   # Responsive layout styling
│   │   └── js/
│   │       ├── accounts.js                 # Multi-account state & OAuth activation
│   │       └── quotas.js                   # Gemini 2.5 Flash & Pro quota polling
│   │
│   └── patcher/                            # Transport layer configuration
│       ├── __init__.py
│       ├── detector.py                     # Antigravity installation locator
│       └── integrator.py                   # Safe proxy routing manager & backup guardian
│
└── tests/                                  # Enterprise verification suite
    ├── __init__.py
    ├── test_database_fts5.py               # SQLite FTS5 indexing & BM25 retrieval tests
    ├── test_translator.py                  # Protocol mapping and tool call translation tests
    ├── test_proxy_endpoints.py             # Proxy router and passthrough latency tests
    └── test_balance_fetcher.py             # Telemetry parsing & credit query validation
```

---

## ⚡ Installation & Prerequisites

### System Requirements
- **Operating System**: Windows 10/11 (x64), macOS 12+ (Intel/Apple Silicon), or Linux (x86_64).
- **Runtime Environment**: Python 3.10, 3.11, or 3.12.
- **Antigravity**: Standalone desktop installation.

### Step 1: Clone Repository
```bash
git clone https://github.com/Arean82/Antigravity_Universal_Connector.git
cd Antigravity_Universal_Connector
```

### Step 2: Configure Environment & Dependencies
```bash
# Initialize isolated virtual environment
python -m venv venv

# Activate environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate environment (macOS/Linux)
source venv/bin/activate

# Install enterprise dependencies
pip install -r requirements.txt
```

### Step 3: Compile Declarative Layouts
```bash
python scripts/compile_ui.py
```

### Step 4: Run Application
```bash
python src/main.py
```

---

## 📡 Protocol & Wire Specification

Antigravity communicates internally via Google's Cloud Code internal API envelope (`/v1internal:*`). The proxy server transparently intercepts and decodes these contracts:

### 1. Inbound Model Enumeration
```http
POST /v1internal:fetchAvailableModels HTTP/1.1
Host: 127.0.0.1:50999
Content-Type: application/json
```
The gateway queries upstream Google models, appends the virtual model entry (`⚡ Universal Connector`), and injects it into `agentModelSorts` so it populates Antigravity's model dropdown seamlessly.

### 2. Stream Generation & Transcoding
```http
POST /v1internal:streamGenerateContent?alt=sse HTTP/1.1
Host: 127.0.0.1:50999
Content-Type: application/json
```
- **Gemini Model Selected**: Gateway initiates direct, streaming reverse-proxy to `https://daily-cloudcode-pa.googleapis.com` with zero schema modification.
- **Universal Connector Selected**: Gateway extracts `systemInstruction`, multi-turn `contents`, and `tools`, maps them to standard OpenAI Chat Completions JSON, forwards the request to the active provider, and yields Server-Sent Events (SSE) wrapped in Cloud Code envelopes:
```json
{
  "response": {
    "candidates": [
      {
        "content": {
          "role": "model",
          "parts": [{ "text": "..." }]
        },
        "finishReason": null,
        "index": 0
      }
    ]
  },
  "traceId": "trace-uuid",
  "metadata": {}
}
```

---

## 🧪 Verification & Quality Assurance

Every build and commit must pass automated verification suites adhering to the **Zero Unresolved Issues** standard:

```bash
# Execute full test suite
python -m unittest discover -s tests -p "test_*.py"

# Execute SQLite FTS5 performance benchmarks
python -m unittest tests/test_database_fts5.py

# Verify Protocol Transcoding Fidelity
python -m unittest tests/test_translator.py
```

---

## 📄 License & Distribution

Distributed under the terms of the project [LICENSE](LICENSE). All code adheres to strict enterprise delivery specifications with zero telemetry leakage and client-side isolation.
