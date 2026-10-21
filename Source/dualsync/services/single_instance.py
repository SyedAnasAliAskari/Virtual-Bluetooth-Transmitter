from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class SingleInstance:
    def __init__(self, name: str = "Local\\DualSync.V1") -> None:
        self.handle = None
        self.activation_event = None
        self.already_running = False
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.CreateEventW.restype = wintypes.HANDLE
            self.handle = kernel32.CreateMutexW(None, False, name)
            self.already_running = kernel32.GetLastError() == 183
            self.activation_event = kernel32.CreateEventW(
                None, False, False, f"{name}.Activate"
            )
            if self.already_running and self.activation_event:
                kernel32.SetEvent(self.activation_event)

    def activation_requested(self) -> bool:
        """Return true once when a second launch asks the running app to open."""
        if not self.activation_event or sys.platform != "win32":
            return False
        return ctypes.windll.kernel32.WaitForSingleObject(self.activation_event, 0) == 0

    def close(self) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
        if self.activation_event:
            ctypes.windll.kernel32.CloseHandle(self.activation_event)
            self.activation_event = None
