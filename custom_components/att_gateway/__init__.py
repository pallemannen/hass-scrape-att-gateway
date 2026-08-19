"""The AT&T Gateway integration.

Depends on Home Assistant Core's built-in `scrape`/`rest` integrations and
reuses their HTTP-fetch/HTML-parse building blocks directly, instead of
reimplementing them:

- `homeassistant.components.rest.RESOURCE_SCHEMA` / `create_rest_data_from_config`
  build the `RestData` object that performs the actual HTTP GET.
- `homeassistant.components.scrape.coordinator.ScrapeCoordinator` wraps that
  `RestData` in a `DataUpdateCoordinator` that fetches on an interval and
  parses the response into a `BeautifulSoup` document.

Unlike the multiscrape-based Xfinity Gateway integration, this gateway needs
no authentication at all (its status pages are served without a login), so
there's no shared HTTP session or credential validation to manage - just two
independent coordinators, one per status page, each built the same way
`scrape`'s own `async_setup_entry` builds its own coordinator.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN, STATUS_PATH, SYSINFO_PATH
from .device import build_device_info
from .util import build_rest_config

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def _async_build_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, host: str, path: str
) -> ScrapeCoordinator:
    """Build and refresh a ScrapeCoordinator for one gateway status page."""
    rest_config = build_rest_config(host, path)
    rest = create_rest_data_from_config(hass, rest_config)
    coordinator = ScrapeCoordinator(
        hass, entry, rest, rest_config, timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    )
    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AT&T Gateway from a config entry."""
    host = entry.data[CONF_HOST]

    coordinator_sysinfo = await _async_build_coordinator(hass, entry, host, SYSINFO_PATH)
    coordinator_status = await _async_build_coordinator(hass, entry, host, STATUS_PATH)

    entry.runtime_data = {
        "sysinfo": coordinator_sysinfo,
        "status": coordinator_status,
        "device_info": build_device_info(entry, coordinator_sysinfo),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry update (e.g. host changed via reconfigure)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
