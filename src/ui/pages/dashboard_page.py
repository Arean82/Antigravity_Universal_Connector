"""Native PySide6 Dashboard Page Controller.
Directly loads dashboard.ui dynamically via QUiLoader (Zero UIC compilation).
100% feature-complete production port of Dashboard.tsx:
  - Personalized greeting "Hello, {name}"
  - 4-condition account health classification (active, disabled, abnormal/risk)
  - 7 QLCDNumber stat cards (Total, Active, Disabled, Abnormal, Port, Tokens, Requests)
  - Quota Matrix with dynamic title and pool count badge
  - Double pill capsule controller (Available Accounts Only vs Include Disabled)
  - 3 standalone model quota cards (Gemini Text, Gemini Image, Claude):
      * Weighted effective percentage (ULTRA 2.0, PRO 1.5, FREE 1.0)
      * 5H rolling average
      * 7-day weekly quota average
      * Weekly 0% fuse detection and warning alerts
      * Sufficient / Tight dynamic badges
  - Current Active Account detail panel
  - Best Accounts ranked panel with per-row Switch buttons
  - Quick-connect endpoints (OpenAI / Claude) with 1-click clipboard copy
  - 1-Click Import from Antigravity & Browser OAuth Add Account
  - Quick Links: "View All Accounts & Settings" and "Export Accounts Data (JSON)"
  - Full Google Account Pool management table
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QFile, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QDesktopServices
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLCDNumber,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.database import db
from src.core.vscdb_importer import VscdbImporter
from src.core.account_manager import AccountManager

# Subscription tier weights matching Dashboard.tsx
TIER_WEIGHTS: Dict[str, float] = {"ULTRA": 2.0, "PRO": 1.5, "FREE": 1.0}


def _classify_account(acc: Dict[str, Any]) -> str:
    """4-condition account health classifier matching Dashboard.tsx.
    - abnormal  → quota.is_forbidden or validation_blocked
    - disabled  → is_active == 0
    - active    → active, enabled, healthy
    """
    quota: Dict[str, Any] = acc.get("quota") or {}
    if quota.get("is_forbidden") or acc.get("validation_blocked"):
        return "abnormal"
    if not acc.get("is_active"):
        return "disabled"
    return "active"


class DashboardPage(QWidget):
    """Landing Dashboard page — full 1:1 port of Dashboard.tsx."""

    def __init__(self, bridge=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.bridge = bridge
        self.only_available: bool = True

        ui_file_path = os.path.join(
            os.path.dirname(__file__), "..", "forms", "dashboard.ui"
        )
        ui_file = QFile(ui_file_path)
        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Failed to open UI form: {ui_file_path}")

        loader = QUiLoader()
        self.form_widget = loader.load(ui_file, self)
        ui_file.close()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.form_widget)

        self._bind_widgets()
        self._setup_table_headers()
        self._connect_signals()
        self.load_from_config()

        if self.bridge:
            self.bridge.proxyStatusChanged.connect(self._on_proxy_status_changed)
            self.bridge.accountSwitched.connect(lambda acc_id: self.load_from_config())

    # ------------------------------------------------------------------
    # Widget binding
    # ------------------------------------------------------------------

    def _bind_widgets(self):
        fw = self.form_widget

        # Header
        self.lbl_greeting: QLabel = fw.findChild(QLabel, "lblGreeting")
        self.lbl_proxy_badge: QLabel = fw.findChild(QLabel, "lblProxyBadge")
        self.btn_toggle_proxy: QPushButton = fw.findChild(QPushButton, "btnToggleProxy")
        self.btn_refresh_quota: QPushButton = fw.findChild(QPushButton, "btnRefreshQuota")
        self.btn_export_data: QPushButton = fw.findChild(QPushButton, "btnExportData")

        # Stat cards — QLCDNumber
        self.val_total_accounts: QLCDNumber = fw.findChild(QLCDNumber, "valTotalAccounts")
        self.val_active_accounts: QLCDNumber = fw.findChild(QLCDNumber, "valActiveAccounts")
        self.val_disabled_accounts: QLCDNumber = fw.findChild(QLCDNumber, "valDisabledAccounts")
        self.val_abnormal_accounts: QLCDNumber = fw.findChild(QLCDNumber, "valAbnormalAccounts")
        self.val_proxy_port: QLCDNumber = fw.findChild(QLCDNumber, "valProxyPort")
        self.val_total_tokens: QLCDNumber = fw.findChild(QLCDNumber, "valTotalTokens")
        self.val_total_requests: QLCDNumber = fw.findChild(QLCDNumber, "valTotalRequests")
        self.lbl_risk_badge: QLabel = fw.findChild(QLabel, "lblCardRiskBadge")

        # Quota Matrix & Pill Capsule Controls
        self.lbl_quota_matrix_title: QLabel = fw.findChild(QLabel, "lblQuotaMatrixTitle")
        self.lbl_pool_count_badge: QLabel = fw.findChild(QLabel, "lblPoolCountBadge")
        self.btn_only_available: QPushButton = fw.findChild(QPushButton, "btnOnlyAvailable")
        self.btn_include_disabled: QPushButton = fw.findChild(QPushButton, "btnIncludeDisabled")

        # 3 Model Quota Cards
        # Gemini Text
        self.val_gt_weighted: QLabel = fw.findChild(QLabel, "valGTWeighted")
        self.lbl_gt_badge: QLabel = fw.findChild(QLabel, "lblGTBadge")
        self.lbl_gt_5h: QLabel = fw.findChild(QLabel, "lblGT5h")
        self.lbl_gt_weekly: QLabel = fw.findChild(QLabel, "lblGTWeekly")
        self.lbl_gt_warning: QLabel = fw.findChild(QLabel, "lblGTWarning")

        # Gemini Image
        self.val_gi_weighted: QLabel = fw.findChild(QLabel, "valGIWeighted")
        self.lbl_gi_badge: QLabel = fw.findChild(QLabel, "lblGIBadge")
        self.lbl_gi_5h: QLabel = fw.findChild(QLabel, "lblGI5h")
        self.lbl_gi_weekly: QLabel = fw.findChild(QLabel, "lblGIWeekly")
        self.lbl_gi_warning: QLabel = fw.findChild(QLabel, "lblGIWarning")

        # Claude
        self.val_claude_weighted: QLabel = fw.findChild(QLabel, "valClaudeWeighted")
        self.lbl_claude_badge: QLabel = fw.findChild(QLabel, "lblClaudeBadge")
        self.lbl_claude_5h: QLabel = fw.findChild(QLabel, "lblClaude5h")
        self.lbl_claude_weekly: QLabel = fw.findChild(QLabel, "lblClaudeWeekly")
        self.lbl_claude_warning: QLabel = fw.findChild(QLabel, "lblClaudeWarning")

        # Quick-connect
        self.edit_openai_url: QLineEdit = fw.findChild(QLineEdit, "editOpenAiUrl")
        self.btn_copy_openai: QPushButton = fw.findChild(QPushButton, "btnCopyOpenAi")
        self.edit_claude_url: QLineEdit = fw.findChild(QLineEdit, "editClaudeUrl")
        self.btn_copy_claude: QPushButton = fw.findChild(QPushButton, "btnCopyClaude")

        # Current account panel
        self.lbl_current_email: QLabel = fw.findChild(QLabel, "lblCurrentEmail")
        self.lbl_current_tier: QLabel = fw.findChild(QLabel, "lblCurrentTier")
        self.lbl_current_quota: QLabel = fw.findChild(QLabel, "lblCurrentQuota")
        self.lbl_current_status: QLabel = fw.findChild(QLabel, "lblCurrentStatus")

        # Best accounts table
        self.table_best_accounts: QTableWidget = fw.findChild(QTableWidget, "tableBestAccounts")

        # Quick Links
        self.btn_view_all_accounts: QPushButton = fw.findChild(QPushButton, "btnViewAllAccounts")
        self.btn_export_data_bottom: QPushButton = fw.findChild(QPushButton, "btnExportDataBottom")

        # Pool action buttons & main table
        self.btn_import_vscdb: QPushButton = fw.findChild(QPushButton, "btnImportVscdb")
        self.btn_add_account: QPushButton = fw.findChild(QPushButton, "btnAddAccount")
        self.btn_refresh_accounts: QPushButton = fw.findChild(QPushButton, "btnRefreshAccounts")
        self.table_accounts: QTableWidget = fw.findChild(QTableWidget, "tableAccounts")

    def _setup_table_headers(self):
        if self.table_accounts:
            h = self.table_accounts.horizontalHeader()
            h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        if self.table_best_accounts:
            h = self.table_best_accounts.horizontalHeader()
            h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self):
        if self.btn_toggle_proxy:
            self.btn_toggle_proxy.clicked.connect(self._toggle_proxy)
        if self.btn_refresh_quota:
            self.btn_refresh_quota.clicked.connect(self._refresh_current_quota)
        if self.btn_export_data:
            self.btn_export_data.clicked.connect(self._export_data)
        if self.btn_export_data_bottom:
            self.btn_export_data_bottom.clicked.connect(self._export_data)
        if self.btn_view_all_accounts:
            self.btn_view_all_accounts.clicked.connect(self._navigate_to_accounts)

        # Quota Matrix Pill Toggles
        if self.btn_only_available:
            self.btn_only_available.clicked.connect(lambda: self._set_only_available(True))
        if self.btn_include_disabled:
            self.btn_include_disabled.clicked.connect(lambda: self._set_only_available(False))

        # Copy buttons
        if self.btn_copy_openai:
            self.btn_copy_openai.clicked.connect(
                lambda: self._copy_to_clipboard(self.edit_openai_url.text())
            )
        if self.btn_copy_claude:
            self.btn_copy_claude.clicked.connect(
                lambda: self._copy_to_clipboard(self.edit_claude_url.text())
            )

        # Pool actions
        if self.btn_import_vscdb:
            self.btn_import_vscdb.clicked.connect(self._import_from_vscdb)
        if self.btn_add_account:
            self.btn_add_account.clicked.connect(self._show_add_account_dialog)
        if self.btn_refresh_accounts:
            self.btn_refresh_accounts.clicked.connect(self.load_from_config)

    def _set_only_available(self, only_available: bool):
        self.only_available = only_available
        if self.btn_only_available:
            self.btn_only_available.setChecked(only_available)
        if self.btn_include_disabled:
            self.btn_include_disabled.setChecked(not only_available)
        self.load_from_config()

    def _navigate_to_accounts(self):
        """Navigate to Account Settings page in MainWindow."""
        win = self.window()
        if hasattr(win, "_show_account_settings"):
            win._show_account_settings()
        elif hasattr(win, "stack"):
            win.stack.setCurrentIndex(5)

    def _copy_to_clipboard(self, text: str):
        QGuiApplication.clipboard().setText(text)

    # ------------------------------------------------------------------
    # Proxy Controls
    # ------------------------------------------------------------------

    def _toggle_proxy(self):
        if not self.bridge:
            return
        status = json.loads(self.bridge.get_proxy_status())
        port = status.get("port", 8045)
        if status.get("running"):
            self.bridge.stop_proxy()
            self._update_proxy_badge(running=False, port=port)
        else:
            self.bridge.start_proxy(port)
            self._update_proxy_badge(running=True, port=port)

    def _on_proxy_status_changed(self, running: bool, port: int):
        self._update_proxy_badge(running=running, port=port)

    def _update_proxy_badge(self, running: bool, port: int):
        if self.edit_openai_url:
            self.edit_openai_url.setText(f"http://127.0.0.1:{port}/v1")
        if self.edit_claude_url:
            self.edit_claude_url.setText(f"http://127.0.0.1:{port}/v1/messages")
        if self.val_proxy_port:
            self.val_proxy_port.display(port)

        if running:
            if self.lbl_proxy_badge:
                self.lbl_proxy_badge.setText(f"ONLINE : PORT {port}")
                self.lbl_proxy_badge.setStyleSheet(
                    "background-color: #28A745; color: #FFFFFF; border-radius: 4px;"
                    " padding: 4px 10px; font-size: 11px; font-weight: bold;"
                )
            if self.btn_toggle_proxy:
                self.btn_toggle_proxy.setText("Stop Proxy")
                self.btn_toggle_proxy.setStyleSheet(
                    "background-color: #DC3545; color: #FFFFFF; font-weight: bold;"
                    " border: none; border-radius: 5px; padding: 6px 14px; font-size: 11px;"
                )
        else:
            if self.lbl_proxy_badge:
                self.lbl_proxy_badge.setText("PROXY STOPPED")
                self.lbl_proxy_badge.setStyleSheet(
                    "background-color: #DC3545; color: #FFFFFF; border-radius: 4px;"
                    " padding: 4px 10px; font-size: 11px; font-weight: bold;"
                )
            if self.btn_toggle_proxy:
                self.btn_toggle_proxy.setText("Start Proxy")
                self.btn_toggle_proxy.setStyleSheet(
                    "background-color: #28A745; color: #FFFFFF; font-weight: bold;"
                    " border: none; border-radius: 5px; padding: 6px 14px; font-size: 11px;"
                )

    # ------------------------------------------------------------------
    # Refresh quota for current account
    # ------------------------------------------------------------------

    def _refresh_current_quota(self):
        if not self.bridge:
            QMessageBox.warning(self, "Proxy Not Ready", "Proxy bridge is not available.")
            return
        active = next((a for a in db.list_accounts() if a.get("is_active")), None)
        if not active:
            QMessageBox.information(self, "No Active Account", "No active account to refresh.")
            return
        try:
            if self.btn_refresh_quota:
                self.btn_refresh_quota.setEnabled(False)
                self.btn_refresh_quota.setText("Refreshing…")
            result = json.loads(self.bridge.refresh_account_quota(active.get("email", "")))
            if result.get("error"):
                QMessageBox.warning(self, "Refresh Failed", result["error"])
            else:
                self.load_from_config()
        except Exception as exc:
            QMessageBox.critical(self, "Refresh Error", str(exc))
        finally:
            if self.btn_refresh_quota:
                self.btn_refresh_quota.setEnabled(True)
                self.btn_refresh_quota.setText("Refresh Quota")

    # ------------------------------------------------------------------
    # Export accounts to JSON
    # ------------------------------------------------------------------

    def _export_data(self):
        accounts = db.list_accounts()
        export_data = []
        for acc in accounts:
            export_data.append({
                "email": acc.get("email", ""),
                "name": acc.get("name", ""),
                "subscription_tier": acc.get("subscription_tier", "FREE"),
                "is_active": bool(acc.get("is_active")),
                "health": _classify_account(acc),
                "quota": acc.get("quota") or {},
                "last_refreshed": acc.get("last_refreshed", 0),
            })

        default_path = str(Path.home() / f"antigravity_accounts_{int(time.time())}.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Account Data", default_path, "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(export_data)} accounts to:\n{file_path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    # ------------------------------------------------------------------
    # Quota Matrix Computation (exact line-by-line mirror of Dashboard.tsx)
    # ------------------------------------------------------------------

    def _get_5h_quota(self, acc: Dict[str, Any], model_key: str) -> Optional[int]:
        quota = acc.get("quota") or {}
        models = quota.get("models") or []
        if model_key == "gemini-image":
            for m in models:
                if "image" in m.get("name", "").lower():
                    return m.get("percentage")
            return None
        elif model_key == "claude":
            for m in models:
                if "claude" in m.get("name", "").lower():
                    return m.get("percentage")
            return None
        else:  # gemini-pro / text
            for m in models:
                n = m.get("name", "").lower()
                if "pro" in n and "gemini" in n:
                    return m.get("percentage")
            return quota.get("pro_percentage") or quota.get("flash_percentage")

    def _get_weekly_quota(self, acc: Dict[str, Any], model_key: str) -> Optional[int]:
        quota = acc.get("quota") or {}
        groups = quota.get("quota_groups") or []
        is_claude = (model_key == "claude")

        for g in groups:
            gname = (g.get("display_name") or "").lower()
            matches = (
                ("claude" in gname or "gpt" in gname or "3p" in gname)
                if is_claude
                else ("gemini" in gname or ("claude" not in gname and "gpt" not in gname and "3p" not in gname))
            )
            if matches:
                for b in g.get("buckets") or []:
                    w = (b.get("window") or "").lower()
                    bid = (b.get("bucket_id") or "").lower()
                    if "week" in w or "week" in bid or "7d" in w:
                        frac = b.get("remaining_fraction")
                        if frac is not None:
                            return int(round(frac * 100))
        return None

    def _compute_metrics(self, pool: List[Dict[str, Any]], model_key: str) -> Dict[str, Any]:
        if not pool:
            return {"avg5h": 0, "avgWeekly": 0, "weightedEffective": 0, "zeroWeeklyCount": 0}

        sum5h, count5h = 0, 0
        sumWeekly, countWeekly = 0, 0
        sumWeighted, totalWeight = 0.0, 0.0
        zeroWeeklyCount = 0

        for a in pool:
            q5h = self._get_5h_quota(a, model_key)
            qWeekly = self._get_weekly_quota(a, model_key)

            if q5h is not None and q5h >= 0:
                sum5h += q5h
                count5h += 1

            if qWeekly is not None and qWeekly >= 0:
                sumWeekly += qWeekly
                countWeekly += 1
                if qWeekly <= 0:
                    zeroWeeklyCount += 1

            effective = q5h if q5h is not None else 0
            if qWeekly is not None and qWeekly <= 0:
                effective = 0  # fuse to 0

            tier = (a.get("subscription_tier") or "FREE").upper()
            weight = 2.0 if "ULTRA" in tier else 1.5 if "PRO" in tier else 1.0
            sumWeighted += effective * weight
            totalWeight += weight

        avg5h = int(round(sum5h / count5h)) if count5h > 0 else 0
        avgWeekly = int(round(sumWeekly / countWeekly)) if countWeekly > 0 else 0
        weightedEffective = int(round(sumWeighted / totalWeight)) if totalWeight > 0 else 0

        return {
            "avg5h": avg5h,
            "avgWeekly": avgWeekly,
            "weightedEffective": weightedEffective,
            "zeroWeeklyCount": zeroWeeklyCount,
        }

    # ------------------------------------------------------------------
    # Main Data Load & Rendering
    # ------------------------------------------------------------------

    def load_from_config(self):
        accounts = db.list_accounts()

        # Health classifications
        abnormal_accounts = [a for a in accounts if _classify_account(a) == "abnormal"]
        disabled_accounts = [a for a in accounts if _classify_account(a) == "disabled"]
        available_accounts = [a for a in accounts if _classify_account(a) == "active"]
        normal_accounts = [a for a in accounts if _classify_account(a) != "abnormal"]

        total = len(accounts)
        abnormal = len(abnormal_accounts)
        disabled = len(disabled_accounts)
        available = len(available_accounts)
        normal = len(normal_accounts)

        # Base pool for matrix calculation
        base_pool = (
            (available_accounts if available > 0 else normal_accounts)
            if self.only_available
            else normal_accounts
        )

        # Proxy status
        port = 8045
        running = False
        if self.bridge:
            try:
                status = json.loads(self.bridge.get_proxy_status())
                port = status.get("port", 8045)
                running = status.get("running", False)
            except Exception:
                pass

        # Tokens
        total_tokens = sum((a.get("quota") or {}).get("used_tokens", 0) for a in accounts)
        total_requests = sum((a.get("quota") or {}).get("request_count", 0) for a in accounts)

        # LCD Cards
        _lcd = lambda w, v: w.display(v) if w else None
        _lcd(self.val_total_accounts, total)
        _lcd(self.val_active_accounts, available)
        _lcd(self.val_disabled_accounts, disabled)
        _lcd(self.val_abnormal_accounts, abnormal)
        _lcd(self.val_proxy_port, port)
        _lcd(self.val_total_tokens, total_tokens)
        _lcd(self.val_total_requests, total_requests)

        # Risk badge coloring
        if self.lbl_risk_badge and self.val_abnormal_accounts:
            if abnormal > 0:
                self.lbl_risk_badge.setStyleSheet(
                    "background-color: #FEB2B2; color: #742A2A; border-radius: 4px;"
                    " padding: 2px 6px; font-size: 9px; font-weight: bold;"
                )
                self.val_abnormal_accounts.setStyleSheet("color: #E53E3E;")
            else:
                self.lbl_risk_badge.setStyleSheet(
                    "background-color: #E2E8F0; color: #4A5568; border-radius: 4px;"
                    " padding: 2px 6px; font-size: 9px; font-weight: bold;"
                )
                self.val_abnormal_accounts.setStyleSheet("color: #718096;")

        # Greeting
        current_acc = next((a for a in accounts if a.get("is_active")), None)
        if self.lbl_greeting:
            if current_acc:
                name = current_acc.get("name") or current_acc.get("email", "")
                self.lbl_greeting.setText(f"Hello, {name.split('@')[0]}!")
            else:
                self.lbl_greeting.setText("Hello!")

        # Update Quota Matrix Section
        self._render_quota_matrix(base_pool, available, normal)

        # Update Current Account, Best Accounts, Proxy Badge, and Accounts Table
        self._render_current_account(current_acc)
        self._update_proxy_badge(running=running, port=port)
        self._render_best_accounts(accounts)
        self._render_accounts_table(accounts)

    # ------------------------------------------------------------------
    # Render Quota Productivity Matrix
    # ------------------------------------------------------------------

    def _render_quota_matrix(self, base_pool: List[Dict[str, Any]], available_count: int, normal_count: int):
        # Update dynamic title and pool count
        if self.lbl_quota_matrix_title:
            if self.only_available:
                self.lbl_quota_matrix_title.setText("Available Accounts Quota Productivity Matrix")
            else:
                self.lbl_quota_matrix_title.setText("All Normal Accounts Quota Matrix (Including Disabled)")

        if self.lbl_pool_count_badge:
            self.lbl_pool_count_badge.setText(f"(Pool: {len(base_pool)})")

        if self.btn_only_available:
            self.btn_only_available.setText(f"Available ({available_count})")
            self.btn_only_available.setChecked(self.only_available)

        if self.btn_include_disabled:
            self.btn_include_disabled.setText(f"Include Disabled ({normal_count})")
            self.btn_include_disabled.setChecked(not self.only_available)

        # Compute metrics for the 3 model families
        gt = self._compute_metrics(base_pool, "gemini-pro")
        gi = self._compute_metrics(base_pool, "gemini-image")
        cl = self._compute_metrics(base_pool, "claude")

        # 1. Gemini Text
        if self.val_gt_weighted:
            self.val_gt_weighted.setText(f"{gt['weightedEffective']}%")
        if self.lbl_gt_badge:
            suff = gt["weightedEffective"] >= 50
            self.lbl_gt_badge.setText("Sufficient" if suff else "Tight")
            self.lbl_gt_badge.setStyleSheet(
                "background-color: #C6F6D5; color: #22543D; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
                if suff else
                "background-color: #FEEBC8; color: #7B341E; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
            )
        if self.lbl_gt_5h:
            self.lbl_gt_5h.setText(f"5H Rolling: {gt['avg5h']}%")
        if self.lbl_gt_weekly:
            self.lbl_gt_weekly.setText(f"7D Weekly: {gt['avgWeekly']}%")
        if self.lbl_gt_warning:
            if gt["zeroWeeklyCount"] > 0:
                self.lbl_gt_warning.setText(f"⚠ {gt['zeroWeeklyCount']} accounts weekly quota fused to zero")
            else:
                self.lbl_gt_warning.setText("")

        # 2. Gemini Image
        if self.val_gi_weighted:
            self.val_gi_weighted.setText(f"{gi['weightedEffective']}%")
        if self.lbl_gi_badge:
            suff = gi["weightedEffective"] >= 50
            self.lbl_gi_badge.setText("Sufficient" if suff else "Tight")
            self.lbl_gi_badge.setStyleSheet(
                "background-color: #E9D8FD; color: #44337A; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
                if suff else
                "background-color: #FEEBC8; color: #7B341E; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
            )
        if self.lbl_gi_5h:
            self.lbl_gi_5h.setText(f"5H Rolling: {gi['avg5h']}%")
        if self.lbl_gi_weekly:
            self.lbl_gi_weekly.setText(f"7D Weekly: {gi['avgWeekly']}%")
        if self.lbl_gi_warning:
            if gi["zeroWeeklyCount"] > 0:
                self.lbl_gi_warning.setText(f"⚠ {gi['zeroWeeklyCount']} accounts weekly quota fused to zero")
            else:
                self.lbl_gi_warning.setText("")

        # 3. Claude
        if self.val_claude_weighted:
            self.val_claude_weighted.setText(f"{cl['weightedEffective']}%")
        if self.lbl_claude_badge:
            suff = cl["weightedEffective"] >= 50
            self.lbl_claude_badge.setText("Sufficient" if suff else "Tight")
            self.lbl_claude_badge.setStyleSheet(
                "background-color: #BEE3F8; color: #2A4365; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
                if suff else
                "background-color: #FEEBC8; color: #7B341E; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
            )
        if self.lbl_claude_5h:
            self.lbl_claude_5h.setText(f"5H Rolling: {cl['avg5h']}%")
        if self.lbl_claude_weekly:
            self.lbl_claude_weekly.setText(f"7D Weekly: {cl['avgWeekly']}%")
        if self.lbl_claude_warning:
            if cl["zeroWeeklyCount"] > 0:
                self.lbl_claude_warning.setText(f"⚠ {cl['zeroWeeklyCount']} accounts weekly quota fused to zero")
            else:
                self.lbl_claude_warning.setText("")

    # ------------------------------------------------------------------
    # Current Account Panel
    # ------------------------------------------------------------------

    def _render_current_account(self, acc: Optional[Dict[str, Any]]):
        if not acc:
            if self.lbl_current_email:
                self.lbl_current_email.setText("No account active")
            if self.lbl_current_tier:
                self.lbl_current_tier.setText("Tier: —")
            if self.lbl_current_quota:
                self.lbl_current_quota.setText("Quota: —")
            if self.lbl_current_status:
                self.lbl_current_status.setText("Status: —")
            return

        email = acc.get("email", "")
        tier = acc.get("subscription_tier", "FREE")
        quota: Dict[str, Any] = acc.get("quota") or {}
        flash_pct = quota.get("flash_percentage", 100)
        pro_pct = quota.get("pro_percentage", 100)
        is_forbidden = quota.get("is_forbidden", False)

        if self.lbl_current_email:
            self.lbl_current_email.setText(email)
        if self.lbl_current_tier:
            self.lbl_current_tier.setText(f"Tier: {tier}")
        if self.lbl_current_quota:
            self.lbl_current_quota.setText(f"Flash Quota: {flash_pct}%   Pro Quota: {pro_pct}%")
        if self.lbl_current_status:
            status_text = "⚠ Forbidden (Quota Blocked)" if is_forbidden else "✓ Healthy"
            self.lbl_current_status.setText(f"Status: {status_text}")
            color = "#E53E3E" if is_forbidden else "#28A745"
            self.lbl_current_status.setStyleSheet(f"font-size: 11px; color: {color};")

    # ------------------------------------------------------------------
    # Best Accounts Panel (top 5)
    # ------------------------------------------------------------------

    def _render_best_accounts(self, accounts: List[Dict[str, Any]]):
        if not self.table_best_accounts:
            return

        pool = [a for a in accounts if _classify_account(a) == "active"]
        pool.sort(
            key=lambda a: (a.get("quota") or {}).get("flash_percentage", 0),
            reverse=True,
        )
        top = pool[:5]

        self.table_best_accounts.setRowCount(len(top))
        for row, acc in enumerate(top):
            email = acc.get("email", "")
            tier = acc.get("subscription_tier", "FREE")
            quota = acc.get("quota") or {}
            flash_pct = quota.get("flash_percentage", 100)
            acc_id = str(acc.get("id", ""))

            item_email = QTableWidgetItem(email)
            item_tier = QTableWidgetItem(tier)
            item_tier.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_quota = QTableWidgetItem(f"{flash_pct}%")
            item_quota.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_best_accounts.setItem(row, 0, item_email)
            self.table_best_accounts.setItem(row, 1, item_tier)
            self.table_best_accounts.setItem(row, 2, item_quota)

            btn_switch = QPushButton("Switch")
            btn_switch.setStyleSheet(
                "background-color: #0D6EFD; color: white; font-size: 10px;"
                " border: none; border-radius: 3px; padding: 3px 8px;"
            )
            btn_switch.clicked.connect(
                lambda checked=False, aid=acc_id: self._switch_account(aid)
            )
            self.table_best_accounts.setCellWidget(row, 3, btn_switch)

    # ------------------------------------------------------------------
    # Full Account Pool Table
    # ------------------------------------------------------------------

    def _render_accounts_table(self, accounts: List[Dict[str, Any]]):
        if not self.table_accounts:
            return

        self.table_accounts.setRowCount(len(accounts))
        for row, acc in enumerate(accounts):
            acc_id = str(acc.get("id", ""))
            health = _classify_account(acc)
            quota: Dict[str, Any] = acc.get("quota") or {}
            flash_pct = quota.get("flash_percentage", 100)

            status_text = {"active": "Active", "disabled": "Disabled", "abnormal": "Risk"}.get(health, "Unknown")
            status_color = {"active": Qt.GlobalColor.darkGreen, "disabled": Qt.GlobalColor.gray, "abnormal": Qt.GlobalColor.red}.get(health, Qt.GlobalColor.black)
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setForeground(status_color)

            item_email = QTableWidgetItem(acc.get("email", ""))
            item_name = QTableWidgetItem(acc.get("name", "") or acc.get("email", ""))
            item_tier = QTableWidgetItem(acc.get("subscription_tier", "FREE"))
            item_tier.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_quota = QTableWidgetItem(f"{flash_pct}%")
            item_quota.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_accounts.setItem(row, 0, item_status)
            self.table_accounts.setItem(row, 1, item_email)
            self.table_accounts.setItem(row, 2, item_name)
            self.table_accounts.setItem(row, 3, item_tier)
            self.table_accounts.setItem(row, 4, item_quota)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            is_active = bool(acc.get("is_active"))
            btn_switch = QPushButton("Active" if is_active else "Activate")
            btn_switch.setEnabled(not is_active)
            btn_switch.clicked.connect(lambda checked=False, aid=acc_id: self._switch_account(aid))
            actions_layout.addWidget(btn_switch)

            btn_del = QPushButton("Remove")
            btn_del.setStyleSheet("color: #DC3545;")
            btn_del.clicked.connect(lambda checked=False, aid=acc_id: self._delete_account(aid))
            actions_layout.addWidget(btn_del)

            self.table_accounts.setCellWidget(row, 5, actions_widget)

    # ------------------------------------------------------------------
    # Account actions
    # ------------------------------------------------------------------

    def _switch_account(self, account_id: str):
        if self.bridge:
            try:
                res = json.loads(self.bridge.switch_account(account_id))
                if not res.get("success"):
                    QMessageBox.warning(self, "Switch Failed", res.get("error", "Failed to switch account"))
                    return
            except Exception as exc:
                accounts = db.list_accounts()
                acc = next((a for a in accounts if str(a.get("id")) == account_id), None)
                if acc:
                    db.set_active_account(acc.get("email", ""))
                else:
                    QMessageBox.warning(self, "Switch Failed", str(exc))
                    return
        else:
            accounts = db.list_accounts()
            acc = next((a for a in accounts if str(a.get("id")) == account_id), None)
            if acc:
                db.set_active_account(acc.get("email", ""))
        self.load_from_config()

    def _delete_account(self, account_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            "Are you sure you want to remove this account from the pool?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            accounts = db.list_accounts()
            acc = next((a for a in accounts if str(a.get("id")) == account_id), None)
            if acc:
                db.delete_account(acc.get("email", ""))
            self.load_from_config()

    def _import_from_vscdb(self):
        try:
            acc = VscdbImporter.import_live_antigravity_account()
            if acc:
                QMessageBox.information(
                    self, "Import Successful",
                    f"Successfully imported Antigravity account:\n{acc.get('email', '')}",
                )
                self.load_from_config()
            else:
                QMessageBox.warning(self, "Import Notice", "No Antigravity tokens found in local storage.")
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Failed to import from Antigravity: {exc}")

    def _show_add_account_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Google Account")
        dialog.setMinimumWidth(450)

        layout = QVBoxLayout(dialog)
        info_lbl = QLabel(
            "<b>Add an account to the pool:</b><br>"
            "1. Click <i>Launch Google Login</i> to authenticate via browser.<br>"
            "2. Or enter a Refresh Token manually.",
            dialog,
        )
        layout.addWidget(info_lbl)

        btn_browser = QPushButton("Launch Google Login (Browser OAuth)", dialog)
        btn_browser.setStyleSheet("background-color: #0D6EFD; color: white; font-weight: bold; padding: 8px;")
        layout.addWidget(btn_browser)

        def _launch_browser():
            try:
                url, _server = AccountManager.prepare_oauth_login()
                QDesktopServices.openUrl(QUrl(url))
                QMessageBox.information(
                    dialog, "Browser Opened",
                    "A Google OAuth consent page has opened in your default browser.\n"
                    "Once you authorize, the account will automatically be imported.",
                )
            except Exception as ex:
                QMessageBox.critical(dialog, "OAuth Error", str(ex))

        btn_browser.clicked.connect(_launch_browser)

        form_layout = QFormLayout()
        edit_email = QLineEdit(dialog)
        edit_email.setPlaceholderText("user@gmail.com (optional)")
        edit_token = QLineEdit(dialog)
        edit_token.setPlaceholderText("Enter Google refresh token")
        edit_token.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Email:", edit_email)
        form_layout.addRow("Refresh Token:", edit_token)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        layout.addWidget(buttons)

        def _on_accept():
            token = edit_token.text().strip()
            if not token:
                QMessageBox.warning(dialog, "Input Required", "Please enter a refresh token or use the browser login button.")
                return
            if self.bridge:
                try:
                    res = json.loads(self.bridge.add_account(edit_email.text().strip(), token))
                    if "error" in res:
                        QMessageBox.critical(dialog, "Add Account Error", res["error"])
                        return
                except Exception:
                    db.add_or_update_account(edit_email.text().strip(), token)
            else:
                db.add_or_update_account(edit_email.text().strip(), token)
            dialog.accept()
            self.load_from_config()

        buttons.accepted.connect(_on_accept)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()
