import pytest
from unittest.mock import MagicMock, patch, call
from mqtt_client import HisenseMQTTClient


@pytest.fixture
def client():
    cfg = {
        "tv_ip": "192.168.1.100",
        "mqtt_port": 36669,
        "mqtt_username": "hisenseservice",
        "mqtt_password": "multimqttservice",
        "client_id": "SavantHost",
        "retry_interval_sec": 30,
        "stale_state_timeout_sec": 60,
    }
    with patch("mqtt_client.mqtt.Client") as MockClient:
        mock_mqtt = MagicMock()
        MockClient.return_value = mock_mqtt
        c = HisenseMQTTClient(cfg, cert_dir="/fake/certs")
        c._mqtt = mock_mqtt
        c._connected.set()
        yield c


def test_topic_construction(client):
    assert client._topic("remote_service", "sendkey") == \
        "/remoteapp/tv/remote_service/SavantHost/actions/sendkey"
    assert client._topic("ui_service", "changesource") == \
        "/remoteapp/tv/ui_service/SavantHost/actions/changesource"
    assert client._topic("platform_service", "changevolume") == \
        "/remoteapp/tv/platform_service/SavantHost/actions/changevolume"


def test_send_key(client):
    client.send_key("KEY_POWER")
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/remote_service/SavantHost/actions/sendkey",
        "KEY_POWER"
    )


def test_send_key_when_disconnected(client):
    client._connected.clear()
    with pytest.raises(ConnectionError, match="Not connected"):
        client.send_key("KEY_POWER")


def test_nav_keys(client):
    valid_keys = {
        "up": "KEY_UP", "down": "KEY_DOWN", "left": "KEY_LEFT",
        "right": "KEY_RIGHT", "ok": "KEY_OK", "back": "KEY_BACK",
        "home": "KEY_HOME", "menu": "KEY_MENU", "exit": "KEY_EXIT",
    }
    for nav_key, mqtt_key in valid_keys.items():
        client._mqtt.reset_mock()
        client.send_nav(nav_key)
        client._mqtt.publish.assert_called_once_with(
            "/remoteapp/tv/remote_service/SavantHost/actions/sendkey",
            mqtt_key
        )


def test_nav_invalid_key(client):
    with pytest.raises(ValueError, match="Invalid nav key"):
        client.send_nav("invalid")


def test_set_volume(client):
    client.set_volume(50)
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/platform_service/SavantHost/actions/changevolume",
        "50"
    )


def test_set_volume_clamps(client):
    client.set_volume(150)
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/platform_service/SavantHost/actions/changevolume",
        "100"
    )
    client._mqtt.reset_mock()
    client.set_volume(-5)
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/platform_service/SavantHost/actions/changevolume",
        "0"
    )


def test_volume_up(client):
    client.volume_up()
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/remote_service/SavantHost/actions/sendkey",
        "KEY_VOLUMEUP"
    )


def test_volume_down(client):
    client.volume_down()
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/remote_service/SavantHost/actions/sendkey",
        "KEY_VOLUMEDOWN"
    )


def test_mute_on_sends_key_when_not_muted(client):
    client._state["mute"] = "OFF"
    client.mute_on()
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/remote_service/SavantHost/actions/sendkey",
        "KEY_MUTE"
    )


def test_mute_on_skips_when_already_muted(client):
    client._state["mute"] = "ON"
    client.mute_on()
    client._mqtt.publish.assert_not_called()


def test_mute_off_sends_key_when_muted(client):
    client._state["mute"] = "ON"
    client.mute_off()
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/remote_service/SavantHost/actions/sendkey",
        "KEY_MUTE"
    )


def test_mute_on_sends_when_state_unknown(client):
    client._state["mute"] = None
    client.mute_on()
    client._mqtt.publish.assert_called_once()


def test_mute_off_sends_when_state_unknown(client):
    client._state["mute"] = None
    client.mute_off()
    client._mqtt.publish.assert_called_once()


def test_change_source(client):
    client._source_map = {"HDMI1": "1", "HDMI2": "2"}
    client.change_source("HDMI1")
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/ui_service/SavantHost/actions/changesource",
        '{"sourceid": "1"}'
    )


def test_change_source_no_map(client):
    client._source_map = None
    with pytest.raises(RuntimeError, match="Source map not available"):
        client.change_source("HDMI1")


def test_change_source_unknown_source(client):
    client._source_map = {"HDMI1": "1"}
    with pytest.raises(ValueError, match="Unknown source"):
        client.change_source("HDMI9")


def test_on_message_volume_update(client):
    msg = MagicMock()
    msg.topic = "/remoteapp/mobile/broadcast/ui_service/volume"
    msg.payload = b'{"volume_value": 42}'
    client._on_message(None, None, msg)
    assert client.state["volume"] == 42


def test_on_message_state_update(client):
    msg = MagicMock()
    msg.topic = "/remoteapp/mobile/broadcast/ui_service/state"
    msg.payload = b'{"statetype": "sourceswitch", "sourcename": "HDMI 2"}'
    client._on_message(None, None, msg)
    assert client.state["input"] == "HDMI 2"


def test_query_source_list(client):
    client.query_source_list()
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/ui_service/SavantHost/actions/sourcelist",
        ""
    )


def test_query_source_list_when_disconnected(client):
    client._connected.clear()
    with pytest.raises(ConnectionError, match="Not connected"):
        client.query_source_list()


def test_source_map_property(client):
    assert client.source_map is None
    client._source_map = {"HDMI1": "1"}
    assert client.source_map == {"HDMI1": "1"}


def test_set_source_map_calls_config_callback(client):
    callback = MagicMock()
    client._on_config_changed = callback
    client.set_source_map({"HDMI1": "1"})
    callback.assert_called_once_with("source_map", {"HDMI1": "1"})
    assert client.source_map == {"HDMI1": "1"}


def test_confirm_pairing_calls_config_callback(client):
    callback = MagicMock()
    client._on_config_changed = callback
    client.confirm_pairing(1234)
    callback.assert_called_once_with("auth_token", "1234")


def test_stale_timer_fires(client):
    client._stale_timeout = 0.01  # 10ms for test
    client._reset_stale_timer()
    import time
    time.sleep(0.05)
    # Should have published a gettvstate query
    client._mqtt.publish.assert_called_with(
        "/remoteapp/tv/ui_service/SavantHost/actions/gettvstate",
        ""
    )


def test_stale_timer_cancelled_on_disconnect(client):
    client._reset_stale_timer()
    assert client._stale_timer is not None
    client._cancel_stale_timer()
    assert client._stale_timer is None
