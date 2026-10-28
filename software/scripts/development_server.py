"""Validate an explicit local dashboard origin without DNS or secret logging."""

import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_SERVER = "http://127.0.0.1:3000"


def local_origin(value):
    if not isinstance(value, str):
        raise ValueError("Local server must be an explicit origin")
    url = urlsplit(value)
    if (url.scheme not in {"http", "https"} or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment or url.path not in {"", "/"}
            or any(character.isspace() or character in '\\"' for character in value)):
        raise ValueError("Local server must be an origin without credentials or a path")
    if url.hostname != "localhost":
        try:
            address = ipaddress.ip_address(url.hostname)
        except ValueError:
            raise ValueError("Use localhost or an explicit private-network IP address") from None
        networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")
        allowed = (any(address in ipaddress.ip_network(network) for network in networks)
                   if address.version == 4 else address == ipaddress.ip_address("::1"))
        if not allowed:
            raise ValueError("Development server must use a loopback or private LAN address")
    port = url.port
    if port == 0:
        raise ValueError("Local server port must be between 1 and 65535")
    return value.rstrip("/")


def development_server(project):
    path = Path(project) / "local.settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(settings, dict) or set(settings) - {"server"}:
        raise ValueError("Local development settings support only a server origin")
    return local_origin(settings.get("server", DEFAULT_SERVER))
