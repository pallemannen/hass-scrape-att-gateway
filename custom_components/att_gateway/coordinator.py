"""Coordinator for the gateway's pages behind the Device Access Code.

Holds a parsed BeautifulSoup document in `.data`, like Core's
ScrapeCoordinator, so the same entity classes and `extract_text` work for
both locked and open pages.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from bs4 import BeautifulSoup

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GatewayAuthError, GatewayClient, GatewayConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LockedPageCoordinator(DataUpdateCoordinator[BeautifulSoup]):
    """Fetches and parses one locked gateway page on an interval."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: GatewayClient, path: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {path}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.path = path

    async def _async_update_data(self) -> BeautifulSoup:
        try:
            body = await self.client.async_get_page(self.path)
        except GatewayAuthError as err:
            raise UpdateFailed(f"Device Access Code rejected: {err}") from err
        except GatewayConnectionError as err:
            raise UpdateFailed(str(err)) from err
        return await self.hass.async_add_executor_job(BeautifulSoup, body, "html.parser")
