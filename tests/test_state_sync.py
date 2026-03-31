import pytest
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock


def _make_cfg():
    return {
        "tv_ip": "192.168.1.125",
        "tv_mac": "AA:BB:CC:DD:EE:FF",
        "bind_address": "127.0.0.1",
        "bridge_port": 8642,
        "client_id": "SavantHost",
        "api_port": 6466,
        "pair_port": 6467,
        "source_map": None,
    }


def _make_client():
    from androidtv_client import AndroidTVClient
    return AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")


def test_power_on_callback():
    client = _make_client()
    client._on_is_on_updated(True)
    assert client.state["power"] == "ON"


def test_power_off_callback():
    client = _make_client()
    client._on_is_on_updated(True)
    client._on_is_on_updated(False)
    assert client.state["power"] == "OFF"


def test_volume_callback():
    client = _make_client()
    client._on_volume_updated({"level": 72, "max": 100, "muted": False})
    assert client.state["volume"] == 72
    assert client.state["mute"] == "OFF"


def test_volume_muted_callback():
    client = _make_client()
    client._on_volume_updated({"level": 30, "max": 100, "muted": True})
    assert client.state["volume"] == 30
    assert client.state["mute"] == "ON"


def test_volume_unmuted_callback():
    client = _make_client()
    client._state["mute"] = "ON"
    client._on_volume_updated({"level": 30, "max": 100, "muted": False})
    assert client.state["mute"] == "OFF"


def test_app_callback():
    client = _make_client()
    client._on_app_updated("com.netflix.mediaclient")
    assert client.state["input"] == "com.netflix.mediaclient"


def test_availability_lost():
    client = _make_client()
    client._connected = True
    client._on_availability_updated(False)
    assert client.connected is False
    assert client.state["power"] == "OFF"


def test_availability_restored():
    client = _make_client()
    client._on_availability_updated(True)
    assert client.connected is True


def test_sequential_volume_updates():
    client = _make_client()
    for vol in [10, 50, 75, 100, 0]:
        client._on_volume_updated({"level": vol, "max": 100, "muted": False})
        assert client.state["volume"] == vol
