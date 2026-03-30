import re
import socket


def build_magic_packet(mac_address):
    mac = mac_address.upper().replace(":", "").replace("-", "")
    if not re.match(r"^[0-9A-F]{12}$", mac):
        raise ValueError(f"Invalid MAC address: {mac_address}")
    mac_bytes = bytes.fromhex(mac)
    return b"\xff" * 6 + mac_bytes * 16


def send_wol(mac_address):
    packet = build_magic_packet(mac_address)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, ("<broadcast>", 9))
