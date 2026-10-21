from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / name


def app_icon(size: int = 64) -> QIcon:
    del size
    ico = asset_path("golden-earbuds.ico")
    return QIcon(str(ico if ico.exists() else asset_path("golden-earbuds.png")))
