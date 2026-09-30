# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-09-30

### Added

- Optional Device Access Code (printed on the gateway) in setup and reconfigure. It's checked with a real login, and unlocks the NAT table, speed test and restart.
- Sensors from the LAN status page: LAN IP address, LAN netmask, DHCP leases available/allocated, IP passthrough address, LAN IPv6 address and subnet, delegated IPv6 prefix, Wi-Fi 2.4/5 GHz status, per-port LAN connection status and speed, and the number of active/inactive clients.
- Sensors from the broadband status page: broadband source, external link speed, external IPv6 default gateway, primary/secondary IPv6 DNS, and PON link status.
- Binary sensors for DHCP server, packet filter, IP passthrough, NAT default server and "Firewall Advanced".
- An "IP Address" sensor: the address Home Assistant reaches the gateway on (the configured host, resolved).
- With the access code: NAT sessions available/in use, the latest speed test's download/upload throughput and time, a "Run Speed Test" button, and a "Restart" button (disabled by default).

### Changed

- "Model Number" is now called "Model", matching the Xfinity Gateway integration. Entity IDs are unchanged.

## [1.0.0] - 2026-08-19

### Added

- Initial release: a Home Assistant custom integration (`att_gateway`)
  using the core Home Assistant integration `scrape` to create native
  config-flow-based entities.
- Depends on Home Assistant Core's built-in `scrape`/`rest` integrations.
- Sensors for connection status, current time, system uptime, last reboot,
  external IP/IPv6 address, default gateway, primary/secondary DNS, and
  receive/transmit packet/byte/unicast counters; a connectivity binary
  sensor; and device info (manufacturer, model, hardware/software version,
  serial number, first use date).
