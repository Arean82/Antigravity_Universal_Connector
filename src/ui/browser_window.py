import os
import sys
import time
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QMenuBar, QMessageBox, QStackedWidget
from PySide6.QtGui import QAction, QKeySequence, QActionGroup
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineScript, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl
from src.core.database import db
from src.ui.bridge import BackendBridge
from src.proxy.server import LocalProxyServer
from src.ui.pages.debug_console_page import DebugConsolePage
from src.ui.pages.proxy_settings_page import ProxySettingsPage
from src.ui.pages.advanced_settings_page import AdvancedSettingsPage
from src.ui.pages.general_settings_page import GeneralSettingsPage
from src.ui.pages.account_settings_page import AccountSettingsPage

class CustomWebPage(QWebEnginePage):
    def __init__(self, parent=None, log_callback=None):
        super().__init__(parent)
        self.log_callback = log_callback

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        print(f"js: {message}")
        if self.log_callback:
            lvl_name = "INFO"
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                lvl_name = "ERROR"
            elif level == QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel:
                lvl_name = "WARN"

            src = sourceId.split("/")[-1] if sourceId else "browser"
            self.log_callback(
                level=lvl_name,
                target=f"web::{src}",
                message=message,
                fields={"line": lineNumber, "source": sourceId}
            )

TAURI_POLYFILL_JS = """
(function() {
    window.__TAURI__ = window.__TAURI__ || {};
    window.__TAURI_INTERNALS__ = window.__TAURI_INTERNALS__ || {};

    try {
        localStorage.setItem('app_language', 'en');
        localStorage.setItem('i18nextLng', 'en');
    } catch(e) {}


    // Tauri v2 internals metadata required by getCurrentWindow()
    window.__TAURI_INTERNALS__.metadata = {
        currentWindow: {
            label: "main"
        }
    };

    // Fix: Event plugin internals required by Tauri v2 unlisten()
    const mockEventPlugin = {
        unregisterListener: function(event, eventId) {},
        registerListener: function(event, eventId) {}
    };
    window.__TAURI_EVENT_PLUGIN_INTERNALS__ = mockEventPlugin;
    try {
        Object.defineProperty(window, '__TAURI_EVENT_PLUGIN_INTERNALS__', {
            value: mockEventPlugin,
            writable: true,
            configurable: true
        });
    } catch(e) {}

    let _cbCounter = 1;
    const _callbacks = {};

    window.__TAURI_INTERNALS__.transformCallback = function(callback, once) {
        const id = _cbCounter++;
        _callbacks[id] = function(arg) {
            if (once) delete _callbacks[id];
            return callback(arg);
        };
        return id;
    };

    const mockWindowObj = {
        show: async () => {},
        hide: async () => {},
        close: async () => {},
        minimize: async () => {},
        maximize: async () => {},
        setFocus: async () => {},
        setTitle: async () => {},
        setBackgroundColor: async () => {},
        setSize: async () => {},
        setDecorations: async () => {},
        setResizable: async () => {},
        setAlwaysOnTop: async () => {},
        setShadow: async () => {},
        center: async () => {},
        startDragging: () => {},
        innerSize: async () => ({ width: 1280, height: 850 }),
        outerSize: async () => ({ width: 1280, height: 850 }),
        scaleFactor: async () => 1.0,
        isFocused: async () => true,
        isVisible: async () => true,
        isFullscreen: async () => false,
        isMinimized: async () => false,
        isMaximized: async () => false,
        listen: async () => () => {},
        once: async () => () => {}
    };

    window.__TAURI__.window = {
        currentWindow: function() {
            return mockWindowObj;
        },
        getCurrentWindow: function() {
            return mockWindowObj;
        }
    };

    window.__TAURI__.event = {
        listen: async function(event, handler) {
            return function unlisten() {};
        },
        emit: async function(event, payload) {}
    };

    // Generic IPC dispatcher for window.__TAURI_INTERNALS__.invoke and window.__TAURI__.invoke
    const invokeHandler = async function(cmd, args) {
        // Handle window plugin calls
        if (typeof cmd === 'string' && cmd.startsWith('plugin:window')) {
            if (cmd === 'plugin:window|get_all_windows') return ['main'];
            if (cmd === 'plugin:window|is_focused') return true;
            if (cmd === 'plugin:window|is_visible') return true;
            if (cmd === 'plugin:window|is_maximized') return false;
            if (cmd === 'plugin:window|is_minimized') return false;
            if (cmd === 'plugin:window|inner_size' || cmd === 'plugin:window|outer_size') {
                return { width: 1280, height: 850 };
            }
            if (cmd === 'plugin:window|scale_factor') return 1.0;
            return null;
        }

        if (typeof cmd === 'string' && cmd.startsWith('plugin:event')) {
            if (cmd === 'plugin:event|listen') {
                return 1000 + Math.floor(Math.random() * 9000);
            }
            if (cmd === 'plugin:event|unlisten') {
                return null;
            }
            if (cmd === 'plugin:event|emit') {
                return null;
            }
            return null;
        }

        const waitForBridge = async () => {
            let attempts = 0;
            while (!window.backendBridge && attempts < 50) {
                await new Promise(r => setTimeout(r, 20));
                attempts++;
            }
            return window.backendBridge;
        };

        const bridge = await waitForBridge();

        try {
            if (cmd === 'load_config' || cmd === 'get_config') {
                if (bridge && bridge.load_config) {
                    const res = await new Promise(r => bridge.load_config(r));
                    return JSON.parse(res);
                }
                return {
                    language: 'en',
                    theme: 'system',
                    auto_refresh: true,
                    refresh_interval: 15,
                    proxy: { enabled: false, port: 8045, api_key: 'sk-antigravity' },
                    scheduled_warmup: { enabled: false, monitored_models: [] },
                    quota_protection: { enabled: false, threshold_percentage: 10, monitored_models: [] },
                    pinned_quota_models: { models: [] },
                    circuit_breaker: { enabled: true, backoff_steps: [60, 300, 1800, 7200], lock_on_zero_quota: false }
                };
            }

            if (cmd === 'is_debug_console_enabled') {
                return false;
            }

            if (cmd === 'list_accounts') {
                if (bridge && bridge.list_accounts) {
                    const res = await new Promise(r => bridge.list_accounts(r));
                    return JSON.parse(res);
                }
                return { accounts: [], current_account_id: null };
            }

            if (cmd === 'get_current_account') {
                if (bridge && bridge.get_current_account) {
                    const res = await new Promise(r => bridge.get_current_account(r));
                    return JSON.parse(res);
                }
                return null;
            }

            if (cmd === 'add_account') {
                const email = args ? args.email : '';
                const token = args ? args.refreshToken : '';
                if (bridge && bridge.add_account) {
                    const res = await new Promise(r => bridge.add_account(email, token, r));
                    return JSON.parse(res);
                }
                return { id: 'acc_1', email: email || 'user@gmail.com', status: 'active' };
            }

            if (cmd === 'delete_account') {
                const accId = args ? args.accountId : '';
                if (bridge && bridge.delete_account) {
                    const res = await new Promise(r => bridge.delete_account(accId, r));
                    return JSON.parse(res);
                }
                return { success: true };
            }

            if (cmd === 'delete_accounts') {
                return { success: true };
            }

            if (cmd === 'get_proxy_status') {
                if (bridge && bridge.get_proxy_status) {
                    try {
                        const res = await new Promise(r => bridge.get_proxy_status(r));
                        const parsed = JSON.parse(res);
                        if (parsed && typeof parsed === 'object') {
                            return {
                                running: !!parsed.running,
                                port: parsed.port || 8045,
                                base_url: parsed.base_url || 'http://127.0.0.1:8045',
                                active_accounts: parsed.active_accounts || 0
                            };
                        }
                    } catch (e) {
                        console.error('Error fetching proxy status:', e);
                    }
                }
                return { running: false, port: 8045, base_url: 'http://127.0.0.1:8045', active_accounts: 0 };
            }

            if (cmd === 'show_main_window' || cmd === 'set_window_theme') {
                return;
            }

            if (cmd === 'fetch_account_quota' || cmd === 'refresh_account_quota') {
                const accId = args ? args.accountId : '';
                if (bridge && bridge.fetch_account_quota) {
                    const res = await new Promise(r => bridge.fetch_account_quota(accId, r));
                    return JSON.parse(res);
                }
                return {};
            }

            if (cmd === 'switch_account') {
                const accId = args ? args.accountId : '';
                if (bridge && bridge.switch_account) {
                    const res = await new Promise(r => bridge.switch_account(accId, r));
                    return JSON.parse(res);
                }
                return { success: false };
            }

            if (cmd === 'start_proxy_service') {
                if (bridge && bridge.start_proxy) {
                    const res = await new Promise(r => bridge.start_proxy(8045, r));
                    return JSON.parse(res);
                }
                return { success: true, port: 8045 };
            }

            if (cmd === 'stop_proxy_service') {
                if (bridge && bridge.stop_proxy) {
                    const res = await new Promise(r => bridge.stop_proxy(r));
                    return JSON.parse(res);
                }
                return { success: true };
            }

            if (cmd === 'import_from_db' || cmd === 'import_v1_accounts') {
                if (bridge && bridge.import_from_vscdb) {
                    const res = await new Promise(r => bridge.import_from_vscdb(r));
                    return JSON.parse(res);
                }
                return { success: false, error: 'Bridge not initialized' };
            }

            if (cmd === 'get_token_stats_summary' || cmd === 'get_proxy_stats') {
                return { total_requests: 0, total_tokens: 0, successful_requests: 0, failed_requests: 0 };
            }

            if (cmd === 'get_opencode_sync_status') {
                return { installed: false, synced: false };
            }

            if (cmd === 'get_opencode_providers') {
                return [];
            }

            if (cmd === 'list_user_tokens') {
                return [];
            }

            if (cmd === 'get_user_token_summary') {
                return {
                    total_users: 0,
                    active_tokens: 0,
                    total_tokens: 0,
                    today_requests: 0
                };
            }

            if (cmd === 'create_user_token' || cmd === 'update_user_token' || cmd === 'delete_user_token' || cmd === 'renew_user_token') {
                return { success: true };
            }

            if (cmd === 'get_ip_stats') {
                return { total_requests: 0, unique_ips: 0, blocked_requests: 0 };
            }

            if (cmd === 'get_ip_token_stats') {
                return [];
            }

            if (cmd === 'get_debug_console_logs') {
                return [];
            }

            if (cmd === 'should_check_updates') {
                return false;
            }

            if (cmd === 'save_config' || cmd === 'update_model_mapping') {
                if (args && args.config && bridge && bridge.save_config) {
                    const res = await new Promise(r => bridge.save_config(JSON.stringify(args.config), r));
                    return JSON.parse(res);
                }
                return { success: true };
            }

            if (cmd === 'generate_api_key') {
                return 'sk-antigravity-' + Math.random().toString(36).substring(2, 15);
            }

            if (cmd === 'clear_proxy_session_bindings' || cmd === 'clear_all_proxy_rate_limits') {
                return { success: true };
            }

            if (cmd === 'prepare_oauth_url') {
                return { url: 'https://accounts.google.com/o/oauth2/v2/auth' };
            }

            if (cmd === 'cancel_oauth_login') {
                return { success: true };
            }

            if (cmd === 'list_oauth_clients') {
                return { clients: [] };
            }

            if (cmd === 'cloudflared_get_status') {
                return {
                    installed: false,
                    running: false,
                    url: '',
                    version: '',
                    error: null
                };
            }

            if (cmd === 'get_update_settings') {
                return { auto_check: true, check_interval_hours: 24 };
            }

            if (cmd === 'save_update_settings') {
                return { success: true };
            }

            if (cmd === 'get_data_dir_path') {
                return '~/.antigravity_tools/';
            }

            if (cmd === 'is_auto_launch_enabled') {
                return false;
            }

            if (cmd === 'toggle_auto_launch') {
                return { success: true };
            }

            if (cmd === 'check_homebrew_installation') {
                return false;
            }

            if (cmd === 'check_for_updates') {
                return { has_update: false, latest_version: '1.0.0' };
            }

            if (cmd === 'get_ip_access_logs') {
                return { logs: [], total: 0 };
            }

            if (cmd === 'get_ip_blacklist' || cmd === 'get_ip_whitelist') {
                return [];
            }

            if (cmd === 'get_security_config') {
                return {
                    blacklist: { enabled: false, block_message: '' },
                    whitelist: { enabled: false, whitelist_priority: false }
                };
            }

            if (cmd === 'update_security_config') {
                return { success: true };
            }

            if (typeof cmd === 'string' && cmd.startsWith('get_token_stats_')) {
                return [];
            }

            if (cmd === 'save_last_route') {
                if (args && args.route && bridge && bridge.save_last_route) {
                    bridge.save_last_route(args.route, () => {});
                }
                return { success: true };
            }

            return null;
        } catch (err) {
            console.error('[Tauri Polyfill] Error executing cmd:', cmd, err);
            return null;
        }
    };

    window.__TAURI_INTERNALS__.invoke = invokeHandler;
    window.__TAURI__.invoke = invokeHandler;
    window.__TAURI__.core = { invoke: invokeHandler };
})();
"""

class MainWindow(QMainWindow):
    """
    Main Desktop Window hosting the modern Web UI via PySide6 QWebEngineView.
    Embeds QWebChannel for direct bidirectional IPC with Python & Rust services.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Antigravity Universal Connector")
        self.resize(1280, 850)

        # Start local embedded HTTP server for HTML5 history route compatibility
        self.proxy_server = LocalProxyServer(host="127.0.0.1", port=8045)
        self.proxy_server.start()

        # Central multi-page container supporting progressive native PySide6 migration
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget(self)
        self.layout.addWidget(self.stack)

        # Configure QWebChannel & BackendBridge
        self.bridge = BackendBridge(self)
        self.bridge.proxy_server = self.proxy_server

        # Index 1: Native PySide6 Debug Console (100% Native, built from debug_console.ui)
        self.debug_console_page = DebugConsolePage(self)

        # Index 2: Native PySide6 Proxy Settings (100% Native, built from proxy_settings.ui)
        self.proxy_settings_page = ProxySettingsPage(bridge=self.bridge, parent=self)

        # Index 3: Native PySide6 Advanced Settings (100% Native, built from advanced_settings.ui)
        self.advanced_settings_page = AdvancedSettingsPage(bridge=self.bridge, parent=self)

        # Index 4: Native PySide6 General Settings (100% Native, built from general_settings.ui)
        self.general_settings_page = GeneralSettingsPage(bridge=self.bridge, parent=self)

        # Index 5: Native PySide6 Account Settings (100% Native, built from account_settings.ui)
        self.account_settings_page = AccountSettingsPage(bridge=self.bridge, parent=self)

        # Index 0: WebEngine View (for views not yet migrated)
        self.web_view = QWebEngineView(self)
        self.web_page = CustomWebPage(self.web_view, log_callback=self.debug_console_page.add_log)
        self.web_view.setPage(self.web_page)
        self.stack.addWidget(self.web_view)                 # Index 0
        self.stack.addWidget(self.debug_console_page)        # Index 1
        self.stack.addWidget(self.proxy_settings_page)       # Index 2
        self.stack.addWidget(self.advanced_settings_page)    # Index 3
        self.stack.addWidget(self.general_settings_page)     # Index 4
        self.stack.addWidget(self.account_settings_page)     # Index 5

        # Inject Polyfill script at DocumentCreation so it executes before React
        self._inject_tauri_polyfill()

        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject("backendBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Connect loadFinished to restore last active route from SQLite
        self.web_view.loadFinished.connect(self._on_page_load_finished)

        # Native Desktop Menu Bar
        self._create_menu_bar()

        self._load_frontend()

    def _create_menu_bar(self):
        menubar = self.menuBar()
        # Authentic native Windows Vista / XP classic menu bar styling
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #F0F0F0;
                color: #000000;
                font-family: 'Segoe UI', 'Tahoma', sans-serif;
                font-size: 12px;
                border-bottom: 1px solid #D0D0D0;
                padding: 1px 2px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 8px;
                border-radius: 2px;
            }
            QMenuBar::item:selected {
                background-color: #CCE8FF;
                border: 1px solid #99D1FF;
                color: #000000;
            }
            QMenuBar::item:pressed {
                background-color: #99D1FF;
                border: 1px solid #66BAFF;
            }
            QMenu {
                background-color: #F8F8F8;
                color: #000000;
                font-family: 'Segoe UI', 'Tahoma', sans-serif;
                font-size: 12px;
                border: 1px solid #999999;
                padding: 3px;
            }
            QMenu::item {
                padding: 4px 24px 4px 20px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #90C8F6;
                color: #000000;
            }
            QMenu::separator {
                height: 1px;
                background-color: #D4D4D4;
                margin: 3px 6px;
            }
        """)

        # --- File Menu ---
        file_menu = menubar.addMenu("&File")

        reload_action = QAction("&Reload UI", self)
        reload_action.setShortcut(QKeySequence("Ctrl+R"))
        reload_action.triggered.connect(self._reload_page)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Navigation Menu ---
        nav_menu = menubar.addMenu("&Navigate")

        nav_items = [
            ("Dashboard", "/", "Ctrl+1"),
            ("Accounts", "/accounts", "Ctrl+2"),
            ("API Proxy", "/api-proxy", "Ctrl+3"),
            ("Transit Station", "/apikey-fun", "Ctrl+4"),
            ("Traffic Logs", "/monitor", "Ctrl+5"),
            ("Token Stats", "/token-stats", "Ctrl+6"),
            ("User Tokens", "/user-token", "Ctrl+7"),
            ("IP Management", "/security", "Ctrl+8"),
        ]

        for label, path, shortcut in nav_items:
            action = QAction(label, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda checked=False, p=path: self._navigate_to(p))
            nav_menu.addAction(action)

        # --- Settings Menu (Dedicated Top-Level) ---
        settings_menu = menubar.addMenu("&Settings")

        settings_sections = [
            ("General Settings", "general", "Ctrl+G"),
            ("Account Settings", "account", "Ctrl+A"),
            ("Proxy Settings", "proxy", "Ctrl+P"),
            ("Advanced Settings", "advanced", "Ctrl+Alt+A"),
            ("Debug Console", "debug", "Ctrl+Shift+D"),
        ]

        for label, tab, shortcut in settings_sections:
            action = QAction(label, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda checked=False, t=tab: self._navigate_to_settings_tab(t))
            settings_menu.addAction(action)

        # --- View / Theme Menu ---
        view_menu = menubar.addMenu("&View")

        theme_menu = view_menu.addMenu("&Theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        current_cfg = self.bridge.config
        current_theme = current_cfg.get("theme", "system")

        for t_label, t_val in [("&System Default", "system"), ("&Light", "light"), ("&Dark", "dark")]:
            t_action = QAction(t_label, self, checkable=True)
            if t_val == current_theme:
                t_action.setChecked(True)
            t_action.triggered.connect(lambda checked=False, val=t_val: self._set_theme(val))
            theme_group.addAction(t_action)
            theme_menu.addAction(t_action)

        # --- Language Menu ---
        lang_menu = menubar.addMenu("&Language")
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)

        current_lang = current_cfg.get("language", "en")

        languages = [
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

        for l_label, l_code in languages:
            l_action = QAction(l_label, self, checkable=True)
            if l_code == current_lang:
                l_action.setChecked(True)
            l_action.triggered.connect(lambda checked=False, code=l_code: self._set_language(code))
            lang_group.addAction(l_action)
            lang_menu.addAction(l_action)

        # --- Tools Menu ---
        tools_menu = menubar.addMenu("&Tools")

        debug_console_action = QAction("Debug Console", self)
        debug_console_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        debug_console_action.triggered.connect(self._show_debug_console)
        tools_menu.addAction(debug_console_action)

        tools_menu.addSeparator()

        start_proxy_action = QAction("Start Proxy Service", self)
        start_proxy_action.triggered.connect(lambda: self.bridge.start_proxy(8045, lambda res: None))
        tools_menu.addAction(start_proxy_action)

        stop_proxy_action = QAction("Stop Proxy Service", self)
        stop_proxy_action.triggered.connect(lambda: self.bridge.stop_proxy(lambda res: None))
        tools_menu.addAction(stop_proxy_action)

        tools_menu.addSeparator()

        import_action = QAction("Import Accounts from VSCode DB", self)
        import_action.triggered.connect(lambda: self.bridge.import_from_vscdb(lambda res: None))
        tools_menu.addAction(import_action)

        # --- Help Menu ---
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _set_theme(self, theme_val: str):
        self.bridge.config["theme"] = theme_val
        self.bridge.save_config(json.dumps(self.bridge.config))
        # Dynamically evaluate system dark preference if 'system'
        js = f"""
        (function() {{
            const chosen = '{theme_val}';
            const isDark = chosen === 'dark' || (chosen === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
            const actualTheme = isDark ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', actualTheme);
            document.documentElement.style.backgroundColor = isDark ? '#1d232a' : '#FAFBFC';
            if (isDark) {{
                document.documentElement.classList.add('dark');
            }} else {{
                document.documentElement.classList.remove('dark');
            }}
            localStorage.setItem('app-theme-preference', chosen);
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _set_language(self, lang_code: str):
        self.bridge.config["language"] = lang_code
        self.bridge.save_config(json.dumps(self.bridge.config))
        js = f"""
        (function() {{
            const lang = '{lang_code}';
            localStorage.setItem('i18nextLng', lang);
            localStorage.setItem('app_language', lang);
            document.documentElement.dir = (lang === 'ar') ? 'rtl' : 'ltr';
            if (window.i18next) {{
                window.i18next.changeLanguage(lang);
            }} else {{
                window.location.reload();
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _navigate_to(self, path: str):
        self.stack.setCurrentIndex(0)
        db.set_setting("last_active_route", path)
        js = f"window.location.pathname = '{path}'; if (window.__REACT_ROUTER__) {{ window.__REACT_ROUTER__.navigate('{path}'); }}"
        self.web_view.page().runJavaScript(js)

    def _show_debug_console(self):
        self.stack.setCurrentIndex(1)
        self.debug_console_page.add_log(
            level="INFO",
            target="ui::navigator",
            message="Switched to native PySide6 Debug Console view."
        )

    def _show_proxy_settings(self):
        self.proxy_settings_page.load_from_config()
        self.stack.setCurrentIndex(2)

    def _show_advanced_settings(self):
        self.advanced_settings_page.load_from_config()
        self.stack.setCurrentIndex(3)

    def _show_general_settings(self):
        self.general_settings_page.load_from_config()
        self.stack.setCurrentIndex(4)

    def _show_account_settings(self):
        self.account_settings_page.load_from_config()
        self.stack.setCurrentIndex(5)

    def _navigate_to_settings_tab(self, tab_name: str):
        if tab_name == "general":
            self._show_general_settings()
            return
        if tab_name == "account":
            self._show_account_settings()
            return
        if tab_name == "proxy":
            self._show_proxy_settings()
            return
        if tab_name == "advanced":
            self._show_advanced_settings()
            return
        if tab_name == "debug":
            self._show_debug_console()
            return

        self._show_general_settings()
        db.set_setting("last_active_route", "/settings")
        js = f"""
        (function() {{
            if (window.location.pathname !== '/settings') {{
                window.location.pathname = '/settings';
                if (window.__REACT_ROUTER__) window.__REACT_ROUTER__.navigate('/settings');
            }}
            setTimeout(() => {{
                // Find tab buttons in Settings page and click the desired tab
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {{
                    const text = (btn.textContent || '').trim().toLowerCase();
                    if (text.includes('{tab_name}') || btn.getAttribute('data-tab') === '{tab_name}') {{
                        btn.click();
                        break;
                    }}
                }}
            }}, 350);
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _on_page_load_finished(self, success: bool):
        if success:
            last_route = db.get_setting("last_active_route", "/")
            if last_route and last_route != "/":
                nav_js = f"""
                setTimeout(() => {{
                    if (window.location.pathname !== '{last_route}') {{
                        window.history.pushState(null, '', '{last_route}');
                        window.dispatchEvent(new PopStateEvent('popstate'));
                    }}
                }}, 300);
                """
                self.web_view.page().runJavaScript(nav_js)

            # Remove duplicate web navbar completely (now handled by native desktop QMenuBar)
            cleanup_nav_js = """
            (function() {
                const removeNav = () => {
                    document.querySelectorAll('nav').forEach(el => el.remove());
                };
                removeNav();
                setTimeout(removeNav, 100);
                setTimeout(removeNav, 500);

                // Ensure each settings tab has a dedicated Save Settings button at the bottom
                const ensureBottomSave = () => {
                    const settingsContainer = document.querySelector('.bg-white.dark\\\\:bg-base-100.rounded-2xl.p-6, [class*="rounded-2xl p-6"]');
                    if (settingsContainer && !document.getElementById('bottom-save-settings-bar')) {
                        const bar = document.createElement('div');
                        bar.id = 'bottom-save-settings-bar';
                        bar.className = 'mt-8 pt-4 border-t border-gray-100 dark:border-base-200 flex justify-end items-center gap-3';
                        bar.innerHTML = `
                            <button id="bottom-save-btn" class="px-6 py-2.5 bg-blue-500 hover:bg-blue-600 text-white font-medium text-sm rounded-xl transition-all shadow-sm flex items-center gap-2">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/></svg>
                                Save Settings
                            </button>
                        `;
                        settingsContainer.appendChild(bar);

                        const btn = bar.querySelector('#bottom-save-btn');
                        btn.onclick = () => {
                            // Trigger original save button or dispatch save
                            const originalSave = document.querySelector('.p-5.space-y-4 button[class*="bg-blue-500"]');
                            if (originalSave) {
                                originalSave.click();
                            } else if (window.__TAURI__ && window.__TAURI__.invoke) {
                            }
                        };
                    }
                };
                setInterval(ensureBottomSave, 500);

                // Remove any legacy About or Update views and external upstream repo links
                const purgeAboutAndUpdates = () => {
                    document.querySelectorAll('a, button, div').forEach(el => {
                        const href = el.getAttribute('href') || '';
                        if (href.includes('Antigravity-Manager') || href.includes('lbjlaq')) {
                            el.remove();
                        }
                    });
                };
                purgeAboutAndUpdates();
                setInterval(purgeAboutAndUpdates, 1000);
            })();
            """
            self.web_view.page().runJavaScript(cleanup_nav_js)

            # Auto-save route changes when user clicks around inside the app
            track_js = """
            if (!window.__route_listener_installed) {
                window.__route_listener_installed = true;
                const reportRoute = () => {
                    if (window.backendBridge && window.backendBridge.save_last_route) {
                        window.backendBridge.save_last_route(window.location.pathname, () => {});
                    }
                };
                window.addEventListener('popstate', reportRoute);
                const originalPush = window.history.pushState;
                window.history.pushState = function() {
                    originalPush.apply(this, arguments);
                    reportRoute();
                };
            }
            """
            self.web_view.page().runJavaScript(track_js)

    def _reload_page(self):
        self.web_view.reload()

    def _show_about(self):
        QMessageBox.about(
            self,
            "About Antigravity Universal Connector",
            "<h3>Antigravity Universal Connector</h3>"
            "<p>Unified Multi-Gateway Desktop Client & Proxy Architecture.</p>"
            "<p>Version: 1.0.0 Production</p>"
        )

    def _inject_tauri_polyfill(self):
        script = QWebEngineScript()
        script.setName("TauriPolyfill")
        script.setSourceCode(TAURI_POLYFILL_JS)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.web_view.page().scripts().insert(script)

    def _load_frontend(self):
        last_route = db.get_setting("last_active_route", "/")
        initial_url = f"http://127.0.0.1:8045{last_route}" if last_route and last_route.startswith("/") else "http://127.0.0.1:8045/"
        self.web_view.setUrl(QUrl(initial_url))

    def closeEvent(self, event):
        def _save_url_callback(url_str):
            try:
                if url_str:
                    from urllib.parse import urlparse
                    parsed = urlparse(url_str)
                    if parsed.path:
                        db.set_setting("last_active_route", parsed.path)
            except Exception:
                pass

        try:
            self.web_view.page().runJavaScript("window.location.href", _save_url_callback)
        except Exception:
            pass

        if hasattr(self, 'proxy_server') and self.proxy_server:
            self.proxy_server.stop()
        super().closeEvent(event)
