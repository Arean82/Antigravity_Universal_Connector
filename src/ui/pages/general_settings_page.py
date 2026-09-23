import os
import json
from typing import Dict, Any, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFileDialog
from PySide6.QtCore import QFile, Signal, QTimer
from PySide6.QtUiTools import QUiLoader

from src.core.database import db

class GeneralSettingsPage(QWidget):
    """
    100% Native PySide6 General Settings Controller.
    Renders general_settings.ui directly via QUiLoader (zero intermediate .py files).
    Binds directly to BackendBridge and SQLite app_config.
    """
    settingsSaved = Signal()

    LANGUAGES = [
        ("English", "en"),
        ("Español", "es"),
        ("Français", "fr"),
        ("Deutsch", "de"),
        ("日本語", "ja"),
        ("한국어", "ko"),
        ("Русский", "ru"),
        ("Português", "pt"),
        ("Tiếng Việt", "vi"),
        ("Türkçe", "tr"),
        ("العربية", "ar"),
        ("Bahasa Melayu", "my"),
    ]

    THEMES = [
        ("System Default", "system"),
        ("Light Theme", "light"),
        ("Dark Theme", "dark"),
    ]

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        # Direct QUiLoader loading
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "general_settings.ui")
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
        self.ui.btnBrowseExportPath.clicked.connect(self._browse_export_path)
        self.ui.btnSaveSettings.clicked.connect(self.save_settings)

    def load_from_config(self):
        if self.bridge:
            cfg = self.bridge.config
        else:
            saved = db.get_setting("app_config")
            cfg = json.loads(saved) if saved else {}

        # Language
        current_lang = cfg.get("language", "en")
        for i, (label, code) in enumerate(self.LANGUAGES):
            if code == current_lang:
                self.ui.comboLanguage.setCurrentIndex(i)
                break

        # Theme
        current_theme = cfg.get("theme", "system")
        for i, (label, val) in enumerate(self.THEMES):
            if val == current_theme:
                self.ui.comboTheme.setCurrentIndex(i)
                break

        # Startup & updates
        self.ui.chkAutoLaunch.setChecked(bool(cfg.get("auto_launch", False)))
        self.ui.chkAutoCheckUpdate.setChecked(bool(cfg.get("auto_check_update", False)))
        self.ui.spinUpdateInterval.setValue(int(cfg.get("update_check_interval", 24)))

        # Export path
        self.ui.editDefaultExportPath.setText(cfg.get("default_export_path") or "")

    def save_settings(self):
        cfg = self.bridge.config if self.bridge else {}

        lang_idx = self.ui.comboLanguage.currentIndex()
        if 0 <= lang_idx < len(self.LANGUAGES):
            cfg["language"] = self.LANGUAGES[lang_idx][1]

        theme_idx = self.ui.comboTheme.currentIndex()
        if 0 <= theme_idx < len(self.THEMES):
            cfg["theme"] = self.THEMES[theme_idx][1]

        cfg["auto_launch"] = self.ui.chkAutoLaunch.isChecked()
        cfg["auto_check_update"] = self.ui.chkAutoCheckUpdate.isChecked()
        cfg["update_check_interval"] = self.ui.spinUpdateInterval.value()
        cfg["default_export_path"] = self.ui.editDefaultExportPath.text().strip() or None

        if self.bridge:
            self.bridge.save_config(json.dumps(cfg))
        else:
            db.set_setting("app_config", json.dumps(cfg))

        self.ui.lblSaveStatus.setText("Settings saved successfully to SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #28A745; font-weight: bold;")
        QTimer.singleShot(3000, lambda: self._reset_save_status())
        self.settingsSaved.emit()

    def _reset_save_status(self):
        self.ui.lblSaveStatus.setText("All general preferences are saved to local SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #6C757D; font-style: italic;")

    def _browse_export_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Export Directory")
        if folder:
            self.ui.editDefaultExportPath.setText(folder)
