import sys
from contextlib import contextmanager

import pytest

from dualsync.core.device_manager import DeviceManager


@pytest.mark.skipif(sys.platform != "win32", reason="WASAPI is Windows-only")
def test_discovers_active_wasapi_render_endpoints():
    devices = DeviceManager().discover()
    assert devices
    assert any(item.is_default for item in devices)
    assert all(item.channels in (1, 2) for item in devices)
    assert len({item.endpoint_id for item in devices}) == len(devices)


class FakeStream:
    def close(self):
        pass


class FakeAudio:
    def get_host_api_info_by_type(self, _api):
        return {"index": 7, "defaultOutputDevice": 1}

    def get_device_count(self):
        return 2

    def get_device_info_by_index(self, index):
        return {
            "hostApi": 7,
            "maxOutputChannels": 2,
            "isLoopbackDevice": False,
            "name": "Speakers" if index == 0 else "Disconnected TWS",
            "defaultSampleRate": 48000,
        }

    def open(self, **kwargs):
        if kwargs["output_device_index"] == 1:
            raise OSError(-9992, "Insufficient memory")
        return FakeStream()


class FakePyAudio:
    paWASAPI = 13
    paFloat32 = 1


def test_discovery_filters_enumerated_but_unusable_endpoint(monkeypatch):
    manager = DeviceManager()

    @contextmanager
    def fake_audio():
        yield FakeAudio(), FakePyAudio

    monkeypatch.setattr(manager, "_audio", fake_audio)
    devices = manager.discover()

    assert [item.name for item in devices] == ["Speakers"]
    assert not devices[0].is_default
