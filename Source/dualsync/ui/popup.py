from __future__ import annotations

import threading

from PySide6.QtCore import QMimeData, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dualsync.core.audio_engine import AudioEngine
from dualsync.core.device_manager import DeviceManager
from dualsync.core.latency_calibrator import software_calibration
from dualsync.core.models import AudioDevice, AudioMode
from dualsync.services.config import AppSettings, ConfigStore

from .icon import app_icon
from .settings import SettingsDialog

DEVICE_MIME = "application/x-dualsync-endpoint"


class DragHeader(QWidget):
    """A compact title bar that moves its frameless parent window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class WindowControlButton(QToolButton):
    """A precisely centered, high-contrast frameless-window control."""

    def __init__(self, control: str, parent=None) -> None:
        super().__init__(parent)
        self.control = control
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#ffffff"), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        center = self.rect().center()
        if self.control == "close":
            painter.drawLine(center.x() - 5, center.y() - 5,
                             center.x() + 5, center.y() + 5)
            painter.drawLine(center.x() + 5, center.y() - 5,
                             center.x() - 5, center.y() + 5)
        else:
            painter.drawLine(center.x() - 5, center.y(), center.x() + 5, center.y())


class DeviceSlot(QFrame):
    choose_requested = Signal(int)
    assign_requested = Signal(int, str)

    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self.endpoint_id = ""
        self.setObjectName("deviceSlot")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(2)
        self.role = QLabel(self._role_name(index))
        self.role.setObjectName("slotRole")
        self.name = QLabel("+")
        self.name.setObjectName("slotEmpty")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name.setWordWrap(True)
        for label in (self.role, self.name):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.role)
        layout.addWidget(self.name, 1)

    @staticmethod
    def _role_name(index: int) -> str:
        return ["PRIMARY", "SECONDARY", "OUTPUT 3", "OUTPUT 4", "OUTPUT 5"][index]

    def set_device(self, endpoint_id: str, name: str = "") -> None:
        self.endpoint_id = endpoint_id
        self.name.setText(name if endpoint_id else "+")
        self.name.setObjectName("slotName" if endpoint_id else "slotEmpty")
        self.name.style().unpolish(self.name)
        self.name.style().polish(self.name)
        self.setToolTip(name or "Select or drop a connected device")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.choose_requested.emit(self.index)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(DEVICE_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        endpoint_id = bytes(event.mimeData().data(DEVICE_MIME)).decode("utf-8")
        if endpoint_id:
            self.assign_requested.emit(self.index, endpoint_id)
            event.acceptProposedAction()


class DeviceRow(QFrame):
    enable_requested = Signal(str, bool)
    remove_requested = Signal(str)
    rejoin_requested = Signal(str)
    volume_changed = Signal(str, float)
    delay_changed = Signal(str, float)

    def __init__(self, endpoint_id: str, name: str, selected: bool, is_default: bool,
                 volume: float, delay_ms: float, parent=None) -> None:
        super().__init__(parent)
        self.endpoint_id = endpoint_id
        self.is_default = is_default
        self._drag_start: QPoint | None = None
        self.setObjectName("deviceRow")
        root = QVBoxLayout(self)
        root.setContentsMargins(13, 11, 13, 11)
        root.setSpacing(9)
        top = QHBoxLayout()
        self.name = QLabel(name)
        self.name.setToolTip(f"{name}\n{endpoint_id}")
        self.name.setCursor(Qt.CursorShape.OpenHandCursor)
        self.name.setMinimumWidth(0)
        self.name.setMaximumWidth(245)
        self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status = QLabel("Available")
        self.status.setObjectName("deviceStatus")
        top.addWidget(self.name, 1)
        top.addWidget(self.status)
        root.addLayout(top)
        audio_controls = QHBoxLayout()
        audio_controls.setSpacing(9)
        actions = QHBoxLayout()
        actions.setSpacing(7)
        self.enable = QPushButton("Pause")
        self.enable.clicked.connect(self._toggle)
        self.rejoin = QPushButton("Rejoin")
        self.rejoin.clicked.connect(lambda: self.rejoin_requested.emit(self.endpoint_id))
        self.remove = QPushButton("Remove" if selected else "Add")
        self.remove.clicked.connect(lambda: self.remove_requested.emit(self.endpoint_id))
        self.volume_label = QLabel("100%")
        self.volume_label.setObjectName("value")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(volume * 100))
        self.volume.setMinimumWidth(90)
        self.volume.valueChanged.connect(self._volume_changed)
        self.delay = QDoubleSpinBox()
        self.delay.setRange(-30.0, 250.0)
        self.delay.setDecimals(1)
        self.delay.setSingleStep(0.1)
        self.delay.setSuffix(" ms")
        self.delay.setValue(delay_ms)
        self.delay.setKeyboardTracking(False)
        self.delay.setFixedWidth(74)
        self.delay.setToolTip(
            "Fine sync: add delay to the device heard first. Negative values make this "
            "renderer play earlier by reducing its software buffer."
        )
        self.delay.valueChanged.connect(
            lambda value: self.delay_changed.emit(self.endpoint_id, value)
        )
        self.volume_title = QLabel("Volume")
        self.delay_title = QLabel("Timing")
        self.volume_title.setObjectName("fieldLabel")
        self.delay_title.setObjectName("fieldLabel")
        audio_controls.addWidget(self.volume_title)
        audio_controls.addWidget(self.volume, 1)
        audio_controls.addWidget(self.volume_label)
        audio_controls.addSpacing(8)
        audio_controls.addWidget(self.delay_title)
        audio_controls.addWidget(self.delay)
        actions.addStretch()
        actions.addWidget(self.enable)
        actions.addWidget(self.rejoin)
        actions.addWidget(self.remove)
        root.addLayout(audio_controls)
        root.addLayout(actions)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(DEVICE_MIME, self.endpoint_id.encode("utf-8"))
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
            self._drag_start = None
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def _toggle(self) -> None:
        self.enable_requested.emit(self.endpoint_id, self.enable.text() != "Resume")

    def _volume_changed(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(self.endpoint_id, value / 100.0)

    def update_state(self, *, selected: bool, available: bool, enabled: bool,
                     rendering: bool, sharing_active: bool, state: str = "") -> None:
        self.remove.setText("Remove" if selected else "Add")
        controls_visible = selected and available and not self.is_default
        self.enable.setVisible(controls_visible)
        self.rejoin.setVisible(
            controls_visible and sharing_active and enabled and not rendering
        )
        self.volume.setVisible(controls_visible)
        self.volume_label.setVisible(controls_visible)
        self.volume_title.setVisible(controls_visible)
        self.delay.setVisible(controls_visible)
        self.delay_title.setVisible(controls_visible)
        if self.is_default:
            self.status.setText("Windows primary" if available else "Default changed")
            self.enable.setToolTip("The primary endpoint is controlled by Windows.")
        elif not selected:
            self.status.setText("Connected" if available else "Unavailable")
        elif not available:
            self.status.setText("Offline · remembered")
        elif not sharing_active:
            self.status.setText("Ready")
        elif rendering:
            self.status.setText("Sharing")
        elif not enabled:
            self.status.setText("Paused")
        elif state:
            self.status.setText("Output error")
            self.status.setToolTip(state)
        else:
            self.status.setText("Ready to rejoin")
            self.status.setToolTip("")
        self.enable.setText("Pause" if enabled else "Resume")
        self.enable.setEnabled(available)
        self.rejoin.setEnabled(available)
        self.remove.setEnabled(available or selected)


class ControlPopup(QFrame):
    sharing_changed = Signal(bool)
    quit_requested = Signal()
    devices_polled = Signal(object, str)

    def __init__(self, engine: AudioEngine, manager: DeviceManager,
                 settings: AppSettings, store: ConfigStore) -> None:
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowIcon(app_icon())
        self.setWindowTitle("DualSync")
        self.setObjectName("popup")
        self.setFixedSize(560, 760)
        self.engine = engine
        self.manager = manager
        self.settings = settings
        self.store = store
        self.devices: list[AudioDevice] = []
        self.rows: dict[str, list[DeviceRow]] = {}
        self.renderer_errors: dict[str, str] = {}
        self._busy = False
        self._polling = False
        self._restart_pending = False
        self._capture_default_id = ""
        self._awaiting_slot: int | None = None
        self.devices_polled.connect(self._on_devices_polled)
        self._build()
        self.refresh_devices()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._refresh_metrics)
        self.timer.start()
        self.device_timer = QTimer(self)
        self.device_timer.setInterval(2500)
        self.device_timer.timeout.connect(self._poll_devices)
        self.device_timer.start()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(11)
        header = DragHeader(self)
        top = QHBoxLayout(header)
        top.setContentsMargins(0, 0, 0, 0)
        brand_icon = QLabel()
        brand_icon.setPixmap(app_icon().pixmap(36, 36))
        brand_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title = QLabel("DualSync")
        title.setObjectName("title")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.status = QPushButton("OFF")
        self.status.setObjectName("statusOff")
        self.status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status.setToolTip("Start or stop DualSync audio sharing")
        self.status.clicked.connect(self.toggle_sharing)
        top.addWidget(brand_icon)
        top.addSpacing(5)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.status)
        minimize_button = WindowControlButton("minimize", self)
        minimize_button.setObjectName("minimizeButton")
        minimize_button.setAccessibleName("Minimize DualSync")
        minimize_button.setToolTip("Minimize DualSync")
        minimize_button.clicked.connect(self.showMinimized)
        top.addWidget(minimize_button)
        close_button = WindowControlButton("close", self)
        close_button.setObjectName("closeButton")
        close_button.setAccessibleName("Quit DualSync")
        close_button.setToolTip("Quit DualSync")
        close_button.clicked.connect(self.close)
        top.addWidget(close_button)
        root.addWidget(header)
        self.subtitle = QLabel("System audio sharing is paused")
        self.subtitle.setObjectName("muted")
        root.addWidget(self.subtitle)

        slots_header = QHBoxLayout()
        slots_label = QLabel("OUTPUT SLOTS")
        slots_label.setObjectName("eyebrow")
        slots_help = QLabel("Click a + or drag a connected device")
        slots_help.setObjectName("muted")
        slots_header.addWidget(slots_label)
        slots_header.addStretch()
        slots_header.addWidget(slots_help)
        root.addLayout(slots_header)
        slot_row = QHBoxLayout()
        slot_row.setSpacing(7)
        self.slots: list[DeviceSlot] = []
        for index in range(5):
            slot = DeviceSlot(index, self)
            slot.choose_requested.connect(self._choose_slot_device)
            slot.assign_requested.connect(self._assign_to_slot)
            self.slots.append(slot)
            slot_row.addWidget(slot, 1)
        root.addLayout(slot_row)

        source = QFrame()
        source.setObjectName("sourceBar")
        source_layout = QHBoxLayout(source)
        source_layout.setContentsMargins(12, 9, 12, 9)
        source_label = QLabel("WINDOWS AUDIO SOURCE")
        source_label.setObjectName("eyebrow")
        self.source_name = QLabel("Detecting…")
        self.source_name.setObjectName("sourceName")
        source_layout.addWidget(source_label)
        source_layout.addStretch()
        source_layout.addWidget(self.source_name)
        root.addWidget(source)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("deviceTabs")

        sharing_page = QWidget()
        sharing_root = QVBoxLayout(sharing_page)
        sharing_root.setContentsMargins(0, 10, 0, 0)
        sharing_root.setSpacing(8)
        sharing_header = QHBoxLayout()
        sharing_hint = QLabel("Saved sharing group")
        sharing_hint.setObjectName("sectionTitle")
        self.count = QLabel("0 of 5")
        self.count.setObjectName("muted")
        sharing_header.addWidget(sharing_hint)
        sharing_header.addStretch()
        sharing_header.addWidget(self.count)
        sharing_root.addLayout(sharing_header)
        sharing_scroll = QScrollArea()
        sharing_scroll.setWidgetResizable(True)
        sharing_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sharing_box = QWidget()
        self.sharing_layout = QVBoxLayout(self.sharing_box)
        self.sharing_layout.setContentsMargins(0, 0, 0, 0)
        self.sharing_layout.setSpacing(8)
        self.sharing_layout.addStretch()
        sharing_scroll.setWidget(self.sharing_box)
        sharing_root.addWidget(sharing_scroll, 1)
        sharing_note = QLabel(
            "Remove changes the DualSync group only; it never disconnects Bluetooth."
        )
        sharing_note.setObjectName("muted")
        sharing_note.setWordWrap(True)
        sharing_root.addWidget(sharing_note)

        devices_page = QWidget()
        devices_root = QVBoxLayout(devices_page)
        devices_root.setContentsMargins(0, 10, 0, 0)
        devices_root.setSpacing(8)
        devices_header = QHBoxLayout()
        devices_hint = QLabel("Connected Windows outputs")
        devices_hint.setObjectName("sectionTitle")
        refresh = QPushButton("Refresh")
        refresh.setObjectName("compact")
        refresh.clicked.connect(self.refresh_devices)
        bluetooth = QPushButton("Bluetooth settings")
        bluetooth.setObjectName("compact")
        bluetooth.clicked.connect(self.manager.open_bluetooth_settings)
        devices_header.addWidget(devices_hint)
        devices_header.addStretch()
        devices_header.addWidget(refresh)
        devices_header.addWidget(bluetooth)
        devices_root.addLayout(devices_header)
        available_scroll = QScrollArea()
        available_scroll.setWidgetResizable(True)
        available_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.available_box = QWidget()
        self.available_layout = QVBoxLayout(self.available_box)
        self.available_layout.setContentsMargins(0, 0, 0, 0)
        self.available_layout.setSpacing(8)
        self.available_layout.addStretch()
        available_scroll.setWidget(self.available_box)
        devices_root.addWidget(available_scroll, 1)

        self.tabs.addTab(sharing_page, "Sharing")
        self.tabs.addTab(devices_page, "Devices")
        root.addWidget(self.tabs, 1)

        sync_label = QLabel("PLAYBACK SYNC")
        sync_label.setObjectName("eyebrow")
        root.addWidget(sync_label)
        mode_row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems([item.value for item in AudioMode])
        self.mode.setCurrentText(self.settings.mode)
        self.mode.currentTextChanged.connect(self._mode_changed)
        self.mode.setToolTip("Playback buffering mode")
        calibrate = QPushButton("Estimate timing")
        calibrate.setToolTip(
            "Estimate host buffer differences; use each device's Timing field for final tuning"
        )
        calibrate.clicked.connect(self._calibrate)
        mode_row.addWidget(self.mode, 1)
        mode_row.addWidget(calibrate)
        root.addLayout(mode_row)
        self.health = QLabel("Software timing: idle | Acoustic timing: not measured")
        self.health.setObjectName("muted")
        self.health.setWordWrap(True)
        root.addWidget(self.health)

        bottom = QHBoxLayout()
        quit_button = QPushButton("Quit")
        quit_button.setObjectName("danger")
        quit_button.setToolTip("Stop sharing and exit DualSync")
        quit_button.clicked.connect(self.quit_requested.emit)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self._settings)
        bottom.addWidget(quit_button)
        bottom.addWidget(settings_button)
        bottom.addStretch()
        root.addLayout(bottom)

    def _discover(self) -> list[AudioDevice]:
        return self.manager.discover()

    @staticmethod
    def _clear_device_layout(layout: QVBoxLayout) -> None:
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _add_empty_state(layout: QVBoxLayout, title: str, detail: str) -> None:
        card = QFrame()
        card.setObjectName("emptyState")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("emptyTitle")
        message = QLabel(detail)
        message.setObjectName("muted")
        message.setWordWrap(True)
        card_layout.addWidget(heading)
        card_layout.addWidget(message)
        layout.insertWidget(0, card)

    def refresh_devices(self, *_ignored) -> None:
        try:
            discovered = self._discover()
        except Exception as exc:
            QMessageBox.warning(self, "Device discovery failed", str(exc))
            return
        self._apply_discovered(discovered)

    def _apply_discovered(
        self, discovered: list[AudioDevice], *, auto_add_new: bool = False
    ) -> None:
        previous = {item.endpoint_id: item for item in self.devices}
        previous_ids = set(previous)
        self.devices = discovered
        for device in discovered:
            self.settings.known_device_names[device.endpoint_id] = device.name

        if auto_add_new and self.settings.auto_rejoin:
            new_devices = [item for item in discovered if item.endpoint_id not in previous_ids]
            for device in new_devices:
                if device.endpoint_id in self.settings.selected_endpoint_ids:
                    continue
                if len(self.settings.selected_endpoint_ids) >= self.settings.max_outputs:
                    break
                if self._awaiting_slot is not None:
                    self._assign_to_slot(
                        self._awaiting_slot, device.endpoint_id, refresh=False
                    )
                    self._awaiting_slot = None
                else:
                    self.settings.selected_endpoint_ids.append(device.endpoint_id)
                    self.settings.device_enabled[device.endpoint_id] = True

        self._clear_device_layout(self.sharing_layout)
        self._clear_device_layout(self.available_layout)
        self.rows.clear()
        current = {item.endpoint_id: item for item in discovered}
        default = next((item for item in discovered if item.is_default), None)
        self.source_name.setText(default.name if default else "No Windows default output")

        selected_ids = list(dict.fromkeys(self.settings.selected_endpoint_ids))
        self.settings.selected_endpoint_ids = selected_ids[:self.settings.max_outputs]
        selected_ids = self.settings.selected_endpoint_ids

        for endpoint_id in selected_ids:
            device = current.get(endpoint_id) or previous.get(endpoint_id)
            name = (device.name if device else
                    self.settings.known_device_names.get(endpoint_id, "Unavailable device"))
            row = DeviceRow(
                endpoint_id, name, True, bool(device and device.is_default),
                self.settings.device_volumes.get(endpoint_id, 1.0),
                self.settings.delays_ms.get(endpoint_id, 0.0), self,
            )
            row.enable_requested.connect(self._set_device_enabled)
            row.remove_requested.connect(self._toggle_membership)
            row.rejoin_requested.connect(self._rejoin)
            row.volume_changed.connect(self._set_volume)
            row.delay_changed.connect(self._set_delay)
            self.rows.setdefault(endpoint_id, []).append(row)
            self.sharing_layout.insertWidget(self.sharing_layout.count() - 1, row)

        for device in discovered:
            selected = device.endpoint_id in selected_ids
            row = DeviceRow(
                device.endpoint_id, device.name, selected, device.is_default,
                self.settings.device_volumes.get(device.endpoint_id, 1.0),
                self.settings.delays_ms.get(device.endpoint_id, 0.0), self,
            )
            row.remove_requested.connect(self._toggle_membership)
            row.enable_requested.connect(self._set_device_enabled)
            row.rejoin_requested.connect(self._rejoin)
            row.volume_changed.connect(self._set_volume)
            row.delay_changed.connect(self._set_delay)
            self.rows.setdefault(device.endpoint_id, []).append(row)
            self.available_layout.insertWidget(self.available_layout.count() - 1, row)

        if not selected_ids:
            self._add_empty_state(
                self.sharing_layout,
                "No outputs in your sharing group",
                "Open Devices and add a connected output to begin.",
            )
        if not discovered:
            self._add_empty_state(
                self.available_layout,
                "No audio outputs connected",
                "Connect an audio device in Windows, then select Refresh.",
            )
        self.tabs.setTabText(0, f"Sharing  {len(selected_ids)}")
        self.tabs.setTabText(1, f"Devices  {len(discovered)}")
        self._refresh_slots(current)
        self._sync_dynamic_renderers(previous, current)
        self._update_rows()
        self.store.save(self.settings)

    def _poll_devices(self) -> None:
        if self._polling:
            return
        self._polling = True
        threading.Thread(
            target=self._poll_devices_worker,
            name="device-discovery",
            daemon=True,
        ).start()

    def _poll_devices_worker(self) -> None:
        try:
            current = self._discover()
        except Exception as exc:
            self.devices_polled.emit(None, str(exc))
            return
        self.devices_polled.emit(current, "")

    def _on_devices_polled(self, current, error: str) -> None:
        self._polling = False
        if error or current is None:
            return
        old_signature = {(d.endpoint_id, d.pa_index, d.is_default) for d in self.devices}
        new_signature = {(d.endpoint_id, d.pa_index, d.is_default) for d in current}
        if old_signature != new_signature:
            self._apply_discovered(current, auto_add_new=True)

    def _refresh_slots(self, current: dict[str, AudioDevice]) -> None:
        selected = self.settings.selected_endpoint_ids
        for index, slot in enumerate(self.slots):
            slot.setVisible(index < self.settings.max_outputs)
            if index >= self.settings.max_outputs:
                continue
            if index < len(selected):
                endpoint_id = selected[index]
                device = current.get(endpoint_id)
                name = (
                    device.name if device else
                    f"{self.settings.known_device_names.get(endpoint_id, 'Saved device')}\nOffline"
                )
                slot.set_device(endpoint_id, name)
            else:
                slot.set_device("")

    def _choose_slot_device(self, index: int) -> None:
        if index >= self.settings.max_outputs:
            return
        if not self.devices:
            answer = QMessageBox.question(
                self,
                "Connect an audio device",
                "No usable audio output is connected. Open Windows Bluetooth settings?\n\n"
                "The next device Windows discovers will be placed in this slot automatically.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._awaiting_slot = index
                self.manager.open_bluetooth_settings()
            return

        menu = QMenu(self)
        current_id = (
            self.settings.selected_endpoint_ids[index]
            if index < len(self.settings.selected_endpoint_ids) else ""
        )
        for device in self.devices:
            label = f"✓  {device.name}" if device.endpoint_id == current_id else device.name
            action = menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, slot=index, endpoint=device.endpoint_id:
                self._assign_to_slot(slot, endpoint)
            )
        menu.addSeparator()
        connect_new = menu.addAction("Connect a new device…")
        connect_new.triggered.connect(
            lambda: self._open_connection_for_slot(index)
        )
        if current_id:
            remove = menu.addAction("Clear this slot")
            remove.triggered.connect(lambda: self._toggle_membership(current_id))
        slot = self.slots[index]
        menu.exec(slot.mapToGlobal(QPoint(0, slot.height())))

    def _open_connection_for_slot(self, index: int) -> None:
        self._awaiting_slot = index
        self.manager.open_bluetooth_settings()

    def _assign_to_slot(
        self, index: int, endpoint_id: str, *, refresh: bool = True
    ) -> None:
        if index >= self.settings.max_outputs:
            return
        current = {item.endpoint_id: item for item in self.devices}
        if endpoint_id not in current:
            if refresh:
                QMessageBox.information(
                    self, "Device unavailable", "That device is no longer connected to Windows."
                )
            return
        old_ids = list(self.settings.selected_endpoint_ids)
        selected = list(old_ids)
        if endpoint_id in selected:
            selected.remove(endpoint_id)
        selected.insert(min(index, len(selected)), endpoint_id)
        selected = selected[:self.settings.max_outputs]
        self.settings.selected_endpoint_ids = selected
        self.settings.device_enabled[endpoint_id] = True

        removed = set(old_ids) - set(selected)
        for removed_id in removed:
            self.engine.remove_renderer(removed_id)
        if self.engine.running and endpoint_id not in old_ids:
            self._add_device_renderer(current[endpoint_id])
        self.store.save(self.settings)
        if refresh:
            self._apply_discovered(self.devices)

    def _sync_dynamic_renderers(self, previous: dict[str, AudioDevice],
                                current: dict[str, AudioDevice]) -> None:
        if not self.engine.running:
            return
        for endpoint_id in self.engine.renderer_ids() - current.keys():
            self.engine.remove_renderer(endpoint_id)
        for endpoint_id in self.settings.selected_endpoint_ids:
            device = current.get(endpoint_id)
            enabled = self.settings.device_enabled.get(endpoint_id, True)
            returning = endpoint_id not in previous and device is not None
            if (device and not device.is_default and enabled and self.settings.auto_rejoin
                    and (returning or not self.engine.has_renderer(endpoint_id))):
                self._add_device_renderer(device)
        defaults = [device for device in current.values() if device.is_default]
        default_id = defaults[0].endpoint_id if defaults else ""
        if self._capture_default_id and not default_id:
            self.stop_sharing()
            self.subtitle.setText("No usable Windows default output is connected")
            return
        if default_id and default_id != self._capture_default_id and not self._restart_pending:
            self._restart_pending = True
            self.subtitle.setText("Windows audio source changed · restarting capture…")
            QTimer.singleShot(0, self._restart_after_source_change)

    def _restart_after_source_change(self) -> None:
        try:
            if self.engine.running:
                self.stop_sharing()
                self.start_sharing()
        finally:
            self._restart_pending = False

    def selected_devices(self) -> list[AudioDevice]:
        selected = set(self.settings.selected_endpoint_ids)
        return [item for item in self.devices if item.endpoint_id in selected]

    def _toggle_membership(self, endpoint_id: str) -> None:
        if endpoint_id in self.settings.selected_endpoint_ids:
            self.engine.remove_renderer(endpoint_id)
            self.settings.selected_endpoint_ids.remove(endpoint_id)
            self.settings.device_enabled.pop(endpoint_id, None)
            self.renderer_errors.pop(endpoint_id, None)
        else:
            if len(self.settings.selected_endpoint_ids) >= self.settings.max_outputs:
                QMessageBox.information(
                    self, "Output limit", f"The configured limit is {self.settings.max_outputs}."
                )
                return
            self.settings.selected_endpoint_ids.append(endpoint_id)
            self.settings.device_enabled[endpoint_id] = True
            device = next((d for d in self.devices if d.endpoint_id == endpoint_id), None)
            if self.engine.running and device and not device.is_default:
                self._add_device_renderer(device)
        self.store.save(self.settings)
        self.refresh_devices()

    def _set_device_enabled(self, endpoint_id: str, pause: bool) -> None:
        enabled = not pause
        self.settings.device_enabled[endpoint_id] = enabled
        if enabled:
            self._rejoin(endpoint_id)
        else:
            self.engine.remove_renderer(endpoint_id)
        self.store.save(self.settings)
        self._update_rows()

    def _rejoin(self, endpoint_id: str) -> None:
        self.settings.device_enabled[endpoint_id] = True
        device = next((d for d in self.devices if d.endpoint_id == endpoint_id), None)
        if not device:
            QMessageBox.information(
                self, "Device unavailable",
                "Windows is not exposing this device as an active audio endpoint. Connect it in "
                "Bluetooth Settings, then DualSync can rejoin it.",
            )
        elif self.engine.running:
            self.renderer_errors.pop(endpoint_id, None)
            self._add_device_renderer(device)
        self.store.save(self.settings)
        self._update_rows()

    def _add_device_renderer(self, device: AudioDevice) -> None:
        try:
            self.engine.add_renderer(
                device,
                delay_ms=self.settings.delays_ms.get(device.endpoint_id, 0.0),
                volume=self.settings.device_volumes.get(device.endpoint_id, 1.0),
            )
        except Exception as exc:
            self.renderer_errors[device.endpoint_id] = str(exc)

    def _set_volume(self, endpoint_id: str, volume: float) -> None:
        self.settings.device_volumes[endpoint_id] = volume
        self.engine.set_renderer_volume(endpoint_id, volume)
        self.store.save(self.settings)

    def _set_delay(self, endpoint_id: str, delay_ms: float) -> None:
        self.settings.delays_ms[endpoint_id] = delay_ms
        self.engine.set_renderer_delay(endpoint_id, delay_ms)
        self.store.save(self.settings)

    def _update_rows(self) -> None:
        available = {item.endpoint_id for item in self.devices}
        defaults = {item.endpoint_id for item in self.devices if item.is_default}
        selected = set(self.settings.selected_endpoint_ids)
        for endpoint_id, endpoint_rows in self.rows.items():
            for row in endpoint_rows:
                row.is_default = endpoint_id in defaults
                row.update_state(
                    selected=endpoint_id in selected,
                    available=endpoint_id in available,
                    enabled=self.settings.device_enabled.get(endpoint_id, True),
                    rendering=self.engine.has_renderer(endpoint_id),
                    sharing_active=self.engine.running,
                    state=self.renderer_errors.get(endpoint_id, ""),
                )
        self.count.setText(f"{len(selected)} of {self.settings.max_outputs}")

    def toggle_sharing(self) -> None:
        self.stop_sharing() if self.engine.running else self.start_sharing()

    def start_sharing(self) -> None:
        if self._busy:
            return
        devices = self.selected_devices()
        if len(devices) < 2:
            QMessageBox.information(
                self, "Two outputs required",
                "Assign a connected Primary and Secondary output before turning DualSync on.",
            )
            return
        enabled = [
            item for item in devices
            if item.is_default or self.settings.device_enabled.get(item.endpoint_id, True)
        ]
        if not enabled:
            QMessageBox.information(self, "Outputs paused", "Resume at least one output first.")
            return
        self._busy = True
        self.status.setEnabled(False)
        try:
            self.engine.start(
                enabled, AudioMode(self.mode.currentText()), self.settings.delays_ms,
                self.settings.device_volumes,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not start sharing", str(exc))
            return
        finally:
            self._busy = False
            self.status.setEnabled(True)
        self.settings.was_running = True
        default = next((item for item in self.devices if item.is_default), None)
        self._capture_default_id = default.endpoint_id if default else ""
        self.store.save(self.settings)
        self._set_power_state(True)

    def stop_sharing(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status.setEnabled(False)
        try:
            self.engine.stop()
        except Exception as exc:
            QMessageBox.warning(self, "Audio shutdown warning", str(exc))
        finally:
            self._busy = False
            self.status.setEnabled(True)
        self.settings.was_running = False
        self._capture_default_id = ""
        self.store.save(self.settings)
        self._set_power_state(False)

    def _set_power_state(self, running: bool) -> None:
        self.status.setText("ON" if running else "OFF")
        self.status.setObjectName("statusOn" if running else "statusOff")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.subtitle.setText(
            f"Capturing {self.engine.primary_name}"
            if running else "System audio sharing is paused"
        )
        if not running:
            self.health.setText("Software timing: idle | Acoustic timing: not measured")
        self._update_rows()
        self.sharing_changed.emit(running)

    def renderer_failed(self, endpoint_id: str, message: str) -> None:
        self.renderer_errors[endpoint_id] = message
        self._update_rows()

    def _refresh_metrics(self) -> None:
        self._update_rows()
        metrics = self.engine.metrics()
        if not metrics:
            if self.engine.running:
                self.health.setText("Capture active | No secondary outputs currently sharing")
            return
        worst = max((item.buffer_ms for item in metrics), default=0)
        underruns = sum(item.underruns for item in metrics)
        drift = max((abs(item.drift_ppm) for item in metrics), default=0)
        self.health.setText(
            f"Software estimate | buffer {worst:.0f} ms | drift <= {drift:.0f} ppm | "
            f"underruns {underruns}\nAcoustic timing: not measured"
        )

    def _mode_changed(self, value: str) -> None:
        self.settings.mode = value
        self.store.save(self.settings)

    def _calibrate(self) -> None:
        devices = self.selected_devices()
        if len(devices) < 2:
            QMessageBox.information(
                self, "Timing estimate",
                "Connect and assign at least two outputs before estimating sync.",
            )
            return
        try:
            records = software_calibration(devices)
            for record in records:
                self.settings.set_calibration(record)
            self.store.save(self.settings)
            self.health.setText(
                "Software timing estimate saved · Fine-tune each Timing value by ear"
            )
            self._update_rows()
        except Exception as exc:
            QMessageBox.warning(self, "Timing estimate failed", str(exc))

    def _settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.store, self)
        dialog.settings_changed.connect(self.refresh_devices)
        dialog.exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.quit_requested.emit()
