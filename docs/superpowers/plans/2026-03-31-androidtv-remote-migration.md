# Android TV Remote v2 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the MQTT transport layer with Android TV Remote v2 protocol so the bridge can control the Hisense 100U65QF (Android TV).

**Architecture:** A sync wrapper (`androidtv_client.py`) runs the async `androidtvremote2` library in a background thread. Flask HTTP API and Savant profile stay the same — only the TV communication layer changes.

**Tech Stack:** Python 3.8+, androidtvremote2, Flask, Waitress, asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/androidtv_client.py` | Create | Sync wrapper around async androidtvremote2 library |
| `src/mqtt_client.py` | Delete | No longer needed |
| `src/config.py` | Modify | Update required fields (remove MQTT, add Android TV) |
| `src/bridge.py` | Modify | Swap client import and key names |
| `src/wol.py` | No change | Wake-on-LAN stays the same |
| `requirements.txt` | Modify | Replace paho-mqtt with androidtvremote2 |
| `config.json.example` | Rewrite | New config schema |
| `deploy/install.sh` | Modify | Update config generation |
| `deploy/hisense-bridge.service` | Modify | Update description |
| `savant/hisense_100u65qf.xml` | Modify | Update notes section |
| `tests/test_androidtv_client.py` | Create | Tests for new client |
| `tests/test_config.py` | Modify | Update config fixtures |
| `tests/test_bridge.py` | Modify | Update fixtures and key assertions |
| `tests/test_state_sync.py` | Rewrite | Test callback-based state updates |
| `tests/test_mqtt_client.py` | Delete | No longer needed |
| `tests/test_pairing.py` | Delete | Pairing tests merged into test_androidtv_client.py |

---

### Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

```
androidtvremote2>=0.1.1
flask>=2.0.0
waitress>=2.0.0
pytest>=7.0.0
pytest-mock>=3.0.0
pytest-asyncio>=0.21.0
```

- [ ] **Step 2: Install new dependencies**

Run: `cd /Users/liorlight/Code/hisense-mqtt-bridge-savant && pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: replace paho-mqtt with androidtvremote2 dependency"
```

---

### Task 2: Update config.py and config.json.example

**Files:**
- Modify: `src/config.py`
- Rewrite: `config.json.example`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test for new required fields**

Replace `tests/test_config.py` contents:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/liorlight/Code/hisense-mqtt-bridge-savant && python -m pytest tests/test_config.py -v`
Expected: `test_load_config_success` fails (missing `api_port` in REQUIRED_FIELDS causes no error, but the assertion for `api_port` fails because old config didn't have it — actually the fixture already has the new fields, so tests should fail because `config.py` still requires `mqtt_port` etc.)

- [ ] **Step 3: Update config.py**

Replace `src/config.py` contents:

```python
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
```

- [ ] **Step 4: Update config.json.example**

Replace `config.json.example` contents:

```json
{
  "tv_ip": "192.168.1.XX",
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
    "Apps": "KEYCODE_HOME"
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/config.py config.json.example tests/test_config.py
git commit -m "feat: update config for Android TV Remote v2 (remove MQTT fields)"
```

---

### Task 3: Create androidtv_client.py with connection and state tracking

**Files:**
- Create: `src/androidtv_client.py`
- Create: `tests/test_androidtv_client.py`

- [ ] **Step 1: Write failing tests for connection and state**

Create `tests/test_androidtv_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_androidtv_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'androidtv_client'`

- [ ] **Step 3: Create androidtv_client.py with core structure**

Create `src/androidtv_client.py`:

```python
import asyncio
import logging
import threading
import time
from androidtvremote2 import AndroidTVRemote, InvalidAuth, CannotConnect, ConnectionClosed

logger = logging.getLogger(__name__)

NAV_KEY_MAP = {
    "up": "KEYCODE_DPAD_UP",
    "down": "KEYCODE_DPAD_DOWN",
    "left": "KEYCODE_DPAD_LEFT",
    "right": "KEYCODE_DPAD_RIGHT",
    "ok": "KEYCODE_DPAD_CENTER",
    "back": "KEYCODE_BACK",
    "home": "KEYCODE_HOME",
    "menu": "KEYCODE_MENU",
    "exit": "KEYCODE_HOME",
}

MAX_VOLUME_STEPS = 20


class AndroidTVClient:
    def __init__(self, cfg, cert_dir="certs", on_config_changed=None):
        self._cfg = cfg
        self._cert_dir = cert_dir
        self._on_config_changed = on_config_changed
        self._source_map = cfg.get("source_map")
        self._state = {"power": "OFF", "volume": 0, "mute": "OFF", "input": None}
        self._lock = threading.Lock()
        self._loop = None
        self._loop_thread = None
        self._remote = None
        self._connected = False

    @property
    def connected(self):
        return self._connected

    @property
    def state(self):
        with self._lock:
            return dict(self._state)

    @property
    def source_map(self):
        return self._source_map

    def connect(self):
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop, daemon=True
        )
        self._loop_thread.start()
        future = asyncio.run_coroutine_threadsafe(
            self._async_connect(), self._loop
        )
        future.result(timeout=30)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _async_connect(self):
        cert_file = f"{self._cert_dir}/cert.pem"
        key_file = f"{self._cert_dir}/key.pem"
        self._remote = AndroidTVRemote(
            client_name=self._cfg["client_id"],
            certfile=cert_file,
            keyfile=key_file,
            host=self._cfg["tv_ip"],
            api_port=self._cfg.get("api_port", 6466),
            pair_port=self._cfg.get("pair_port", 6467),
            loop=self._loop,
        )
        await self._remote.async_generate_cert_if_missing()
        self._remote.add_is_on_updated_callback(self._on_is_on_updated)
        self._remote.add_volume_info_updated_callback(self._on_volume_updated)
        self._remote.add_current_app_updated_callback(self._on_app_updated)
        self._remote.add_is_available_updated_callback(self._on_availability_updated)
        try:
            await self._remote.async_connect()
            self._connected = True
            with self._lock:
                if self._remote.is_on:
                    self._state["power"] = "ON"
                vol = self._remote.volume_info
                if vol:
                    self._state["volume"] = vol["level"]
                    self._state["mute"] = "ON" if vol["muted"] else "OFF"
            logger.info("Connected to Android TV at %s", self._cfg["tv_ip"])
        except (CannotConnect, ConnectionClosed) as e:
            logger.warning("Initial connection failed: %s. Will keep retrying.", e)
        except InvalidAuth:
            logger.warning("Pairing required. Use /api/auth/pair to pair.")
        self._remote.keep_reconnecting()

    def _on_is_on_updated(self, is_on):
        with self._lock:
            self._state["power"] = "ON" if is_on else "OFF"
        logger.debug("Power updated: %s", self._state["power"])

    def _on_volume_updated(self, volume_info):
        with self._lock:
            self._state["volume"] = volume_info["level"]
            self._state["mute"] = "ON" if volume_info["muted"] else "OFF"
        logger.debug("Volume updated: %s mute=%s",
                      volume_info["level"], volume_info["muted"])

    def _on_app_updated(self, app):
        with self._lock:
            self._state["input"] = app
        logger.debug("App updated: %s", app)

    def _on_availability_updated(self, is_available):
        self._connected = is_available
        if not is_available:
            with self._lock:
                self._state["power"] = "OFF"
            logger.info("TV became unavailable")
        else:
            logger.info("TV became available")

    def disconnect(self):
        if self._remote:
            self._remote.disconnect()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread:
            self._loop_thread.join(timeout=5)
        self._connected = False
        logger.info("Disconnected from Android TV")

    # --- Commands ---

    def send_key(self, key):
        if not self._connected:
            raise ConnectionError("Not connected to TV")
        self._remote.send_key_command(key)
        logger.debug("Sent key: %s", key)

    def send_nav(self, nav_key):
        if nav_key not in NAV_KEY_MAP:
            raise ValueError(f"Invalid nav key: {nav_key}")
        self.send_key(NAV_KEY_MAP[nav_key])

    def set_volume(self, value):
        if not self._connected:
            raise ConnectionError("Not connected to TV")
        target = max(0, min(100, int(value)))
        with self._lock:
            current = self._state["volume"]
        delta = target - current
        steps = min(abs(delta), MAX_VOLUME_STEPS)
        key = "KEYCODE_VOLUME_UP" if delta > 0 else "KEYCODE_VOLUME_DOWN"
        for _ in range(steps):
            self._remote.send_key_command(key)
        logger.debug("Set volume: %s -> %s (%d steps)", current, target, steps)

    def volume_up(self):
        self.send_key("KEYCODE_VOLUME_UP")

    def volume_down(self):
        self.send_key("KEYCODE_VOLUME_DOWN")

    def mute_on(self):
        if not self._connected:
            raise ConnectionError("Not connected to TV")
        with self._lock:
            if self._state["mute"] == "ON":
                return
        self._remote.send_key_command("KEYCODE_VOLUME_MUTE")
        logger.debug("Mute on (toggle sent)")

    def mute_off(self):
        if not self._connected:
            raise ConnectionError("Not connected to TV")
        with self._lock:
            if self._state["mute"] == "OFF":
                return
        self._remote.send_key_command("KEYCODE_VOLUME_MUTE")
        logger.debug("Mute off (toggle sent)")

    def change_source(self, source_name):
        if not self._connected:
            raise ConnectionError("Not connected to TV")
        if self._source_map is None:
            raise RuntimeError("Source map not available")
        if source_name not in self._source_map:
            raise ValueError(f"Unknown source: {source_name}")
        key_code = self._source_map[source_name]
        self._remote.send_key_command(key_code)
        with self._lock:
            self._state["input"] = source_name
        logger.debug("Changed source to %s via %s", source_name, key_code)

    def set_source_map(self, source_map):
        self._source_map = source_map
        if self._on_config_changed:
            self._on_config_changed("source_map", source_map)
        logger.info("Source map updated: %s", source_map)

    # --- Pairing ---

    def initiate_pairing(self):
        if not self._loop:
            raise ConnectionError("Client not started")
        future = asyncio.run_coroutine_threadsafe(
            self._remote.async_start_pairing(), self._loop
        )
        future.result(timeout=10)
        logger.info("Pairing initiated - check TV for code")

    def confirm_pairing(self, pin):
        if not self._loop:
            raise ConnectionError("Client not started")
        pin = str(pin)
        future = asyncio.run_coroutine_threadsafe(
            self._remote.async_finish_pairing(pin), self._loop
        )
        try:
            future.result(timeout=10)
        except InvalidAuth:
            raise ValueError("Invalid pairing code")
        logger.info("Pairing confirmed")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_androidtv_client.py::test_initial_state_is_off tests/test_androidtv_client.py::test_connected_property_false_before_connect tests/test_androidtv_client.py::test_source_map_from_config -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/androidtv_client.py tests/test_androidtv_client.py
git commit -m "feat: add AndroidTVClient with connection and state tracking"
```

---

### Task 4: Add command and pairing tests

**Files:**
- Modify: `tests/test_androidtv_client.py`

- [ ] **Step 1: Add command tests to test_androidtv_client.py**

Append to `tests/test_androidtv_client.py`:

```python
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
    assert client.state["input"] == "HDMI2"


def test_change_source_unknown(mock_remote):
    from androidtv_client import AndroidTVClient
    mock, _ = mock_remote
    client = AndroidTVClient(_make_cfg(), cert_dir="/tmp/certs")
    client._remote = mock
    client._connected = True
    with pytest.raises(ValueError, match="Unknown source"):
        client.change_source("HDMI99")


def test_change_source_no_map():
    from androidtv_client import AndroidTVClient
    cfg = _make_cfg()
    cfg["source_map"] = None
    client = AndroidTVClient(cfg, cert_dir="/tmp/certs")
    client._connected = True
    with pytest.raises(RuntimeError, match="Source map not available"):
        client.change_source("HDMI1")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_androidtv_client.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_androidtv_client.py
git commit -m "test: add command and mute deduplication tests for AndroidTVClient"
```

---

### Task 5: Add state callback tests

**Files:**
- Rewrite: `tests/test_state_sync.py`

- [ ] **Step 1: Rewrite test_state_sync.py for callback-based state**

Replace `tests/test_state_sync.py` contents:

```python
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_state_sync.py -v`
Expected: All 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_state_sync.py
git commit -m "test: rewrite state sync tests for callback-based Android TV state"
```

---

### Task 6: Update bridge.py

**Files:**
- Modify: `src/bridge.py`
- Modify: `tests/test_bridge.py`

- [ ] **Step 1: Update test_bridge.py fixtures**

Replace `tests/test_bridge.py` contents:

```python
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


@pytest.fixture
def app():
    with patch("bridge.AndroidTVClient") as MockClient, \
         patch("bridge.send_wol") as mock_wol:
        mock_client = MagicMock()
        type(mock_client).connected = PropertyMock(return_value=True)
        type(mock_client).state = PropertyMock(return_value={
            "power": "ON", "volume": 25, "mute": "OFF", "input": "HDMI 1"
        })
        type(mock_client).source_map = PropertyMock(return_value=None)
        MockClient.return_value = mock_client

        from bridge import create_app
        cfg = {
            "tv_ip": "192.168.1.125",
            "tv_mac": "AA:BB:CC:DD:EE:FF",
            "bind_address": "127.0.0.1",
            "bridge_port": 8642,
            "client_id": "SavantHost",
            "api_port": 6466,
            "pair_port": 6467,
            "source_map": None,
        }
        application = create_app(cfg, tv_client=mock_client)
        application.config["TESTING"] = True
        yield application, mock_client


@pytest.fixture
def client(app):
    application, mock_client = app
    return application.test_client(), mock_client


def test_health_endpoint(client):
    http, mock_client = client
    resp = http.get("/api/health")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["bridge"] == "running"
    assert data["tv_connected"] is True


def test_state_endpoint(client):
    http, mock_client = client
    resp = http.get("/api/state")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["power"] == "ON"
    assert data["volume"] == 25
    assert data["mute"] == "OFF"
    assert data["input"] == "HDMI 1"


def test_power_on(client):
    http, mock_client = client
    resp = http.put("/api/power/on")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["status"] == "ok"
    assert data["power"] == "PENDING"


def test_power_off(client):
    http, mock_client = client
    resp = http.put("/api/power/off")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["status"] == "ok"
    mock_client.send_key.assert_called_once_with("KEYCODE_POWER")


def test_nav_up(client):
    http, mock_client = client
    resp = http.put("/api/nav/up")
    assert resp.status_code == 200
    mock_client.send_nav.assert_called_once_with("up")


def test_nav_invalid(client):
    http, mock_client = client
    mock_client.send_nav.side_effect = ValueError("Invalid nav key: jump")
    resp = http.put("/api/nav/jump")
    assert resp.status_code == 400


def test_power_off_when_disconnected(client):
    http, mock_client = client
    mock_client.send_key.side_effect = ConnectionError("Not connected")
    resp = http.put("/api/power/off")
    assert resp.status_code == 503


def test_volume_set(client):
    http, mock_client = client
    resp = http.put("/api/volume/set?value=50")
    assert resp.status_code == 200
    mock_client.set_volume.assert_called_once_with("50")


def test_volume_set_missing_value(client):
    http, mock_client = client
    resp = http.put("/api/volume/set")
    assert resp.status_code == 400


def test_volume_up(client):
    http, mock_client = client
    resp = http.put("/api/volume/up")
    assert resp.status_code == 200
    mock_client.volume_up.assert_called_once()


def test_volume_down(client):
    http, mock_client = client
    resp = http.put("/api/volume/down")
    assert resp.status_code == 200
    mock_client.volume_down.assert_called_once()


def test_mute_on(client):
    http, mock_client = client
    resp = http.put("/api/mute/on")
    assert resp.status_code == 200
    mock_client.mute_on.assert_called_once()


def test_mute_off(client):
    http, mock_client = client
    resp = http.put("/api/mute/off")
    assert resp.status_code == 200
    mock_client.mute_off.assert_called_once()


def test_input_select(client):
    http, mock_client = client
    resp = http.put("/api/input/select?source=HDMI1")
    assert resp.status_code == 200
    mock_client.change_source.assert_called_once_with("HDMI1")


def test_input_select_missing_source(client):
    http, mock_client = client
    resp = http.put("/api/input/select")
    assert resp.status_code == 400


def test_input_select_no_source_map(client):
    http, mock_client = client
    mock_client.change_source.side_effect = RuntimeError("Source map not available")
    resp = http.put("/api/input/select?source=HDMI1")
    assert resp.status_code == 503


def test_input_list_no_map(client):
    http, mock_client = client
    resp = http.get("/api/input/list")
    assert resp.status_code == 503


def test_input_list_with_map(client):
    http, mock_client = client
    type(mock_client).source_map = PropertyMock(
        return_value={"HDMI1": "KEYCODE_TV_INPUT_HDMI_1", "HDMI2": "KEYCODE_TV_INPUT_HDMI_2"}
    )
    resp = http.get("/api/input/list")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["sources"]["HDMI1"] == "KEYCODE_TV_INPUT_HDMI_1"


def test_auth_pair(client):
    http, mock_client = client
    resp = http.put("/api/auth/pair")
    assert resp.status_code == 200
    mock_client.initiate_pairing.assert_called_once()


def test_auth_confirm(client):
    http, mock_client = client
    resp = http.put("/api/auth/confirm?pin=A1B2C3")
    assert resp.status_code == 200
    mock_client.confirm_pairing.assert_called_once_with("A1B2C3")


def test_auth_confirm_missing_pin(client):
    http, mock_client = client
    resp = http.put("/api/auth/confirm")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bridge.py -v`
Expected: FAIL (bridge.py still imports HisenseMQTTClient)

- [ ] **Step 3: Update bridge.py**

Replace `src/bridge.py` contents:

```python
import json
import logging
import signal
import sys
from flask import Flask, request, jsonify
from config import load_config, save_config
from androidtv_client import AndroidTVClient
from wol import send_wol

logger = logging.getLogger(__name__)


def create_app(cfg, tv_client=None, config_path=None):
    app = Flask(__name__)
    app.config["cfg"] = cfg
    app.config["config_path"] = config_path

    if tv_client is None:
        tv_client = AndroidTVClient(cfg)
    app.config["tv"] = tv_client
    app.config["tv_mac"] = cfg["tv_mac"]

    @app.route("/api/health", methods=["GET"])
    def health():
        tc = app.config["tv"]
        return jsonify({
            "bridge": "running",
            "tv_connected": tc.connected,
            "tv_power": tc.state.get("power", "UNKNOWN"),
        })

    @app.route("/api/state", methods=["GET"])
    def state():
        tc = app.config["tv"]
        return jsonify(tc.state)

    @app.route("/api/power/on", methods=["PUT"])
    def power_on():
        send_wol(app.config["tv_mac"])
        return jsonify({"status": "ok", "power": "PENDING"})

    @app.route("/api/power/off", methods=["PUT"])
    def power_off():
        tc = app.config["tv"]
        try:
            tc.send_key("KEYCODE_POWER")
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/nav/<key>", methods=["PUT"])
    def nav(key):
        tc = app.config["tv"]
        try:
            tc.send_nav(key)
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/volume/set", methods=["PUT"])
    def volume_set():
        tc = app.config["tv"]
        value = request.args.get("value")
        if value is None:
            return jsonify({"status": "error", "message": "Missing value param"}), 400
        try:
            tc.set_volume(value)
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/volume/up", methods=["PUT"])
    def volume_up():
        tc = app.config["tv"]
        try:
            tc.volume_up()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/volume/down", methods=["PUT"])
    def volume_down():
        tc = app.config["tv"]
        try:
            tc.volume_down()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/mute/on", methods=["PUT"])
    def mute_on():
        tc = app.config["tv"]
        try:
            tc.mute_on()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/mute/off", methods=["PUT"])
    def mute_off():
        tc = app.config["tv"]
        try:
            tc.mute_off()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/input/select", methods=["PUT"])
    def input_select():
        tc = app.config["tv"]
        source = request.args.get("source")
        if source is None:
            return jsonify({"status": "error", "message": "Missing source param"}), 400
        try:
            tc.change_source(source)
        except RuntimeError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/input/list", methods=["GET"])
    def input_list():
        tc = app.config["tv"]
        source_map = tc.source_map
        if source_map is None:
            return jsonify({"status": "error", "message": "Source map not yet available"}), 503
        return jsonify({"status": "ok", "sources": source_map})

    @app.route("/api/auth/pair", methods=["PUT"])
    def auth_pair():
        tc = app.config["tv"]
        try:
            tc.initiate_pairing()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok", "message": "Check TV for pairing code"})

    @app.route("/api/auth/confirm", methods=["PUT"])
    def auth_confirm():
        tc = app.config["tv"]
        pin = request.args.get("pin")
        if pin is None:
            return jsonify({"status": "error", "message": "Missing pin param"}), 400
        try:
            tc.confirm_pairing(pin)
        except (ValueError, ConnectionError) as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        return jsonify({"status": "ok"})

    return app


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    cfg = load_config(config_path)
    logger.info("Starting Hisense Android TV Bridge on %s:%s",
                cfg["bind_address"], cfg["bridge_port"])

    def on_config_changed(key, value):
        cfg[key] = value
        save_config(config_path, cfg)
        logger.info("Config persisted: %s updated", key)

    tv_client = AndroidTVClient(cfg, on_config_changed=on_config_changed)
    tv_client.connect()

    app = create_app(cfg, tv_client=tv_client, config_path=config_path)

    def shutdown_handler(signum, frame):
        tv_client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    from waitress import serve
    serve(app, host=cfg["bind_address"], port=cfg["bridge_port"])


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bridge.py -v`
Expected: All 22 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bridge.py tests/test_bridge.py
git commit -m "feat: update bridge.py to use AndroidTVClient instead of MQTT"
```

---

### Task 7: Clean up old MQTT files

**Files:**
- Delete: `src/mqtt_client.py`
- Delete: `tests/test_mqtt_client.py`
- Delete: `tests/test_pairing.py`
- Delete: `certs/rcm_certchain_pem.cer` (if exists)
- Delete: `certs/rcm_pem_privkey.pkcs8` (if exists)

- [ ] **Step 1: Remove old files**

```bash
cd /Users/liorlight/Code/hisense-mqtt-bridge-savant
rm -f src/mqtt_client.py tests/test_mqtt_client.py tests/test_pairing.py
rm -f certs/rcm_certchain_pem.cer certs/rcm_pem_privkey.pkcs8
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass, no import errors from deleted files

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove MQTT client, pairing tests, and Hisense cert files"
```

---

### Task 8: Update deploy scripts and Savant profile notes

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/hisense-bridge.service`
- Modify: `savant/hisense_100u65qf.xml`

- [ ] **Step 1: Update install.sh**

Replace `deploy/install.sh` contents:

```bash
#!/usr/bin/env bash
# deploy/install.sh — Install Hisense Android TV Bridge on Savant Smart Host
set -euo pipefail

INSTALL_DIR="/opt/hisense-bridge"
SERVICE_USER="hisense-bridge"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Hisense Android TV Bridge Installer ==="

# Create user if not exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Create install directory
echo "Installing to $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"/{src,certs}

# Copy source files
sudo cp "$SCRIPT_DIR"/src/*.py "$INSTALL_DIR/src/"
sudo cp "$SCRIPT_DIR"/requirements.txt "$INSTALL_DIR/"

# Create venv and install deps
echo "Setting up Python virtual environment..."
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# Configure TV connection
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    read -rp "TV IP address: " TV_IP
    read -rp "TV MAC address (AA:BB:CC:DD:EE:FF): " TV_MAC
    sudo "$INSTALL_DIR/venv/bin/python3" -c "
import json, sys
cfg = {
    'tv_ip': sys.argv[1],
    'tv_mac': sys.argv[2],
    'bind_address': '127.0.0.1',
    'bridge_port': 8642,
    'client_id': 'SavantHost',
    'api_port': 6466,
    'pair_port': 6467,
    'source_map': {
        'HDMI1': 'KEYCODE_TV_INPUT_HDMI_1',
        'HDMI2': 'KEYCODE_TV_INPUT_HDMI_2',
        'HDMI3': 'KEYCODE_TV_INPUT_HDMI_3',
        'HDMI4': 'KEYCODE_TV_INPUT_HDMI_4',
        'Apps': 'KEYCODE_HOME',
    },
}
with open('$INSTALL_DIR/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
" "$TV_IP" "$TV_MAC"
else
    echo "Config already exists, skipping..."
fi

# Set permissions
sudo chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
sudo chmod 600 "$INSTALL_DIR/config.json"

# Install systemd service
echo "Installing systemd service..."
sudo cp "$SCRIPT_DIR/deploy/hisense-bridge.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hisense-bridge
sudo systemctl start hisense-bridge

echo ""
echo "=== Installation complete ==="
echo "Service status: sudo systemctl status hisense-bridge"
echo "View logs:      sudo journalctl -u hisense-bridge -f"
echo ""
echo "To pair with TV (TV must be on):"
echo "  curl -X PUT http://localhost:8642/api/auth/pair"
echo "  (Enter 6-character code shown on TV screen)"
echo "  curl -X PUT 'http://localhost:8642/api/auth/confirm?pin=XXXXXX'"
echo ""
```

- [ ] **Step 2: Update hisense-bridge.service**

Replace `deploy/hisense-bridge.service` contents:

```ini
[Unit]
Description=Hisense Android TV Bridge for Savant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/hisense-bridge/venv/bin/python /opt/hisense-bridge/src/bridge.py /opt/hisense-bridge/config.json
WorkingDirectory=/opt/hisense-bridge
Restart=always
RestartSec=5
User=hisense-bridge

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Update Savant XML notes**

In `savant/hisense_100u65qf.xml`, replace the `<notes>` section to reference Android TV Remote v2 instead of MQTT. Update the setup notes to describe the pairing flow with 6-character hex codes. Keep the rest of the profile unchanged since the HTTP API is identical.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add deploy/install.sh deploy/hisense-bridge.service savant/hisense_100u65qf.xml
git commit -m "chore: update deploy scripts and Savant profile for Android TV Remote v2"
```

---

### Task 9: Final integration verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass, no import errors, no warnings about missing modules

- [ ] **Step 2: Verify no references to old MQTT code remain**

Run: `grep -r "mqtt\|paho\|HisenseMQTT\|mqtt_client\|mqtt_port\|mqtt_username\|mqtt_password" src/ tests/ deploy/ --include="*.py" --include="*.sh" --include="*.service"`
Expected: No matches (or only in comments/docs)

- [ ] **Step 3: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup - verify no MQTT references remain"
```
