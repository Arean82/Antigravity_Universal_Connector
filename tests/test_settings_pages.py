import sys
import unittest
import json
from PySide6.QtWidgets import QApplication
from src.ui.pages.proxy_settings_page import ProxySettingsPage
from src.ui.pages.advanced_settings_page import AdvancedSettingsPage
from src.ui.pages.general_settings_page import GeneralSettingsPage
from src.ui.pages.account_settings_page import AccountSettingsPage
from src.ui.pages.debug_console_page import DebugConsolePage
from src.ui.browser_window import MainWindow

class TestNativeSettingsPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_general_settings_page_direct_ui(self):
        page = GeneralSettingsPage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.windowTitle(), "General Settings")

        # Test language, theme, startup values
        page.ui.comboLanguage.setCurrentIndex(0) # English
        page.ui.comboTheme.setCurrentIndex(1)    # Light Theme
        page.ui.chkAutoLaunch.setChecked(True)
        page.ui.editDefaultExportPath.setText(r"C:\Custom\Exports")
        page.save_settings()

        page.load_from_config()
        self.assertEqual(page.ui.comboLanguage.currentIndex(), 0)
        self.assertEqual(page.ui.comboTheme.currentIndex(), 1)
        self.assertTrue(page.ui.chkAutoLaunch.isChecked())
        self.assertEqual(page.ui.editDefaultExportPath.text(), r"C:\Custom\Exports")

    def test_account_settings_page_direct_ui(self):
        page = AccountSettingsPage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.windowTitle(), "Account Settings")

        # Test quota refresh and sync
        page.ui.chkAutoRefresh.setChecked(True)
        page.ui.spinRefreshInterval.setValue(25)
        page.ui.chkScheduledWarmup.setChecked(True)
        page.ui.spinQuotaThreshold.setValue(15)
        page.save_settings()

        page.load_from_config()
        self.assertTrue(page.ui.chkAutoRefresh.isChecked())
        self.assertEqual(page.ui.spinRefreshInterval.value(), 25)
        self.assertTrue(page.ui.chkScheduledWarmup.isChecked())
        self.assertEqual(page.ui.spinQuotaThreshold.value(), 15)

    def test_proxy_settings_page_direct_ui(self):
        page = ProxySettingsPage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.windowTitle(), "Proxy Settings")

        page.ui.spinPort.setValue(9090)
        page.ui.chkAllowLan.setChecked(True)
        page.ui.editApiKey.setText("sk-test-key-1234")
        page.save_settings()

        page.load_from_config()
        self.assertEqual(page.ui.spinPort.value(), 9090)
        self.assertTrue(page.ui.chkAllowLan.isChecked())
        self.assertEqual(page.ui.editApiKey.text(), "sk-test-key-1234")

    def test_advanced_settings_page_direct_ui(self):
        page = AdvancedSettingsPage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.windowTitle(), "Advanced Settings")

        page.ui.editAntigravityPath.setText(r"C:\Custom\Antigravity.exe")
        page.ui.chkLockOnZeroQuota.setChecked(True)
        page.ui.editBackoffSteps.setText("10, 20, 30")
        page.save_settings()

        page.load_from_config()
        self.assertEqual(page.ui.editAntigravityPath.text(), r"C:\Custom\Antigravity.exe")
        self.assertTrue(page.ui.chkLockOnZeroQuota.isChecked())
        self.assertEqual(page.ui.editBackoffSteps.text(), "10, 20, 30")

    def test_mainwindow_stack_navigation_and_shortcuts(self):
        win = MainWindow()
        self.assertEqual(win.stack.count(), 6)
        self.assertEqual(win.stack.widget(0), win.web_view)
        self.assertEqual(win.stack.widget(1), win.debug_console_page)
        self.assertEqual(win.stack.widget(2), win.proxy_settings_page)
        self.assertEqual(win.stack.widget(3), win.advanced_settings_page)
        self.assertEqual(win.stack.widget(4), win.general_settings_page)
        self.assertEqual(win.stack.widget(5), win.account_settings_page)

        # Test switching to General Settings
        win._navigate_to_settings_tab("general")
        self.assertEqual(win.stack.currentIndex(), 4)

        # Test switching to Account Settings
        win._navigate_to_settings_tab("account")
        self.assertEqual(win.stack.currentIndex(), 5)

        # Test switching to Proxy Settings
        win._navigate_to_settings_tab("proxy")
        self.assertEqual(win.stack.currentIndex(), 2)

        # Test switching to Advanced Settings
        win._navigate_to_settings_tab("advanced")
        self.assertEqual(win.stack.currentIndex(), 3)

        # Test switching to Debug Console
        win._navigate_to_settings_tab("debug")
        self.assertEqual(win.stack.currentIndex(), 1)

        # Test switching back to Web view
        win._navigate_to("/")
        self.assertEqual(win.stack.currentIndex(), 0)

if __name__ == "__main__":
    unittest.main()
