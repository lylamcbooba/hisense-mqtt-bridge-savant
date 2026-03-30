import json
import logging
import signal
import sys
from flask import Flask, request, jsonify
from config import load_config, save_config
from mqtt_client import HisenseMQTTClient
from wol import send_wol

logger = logging.getLogger(__name__)


def create_app(cfg, mqtt_client=None, config_path=None):
    app = Flask(__name__)
    app.config["cfg"] = cfg
    app.config["config_path"] = config_path

    if mqtt_client is None:
        mqtt_client = HisenseMQTTClient(cfg)
    app.config["mqtt"] = mqtt_client
    app.config["tv_mac"] = cfg["tv_mac"]

    @app.route("/api/health", methods=["GET"])
    def health():
        mc = app.config["mqtt"]
        return jsonify({
            "bridge": "running",
            "tv_connected": mc.connected,
            "tv_power": mc.state.get("power", "UNKNOWN"),
        })

    @app.route("/api/state", methods=["GET"])
    def state():
        mc = app.config["mqtt"]
        return jsonify(mc.state)

    @app.route("/api/power/on", methods=["PUT"])
    def power_on():
        send_wol(app.config["tv_mac"])
        return jsonify({"status": "ok", "power": "PENDING"})

    @app.route("/api/power/off", methods=["PUT"])
    def power_off():
        mc = app.config["mqtt"]
        try:
            mc.send_key("KEY_POWER")
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/nav/<key>", methods=["PUT"])
    def nav(key):
        mc = app.config["mqtt"]
        try:
            mc.send_nav(key)
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/volume/set", methods=["PUT"])
    def volume_set():
        mc = app.config["mqtt"]
        value = request.args.get("value")
        if value is None:
            return jsonify({"status": "error", "message": "Missing value param"}), 400
        try:
            mc.set_volume(value)
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/volume/up", methods=["PUT"])
    def volume_up():
        mc = app.config["mqtt"]
        try:
            mc.volume_up()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/volume/down", methods=["PUT"])
    def volume_down():
        mc = app.config["mqtt"]
        try:
            mc.volume_down()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/mute/on", methods=["PUT"])
    def mute_on():
        mc = app.config["mqtt"]
        try:
            mc.mute_on()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/mute/off", methods=["PUT"])
    def mute_off():
        mc = app.config["mqtt"]
        try:
            mc.mute_off()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/input/select", methods=["PUT"])
    def input_select():
        mc = app.config["mqtt"]
        source = request.args.get("source")
        if source is None:
            return jsonify({"status": "error", "message": "Missing source param"}), 400
        try:
            mc.change_source(source)
        except RuntimeError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok"})

    @app.route("/api/input/list", methods=["GET"])
    def input_list():
        mc = app.config["mqtt"]
        source_map = mc.source_map
        if source_map is None:
            return jsonify({"status": "error", "message": "Source map not yet available"}), 503
        return jsonify({"status": "ok", "sources": source_map})

    @app.route("/api/auth/pair", methods=["PUT"])
    def auth_pair():
        mc = app.config["mqtt"]
        try:
            mc.initiate_pairing()
        except ConnectionError as e:
            return jsonify({"status": "error", "message": str(e)}), 503
        return jsonify({"status": "ok", "message": "Check TV for PIN code"})

    @app.route("/api/auth/confirm", methods=["PUT"])
    def auth_confirm():
        mc = app.config["mqtt"]
        pin = request.args.get("pin")
        if pin is None:
            return jsonify({"status": "error", "message": "Missing pin param"}), 400
        try:
            mc.confirm_pairing(pin)
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
    logger.info("Starting Hisense MQTT Bridge on %s:%s", cfg["bind_address"], cfg["bridge_port"])

    def on_config_changed(key, value):
        cfg[key] = value
        save_config(config_path, cfg)
        logger.info("Config persisted: %s updated", key)

    mqtt_client = HisenseMQTTClient(cfg, on_config_changed=on_config_changed)
    mqtt_client.connect()

    app = create_app(cfg, mqtt_client=mqtt_client, config_path=config_path)

    def shutdown_handler(signum, frame):
        mqtt_client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    from waitress import serve
    serve(app, host=cfg["bind_address"], port=cfg["bridge_port"])


if __name__ == "__main__":
    main()
