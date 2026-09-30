"""Sensors for the AT&T Gateway integration.

Each sensor is a thin CoordinatorEntity reading a CSS selector out of the
BeautifulSoup document `ScrapeCoordinator.data` already holds - the fetch/
parse work is entirely `scrape`'s (see the package docstring in __init__.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import socket

from homeassistant.components.scrape.coordinator import ScrapeCoordinator
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BYTE_FIELD_KEYS,
    CONF_HOST,
    CONNECTION_STATUS_FIELD_KEY,
    COUNTER_FIELD_KEYS,
    CURRENT_TIME_FIELD_KEY,
    CURRENT_TIME_FORMAT,
    DEFAULT_SCAN_INTERVAL,
    GAUGE_FIELD_KEYS,
    GatewayField,
    ICON_ACTIVE,
    ICON_INACTIVE,
    LAN_FIELDS,
    LAN_INTERFACES_TABLE,
    LAN_PORT_SPEED_FIELD_KEYS,
    LAST_REBOOT_ICON,
    LINK_SPEED_FIELD_KEYS,
    NAT_FIELDS,
    SPEED_TABLE,
    SPEED_TIME_FORMAT,
    STATIC_ICONS,
    STATUS_FIELDS,
    SYSINFO_FIELDS,
    SYSTEM_UPTIME_FIELD_KEY,
)
from .util import entity_object_id, extract_text as _extract_text

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = "sensor.{}"
# Only IpAddressSensor polls; everything else is coordinator-driven.
SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


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

    coordinator_lan: ScrapeCoordinator = entry.runtime_data["lan"]
    for coordinator, fields in (
        (coordinator_status, STATUS_FIELDS),
        (coordinator_lan, LAN_FIELDS),
        (entry.runtime_data.get("nat"), NAT_FIELDS),
    ):
        if coordinator is None:
            continue
        for field in fields:
            if field.key in COUNTER_FIELD_KEYS:
                cls = CounterFieldSensor
            elif field.key in GAUGE_FIELD_KEYS:
                cls = GaugeFieldSensor
            elif field.key in LINK_SPEED_FIELD_KEYS:
                cls = LinkSpeedSensor
            elif field.key in LAN_PORT_SPEED_FIELD_KEYS:
                cls = LanPortSpeedSensor
            else:
                cls = GatewayFieldSensor
            entities.append(cls(hass, coordinator, field, device_info))

    entities.append(LastRebootSensor(hass, coordinator_sysinfo, device_info))
    entities.append(IpAddressSensor(hass, entry.data[CONF_HOST], device_info))
    entities.extend(
        ClientCountSensor(hass, coordinator_lan, device_info, key, name, column)
        for key, name, column in (
            ("active_client_count", "Number of Active Clients", 3),
            ("inactive_client_count", "Number of Inactive Clients", 4),
        )
    )

    if (coordinator_speed := entry.runtime_data.get("speed")) is not None:
        entities.extend(
            SpeedTestSensor(hass, coordinator_speed, device_info, key, name, direction)
            for key, name, direction in (
                ("speed_test_download", "Speed Test Download", "downstream"),
                ("speed_test_upload", "Speed Test Upload", "upstream"),
            )
        )
        entities.append(LastSpeedTestSensor(hass, coordinator_speed, device_info))

    async_add_entities(entities)


def _init_entity(entity, hass: HomeAssistant, key: str, device_info: DeviceInfo) -> None:
    """Shared unique_id/entity_id/device/icon setup for the derived sensors."""
    entity._attr_unique_id = f"att_gateway_{key}"
    entity._attr_device_info = device_info
    entity._attr_icon = STATIC_ICONS.get(key)
    entity.entity_id = async_generate_entity_id(
        ENTITY_ID_FORMAT, entity_object_id(entity._attr_name), hass=hass
    )


def _parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


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
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
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
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
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


class GaugeFieldSensor(GatewayFieldSensor):
    """A GatewayFieldSensor whose value is a plain integer that goes up and down."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the value, parsed as an int."""
        return _parse_int(_extract_text(self.coordinator, self._field.select))


class LinkSpeedSensor(GaugeFieldSensor):
    """A link speed the gateway reports in Mbps."""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND


class LanPortSpeedSensor(LinkSpeedSensor):
    """A LAN port speed; the gateway reports these in bit/s (0 when the port is down)."""

    @property
    def native_value(self) -> int | None:
        """Return the port speed in Mbps."""
        value = super().native_value
        return value // 1_000_000 if value is not None else None


class ClientCountSensor(CoordinatorEntity[ScrapeCoordinator], SensorEntity):
    """Active or inactive client count, summed over the LAN Interfaces table.

    That table has one row per interface (Ethernet, 5G Ethernet, Wi-Fi 2.4/5
    GHz, Mesh Clients) with "Active Devices"/"Inactive Devices" columns.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        device_info: DeviceInfo,
        key: str,
        name: str,
        column: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._select = f"{LAN_INTERFACES_TABLE} tr td:nth-child({column})"
        _init_entity(self, hass, key, device_info)

    @property
    def native_value(self) -> int | None:
        """Return the summed count."""
        if self.coordinator.data is None:
            return None
        values = [_parse_int(td.get_text(strip=True)) for td in self.coordinator.data.select(self._select)]
        values = [v for v in values if v is not None]
        return sum(values) if values else None


class SpeedTestSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Throughput of the gateway's most recent speed test in one direction."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        key: str,
        name: str,
        direction: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._direction = direction
        _init_entity(self, hass, key, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the newest result's throughput for this direction."""
        for cells in _speed_rows(self.coordinator):
            if len(cells) > 2 and cells[1] == self._direction:
                try:
                    return float(cells[2])
                except ValueError:
                    return None
        return None


class LastSpeedTestSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Completion time of the gateway's most recent speed test (gateway local time)."""

    _attr_has_entity_name = True
    _attr_name = "Last Speed Test"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, hass: HomeAssistant, coordinator: DataUpdateCoordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        _init_entity(self, hass, "last_speed_test", device_info)

    @property
    def native_value(self) -> datetime | None:
        """Return the newest result's completion time."""
        for cells in _speed_rows(self.coordinator):
            try:
                naive = datetime.strptime(cells[0], SPEED_TIME_FORMAT)
            except (IndexError, ValueError):
                continue
            return naive.replace(tzinfo=dt_util.now().tzinfo)
        return None


def _speed_rows(coordinator: DataUpdateCoordinator) -> list[list[str]]:
    """Return the speed test history rows as lists of cell texts, newest first."""
    if coordinator.data is None:
        return []
    return [
        [td.get_text(strip=True) for td in tr.select("td")]
        for tr in coordinator.data.select(f"{SPEED_TABLE} tr")
    ]


class IpAddressSensor(SensorEntity):
    """The address Home Assistant reaches the gateway on (the configured host).

    Normally the same as "LAN IP Address"; if the configured host is a name,
    it is resolved, so a DNS change shows up here.
    """

    _attr_has_entity_name = True
    _attr_name = "IP Address"

    def __init__(self, hass: HomeAssistant, host: str, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._host = host
        _init_entity(self, hass, "ip_address", device_info)

    async def async_added_to_hass(self) -> None:
        """Resolve right away instead of waiting for the first poll."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Resolve the configured host."""
        try:
            self._attr_native_value = await self.hass.async_add_executor_job(
                socket.gethostbyname, self._host
            )
        except OSError:
            self._attr_native_value = None
