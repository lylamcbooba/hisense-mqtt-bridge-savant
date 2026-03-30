import socket
import pytest
from unittest.mock import patch, MagicMock
from wol import build_magic_packet, send_wol


def test_build_magic_packet_structure():
    packet = build_magic_packet("AA:BB:CC:DD:EE:FF")
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    mac_bytes = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
    assert packet[6:12] == mac_bytes
    assert packet[96:102] == mac_bytes


def test_build_magic_packet_lowercase():
    packet = build_magic_packet("aa:bb:cc:dd:ee:ff")
    mac_bytes = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
    assert packet[6:12] == mac_bytes


def test_build_magic_packet_no_colons():
    packet = build_magic_packet("AABBCCDDEEFF")
    mac_bytes = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
    assert packet[6:12] == mac_bytes


def test_build_magic_packet_invalid_mac():
    with pytest.raises(ValueError, match="Invalid MAC"):
        build_magic_packet("not-a-mac")


@patch("wol.socket.socket")
def test_send_wol_broadcasts_packet(mock_socket_cls):
    mock_sock = MagicMock()
    mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
    mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
    send_wol("AA:BB:CC:DD:EE:FF")
    mock_sock.setsockopt.assert_called_once_with(
        socket.SOL_SOCKET, socket.SO_BROADCAST, 1
    )
    mock_sock.sendto.assert_called_once()
    args = mock_sock.sendto.call_args
    assert len(args[0][0]) == 102
    assert args[0][1] == ("<broadcast>", 9)
