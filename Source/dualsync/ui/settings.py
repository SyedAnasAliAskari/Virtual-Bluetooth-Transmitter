from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from dualsync.core.models import AudioMode
from dualsync.services.config import AppSettings, ConfigStore
from dualsync.services.startup_manager import set_start_with_windows

from .icon import app_icon


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, settings: AppSettings, store: ConfigStore, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.store = store
        self.setWindowTitle("DualSync Settings")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        title = QLabel("Advanced settings")
        title.setObjectName("title")
        layout.addWidget(title)
        form = QFormLayout()
        self.startup = QCheckBox("Start DualSync with Windows")
        self.startup.setChecked(settings.start_with_windows)
        self.resume = QCheckBox("Automatically resume sharing")
        self.resume.setChecked(settings.auto_resume)
        self.rejoin = QCheckBox("Automatically rejoin returning devices")
        self.rejoin.setChecked(settings.auto_rejoin)
        self.restore = QCheckBox("Restore previous devices")
        self.restore.setChecked(settings.restore_devices)
        self.notifications = QCheckBox("Enable notifications")
        self.notifications.setChecked(settings.notifications)
        self.maximum = QSpinBox()
        self.maximum.setRange(2, 5)
        self.maximum.setValue(settings.max_outputs)
        self.mode = QComboBox()
        self.mode.addItems([item.value for item in AudioMode])
        self.mode.setCurrentText(settings.mode)
        form.addRow(self.startup)
        form.addRow(self.resume)
        form.addRow(self.rejoin)
        form.addRow(self.restore)
        form.addRow(self.notifications)
        form.addRow("Maximum outputs", self.maximum)
        form.addRow("Synchronization mode", self.mode)
        layout.addLayout(form)
        reset = QPushButton("Reset configuration")
        reset.setObjectName("danger")
        reset.clicked.connect(self._reset)
        layout.addWidget(reset)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        changed_startup = self.settings.start_with_windows != self.startup.isChecked()
        self.settings.start_with_windows = self.startup.isChecked()
        self.settings.auto_resume = self.resume.isChecked()
        self.settings.auto_rejoin = self.rejoin.isChecked()
        self.settings.restore_devices = self.restore.isChecked()
        self.settings.notifications = self.notifications.isChecked()
        self.settings.max_outputs = self.maximum.value()
        self.settings.mode = self.mode.currentText()
        if changed_startup:
            set_start_with_windows(self.settings.start_with_windows)
        self.store.save(self.settings)
        self.settings_changed.emit()
        self.accept()

    def _reset(self) -> None:
        set_start_with_windows(False)
        self.store.reset()
        self.settings.__dict__.update(AppSettings().__dict__)
        self.settings_changed.emit()
        self.accept()
