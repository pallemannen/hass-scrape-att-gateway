"""Buttons for the AT&T Gateway integration (need the Device Access Code)."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .api import GatewayAuthError, GatewayClient, GatewayConnectionError
from .const import RESTART_PATH, SPEED_PATH, SPEED_TEST_DURATION
from .util import entity_object_id

ENTITY_ID_FORMAT = "button.{}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AT&T Gateway buttons from a config entry."""
    client: GatewayClient | None = entry.runtime_data["client"]
    if client is None:
        return
    device_info: DeviceInfo = entry.runtime_data["device_info"]
    async_add_entities(
        [
            RunSpeedTestButton(hass, client, device_info, entry.runtime_data["speed"]),
            RestartButton(hass, client, device_info),
        ]
    )


class GatewayButton(ButtonEntity):
    """Submits one form on a locked gateway page."""

    _attr_has_entity_name = True
    _path: str
    _fields: dict[str, str]

    def __init__(
        self, hass: HomeAssistant, client: GatewayClient, device_info: DeviceInfo, key: str
    ) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_unique_id = f"att_gateway_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )

    async def async_press(self) -> None:
        """Submit the form."""
        try:
            await self._client.async_submit(self._path, self._fields)
        except (GatewayAuthError, GatewayConnectionError) as err:
            raise HomeAssistantError(f"{self.name} failed: {err}") from err


class RunSpeedTestButton(GatewayButton):
    """Starts the gateway's own speed test (measured from the gateway, not from HA)."""

    _attr_name = "Run Speed Test"
    _attr_icon = "mdi:speedometer"
    _path = SPEED_PATH
    _fields = {"hidden": "", "run": "Run Speed Test"}

    def __init__(self, hass, client, device_info, coordinator_speed) -> None:
        """Initialize the button."""
        super().__init__(hass, client, device_info, "run_speed_test")
        self._coordinator_speed = coordinator_speed

    async def async_press(self) -> None:
        """Start the test, then refresh the results once it has finished."""
        await super().async_press()
        async_call_later(
            self.hass,
            timedelta(seconds=SPEED_TEST_DURATION),
            lambda _now: self.hass.async_create_task(
                self._coordinator_speed.async_request_refresh()
            ),
        )


class RestartButton(GatewayButton):
    """Restarts the gateway. Takes the internet connection down for a few minutes."""

    _attr_name = "Restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _path = RESTART_PATH
    _fields = {"Restart": "Restart"}

    def __init__(self, hass, client, device_info) -> None:
        """Initialize the button."""
        super().__init__(hass, client, device_info, "restart")
