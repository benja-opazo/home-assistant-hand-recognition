import io
import json
import logging
import os
import threading
import zipfile

import requests as http

from flask import Flask, Response, render_template, request, jsonify, send_file

from config import load_config, save_config
from log_handler import InMemoryLogHandler
from snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


class _ReverseProxied:
    """Middleware that sets SCRIPT_NAME from the X-Ingress-Path header."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get("HTTP_X_INGRESS_PATH", "")
        if script_name:
            environ["SCRIPT_NAME"] = script_name
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(script_name):
                environ["PATH_INFO"] = path_info[len(script_name):]
        return self.app(environ, start_response)


def create_app(config: dict, log_handler: InMemoryLogHandler, snapshot_store: SnapshotStore, available_gestures: list[tuple[str, str]] | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.wsgi_app = _ReverseProxied(app.wsgi_app)
    app.config["current_config"] = config

    # ------------------------------------------------------------------ #
    #  Config routes                                                       #
    # ------------------------------------------------------------------ #

    @app.get("/")
    def index():
        try:
            cfg = load_config()
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            cfg = {}
        return render_template("index.html", config=cfg, available_gestures=available_gestures or [])

    @app.post("/api/config")
    def update_config():
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "No data provided"}), 400

            cfg = load_config()

            str_fields = ["mqtt_host", "mqtt_username", "mqtt_password", "frigate_url",
                          "output_topic_template", "mqtt_topic", "frigate_snapshot_mode",
                          "recognizer_backend", "gesture_recognizer_model_path"]
            int_fields = ["mqtt_port", "web_ui_port", "max_snapshots",
                          "mediapipe_max_num_hands", "mediapipe_model_complexity",
                          "frigate_snapshot_quality", "frigate_snapshot_height",
                          "frigate_snapshot_crop"]
            float_fields = ["mediapipe_min_detection_confidence", "landmark_sigmoid_k", "landmark_score_threshold"]

            for field in float_fields:
                if field in data:
                    try:
                        cfg[field] = float(data[field])
                    except (ValueError, TypeError):
                        return jsonify({"error": f"Invalid value for {field}"}), 400

            for field in str_fields:
                if field in data:
                    cfg[field] = str(data[field])
            for field in int_fields:
                if field in data:
                    try:
                        cfg[field] = int(data[field])
                    except (ValueError, TypeError):
                        return jsonify({"error": f"Invalid value for {field}"}), 400

            if "enabled_gestures" in data:
                if not isinstance(data["enabled_gestures"], list):
                    return jsonify({"error": "enabled_gestures must be a list"}), 400
                cfg["enabled_gestures"] = [str(g) for g in data["enabled_gestures"]]

            if "topic_filters" in data:
                filters = data["topic_filters"]
                if not isinstance(filters, list):
                    return jsonify({"error": "topic_filters must be a list"}), 400
                cfg["topic_filters"] = [
                    {
                        "property":   str(f.get("property", "")),
                        "comparator": str(f.get("comparator", "==")),
                        "value":      str(f.get("value", "")),
                    }
                    for f in filters if isinstance(f, dict)
                ]

            save_config(cfg)
            app.config["current_config"] = cfg

            if "max_snapshots" in data:
                snapshot_store.update_max(cfg["max_snapshots"])

            return jsonify({"status": "ok"})

        except Exception as e:
            logger.error("Failed to save config: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.get("/api/config")
    def get_config():
        try:
            return jsonify(load_config())
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------ #
    #  Log routes                                                          #
    # ------------------------------------------------------------------ #

    @app.get("/api/logs")
    def get_logs():
        return jsonify(log_handler.get_records())

    @app.delete("/api/logs")
    def clear_logs():
        log_handler.clear()
        return jsonify({"status": "ok"})

    @app.get("/api/logs/stream")
    def stream_logs():
        def generate():
            for entry in log_handler.get_records():
                yield f"data: {json.dumps(entry)}\n\n"
            q = log_handler.subscribe()
            try:
                while True:
                    try:
                        entry = q.get(timeout=15)
                        yield f"data: {json.dumps(entry)}\n\n"
                    except Exception:
                        yield ": keepalive\n\n"
            finally:
                log_handler.unsubscribe(q)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ------------------------------------------------------------------ #
    #  Snapshot routes                                                     #
    # ------------------------------------------------------------------ #

    @app.get("/api/snapshots")
    def get_snapshots():
        return jsonify(snapshot_store.get_all())

    @app.get("/api/snapshots/<snapshot_id>/image")
    def get_snapshot_image(snapshot_id):
        s = snapshot_store.get_by_id(snapshot_id)
        if not s:
            return jsonify({"error": "Not found"}), 404
        return send_file(s["image_path"], mimetype="image/jpeg")

    @app.post("/api/snapshots/<snapshot_id>/reclassify")
    def reclassify_snapshot(snapshot_id):
        s = snapshot_store.get_by_id(snapshot_id)
        if not s:
            return jsonify({"error": "Not found"}), 404
        try:
            import cv2
            from recognizer_factory import create_recognizer
            cfg        = load_config()
            recognizer = create_recognizer(cfg)
            image      = cv2.imread(s["image_path"])
            if image is None:
                return jsonify({"error": "Image file not found on disk"}), 404
            debug      = bool(cfg.get("debug_mode", False))
            detections = (
                recognizer.recognize_debug(image) if debug and hasattr(recognizer, "recognize_debug")
                else recognizer.recognize(image)
            )
            recognizer.close()
            payload = {"detections": detections, "debug": debug}
            logger.debug("Reclassify response for %s: %s", snapshot_id, payload)
            return jsonify(payload)
        except Exception as e:
            logger.error("Reclassify failed for %s: %s", snapshot_id, e)
            return jsonify({"error": str(e)}), 500

    @app.delete("/api/snapshots/<snapshot_id>")
    def delete_snapshot(snapshot_id):
        if snapshot_store.delete(snapshot_id):
            return jsonify({"status": "ok"})
        return jsonify({"error": "Not found"}), 404

    @app.delete("/api/snapshots")
    def clear_snapshots():
        snapshot_store.clear()
        return jsonify({"status": "ok"})

    # ------------------------------------------------------------------ #
    #  Power routes                                                        #
    # ------------------------------------------------------------------ #

    def _supervisor_call(path: str) -> bool:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return False
        try:
            http.post(
                f"http://supervisor/addons/self/{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            return True
        except Exception as e:
            logger.error("Supervisor call '%s' failed: %s", path, e)
            return False

    # ------------------------------------------------------------------ #
    #  Gesture model routes                                               #
    # ------------------------------------------------------------------ #

    @app.get("/api/gesture-model-status")
    def gesture_model_status():
        cfg = load_config()
        model_path = cfg.get("gesture_recognizer_model_path", "/data/gesture_recognizer.task")
        exists = os.path.isfile(model_path)
        size_mb = round(os.path.getsize(model_path) / (1024 * 1024), 1) if exists else None
        return jsonify({"exists": exists, "path": model_path, "size_mb": size_mb})

    @app.post("/api/download-gesture-model")
    def download_gesture_model():
        cfg = load_config()
        model_path = cfg.get("gesture_recognizer_model_path", "/data/gesture_recognizer.task")
        model_url  = (
            "https://storage.googleapis.com/mediapipe-models/"
            "gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
        )
        try:
            os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
            resp = http.get(model_url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(model_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            size_mb = round(os.path.getsize(model_path) / (1024 * 1024), 1)
            logger.info("Gesture model downloaded to %s (%.1f MB)", model_path, size_mb)
            return jsonify({"status": "ok", "path": model_path, "size_mb": size_mb})
        except Exception as e:
            logger.error("Failed to download gesture model: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.post("/api/restart")
    def restart():
        if not _supervisor_call("restart"):
            threading.Timer(0.3, lambda: os._exit(1)).start()
        return jsonify({"status": "restarting"})

    @app.post("/api/shutdown")
    def shutdown():
        if not _supervisor_call("stop"):
            threading.Timer(0.3, lambda: os._exit(0)).start()
        return jsonify({"status": "stopping"})

    @app.post("/api/snapshots/download")
    def download_snapshots_zip():
        data = request.get_json(force=True) or {}
        ids  = data.get("ids", [])
        if not ids:
            return jsonify({"error": "No snapshot IDs provided"}), 400

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for sid in ids:
                s = snapshot_store.get_by_id(sid)
                if s and os.path.exists(s["image_path"]):
                    safe_time = s["timestamp"].replace(":", "-").replace(" ", "_")
                    filename  = f"{s['camera']}_{safe_time}.jpg"
                    zf.write(s["image_path"], filename)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name="snapshots.zip",
        )

    return app
