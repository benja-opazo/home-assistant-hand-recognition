import os
import yaml

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/data/config.yaml")
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_default.yaml")


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}

    with open(DEFAULT_CONFIG_PATH, "r") as f:
        defaults = yaml.safe_load(f)

    config = {**defaults, **user_config}

    # Environment variables (set by run.sh from HA options) take highest priority
    env_map = {
        "MQTT_HOST": "mqtt_host",
        "MQTT_PORT": ("mqtt_port", int),
        "MQTT_USERNAME": "mqtt_username",
        "MQTT_PASSWORD": "mqtt_password",
        "FRIGATE_URL": "frigate_url",
        "SCORE_THRESHOLD": ("score_threshold", float),
        "OUTPUT_TOPIC_TEMPLATE": "output_topic_template",
        "WEB_UI_PORT": ("web_ui_port", int),
    }
    for env_key, field in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            if isinstance(field, tuple):
                key, cast = field
                config[key] = cast(value)
            else:
                config[field] = value

    return config


def save_config(config: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
