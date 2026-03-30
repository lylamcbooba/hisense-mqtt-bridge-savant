import json
import logging
import os
import ssl
import threading
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


NAV_KEY_MAP = {
    "up": "KEY_UP", "down": "KEY_DOWN", "left": "KEY_LEFT",
    "right": "KEY_RIGHT", "ok": "KEY_OK", "back": "KEY_BACK",
    "home": "KEY_HOME", "menu": "KEY_MENU", "exit": "KEY_EXIT",
}

BROADCAST_STATE = "/remoteapp/mobile/broadcast/ui_service/state"
BROADCAST_VOLUME = "/remoteapp/mobile/broadcast/ui_service/volume"


class HisenseMQTTClient:
    def __init__(self, cfg, cert_dir="certs", on_config_changed=None):
        self._cfg = cfg
        self._cert_dir = cert_dir
        self._client_id = cfg["client_id"]
        self._connected = threading.Event()
        self._state = {"power": "OFF", "volume": 0, "mute": "OFF", "input": None}
        self._lock = threading.Lock()
        self._source_map = cfg.get("source_map")
        self._on_config_changed = on_config_changed
        self._stale_timer = None
        self._stale_timeout = cfg.get("stale_state_timeout_sec", 60)
        self._mqtt = mqtt.Client(
            client_id=self._client_id,
            protocol=mqtt.MQTTv311,
        )
        self._mqtt.username_pw_set(cfg["mqtt_username"], cfg["mqtt_password"])
        self._setup_tls()
        self._mqtt.on_connect = self._on_connect
        self._mqtt.on_disconnect = self._on_disconnect
        self._mqtt.on_message = self._on_message

    def _setup_tls(self):
        cert_path = os.path.join(self._cert_dir, "rcm_certchain_pem.cer")
        key_path = os.path.join(self._cert_dir, "rcm_pem_privkey.pkcs8")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ctx.load_cert_chain(cert_path, key_path)
        self._mqtt.tls_set_context(ctx)

    def _topic(self, service, command):
        return f"/remoteapp/tv/{service}/{self._client_id}/actions/{command}"

    def connect(self):
        self._mqtt.reconnect_delay_set(min_delay=5, max_delay=30)
        try:
            self._mqtt.connect(self._cfg["tv_ip"], self._cfg["mqtt_port"])
            self._mqtt.loop_start()
            logger.info("MQTT connection initiated to %s:%s",
                        self._cfg["tv_ip"], self._cfg["mqtt_port"])
        except Exception as e:
            logger.warning("MQTT connect failed: %s. Will retry via loop_start.", e)
            self._connected.clear()
            self._mqtt.loop_start()

    def disconnect(self):
        self._cancel_stale_timer()
        self._mqtt.loop_stop()
        self._mqtt.disconnect()
        self._connected.clear()
        logger.info("MQTT disconnected")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected.set()
            client.subscribe(BROADCAST_STATE)
            client.subscribe(BROADCAST_VOLUME)
            with self._lock:
                self._state["power"] = "ON"
            logger.info("Connected to TV MQTT broker")
            self._reset_stale_timer()
            if self._source_map is None:
                self._query_source_list()
        else:
            logger.warning("MQTT connect returned rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        self._cancel_stale_timer()
        with self._lock:
            self._state["power"] = "OFF"
        logger.info("Disconnected from TV (rc=%s), will auto-reconnect", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        self._reset_stale_timer()
        with self._lock:
            if msg.topic == BROADCAST_VOLUME:
                if "volume_value" in payload:
                    self._state["volume"] = int(payload["volume_value"])
                if "volume_mute" in payload:
                    self._state["mute"] = "ON" if payload["volume_mute"] else "OFF"
            elif msg.topic == BROADCAST_STATE:
                if payload.get("statetype") == "sourceswitch":
                    self._state["input"] = payload.get("sourcename")

    # --- Stale state timer ---

    def _reset_stale_timer(self):
        self._cancel_stale_timer()
        if self._stale_timeout > 0:
            self._stale_timer = threading.Timer(
                self._stale_timeout, self._on_stale_state
            )
            self._stale_timer.daemon = True
            self._stale_timer.start()

    def _cancel_stale_timer(self):
        if self._stale_timer is not None:
            self._stale_timer.cancel()
            self._stale_timer = None

    def _on_stale_state(self):
        if self._connected.is_set():
            logger.info("No broadcast in %ss, querying TV state", self._stale_timeout)
            self._mqtt.publish(self._topic("ui_service", "gettvstate"), "")
            self._reset_stale_timer()

    # --- Properties ---

    @property
    def connected(self):
        return self._connected.is_set()

    @property
    def state(self):
        with self._lock:
            return dict(self._state)

    @property
    def source_map(self):
        return self._source_map

    # --- Commands ---

    def send_key(self, key):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        self._mqtt.publish(self._topic("remote_service", "sendkey"), key)
        logger.debug("Sent key: %s", key)

    def send_nav(self, nav_key):
        if nav_key not in NAV_KEY_MAP:
            raise ValueError(f"Invalid nav key: {nav_key}")
        self.send_key(NAV_KEY_MAP[nav_key])

    def set_volume(self, value):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        value = max(0, min(100, int(value)))
        self._mqtt.publish(
            self._topic("platform_service", "changevolume"), str(value)
        )
        with self._lock:
            self._state["volume"] = value
        logger.debug("Set volume to %s", value)

    def volume_up(self):
        self.send_key("KEY_VOLUMEUP")

    def volume_down(self):
        self.send_key("KEY_VOLUMEDOWN")

    def mute_on(self):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        with self._lock:
            if self._state["mute"] == "ON":
                return
            self._state["mute"] = "ON"
        self._mqtt.publish(self._topic("remote_service", "sendkey"), "KEY_MUTE")

    def mute_off(self):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        with self._lock:
            if self._state["mute"] == "OFF":
                return
            self._state["mute"] = "OFF"
        self._mqtt.publish(self._topic("remote_service", "sendkey"), "KEY_MUTE")

    def change_source(self, source_name):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        if self._source_map is None:
            raise RuntimeError("Source map not available")
        if source_name not in self._source_map:
            raise ValueError(f"Unknown source: {source_name}")
        source_id = self._source_map[source_name]
        payload = json.dumps({"sourceid": source_id})
        self._mqtt.publish(
            self._topic("ui_service", "changesource"), payload
        )
        with self._lock:
            self._state["input"] = source_name

    def set_source_map(self, source_map):
        self._source_map = source_map
        self._notify_config_changed("source_map", source_map)
        logger.info("Source map updated: %s", source_map)

    # --- Source list query ---

    def _query_source_list(self):
        logger.info("Querying TV for source list")
        self._mqtt.publish(self._topic("ui_service", "sourcelist"), "")

    def query_source_list(self):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        self._query_source_list()

    # --- Auth/Pairing ---

    def initiate_pairing(self):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        payload = json.dumps({"authNum": 0})
        self._mqtt.publish(
            self._topic("ui_service", "authenticationcode"), payload
        )
        logger.info("Pairing initiated - check TV for PIN")

    def confirm_pairing(self, pin):
        if not self._connected.is_set():
            raise ConnectionError("Not connected to TV")
        pin = int(pin)
        if pin < 0 or pin > 9999:
            raise ValueError("PIN must be 0-9999")
        payload = json.dumps({"authNum": pin})
        self._mqtt.publish(
            self._topic("ui_service", "authenticationcode"), payload
        )
        self._notify_config_changed("auth_token", str(pin))
        logger.info("Pairing confirmed")

    # --- Config persistence ---

    def _notify_config_changed(self, key, value):
        if self._on_config_changed:
            self._on_config_changed(key, value)
