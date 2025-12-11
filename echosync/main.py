# echo_sync/main.py
import sys
from PySide6.QtWidgets import QApplication
from echo_sync.ui_main import EchoSyncApp

def main():
    app = QApplication(sys.argv)
    window = EchoSyncApp()
    window.resize(1200, 780)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
