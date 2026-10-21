# Build with: pyinstaller --clean --noconfirm DualSync.spec
from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = collect_dynamic_libs("pyaudiowpatch")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=[("dualsync/assets", "dualsync/assets")],
    hiddenimports=["pyaudiowpatch"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DualSync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="dualsync/assets/golden-earbuds.ico",
)
