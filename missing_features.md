# PySide6 Missing Features vs Original React Audit & Implementation Tracker

## Dashboard (100% Implemented)

| Page | Feature | Status | Implementation Details |
|------|---------|--------|------------------------|
| Dashboard | Total Accounts stat card | ✅ Added | Implemented via `valTotalAccounts` QLCDNumber |
| Dashboard | Disabled Accounts stat card | ✅ Added | Implemented via `valDisabledAccounts` QLCDNumber |
| Dashboard | Abnormal/Risk Accounts stat card (red when >0) | ✅ Added | Implemented via `valAbnormalAccounts` QLCDNumber + `lblCardRiskBadge` dynamic red alert |
| Dashboard | 4-condition account health classifier | ✅ Added | Implemented via `_classify_account` (disabled, abnormal/is_forbidden, active) |
| Dashboard | Quota Matrix section title (dynamic) | ✅ Added | Implemented via `lblQuotaMatrixTitle` toggling between Available vs All Normal |
| Dashboard | Pool count label | ✅ Added | Implemented via `lblPoolCountBadge` displaying `(Pool: {count})` |
| Dashboard | "Available Accounts Only" pill toggle button | ✅ Added | Implemented via `btnOnlyAvailable` capsule button with live count |
| Dashboard | "Include Disabled" pill toggle button | ✅ Added | Implemented via `btnIncludeDisabled` capsule button with live count |
| Dashboard | Gemini Text quota card (weightedEffective %, avg5h, avgWeekly, zero-fuse warning) | ✅ Added | Implemented via `cardGeminiText` (`valGTWeighted`, `lblGTBadge`, `lblGT5h`, `lblGTWeekly`, `lblGTWarning`) |
| Dashboard | Gemini Image quota card (weightedEffective %, avg5h, avgWeekly, zero-fuse warning) | ✅ Added | Implemented via `cardGeminiImage` (`valGIWeighted`, `lblGIBadge`, `lblGI5h`, `lblGIWeekly`, `lblGIWarning`) |
| Dashboard | Claude quota card (weightedEffective %, avg5h, avgWeekly, zero-fuse warning) | ✅ Added | Implemented via `cardClaude` (`valClaudeWeighted`, `lblClaudeBadge`, `lblClaude5h`, `lblClaudeWeekly`, `lblClaudeWarning`) |
| Dashboard | Weighted quota calculation (ULTRA×2.0, PRO×1.5, FREE×1.0) | ✅ Added | Implemented in `_compute_metrics` via `TIER_WEIGHTS` |
| Dashboard | 5H rolling average computation | ✅ Added | Implemented in `_compute_metrics` with `sum5h / count5h` |
| Dashboard | 7-day weekly average computation | ✅ Added | Implemented in `_compute_metrics` with `sumWeekly / countWeekly` |
| Dashboard | Zero-weekly-count fuse detection per model | ✅ Added | Implemented in `_compute_metrics` setting effective=0 on zero-weekly and alerting in red banner |
| Dashboard | CurrentAccount detail panel | ✅ Added | Implemented via `groupCurrentAccount` (email, tier, flash/pro quota, health status) |
| Dashboard | BestAccounts ranked panel with per-row Switch button | ✅ Added | Implemented via `tableBestAccounts` with per-row Switch QPushButton |
| Dashboard | Refresh Quota button (calls remote API for current account) | ✅ Added | Implemented via `btnRefreshQuota` wired to `bridge.refresh_account_quota` |
| Dashboard | "View All Accounts" navigation button | ✅ Added | Implemented via `btnViewAllAccounts` navigating directly to Account Settings |
| Dashboard | "Export Data" JSON export button | ✅ Added | Implemented via `btnExportData` & `btnExportDataBottom` with QFileDialog JSON save |
| Dashboard | Personalized greeting "Hello, {name}" | ✅ Added | Implemented via `lblGreeting` dynamically showing active account name |

---

## Token Stats (100% Implemented)

| Page | Feature | Status | Implementation Details |
|------|---------|--------|------------------------|
| Token Stats | Models Used stat card (6th card) | ✅ Added | Implemented via `valModelsUsed` QLCDNumber |
| Token Stats | Model/Account Trend stacked area / bar chart | ✅ Added | Implemented via `QChartView` + `QBarSeries` (Cached, Uncached Input, Output) |
| Token Stats | "By Model" / "By Account" view-mode toggle buttons | ✅ Added | Implemented via `btnViewByModel` and `btnViewByAccount` checkable buttons |
| Token Stats | Token Usage Trend stacked bar chart (cached / uncached input / output) | ✅ Added | Implemented with QBarSets: Cached (`#93C5FD`), Uncached (`#3B82F6`), Output (`#8B5CF6`) |
| Token Stats | Account Distribution donut pie chart | ✅ Added | Implemented via `QPieSeries` with hole size 0.4 and color theme |
| Token Stats | Pie chart legend list (top 5 accounts with color dots) | ✅ Added | Implemented via `_rebuild_pie_legend` dynamic colored dot badges |
| Token Stats | Inline progress bar in Model table Share % column | ✅ Added | Implemented via `QProgressBar` styled chunk matching model color |
| Token Stats | Color dot indicator next to model name in Model table | ✅ Added | Implemented via `MODEL_COLORS` palette dots next to model name |
| Token Stats | viewMode toggle (model table vs account table conditional visibility) | ✅ Added | Implemented via `_set_view_mode` showing/hiding `groupModelStats` and `groupAccountStats` |
| Token Stats | Share % column in Account table | ✅ Added | Implemented in column 6 with inline `QProgressBar` |
| Token Stats | Real token stats aggregation from backend accounts | ✅ Added | Implemented via DB account loop reading `quota_json` |
| Token Stats | uncached_input_tokens derived field | ✅ Added | Implemented via `_uncached(input_t, cached_t)` and dedicated table column |
| Token Stats | Dynamic model list from backend | ✅ Added | Dynamically extracted from account quota models instead of hardcoded 3 |
| Token Stats | Loading state (disabled button, loading text) | ✅ Added | `btnRefreshStats` disabled with "Loading…" text while refreshing |
| Token Stats | formatNumber K/M abbreviation | ✅ Added | Implemented via `_fmt()` formatting numbers as `K`, `M`, or locale formatted |

---

## API Proxy — Audit Pending
## Traffic Logs / Monitor — Audit Pending
## Security / IP Management — Audit Pending
## Settings (General / Account / Advanced) — Audit Pending
## User Tokens — Audit Pending
