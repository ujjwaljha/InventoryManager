from __future__ import annotations

import socket


def lan_ip() -> str:
    """Best local LAN address without needing internet (works offline)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        host = sock.getsockname()[0]
        if host and not host.startswith("127."):
            return host
    except OSError:
        pass
    finally:
        sock.close()
    try:
        return socket.gethostbyname(socket.gethostname()) or "127.0.0.1"
    except OSError:
        return "127.0.0.1"


def shop_url(port: int = 8000) -> str:
    return f"http://{lan_ip()}:{port}/shop"
