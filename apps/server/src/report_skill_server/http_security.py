from __future__ import annotations

import secrets
from urllib.parse import urlsplit

from fastapi import Request

from .config import Settings

REQUEST_TOKEN_HEADER = "X-Report-Skill-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def new_request_token() -> str:
    return secrets.token_urlsafe(32)


def origin_is_trusted(request: Request, settings: Settings) -> bool:
    origin = request.headers.get("origin")
    return origin is None or origin in settings.trusted_origins


def host_is_trusted(request: Request, settings: Settings) -> bool:
    raw_host = request.headers.get("host", "")
    try:
        parsed = urlsplit(f"//{raw_host}")
        hostname = parsed.hostname
        _port = parsed.port
    except ValueError:
        return False
    if not hostname or parsed.username or parsed.password:
        return False
    return hostname.lower() in {host.lower() for host in settings.trusted_hosts}


def request_token_is_valid(request: Request, expected: str) -> bool:
    supplied = request.headers.get(REQUEST_TOKEN_HEADER, "")
    return bool(supplied) and secrets.compare_digest(supplied, expected)
