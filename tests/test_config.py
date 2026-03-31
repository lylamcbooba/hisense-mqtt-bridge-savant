import json
import pytest
from config import load_config, save_config, ConfigError


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.json"
    data = {
        "tv_ip": "192.168.1.125",
        "tv_mac": "AA:BB:CC:DD:EE:FF",
        "bind_address": "127.0.0.1",
        "bridge_port": 8642,
        "client_id": "SavantHost",
        "api_port": 6466,
        "pair_port": 6467,
        "source_map": None,
    }
    path.write_text(json.dumps(data))
    return path


def test_load_config_success(config_file):
    cfg = load_config(str(config_file))
    assert cfg["tv_ip"] == "192.168.1.125"
    assert cfg["tv_mac"] == "AA:BB:CC:DD:EE:FF"
    assert cfg["bridge_port"] == 8642
    assert cfg["api_port"] == 6466


def test_load_config_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.json")


def test_load_config_missing_required_field(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tv_ip": "192.168.1.125"}))
    with pytest.raises(ConfigError, match="tv_mac"):
        load_config(str(path))


def test_save_config_persists_source_map(config_file):
    cfg = load_config(str(config_file))
    cfg["source_map"] = {"HDMI1": "KEYCODE_TV_INPUT_HDMI_1"}
    save_config(str(config_file), cfg)
    reloaded = load_config(str(config_file))
    assert reloaded["source_map"]["HDMI1"] == "KEYCODE_TV_INPUT_HDMI_1"
