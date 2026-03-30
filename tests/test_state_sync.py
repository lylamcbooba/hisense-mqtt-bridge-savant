import json
import pytest
from unittest.mock import MagicMock, patch
from mqtt_client import HisenseMQTTClient, BROADCAST_VOLUME, BROADCAST_STATE


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


def _make_msg(topic, payload_dict):
    msg = MagicMock()
    msg.topic = topic
    msg.payload = json.dumps(payload_dict).encode()
    return msg


def test_volume_broadcast_updates_state(client):
    msg = _make_msg(BROADCAST_VOLUME, {"volume_value": 72})
    client._on_message(None, None, msg)
    assert client.state["volume"] == 72


def test_mute_broadcast_updates_state(client):
    msg = _make_msg(BROADCAST_VOLUME, {"volume_value": 30, "volume_mute": True})
    client._on_message(None, None, msg)
    assert client.state["mute"] == "ON"
    assert client.state["volume"] == 30


def test_unmute_broadcast_updates_state(client):
    client._state["mute"] = "ON"
    msg = _make_msg(BROADCAST_VOLUME, {"volume_value": 30, "volume_mute": False})
    client._on_message(None, None, msg)
    assert client.state["mute"] == "OFF"


def test_source_switch_broadcast(client):
    msg = _make_msg(BROADCAST_STATE, {
        "statetype": "sourceswitch",
        "sourcename": "HDMI 3"
    })
    client._on_message(None, None, msg)
    assert client.state["input"] == "HDMI 3"


def test_malformed_payload_ignored(client):
    msg = MagicMock()
    msg.topic = BROADCAST_VOLUME
    msg.payload = b"not json"
    client._on_message(None, None, msg)
    assert client.state["volume"] == 0


def test_sequential_volume_updates(client):
    for vol in [10, 50, 75, 100, 0]:
        msg = _make_msg(BROADCAST_VOLUME, {"volume_value": vol})
        client._on_message(None, None, msg)
        assert client.state["volume"] == vol


def test_state_after_connect_disconnect(client):
    client._on_connect(client._mqtt, None, None, 0)
    assert client.state["power"] == "ON"
    client._on_disconnect(None, None, 0)
    assert client.state["power"] == "OFF"
    assert client.connected is False
