from __future__ import annotations

import argparse
import ctypes
import logging
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from dualsync.core.audio_engine import AudioEngine
from dualsync.core.device_manager import DeviceManager
from dualsync.services.config import ConfigStore
from dualsync.services.diagnostics import configure_logging
from dualsync.services.single_instance import SingleInstance
from dualsync.ui.icon import app_icon
from dualsync.ui.style import STYLESHEET
from dualsync.ui.tray import TrayController

log = logging.getLogger(__name__)

WINDOWS_APP_ID = "DualSync.AudioSynchronizer.1.1"


def set_windows_app_id() -> None:
    """Give every DualSync window one stable Windows taskbar identity."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except (AttributeError, OSError):
        log.debug("Unable to set Windows AppUserModelID", exc_info=True)


class ErrorBridge(QObject):
    error = Signal(str, str)


def main() -> int:
    parser = argparse.ArgumentParser(description="DualSync multi-device audio synchronizer")
    parser.add_argument("--minimized", action="store_true")
    args = parser.parse_args()
    configure_logging()
    instance = SingleInstance()
    if instance.already_running:
        return 2
    set_windows_app_id()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("DualSync")
    app.setApplicationDisplayName("DualSync")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLESHEET)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "DualSync", "Windows system tray is unavailable.")
        return 3
    store = ConfigStore()
    settings = store.load()
    manager = DeviceManager()
    tray: TrayController | None = None
    bridge = ErrorBridge()

    def show_engine_error(endpoint_id: str, message: str) -> None:
        log.error("audio engine: %s", message)
        if tray:
            tray.popup.renderer_failed(endpoint_id, message)
            if settings.notifications:
                tray.tray.showMessage(
                    "DualSync output stopped", message, QSystemTrayIcon.MessageIcon.Warning
                )

    bridge.error.connect(show_engine_error)
    engine = AudioEngine(bridge.error.emit)
    tray = TrayController(app, engine, manager, settings, store)
    activation_timer = QTimer(app)
    activation_timer.setInterval(150)
    activation_timer.timeout.connect(
        lambda: tray.show_popup() if instance.activation_requested() else None
    )
    activation_timer.start()
    if args.minimized:
        QTimer.singleShot(0, tray.popup.showMinimized)
    else:
        QTimer.singleShot(0, tray.show_popup)
    if settings.auto_resume and settings.was_running:
        QTimer.singleShot(1200, tray.popup.start_sharing)
    app.aboutToQuit.connect(engine.stop)
    try:
        return app.exec()
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
