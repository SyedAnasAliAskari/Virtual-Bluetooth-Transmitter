# DualSync 1.2

DualSync is a Windows 11 application that captures the current default playback endpoint through
WASAPI loopback and routes synchronized copies to additional active audio outputs. Processing is
local to the computer.

The application uses a clean black-and-gold interface with a golden-earbuds icon across the main
window, taskbar, executable, and system tray.

> DualSync does not claim seamless hot-swapping, a guaranteed 1–2 ms acoustic match, or reliable
> five-device Bluetooth playback until those behaviors have been verified with matching hardware.
> See [`Source/docs/FEASIBILITY.md`](Source/docs/FEASIBILITY.md) for Windows and Bluetooth limits.

## Project layout

The project root is intentionally simple:

- `DualSync.exe` — ready-to-run Windows application.
- `README.md` — usage, validation, and technical notes.
- `Source/` — source code, tests, packaging configuration, documentation, and legacy archive.

## Using DualSync

1. Connect the required audio outputs in Windows.
2. Keep the desired source/primary output selected as the Windows default.
3. Open `DualSync.exe`.
4. Select the **Devices** tab to see outputs currently exposed by Windows.
5. Click an empty output slot or drag a connected device into it. The first assigned output is
   Primary, the second is Secondary, and up to five outputs can be selected.
6. Use the **ON/OFF** button in the header to start or pause audio sharing.

The Windows default endpoint continues playing normally. DualSync creates independent renderers
for the additional outputs to avoid a feedback loop.

### Window and tray controls

- **Minimize (−)** hides the main window while DualSync continues running.
- **Close (X)** fully stops and exits DualSync. `Alt+F4` performs the same action.
- Clicking the taskbar icon restores the main window.
- Single-clicking the system-tray icon opens the window.
- Right-clicking the tray icon provides **Open DualSync**, Start/Pause, Settings, and
  **Quit DualSync**.
- Double-clicking or middle-clicking the tray icon exits the application.

Launching `DualSync.exe` while it is already running activates the existing window instead of
starting a second independent instance.

Configuration, calibration profiles, and logs are stored under `%LOCALAPPDATA%\DualSync`.

## Output management

The **Sharing** tab contains the saved routing group. The **Devices** tab contains audio endpoints
currently available through Windows. Disconnected remembered devices are not presented as
currently connected.

Each selected secondary output supports:

- Pause and Resume without interrupting other outputs.
- Remove and Rejoin without restarting unaffected renderers.
- Independent volume.
- A live connection/rendering status.
- Per-device timing adjustment in 0.1 ms steps.

These controls change DualSync routing only; they do not disconnect the Bluetooth radio link. Use
**Bluetooth settings** for Windows-managed connection actions.

DualSync polls active WASAPI endpoints every 2.5 seconds. When an endpoint disappears, only its
renderer is released. If **Automatically rejoin returning devices** is enabled, a returning output
receives a fresh buffer, its saved volume and timing profile, and drift compensation without
restarting healthy renderers.

A change to the Windows default output requires the loopback capture source to restart. DualSync
detects this condition, but that transition is not described as seamless.

## Synchronization and calibration

Use a small positive **Timing** value for the device heard first. A negative value can make a routed
secondary play slightly earlier by reducing its software buffer target. Changes are applied to the
live renderer and saved per endpoint.

**Estimate timing** records rough host-buffer offsets. It does not measure Bluetooth codec,
wireless, speaker, or acoustic delay. Final synchronization should be tuned by ear or measured with
a microphone.

The code-level microphone workflow is available through
`dualsync.core.latency_calibrator.AcousticCalibrator`. Place one microphone equidistant from the
outputs in a quiet room and call `measure(devices, repeats=3)`. Review the confidence result before
applying an offset.

## Run from source

Use 64-bit Python 3.12:

```powershell
cd Source
python -m pip install -r requirements.txt
python main.py
```

## Validate

```powershell
cd Source
python -m pytest
python -m ruff check .
python -m scripts.list_devices
python -m scripts.audio_smoke_test --seconds 10
```

The current automated suite contains 21 passing tests, including independent renderer management,
single-instance activation, and separate minimize/quit window-control behavior.

The audio smoke test opens the real default loopback and first active secondary output. It does not
prove audible playback when the captured stream is silent, and it does not measure acoustic delay.

For endurance testing, play browser video and a local media file, leave DualSync active for at
least 30 minutes per device configuration, and review diagnostics in `%LOCALAPPDATA%\DualSync`.

## Build the executable

```powershell
cd Source
python -m pip install -r requirements-dev.txt
pyinstaller --clean --noconfirm DualSync.spec
```

The windowed build is written to `Source\dist\DualSync.exe`. Copy the verified build to the project
root as `DualSync.exe`. It does not open a console and does not require administrator privileges.

To uninstall, disable **Start DualSync with Windows**, quit DualSync, delete the executable, and
optionally remove `%LOCALAPPDATA%\DualSync`.

## Current implementation status

Implemented:

- Active WASAPI endpoint discovery and default-output loopback capture.
- Five selectable outputs: one Windows primary and up to four secondary renderers.
- Independent renderer cancellation, buffers, volume, timing, failure isolation, and cleanup.
- Sample-rate and channel conversion, bounded buffers, drift correction, and underrun diagnostics.
- Dynamic endpoint removal and optional automatic rejoin with saved profiles.
- Connected-device and saved-sharing-group views with drag-and-drop assignment.
- Taskbar and tray lifecycle, startup integration, auto-resume, and single-instance activation.
- Functional header ON/OFF, minimize, and full-quit controls.

Hardware-dependent and not yet claimed as verified:

- Repeated Bluetooth disconnect/reconnect cycles across several headset models.
- Sustained three-to-five-device playback.
- Thirty-minute multi-device endurance and sleep/resume stability.
- A measured 1–2 ms or 0–10 ms acoustic match between Bluetooth devices.
- Seamless hot-swapping under every Windows audio driver.

The latest local hardware check detected the Realtek Windows output. Multi-device Bluetooth and
acoustic-latency claims still require tests using the intended physical devices.
