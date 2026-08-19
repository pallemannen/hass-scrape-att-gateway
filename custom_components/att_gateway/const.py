"""Constants for the AT&T Gateway integration."""
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "att_gateway"

CONF_HOST = "host"
DEFAULT_HOST = "192.168.1.254"
CONF_NAME = "name"
DEFAULT_NAME = "AT&T Gateway"
DEFAULT_SCAN_INTERVAL = 300

SYSINFO_PATH = "sysinfo.ha"
STATUS_PATH = "broadbandstatistics.ha"

# The gateway reports both of these as plain ISO-ish strings with no
# separate "T" handling needed except for Current Date/Time, which uses a
# literal "T" separator with no trailing "Z" (unlike First Use Date, which
# does have one). Verified against a real BGW320-500 gateway response.
CURRENT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class GatewayField:
    """A single scraped field on one of the gateway's status pages."""

    key: str
    name: str
    select: str


# sysinfo.ha: a single <table> on the page, so "table:nth-of-type(1)" is
# unambiguous. Row positions verified directly against a real BGW320-500's
# /cgi-bin/sysinfo.ha response (fetched and inspected row-by-row), not
# guessed or carried over from a different gateway model.
SYSINFO_FIELDS: tuple[GatewayField, ...] = (
    GatewayField(
        "manufacturer", "Manufacturer", "table:nth-of-type(1) tr:nth-child(1) td:nth-child(2)"
    ),
    GatewayField(
        "model_number", "Model Number", "table:nth-of-type(1) tr:nth-child(2) td:nth-child(2)"
    ),
    GatewayField(
        "serial_number", "Serial Number", "table:nth-of-type(1) tr:nth-child(3) td:nth-child(2)"
    ),
    GatewayField(
        "software_version",
        "Software Version",
        "table:nth-of-type(1) tr:nth-child(4) td:nth-child(2)",
    ),
    GatewayField(
        "mac_address", "MAC Address", "table:nth-of-type(1) tr:nth-child(5) td:nth-child(2)"
    ),
    GatewayField(
        "first_use_date",
        "First Use Date",
        "table:nth-of-type(1) tr:nth-child(6) td:nth-child(2)",
    ),
    GatewayField(
        "system_uptime",
        "System Uptime",
        "table:nth-of-type(1) tr:nth-child(7) td:nth-child(2)",
    ),
    GatewayField(
        "current_time", "Current Time", "table:nth-of-type(1) tr:nth-child(8) td:nth-child(2)"
    ),
    GatewayField(
        "hardware_version",
        "Hardware Version",
        "table:nth-of-type(1) tr:nth-child(9) td:nth-child(2)",
    ),
)

CURRENT_TIME_FIELD_KEY = "current_time"
SYSTEM_UPTIME_FIELD_KEY = "system_uptime"

# broadbandstatistics.ha: three separate tables identified by their (stable,
# unique) `summary` attribute rather than position, since the page has
# several tables and their order could plausibly change with a firmware
# update. Row positions within each table verified the same way as
# SYSINFO_FIELDS above.
#
# Note: this fixes a real bug found in this gateway's previously
# hand-configured Scrape helper entities - "Secondary DNS" was configured
# with the exact same selector as "Primary DNS" (tr:nth-child(8) in both
# cases), so sensor.at_t_secondary_dns silently mirrored the primary DNS
# value instead of the actual secondary one at tr:nth-child(9).
STATUS_FIELDS: tuple[GatewayField, ...] = (
    GatewayField(
        "connection_status",
        "Connection Status",
        'table[summary*="WAN"] tr:nth-child(3) td:nth-child(2)',
    ),
    GatewayField(
        "external_ip_address",
        "External IP Address",
        'table[summary*="WAN"] tr:nth-child(5) td:nth-child(2)',
    ),
    GatewayField(
        "external_default_gateway",
        "External Default Gateway",
        'table[summary*="WAN"] tr:nth-child(6) td:nth-child(2)',
    ),
    GatewayField(
        "primary_dns", "Primary DNS", 'table[summary*="WAN"] tr:nth-child(8) td:nth-child(2)'
    ),
    GatewayField(
        "secondary_dns",
        "Secondary DNS",
        'table[summary*="WAN"] tr:nth-child(9) td:nth-child(2)',
    ),
    GatewayField(
        "external_ipv6_address",
        "External IPv6 Address",
        'table[summary*="IPv6 Table"] tr:nth-child(3) td:nth-child(2)',
    ),
    GatewayField(
        "receive_packets",
        "Receive Packets",
        'table[summary*="IPv4 Statistics"] tr:nth-child(1) td:nth-child(2)',
    ),
    GatewayField(
        "transmit_packets",
        "Transmit Packets",
        'table[summary*="IPv4 Statistics"] tr:nth-child(2) td:nth-child(2)',
    ),
    GatewayField(
        "receive_bytes",
        "Receive Bytes",
        'table[summary*="IPv4 Statistics"] tr:nth-child(3) td:nth-child(2)',
    ),
    GatewayField(
        "transmit_bytes",
        "Transmit Bytes",
        'table[summary*="IPv4 Statistics"] tr:nth-child(4) td:nth-child(2)',
    ),
    GatewayField(
        "receive_unicast",
        "Receive Unicast",
        'table[summary*="IPv4 Statistics"] tr:nth-child(5) td:nth-child(2)',
    ),
    GatewayField(
        "transmit_unicast",
        "Transmit Unicast",
        'table[summary*="IPv4 Statistics"] tr:nth-child(6) td:nth-child(2)',
    ),
)

CONNECTION_STATUS_FIELD_KEY = "connection_status"

# Fields whose value is a plain integer counter, not a display string -
# these get SensorStateClass.TOTAL_INCREASING so history/statistics work.
COUNTER_FIELD_KEYS = frozenset(
    {
        "receive_packets",
        "transmit_packets",
        "receive_bytes",
        "transmit_bytes",
        "receive_unicast",
        "transmit_unicast",
    }
)
BYTE_FIELD_KEYS = frozenset({"receive_bytes", "transmit_bytes"})

ICON_ACTIVE = "mdi:check-network-outline"
ICON_INACTIVE = "mdi:close-network-outline"
LAST_REBOOT_ICON = "mdi:clock-time-four-outline"

STATIC_ICONS: dict[str, str] = {
    "manufacturer": "mdi:factory",
    "model_number": "mdi:tag-outline",
    "serial_number": "mdi:numeric",
    "software_version": "mdi:source-branch",
    "mac_address": "mdi:barcode",
    "first_use_date": "mdi:calendar-clock-outline",
    "system_uptime": "mdi:clock-time-four-outline",
    "current_time": "mdi:clock-time-four-outline",
    "hardware_version": "mdi:chip",
    "external_ip_address": "mdi:ip-network-outline",
    "external_default_gateway": "mdi:play-network-outline",
    "primary_dns": "mdi:dns-outline",
    "secondary_dns": "mdi:dns-outline",
    "external_ipv6_address": "mdi:ip-network-outline",
    "receive_packets": "mdi:download-network-outline",
    "transmit_packets": "mdi:upload-network-outline",
    "receive_bytes": "mdi:download-network-outline",
    "transmit_bytes": "mdi:upload-network-outline",
    "receive_unicast": "mdi:download-network-outline",
    "transmit_unicast": "mdi:upload-network-outline",
}
