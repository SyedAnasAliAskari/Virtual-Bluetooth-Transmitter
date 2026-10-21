from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager

from .models import AudioDevice

log = logging.getLogger(__name__)


def _friendly_name(name: str) -> str:
    return name.replace(" [Loopback]", "").strip()


class DeviceManager:
    """Discovers active render endpoints exposed by PortAudio's WASAPI host."""

    @contextmanager
    def _audio(self):
        import pyaudiowpatch as pyaudio

        audio = pyaudio.PyAudio()
        try:
            yield audio, pyaudio
        finally:
            audio.terminate()

    def discover(self) -> list[AudioDevice]:
        devices: list[AudioDevice] = []
        with self._audio() as (audio, pyaudio):
            host = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_index = int(host.get("defaultOutputDevice", -1))
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if int(info.get("hostApi", -1)) != int(host["index"]):
                    continue
                channels = int(info.get("maxOutputChannels", 0))
                if channels <= 0 or info.get("isLoopbackDevice", False):
                    continue
                name = _friendly_name(str(info["name"]))
                rate = int(float(info["defaultSampleRate"]))
                output_channels = min(2, channels)
                stream = None
                try:
                    # WASAPI may retain a disconnected Bluetooth endpoint in its
                    # enumeration. Opening it is the reliable availability check.
                    stream = audio.open(
                        format=pyaudio.paFloat32,
                        channels=output_channels,
                        rate=rate,
                        output=True,
                        output_device_index=index,
                        frames_per_buffer=max(128, int(rate * 0.01)),
                        start=False,
                    )
                except Exception as exc:
                    log.info("Ignoring unavailable endpoint %s: %s", name, exc)
                    continue
                finally:
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            log.debug("Endpoint probe close failed: %s", name, exc_info=True)
                signature = f"{name.casefold()}|{channels}|{rate}"
                digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:20]
                devices.append(
                    AudioDevice(
                        endpoint_id=f"wasapi:{digest}",
                        name=name,
                        pa_index=index,
                        channels=output_channels,
                        sample_rate=rate,
                        is_default=index == default_index,
                        is_bluetooth=any(
                            token in name.casefold()
                            for token in ("bluetooth", "headphones", "headset", "earbuds")
                        ),
                        supported_formats=[f"{rate} Hz / {min(2, channels)} ch / float32"],
                    )
                )
        return devices

    def default_loopback(self) -> dict:
        with self._audio() as (audio, _):
            return dict(audio.get_default_wasapi_loopback())

    @staticmethod
    def open_bluetooth_settings() -> None:
        import os

        os.startfile("ms-settings:bluetooth")  # noqa: S606 - intentional Windows settings URI
