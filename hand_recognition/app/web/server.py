import json
import logging

from flask import Flask, Response, render_template, request, jsonify

from config import load_config, save_config
from log_handler import InMemoryLogHandler

logger = logging.getLogger(__name__)


class _ReverseProxied:
    """Middleware that sets SCRIPT_NAME from the X-Ingress-Path header.

    Home Assistant ingress proxies requests to the add-on under a dynamic
    path (e.g. /api/hassio_ingress/<token>). Flask needs to know this prefix
    so url_for() generates correct absolute URLs.
    """

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


def create_app(config: dict, log_handler: InMemoryLogHandler) -> Flask:
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
        return render_template("index.html", config=cfg)

    @app.post("/api/config")
    def update_config():
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "No data provided"}), 400

            cfg = load_config()

            str_fields = ["mqtt_host", "mqtt_username", "mqtt_password", "frigate_url", "output_topic_template"]
            int_fields = ["mqtt_port", "web_ui_port"]
            float_fields = ["score_threshold"]

            for field in str_fields:
                if field in data:
                    cfg[field] = str(data[field])
            for field in int_fields:
                if field in data:
                    try:
                        cfg[field] = int(data[field])
                    except (ValueError, TypeError):
                        return jsonify({"error": f"Invalid value for {field}"}), 400
            for field in float_fields:
                if field in data:
                    try:
                        cfg[field] = float(data[field])
                    except (ValueError, TypeError):
                        return jsonify({"error": f"Invalid value for {field}"}), 400

            save_config(cfg)
            app.config["current_config"] = cfg
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
            # Send all buffered entries first
            for entry in log_handler.get_records():
                yield f"data: {json.dumps(entry)}\n\n"

            # Then stream new entries as they arrive
            q = log_handler.subscribe()
            try:
                while True:
                    try:
                        entry = q.get(timeout=15)
                        yield f"data: {json.dumps(entry)}\n\n"
                    except Exception:
                        # Timeout — send a keepalive comment to prevent proxy closing
                        yield ": keepalive\n\n"
            finally:
                log_handler.unsubscribe(q)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",   # prevent nginx/HA proxy from buffering
            },
        )

    return app
