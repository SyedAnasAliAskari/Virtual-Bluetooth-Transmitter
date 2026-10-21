from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from dualsync.services.config import AppSettings
from dualsync.ui.popup import ControlPopup, WindowControlButton


def _popup() -> ControlPopup:
    QApplication.instance() or QApplication([])
    engine = MagicMock()
    engine.running = False
    engine.has_renderer.return_value = False
    engine.metrics.return_value = []
    manager = MagicMock()
    manager.discover.return_value = []
    return ControlPopup(engine, manager, AppSettings(), MagicMock())


def test_close_control_requests_full_application_exit() -> None:
    popup = _popup()
    exit_requests: list[bool] = []
    popup.quit_requested.connect(lambda: exit_requests.append(True))

    close_button = next(
        button for button in popup.findChildren(WindowControlButton)
        if button.objectName() == "closeButton"
    )
    close_button.click()

    assert exit_requests == [True]


def test_minimize_control_does_not_request_exit() -> None:
    popup = _popup()
    exit_requests: list[bool] = []
    popup.quit_requested.connect(lambda: exit_requests.append(True))
    popup.show()

    minimize_button = next(
        button for button in popup.findChildren(WindowControlButton)
        if button.objectName() == "minimizeButton"
    )
    minimize_button.click()
    QApplication.processEvents()

    assert popup.isMinimized()
    assert exit_requests == []
