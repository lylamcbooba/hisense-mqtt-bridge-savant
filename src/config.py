import json
import os

REQUIRED_FIELDS = ["tv_ip", "tv_mac", "bind_address", "bridge_port", "client_id",
                   "api_port"]


class ConfigError(Exception):
    pass


def load_config(path):
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    with open(path, "r") as f:
        cfg = json.load(f)
    for field in REQUIRED_FIELDS:
        if field not in cfg:
            raise ConfigError(f"Missing required config field: {field}")
    return cfg


def save_config(path, cfg):
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
