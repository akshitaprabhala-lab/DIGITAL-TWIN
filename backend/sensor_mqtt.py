"""Real MQTT sensor pipeline: device publisher -> mosquitto broker ->
ingestion subscriber -> in-memory latest reading -> consumed by the SSE feed.

Everything is guarded: if the broker/paho is unavailable the app degrades
gracefully (the SSE endpoint falls back to synthetic generation) so the live
feed always works.
"""
import os
import json
import time
import math
import random
import socket
import logging
import threading
import subprocess

logger = logging.getLogger(__name__)

BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
TOPIC = "twinmed/sensor/wearable"

_state = {"connected": False, "latest": None, "started": False}


def is_connected():
    return _state["connected"]


def get_latest():
    return _state["latest"]


def _port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_broker():
    if _port_open(BROKER_HOST, BROKER_PORT):
        return True
    binary = "/usr/sbin/mosquitto"
    if not os.path.exists(binary):
        logger.warning("mosquitto binary not found; MQTT disabled (SSE fallback active)")
        return False
    try:
        subprocess.Popen([binary, "-c", os.path.join(os.path.dirname(__file__), "mosquitto.conf")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(10):
            time.sleep(0.4)
            if _port_open(BROKER_HOST, BROKER_PORT):
                logger.info("Started local mosquitto broker")
                return True
    except Exception as e:
        logger.warning(f"Could not start mosquitto: {e}")
    return False


def _publisher_loop():
    """Simulated wearable device publishing raw sensor signals over MQTT."""
    import paho.mqtt.client as mqtt
    cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twinmed-wearable")
    while True:
        try:
            cli.connect(BROKER_HOST, BROKER_PORT, 30)
            cli.loop_start()
            break
        except Exception:
            time.sleep(1.0)
    t = 0
    while True:
        phase = t / 6.0
        payload = {
            "device_id": "wearable-01", "ts": time.time(),
            "lactate": round(1.2 + 0.4 * math.sin(phase) + random.uniform(-0.1, 0.1), 2),
            "cortisol": round(12 + 3 * math.sin(phase / 3) + random.uniform(-0.6, 0.6), 1),
            "sodium": round(38 + 2 * math.sin(phase / 2) + random.uniform(-0.5, 0.5), 1),
            "heart_rate": round(74 + 6 * math.sin(phase / 2) + random.uniform(-2, 2), 0),
            "spo2": round(min(100, 98 + random.uniform(-0.6, 0.4)), 1),
        }
        try:
            cli.publish(TOPIC, json.dumps(payload))
        except Exception:
            pass
        t += 1
        time.sleep(0.5)


def _ingestion_start():
    import paho.mqtt.client as mqtt

    def on_connect(client, userdata, flags, reason_code, properties=None):
        _state["connected"] = True
        client.subscribe(TOPIC)
        logger.info("MQTT ingestion subscribed to %s", TOPIC)

    def on_disconnect(client, userdata, *args):
        _state["connected"] = False

    def on_message(client, userdata, msg):
        try:
            _state["latest"] = json.loads(msg.payload.decode())
        except Exception:
            pass

    cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twinmed-ingestion")
    cli.on_connect = on_connect
    cli.on_disconnect = on_disconnect
    cli.on_message = on_message
    while True:
        try:
            cli.connect(BROKER_HOST, BROKER_PORT, 30)
            break
        except Exception:
            time.sleep(1.0)
    cli.loop_start()


def start():
    """Idempotently start broker + publisher + ingestion in background threads."""
    if _state["started"]:
        return
    _state["started"] = True

    def boot():
        if not _ensure_broker():
            return
        try:
            _ingestion_start()
            threading.Thread(target=_publisher_loop, daemon=True).start()
        except Exception as e:
            logger.warning(f"MQTT pipeline init failed: {e}")

    threading.Thread(target=boot, daemon=True).start()
