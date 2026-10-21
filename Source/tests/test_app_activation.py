from __future__ import annotations

import os
import sys

import pytest
from PySide6.QtWidgets import QSystemTrayIcon

from dualsync.services.single_instance import SingleInstance
from dualsync.ui.tray import TrayController


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named objects only")
def test_second_instance_requests_activation() -> None:
    name = f"Local\\DualSync.Test.{os.getpid()}"
    first = SingleInstance(name)
    second = SingleInstance(name)
    try:
        assert not first.already_running
        assert second.already_running
        assert first.activation_requested()
        assert not first.activation_requested()
    finally:
        second.close()
        first.close()


def test_tray_double_click_exits_and_single_click_opens() -> None:
    actions: list[str] = []
    controller = TrayController.__new__(TrayController)
    controller.exit = lambda: actions.append("exit")
    controller.show_popup = lambda: actions.append("open")

    controller._activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    controller._activated(QSystemTrayIcon.ActivationReason.Trigger)

    assert actions == ["exit", "open"]
