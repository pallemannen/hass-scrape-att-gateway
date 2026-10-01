"""Wi-Fi Mode select for the AT&T Gateway integration (needs the Device Access Code)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import GatewayAuthError, GatewayClient, GatewayConnectionError
from .const import WIFI_MODES, WIFI_PATH, WIFI_SAVE_BUTTON, WIFI_SWITCHES
from .util import entity_object_id, extract_text

ENTITY_ID_FORMAT = "select.{}"
_RADIO_FIELDS = tuple(field for key, _, field in WIFI_SWITCHES if key != "guest_wifi")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wi-Fi Mode select from a config entry."""
    client: GatewayClient | None = entry.runtime_data["client"]
    if client is None:
        return
    async_add_entities(
        [WifiModeSelect(hass, entry.runtime_data["wifi"], client, entry.runtime_data["device_info"])]
    )


class WifiModeSelect(CoordinatorEntity[DataUpdateCoordinator], SelectEntity):
    """Which Wi-Fi radios are on: off, 2.4 GHz, 5 GHz or all."""

    _attr_has_entity_name = True
    _attr_name = "Wi-Fi Mode"
    _attr_translation_key = "wifi_mode"
    _attr_options = list(WIFI_MODES)

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        client: GatewayClient,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = "att_gateway_wifi_mode"
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )

    @property
    def current_option(self) -> str | None:
        """Return the mode matching the radios' current settings."""
        radios = tuple(
            extract_text(self.coordinator, f'select[name="{field}"] option[selected]', "value")
            for field in _RADIO_FIELDS
        )
        return next((mode for mode, setting in WIFI_MODES.items() if setting == radios), None)

    async def async_select_option(self, option: str) -> None:
        """Set the radios for the chosen mode."""
        changes = dict(zip(_RADIO_FIELDS, WIFI_MODES[option]))
        try:
            await self._client.async_save_form(WIFI_PATH, changes, WIFI_SAVE_BUTTON)
        except (GatewayAuthError, GatewayConnectionError) as err:
            raise HomeAssistantError(f"{self.name} failed: {err}") from err
        await self.coordinator.async_request_refresh()
