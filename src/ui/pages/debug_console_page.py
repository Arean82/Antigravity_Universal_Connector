import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QFile
from PySide6.QtUiTools import QUiLoader

class DebugConsolePage(QWidget):
    """
    100% Direct Native PySide6 Debug Console.
    Renders debug_console.ui DIRECTLY via QUiLoader at runtime.
    No intermediate generated Python UI files.
    """
    logReceived = Signal(dict)

    LEVEL_COLORS = {
        "ERROR": "#DC3545",
        "WARN": "#D39E00",
        "INFO": "#0D6EFD",
        "DEBUG": "#6C757D",
        "TRACE": "#6F42C1"
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # Direct loading of the .ui file using QUiLoader
        ui_path = os.path.join(os.path.dirname(__file__), "..", "forms", "debug_console.ui")
        ui_file = QFile(ui_path)
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Cannot open UI file: {ui_path}")

        loader = QUiLoader()
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        if self.ui is None:
            raise RuntimeError(f"Failed to load UI from {ui_path}: {loader.errorString()}")

        # Put loaded UI into this widget's layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        self._logs: List[Dict[str, Any]] = []
        self._filtered_indices: List[int] = []
        self._active_filters = {"ERROR", "WARN", "INFO", "DEBUG"}
        self._search_query = ""
        self._auto_scroll = True
        self._is_enabled = True

        self._setup_table()
        self._connect_signals()
        self.logReceived.connect(self._on_log_received)

        # Initial ready log
        self.add_log(
            level="INFO",
            target="system::console",
            message="Native PySide6 Debug Console directly loaded from debug_console.ui.",
            fields={"runtime": "PySide6", "loader": "QUiLoader", "ui_file": "debug_console.ui"}
        )

    def _setup_table(self):
        table = self.ui.tableLogs
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(26)
        table.verticalHeader().setVisible(False)

        # Set splitter proportions (75% table, 25% details)
        self.ui.splitterConsole.setSizes([520, 180])

    def _connect_signals(self):
        self.ui.chkEnableCapture.toggled.connect(self._on_capture_toggled)
        self.ui.btnFilterError.toggled.connect(lambda c: self._on_filter_toggled("ERROR", c))
        self.ui.btnFilterWarn.toggled.connect(lambda c: self._on_filter_toggled("WARN", c))
        self.ui.btnFilterInfo.toggled.connect(lambda c: self._on_filter_toggled("INFO", c))
        self.ui.btnFilterDebug.toggled.connect(lambda c: self._on_filter_toggled("DEBUG", c))
        self.ui.editSearch.textChanged.connect(self._on_search_text_changed)
        self.ui.btnAutoScroll.toggled.connect(self._on_auto_scroll_toggled)
        self.ui.btnClear.clicked.connect(self.clear_logs)
        self.ui.btnExport.clicked.connect(self._on_export_clicked)
        self.ui.tableLogs.itemSelectionChanged.connect(self._on_row_selected)

    def add_log(self, level: str, target: str, message: str, fields: Optional[Dict[str, Any]] = None):
        """Thread-safe entrypoint to append a log message."""
        if not self._is_enabled:
            return

        entry = {
            "timestamp": time.time(),
            "time_str": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": level.upper(),
            "target": target,
            "message": message,
            "fields": fields or {}
        }
        self.logReceived.emit(entry)

    @Slot(dict)
    def _on_log_received(self, entry: dict):
        self._logs.append(entry)
        total = len(self._logs)
        self.ui.lblTotalLogs.setText(f"Total Logs: {total}")

        if self._matches_filter(entry):
            row_idx = len(self._logs) - 1
            self._append_table_row(entry, row_idx)
            self._filtered_indices.append(row_idx)
            self.ui.lblVisibleLogs.setText(f"Showing: {len(self._filtered_indices)}")

            if self._auto_scroll:
                self.ui.tableLogs.scrollToBottom()

    def _matches_filter(self, entry: dict) -> bool:
        lvl = entry.get("level", "INFO")
        if lvl not in self._active_filters:
            return False

        if self._search_query:
            q = self._search_query.lower()
            msg = entry.get("message", "").lower()
            target = entry.get("target", "").lower()
            if q not in msg and q not in target:
                return False

        return True

    def _append_table_row(self, entry: dict, raw_idx: int):
        from PySide6.QtGui import QBrush, QColor
        table = self.ui.tableLogs
        row = table.rowCount()
        table.insertRow(row)

        item_time = QTableWidgetItem(entry["time_str"])
        item_time.setForeground(QBrush(QColor("#6C757D")))
        item_time.setTextAlignment(Qt.AlignCenter)
        item_time.setData(Qt.UserRole, raw_idx)

        lvl = entry["level"]
        item_level = QTableWidgetItem(lvl)
        lvl_color = self.LEVEL_COLORS.get(lvl, "#495057")
        item_level.setForeground(QBrush(QColor(lvl_color)))
        font = item_level.font()
        font.setBold(True)
        item_level.setFont(font)
        item_level.setTextAlignment(Qt.AlignCenter)

        item_target = QTableWidgetItem(entry["target"])
        item_target.setForeground(QBrush(QColor("#495057")))

        item_msg = QTableWidgetItem(entry["message"])
        item_msg.setForeground(QBrush(QColor("#212529")))

        table.setItem(row, 0, item_time)
        table.setItem(row, 1, item_level)
        table.setItem(row, 2, item_target)
        table.setItem(row, 3, item_msg)

    def _repopulate_table(self):
        table = self.ui.tableLogs
        table.setRowCount(0)
        self._filtered_indices.clear()

        for idx, entry in enumerate(self._logs):
            if self._matches_filter(entry):
                self._append_table_row(entry, idx)
                self._filtered_indices.append(idx)

        self.ui.lblVisibleLogs.setText(f"Showing: {len(self._filtered_indices)}")
        if self._auto_scroll:
            table.scrollToBottom()

    def _on_filter_toggled(self, level: str, checked: bool):
        if checked:
            self._active_filters.add(level)
        else:
            self._active_filters.discard(level)
        self._repopulate_table()

    def _on_search_text_changed(self, text: str):
        self._search_query = text.strip()
        self._repopulate_table()

    def _on_auto_scroll_toggled(self, checked: bool):
        self._auto_scroll = checked
        if checked:
            self.ui.btnAutoScroll.setText("Auto-Scroll: ON")
            self.ui.tableLogs.scrollToBottom()
        else:
            self.ui.btnAutoScroll.setText("Auto-Scroll: OFF")

    def _on_capture_toggled(self, checked: bool):
        self._is_enabled = checked
        status_text = "Logging Enabled" if checked else "Logging Paused"
        self.ui.lblStatusNotice.setText(status_text)

    def _on_row_selected(self):
        selected = self.ui.tableLogs.selectedItems()
        if not selected:
            self.ui.textLogDetail.clear()
            return

        row = selected[0].row()
        item_time = self.ui.tableLogs.item(row, 0)
        if not item_time:
            return

        raw_idx = item_time.data(Qt.UserRole)
        if raw_idx is not None and 0 <= raw_idx < len(self._logs):
            entry = self._logs[raw_idx]
            detail_text = (
                f"=== LOG ENTRY DETAILS ===\n"
                f"Timestamp: {entry['time_str']} ({datetime.fromtimestamp(entry['timestamp']).isoformat()})\n"
                f"Level:     {entry['level']}\n"
                f"Target:    {entry['target']}\n"
                f"Message:   {entry['message']}\n"
            )
            if entry.get("fields"):
                detail_text += f"\n=== STRUCTURED PAYLOAD ===\n"
                detail_text += json.dumps(entry["fields"], indent=2, ensure_ascii=False)

            self.ui.textLogDetail.setPlainText(detail_text)

    def clear_logs(self):
        self._logs.clear()
        self._filtered_indices.clear()
        self.ui.tableLogs.setRowCount(0)
        self.ui.textLogDetail.clear()
        self.ui.lblTotalLogs.setText("Total Logs: 0")
        self.ui.lblVisibleLogs.setText("Showing: 0")

    def _on_export_clicked(self):
        if not self._logs:
            QMessageBox.information(self, "Export Logs", "No log entries to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Debug Logs",
            os.path.expanduser("~/antigravity_debug.log"),
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                for entry in self._logs:
                    f.write(f"[{entry['time_str']}] [{entry['level']}] [{entry['target']}] {entry['message']}\n")
                    if entry.get("fields"):
                        f.write(f"  Payload: {json.dumps(entry['fields'], ensure_ascii=False)}\n")
            QMessageBox.information(self, "Export Successful", f"Logs exported to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export logs: {e}")
