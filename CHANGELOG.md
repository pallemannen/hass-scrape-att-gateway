# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.2.0] - 2026-09-30

### Added

- Per-port LAN traffic counters: transmit/receive packets, bytes, dropped and errors (ports 2-4 disabled by default).
- Fiber status, fiber link state, and a "Fiber Alarm" problem sensor that is on when any of the fiber module's alarm/warning counters is non-zero.
- MTU and IPv6 MTU (disabled by default).
- With the access code: Wi-Fi 2.4 GHz, Wi-Fi 5 GHz and Guest Wi-Fi switches, and their SSIDs.
- With the access code: the number of MAC filter entries, packet filter rules, hosted applications and custom services, with the entries as attributes.
- With the access code: IPv6, DHCPv6 and DHCPv6 prefix delegation settings (binary sensors), router advertisement MTU (disabled by default), and the passthrough settings: allocation mode, passthrough mode, fixed MAC address and DHCP lease.

### Changed

- "IP Passthrough" and "IP Passthrough Address" are now called "Bridge Mode" and "Bridge Mode Address", matching the Xfinity Gateway integration. Entity IDs follow.
- The On/Off binary sensors (DHCP server, bridge mode, packet filter, NAT default server, Firewall Advanced) get their own state-dependent icons instead of the default check mark.
- LAN port status switches between `mdi:ethernet`/`mdi:ethernet-off`, Wi-Fi status between `mdi:wifi`/`mdi:wifi-off`, and LAN netmask uses `mdi:slash-forward-box`, matching the Xfinity Gateway integration.

### Fixed

- PON Link Status had no icon (invalid icon name); it now uses `mdi:wan`.

## [1.1.0] - 2026-09-30

### Added

- Optional Device Access Code in setup and reconfigure, unlocking the NAT table, speed test and restart.
- Sensors from the LAN status page: LAN IP address, LAN netmask, DHCP leases available/allocated, IP passthrough address, LAN IPv6 address and subnet, delegated IPv6 prefix, Wi-Fi 2.4/5 GHz status, per-port LAN connection status and speed, and the number of active/inactive clients.
- Sensors from the broadband status page: broadband source, external link speed, external IPv6 default gateway, primary/secondary IPv6 DNS, and PON link status.
- Binary sensors for DHCP server, packet filter, IP passthrough, NAT default server and "Firewall Advanced".
- An "IP Address" sensor: the address Home Assistant reaches the gateway on (the configured host, resolved).
- With the access code: NAT sessions available/in use, the latest speed test's download/upload throughput and time, a "Run Speed Test" button, and a "Restart" button (disabled by default).

### Changed

- "Model Number" is now called "Model", matching the Xfinity Gateway integration.
- Entity IDs now follow the entity name, like the Xfinity Gateway integration's. Old automatic IDs are renamed at startup (in practice only `sensor.att_gateway_model_number` → `sensor.att_gateway_model`).

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
