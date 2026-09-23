import sys
import unittest
import json
from PySide6.QtWidgets import QApplication
from src.ui.pages.proxy_settings_page import ProxySettingsPage
from src.ui.pages.advanced_settings_page import AdvancedSettingsPage
from src.ui.pages.general_settings_page import GeneralSettingsPage
from src.ui.pages.account_settings_page import AccountSettingsPage
from src.ui.pages.debug_console_page import DebugConsolePage
from src.ui.pages.user_tokens_page import UserTokensPage
from src.ui.pages.ip_management_page import IpManagementPage
from src.ui.pages.traffic_logs_page import TrafficLogsPage
from src.ui.pages.token_stats_page import TokenStatsPage
from src.ui.pages.dashboard_page import DashboardPage
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

        # Verify QLCDNumber widgets exist
        self.assertIsNotNone(page.ui.valProxyPort)
        self.assertIsNotNone(page.ui.valActiveAccounts)
        self.assertIsNotNone(page.ui.valCooldownAccounts)
        self.assertIsNotNone(page.ui.valProxyOnline)

        page.ui.spinPort.setValue(9090)
        page.ui.chkAllowLan.setChecked(True)
        page.ui.editApiKey.setText("sk-test-key-1234")
        page.save_settings()

        page.load_from_config()
        self.assertEqual(page.ui.spinPort.value(), 9090)
        self.assertTrue(page.ui.chkAllowLan.isChecked())
        self.assertEqual(page.ui.editApiKey.text(), "sk-test-key-1234")
        self.assertEqual(page.ui.valProxyPort.value(), 9090)


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

    def test_ip_management_page_direct_ui(self):
        page = IpManagementPage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.windowTitle(), "IP Management")

        page.rules.clear()
        page.save_settings()

        # Test policy controls
        page.ui.chkEnableFiltering.setChecked(True)
        page.ui.comboFilterMode.setCurrentIndex(1) # Whitelist
        page.ui.chkAllowLoopback.setChecked(True)
        page.ui.chkAllowLan.setChecked(False)

        # Add valid IP rule
        page.ui.editRuleIp.setText("192.168.1.50")
        page.ui.comboRuleAction.setCurrentIndex(0) # ALLOW
        page.ui.editRuleNote.setText("Test Allowed Machine")
        page._on_add_rule()

        self.assertEqual(len(page.rules), 1)
        self.assertEqual(page.rules[0]["pattern"], "192.168.1.50")
        self.assertEqual(page.rules[0]["action"], "ALLOW")
        self.assertEqual(page.rules[0]["note"], "Test Allowed Machine")

        # Save and reload
        page.save_settings()
        page.load_from_config()

        self.assertTrue(page.ui.chkEnableFiltering.isChecked())
        self.assertEqual(page.ui.comboFilterMode.currentIndex(), 1)
        self.assertTrue(page.ui.chkAllowLoopback.isChecked())
        self.assertFalse(page.ui.chkAllowLan.isChecked())
        self.assertEqual(len(page.rules), 1)
        self.assertEqual(page.rules[0]["pattern"], "192.168.1.50")

    def test_user_tokens_page_direct_ui(self):
        page = UserTokensPage()
        self.assertIsNotNone(page.ui)
        self.assertEqual(page.ui.windowTitle(), "User Tokens")

        page.tokens.clear()
        page.save_settings()

        # Test token generation
        page.ui.editTokenName.setText("VS Code Client")
        page.ui.spinRpm.setValue(120)
        page.ui.spinDailyQuota.setValue(5000)
        page._on_generate_token()

        self.assertEqual(len(page.tokens), 1)
        token_entry = page.tokens[0]
        self.assertEqual(token_entry["name"], "VS Code Client")
        self.assertEqual(token_entry["rpm"], 120)
        self.assertEqual(token_entry["daily_quota"], 5000)
        self.assertTrue(token_entry["token"].startswith("sk-antigravity-"))
        self.assertEqual(token_entry["status"], "Active")

        # Test pause/resume
        page._toggle_token_status(0)
        self.assertEqual(page.tokens[0]["status"], "Suspended")
        page._toggle_token_status(0)
        self.assertEqual(page.tokens[0]["status"], "Active")

        # Save and reload
        page.save_settings()
        page.load_from_config()
        self.assertEqual(len(page.tokens), 1)
        self.assertEqual(page.tokens[0]["name"], "VS Code Client")

    def test_traffic_logs_page_direct_ui(self):
        page = TrafficLogsPage()
        self.assertIsNotNone(page.form_widget)
        self.assertEqual(page.form_widget.windowTitle(), "Traffic Logs")

        # Verify QLCDNumber widgets exist
        self.assertIsNotNone(page.val_total_requests)
        self.assertIsNotNone(page.val_success_rate)
        self.assertIsNotNone(page.val_active_connections)
        self.assertIsNotNone(page.val_blocked_requests)

        # Add sample traffic record
        page.add_traffic_record(
            method="POST",
            path="/v1/chat/completions",
            model="gemini-2.5-pro",
            client_ip="127.0.0.1",
            status=200,
            duration_ms=45.2,
        )
        page.load_from_config()
        self.assertEqual(len(page.traffic_records), 1)
        self.assertEqual(page.val_total_requests.value(), 1)
        self.assertEqual(page.table_logs.rowCount(), 1)

    def test_token_stats_page_direct_ui(self):
        page = TokenStatsPage()
        self.assertIsNotNone(page.form_widget)
        self.assertEqual(page.form_widget.windowTitle(), "Token Stats")

        # Verify all 6 QLCDNumber widgets exist
        self.assertIsNotNone(page.val_total_tokens)
        self.assertIsNotNone(page.val_input_tokens)
        self.assertIsNotNone(page.val_output_tokens)
        self.assertIsNotNone(page.val_cached_tokens)
        self.assertIsNotNone(page.val_active_accounts)
        self.assertIsNotNone(page.val_models_used)  # 6th card

        # Verify viewMode toggle buttons exist
        self.assertIsNotNone(page.btn_view_by_model)
        self.assertIsNotNone(page.btn_view_by_account)

        # Verify both tables exist with correct column counts
        self.assertIsNotNone(page.table_model_stats)
        self.assertIsNotNone(page.table_account_stats)
        self.assertEqual(page.table_model_stats.columnCount(), 7)
        self.assertEqual(page.table_account_stats.columnCount(), 7)

        # Test loading (dynamic rows based on DB quota_json)
        page.load_from_config()
        self.assertGreaterEqual(page.table_model_stats.rowCount(), 0)
        self.assertGreaterEqual(page.table_account_stats.rowCount(), 0)

        # Test viewMode toggle
        page._set_view_mode(TokenStatsPage.VIEW_BY_ACCOUNT)
        self.assertEqual(page._view_mode, TokenStatsPage.VIEW_BY_ACCOUNT)
        page._set_view_mode(TokenStatsPage.VIEW_BY_MODEL)
        self.assertEqual(page._view_mode, TokenStatsPage.VIEW_BY_MODEL)

    def test_dashboard_page_direct_ui(self):
        page = DashboardPage()
        self.assertIsNotNone(page.form_widget)
        self.assertEqual(page.form_widget.windowTitle(), "Dashboard")

        # Verify QLCDNumber widgets exist
        self.assertIsNotNone(page.val_active_accounts)
        self.assertIsNotNone(page.val_proxy_port)
        self.assertIsNotNone(page.val_total_tokens)
        self.assertIsNotNone(page.val_total_requests)

        # Verify account pool table exists
        self.assertIsNotNone(page.table_accounts)

        # Verify Quick Connect URL fields exist
        self.assertIsNotNone(page.edit_openai_url)
        self.assertIsNotNone(page.edit_claude_url)

        # Test loading config (no bridge)
        page.load_from_config()

    def test_mainwindow_stack_navigation_and_shortcuts(self):
        win = MainWindow()
        self.assertEqual(win.stack.count(), 11)
        self.assertEqual(win.stack.widget(0), win.web_view)
        self.assertEqual(win.stack.widget(1), win.debug_console_page)
        self.assertEqual(win.stack.widget(2), win.proxy_settings_page)
        self.assertEqual(win.stack.widget(3), win.advanced_settings_page)
        self.assertEqual(win.stack.widget(4), win.general_settings_page)
        self.assertEqual(win.stack.widget(5), win.account_settings_page)
        self.assertEqual(win.stack.widget(6), win.user_tokens_page)
        self.assertEqual(win.stack.widget(7), win.ip_management_page)
        self.assertEqual(win.stack.widget(8), win.traffic_logs_page)
        self.assertEqual(win.stack.widget(9), win.token_stats_page)
        self.assertEqual(win.stack.widget(10), win.dashboard_page)

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

        # Test switching to API Proxy route (/api-proxy)
        win._navigate_to("/api-proxy")
        self.assertEqual(win.stack.currentIndex(), 2)

        # Test switching to User Tokens route (/user-token)
        win._navigate_to("/user-token")
        self.assertEqual(win.stack.currentIndex(), 6)

        # Test switching to IP Management route (/security)
        win._navigate_to("/security")
        self.assertEqual(win.stack.currentIndex(), 7)

        # Test switching to Traffic Logs route (/monitor)
        win._navigate_to("/monitor")
        self.assertEqual(win.stack.currentIndex(), 8)

        # Test switching to Token Stats route (/token-stats)
        win._navigate_to("/token-stats")
        self.assertEqual(win.stack.currentIndex(), 9)

        # Test switching to Dashboard route (/)
        win._navigate_to("/")
        self.assertEqual(win.stack.currentIndex(), 10)

if __name__ == "__main__":
    unittest.main()
