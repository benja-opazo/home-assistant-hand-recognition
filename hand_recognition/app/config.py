import json
import os
import yaml

# HA writes add-on options (from config.yaml schema) to this file at startup
HA_OPTIONS_PATH = "/data/options.json"

# User config saved by the web UI
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/data/config.yaml")

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_default.yaml")


def load_config() -> dict:
    with open(DEFAULT_CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    # HA options take priority over defaults
    if os.path.exists(HA_OPTIONS_PATH):
        with open(HA_OPTIONS_PATH, "r") as f:
            ha_options = json.load(f) or {}
        config.update(ha_options)

    # Web UI saved config takes priority over HA options
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            user_config = yaml.safe_load(f) or {}
        user_config.pop("debug_mode", None)  # HA-managed only; never let config.yaml override
        config.update(user_config)

    return config


def save_config(config: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
