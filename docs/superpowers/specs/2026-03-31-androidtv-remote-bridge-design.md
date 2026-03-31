# Hisense 100U65QF Bridge: MQTT to Android TV Remote v2 Migration

**Date:** 2026-03-31
**Status:** Draft

## Background

The Hisense 100U65QF is an Android TV-based laser TV, not a VIDAA-based TV. It does not run an MQTT broker. The existing MQTT bridge cannot connect. The TV advertises `_androidtvremote2._tcp` on port 6466, confirming support for the Android TV Remote protocol v2.

## Goal

Replace the MQTT transport layer with the Android TV Remote v2 protocol while preserving the HTTP API interface and Savant component profile. The Savant integration should work identically from Blueprint's perspective.

## Architecture

```
┌─────────────────────────────────┐
│  Savant Blueprint / App         │
└──────────────┬──────────────────┘
               │ HTTP (localhost:8642)
┌──────────────▼──────────────────┐
│  Bridge Service                  │
│  ├─ Flask HTTP API (sync)        │
│  ├─ AsyncIO Thread               │
│  │  └─ AndroidTVRemote client    │
│  └─ WOL (UDP broadcast)         │
└──────────────┬──────────────────┘
               │ TLS (port 6466)
               │ Android TV Remote v2
┌──────────────▼──────────────────┐
│  Hisense 100U65QF               │
│  (Android TV)                   │
└─────────────────────────────────┘
```

## Components

### 1. androidtv_client.py (replaces mqtt_client.py)

Wraps the `androidtvremote2` library to provide a synchronous interface matching what `bridge.py` expects.

**Threading model:** The `androidtvremote2` library is asyncio-based. We run a dedicated asyncio event loop in a daemon thread. Synchronous methods in the client use `asyncio.run_coroutine_threadsafe()` to dispatch calls and block on results.

**Class: AndroidTVClient**

```python
class AndroidTVClient:
    def __init__(self, cfg, cert_dir="certs", on_config_changed=None)
    def connect(self)           # Start async loop thread, initiate connection
    def disconnect(self)        # Stop loop, close connection

    # Properties
    @property
    def connected(self) -> bool
    @property
    def state(self) -> dict     # {power, volume, mute, input}

    # Commands
    def send_key(self, key)     # Send raw KEYCODE_*
    def send_nav(self, nav_key) # up/down/left/right/ok/back/home/menu/exit
    def set_volume(self, value) # Absolute volume 0-100
    def volume_up(self)
    def volume_down(self)
    def mute_on(self)
    def mute_off(self)
    def change_source(self, source_name)  # HDMI1, HDMI2, etc.

    # Pairing
    def initiate_pairing(self)            # Shows code on TV
    def confirm_pairing(self, pin)        # 6-char hex code
```

**State tracking:** Register callbacks with the `AndroidTVRemote` instance:
- `is_on` -> updates `state["power"]` to "ON" or "OFF"
- `volume_info` -> updates `state["volume"]` (level) and `state["mute"]` (muted bool -> "ON"/"OFF")
- `current_app` -> updates `state["input"]` (we map app package names to friendly input names)

**Key code mapping:**

| Bridge command | Android TV key code |
|---------------|-------------------|
| Power off | `KEYCODE_POWER` |
| Volume up | `KEYCODE_VOLUME_UP` |
| Volume down | `KEYCODE_VOLUME_DOWN` |
| Mute toggle | `KEYCODE_VOLUME_MUTE` |
| D-pad up | `KEYCODE_DPAD_UP` |
| D-pad down | `KEYCODE_DPAD_DOWN` |
| D-pad left | `KEYCODE_DPAD_LEFT` |
| D-pad right | `KEYCODE_DPAD_RIGHT` |
| OK/Select | `KEYCODE_DPAD_CENTER` |
| Back | `KEYCODE_BACK` |
| Home | `KEYCODE_HOME` |
| Menu | `KEYCODE_MENU` |
| Exit | `KEYCODE_HOME` (no dedicated exit on Android TV) |

**Input switching:**

Android TV doesn't have a universal "switch to HDMI 1" command that works across all devices. We use two strategies:

1. **HDMI key codes** (preferred): `KEYCODE_TV_INPUT_HDMI_1` through `KEYCODE_TV_INPUT_HDMI_4`. These exist in the Android key code spec and work on most TVs with a built-in tuner.
2. **Fallback: app launch**: If HDMI key codes don't work, we can launch the TV's input selector activity via `send_launch_app_command()`.

The `source_map` config field maps friendly names to key codes:

```json
{
  "source_map": {
    "HDMI1": "KEYCODE_TV_INPUT_HDMI_1",
    "HDMI2": "KEYCODE_TV_INPUT_HDMI_2",
    "HDMI3": "KEYCODE_TV_INPUT_HDMI_3",
    "HDMI4": "KEYCODE_TV_INPUT_HDMI_4",
    "Apps": "KEYCODE_HOME"
  }
}
```

**Mute handling:** Android TV Remote v2 only has a mute toggle (`KEYCODE_VOLUME_MUTE`), not discrete on/off. We track mute state via `volume_info` callbacks and only send the toggle when needed (same deduplication logic as the MQTT version).

**Pairing flow:**
1. Client calls `async_generate_cert_if_missing()` to create TLS client certs
2. Client calls `async_start_pairing()` -> TV displays 6-character hex code
3. User reads code from TV screen
4. Client calls `async_finish_pairing(code)` -> pairing complete
5. Certs are persisted in `certs/` directory - pairing only needed once

**Reconnection:** The library has built-in `keep_reconnecting()` with exponential backoff up to 30 seconds. On disconnect, we set power state to "OFF" (same as MQTT version). On reconnect, state callbacks fire automatically.

### 2. config.py (modified)

**Removed fields:** `mqtt_port`, `mqtt_username`, `mqtt_password`

**New fields:** `api_port` (default 6466), `pair_port` (default 6467)

**Updated REQUIRED_FIELDS:**
```python
REQUIRED_FIELDS = ["tv_ip", "tv_mac", "bind_address", "bridge_port", "client_id",
                   "api_port"]
```

**Config example:**
```json
{
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
    "Apps": "KEYCODE_HOME"
  }
}
```

### 3. bridge.py (minor changes)

- Import `AndroidTVClient` instead of `HisenseMQTTClient`
- Instantiate `AndroidTVClient` instead of `HisenseMQTTClient`
- Remove `cert_dir` parameter (certs auto-generated by library)
- Pairing endpoints: `confirm` now accepts 6-char hex code instead of 4-digit numeric PIN
- Everything else stays the same - same routes, same response format, same error handling

### 4. wol.py (unchanged)

Wake-on-LAN still needed for power on. No changes.

### 5. Savant XML profile (minor updates)

- Update `<notes>` to reference Android TV Remote v2 instead of MQTT
- No changes to endpoints, state variables, or actions - the HTTP API is identical

### 6. deploy/install.sh (updated)

- Replace `paho-mqtt` dependency with `androidtvremote2`
- Remove certificate download step (certs are auto-generated)
- Remove `mqtt_port`, `mqtt_username`, `mqtt_password` from config generation
- Add `api_port` and `pair_port` to config generation

### 7. Certificates

The `androidtvremote2` library auto-generates a self-signed TLS client certificate on first run via `async_generate_cert_if_missing()`. These are stored in the `certs/` directory:
- `cert.pem` - client certificate
- `key.pem` - client private key

No external certificate download is needed (unlike the MQTT version which required Hisense-specific certs).

### 8. Tests

All test files rewritten to mock `AndroidTVRemote` instead of `paho.mqtt.client`:

| Test file | What it tests |
|-----------|--------------|
| test_config.py | Config loading/saving (updated fields) |
| test_androidtv_client.py | Client wrapper: connect, disconnect, commands, state, pairing |
| test_bridge.py | HTTP API endpoints (same tests, different mock) |
| test_wol.py | Wake-on-LAN (unchanged) |
| test_state_sync.py | State callback handling |

## Dependencies

**Remove:** `paho-mqtt>=1.6.0,<2.0.0`

**Add:** `androidtvremote2>=0.1.1`

**Keep:** `flask`, `waitress`, `pytest`, `pytest-mock`

**New transitive deps:** `protobuf` (via androidtvremote2)

## Migration Checklist

1. Replace `mqtt_client.py` with `androidtv_client.py`
2. Update `config.py` required fields
3. Update `bridge.py` imports and client instantiation
4. Update `deploy/install.sh`
5. Update `requirements.txt`
6. Update Savant XML notes
7. Rewrite all MQTT-specific tests
8. Update `README.md`
9. Update `config.json.example`
10. Remove old Hisense MQTT cert files from `certs/`

## Risk Assessment

**Low risk:**
- HTTP API unchanged - Savant profile works without modification
- WOL unchanged
- Config structure similar

**Medium risk:**
- Async/sync bridging - need to handle event loop lifecycle carefully
- Input switching via HDMI key codes may not work on this specific TV model - needs testing, fallback strategy documented above
- Volume set: Android TV Remote v2 doesn't have absolute volume set, only relative (up/down) and we receive current level via callbacks. SetVolume will need to calculate delta and send repeated up/down commands, or we accept this limitation and only support relative volume.

**Mitigation for absolute volume:**
SetVolume calculates the delta between current volume (from callbacks) and target, then sends repeated KEYCODE_VOLUME_UP or KEYCODE_VOLUME_DOWN with a short delay between each. This matches how Savant's volume slider works internally (it sends IncreaseVolume/DecreaseVolume). For large jumps (>20 steps), we cap at 20 steps per call to avoid blocking. The next poll cycle will show progress and Savant can send another SetVolume if needed.
