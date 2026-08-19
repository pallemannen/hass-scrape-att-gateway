# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
