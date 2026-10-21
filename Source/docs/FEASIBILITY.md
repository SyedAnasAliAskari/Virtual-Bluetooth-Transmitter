# DualSync Phase 1 feasibility record

Date: 2026-10-21. Target: Windows 11 on the supplied ThinkPad T580.

## Architecture decision

DualSync uses the Windows WASAPI shared-mode backend in PortAudio through PyAudioWPatch.
PyAudioWPatch is required because standard PyAudio and python-sounddevice do not expose a
portable Windows loopback capture switch. It creates input views of active render endpoints,
then PortAudio calls `IAudioClient` for capture and render. The UI never runs in an audio
callback.

The Windows default render endpoint is the capture source and remains the primary audible
output. DualSync does not render the captured stream back to that endpoint: doing so would
recapture its own output and create feedback. It renders copies only to selected secondary
endpoints. Consequently a two-device session consists of the normal default device plus one
DualSync renderer.

Each secondary owns a bounded ring buffer, blocking render stream, sample-rate converter,
manual offset and a bounded PI drift controller. Overflow drops the oldest audio. Underflow
inserts silence and is counted. Correction is limited to ±250 ppm, so it cannot run away.

## Confirmed on this machine

- Python 3.12.10 is installed.
- PortAudio enumerates Windows WASAPI.
- Active stereo render endpoints at inspection time: `Headphones (2- TWS)` (default,
  48 kHz) and `Speaker/HP (Realtek High Definition Audio)` (48 kHz).
- A loopback endpoint exists for each active renderer.
- Several paired Bluetooth devices appear through WDM-KS but are not active WASAPI render
  endpoints. DualSync intentionally does not present these as usable.

## Hard platform limits

- Classic Bluetooth A2DP devices have independent codec, radio and device buffers. WASAPI
  timestamps do not reveal final acoustic arrival time.
- Windows and the Bluetooth adapter decide how many A2DP links can stream concurrently.
  Five selections are supported by the application, not guaranteed by this laptop/radio.
- A device must already be paired and expose an active WASAPI render endpoint. DualSync can
  open Windows Bluetooth Settings but cannot safely force a profile connection.
- Shared mode is chosen for compatibility and format conversion. An application cannot make
  unrelated Bluetooth clocks share a hardware clock.
- The generated `wasapi:<hash>` identifier is a persistent signature derived from the active
  endpoint name/format because PortAudio does not expose the underlying IMMDevice endpoint
  GUID. Duplicate identically named devices cannot be disambiguated reliably in V1.

## Meaning of measurements

Runtime buffer depth, underflow count and drift correction are software-observable. They are
not acoustic synchronization measurements. Software calibration has intentionally low
confidence. Microphone calibration sequentially plays chirps, detects arrivals by normalized
cross-correlation, repeats measurements and stores relative delay plus confidence. Microphone
position, room reflections, noise suppression and device DSP remain sources of uncertainty.

The 0–10 ms target is aspirational and must not be displayed as achieved until repeated
microphone or external measurement establishes it.

## V1.1 dynamic renderer behavior

Each secondary renderer now owns its cancellation event. The capture callback snapshots the
renderer registry under a lock and feeds outside that lock. Removing or failing one renderer
therefore does not mutate a collection being iterated and does not signal healthy renderers.
Capture intentionally remains active when the registry becomes empty, allowing a returning
endpoint to rejoin the live timeline.

Endpoint presence is polled through active WASAPI discovery. This detects the observable effect
of earbuds entering a charging case (the endpoint disappears), but Windows does not provide a
portable guarantee that every model removes its endpoint immediately. Bluetooth radio disconnect
is left to Windows Settings. A rejoining renderer restores its saved delay and volume and fills a
fresh buffer to the selected mode target. This is a software alignment strategy, not a claim of
seamless or acoustically verified hot-swapping.

## Expansion gates

1. One secondary renderer must pass a 30-minute browser and local-media run with no engine
   crash and acceptable underflow count.
2. Connect a second active Bluetooth stereo endpoint; repeat the run and perform acoustic
   calibration.
3. Add third, then fourth secondary only after the prior configuration is stable.
4. Stop at the first adapter/driver connection failure and report that as the tested hardware
   limit. Do not count inactive or hands-free endpoints as successful outputs.
