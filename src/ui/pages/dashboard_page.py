"""Native PySide6 Dashboard Page Controller.
Directly loads dashboard.ui dynamically via QUiLoader (Zero UIC compilation).
Features QLCDNumber metric display cards, service controls, 1-click Antigravity import,
Google OAuth loopback & direct token login dialogs, and real-time account pool management.
"""

from __future__ import annotations

import os
import json
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QFile, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QDesktopServices
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLCDNumber,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
)

from src.core.database import db
from src.core.vscdb_importer import VscdbImporter
from src.core.account_manager import AccountManager


class DashboardPage(QWidget):
    """
    Landing Dashboard page loaded dynamically from src/ui/forms/dashboard.ui.
    Integrates QLCDNumber summary cards, Quick-Connect URL copying,
    and Google Account pool management with 1-click Antigravity import.
    """

    def __init__(self, bridge=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.bridge = bridge

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

        # Connect bridge signals if available
        if self.bridge:
            self.bridge.proxyStatusChanged.connect(self._on_proxy_status_changed)
            self.bridge.accountSwitched.connect(lambda acc_id: self.load_from_config())

    def _bind_widgets(self):
        # Header & Proxy Controls
        self.lbl_proxy_badge: QLabel = self.form_widget.findChild(QLabel, "lblProxyBadge")
        self.btn_toggle_proxy: QPushButton = self.form_widget.findChild(QPushButton, "btnToggleProxy")

        # QLCDNumber widgets
        self.val_active_accounts: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valActiveAccounts")
        self.val_proxy_port: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valProxyPort")
        self.val_total_tokens: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valTotalTokens")
        self.val_total_requests: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valTotalRequests")

        # Quick Connect
        self.edit_openai_url: QLineEdit = self.form_widget.findChild(QLineEdit, "editOpenAiUrl")
        self.btn_copy_openai: QPushButton = self.form_widget.findChild(QPushButton, "btnCopyOpenAi")
        self.edit_claude_url: QLineEdit = self.form_widget.findChild(QLineEdit, "editClaudeUrl")
        self.btn_copy_claude: QPushButton = self.form_widget.findChild(QPushButton, "btnCopyClaude")

        # Account Pool
        self.btn_import_vscdb: QPushButton = self.form_widget.findChild(QPushButton, "btnImportVscdb")
        self.btn_add_account: QPushButton = self.form_widget.findChild(QPushButton, "btnAddAccount")
        self.btn_refresh_accounts: QPushButton = self.form_widget.findChild(QPushButton, "btnRefreshAccounts")
        self.table_accounts: QTableWidget = self.form_widget.findChild(QTableWidget, "tableAccounts")

    def _setup_table_headers(self):
        if self.table_accounts:
            header = self.table_accounts.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

    def _connect_signals(self):
        if self.btn_toggle_proxy:
            self.btn_toggle_proxy.clicked.connect(self._toggle_proxy)
        if self.btn_copy_openai:
            self.btn_copy_openai.clicked.connect(lambda: self._copy_to_clipboard(self.edit_openai_url.text()))
        if self.btn_copy_claude:
            self.btn_copy_claude.clicked.connect(lambda: self._copy_to_clipboard(self.edit_claude_url.text()))
        if self.btn_import_vscdb:
            self.btn_import_vscdb.clicked.connect(self._import_from_vscdb)
        if self.btn_add_account:
            self.btn_add_account.clicked.connect(self._show_add_account_dialog)
        if self.btn_refresh_accounts:
            self.btn_refresh_accounts.clicked.connect(self.load_from_config)

    def _copy_to_clipboard(self, text: str):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Copied", f"Copied to clipboard:\n{text}")

    def _toggle_proxy(self):
        if not self.bridge:
            return
        status = json.loads(self.bridge.get_proxy_status())
        if status.get("running"):
            self.bridge.stop_proxy()
            self._update_proxy_badge(running=False, port=status.get("port", 8045))
        else:
            port = status.get("port", 8045)
            self.bridge.start_proxy(port)
            self._update_proxy_badge(running=True, port=port)

    def _on_proxy_status_changed(self, running: bool, port: int):
        self._update_proxy_badge(running=running, port=port)

    def _update_proxy_badge(self, running: bool, port: int):
        if running:
            if self.lbl_proxy_badge:
                self.lbl_proxy_badge.setText(f"ONLINE : PORT {port}")
                self.lbl_proxy_badge.setStyleSheet(
                    "background-color: #28A745; color: #FFFFFF; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
                )
            if self.btn_toggle_proxy:
                self.btn_toggle_proxy.setText("Stop Proxy")
                self.btn_toggle_proxy.setStyleSheet(
                    "background-color: #DC3545; color: #FFFFFF; font-weight: bold; border: none; border-radius: 5px; padding: 6px 14px; font-size: 11px;"
                )
        else:
            if self.lbl_proxy_badge:
                self.lbl_proxy_badge.setText("PROXY STOPPED")
                self.lbl_proxy_badge.setStyleSheet(
                    "background-color: #DC3545; color: #FFFFFF; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
                )
            if self.btn_toggle_proxy:
                self.btn_toggle_proxy.setText("Start Proxy")
                self.btn_toggle_proxy.setStyleSheet(
                    "background-color: #28A745; color: #FFFFFF; font-weight: bold; border: none; border-radius: 5px; padding: 6px 14px; font-size: 11px;"
                )

    def _import_from_vscdb(self):
        try:
            acc = VscdbImporter.import_live_antigravity_account()
            if acc:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Successfully imported Antigravity account:\n{acc.get('email', '')}"
                )
                self.load_from_config()
            else:
                QMessageBox.warning(
                    self,
                    "Import Notice",
                    "No Antigravity tokens found in local storage."
                )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import from Antigravity: {e}")

    def _show_add_account_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Google Account")
        dialog.setMinimumWidth(450)

        layout = QVBoxLayout(dialog)

        info_lbl = QLabel(
            "<b>Add an account to the pool:</b><br>"
            "1. Click <i>Launch Google Login</i> to authenticate via browser.<br>"
            "2. Or enter a Refresh Token manually.",
            dialog
        )
        layout.addWidget(info_lbl)

        btn_browser = QPushButton("Launch Google Login (Browser OAuth)", dialog)
        btn_browser.setStyleSheet(
            "background-color: #0D6EFD; color: white; font-weight: bold; padding: 8px;"
        )
        layout.addWidget(btn_browser)

        def _launch_browser():
            try:
                url, server = AccountManager.prepare_oauth_login()
                QDesktopServices.openUrl(QUrl(url))
                QMessageBox.information(
                    dialog,
                    "Browser Opened",
                    "A Google OAuth consent page has opened in your default browser.\n"
                    "Once you authorize, the account will automatically be imported."
                )
            except Exception as ex:
                QMessageBox.critical(dialog, "OAuth Error", str(ex))

        btn_browser.clicked.connect(_launch_browser)

        form_layout = QFormLayout()
        edit_email = QLineEdit(dialog)
        edit_email.setPlaceholderText("user@gmail.com (optional)")
        edit_token = QLineEdit(dialog)
        edit_token.setPlaceholderText("Enter Google refresh token")
        edit_token.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Email:", edit_email)
        form_layout.addRow("Refresh Token:", edit_token)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        layout.addWidget(buttons)

        def _on_accept():
            token = edit_token.text().strip()
            if not token:
                QMessageBox.warning(dialog, "Input Required", "Please enter a refresh token or use the browser login button.")
                return
            if self.bridge:
                res = json.loads(self.bridge.add_account(edit_email.text().strip(), token))
                if "error" in res:
                    QMessageBox.critical(dialog, "Add Account Error", res["error"])
                    return
            dialog.accept()
            self.load_from_config()

        buttons.accepted.connect(_on_accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def load_from_config(self):
        """Loads live account pool, proxy status, and updates QLCDNumber cards."""
        accounts = db.list_accounts()
        active_count = len([a for a in accounts if a.get("is_active")])

        port = 8045
        running = True
        if self.bridge:
            status = json.loads(self.bridge.get_proxy_status())
            port = status.get("port", 8045)
            running = status.get("running", False)

        total_tokens = 0
        for a in accounts:
            q = a.get("quota") or {}
            if isinstance(q, dict):
                total_tokens += q.get("used_tokens", 0) or q.get("total_tokens", 0)

        # Update QLCDNumber displays
        if self.val_active_accounts:
            self.val_active_accounts.display(active_count)
        if self.val_proxy_port:
            self.val_proxy_port.display(port)
        if self.val_total_tokens:
            self.val_total_tokens.display(total_tokens)
        if self.val_total_requests:
            self.val_total_requests.display(len(accounts))

        self._update_proxy_badge(running=running, port=port)
        self._render_accounts_table(accounts)

    def _render_accounts_table(self, accounts: List[Dict[str, Any]]):
        if not self.table_accounts:
            return

        self.table_accounts.setRowCount(len(accounts))
        for row, a in enumerate(accounts):
            acc_id = str(a.get("id", ""))
            is_active = bool(a.get("is_active", False))

            item_active = QTableWidgetItem("Active" if is_active else "Standby")
            item_active.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_active:
                item_active.setForeground(Qt.GlobalColor.darkGreen)

            item_email = QTableWidgetItem(a.get("email", ""))
            item_name = QTableWidgetItem(a.get("name", "") or a.get("email", ""))
            item_tier = QTableWidgetItem(a.get("subscription_tier", "FREE"))
            item_tier.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_status = QTableWidgetItem("Ready")
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_accounts.setItem(row, 0, item_active)
            self.table_accounts.setItem(row, 1, item_email)
            self.table_accounts.setItem(row, 2, item_name)
            self.table_accounts.setItem(row, 3, item_tier)
            self.table_accounts.setItem(row, 4, item_status)

            # Actions widget (Switch / Delete)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            btn_switch = QPushButton("Activate" if not is_active else "Active")
            btn_switch.setEnabled(not is_active)
            btn_switch.clicked.connect(lambda checked=False, aid=acc_id: self._switch_account(aid))
            actions_layout.addWidget(btn_switch)

            btn_del = QPushButton("Remove")
            btn_del.setStyleSheet("color: #DC3545;")
            btn_del.clicked.connect(lambda checked=False, aid=acc_id: self._delete_account(aid))
            actions_layout.addWidget(btn_del)

            self.table_accounts.setCellWidget(row, 5, actions_widget)

    def _switch_account(self, account_id: str):
        if self.bridge:
            res = json.loads(self.bridge.switch_account(account_id))
            if res.get("success"):
                self.load_from_config()
            else:
                QMessageBox.warning(self, "Switch Failed", res.get("error", "Failed to switch account"))

    def _delete_account(self, account_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            "Are you sure you want to remove this account from the pool?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_account(account_id)
            self.load_from_config()
