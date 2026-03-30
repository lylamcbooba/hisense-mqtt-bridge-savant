import pytest
from unittest.mock import MagicMock, patch
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


def test_initiate_pairing(client):
    client.initiate_pairing()
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/ui_service/SavantHost/actions/authenticationcode",
        '{"authNum": 0}'
    )


def test_confirm_pairing(client):
    client.confirm_pairing(1234)
    client._mqtt.publish.assert_called_once_with(
        "/remoteapp/tv/ui_service/SavantHost/actions/authenticationcode",
        '{"authNum": 1234}'
    )


def test_confirm_pairing_validates_pin(client):
    with pytest.raises(ValueError, match="PIN must be"):
        client.confirm_pairing(99999)
    with pytest.raises(ValueError, match="PIN must be"):
        client.confirm_pairing(-1)
