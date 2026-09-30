"""Binary sensor for the AT&T Gateway integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONNECTION_STATUS_FIELD_KEY,
    DHCP_SERVER_FIELD,
    FIREWALL_FIELDS,
    GatewayField,
    ICON_ACTIVE,
    ICON_INACTIVE,
    ON_OFF_ICONS,
    STATUS_FIELDS,
)
from .util import entity_object_id, extract_text

ENTITY_ID_FORMAT = "binary_sensor.{}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AT&T Gateway binary sensor from a config entry."""
    coordinator_status: ScrapeCoordinator = entry.runtime_data["status"]
    device_info: DeviceInfo = entry.runtime_data["device_info"]
    entities: list[BinarySensorEntity] = [
        GatewayConnectivitySensor(hass, coordinator_status, device_info)
    ]
    entities.extend(
        OnOffFieldSensor(hass, entry.runtime_data["firewall"], field, device_info)
        for field in FIREWALL_FIELDS
    )
    entities.append(
        OnOffFieldSensor(hass, entry.runtime_data["lan"], DHCP_SERVER_FIELD, device_info)
    )
    async_add_entities(entities)


class GatewayConnectivitySensor(CoordinatorEntity[ScrapeCoordinator], BinarySensorEntity):
    """Derived connectivity sensor: on when Connection Status is "Up".

    "up" is the verified value on a real BGW320-500 - matches the
    previously-validated manual Template Helper (`binary_sensor.at_t_connection`)
    this integration replaces.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Connectivity"

    def __init__(
        self, hass: HomeAssistant, coordinator: ScrapeCoordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "att_gateway_connectivity"
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )
        self._select = next(
            f.select for f in STATUS_FIELDS if f.key == CONNECTION_STATUS_FIELD_KEY
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the gateway reports its connection as up."""
        value = extract_text(self.coordinator, self._select)
        return value.lower() == "up" if value is not None else None

    @property
    def icon(self) -> str:
        """Return a state-dependent icon."""
        return ICON_ACTIVE if self.is_on else ICON_INACTIVE


class OnOffFieldSensor(CoordinatorEntity[ScrapeCoordinator], BinarySensorEntity):
    """A status row the gateway shows as "On"/"Off" (firewall features, DHCP server)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        field: GatewayField,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._field = field
        self._attr_name = field.name
        self._attr_unique_id = f"att_gateway_{field.key}"
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the gateway shows the feature as on."""
        value = extract_text(self.coordinator, self._field.select)
        return value.lower().startswith("on") if value else None

    @property
    def icon(self) -> str | None:
        """Return a state-dependent icon."""
        on_icon, off_icon = ON_OFF_ICONS[self._field.key]
        return on_icon if self.is_on else off_icon
