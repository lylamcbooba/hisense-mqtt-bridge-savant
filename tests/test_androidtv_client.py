import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


def _make_cfg():
    return {
        "tv_ip": "192.168.1.125",
        "tv_mac": "AA:BB:CC:DD:EE:FF",
        "bind_address": "127.0.0.1",
        "bridge_port": 8642,
        "client_id": "SavantHost",
        "api_port": 6466,
        "pair_port": 6467,
        "source_map": {
            "HDMI1": "KEYCODE_TV_INPUT_HDMI_1",
            "HDMI2": "KEYCODE_TV_INPUT_HDMI_2",
            "HDMI3": "KEYCODE_TV_INPUT_HDMI_3",
            "HDMI4": "KEYCODE_TV_INPUT_HDMI_4",
            "Apps": "KEYCODE_HOME",
        },
    }


@pytest.fixture
def mock_remote():
    with patch("androidtv_client.AndroidTVRemote") as MockRemote:
        mock = AsyncMock()
        mock.async_generate_cert_if_missing = AsyncMock(return_value=False)
        mock.async_connect = AsyncMock()
        mock.keep_reconnecting = MagicMock()
        mock.disconnect = MagicMock()
        mock.send_key_command = MagicMock()
        mock.send_launch_app_command = MagicMock()
        type(mock).is_on = PropertyMock(return_value=True)
        type(mock).volume_info = PropertyMock(return_value={
            "level": 25, "max": 100, "muted": False
        })
        type(mock).current_app = PropertyMock(return_value="com.example.app")
        MockRemote.return_value = mock
        yield mock, MockRemote


def test_initial_state_is_off():
    from androidtv_client import AndroidTVClient
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    assert client.state["power"] == "OFF"
    assert client.state["volume"] == 0
    assert client.state["mute"] == "OFF"


def test_connected_property_false_before_connect():
    from androidtv_client import AndroidTVClient
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    assert client.connected is False


def test_source_map_from_config():
    from androidtv_client import AndroidTVClient
    cfg = _make_cfg()
    client = AndroidTVClient(cfg, cert_dir="/tmp/certs")
    assert client.source_map["HDMI1"] == "KEYCODE_TV_INPUT_HDMI_1"
