from __future__ import annotations

import logging

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from dualsync.core.audio_engine import AudioEngine
from dualsync.core.device_manager import DeviceManager
from dualsync.services.config import AppSettings, ConfigStore

from .icon import app_icon
from .popup import ControlPopup

log = logging.getLogger(__name__)


class TrayController:
    def __init__(
        self,
        app: QApplication,
        engine: AudioEngine,
        manager: DeviceManager,
        settings: AppSettings,
        store: ConfigStore,
    ) -> None:
        self.app = app
        self.engine = engine
        self.settings = settings
        self.store = store
        self._positioned = False
        self.popup = ControlPopup(engine, manager, settings, store)
        self.tray = QSystemTrayIcon(app_icon(), app)
        self.tray.setToolTip("DualSync — paused\nClick to open · Double-click to quit")
        # Keep strong references: otherwise PySide may collect the menu/actions after init.
        self.menu = QMenu()
        self.open_action = QAction("Open DualSync", self.menu)
        self.toggle_action = QAction("Start sharing", self.menu)
        self.settings_action = QAction("Settings", self.menu)
        self.quit_action = QAction("Quit DualSync", self.menu)

        self.open_action.triggered.connect(self.show_popup)
        self.toggle_action.triggered.connect(self.popup.toggle_sharing)
        self.settings_action.triggered.connect(self.popup._settings)
        self.quit_action.triggered.connect(self.exit)

        self.menu.addAction(self.open_action)
        self.menu.addAction(self.toggle_action)
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.menu.setDefaultAction(self.open_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.popup.sharing_changed.connect(self._sharing_changed)
        self.popup.quit_requested.connect(self.exit)
        self.tray.show()

    def _activated(self, reason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        }:
            self.exit()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_popup()

    def show_popup(self) -> None:
        screen = self.app.primaryScreen().availableGeometry()
        if not self._positioned:
            cursor = self.tray.geometry().center()
            if cursor.isNull():
                cursor = QPoint(screen.right(), screen.bottom())
            x = max(
                screen.left(),
                min(cursor.x() - self.popup.width() // 2, screen.right() - self.popup.width()),
            )
            y = max(
                screen.top(),
                min(cursor.y() - self.popup.height(), screen.bottom() - self.popup.height()),
            )
            self.popup.move(x, y)
            self._positioned = True
        if self.popup.isMinimized():
            self.popup.showNormal()
        else:
            self.popup.show()
        self.popup.raise_()
        self.popup.activateWindow()

    def _sharing_changed(self, running: bool) -> None:
        self.toggle_action.setText("Pause sharing" if running else "Start sharing")
        state = "sharing" if running else "paused"
        self.tray.setToolTip(
            f"DualSync — {state}\nClick to open · Double-click to quit"
        )

    def exit(self) -> None:
        try:
            self.engine.stop()
        except Exception:
            log.exception("Audio engine shutdown failed")
        self.settings.was_running = False
        self.store.save(self.settings)
        self.tray.hide()
        self.app.quit()
