"""Sensors for the AT&T Gateway integration.

Each sensor is a thin CoordinatorEntity reading a CSS selector out of the
BeautifulSoup document `ScrapeCoordinator.data` already holds - the fetch/
parse work is entirely `scrape`'s (see the package docstring in __init__.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
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
    COUNTER_FIELD_KEYS,
    CURRENT_TIME_FIELD_KEY,
    CURRENT_TIME_FORMAT,
    DEFAULT_SCAN_INTERVAL,
    ENUM_STATUS_FIELDS,
    FIBER_FIELDS,
    GAUGE_FIELD_KEYS,
    GatewayField,
    LAN_FIELDS,
    LAN_INTERFACES_TABLE,
    LAN_PORT_SPEED_FIELD_KEYS,
    LAST_REBOOT_ICON,
    LINK_SPEED_FIELD_KEYS,
    LIST_COUNTS,
    NAT_FIELDS,
    PACKET_FILTER_TABLE,
    PASSTHROUGH_FIELDS,
    PASSTHROUGH_LEASE_INPUTS,
    RA_MTU_FIELD,
    SPEED_TABLE,
    SPEED_TIME_FORMAT,
    STATIC_ICONS,
    STATUS_FIELDS,
    SYSINFO_FIELDS,
    SYSTEM_UPTIME_FIELD_KEY,
    WIFI_SSID_FIELDS,
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
        (entry.runtime_data["fiber"], FIBER_FIELDS),
        (entry.runtime_data.get("nat"), NAT_FIELDS),
        (entry.runtime_data.get("ipv6"), (RA_MTU_FIELD,)),
        (entry.runtime_data.get("passthrough"), PASSTHROUGH_FIELDS),
        (entry.runtime_data.get("wifi"), WIFI_SSID_FIELDS),
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
            elif field.key in ENUM_STATUS_FIELDS:
                cls = StatusSensor
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

    if (coordinator_passthrough := entry.runtime_data.get("passthrough")) is not None:
        entities.append(PassthroughLeaseSensor(hass, coordinator_passthrough, device_info))
    for key, name, _, table in LIST_COUNTS:
        if (coordinator := entry.runtime_data.get(key)) is not None:
            entities.append(ListCountSensor(hass, coordinator, device_info, key, name, table))
    if (coordinator_pf := entry.runtime_data.get("packet_filter")) is not None:
        entities.append(PacketFilterRulesSensor(hass, coordinator_pf, device_info))

    async_add_entities(entities)


def _init_entity(entity, hass: HomeAssistant, key: str, device_info: DeviceInfo) -> None:
    """Shared unique_id/entity_id/device/icon setup for the derived sensors."""
    entity._attr_unique_id = f"att_gateway_{key}"
    entity._attr_translation_key = key
    entity._attr_device_info = device_info
    entity._attr_icon = STATIC_ICONS.get(key)
    entity.entity_id = async_generate_entity_id(
        ENTITY_ID_FORMAT, entity_object_id(entity._attr_name), hass=hass
    )


def _cell_text(td) -> str:
    return re.sub(r"\s+", " ", td.get_text(" ", strip=True))


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
        self._attr_entity_registry_enabled_default = field.enabled
        self._attr_unique_id = f"att_gateway_{field.key}"
        self._attr_translation_key = field.key
        self._attr_device_info = device_info
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, entity_object_id(self._attr_name), hass=hass
        )
        self._static_icon = STATIC_ICONS.get(field.key)

    @property
    def native_value(self) -> str | None:
        """Return the sensor's current value."""
        return _extract_text(self.coordinator, self._field.select, self._field.attr)

    @property
    def icon(self) -> str | None:
        """Return a static icon, or a state-dependent one for Connection Status."""
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
        self._attr_translation_key = "last_reboot"
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
        return _parse_int(_extract_text(self.coordinator, self._field.select, self._field.attr))


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
    """Active or inactive client count, summed over the LAN Interfaces table."""

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
    """The address Home Assistant reaches the gateway on (configured host, resolved)."""

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


class PassthroughLeaseSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """The passthrough DHCP lease time (days/hours/minutes/seconds form fields)."""

    _attr_has_entity_name = True
    _attr_name = "Passthrough DHCP Lease"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self, hass: HomeAssistant, coordinator: DataUpdateCoordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        _init_entity(self, hass, "passthrough_dhcp_lease", device_info)

    @property
    def native_value(self) -> int | None:
        """Return the lease time in seconds."""
        total = 0
        for name, seconds in PASSTHROUGH_LEASE_INPUTS.items():
            value = _parse_int(_extract_text(self.coordinator, f'input[name="{name}"]', "value"))
            if value is None:
                return None
            total += value * seconds
        return total


class ListCountSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Number of entries in a list table; the entries' cell texts as an attribute."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        key: str,
        name: str,
        table: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._table = table
        _init_entity(self, hass, key, device_info)

    def _entries(self) -> list[str] | None:
        if self.coordinator.data is None:
            return None
        # The empty list is a single <th> row ("No ... entries have been defined").
        return [
            " | ".join(cell for cell in map(_cell_text, tr.select("td")) if cell)
            for tr in self.coordinator.data.select(f"{self._table} tr")
            if tr.select("td")
        ]

    @property
    def native_value(self) -> int | None:
        """Return the number of entries."""
        entries = self._entries()
        return len(entries) if entries is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, list[str]] | None:
        """Return the entries."""
        entries = self._entries()
        return {"entries": entries} if entries else None


class PacketFilterRulesSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Number of packet filter rules that have at least one match condition.

    Each rule is a numbered row followed by rows for its match conditions;
    empty rule slots are shown too, so those aren't counted.
    """

    _attr_has_entity_name = True
    _attr_name = "Number of Packet Filter Rules"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, hass: HomeAssistant, coordinator: DataUpdateCoordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        _init_entity(self, hass, "packet_filter_rules", device_info)

    def _rules(self) -> list[str] | None:
        if self.coordinator.data is None:
            return None
        rules: list[list[str]] = []
        for tr in self.coordinator.data.select(f"{PACKET_FILTER_TABLE} tr"):
            cells = [_cell_text(td) for td in tr.select("td")]
            if not cells:
                continue
            if cells[0].isdigit():
                rules.append([])
            elif rules and any(cells):
                rules[-1].append(" ".join(c for c in cells if c))
        return [" / ".join(r) for r in rules if r]

    @property
    def native_value(self) -> int | None:
        """Return the number of non-empty rules."""
        rules = self._rules()
        return len(rules) if rules is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, list[str]] | None:
        """Return the rules' match conditions."""
        rules = self._rules()
        return {"rules": rules} if rules else None


class StatusSensor(GatewayFieldSensor):
    """A link or Wi-Fi status as an enum; icons per state come from icons.json."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        field: GatewayField,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, coordinator, field, device_info)
        self._states = ENUM_STATUS_FIELDS[field.key]
        self._attr_options = sorted(set(self._states.values()))

    @property
    def native_value(self) -> str | None:
        """Return the shared state key for the gateway's value."""
        raw = _extract_text(self.coordinator, self._field.select)
        if not raw:
            return None
        state = self._states.get(raw.lower())
        if state is None:
            _LOGGER.debug("Unexpected %s value %r", self._field.name, raw)
        return state

    @property
    def icon(self) -> None:
        """Leave icons to icons.json."""
        return None
