# hass-scrape-att-gateway

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=Integration&repository=hass-scrape-att-gateway&owner=pallemannen)

A Home Assistant integration for monitoring an AT&T Internet Gateway (e.g. BGW320-series): connection status, uptime, last reboot, IP/IPv6 addresses, DNS servers, and traffic counters.

**Uses Home Assistant's built-in `scrape`/`rest` integrations under the hood** to fetch and parse the gateway's status pages - no separate HACS dependency to install, unlike some other gateway integrations.

## Gateway compatibility

Developed and tested against a BGW320-500 running firmware 6.34.7. The gateway's status pages (`/cgi-bin/sysinfo.ha` and `/cgi-bin/broadbandstatistics.ha`) require no login, so this should work unmodified against any AT&T gateway that serves the same pages. Please open an issue if a field doesn't scrape correctly on your model.

## Installation

1. Add this repository to HACS as a custom repository (category "Integration"), then install "AT&T Gateway".
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for "AT&T Gateway", and enter your gateway's **IP address** (defaults to `192.168.1.254`).

   The address is checked against the gateway during setup, so you'll see an error right away if it's wrong or unreachable, rather than ending up with sensors that silently never update.

No YAML editing or manually edited config files needed - everything is set up through the UI.

## What you get

**Sensors**
- Connection status, current time, system uptime, last reboot
- External IP and IPv6 addresses, default gateway, primary/secondary DNS
- Receive/transmit packet, byte, and unicast counters
- Manufacturer, model, hardware/software version, serial number, first use date

**Binary sensor**
- Connectivity (on when the gateway reports its connection as "Up")

All of these are created automatically when you set up the integration - nothing extra to configure.

## HACS

More info about HACS can be found at https://www.hacs.xyz/

## Credits

Icon by VectorLogoZone on [Icon-Icons.com](https://icon-icons.com/authors/1032-vectorlogozone).

## License

MIT - see [LICENSE](LICENSE).
