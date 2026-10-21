from __future__ import annotations

import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" -m dualsync.main --minimized'


def set_start_with_windows(enabled: bool) -> None:
    if sys.platform != "win32":
        raise OSError("startup registration is supported only on Windows")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, "DualSync", 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, "DualSync")
            except FileNotFoundError:
                pass


def is_start_with_windows() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, "DualSync")
            return True
    except FileNotFoundError:
        return False
