from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse


API_PATH_RE = re.compile(r'/(?:api|java-api)/[^"\'\\\s]+')
ROUTE_PATH_RE = re.compile(r'path:\s*"([^"]+)"')
ASSET_RE = re.compile(
    r"""<(?:script|link)\b[^>]+(?:src|href)=["']?([^"' >]+)""",
    re.IGNORECASE,
)
ABSOLUTE_URL_RE = re.compile(r"https?://[^\"'<>\\\s)]+")
HTML_ATTR_REF_RE = re.compile(r"""<[^>]+\b(?:src|href|poster)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
CSS_URL_REF_RE = re.compile(r"""url\(\s*["']?([^"')]+)""", re.IGNORECASE)
FETCH_REF_RE = re.compile(r"""fetch\(\s*["']([^"']+)["']""", re.IGNORECASE)


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})


def extract_api_paths(script: str) -> list[str]:
    return _sorted_unique(match.group(0) for match in API_PATH_RE.finditer(script))


def extract_routes(script: str) -> list[str]:
    return _sorted_unique(match.group(1) for match in ROUTE_PATH_RE.finditer(script))


def extract_shell_assets(html: str) -> list[str]:
    return _sorted_unique(match.group(1) for match in ASSET_RE.finditer(html))


def find_app_bundle_url(asset_urls: list[str]) -> str | None:
    for url in asset_urls:
        if url.startswith("/js/app") and url.endswith(".js"):
            return url
    return None


def extract_absolute_urls(text: str) -> list[str]:
    return _sorted_unique(
        candidate
        for match in ABSOLUTE_URL_RE.finditer(text)
        for candidate in [match.group(0)]
        if _looks_like_static_reference(candidate)
    )


def _looks_like_static_reference(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(("data:", "blob:", "#", "javascript:", "mailto:", "tel:")):
        return False
    if any(char in text for char in "{}[]<>,;"):
        return False
    if any(char in text for char in ("(", ")", "*", "|")):
        return False
    if text.startswith(("+", "$")) or text.endswith(("+", ":", "=")):
        return False
    if re.fullmatch(r"[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*", text):
        return False
    parsed = urlparse(text)
    if parsed.scheme:
        return parsed.scheme in {"http", "https"}
    if text.startswith(("/", "./", "../")):
        return True
    return "/" in text or bool(Path(text).suffix) or "?" in text


def extract_referenced_urls(
    base_url: str,
    text: str,
    *,
    include_absolute_urls: bool = True,
    include_html_attrs: bool = True,
) -> list[str]:
    refs: list[str] = []

    def append_matches(pattern: re.Pattern[str]) -> None:
        for match in pattern.finditer(text):
            value = match.group(1)
            if not value:
                continue
            if not _looks_like_static_reference(value):
                continue
            refs.append(urljoin(base_url, value))

    if include_html_attrs:
        append_matches(HTML_ATTR_REF_RE)
    append_matches(CSS_URL_REF_RE)
    append_matches(FETCH_REF_RE)
    if include_absolute_urls:
        refs.extend(extract_absolute_urls(text))
    return _sorted_unique(refs)
