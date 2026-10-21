# DualSync 1.2

DualSync is a Windows 11 tray application that captures the current default playback endpoint
through WASAPI loopback and sends synchronized copies to additional active audio endpoints.
Everything runs locally.

The current build uses a black-and-gold visual system and a custom golden-earbuds application,
taskbar, and tray icon.

The interface supports an ordered Primary, Secondary, and up to three additional output slots.
It does **not** claim measured 0–10 ms acoustic synchronization or five simultaneous Bluetooth
streams without matching hardware verification. See
[`Source/docs/FEASIBILITY.md`](Source/docs/FEASIBILITY.md) for confirmed facts and platform limits.

## Folder layout

The project root is intentionally simple:

- `DualSync.exe` — ready-to-run Windows application.
- `README.md` — usage and technical notes.
- `Source/` — Python source, tests, packaging configuration, documentation, and a retained
  legacy archive.

## Install and run

Use 64-bit Python 3.12:

```powershell
cd Source
python -m pip install -r requirements.txt
python main.py
```

Keep the device you want as the primary output selected as the Windows default. In DualSync,
click an output slot or drag a device from **Devices** into it. The first slot is Primary and the
second is Secondary. Use the **ON/OFF** control in the title bar to control sharing. The Windows
default endpoint plays normally; DualSync renders to the secondaries to avoid a feedback cycle.

The close button minimizes DualSync and leaves its taskbar icon available. Right-click the tray
icon for Start/Pause, Settings, and Quit DualSync. Configuration and logs live in
`%LOCALAPPDATA%\DualSync`.

## Calibration

**Estimate timing** saves rough host-buffer offsets inline. It cannot measure Bluetooth codec or
acoustic delay; use each device's 0.1 ms Timing control for final tuning.

The code-level microphone calibration is available as
`dualsync.core.latency_calibrator.AcousticCalibrator`. Place one microphone equidistant from
the devices in a quiet room and call `measure(devices, repeats=3)`. It plays a chirp through
each endpoint independently and stores no recording. Keep Windows microphone enhancements and
automatic gain disabled where possible. Review confidence before applying offsets.

## Validate

```powershell
cd Source
python -m pytest
python -m scripts.list_devices
python -m scripts.audio_smoke_test --seconds 10
```

The smoke test opens the real default loopback and first active secondary output. It does not
prove audible output if the captured stream is silent and it does not measure acoustic delay.

For a proper endurance run, play browser video and a local media file, leave DualSync active
for at least 30 minutes per configuration, and save diagnostics from `%LOCALAPPDATA%\DualSync`.

## Build the Windows executable

```powershell
cd Source
python -m pip install -r requirements-dev.txt
pyinstaller --clean --noconfirm DualSync.spec
```

The windowed build output is `Source\dist\DualSync.exe`; the ready-to-run copy is kept at the
project root. It does not open a console and needs no
administrator privileges. To uninstall, disable **Start DualSync with Windows**, exit the tray
app, delete the executable, then optionally delete `%LOCALAPPDATA%\DualSync`.

## Independent output controls

Each selected secondary output has Pause/Resume, Remove/Rejoin, volume, and live status
controls. These operations affect DualSync routing only; they do not disconnect the Bluetooth
radio link. Use **Bluetooth settings** for Windows-managed connection actions.

DualSync polls active WASAPI endpoints every 2.5 seconds. A disappearing endpoint loses only
its own renderer. If **Automatically rejoin returning devices** is enabled, a returning endpoint
gets a new buffer, its saved volume and calibration offset, and the current mode's synchronization
target without restarting healthy renderers. A change to the Windows default capture endpoint is
detected and requests a sharing restart because changing the loopback source cannot be guaranteed
to be interruption-free.

Each routed secondary also has a **Fine sync** control with 0.1 ms steps. Add a small positive
value to the device heard first; use a negative value when that routed secondary needs to play
slightly earlier. Adjustments change the live buffer target smoothly and are saved per endpoint.
They are software offsets, not acoustic measurements.

## Current scope

- Implemented: active WASAPI discovery, default loopback capture, 1–4 secondary renderers
  (five selected outputs including the primary), stereo/mono conversion, sample-rate
  conversion, independent bounded buffers, drift correction, manual/calibrated delay,
  underrun diagnostics, profiles persistence API, hot refresh, tray lifecycle, per-user
  startup, auto-resume, and single-instance protection.
- V1.1 adds dynamically managed renderer lifecycles, individual volume, endpoint polling,
  failure isolation, remembered disconnected rows, and optional automatic rejoin.
- Hardware-dependent: concurrent Bluetooth capacity, reconnect behavior of each driver,
  acoustic accuracy, sleep/resume stability, and sustained three/five-device playback.
- Not claimed as tested: 30-minute endurance, three/five devices, or 0–10 ms acoustic timing.
