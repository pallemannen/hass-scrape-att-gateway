"""Config flow for the AT&T Gateway integration.

The only credential is the optional Device Access Code (printed on the
gateway), used for the few locked pages; the main status pages aren't behind
a login. Validation fetches the System Information page and checks for
a "Manufacturer" row, using the same RESOURCE_SCHEMA/create_rest_data_from_config
building blocks the rest of this integration reuses from
homeassistant.components.rest - so a wrong/unreachable host, or a host that
answers but isn't actually this gateway, is caught immediately in the UI.
If an access code is given, it's checked with a real login.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import GatewayAuthError, GatewayClient, GatewayConnectionError
from .const import (
    CONF_ACCESS_CODE,
    CONF_HOST,
    CONF_NAME,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DOMAIN,
    SYSINFO_PATH,
)
from .util import build_rest_config

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_ACCESS_CODE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

# Sanity-check marker: present on a real BGW-series gateway's System
# Information page, verified against a live device.
EXPECTED_MARKER = "Manufacturer"


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the gateway."""


class NotAGateway(HomeAssistantError):
    """Error to indicate the host answered but doesn't look like this gateway."""


class InvalidAccessCode(HomeAssistantError):
    """Error to indicate the gateway rejected the Device Access Code."""


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Fetch the System Information page and sanity-check its contents."""
    host = data[CONF_HOST]
    rest_config = build_rest_config(host, SYSINFO_PATH)
    rest = create_rest_data_from_config(hass, rest_config)
    try:
        await rest.async_update()
    except Exception as ex:  # noqa: BLE001 - RestData wraps httpx/aiohttp errors broadly
        raise CannotConnect from ex

    if rest.data is None:
        raise CannotConnect

    if EXPECTED_MARKER not in rest.data:
        raise NotAGateway

    if access_code := data.get(CONF_ACCESS_CODE):
        client = GatewayClient(hass, host, access_code)
        try:
            await client.async_validate()
        except GatewayAuthError as ex:
            raise InvalidAccessCode from ex
        except GatewayConnectionError as ex:
            raise CannotConnect from ex
        finally:
            await client.async_close()


class AttGatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AT&T Gateway."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial setup step."""
        return await self._async_step_form(user_input, is_reconfigure=False)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle changing the gateway's host after setup."""
        return await self._async_step_form(user_input, is_reconfigure=True)

    async def _async_step_form(
        self, user_input: dict[str, Any] | None, is_reconfigure: bool
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_ACCESS_CODE):
                user_input.pop(CONF_ACCESS_CODE, None)
            try:
                await _async_validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NotAGateway:
                errors["base"] = "not_a_gateway"
            except InvalidAccessCode:
                errors["base"] = "invalid_access_code"
            except Exception:  # noqa: BLE001 - genuinely unknown failure, surface generically
                _LOGGER.exception("Unexpected exception during AT&T Gateway setup")
                errors["base"] = "unknown"
            else:
                if is_reconfigure:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data=user_input
                    )
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        if is_reconfigure and user_input is None:
            user_input = dict(self._get_reconfigure_entry().data)

        step_id = "reconfigure" if is_reconfigure else "user"
        schema = self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)
