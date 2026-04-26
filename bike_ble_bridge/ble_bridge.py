import asyncio
import json
import urllib.request
from datetime import datetime, timezone

from bless import BlessServer, BlessGATTCharacteristic
from bless.backends.characteristic import (
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)


# -------------------------------------------------
# BLE UUIDs expected by the Flutter app
# -------------------------------------------------
SERVICE_UUID = "19B10000-E8F2-537E-4F6C-D104768A1214"
DATA_CHAR_UUID = "19B10011-E8F2-537E-4F6C-D104768A1214"

DEVICE_NAME = "Qualcomm Edge Node"


# -------------------------------------------------
# App Lab endpoint
# -------------------------------------------------
SENSOR_HTTP_URL = "http://172.22.0.2:8765/latest"


# -------------------------------------------------
# BLE payload state
# -------------------------------------------------
latest_payload = {
    "humidity_percent": None,
    "temperature_c": None,
    "timestamp": None,
    "toxicity_level": None,
    "trash_detected": False,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def read_sensor_payload():
    """
    Reads full data from App Lab, then sends only the fields
    needed by the phone app.
    """

    global latest_payload

    try:
        with urllib.request.urlopen(SENSOR_HTTP_URL, timeout=1.0) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)

            latest_payload = {
                "humidity_percent": data.get("humidity_percent"),
                "temperature_c": data.get("temperature_c"),
                "timestamp": data.get("timestamp"),
                "toxicity_level": data.get("toxicity_level"),
                "trash_detected": data.get("trash_detected", False),
            }

    except Exception as exc:
        # Keep the last known values, but update timestamp and include error for debugging.
        latest_payload = {
            "humidity_percent": latest_payload.get("humidity_percent"),
            "temperature_c": latest_payload.get("temperature_c"),
            "timestamp": now_iso(),
            "toxicity_level": latest_payload.get("toxicity_level"),
            "trash_detected": latest_payload.get("trash_detected", False),
            "error": str(exc),
        }

    return latest_payload


def payload_bytes():
    """
    Converts latest payload into UTF-8 bytes for BLE.
    """
    return json.dumps(latest_payload).encode("utf-8")


async def main():
    server = BlessServer(name=DEVICE_NAME)

    def read_request(characteristic: BlessGATTCharacteristic, **kwargs):
        print("[BLE READ] Phone requested latest value")
        read_sensor_payload()
        return payload_bytes()

    await server.add_new_service(SERVICE_UUID)

    await server.add_new_characteristic(
        SERVICE_UUID,
        DATA_CHAR_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        None,
        GATTAttributePermissions.readable,
    )

    server.read_request_func = read_request

    await server.start()

    print("[BLE] Advertising as:", DEVICE_NAME)
    print("[BLE] Service UUID:", SERVICE_UUID)
    print("[BLE] Characteristic UUID:", DATA_CHAR_UUID)
    print("[BLE] Polling sensor data from:", SENSOR_HTTP_URL)
    print("[BLE] Sending filtered payload:")
    print("[BLE] humidity_percent, temperature_c, timestamp, toxicity_level, toxicity_score, trash_detected")
    print("[BLE] Open nRF Connect or the Flutter app and scan for the device.")

    while True:
        read_sensor_payload()

        try:
            characteristic = server.get_characteristic(DATA_CHAR_UUID)

            if characteristic is None:
                print("[BLE ERROR] Characteristic not found")
            else:
                characteristic.value = payload_bytes()
                server.update_value(SERVICE_UUID, DATA_CHAR_UUID)

                print("[BLE NOTIFY]", json.dumps(latest_payload))

        except Exception as exc:
            print("[BLE ERROR] Could not notify:", exc)

        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[BLE] Stopped")
