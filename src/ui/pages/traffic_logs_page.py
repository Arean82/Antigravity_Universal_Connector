"""Native PySide6 Traffic Logs / Proxy Monitor Page.
Directly loads traffic_logs.ui dynamically via QUiLoader (Zero UIC compilation).
Features QLCDNumber metric display cards and real-time proxy traffic monitor.
"""

from __future__ import annotations

import os
import time
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QFile, Qt, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLCDNumber,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from src.core.database import db


class TrafficLogsPage(QWidget):
    """
    Traffic Logs / Proxy Monitor page loaded dynamically from src/ui/forms/traffic_logs.ui.
    Presents requests, status breakdown, latency, and client IPs with QLCDNumber summary cards.
    """

    def __init__(self, bridge=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.bridge = bridge

        ui_file_path = os.path.join(
            os.path.dirname(__file__), "..", "forms", "traffic_logs.ui"
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

        # In-memory traffic cache for real-time inspection
        self.traffic_records: List[Dict[str, Any]] = []

        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_from_config)
        self.refresh_timer.start(3000)

    def _bind_widgets(self):
        # QLCDNumber widgets
        self.val_total_requests: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valTotalRequests")
        self.val_success_rate: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valSuccessRate")
        self.val_active_connections: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valActiveConnections")
        self.val_blocked_requests: QLCDNumber = self.form_widget.findChild(QLCDNumber, "valBlockedRequests")

        # Controls
        self.edit_search: QLineEdit = self.form_widget.findChild(QLineEdit, "editSearch")
        self.combo_method: QComboBox = self.form_widget.findChild(QComboBox, "comboMethod")
        self.combo_status: QComboBox = self.form_widget.findChild(QComboBox, "comboStatus")
        self.check_auto_refresh: QCheckBox = self.form_widget.findChild(QCheckBox, "checkAutoRefresh")
        self.btn_refresh: QPushButton = self.form_widget.findChild(QPushButton, "btnRefresh")
        self.btn_clear_logs: QPushButton = self.form_widget.findChild(QPushButton, "btnClearLogs")

        # Table & Footer
        self.table_logs: QTableWidget = self.form_widget.findChild(QTableWidget, "tableLogs")
        self.lbl_log_count: QLabel = self.form_widget.findChild(QLabel, "lblLogCount")

    def _setup_table_headers(self):
        if self.table_logs:
            header = self.table_logs.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

    def _connect_signals(self):
        if self.btn_refresh:
            self.btn_refresh.clicked.connect(self.load_from_config)
        if self.btn_clear_logs:
            self.btn_clear_logs.clicked.connect(self._clear_logs)
        if self.edit_search:
            self.edit_search.textChanged.connect(self._filter_table)
        if self.combo_method:
            self.combo_method.currentIndexChanged.connect(self._filter_table)
        if self.combo_status:
            self.combo_status.currentIndexChanged.connect(self._filter_table)
        if self.check_auto_refresh:
            self.check_auto_refresh.toggled.connect(self._on_auto_refresh_toggled)

    def _on_auto_refresh_toggled(self, checked: bool):
        if checked:
            self.refresh_timer.start(3000)
        else:
            self.refresh_timer.stop()

    def _clear_logs(self):
        self.traffic_records.clear()
        self._filter_table()

    def add_traffic_record(self, method: str, path: str, model: str, client_ip: str, status: int, duration_ms: float):
        record = {
            "time": time.strftime("%H:%M:%S"),
            "method": method,
            "path": path,
            "model": model or "-",
            "client_ip": client_ip,
            "status": status,
            "duration": f"{duration_ms:.1f}",
        }
        self.traffic_records.insert(0, record)
        if len(self.traffic_records) > 500:
            self.traffic_records.pop()
        self._filter_table()

    def load_from_config(self):
        """Refreshes summary statistics and table rows."""
        total = len(self.traffic_records)
        successful = sum(1 for r in self.traffic_records if 200 <= r.get("status", 200) < 400)
        blocked = sum(1 for r in self.traffic_records if r.get("status", 200) >= 400)
        success_rate = (successful / total * 100.0) if total > 0 else 100.0

        active_conn = 0
        if self.bridge and hasattr(self.bridge, "proxy_server") and self.bridge.proxy_server:
            active_conn = 1

        if self.val_total_requests:
            self.val_total_requests.display(total)
        if self.val_success_rate:
            self.val_success_rate.display(f"{success_rate:.1f}")
        if self.val_active_connections:
            self.val_active_connections.display(active_conn)
        if self.val_blocked_requests:
            self.val_blocked_requests.display(blocked)

        self._filter_table()

    def _filter_table(self):
        search_query = self.edit_search.text().strip().lower() if self.edit_search else ""
        method_filter = self.combo_method.currentText() if self.combo_method else "All Methods"
        status_filter = self.combo_status.currentText() if self.combo_status else "All Status"

        filtered = []
        for r in self.traffic_records:
            if search_query:
                match = (
                    search_query in r.get("client_ip", "").lower()
                    or search_query in r.get("path", "").lower()
                    or search_query in r.get("model", "").lower()
                )
                if not match:
                    continue

            if method_filter != "All Methods" and r.get("method") != method_filter:
                continue

            status = r.get("status", 200)
            if status_filter == "2xx Success" and not (200 <= status < 300):
                continue
            if status_filter == "4xx Errors" and not (400 <= status < 500):
                continue
            if status_filter == "5xx Server Errors" and not (500 <= status < 600):
                continue

            filtered.append(r)

        self._render_table(filtered)

    def _render_table(self, records: List[Dict[str, Any]]):
        if not self.table_logs:
            return

        self.table_logs.setRowCount(len(records))
        for row, r in enumerate(records):
            item_time = QTableWidgetItem(r.get("time", ""))
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_method = QTableWidgetItem(r.get("method", ""))
            item_method.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_path = QTableWidgetItem(r.get("path", ""))

            item_model = QTableWidgetItem(r.get("model", ""))
            item_model.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_ip = QTableWidgetItem(r.get("client_ip", ""))
            item_ip.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_status = QTableWidgetItem(str(r.get("status", "")))
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_dur = QTableWidgetItem(str(r.get("duration", "")))
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.table_logs.setItem(row, 0, item_time)
            self.table_logs.setItem(row, 1, item_method)
            self.table_logs.setItem(row, 2, item_path)
            self.table_logs.setItem(row, 3, item_model)
            self.table_logs.setItem(row, 4, item_ip)
            self.table_logs.setItem(row, 5, item_status)
            self.table_logs.setItem(row, 6, item_dur)

        if self.lbl_log_count:
            self.lbl_log_count.setText(f"{len(records)} requests matching current filter ({len(self.traffic_records)} total)")
