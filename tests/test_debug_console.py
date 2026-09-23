import sys
import unittest
from PySide6.QtWidgets import QApplication
from src.ui.pages.debug_console_page import DebugConsolePage

class TestDebugConsolePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_instantiation_and_logging(self):
        page = DebugConsolePage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.lblTitle.text(), "Debug Console")

        # Test adding logs
        page.add_log("INFO", "test::core", "This is an info test log", {"key": "value"})
        page.add_log("ERROR", "test::api", "This is an error test log")
        page.add_log("WARN", "test::proxy", "This is a warning test log")
        page.add_log("DEBUG", "test::worker", "This is a debug test log")

        self.assertEqual(len(page._logs), 5) # 1 initial startup log + 4 added
        self.assertEqual(page.ui.tableLogs.rowCount(), 5)

        # Test level filtering
        page._on_filter_toggled("ERROR", False)
        # Should now hide the ERROR row
        visible_levels = [page.ui.tableLogs.item(r, 1).text() for r in range(page.ui.tableLogs.rowCount())]
        self.assertNotIn("ERROR", visible_levels)
        self.assertIn("INFO", visible_levels)

        # Re-enable ERROR
        page._on_filter_toggled("ERROR", True)
        visible_levels = [page.ui.tableLogs.item(r, 1).text() for r in range(page.ui.tableLogs.rowCount())]
        self.assertIn("ERROR", visible_levels)

        # Test search filtering
        page._on_search_text_changed("proxy")
        self.assertEqual(page.ui.tableLogs.rowCount(), 1)
        self.assertEqual(page.ui.tableLogs.item(0, 2).text(), "test::proxy")

        # Clear search
        page._on_search_text_changed("")
        self.assertEqual(page.ui.tableLogs.rowCount(), 5)

        # Test selection and detail inspector
        page.ui.tableLogs.selectRow(0)
        page._on_row_selected()
        detail_text = page.ui.textLogDetail.toPlainText()
        self.assertIn("=== LOG ENTRY DETAILS ===", detail_text)

        # Test clear
        page.clear_logs()
        self.assertEqual(len(page._logs), 0)
        self.assertEqual(page.ui.tableLogs.rowCount(), 0)
        self.assertEqual(page.ui.textLogDetail.toPlainText(), "")

if __name__ == "__main__":
    unittest.main()
