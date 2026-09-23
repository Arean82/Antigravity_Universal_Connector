import os
import sys
import json
import subprocess
from typing import Dict, Any, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PySide6.QtCore import QFile, Signal, Slot, QTimer
from PySide6.QtUiTools import QUiLoader

from src.core.database import db

class AdvancedSettingsPage(QWidget):
    """
    100% Native PySide6 Advanced Settings Controller.
    Renders advanced_settings.ui directly via QUiLoader (zero intermediate .py files).
    Binds directly to BackendBridge and SQLite app_config.
    """
    settingsSaved = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        # Direct QUiLoader loading
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "advanced_settings.ui")
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

        self._init_data_directory_display()
        self._connect_signals()
        self.load_from_config()

    def _init_data_directory_display(self):
        data_dir = os.path.expanduser("~/.antigravity_tools")
        self.ui.lblDataDirPath.setText(data_dir)

    def _connect_signals(self):
        self.ui.btnBrowseAntigravity.clicked.connect(lambda: self._browse_file("editAntigravityPath"))
        self.ui.btnBrowseIde.clicked.connect(lambda: self._browse_file("editIdePath"))
        self.ui.btnBrowseCli.clicked.connect(lambda: self._browse_file("editCliPath"))
        self.ui.btnDetectAntigravity.clicked.connect(self._detect_antigravity)
        self.ui.btnDetectIde.clicked.connect(self._detect_ide)
        self.ui.btnDetectCli.clicked.connect(self._detect_cli)
        self.ui.btnOpenDataDir.clicked.connect(self._open_data_dir)
        self.ui.btnClearCache.clicked.connect(self._clear_cache)
        self.ui.btnImportVscdb.clicked.connect(self._import_vscdb)
        self.ui.btnSaveSettings.clicked.connect(self.save_settings)

    def load_from_config(self):
        if self.bridge:
            cfg = self.bridge.config
        else:
            saved = db.get_setting("app_config")
            cfg = json.loads(saved) if saved else {}

        # Executables
        self.ui.editAntigravityPath.setText(cfg.get("antigravity_executable") or "")
        self.ui.editIdePath.setText(cfg.get("antigravity_ide_executable") or "")
        self.ui.editCliPath.setText(cfg.get("antigravity_cli_executable") or "")
        self.ui.editExtraArgs.setText(cfg.get("antigravity_args") or "")

        # Circuit breaker
        cb = cfg.get("circuit_breaker", {})
        self.ui.chkCircuitBreaker.setChecked(bool(cb.get("enabled", True)))
        self.ui.chkLockOnZeroQuota.setChecked(bool(cb.get("lock_on_zero_quota", False)))

        steps = cb.get("backoff_steps", [60, 300, 1800, 7200])
        if isinstance(steps, list):
            self.ui.editBackoffSteps.setText(", ".join(str(s) for s in steps))
        else:
            self.ui.editBackoffSteps.setText("60, 300, 1800, 7200")

    def save_settings(self):
        cfg = self.bridge.config if self.bridge else {}

        cfg["antigravity_executable"] = self.ui.editAntigravityPath.text().strip() or None
        cfg["antigravity_ide_executable"] = self.ui.editIdePath.text().strip() or None
        cfg["antigravity_cli_executable"] = self.ui.editCliPath.text().strip() or None
        cfg["antigravity_args"] = self.ui.editExtraArgs.text().strip() or None

        # Parse backoff steps
        raw_steps = self.ui.editBackoffSteps.text()
        steps_list = []
        for part in raw_steps.split(","):
            part = part.strip()
            if part.isdigit():
                steps_list.append(int(part))
        if not steps_list:
            steps_list = [60, 300, 1800, 7200]

        cfg.setdefault("circuit_breaker", {})
        cfg["circuit_breaker"]["enabled"] = self.ui.chkCircuitBreaker.isChecked()
        cfg["circuit_breaker"]["lock_on_zero_quota"] = self.ui.chkLockOnZeroQuota.isChecked()
        cfg["circuit_breaker"]["backoff_steps"] = steps_list

        if self.bridge:
            self.bridge.save_config(json.dumps(cfg))
        else:
            db.set_setting("app_config", json.dumps(cfg))

        self.ui.lblSaveStatus.setText("Settings saved successfully to SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #28A745; font-weight: bold;")
        QTimer.singleShot(3000, lambda: self._reset_save_status())
        self.settingsSaved.emit()

    def _reset_save_status(self):
        self.ui.lblSaveStatus.setText("All advanced configurations are stored in local SQLite.")
        self.ui.lblSaveStatus.setStyleSheet("color: #6C757D; font-style: italic;")

    def _browse_file(self, target_widget_name: str):
        widget = getattr(self.ui, target_widget_name, None)
        if not widget:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Executable Binary",
            "",
            "Executable Files (*.exe *.cmd *.bat);;All Files (*)"
        )
        if file_path:
            widget.setText(file_path)

    def _detect_antigravity(self):
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Antigravity\Antigravity.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe"),
        ]
        found = next((c for c in candidates if os.path.exists(c)), None)
        if found:
            self.ui.editAntigravityPath.setText(found)
            QMessageBox.information(self, "Detection", f"Found Antigravity at:\n{found}")
        else:
            QMessageBox.warning(self, "Detection", "Could not automatically locate Antigravity executable.")

    def _detect_ide(self):
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Antigravity IDE\Antigravity IDE.exe"),
        ]
        found = next((c for c in candidates if os.path.exists(c)), None)
        if found:
            self.ui.editIdePath.setText(found)
            QMessageBox.information(self, "Detection", f"Found Antigravity IDE at:\n{found}")
        else:
            QMessageBox.warning(self, "Detection", "Could not automatically locate Antigravity IDE executable.")

    def _detect_cli(self):
        import shutil
        found = shutil.which("agy") or shutil.which("antigravity")
        if found:
            self.ui.editCliPath.setText(found)
            QMessageBox.information(self, "Detection", f"Found CLI at:\n{found}")
        else:
            QMessageBox.warning(self, "Detection", "Could not automatically locate CLI in system PATH.")

    def _open_data_dir(self):
        data_dir = os.path.expanduser("~/.antigravity_tools")
        os.makedirs(data_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(data_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", data_dir])
        else:
            subprocess.Popen(["xdg-open", data_dir])

    def _clear_cache(self):
        reply = QMessageBox.question(
            self,
            "Clear Antigravity Cache",
            "Are you sure you want to clear temporary cache files? Active sessions will not be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Perform cache cleanup
            cache_dir = os.path.expanduser("~/.antigravity_tools/cache")
            if os.path.exists(cache_dir):
                import shutil
                try:
                    shutil.rmtree(cache_dir)
                    os.makedirs(cache_dir, exist_ok=True)
                except Exception as e:
                    QMessageBox.warning(self, "Cache Clean Error", str(e))
                    return
            QMessageBox.information(self, "Cache Cleared", "Temporary cache has been cleared successfully.")

    def _import_vscdb(self):
        if self.bridge:
            res = self.bridge.import_from_vscdb(lambda r: None)
            QMessageBox.information(self, "Import VSCDB", f"Import initiated:\n{res}")
        else:
            QMessageBox.information(self, "Import VSCDB", "Backend bridge is not connected.")
