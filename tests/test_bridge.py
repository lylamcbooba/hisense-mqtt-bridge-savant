import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


@pytest.fixture
def app():
    with patch("bridge.HisenseMQTTClient") as MockMQTT, \
         patch("bridge.send_wol") as mock_wol:
        mock_client = MagicMock()
        type(mock_client).connected = PropertyMock(return_value=True)
        type(mock_client).state = PropertyMock(return_value={
            "power": "ON", "volume": 25, "mute": "OFF", "input": "HDMI 1"
        })
        type(mock_client).source_map = PropertyMock(return_value=None)
        MockMQTT.return_value = mock_client

        from bridge import create_app
        cfg = {
            "tv_ip": "192.168.1.100",
            "tv_mac": "AA:BB:CC:DD:EE:FF",
            "bind_address": "127.0.0.1",
            "bridge_port": 8642,
            "client_id": "SavantHost",
            "mqtt_port": 36669,
            "mqtt_username": "hisenseservice",
            "mqtt_password": "multimqttservice",
            "auth_token": None,
            "retry_interval_sec": 30,
            "stale_state_timeout_sec": 60,
            "source_map": None,
        }
        application = create_app(cfg, mqtt_client=mock_client)
        application.config["TESTING"] = True
        yield application, mock_client


@pytest.fixture
def client(app):
    application, mock_mqtt = app
    return application.test_client(), mock_mqtt


def test_health_endpoint(client):
    http, mock_mqtt = client
    resp = http.get("/api/health")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["bridge"] == "running"
    assert data["tv_connected"] is True


def test_state_endpoint(client):
    http, mock_mqtt = client
    resp = http.get("/api/state")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["power"] == "ON"
    assert data["volume"] == 25
    assert data["mute"] == "OFF"
    assert data["input"] == "HDMI 1"


def test_power_on(client):
    http, mock_mqtt = client
    resp = http.put("/api/power/on")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["status"] == "ok"
    assert data["power"] == "PENDING"


def test_power_off(client):
    http, mock_mqtt = client
    resp = http.put("/api/power/off")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["status"] == "ok"
    mock_mqtt.send_key.assert_called_once_with("KEY_POWER")


def test_nav_up(client):
    http, mock_mqtt = client
    resp = http.put("/api/nav/up")
    assert resp.status_code == 200
    mock_mqtt.send_nav.assert_called_once_with("up")


def test_nav_invalid(client):
    http, mock_mqtt = client
    mock_mqtt.send_nav.side_effect = ValueError("Invalid nav key: jump")
    resp = http.put("/api/nav/jump")
    assert resp.status_code == 400


def test_power_off_when_disconnected(client):
    http, mock_mqtt = client
    mock_mqtt.send_key.side_effect = ConnectionError("Not connected")
    resp = http.put("/api/power/off")
    assert resp.status_code == 503


def test_volume_set(client):
    http, mock_mqtt = client
    resp = http.put("/api/volume/set?value=50")
    assert resp.status_code == 200
    mock_mqtt.set_volume.assert_called_once_with("50")


def test_volume_set_missing_value(client):
    http, mock_mqtt = client
    resp = http.put("/api/volume/set")
    assert resp.status_code == 400


def test_volume_up(client):
    http, mock_mqtt = client
    resp = http.put("/api/volume/up")
    assert resp.status_code == 200
    mock_mqtt.volume_up.assert_called_once()


def test_volume_down(client):
    http, mock_mqtt = client
    resp = http.put("/api/volume/down")
    assert resp.status_code == 200
    mock_mqtt.volume_down.assert_called_once()


def test_mute_on(client):
    http, mock_mqtt = client
    resp = http.put("/api/mute/on")
    assert resp.status_code == 200
    mock_mqtt.mute_on.assert_called_once()


def test_mute_off(client):
    http, mock_mqtt = client
    resp = http.put("/api/mute/off")
    assert resp.status_code == 200
    mock_mqtt.mute_off.assert_called_once()


def test_input_select(client):
    http, mock_mqtt = client
    resp = http.put("/api/input/select?source=HDMI1")
    assert resp.status_code == 200
    mock_mqtt.change_source.assert_called_once_with("HDMI1")


def test_input_select_missing_source(client):
    http, mock_mqtt = client
    resp = http.put("/api/input/select")
    assert resp.status_code == 400


def test_input_select_no_source_map(client):
    http, mock_mqtt = client
    mock_mqtt.change_source.side_effect = RuntimeError("Source map not available")
    resp = http.put("/api/input/select?source=HDMI1")
    assert resp.status_code == 503


def test_input_list_no_map(client):
    http, mock_mqtt = client
    resp = http.get("/api/input/list")
    assert resp.status_code == 503
    data = json.loads(resp.data)
    assert "not yet available" in data["message"]


def test_input_list_with_map(client):
    http, mock_mqtt = client
    type(mock_mqtt).source_map = PropertyMock(
        return_value={"HDMI1": "1", "HDMI2": "2"}
    )
    resp = http.get("/api/input/list")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["sources"]["HDMI1"] == "1"
    assert data["sources"]["HDMI2"] == "2"


def test_auth_pair(client):
    http, mock_mqtt = client
    resp = http.put("/api/auth/pair")
    assert resp.status_code == 200
    mock_mqtt.initiate_pairing.assert_called_once()


def test_auth_confirm(client):
    http, mock_mqtt = client
    resp = http.put("/api/auth/confirm?pin=1234")
    assert resp.status_code == 200
    mock_mqtt.confirm_pairing.assert_called_once_with("1234")


def test_auth_confirm_missing_pin(client):
    http, mock_mqtt = client
    resp = http.put("/api/auth/confirm")
    assert resp.status_code == 400
