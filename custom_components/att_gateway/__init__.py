"""The AT&T Gateway integration.

Depends on Home Assistant Core's built-in `scrape`/`rest` integrations and
reuses their HTTP-fetch/HTML-parse building blocks directly, instead of
reimplementing them:

- `homeassistant.components.rest.RESOURCE_SCHEMA` / `create_rest_data_from_config`
  build the `RestData` object that performs the actual HTTP GET.
- `homeassistant.components.scrape.coordinator.ScrapeCoordinator` wraps that
  `RestData` in a `DataUpdateCoordinator` that fetches on an interval and
  parses the response into a `BeautifulSoup` document.

Most status pages are served without a login, so each gets its own
independent ScrapeCoordinator, built the same way `scrape`'s own
`async_setup_entry` builds its own coordinator. Pages behind the Device
Access Code go through `api.GatewayClient` instead.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import GatewayClient
from .const import (
    CONF_ACCESS_CODE,
    CONF_HOST,
    DEFAULT_SCAN_INTERVAL,
    FIBER_PATH,
    LIST_COUNTS,
    PACKET_FILTER_PATH,
    FIREWALL_PATH,
    IPV6_PATH,
    LAN_PATH,
    NAT_PATH,
    PASSTHROUGH_PATH,
    SPEED_PATH,
    STATUS_PATH,
    SYSINFO_PATH,
    WIFI_PATH,
)
from .coordinator import LockedPageCoordinator
from .device import build_device_info
from .util import build_rest_config, entity_object_id

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SWITCH]


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
    runtime_data = {
        "sysinfo": coordinator_sysinfo,
        "status": await _async_build_coordinator(hass, entry, host, STATUS_PATH),
        "lan": await _async_build_coordinator(hass, entry, host, LAN_PATH),
        "firewall": await _async_build_coordinator(hass, entry, host, FIREWALL_PATH),
        "fiber": await _async_build_coordinator(hass, entry, host, FIBER_PATH),
        "device_info": build_device_info(entry, coordinator_sysinfo),
        "client": None,
    }

    if access_code := entry.data.get(CONF_ACCESS_CODE):
        client = GatewayClient(hass, host, access_code)
        runtime_data["client"] = client
        for key, path in (
            ("nat", NAT_PATH),
            ("speed", SPEED_PATH),
            ("ipv6", IPV6_PATH),
            ("passthrough", PASSTHROUGH_PATH),
            ("wifi", WIFI_PATH),
            ("packet_filter", PACKET_FILTER_PATH),
            *((key, path) for key, _, path, _ in LIST_COUNTS),
        ):
            coordinator = LockedPageCoordinator(hass, entry, client, path)
            # A rejected code shouldn't take down the open-page entities.
            await coordinator.async_refresh()
            runtime_data[key] = coordinator

    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_remove_retired_entities(hass, entry)
    _async_migrate_entity_ids(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _async_remove_retired_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove registry entries for entities this integration no longer creates."""
    retired = {"att_gateway_connection_status"}
    if entry.runtime_data["client"]:
        retired |= {"att_gateway_wifi_24ghz_status", "att_gateway_wifi_5ghz_status"}
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id in retired:
            registry.async_remove(entity.entity_id)


def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename old key-based entity IDs to name-based ones, unless renamed by hand."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        domain = entity.entity_id.split(".", 1)[0]
        if entity.entity_id != f"{domain}.{entity.unique_id}" or not entity.original_name:
            continue
        new_entity_id = f"{domain}.{entity_object_id(entity.original_name)}"
        if new_entity_id == entity.entity_id or registry.async_get(new_entity_id):
            continue
        _LOGGER.info("Renaming %s to %s", entity.entity_id, new_entity_id)
        registry.async_update_entity(entity.entity_id, new_entity_id=new_entity_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry update (e.g. host changed via reconfigure)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and (client := entry.runtime_data.get("client")):
        await client.async_close()
    return unloaded
