# hass-scrape-att-gateway

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=Integration&repository=hass-scrape-att-gateway&owner=pallemannen)

A Home Assistant integration for monitoring an AT&T Internet Gateway (e.g. BGW320-series): connection status, uptime, last reboot, IP/IPv6 addresses, DNS servers, and traffic counters.

**Uses Home Assistant's built-in `scrape`/`rest` integrations under the hood** to fetch and parse the gateway's status pages - no separate HACS dependency to install, unlike some other gateway integrations.

## Gateway compatibility

Developed and tested against a BGW320-500 running firmware 6.34.7. Most of the gateway's status pages (`sysinfo.ha`, `broadbandstatistics.ha`, `lanstatistics.ha`, `firewall.ha`) require no login, so this should work unmodified against any AT&T gateway that serves the same pages. Also tested on firmware 6.35.8. Please open an issue if a field doesn't scrape correctly on your model.

## Installation

1. Add this repository to HACS as a custom repository (category "Integration"), then install "AT&T Gateway".
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for "AT&T Gateway", and fill in:
   - **Gateway IP address** (defaults to `192.168.1.254` - change it if yours is different)
   - **Device name** (defaults to `AT&T Gateway` - change it if you want something else)
   - **Device Access Code** (optional, printed on the gateway's label) - only needed for the NAT table, speed test and restart. Leave it empty to skip them. It can be added later via **Reconfigure**.

   The address (and the access code, if given) is checked against the gateway during setup, so you'll see an error right away if it's wrong or unreachable, rather than ending up with sensors that silently never update.

No YAML editing or manually edited config files needed - everything is set up through the UI.

## What you get

**Sensors**
- Connection status, current time, system uptime, last reboot
- External IP and IPv6 addresses, default gateways, primary/secondary DNS (IPv4 and IPv6), broadband source, external link speed, PON link status
- Receive/transmit packet, byte, and unicast counters
- LAN IP address and netmask, DHCP leases, bridge mode address
- LAN IPv6 address and subnet, and the **delegated IPv6 prefix** (empty when the gateway isn't delegating one to your router)
- Wi-Fi 2.4/5 GHz status, per-port LAN connection status, speed and traffic counters, number of active/inactive clients
- Fiber status and link state, MTU
- IP address (the address Home Assistant reaches the gateway on)
- Manufacturer, model, hardware/software version, serial number, first use date

**Binary sensors**
- Connectivity (on when the gateway reports its connection as "Up")
- DHCP server, packet filter, bridge mode, NAT default server, Firewall Advanced
- Fiber alarm (on when the fiber module reports an alarm or warning)

**With the Device Access Code**
- NAT sessions available/in use
- IPv6, DHCPv6 and prefix delegation settings, router advertisement MTU
- Passthrough settings: allocation mode, passthrough mode, fixed MAC address, DHCP lease
- Latest speed test: download, upload, and when it ran
- **Run Speed Test** button (measured by the gateway itself, bypassing your own router)
- **Restart** button (disabled by default - it takes your internet connection down for a few minutes)

All of these are created automatically when you set up the integration - nothing extra to configure.

## HACS

More info about HACS can be found at https://www.hacs.xyz/

## Credits

Icon by VectorLogoZone on [Icon-Icons.com](https://icon-icons.com/authors/1032-vectorlogozone).

## License

MIT - see [LICENSE](LICENSE).
