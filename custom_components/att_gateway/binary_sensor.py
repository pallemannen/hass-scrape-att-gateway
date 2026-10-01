"""Binary sensor for the AT&T Gateway integration."""
from __future__ import annotations

from collections.abc import Callable

import logging
import re

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
    FIBER_ALARM_TABLES,
    FIREWALL_FIELDS,
    GatewayField,
    IPV6_SETTING_FIELDS,
    LAN_PORT_LINK_FIELDS,
    ON_OFF_ICONS,
    STATUS_FIELDS,
    WIFI_RADIO_FIELDS,
)
from .util import entity_object_id, extract_text

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = "binary_sensor.{}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AT&T Gateway binary sensor from a config entry."""
    coordinator_status: ScrapeCoordinator = entry.runtime_data["status"]
    device_info: DeviceInfo = entry.runtime_data["device_info"]
    coordinator_lan: ScrapeCoordinator = entry.runtime_data["lan"]
    entities: list[BinarySensorEntity] = [
        ConnectivitySensor(hass, coordinator_status, coordinator_lan, device_info),
        DerivedSensor(
            hass, coordinator_status, device_info, "wan", "WAN", _wan_state,
            BinarySensorDeviceClass.CONNECTIVITY,
        ),
        DerivedSensor(
            hass, coordinator_lan, device_info, "lan", "LAN",
            lambda c: _any_on(_port_states(c)), BinarySensorDeviceClass.CONNECTIVITY,
        ),
        DerivedSensor(
            hass, coordinator_lan, device_info, "wifi", "Wi-Fi",
            lambda c: _any_on(_radio_states(c)),
        ),
    ]
    entities.extend(
        OnOffFieldSensor(hass, entry.runtime_data["firewall"], field, device_info)
        for field in FIREWALL_FIELDS
    )
    entities.append(
        OnOffFieldSensor(hass, entry.runtime_data["lan"], DHCP_SERVER_FIELD, device_info)
    )
    entities.append(FiberAlarmSensor(hass, entry.runtime_data["fiber"], device_info))
    entities.extend(
        StateFieldSensor(
            hass, entry.runtime_data["lan"], field, device_info, ("up", "down"),
            BinarySensorDeviceClass.CONNECTIVITY,
        )
        for field in LAN_PORT_LINK_FIELDS
    )
    if entry.runtime_data["client"] is None:
        # With the access code, the Wi-Fi switches show (and set) this instead.
        entities.extend(
            StateFieldSensor(
                hass, entry.runtime_data["lan"], field, device_info, ("enabled", "disabled")
            )
            for field in WIFI_RADIO_FIELDS
        )
    if (coordinator_ipv6 := entry.runtime_data.get("ipv6")) is not None:
        entities.extend(
            OnOffFieldSensor(hass, coordinator_ipv6, field, device_info)
            for field in IPV6_SETTING_FIELDS
        )
    async_add_entities(entities)


def _two_state(
    value: str | None, name: str, on: str, off: str, prefix: bool = False
) -> bool | None:
    """Map a gateway value to on/off; unexpected values become unknown (None)."""
    if not value:
        return None
    value = value.lower()
    if value == on or (prefix and value.startswith(on + " ")):
        return True
    if value == off or (prefix and value.startswith(off + " ")):
        return False
    _LOGGER.debug("Unexpected %s value %r", name, value)
    return None


def _wan_state(coordinator: ScrapeCoordinator) -> bool | None:
    """WAN is up when the broadband page says "Up"; anything else is down."""
    select = next(f.select for f in STATUS_FIELDS if f.key == CONNECTION_STATUS_FIELD_KEY)
    value = extract_text(coordinator, select)
    return value.lower() == "up" if value is not None else None


def _port_states(coordinator: ScrapeCoordinator) -> list[bool | None]:
    return [
        _two_state(extract_text(coordinator, f.select), f.name, "up", "down")
        for f in LAN_PORT_LINK_FIELDS
    ]


def _radio_states(coordinator: ScrapeCoordinator) -> list[bool | None]:
    return [
        _two_state(extract_text(coordinator, f.select), f.name, "enabled", "disabled")
        for f in WIFI_RADIO_FIELDS
    ]


def _any_on(states: list[bool | None]) -> bool | None:
    """On if any is on, off if all are off, otherwise unknown."""
    if any(state is True for state in states):
        return True
    if states and all(state is False for state in states):
        return False
    return None


class DerivedSensor(CoordinatorEntity[ScrapeCoordinator], BinarySensorEntity):
    """A binary sensor computed from one page's data (icons from icons.json)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        device_info: DeviceInfo,
        key: str,
        name: str,
        compute: Callable[[ScrapeCoordinator], bool | None],
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._compute = compute
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_unique_id = f"att_gateway_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(name), hass=hass
        )

    @property
    def is_on(self) -> bool | None:
        """Return the computed state."""
        return self._compute(self.coordinator)


class ConnectivitySensor(DerivedSensor):
    """WAN up AND (any LAN port connected OR any Wi-Fi radio on)."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator_status: ScrapeCoordinator,
        coordinator_lan: ScrapeCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            hass, coordinator_status, device_info, "connectivity", "Connectivity",
            _wan_state, BinarySensorDeviceClass.CONNECTIVITY,
        )
        self._coordinator_lan = coordinator_lan

    async def async_added_to_hass(self) -> None:
        """Also update when the LAN page refreshes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator_lan.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def available(self) -> bool:
        """Available when both pages are."""
        return super().available and self._coordinator_lan.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return true if the gateway is providing connectivity."""
        wan = _wan_state(self.coordinator)
        if not wan:
            return wan
        lan = _any_on(_port_states(self._coordinator_lan))
        wifi = _any_on(_radio_states(self._coordinator_lan))
        if lan or wifi:
            return True
        if lan is False and wifi is False:
            return False
        return None


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
        self._attr_entity_registry_enabled_default = field.enabled
        self._attr_unique_id = f"att_gateway_{field.key}"
        self._attr_translation_key = field.key
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the gateway shows the feature as on."""
        # "On", "On (public IP address)", "Off"; anything else is unknown.
        return _two_state(
            extract_text(self.coordinator, self._field.select, self._field.attr),
            self._field.name, "on", "off", prefix=True,
        )

    @property
    def icon(self) -> str | None:
        """Return a state-dependent icon."""
        on_icon, off_icon = ON_OFF_ICONS[self._field.key]
        return on_icon if self.is_on else off_icon


class FiberAlarmSensor(CoordinatorEntity[ScrapeCoordinator], BinarySensorEntity):
    """On when any of the fiber module's alarm/warning counters is non-zero."""

    _attr_has_entity_name = True
    _attr_name = "Fiber Alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:wan"

    def __init__(
        self, hass: HomeAssistant, coordinator: ScrapeCoordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "att_gateway_fiber_alarm"
        self._attr_translation_key = "fiber_alarm"
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )

    def _counts(self) -> dict[str, int] | None:
        """Return {"<table>_<alarm|warning>_<low|high>": count} for all tables."""
        soup = self.coordinator.data
        if soup is None:
            return None
        counts: dict[str, int] = {}
        for key, table in FIBER_ALARM_TABLES.items():
            for tr in soup.select(f"{table} tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
                if len(cells) != 3:
                    continue
                for level, cell in zip(("low", "high"), cells[1:]):
                    match = re.match(r"\d+", cell)
                    if match:
                        counts[f"{key}_{cells[0].lower()}_{level}"] = int(match.group())
        return counts or None

    @property
    def is_on(self) -> bool | None:
        """Return true if any alarm or warning counter is non-zero."""
        counts = self._counts()
        return any(counts.values()) if counts is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Return the non-zero counters."""
        counts = self._counts()
        return {k: v for k, v in counts.items() if v} if counts else None


class StateFieldSensor(OnOffFieldSensor):
    """A two-state row: on when the gateway shows `on_value` (icons from icons.json)."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        field: GatewayField,
        device_info: DeviceInfo,
        values: tuple[str, str],
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the sensor with the gateway's (on, off) values."""
        super().__init__(hass, coordinator, field, device_info)
        self._values = values
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        """Return true/false for the known values, None (unknown) for anything else."""
        return _two_state(
            extract_text(self.coordinator, self._field.select), self._field.name, *self._values
        )

    @property
    def icon(self) -> None:
        """Leave icons to icons.json."""
        return None
