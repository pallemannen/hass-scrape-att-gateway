# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-08-19

### Added

- Initial release: a real Home Assistant custom integration (`att_gateway`)
  replacing the previously hand-configured `scrape` UI helpers ("AT&T System
  Information", "AT&T Status") and Template Helpers ("AT&T Connection
  Status", "AT&T Last Reboot") with native config-flow-based entities.
- Depends on Home Assistant Core's built-in `scrape`/`rest` integrations
  (no login required by this gateway, so no separate HACS scraper
  dependency needed).
- Sensors for connection status, current time, system uptime, last reboot,
  external IP/IPv6 address, default gateway, primary/secondary DNS, and
  receive/transmit packet/byte/unicast counters; a connectivity binary
  sensor; and device info (manufacturer, model, hardware/software version,
  serial number, first use date).
- Fixes a bug carried over from the previous manual `scrape` config: the
  "Secondary DNS" selector was an exact copy of "Primary DNS"
  (`tr:nth-child(8)` for both), so it always mirrored the primary DNS value
  instead of the real secondary one at `tr:nth-child(9)`.
