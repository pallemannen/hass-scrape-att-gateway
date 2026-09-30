"""Client for the gateway's pages that require the Device Access Code.

The login form doesn't send the code itself: its JavaScript posts
`hashpassword = md5(access_code + nonce)`, where the nonce is a hidden field
that changes on every page load. A plain-text code in `password` is rejected
(verified against a real BGW320-500). Neither Core's `scrape`/`rest` nor
multiscrape can compute that hash from a freshly scraped nonce, hence this
small client with its own cookie session.
"""
from __future__ import annotations

import asyncio
import hashlib
import re

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import LOGIN_PATH

LOGIN_MARKER = "Access Code Required"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_NONCE_RE = re.compile(
    r'name="nonce"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="nonce"'
)


class GatewayConnectionError(Exception):
    """The gateway could not be reached."""


class GatewayAuthError(Exception):
    """The gateway rejected the Device Access Code."""


def _nonce(body: str) -> str | None:
    match = _NONCE_RE.search(body)
    return (match.group(1) or match.group(2)) if match else None


class GatewayClient:
    """Cookie-based session for the gateway's locked pages."""

    def __init__(self, hass: HomeAssistant, host: str, access_code: str) -> None:
        """Initialize the client."""
        # unsafe=True: the gateway is addressed by IP, and aiohttp's default
        # cookie jar ignores cookies from IP-address hosts.
        self._session = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        self._base = f"http://{host}/cgi-bin/"
        self._access_code = access_code
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, data: dict | None = None) -> str:
        try:
            async with self._session.request(
                method, self._base + path, data=data, timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                return await resp.text(errors="ignore")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GatewayConnectionError(f"{method} {path}: {err}") from err

    async def _login(self) -> None:
        # The first request only sets the session cookie; the login form (and
        # its nonce) is served once the cookie is present.
        body = await self._request("GET", LOGIN_PATH)
        nonce = _nonce(body) or _nonce(await self._request("GET", LOGIN_PATH))
        if nonce is None:
            raise GatewayConnectionError("No login nonce on the login page")
        body = await self._request(
            "POST",
            LOGIN_PATH,
            {
                "nonce": nonce,
                "password": "*" * len(self._access_code),
                "hashpassword": hashlib.md5(
                    (self._access_code + nonce).encode()
                ).hexdigest(),
                "Continue": "Continue",
            },
        )
        if LOGIN_MARKER in body:
            raise GatewayAuthError("Device Access Code was rejected")

    async def _get_page(self, path: str) -> str:
        body = await self._request("GET", path)
        if LOGIN_MARKER in body:
            await self._login()
            body = await self._request("GET", path)
            if LOGIN_MARKER in body:
                raise GatewayAuthError(f"Still not logged in after login: {path}")
        return body

    async def async_get_page(self, path: str) -> str:
        """Return a locked page's HTML, logging in first if the session expired."""
        async with self._lock:
            return await self._get_page(path)

    async def async_submit(self, path: str, fields: dict[str, str]) -> str:
        """Submit a form on a locked page, with that page's current nonce."""
        async with self._lock:
            nonce = _nonce(await self._get_page(path))
            if nonce is None:
                raise GatewayConnectionError(f"No form nonce on {path}")
            return await self._request("POST", path, {"nonce": nonce, **fields})

    async def async_validate(self) -> None:
        """Log in once, raising GatewayAuthError/GatewayConnectionError on failure."""
        async with self._lock:
            await self._login()

    async def async_close(self) -> None:
        """Close the session."""
        await self._session.close()
