"""Constants for the AT&T Gateway integration."""
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "att_gateway"

CONF_HOST = "host"
DEFAULT_HOST = "192.168.1.254"
CONF_NAME = "name"
DEFAULT_NAME = "AT&T Gateway"
CONF_ACCESS_CODE = "access_code"
DEFAULT_SCAN_INTERVAL = 300

SYSINFO_PATH = "sysinfo.ha"
STATUS_PATH = "broadbandstatistics.ha"
LAN_PATH = "lanstatistics.ha"
FIREWALL_PATH = "firewall.ha"

# Pages behind the Device Access Code (see api.py).
LOGIN_PATH = "login.ha"
NAT_PATH = "nattable.ha"
SPEED_PATH = "speed.ha"
RESTART_PATH = "restart.ha"

# Seconds until a speed test result shows up.
SPEED_TEST_DURATION = 60

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
        "model_number", "Model", "table:nth-of-type(1) tr:nth-child(2) td:nth-child(2)"
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
    GatewayField(
        "broadband_source",
        "Broadband Source",
        'table[summary*="WAN"] tr:nth-child(1) td:nth-child(2)',
    ),
    GatewayField(
        "external_link_speed",
        "External Link Speed",
        'table[summary*="Ethernet Statistics"] tr:nth-child(2) td:nth-child(2)',
    ),
    GatewayField(
        "external_ipv6_default_gateway",
        "External IPv6 Default Gateway",
        'table[summary*="IPv6 Table"] tr:nth-child(5) td:nth-child(2)',
    ),
    GatewayField(
        "primary_ipv6_dns",
        "Primary IPv6 DNS",
        'table[summary*="IPv6 Table"] tr:nth-child(6) td:nth-child(2)',
    ),
    GatewayField(
        "secondary_ipv6_dns",
        "Secondary IPv6 DNS",
        'table[summary*="IPv6 Table"] tr:nth-child(7) td:nth-child(2)',
    ),
    GatewayField(
        "pon_link_status",
        "PON Link Status",
        'table[summary*="GPON"] tr:nth-child(1) td:nth-child(2)',
    ),
)

# lanstatistics.ha
_LAN_TABLE = 'table[summary*="critical LAN status"]'
_LAN_IPV6_TABLE = 'table[summary*="IPv6 LAN information"]'
_LAN_PORTS_TABLE = 'table[summary*="LAN Ethernet Statistics"]'
# Unclosed header <tr> on this table, so select cells by class.
_WIFI_TABLE = 'table[summary*="Wi-Fi status"]'
LAN_INTERFACES_TABLE = 'table[summary*="LAN Interfaces"]'

LAN_FIELDS: tuple[GatewayField, ...] = (
    GatewayField("lan_ip_address", "LAN IP Address", f"{_LAN_TABLE} tr:nth-child(1) td"),
    GatewayField("lan_netmask", "LAN Netmask", f"{_LAN_TABLE} tr:nth-child(2) td"),
    GatewayField(
        "dhcp_leases_available", "DHCP Leases Available", f"{_LAN_TABLE} tr:nth-child(6) td"
    ),
    GatewayField(
        "dhcp_leases_allocated", "DHCP Leases Allocated", f"{_LAN_TABLE} tr:nth-child(7) td"
    ),
    GatewayField(
        "ip_passthrough_address", "Bridge Mode Address", f"{_LAN_TABLE} tr:nth-child(13) td"
    ),
    GatewayField(
        "lan_ipv6_address", "LAN IPv6 Address", f"{_LAN_IPV6_TABLE} tr:nth-child(2) td"
    ),
    GatewayField("lan_ipv6_subnet", "LAN IPv6 Subnet", f"{_LAN_IPV6_TABLE} tr:nth-child(4) td"),
    GatewayField(
        "delegated_ipv6_prefix", "Delegated IPv6 Prefix", f"{_LAN_IPV6_TABLE} tr:nth-child(5) td"
    ),
    GatewayField(
        "wifi_24ghz_status", "Wi-Fi 2.4 GHz Status", f"{_WIFI_TABLE} td.col2:nth-of-type(2)"
    ),
    GatewayField(
        "wifi_5ghz_status", "Wi-Fi 5 GHz Status", f"{_WIFI_TABLE} td.col2:nth-of-type(3)"
    ),
    *(
        GatewayField(
            f"lan_{port}_connection_status",
            f"LAN {port} Connection Status",
            f"{_LAN_PORTS_TABLE} tr:nth-child(2) td:nth-child({port + 1})",
        )
        for port in range(1, 5)
    ),
    *(
        GatewayField(
            f"lan_{port}_speed",
            f"LAN {port} Speed",
            f"{_LAN_PORTS_TABLE} tr:nth-child(3) td:nth-child({port + 1})",
        )
        for port in range(1, 5)
    ),
)

# "On"/"Off" status rows, exposed as binary sensors.
_FIREWALL_TABLE = 'table[summary*="Packet Filter"]'
FIREWALL_FIELDS: tuple[GatewayField, ...] = (
    GatewayField("packet_filter", "Packet Filter", f"{_FIREWALL_TABLE} tr:nth-child(1) td"),
    GatewayField("ip_passthrough", "Bridge Mode", f"{_FIREWALL_TABLE} tr:nth-child(2) td"),
    GatewayField(
        "nat_default_server", "NAT Default Server", f"{_FIREWALL_TABLE} tr:nth-child(3) td"
    ),
    GatewayField(
        "firewall_advanced", "Firewall Advanced", f"{_FIREWALL_TABLE} tr:nth-child(4) td"
    ),
)
DHCP_SERVER_FIELD = GatewayField("dhcp_server", "DHCP Server", f"{_LAN_TABLE} tr:nth-child(3) td")

# nattable.ha (needs the Device Access Code).
_NAT_TABLE = 'table[summary*="summary of session information"]'
NAT_FIELDS: tuple[GatewayField, ...] = (
    GatewayField(
        "nat_sessions_available", "NAT Sessions Available", f"{_NAT_TABLE} tr:nth-child(1) td"
    ),
    GatewayField("nat_sessions_in_use", "NAT Sessions In Use", f"{_NAT_TABLE} tr:nth-child(2) td"),
)

# speed.ha (needs the Device Access Code): newest first, one row per direction.
# The latency column isn't used; its values are unreliable.
SPEED_TABLE = 'table[summary*="Speed Test Result History"]'
SPEED_TIME_FORMAT = "%m/%d/%Y %H:%M:%S"

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

# Plain integer gauges (not counters).
GAUGE_FIELD_KEYS = frozenset(
    {
        "dhcp_leases_available",
        "dhcp_leases_allocated",
        "nat_sessions_available",
        "nat_sessions_in_use",
    }
)
# Link speeds: the WAN one is reported in Mbps, the LAN ports in bit/s.
LINK_SPEED_FIELD_KEYS = frozenset({"external_link_speed"})
LAN_PORT_SPEED_FIELD_KEYS = frozenset(f"lan_{port}_speed" for port in range(1, 5))

# (on, off) icons for the On/Off binary sensors; same as Xfinity where it has one.
ON_OFF_ICONS: dict[str, tuple[str, str]] = {
    "dhcp_server": ("mdi:database-export-outline", "mdi:database-off-outline"),
    "ip_passthrough": ("mdi:bridge", "mdi:router-network"),
    "packet_filter": ("mdi:filter", "mdi:filter-off"),
    "nat_default_server": ("mdi:server-network", "mdi:server-network-off"),
    "firewall_advanced": ("mdi:shield-check", "mdi:shield-off"),
}

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
    "ip_address": "mdi:ip-network-outline",
    "broadband_source": "mdi:transit-connection-variant",
    "external_link_speed": "mdi:speedometer",
    "external_ipv6_default_gateway": "mdi:play-network-outline",
    "primary_ipv6_dns": "mdi:dns-outline",
    "secondary_ipv6_dns": "mdi:dns-outline",
    "pon_link_status": "mdi:fiber-manual-record",
    "lan_ip_address": "mdi:ip-network-outline",
    "lan_netmask": "mdi:ip-network-outline",
    "dhcp_leases_available": "mdi:counter",
    "dhcp_leases_allocated": "mdi:counter",
    "ip_passthrough_address": "mdi:ip-network-outline",
    "lan_ipv6_address": "mdi:ip-network-outline",
    "lan_ipv6_subnet": "mdi:ip-network-outline",
    "delegated_ipv6_prefix": "mdi:ip-network-outline",
    "wifi_24ghz_status": "mdi:wifi",
    "wifi_5ghz_status": "mdi:wifi",
    "active_client_count": "mdi:devices",
    "inactive_client_count": "mdi:devices",
    "nat_sessions_available": "mdi:swap-horizontal",
    "nat_sessions_in_use": "mdi:swap-horizontal",
    "speed_test_download": "mdi:download-network-outline",
    "speed_test_upload": "mdi:upload-network-outline",
    "last_speed_test": "mdi:speedometer",
    **{f"lan_{port}_connection_status": "mdi:ethernet" for port in range(1, 5)},
    **{f"lan_{port}_speed": "mdi:speedometer" for port in range(1, 5)},
}
