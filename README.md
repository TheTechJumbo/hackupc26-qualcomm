# hackupc26-qualcomm — Bike Sensor Stack

On-bike environmental sensing and trash detection pipeline with BLE output to a mobile app.

## Architecture

```
Arduino (sketch.ino)
  └─ sensors (temp, humidity, light)
        │ HTTP bridge
        ▼
bike-sensors/python/main.py   ← Flask :8765
  └─ trash detection (.eim Edge Impulse model)
  └─ toxicity scoring
        │ polls /latest every 2s
        ▼
bike-ble-bridge/ble_bridge.py
  └─ GATT server "Qualcomm Edge Node"
        │ BLE notifications
        ▼
Flutter mobile app (or nRF Connect)
```

## Components

### bike-sensors
Arduino + Python service for sensor reading and inference.

- Arduino sketch reads thermo/light sensors every 2 s, forwards via RouterBridge
- Flask server runs trash detection via Edge Impulse `.eim` model and computes a toxicity score (1–10) from temp/humidity
- Disables recording below 15 lux

**Setup:**
1. Flash `sketch/sketch.ino` to the Qualcomm Arduino board (requires `Arduino_Modulino`, `Arduino_RouterBridge`)
2. Place your Edge Impulse model at `python/model/trash-detection.eim`
3. `pip install -r python/requirements.txt`
4. `python python/main.py`

Endpoints at `localhost:8765`: `/latest`, `/video`, `/snapshot`, `/health`

---

### bike-ble-bridge
Python BLE GATT server that bridges the sensor HTTP feed to BLE.

- Advertises as **"Qualcomm Edge Node"**
- Polls `http://172.22.0.2:8765/latest` every 2 s and pushes JSON (humidity, temperature, toxicity, trash status) as BLE notifications

**Setup:**
1. `pip install bless`
2. `python ble_bridge.py`

BLE Service UUID: `19B10000-E8F2-537E-4F6C-D104768A1214`

## Requirements

- Qualcomm Arduino board with Modulino + RouterBridge libraries
- Linux host for BLE GATT server (`bless` / D-Bus)
- Edge Impulse `.eim` trash detection model (see [Edge Impulse docs](https://docs.edgeimpulse.com))
