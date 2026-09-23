import os
import json
import secrets
from typing import Dict, Any, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QMessageBox
from PySide6.QtCore import QFile, Signal, Slot, QTimer
from PySide6.QtUiTools import QUiLoader

from src.core.database import db

class ProxySettingsPage(QWidget):
    """
    100% Native PySide6 Proxy Settings Controller.
    Renders proxy_settings.ui directly via QUiLoader (zero intermediate .py files).
    Binds directly to BackendBridge and SQLite app_config.
    """
    settingsSaved = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        # Direct QUiLoader loading
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "proxy_settings.ui")
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

        self._show_key = False
        self._connect_signals()
        self.load_from_config()
        self._update_status_ui()

        # Hook to bridge status updates if available
        if self.bridge:
            self.bridge.proxyStatusChanged.connect(self._on_proxy_status_changed)

    def _connect_signals(self):
        self.ui.btnStartService.clicked.connect(self._start_service)
        self.ui.btnStopService.clicked.connect(self._stop_service)
        self.ui.btnRestartService.clicked.connect(self._restart_service)
        self.ui.btnToggleShowKey.clicked.connect(self._toggle_show_key)
        self.ui.btnGenerateKey.clicked.connect(self._generate_key)
        self.ui.btnSaveSettings.clicked.connect(self.save_settings)

    def load_from_config(self):
        if self.bridge:
            cfg = self.bridge.config
        else:
            saved = db.get_setting("app_config")
            cfg = json.loads(saved) if saved else {}
        proxy = cfg.get("proxy", {})

        # Port
        port = proxy.get("port", 8045)
        self.ui.spinPort.setValue(int(port))

        # Allow LAN
        self.ui.chkAllowLan.setChecked(bool(proxy.get("allow_lan_access", False)))

        # Auto start
        self.ui.chkAutoStart.setChecked(bool(proxy.get("auto_start", False)))

        # Auth mode
        auth_mode = proxy.get("auth_mode", "off")
        self.ui.comboAuthMode.setCurrentIndex(1 if auth_mode == "bearer" else 0)

        # API key
        api_key = proxy.get("api_key", "sk-antigravity-local")
        self.ui.editApiKey.setText(api_key or "sk-antigravity-local")

        # Request timeout
        timeout = proxy.get("request_timeout", 60)
        self.ui.spinTimeout.setValue(int(timeout))

        # Upstream proxy
        upstream = proxy.get("upstream_proxy", {})
        self.ui.chkUpstreamEnabled.setChecked(bool(upstream.get("enabled", False)))
        self.ui.editUpstreamUrl.setText(upstream.get("url", ""))

        # Logging policy
        self.ui.chkEnableLogging.setChecked(bool(proxy.get("enable_logging", True)))
        retention = proxy.get("log_retention", {})
        self.ui.spinLogMaxAge.setValue(int(retention.get("max_body_age_hours", 24)))

    def save_settings(self):
        cfg = self.bridge.config if self.bridge else {}
        proxy = cfg.setdefault("proxy", {})

        proxy["port"] = self.ui.spinPort.value()
        proxy["allow_lan_access"] = self.ui.chkAllowLan.isChecked()
        proxy["auto_start"] = self.ui.chkAutoStart.isChecked()
        proxy["auth_mode"] = "bearer" if self.ui.comboAuthMode.currentIndex() == 1 else "off"
        proxy["api_key"] = self.ui.editApiKey.text().strip()
        proxy["request_timeout"] = self.ui.spinTimeout.value()

        proxy.setdefault("upstream_proxy", {})
        proxy["upstream_proxy"]["enabled"] = self.ui.chkUpstreamEnabled.isChecked()
        proxy["upstream_proxy"]["url"] = self.ui.editUpstreamUrl.text().strip()

        proxy["enable_logging"] = self.ui.chkEnableLogging.isChecked()
        proxy.setdefault("log_retention", {})
        proxy["log_retention"]["max_body_age_hours"] = self.ui.spinLogMaxAge.value()

        if self.bridge:
            self.bridge.save_config(json.dumps(cfg))
        else:
            db.set_setting("app_config", json.dumps(cfg))

        self.ui.lblSaveStatus.setText("Settings saved successfully to SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #28A745; font-weight: bold;")
        QTimer.singleShot(3000, lambda: self._reset_save_status())
        self.settingsSaved.emit()

    def _reset_save_status(self):
        self.ui.lblSaveStatus.setText("All proxy settings are synchronized with local SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #6C757D; font-style: italic;")

    def _toggle_show_key(self):
        self._show_key = not self._show_key
        if self._show_key:
            self.ui.editApiKey.setEchoMode(QLineEdit.Normal)
            self.ui.btnToggleShowKey.setText("Hide")
        else:
            self.ui.editApiKey.setEchoMode(QLineEdit.Password)
            self.ui.btnToggleShowKey.setText("Show")

    def _generate_key(self):
        new_key = f"sk-{secrets.token_hex(16)}"
        self.ui.editApiKey.setText(new_key)
        self.ui.editApiKey.setEchoMode(QLineEdit.Normal)
        self._show_key = True
        self.ui.btnToggleShowKey.setText("Hide")

    def _start_service(self):
        port = self.ui.spinPort.value()
        if self.bridge:
            self.bridge.start_proxy(port)
            self._update_status_ui(running=True, port=port)

    def _stop_service(self):
        if self.bridge:
            self.bridge.stop_proxy()
            self._update_status_ui(running=False)

    def _restart_service(self):
        self._stop_service()
        QTimer.singleShot(500, self._start_service)

    @Slot(bool, int)
    def _on_proxy_status_changed(self, running: bool, port: int):
        self._update_status_ui(running=running, port=port)

    def _update_status_ui(self, running: Optional[bool] = None, port: Optional[int] = None):
        if running is None and self.bridge:
            status_json = json.loads(self.bridge.get_proxy_status())
            running = status_json.get("running", False)
            port = status_json.get("port", self.ui.spinPort.value())
        elif running is None:
            running = False
            port = self.ui.spinPort.value()

        if running:
            self.ui.lblStatusIcon.setStyleSheet("background-color: #28A745; border-radius: 7px;")
            self.ui.lblStatusText.setText(f"Running on port {port}")
            self.ui.btnStartService.setEnabled(False)
            self.ui.btnStopService.setEnabled(True)
        else:
            self.ui.lblStatusIcon.setStyleSheet("background-color: #DC3545; border-radius: 7px;")
            self.ui.lblStatusText.setText("Proxy Service Stopped")
            self.ui.btnStartService.setEnabled(True)
            self.ui.btnStopService.setEnabled(False)
