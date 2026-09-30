"""Client for the pages behind the Device Access Code (login posts md5(code + nonce))."""
from __future__ import annotations

import asyncio
import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup

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


def _form_values(body: str, path: str) -> dict[str, str]:
    """Current values of the form posting to `path` (text, hidden, selects, checked boxes)."""
    form = BeautifulSoup(body, "html.parser").select_one(f'form[action$="{path}"]')
    if form is None:
        return {}
    values: dict[str, str] = {}
    for el in form.select("input[name], select[name], textarea[name]"):
        name = el["name"]
        if el.name == "select":
            option = el.select_one("option[selected]") or el.select_one("option")
            values[name] = option.get("value", option.get_text(strip=True)) if option else ""
        elif el.name == "textarea":
            values[name] = el.get_text()
        elif el.get("type") in ("submit", "button", "image", "reset"):
            continue
        elif el.get("type") in ("checkbox", "radio"):
            if el.has_attr("checked"):
                values[name] = el.get("value", "on")
        else:
            values[name] = el.get("value", "")
    return values


def _has_input(body: str, path: str, name: str) -> bool:
    """Whether the form posting to `path` has an input called `name`."""
    form = BeautifulSoup(body, "html.parser").select_one(f'form[action$="{path}"]')
    return form is not None and form.select_one(f'input[name="{name}"]') is not None


class GatewayClient:
    """Cookie-based session for the gateway's locked pages."""

    def __init__(self, hass: HomeAssistant, host: str, access_code: str) -> None:
        """Initialize the client."""
        # unsafe=True: aiohttp ignores cookies from IP-address hosts otherwise.
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
        # The first request only sets the cookie; the form comes after.
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

    async def async_save_form(
        self, path: str, changes: dict[str, str], submit: tuple[str, str]
    ) -> str:
        """Re-submit a settings form with all its current values, except `changes`.

        Settings pages save every field at once, so anything not sent back
        would be reset.
        """
        async with self._lock:
            body = await self._get_page(path)
            fields = _form_values(body, path)
            if "nonce" not in fields:
                raise GatewayConnectionError(f"No form nonce on {path}")
            fields.update(changes)
            fields[submit[0]] = submit[1]
            body = await self._request("POST", path, fields)
            # Wi-Fi changes come back as a warning page that must be confirmed.
            confirm = _form_values(body, path)
            if "nonce" in confirm and _has_input(body, path, "Continue"):
                body = await self._request(
                    "POST", path, {"nonce": confirm["nonce"], "Continue": "Continue"}
                )
            return body

    async def async_validate(self) -> None:
        """Log in once, raising GatewayAuthError/GatewayConnectionError on failure."""
        async with self._lock:
            await self._login()

    async def async_close(self) -> None:
        """Close the session."""
        await self._session.close()
