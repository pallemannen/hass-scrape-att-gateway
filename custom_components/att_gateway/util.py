"""Shared helpers for the AT&T Gateway integration."""
from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.components.rest import RESOURCE_SCHEMA
from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.const import CONF_RESOURCE
from homeassistant.helpers.typing import ConfigType

# RESOURCE_SCHEMA (imported from homeassistant.components.rest) is a bare
# dict of voluptuous markers meant to be embedded in a larger vol.Schema -
# see homeassistant/components/scrape/__init__.py's own COMBINED_SCHEMA,
# which does the same `**RESOURCE_SCHEMA` spread. Wrapping it here gives us
# a validator that fills in method/verify_ssl/timeout/encoding defaults from
# just a resource URL, the same way scrape's own config entry setup does.
REST_CONFIG_SCHEMA = vol.Schema(RESOURCE_SCHEMA, extra=vol.ALLOW_EXTRA)


def build_rest_config(host: str, path: str) -> ConfigType:
    """Build a validated rest config dict for one gateway status page."""
    return REST_CONFIG_SCHEMA({CONF_RESOURCE: f"http://{host}/cgi-bin/{path}"})


def extract_text(coordinator: ScrapeCoordinator, select: str) -> str | None:
    """Select and strip a single field's text out of the coordinator's soup."""
    soup = coordinator.data
    if soup is None:
        return None
    matches = soup.select(select)
    if not matches:
        return None
    return matches[0].get_text(strip=True)


# Entity IDs follow the entity name (shared rule with the Xfinity Gateway
# integration), except that "Wi-Fi 2.4 GHz" becomes "wifi_24ghz" etc.
_WIFI_BANDS = (("Wi-Fi 2.4 GHz", "wifi_24ghz"), ("Wi-Fi 5 GHz", "wifi_5ghz"), ("Wi-Fi 6 GHz", "wifi_6ghz"))


def entity_object_id(name: str) -> str:
    """Return the entity ID object id (without domain) for an entity name."""
    for band, replacement in _WIFI_BANDS:
        name = name.replace(band, replacement)
    name = name.replace("Wi-Fi", "wifi")
    return "att_gateway_" + re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", name.lower())).strip("_")
