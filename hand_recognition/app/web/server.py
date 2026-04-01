from flask import Flask, render_template, request, jsonify

from config import load_config, save_config


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


def create_app(config: dict) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.wsgi_app = _ReverseProxied(app.wsgi_app)
    app.config["current_config"] = config

    @app.get("/")
    def index():
        cfg = load_config()
        return render_template("index.html", config=cfg)

    @app.post("/api/config")
    def update_config():
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

    @app.get("/api/config")
    def get_config():
        return jsonify(load_config())

    return app
