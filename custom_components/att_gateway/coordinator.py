"""Coordinator for the pages behind the Device Access Code."""
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


def _parse(body: str, keep: str | None, keep_rows: int | None) -> BeautifulSoup:
    """Parse a page; with `keep`, reduce it to that one element (first `keep_rows` rows)."""
    soup = BeautifulSoup(body, "html.parser")
    if keep is None or (element := soup.select_one(keep)) is None:
        return soup
    if keep_rows is not None:
        for tr in element.find_all("tr")[keep_rows:]:
            tr.decompose()
    return BeautifulSoup(str(element), "html.parser")


class LockedPageCoordinator(DataUpdateCoordinator[BeautifulSoup]):
    """Fetches and parses one locked gateway page on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GatewayClient,
        path: str,
        keep: str | None = None,
        keep_rows: int | None = None,
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
        self._keep = keep
        self._keep_rows = keep_rows

    async def _async_update_data(self) -> BeautifulSoup:
        try:
            body = await self.client.async_get_page(self.path)
        except GatewayAuthError as err:
            raise UpdateFailed(f"Device Access Code rejected: {err}") from err
        except GatewayConnectionError as err:
            raise UpdateFailed(str(err)) from err
        return await self.hass.async_add_executor_job(
            _parse, body, self._keep, self._keep_rows
        )
