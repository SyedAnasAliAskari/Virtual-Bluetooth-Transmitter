from dataclasses import asdict
import json

from dualsync.core.device_manager import DeviceManager

print(json.dumps([asdict(item) for item in DeviceManager().discover()], indent=2))
