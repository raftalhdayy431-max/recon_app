"""نقطة تشغيل البرنامج."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from app import APP_NAME
from app.ui.main_window import MainWindow


def main() -> int:
    if sys.platform == "win32":   # أيقونة مستقلة في شريط المهام
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ReconPro.Reconciliation.1")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(QFont("Arial", 10))
    w = MainWindow()
    w.setWindowIcon(QIcon(MainWindow._logo_pixmap(256)))
    app.setWindowIcon(w.windowIcon())
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
