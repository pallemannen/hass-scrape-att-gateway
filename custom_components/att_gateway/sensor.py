"""Sensors for the AT&T Gateway integration.

Each sensor is a thin CoordinatorEntity reading a CSS selector out of the
BeautifulSoup document `ScrapeCoordinator.data` already holds - the fetch/
parse work is entirely `scrape`'s (see the package docstring in __init__.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    BYTE_FIELD_KEYS,
    CONNECTION_STATUS_FIELD_KEY,
    COUNTER_FIELD_KEYS,
    CURRENT_TIME_FIELD_KEY,
    CURRENT_TIME_FORMAT,
    GatewayField,
    ICON_ACTIVE,
    ICON_INACTIVE,
    LAST_REBOOT_ICON,
    STATIC_ICONS,
    STATUS_FIELDS,
    SYSINFO_FIELDS,
    SYSTEM_UPTIME_FIELD_KEY,
)
from .util import extract_text as _extract_text

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = "sensor.{}"


def _parse_current_time(raw: str | None) -> datetime | None:
    """Parse the gateway's own "Current Date/Time" field into an aware datetime.

    Verified format on a real BGW320-500: "2026-08-19T13:23:01" (no
    trailing "Z", unlike First Use Date) - the "T" is replaced with a space
    before parsing, matching the previously-validated manual Template Helper
    this integration replaces.
    """
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw.replace("T", " "), CURRENT_TIME_FORMAT)
    except ValueError:
        return None
    return naive.replace(tzinfo=dt_util.now().tzinfo)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AT&T Gateway sensors from a config entry."""
    coordinator_sysinfo: ScrapeCoordinator = entry.runtime_data["sysinfo"]
    coordinator_status: ScrapeCoordinator = entry.runtime_data["status"]
    device_info: DeviceInfo = entry.runtime_data["device_info"]

    entities: list[SensorEntity] = []
    for field in SYSINFO_FIELDS:
        if field.key == CURRENT_TIME_FIELD_KEY:
            entities.append(CurrentTimeSensor(hass, coordinator_sysinfo, field, device_info))
        elif field.key == SYSTEM_UPTIME_FIELD_KEY:
            entities.append(UptimeSensor(hass, coordinator_sysinfo, field, device_info))
        elif field.key == "first_use_date":
            entities.append(
                TimestampFieldSensor(hass, coordinator_sysinfo, field, device_info)
            )
        else:
            entities.append(GatewayFieldSensor(hass, coordinator_sysinfo, field, device_info))

    for field in STATUS_FIELDS:
        if field.key in COUNTER_FIELD_KEYS:
            entities.append(CounterFieldSensor(hass, coordinator_status, field, device_info))
        else:
            entities.append(GatewayFieldSensor(hass, coordinator_status, field, device_info))

    entities.append(LastRebootSensor(hass, coordinator_sysinfo, device_info))

    async_add_entities(entities)


class GatewayFieldSensor(CoordinatorEntity[ScrapeCoordinator], SensorEntity):
    """A sensor reading a single scraped field as plain stripped text."""

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
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )
        self._static_icon = STATIC_ICONS.get(field.key)

    @property
    def native_value(self) -> str | None:
        """Return the sensor's current value."""
        return _extract_text(self.coordinator, self._field.select)

    @property
    def icon(self) -> str | None:
        """Return a static icon, or a state-dependent one for Connection Status."""
        if self._field.key == CONNECTION_STATUS_FIELD_KEY:
            value = self.native_value
            return ICON_ACTIVE if value and value.lower() == "up" else ICON_INACTIVE
        return self._static_icon


class CounterFieldSensor(GatewayFieldSensor):
    """A GatewayFieldSensor whose value is a plain integer counter."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        field: GatewayField,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, coordinator, field, device_info)
        if field.key in BYTE_FIELD_KEYS:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.BYTES

    @property
    def native_value(self) -> int | None:
        """Return the counter's current value, parsed as an int."""
        raw = _extract_text(self.coordinator, self._field.select)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            _LOGGER.warning(
                "Could not parse %s as an integer (raw value %r)", self._field.name, raw
            )
            return None


class TimestampFieldSensor(GatewayFieldSensor):
    """A GatewayFieldSensor whose value is an ISO8601 UTC timestamp (has a "Z")."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the parsed timestamp."""
        raw = _extract_text(self.coordinator, self._field.select)
        return dt_util.parse_datetime(raw) if raw else None


class CurrentTimeSensor(GatewayFieldSensor):
    """The gateway's own "Current Date/Time" field, exposed as a timestamp."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the gateway's current time, parsed and localized."""
        raw = _extract_text(self.coordinator, self._field.select)
        return _parse_current_time(raw)


class UptimeSensor(GatewayFieldSensor):
    """The gateway's own "Time Since Last Reboot" field (seconds), as a duration."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the uptime in seconds."""
        raw = _extract_text(self.coordinator, self._field.select)
        if raw is None:
            return None
        try:
            return int(float(raw))
        except ValueError:
            return None


class LastRebootSensor(CoordinatorEntity[ScrapeCoordinator], SensorEntity):
    """Derived timestamp sensor: the gateway's own current time minus its own uptime.

    Deliberately anchored to the gateway's own clock rather than
    dt_util.utcnow() - mirrors the previously-validated manual Template
    Helper (`sensor.at_t_last_reboot`) this integration replaces, and avoids
    drift if the gateway's clock and Home Assistant's disagree.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_name = "Last Reboot"

    def __init__(
        self, hass: HomeAssistant, coordinator: ScrapeCoordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_icon = LAST_REBOOT_ICON
        self._attr_unique_id = "att_gateway_last_reboot"
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )
        self._current_time_select = next(
            f.select for f in SYSINFO_FIELDS if f.key == CURRENT_TIME_FIELD_KEY
        )
        self._uptime_select = next(
            f.select for f in SYSINFO_FIELDS if f.key == SYSTEM_UPTIME_FIELD_KEY
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the computed last-reboot timestamp."""
        gateway_now = _parse_current_time(
            _extract_text(self.coordinator, self._current_time_select)
        )
        raw_uptime = _extract_text(self.coordinator, self._uptime_select)
        if gateway_now is None or raw_uptime is None:
            return None
        try:
            uptime_seconds = float(raw_uptime)
        except ValueError:
            return None
        return gateway_now - timedelta(seconds=uptime_seconds)
