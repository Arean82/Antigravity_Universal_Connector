import os
import json
import time
import ipaddress
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem, QPushButton,
    QHBoxLayout, QMessageBox, QHeaderView
)
from PySide6.QtCore import QFile, Signal, Qt, QTimer
from PySide6.QtUiTools import QUiLoader

from src.core.database import db

class IpManagementPage(QWidget):
    """
    100% Native PySide6 IP Management & Firewall Controller.
    Renders ip_management.ui directly via QUiLoader (zero intermediate .py files).
    Zero regular expressions (uses Python's standard ipaddress module).
    Persists configuration directly into SQLite database.
    """
    policySaved = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.rules: List[Dict[str, Any]] = []

        # Direct QUiLoader loading
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "ip_management.ui")
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

        # Configure tables
        self.ui.tableRules.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.tableRules.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ui.tableRules.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ui.tableRules.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.ui.tableRules.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.ui.tableAuditLog.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.tableAuditLog.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.ui.tableAuditLog.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ui.tableAuditLog.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self._connect_signals()
        self.load_from_config()

    def _connect_signals(self):
        self.ui.btnAddRule.clicked.connect(self._on_add_rule)
        self.ui.btnDeleteSelected.clicked.connect(self._on_delete_selected_rule)
        self.ui.btnClearAllRules.clicked.connect(self._on_clear_all_rules)
        self.ui.btnClearAuditLog.clicked.connect(self._on_clear_audit_log)
        self.ui.btnSaveSettings.clicked.connect(self.save_settings)

    def load_from_config(self):
        saved_policy = db.get_setting("ip_security_policy")
        if saved_policy:
            try:
                data = json.loads(saved_policy)
                self.ui.chkEnableFiltering.setChecked(bool(data.get("enabled", False)))
                mode_idx = 1 if data.get("mode") == "whitelist" else 0
                self.ui.comboFilterMode.setCurrentIndex(mode_idx)
                self.ui.chkAllowLoopback.setChecked(bool(data.get("allow_loopback", True)))
                self.ui.chkAllowLan.setChecked(bool(data.get("allow_lan", True)))
                self.rules = data.get("rules", [])
            except Exception:
                self.rules = []
        else:
            self.rules = []

        self._refresh_rules_table()
        self._refresh_audit_log()

    def save_settings(self):
        mode_val = "whitelist" if self.ui.comboFilterMode.currentIndex() == 1 else "blacklist"
        data = {
            "enabled": self.ui.chkEnableFiltering.isChecked(),
            "mode": mode_val,
            "allow_loopback": self.ui.chkAllowLoopback.isChecked(),
            "allow_lan": self.ui.chkAllowLan.isChecked(),
            "rules": self.rules
        }

        db.set_setting("ip_security_policy", json.dumps(data))
        self.policySaved.emit()

        self.ui.lblStatusMessage.setText("Access policy successfully saved.")
        QTimer.singleShot(3000, lambda: self.ui.lblStatusMessage.setText(""))

    def _on_add_rule(self):
        ip_str = self.ui.editRuleIp.text().strip()
        note = self.ui.editRuleNote.text().strip()
        action = self.ui.comboRuleAction.currentText()

        if not ip_str:
            QMessageBox.warning(self, "Invalid IP Pattern", "Please enter an IP address or CIDR subnet.")
            return

        # Validate IP or CIDR without regex using ipaddress module
        try:
            if "/" in ip_str:
                ipaddress.ip_network(ip_str, strict=False)
            else:
                ipaddress.ip_address(ip_str)
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid IP Format",
                f"'{ip_str}' is not a valid IPv4/IPv6 address or CIDR notation."
            )
            return

        rule = {
            "id": f"rule_{int(time.time() * 1000)}",
            "active": True,
            "pattern": ip_str,
            "action": action,
            "note": note,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.rules.append(rule)
        self.ui.editRuleIp.clear()
        self.ui.editRuleNote.clear()
        self._refresh_rules_table()
        self.save_settings()

    def _on_delete_selected_rule(self):
        row = self.ui.tableRules.currentRow()
        if 0 <= row < len(self.rules):
            del self.rules[row]
            self._refresh_rules_table()
            self.save_settings()

    def _on_clear_all_rules(self):
        if not self.rules:
            return
        res = QMessageBox.question(
            self,
            "Clear Rules",
            "Are you sure you want to remove all access control rules?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self.rules.clear()
            self._refresh_rules_table()
            self.save_settings()

    def _on_clear_audit_log(self):
        db.set_setting("ip_audit_log", "[]")
        self._refresh_audit_log()

    def _refresh_rules_table(self):
        self.ui.tableRules.setRowCount(0)
        for idx, rule in enumerate(self.rules):
            self.ui.tableRules.insertRow(idx)

            # Active status checkbox
            status_item = QTableWidgetItem("Active" if rule.get("active", True) else "Disabled")
            status_item.setTextAlignment(Qt.AlignCenter)
            self.ui.tableRules.setItem(idx, 0, status_item)

            # Pattern
            pattern_item = QTableWidgetItem(rule.get("pattern", ""))
            self.ui.tableRules.setItem(idx, 1, pattern_item)

            # Action
            action_str = rule.get("action", "ALLOW")
            action_item = QTableWidgetItem(action_str)
            action_item.setTextAlignment(Qt.AlignCenter)
            if action_str == "ALLOW":
                action_item.setForeground(Qt.darkGreen)
            else:
                action_item.setForeground(Qt.red)
            self.ui.tableRules.setItem(idx, 2, action_item)

            # Note
            note_item = QTableWidgetItem(rule.get("note", ""))
            self.ui.tableRules.setItem(idx, 3, note_item)

            # Delete button
            btn_del = QPushButton("Delete")
            btn_del.setStyleSheet("color: #DC3545; font-size: 10px; padding: 2px 6px;")
            btn_del.clicked.connect(lambda checked=False, r_idx=idx: self._delete_rule_by_index(r_idx))
            self.ui.tableRules.setCellWidget(idx, 4, btn_del)

        self.ui.lblRuleCount.setText(f"Total Rules: {len(self.rules)}")

    def _delete_rule_by_index(self, index: int):
        if 0 <= index < len(self.rules):
            del self.rules[index]
            self._refresh_rules_table()
            self.save_settings()

    def _refresh_audit_log(self):
        raw = db.get_setting("ip_audit_log", "[]")
        try:
            logs = json.loads(raw)
        except Exception:
            logs = []

        self.ui.tableAuditLog.setRowCount(0)
        for idx, log in enumerate(reversed(logs[-50:])):
            self.ui.tableAuditLog.insertRow(idx)
            self.ui.tableAuditLog.setItem(idx, 0, QTableWidgetItem(log.get("time", "")))
            self.ui.tableAuditLog.setItem(idx, 1, QTableWidgetItem(log.get("ip", "")))

            res_item = QTableWidgetItem(log.get("result", ""))
            if log.get("result") == "ALLOWED":
                res_item.setForeground(Qt.darkGreen)
            else:
                res_item.setForeground(Qt.red)
            self.ui.tableAuditLog.setItem(idx, 2, res_item)
            self.ui.tableAuditLog.setItem(idx, 3, QTableWidgetItem(log.get("rule", "Default Policy")))
