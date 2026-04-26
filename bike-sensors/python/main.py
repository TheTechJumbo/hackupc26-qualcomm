import json
import threading
import time
from datetime import datetime, timezone

from arduino.app_utils import Bridge
from flask import Flask, jsonify, Response

try:
    import cv2
    from edge_impulse_linux.image import ImageImpulseRunner

    MODEL_AVAILABLE = True
except Exception as exc:
    MODEL_AVAILABLE = False
    MODEL_IMPORT_ERROR = exc


app = Flask(__name__)

# -------------------------------------------------
# Config
# -------------------------------------------------

MODEL_PATH = "/app/python/model/trash-detection.eim"

# Your camera was working with index 1.
# If camera does not open, try 0 or 2.
CAMERA_INDEX = 1

# Trash detection threshold
DETECTION_THRESHOLD = 0.3

# Light threshold.
# If lux is below this value, the app blocks recording/model inference.
MIN_RECORDING_LUX = 15

# Print raw model output sometimes
DEBUG_MODEL_OUTPUT = False


# -------------------------------------------------
# Shared state
# -------------------------------------------------

frame_lock = threading.Lock()
latest_jpeg = None

latest_payload = {
    "record_id": 0,
    "timestamp": None,

    # Environmental sensors
    "temperature_c": None,
    "humidity_percent": None,
    "light_lux": None,
    "ambient_light": None,
    "infrared": None,

    # Toxicity / bio-decay score
    "toxicity_score": None,
    "toxicity_level": None,

    # Recording/light status
    "too_dark": False,
    "can_record": True,
    "recording_block_reason": None,

    # Trash/model result
    "trash_detected": False,
    "trash_class": None,
    "confidence": None,
    "boxes": [],
}


# -------------------------------------------------
# Utility functions
# -------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, digits=3):
    try:
        return round(float(value), digits)
    except Exception:
        return None


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def calculate_toxicity_score(temp_c, humidity_percent):
    """
    Bio-decay / toxicity score based on temperature and humidity.
    Returns a score from 1.0 to 10.0.
    """

    if temp_c is None or humidity_percent is None:
        return None

    temp_factor = temp_c / 40.0
    temp_factor = max(0.0, min(temp_factor, 1.0))

    hum_factor = humidity_percent / 100.0
    hum_factor = max(0.0, min(hum_factor, 1.0))

    raw_score = (temp_factor * 0.6) + (hum_factor * 0.4)
    toxicity_score = raw_score * 10.0

    if temp_c >= 30.0 and humidity_percent >= 70.0:
        toxicity_score += 2.0

    toxicity_score = max(1.0, min(toxicity_score, 10.0))

    return round(toxicity_score, 1)


def get_toxicity_level(score):
    if score is None:
        return None

    if score < 4.0:
        return "low"
    elif score < 7.0:
        return "medium"
    else:
        return "high"


def update_toxicity_state():
    latest_payload["toxicity_score"] = calculate_toxicity_score(
        latest_payload.get("temperature_c"),
        latest_payload.get("humidity_percent"),
    )

    latest_payload["toxicity_level"] = get_toxicity_level(
        latest_payload.get("toxicity_score")
    )


def update_light_recording_state():
    """
    Updates too_dark / can_record based on latest light_lux.
    """

    lux = latest_payload.get("light_lux")

    if lux is not None and lux < MIN_RECORDING_LUX:
        latest_payload["too_dark"] = True
        latest_payload["can_record"] = False
        latest_payload["recording_block_reason"] = "too_dark"
    else:
        latest_payload["too_dark"] = False
        latest_payload["can_record"] = True
        latest_payload["recording_block_reason"] = None


def clear_trash_detection():
    latest_payload["trash_detected"] = False
    latest_payload["trash_class"] = None
    latest_payload["confidence"] = None
    latest_payload["boxes"] = []


# -------------------------------------------------
# Sensor handling from sketch.ino through RouterBridge
# -------------------------------------------------

def on_sensor_reading(temperature, humidity, lux=None, ambient_light=None, infrared=None):
    """
    Called by sketch.ino when it does:

    Bridge.notify("sensor_reading", temperature, humidity, lux, ambientLight, infrared);
    """

    latest_payload["record_id"] += 1
    latest_payload["timestamp"] = now_iso()

    latest_payload["temperature_c"] = safe_float(temperature, 1)
    latest_payload["humidity_percent"] = safe_float(humidity, 1)

    latest_payload["light_lux"] = safe_float(lux, 1)
    latest_payload["ambient_light"] = safe_float(ambient_light, 1)
    latest_payload["infrared"] = safe_float(infrared, 1)

    update_toxicity_state()
    update_light_recording_state()

    # If it is too dark, make sure latest trash result is cleared.
    if latest_payload["too_dark"]:
        clear_trash_detection()

    print("[SENSOR]", json.dumps(latest_payload))


def get_initial_sensor_state():
    """
    Called once on startup.
    Reads initial values from sketch.ino using Bridge.call("get_state").
    """

    try:
        response = Bridge.call("get_state")
        data = json.loads(response)

        latest_payload["timestamp"] = now_iso()

        latest_payload["temperature_c"] = safe_float(data.get("temperature_c"), 1)
        latest_payload["humidity_percent"] = safe_float(data.get("humidity_percent"), 1)

        latest_payload["light_lux"] = safe_float(data.get("light_lux"), 1)
        latest_payload["ambient_light"] = safe_float(data.get("ambient_light"), 1)
        latest_payload["infrared"] = safe_float(data.get("infrared"), 1)

        update_toxicity_state()
        update_light_recording_state()

        if latest_payload["too_dark"]:
            clear_trash_detection()

        print("[INIT SENSOR]", latest_payload)

    except Exception as exc:
        print("[INIT SENSOR ERROR]", exc)


# -------------------------------------------------
# Model result normalization
# -------------------------------------------------

def normalize_box_from_edge_impulse(box):
    confidence = safe_float(box.get("value", 0), 3)

    return {
        "label": box.get("label", "trash"),
        "confidence": confidence,
        "x": safe_int(box.get("x", 0)),
        "y": safe_int(box.get("y", 0)),
        "width": safe_int(box.get("width", 0)),
        "height": safe_int(box.get("height", 0)),
    }


def normalize_box_from_yolo(box):
    """
    Supports boxes like:
    {
        "label": "bottle",
        "confidence": 0.87,
        "x": 120,
        "y": 80,
        "width": 90,
        "height": 160
    }

    Also supports common alternatives:
    class/name instead of label
    conf/score/value instead of confidence
    w/h instead of width/height
    """

    confidence = (
        box.get("confidence")
        if box.get("confidence") is not None
        else box.get("conf")
        if box.get("conf") is not None
        else box.get("score")
        if box.get("score") is not None
        else box.get("value", 0)
    )

    label = (
        box.get("label")
        or box.get("class")
        or box.get("name")
        or box.get("trash_class")
        or "trash"
    )

    return {
        "label": label,
        "confidence": safe_float(confidence, 3),
        "x": safe_int(box.get("x", 0)),
        "y": safe_int(box.get("y", 0)),
        "width": safe_int(box.get("width", box.get("w", 0))),
        "height": safe_int(box.get("height", box.get("h", 0))),
    }


def normalize_model_result(result):
    """
    Converts different model output formats into one common format:

    {
        "trash_detected": bool,
        "trash_class": str or None,
        "confidence": float or None,
        "boxes": [...]
    }
    """

    # -------------------------------------------------
    # Case 1: Friend's YOLO-style output
    # -------------------------------------------------
    if isinstance(result, dict) and (
        "trash_detected" in result
        or "trash_class" in result
        or "boxes" in result
    ):
        raw_boxes = result.get("boxes", []) or []
        boxes = []

        for box in raw_boxes:
            normalized = normalize_box_from_yolo(box)

            if (
                normalized["confidence"] is not None
                and normalized["confidence"] >= DETECTION_THRESHOLD
            ):
                boxes.append(normalized)

        top_confidence = safe_float(result.get("confidence"), 3)
        trash_class = result.get("trash_class")

        if boxes:
            best = max(boxes, key=lambda b: b["confidence"])

            return {
                "trash_detected": True,
                "trash_class": trash_class or best["label"],
                "confidence": top_confidence if top_confidence is not None else best["confidence"],
                "boxes": boxes,
            }

        return {
            "trash_detected": bool(result.get("trash_detected", False)),
            "trash_class": trash_class,
            "confidence": top_confidence,
            "boxes": [],
        }

    # -------------------------------------------------
    # Case 2: Edge Impulse object detection
    # -------------------------------------------------
    ei_boxes = result.get("result", {}).get("bounding_boxes", [])

    if ei_boxes:
        boxes = []

        for box in ei_boxes:
            normalized = normalize_box_from_edge_impulse(box)

            if (
                normalized["confidence"] is not None
                and normalized["confidence"] >= DETECTION_THRESHOLD
            ):
                boxes.append(normalized)

        if boxes:
            best = max(boxes, key=lambda b: b["confidence"])

            return {
                "trash_detected": True,
                "trash_class": best["label"],
                "confidence": best["confidence"],
                "boxes": boxes,
            }

        return {
            "trash_detected": False,
            "trash_class": None,
            "confidence": None,
            "boxes": [],
        }

    # -------------------------------------------------
    # Case 3: Edge Impulse classification
    # -------------------------------------------------
    classification = result.get("result", {}).get("classification", {})

    if classification:
        best_label = None
        best_confidence = 0.0

        for label, value in classification.items():
            confidence = safe_float(value, 3)

            if confidence is not None and confidence > best_confidence:
                best_label = label
                best_confidence = confidence

        if best_label is not None and best_confidence >= DETECTION_THRESHOLD:
            return {
                "trash_detected": True,
                "trash_class": best_label,
                "confidence": best_confidence,
                "boxes": [],
            }

    return {
        "trash_detected": False,
        "trash_class": None,
        "confidence": None,
        "boxes": [],
    }


def update_detection_from_model_result(result):
    normalized = normalize_model_result(result)

    latest_payload["trash_detected"] = normalized["trash_detected"]
    latest_payload["trash_class"] = normalized["trash_class"]
    latest_payload["confidence"] = normalized["confidence"]
    latest_payload["boxes"] = normalized["boxes"]
    latest_payload["timestamp"] = now_iso()

    if latest_payload["trash_detected"]:
        print("[TRASH]", json.dumps(normalized))
    else:
        print("[MODEL] No trash detected")


# -------------------------------------------------
# Drawing camera output
# -------------------------------------------------

def draw_status_overlay(frame):
    temp = latest_payload.get("temperature_c")
    hum = latest_payload.get("humidity_percent")
    lux = latest_payload.get("light_lux")
    can_record = latest_payload.get("can_record")
    too_dark = latest_payload.get("too_dark")
    toxicity_score = latest_payload.get("toxicity_score")
    toxicity_level = latest_payload.get("toxicity_level")

    cv2.putText(
        frame,
        f"Temp: {temp} C | Humidity: {hum} %",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"Lux: {lux} | Can record: {can_record}",
        (10, 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"Toxicity: {toxicity_score}/10 ({toxicity_level})",
        (10, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    if too_dark:
        cv2.putText(
            frame,
            "TOO DARK - RECORDING BLOCKED",
            (10, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )
    else:
        if latest_payload.get("trash_detected"):
            status = (
                f"Trash: {latest_payload.get('trash_class')} "
                f"({latest_payload.get('confidence')})"
            )
        else:
            status = "Trash: none"

        cv2.putText(
            frame,
            status,
            (10, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

    return frame


def draw_boxes(frame, boxes):
    for box in boxes:
        label = box.get("label", "trash")
        confidence = safe_float(box.get("confidence", 0), 3)

        if confidence is None or confidence < DETECTION_THRESHOLD:
            continue

        x = safe_int(box.get("x", 0))
        y = safe_int(box.get("y", 0))
        w = safe_int(box.get("width", 0))
        h = safe_int(box.get("height", 0))

        text = f"{label}: {confidence:.2f}"

        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.putText(
            frame,
            text,
            (x, max(y - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    return draw_status_overlay(frame)


# -------------------------------------------------
# Edge Impulse inference
# -------------------------------------------------

def run_edge_impulse_inference(runner, frame):
    """
    Runs Edge Impulse .eim inference on one OpenCV BGR frame.
    """

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    features, cropped = runner.get_features_from_image(rgb)
    result = runner.classify(features)

    return result


# -------------------------------------------------
# Optional friend's custom YOLO wrapper
# -------------------------------------------------
# If your friend gives you a Python file like:
#
#   trash_detector.py
#
# with:
#
#   detect_trash(frame)
#
# place it in /app/python/trash_detector.py
# then uncomment this block.

# try:
#     from trash_detector import detect_trash
#     FRIEND_YOLO_AVAILABLE = True
# except Exception as exc:
#     FRIEND_YOLO_AVAILABLE = False
#     FRIEND_YOLO_IMPORT_ERROR = exc

FRIEND_YOLO_AVAILABLE = False


# -------------------------------------------------
# Camera + model loop
# -------------------------------------------------

def camera_model_loop():
    global latest_jpeg

    if not MODEL_AVAILABLE and not FRIEND_YOLO_AVAILABLE:
        print("[MODEL ERROR] No model method available.")

        if not MODEL_AVAILABLE:
            print("[MODEL ERROR] Edge Impulse import error:")
            print(MODEL_IMPORT_ERROR)

        return

    runner = None

    if not FRIEND_YOLO_AVAILABLE:
        print("[MODEL] Loading Edge Impulse model:", MODEL_PATH)

        try:
            runner = ImageImpulseRunner(MODEL_PATH)
            model_info = runner.init()

            print("[MODEL] Loaded model:")
            print(json.dumps(model_info.get("project", {}), indent=2))

        except Exception as exc:
            print("[MODEL ERROR] Could not load .eim model:")
            print(exc)
            return

    print("[CAMERA] Opening camera index:", CAMERA_INDEX)

    camera = cv2.VideoCapture(CAMERA_INDEX)

    if not camera.isOpened():
        print("[CAMERA ERROR] Could not open camera index", CAMERA_INDEX)
        print("[CAMERA ERROR] Try CAMERA_INDEX = 0 or 2")

        if runner:
            runner.stop()

        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    frame_count = 0

    try:
        while True:
            ok, frame = camera.read()

            if not ok:
                print("[CAMERA ERROR] Could not read frame")
                time.sleep(1)
                continue

            frame_count += 1

            # -------------------------------------------------
            # Too-dark logic:
            # if too dark, do not run model and do not record trash data.
            # -------------------------------------------------
            if latest_payload.get("too_dark"):
                clear_trash_detection()

                annotated = frame.copy()
                annotated = draw_status_overlay(annotated)

                ok_jpeg, jpeg = cv2.imencode(".jpg", annotated)

                if ok_jpeg:
                    with frame_lock:
                        latest_jpeg = jpeg.tobytes()

                if frame_count % 5 == 0:
                    print("[LIGHT] Too dark - skipping model inference")

                time.sleep(1)
                continue

            # -------------------------------------------------
            # Normal model inference path
            # -------------------------------------------------
            try:
                if FRIEND_YOLO_AVAILABLE:
                    result = detect_trash(frame)
                else:
                    result = run_edge_impulse_inference(runner, frame)

                if DEBUG_MODEL_OUTPUT and frame_count % 5 == 0:
                    print("[RAW MODEL RESULT]", json.dumps(result.get("result", result))[:2000])

                update_detection_from_model_result(result)

                boxes = latest_payload.get("boxes", [])
                annotated = draw_boxes(frame.copy(), boxes)

            except Exception as exc:
                print("[MODEL ERROR] Inference failed:")
                print(exc)

                annotated = frame.copy()

                cv2.putText(
                    annotated,
                    "Model inference error",
                    (10, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

                annotated = draw_status_overlay(annotated)

            ok_jpeg, jpeg = cv2.imencode(".jpg", annotated)

            if ok_jpeg:
                with frame_lock:
                    latest_jpeg = jpeg.tobytes()

            # Save debug image every 10 frames
            if frame_count % 10 == 0:
                try:
                    cv2.imwrite("/tmp/latest_camera_debug.jpg", annotated)
                except Exception as exc:
                    print("[CAMERA DEBUG] Could not save debug image:", exc)

            time.sleep(1)

    finally:
        camera.release()

        if runner:
            runner.stop()


# -------------------------------------------------
# Flask endpoints
# -------------------------------------------------

@app.route("/latest", methods=["GET"])
def latest():
    return jsonify(latest_payload)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


def generate_video_stream():
    while True:
        with frame_lock:
            frame = latest_jpeg

        if frame is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

        time.sleep(0.1)


@app.route("/video", methods=["GET"])
def video():
    return Response(
        generate_video_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/snapshot", methods=["GET"])
def snapshot():
    with frame_lock:
        frame = latest_jpeg

    if frame is None:
        return jsonify({"error": "No camera frame available yet"}), 404

    return Response(frame, mimetype="image/jpeg")


# -------------------------------------------------
# Startup
# -------------------------------------------------

Bridge.provide("sensor_reading", on_sensor_reading)

get_initial_sensor_state()

threading.Thread(target=camera_model_loop, daemon=True).start()

print("[HTTP] Sensor + camera/model server starting on port 8765")
app.run(host="0.0.0.0", port=8765)