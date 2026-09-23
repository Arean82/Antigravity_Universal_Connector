import os
import json
import time
import secrets
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem, QPushButton,
    QHBoxLayout, QMessageBox, QHeaderView, QApplication
)
from PySide6.QtCore import QFile, Signal, Qt, QTimer
from PySide6.QtUiTools import QUiLoader

from src.core.database import db

class UserTokensPage(QWidget):
    """
    100% Native PySide6 User Tokens & Authentication Controller.
    Renders user_tokens.ui directly via QUiLoader (zero intermediate .py files).
    Zero regular expressions.
    Manages client authentication tokens, rate limits, daily quotas, and clipboard actions.
    """
    tokensSaved = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.tokens: List[Dict[str, Any]] = []

        # Direct QUiLoader loading
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "user_tokens.ui")
        ui_file = QFile(ui_path)
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Cannot open UI file: {ui_path}")

        loader = QUiLoader()
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        if self.ui is None:
            raise RuntimeError(f"Failed to load UI from {ui_path}: {loader.errorString()}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # Configure table header behavior
        self.ui.tableTokens.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.tableTokens.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ui.tableTokens.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ui.tableTokens.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.ui.tableTokens.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.ui.tableTokens.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self._connect_signals()
        self.load_from_config()

    def _connect_signals(self):
        self.ui.btnGenerateToken.clicked.connect(self._on_generate_token)
        self.ui.btnRevokeSelected.clicked.connect(self._on_revoke_selected_token)
        self.ui.btnSaveSettings.clicked.connect(self.save_settings)

    def load_from_config(self):
        saved = db.get_setting("user_tokens_registry")
        if saved:
            try:
                self.tokens = json.loads(saved)
            except Exception:
                self.tokens = []
        else:
            self.tokens = []

        self._refresh_table()

    def save_settings(self):
        db.set_setting("user_tokens_registry", json.dumps(self.tokens))
        self.tokensSaved.emit()

        self.ui.lblStatusMessage.setText("User tokens saved successfully.")
        QTimer.singleShot(3000, lambda: self.ui.lblStatusMessage.setText(""))

    def _on_generate_token(self):
        name = self.ui.editTokenName.text().strip()
        if not name:
            QMessageBox.warning(self, "Client Name Required", "Please enter a client or application name.")
            return

        rpm = self.ui.spinRpm.value()
        daily_quota = self.ui.spinDailyQuota.value()

        # Secure token generation
        random_suffix = secrets.token_urlsafe(24)
        secret_key = f"sk-antigravity-{random_suffix}"

        token_record = {
            "id": f"tok_{int(time.time() * 1000)}",
            "name": name,
            "token": secret_key,
            "rpm": rpm,
            "daily_quota": daily_quota,
            "status": "Active",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "used_today": 0
        }

        self.tokens.append(token_record)
        self.ui.editTokenName.clear()
        self._refresh_table()
        self.save_settings()

    def _on_revoke_selected_token(self):
        row = self.ui.tableTokens.currentRow()
        if 0 <= row < len(self.tokens):
            del self.tokens[row]
            self._refresh_table()
            self.save_settings()

    def _copy_token_to_clipboard(self, token_str: str):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(token_str)
            self.ui.lblStatusMessage.setText(f"Copied token to clipboard!")
            QTimer.singleShot(2500, lambda: self.ui.lblStatusMessage.setText(""))

    def _toggle_token_status(self, idx: int):
        if 0 <= idx < len(self.tokens):
            curr = self.tokens[idx].get("status", "Active")
            self.tokens[idx]["status"] = "Suspended" if curr == "Active" else "Active"
            self._refresh_table()
            self.save_settings()

    def _refresh_table(self):
        self.ui.tableTokens.setRowCount(0)
        active_count = 0
        total_requests = 0

        for idx, tok in enumerate(self.tokens):
            self.ui.tableTokens.insertRow(idx)

            is_active = tok.get("status") == "Active"
            if is_active:
                active_count += 1
            total_requests += tok.get("used_today", 0)

            # Name
            self.ui.tableTokens.setItem(idx, 0, QTableWidgetItem(tok.get("name", "")))

            # Secret (masked preview)
            raw_token = tok.get("token", "")
            masked = raw_token[:15] + "..." + raw_token[-4:] if len(raw_token) > 20 else raw_token
            self.ui.tableTokens.setItem(idx, 1, QTableWidgetItem(masked))

            # Rate Limit
            rpm_val = tok.get("rpm", 0)
            rpm_str = "Unlimited" if rpm_val == 0 else f"{rpm_val} RPM"
            self.ui.tableTokens.setItem(idx, 2, QTableWidgetItem(rpm_str))

            # Daily Quota
            quota_val = tok.get("daily_quota", 0)
            quota_str = "Unlimited" if quota_val == 0 else f"{quota_val}/day"
            self.ui.tableTokens.setItem(idx, 3, QTableWidgetItem(quota_str))

            # Status
            status_item = QTableWidgetItem(tok.get("status", "Active"))
            status_item.setTextAlignment(Qt.AlignCenter)
            if is_active:
                status_item.setForeground(Qt.darkGreen)
            else:
                status_item.setForeground(Qt.red)
            self.ui.tableTokens.setItem(idx, 4, status_item)

            # Action widget container
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)

            btn_copy = QPushButton("Copy")
            btn_copy.setStyleSheet("font-size: 10px; padding: 2px 6px;")
            btn_copy.clicked.connect(lambda checked=False, t=raw_token: self._copy_token_to_clipboard(t))
            action_layout.addWidget(btn_copy)

            btn_toggle = QPushButton("Pause" if is_active else "Resume")
            btn_toggle.setStyleSheet("font-size: 10px; padding: 2px 6px;")
            btn_toggle.clicked.connect(lambda checked=False, t_idx=idx: self._toggle_token_status(t_idx))
            action_layout.addWidget(btn_toggle)

            btn_del = QPushButton("Delete")
            btn_del.setStyleSheet("color: #DC3545; font-size: 10px; padding: 2px 6px;")
            btn_del.clicked.connect(lambda checked=False, t_idx=idx: self._delete_token_by_index(t_idx))
            action_layout.addWidget(btn_del)

            self.ui.tableTokens.setCellWidget(idx, 5, action_widget)

        # Update cards
        if hasattr(self.ui.valTotalTokens, "display"):
            self.ui.valTotalTokens.display(len(self.tokens))
        elif hasattr(self.ui.valTotalTokens, "setText"):
            self.ui.valTotalTokens.setText(str(len(self.tokens)))

        if hasattr(self.ui.valActiveTokens, "display"):
            self.ui.valActiveTokens.display(active_count)
        elif hasattr(self.ui.valActiveTokens, "setText"):
            self.ui.valActiveTokens.setText(str(active_count))

        if hasattr(self.ui.valTodayRequests, "display"):
            self.ui.valTodayRequests.display(total_requests)
        elif hasattr(self.ui.valTodayRequests, "setText"):
            self.ui.valTodayRequests.setText(str(total_requests))

    def _delete_token_by_index(self, index: int):
        if 0 <= index < len(self.tokens):
            del self.tokens[index]
            self._refresh_table()
            self.save_settings()
