from __future__ import annotations

import re
from urllib.parse import urlparse


LOCAL_EXTERNAL_PREFIX = "/_external"
PRIMARY_HOST = "steam.fun"
LOCAL_HOSTS = {PRIMARY_HOST, f"www.{PRIMARY_HOST}", "127.0.0.1", "localhost"}
IGNORED_EXTERNAL_HOSTS = {"www.w3.org"}
HOST_PATTERN = r"(?:(?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+|localhost|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?"
ABSOLUTE_URL_RE = re.compile(rf"(?P<prefix>https?:)?//(?P<host>{HOST_PATTERN})(?P<path>/[^\"'<>\\\s)]*)?")


def _normalize_host(host: str) -> str:
    return host.split(":", 1)[0].lower()


def is_same_origin_host(host: str) -> bool:
    return _normalize_host(host) in LOCAL_HOSTS


def to_local_same_origin_path(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https:{url}")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if parsed.fragment:
        path = f"{path}#{parsed.fragment}"
    return path


def to_local_external_path(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https:{url}")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if parsed.fragment:
        path = f"{path}#{parsed.fragment}"
    return f"{LOCAL_EXTERNAL_PREFIX}/{parsed.netloc}{path}"


def rewrite_external_urls(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group("prefix") is None and match.group("path") is None:
            return match.group(0)
        host = match.group("host")
        if is_same_origin_host(host):
            return to_local_same_origin_path(match.group(0))
        if _normalize_host(host) in IGNORED_EXTERNAL_HOSTS:
            return match.group(0)
        return to_local_external_path(match.group(0))

    return ABSOLUTE_URL_RE.sub(replace, text)
