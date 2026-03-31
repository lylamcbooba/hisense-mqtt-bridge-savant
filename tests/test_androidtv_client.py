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


def test_send_key(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client.send_key("KEYCODE_POWER")
    mock.send_key_command.assert_called_once_with("KEYCODE_POWER")


def test_send_key_when_disconnected():
    from androidtv_client import AndroidTVClient
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    with pytest.raises(ConnectionError):
        client.send_key("KEYCODE_POWER")


def test_send_nav_up(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client.send_nav("up")
    mock.send_key_command.assert_called_once_with("KEYCODE_DPAD_UP")


def test_send_nav_invalid():
    from androidtv_client import AndroidTVClient
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._connected = True
    with pytest.raises(ValueError, match="Invalid nav key"):
        client.send_nav("jump")


def test_volume_up(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client.volume_up()
    mock.send_key_command.assert_called_once_with("KEYCODE_VOLUME_UP")


def test_volume_down(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client.volume_down()
    mock.send_key_command.assert_called_once_with("KEYCODE_VOLUME_DOWN")


def test_set_volume_up(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["volume"] = 10
    client.set_volume(15)
    assert mock.send_key_command.call_count == 5
    mock.send_key_command.assert_called_with("KEYCODE_VOLUME_UP")


def test_set_volume_down(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["volume"] = 50
    client.set_volume(45)
    assert mock.send_key_command.call_count == 5
    mock.send_key_command.assert_called_with("KEYCODE_VOLUME_DOWN")


def test_set_volume_capped_at_max_steps(mock_remote):
    from androidtv_client import AndroidTVClient, MAX_VOLUME_STEPS
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["volume"] = 0
    client.set_volume(100)
    assert mock.send_key_command.call_count == MAX_VOLUME_STEPS


def test_mute_on_sends_toggle(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["mute"] = "OFF"
    client.mute_on()
    mock.send_key_command.assert_called_once_with("KEYCODE_VOLUME_MUTE")


def test_mute_on_skips_if_already_muted(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["mute"] = "ON"
    client.mute_on()
    mock.send_key_command.assert_not_called()


def test_mute_off_sends_toggle(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["mute"] = "ON"
    client.mute_off()
    mock.send_key_command.assert_called_once_with("KEYCODE_VOLUME_MUTE")


def test_mute_off_skips_if_already_unmuted(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client._state["mute"] = "OFF"
    client.mute_off()
    mock.send_key_command.assert_not_called()


def test_change_source(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    client.change_source("HDMI2")
    mock.send_key_command.assert_called_once_with("KEYCODE_TV_INPUT_HDMI_2")


def test_change_source_unknown(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    with pytest.raises(ValueError, match="Unknown source"):
        client.change_source("HDMI99")


def test_set_volume_invalid_value(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    with pytest.raises(ValueError, match="Invalid volume value"):
        client.set_volume("abc")


def test_change_source_no_map():
    from androidtv_client import AndroidTVClient
    cfg = _make_cfg()
    cfg["source_map"] = None
    client = AndroidTVClient(cfg, cert_dir="/tmp/certs")
    client._connected = True
    with pytest.raises(RuntimeError, match="Source map not available"):
        client.change_source("HDMI1")
