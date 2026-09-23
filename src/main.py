import sys
import os

# Ensure project root is in sys.path before any relative imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtWidgets import QApplication
from src.core.database import db
from src.ui.browser_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Antigravity Universal Connector")
    # Apply native Windows Vista/7/XP classic style to all native widgets
    app.setStyle("windowsvista")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
