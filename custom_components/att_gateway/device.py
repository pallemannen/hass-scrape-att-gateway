"""Shared device info for the AT&T Gateway integration.

Built once per config entry (in __init__.py) from fields already scraped
off sysinfo.ha during the coordinator's first refresh, and attached to every
entity in sensor.py/binary_sensor.py so they all group under one device
instead of appearing as ungrouped entities.
"""
from __future__ import annotations

from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_HOST, CONF_NAME, DEFAULT_NAME, DOMAIN, SYSINFO_FIELDS
from .util import extract_text


def build_device_info(entry: ConfigEntry, coordinator_sysinfo: ScrapeCoordinator) -> DeviceInfo:
    """Build the device info shared by every entity in this config entry."""

    def field(key: str) -> str | None:
        select = next(f.select for f in SYSINFO_FIELDS if f.key == key)
        return extract_text(coordinator_sysinfo, select)

    host = entry.data[CONF_HOST]
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        manufacturer=field("manufacturer") or "AT&T",
        model=field("model_number"),
        sw_version=field("software_version"),
        hw_version=field("hardware_version"),
        serial_number=field("serial_number"),
        configuration_url=f"http://{host}/",
    )
