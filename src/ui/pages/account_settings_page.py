import os
import json
from typing import Dict, Any, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import QFile, Signal, QTimer
from PySide6.QtUiTools import QUiLoader

from src.core.database import db

class AccountSettingsPage(QWidget):
    """
    100% Native PySide6 Account Settings Controller.
    Renders account_settings.ui directly via QUiLoader (zero intermediate .py files).
    Binds directly to BackendBridge and SQLite app_config.
    """
    settingsSaved = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        # Direct QUiLoader loading
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "account_settings.ui")
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

        self._connect_signals()
        self.load_from_config()

    def _connect_signals(self):
        self.ui.btnSaveSettings.clicked.connect(self.save_settings)

    def load_from_config(self):
        if self.bridge:
            cfg = self.bridge.config
        else:
            saved = db.get_setting("app_config")
            cfg = json.loads(saved) if saved else {}

        # Auto refresh
        self.ui.chkAutoRefresh.setChecked(bool(cfg.get("auto_refresh", True)))
        self.ui.spinRefreshInterval.setValue(int(cfg.get("refresh_interval", 15)))

        # Auto sync
        self.ui.chkAutoSync.setChecked(bool(cfg.get("auto_sync", False)))
        self.ui.spinSyncInterval.setValue(int(cfg.get("sync_interval", 5)))

        # Warmup
        warmup = cfg.get("scheduled_warmup", {})
        self.ui.chkScheduledWarmup.setChecked(bool(warmup.get("enabled", False)))

        # Quota protection
        protection = cfg.get("quota_protection", {})
        self.ui.chkQuotaProtection.setChecked(bool(protection.get("enabled", False)))
        self.ui.spinQuotaThreshold.setValue(int(protection.get("threshold_percentage", 10)))

    def save_settings(self):
        cfg = self.bridge.config if self.bridge else {}

        cfg["auto_refresh"] = self.ui.chkAutoRefresh.isChecked()
        cfg["refresh_interval"] = self.ui.spinRefreshInterval.value()
        cfg["auto_sync"] = self.ui.chkAutoSync.isChecked()
        cfg["sync_interval"] = self.ui.spinSyncInterval.value()

        cfg.setdefault("scheduled_warmup", {})
        cfg["scheduled_warmup"]["enabled"] = self.ui.chkScheduledWarmup.isChecked()

        cfg.setdefault("quota_protection", {})
        cfg["quota_protection"]["enabled"] = self.ui.chkQuotaProtection.isChecked()
        cfg["quota_protection"]["threshold_percentage"] = self.ui.spinQuotaThreshold.value()

        if self.bridge:
            self.bridge.save_config(json.dumps(cfg))
        else:
            db.set_setting("app_config", json.dumps(cfg))

        self.ui.lblSaveStatus.setText("Settings saved successfully to SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #28A745; font-weight: bold;")
        QTimer.singleShot(3000, lambda: self._reset_save_status())
        self.settingsSaved.emit()

    def _reset_save_status(self):
        self.ui.lblSaveStatus.setText("All account preferences are stored in local SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #6C757D; font-style: italic;")
