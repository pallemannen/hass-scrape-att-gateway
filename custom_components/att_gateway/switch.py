"""Wi-Fi switches for the AT&T Gateway integration (need the Device Access Code)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import GatewayAuthError, GatewayClient, GatewayConnectionError
from .const import ICON_WIFI_OFF, ICON_WIFI_ON, WIFI_PATH, WIFI_SAVE_BUTTON, WIFI_SWITCHES
from .util import entity_object_id, extract_text

ENTITY_ID_FORMAT = "switch.{}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AT&T Gateway Wi-Fi switches from a config entry."""
    client: GatewayClient | None = entry.runtime_data["client"]
    if client is None:
        return
    device_info: DeviceInfo = entry.runtime_data["device_info"]
    async_add_entities(
        WifiSwitch(hass, entry.runtime_data["wifi"], client, device_info, key, name, field)
        for key, name, field in WIFI_SWITCHES
    )


class WifiSwitch(CoordinatorEntity[DataUpdateCoordinator], SwitchEntity):
    """Turns a Wi-Fi radio or the guest network on or off."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        client: GatewayClient,
        device_info: DeviceInfo,
        key: str,
        name: str,
        field: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._client = client
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"att_gateway_{key}"
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(name), hass=hass
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the setting is on."""
        value = extract_text(self.coordinator, f'select[name="{self._field}"] option[selected]', "value")
        return value == "on" if value else None

    @property
    def icon(self) -> str:
        """Return a state-dependent icon."""
        return ICON_WIFI_ON if self.is_on else ICON_WIFI_OFF

    async def _async_set(self, value: str) -> None:
        try:
            await self._client.async_save_form(WIFI_PATH, {self._field: value}, WIFI_SAVE_BUTTON)
        except (GatewayAuthError, GatewayConnectionError) as err:
            raise HomeAssistantError(f"{self.name} failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self._async_set("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self._async_set("off")
