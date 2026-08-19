"""Shared helpers for the AT&T Gateway integration."""
from __future__ import annotations

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
