import asyncio
import logging
import threading
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
        with self._lock:
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
            with self._lock:
                self._connected = True
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
        with self._lock:
            self._connected = is_available
            if not is_available:
                self._state["power"] = "OFF"
        if not is_available:
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
        with self._lock:
            self._connected = False
        logger.info("Disconnected from Android TV")

    # --- Commands ---

    def send_key(self, key):
        with self._lock:
            if not self._connected:
                raise ConnectionError("Not connected to TV")
        self._remote.send_key_command(key)
        logger.debug("Sent key: %s", key)

    def send_nav(self, nav_key):
        if nav_key not in NAV_KEY_MAP:
            raise ValueError(f"Invalid nav key: {nav_key}")
        self.send_key(NAV_KEY_MAP[nav_key])

    def set_volume(self, value):
        try:
            target = max(0, min(100, int(value)))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid volume value: {value}")
        with self._lock:
            if not self._connected:
                raise ConnectionError("Not connected to TV")
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
        with self._lock:
            if not self._connected:
                raise ConnectionError("Not connected to TV")
            if self._state["mute"] == "ON":
                return
        self._remote.send_key_command("KEYCODE_VOLUME_MUTE")
        logger.debug("Mute on (toggle sent)")

    def mute_off(self):
        with self._lock:
            if not self._connected:
                raise ConnectionError("Not connected to TV")
            if self._state["mute"] == "OFF":
                return
        self._remote.send_key_command("KEYCODE_VOLUME_MUTE")
        logger.debug("Mute off (toggle sent)")

    def change_source(self, source_name):
        with self._lock:
            if not self._connected:
                raise ConnectionError("Not connected to TV")
        if self._source_map is None:
            raise RuntimeError("Source map not available")
        if source_name not in self._source_map:
            raise ValueError(f"Unknown source: {source_name}")
        key_code = self._source_map[source_name]
        self._remote.send_key_command(key_code)
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
        try:
            future.result(timeout=10)
        except CannotConnect:
            raise ConnectionError("Cannot connect to TV for pairing - is the TV fully powered on?")
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
        except CannotConnect:
            raise ConnectionError("Cannot connect to TV - is the TV fully powered on?")
        logger.info("Pairing confirmed")
