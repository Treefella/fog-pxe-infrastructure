# FOG PXE Boot Infrastructure

Configuration files and scripts for a [FOG Project](https://fogproject.org) PXE boot environment using:

- **FOG Server** — imaging server with Apache, TFTP (tftpd-hpa), and dnsmasq Proxy DHCP
- **OpenWrt Router** — handles main DHCP; FOG runs in Proxy DHCP mode alongside it
- **iPXE** — chainloaded via TFTP for both BIOS and UEFI clients

Built and documented by [GLS Tech Limited](https://glstech.co.uk) — IT support & open source consultancy in County Durham.

---

## Network Overview

```
                        ┌──────────────────────────────┐
                        │     LAN: 10.0.0.0/24     │
                        └──────────────────────────────┘
                                        │
               ┌────────────────────────┼────────────────────────┐
               │                        │                        │
               ▼                        ▼                        ▼
  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
  │   OpenWrt Router    │   │   FOG Server        │   │   Client Machines   │
  │   10.0.0.1    │   │   10.0.0.10       │   │   (PXE boot)        │
  │                     │   │                     │   │                     │
  │  • DHCP (main)      │   │  • FOG Project      │   │  BIOS: undionly.kpxe│
  │  • DNS              │◄─►│  • Apache HTTP :80  │   │  UEFI: ipxe.efi     │
  │  • Gateway          │   │  • TFTP :69         │   │                     │
  │                     │   │  • dnsmasq Proxy    │   │                     │
  └─────────────────────┘   │    DHCP :4011       │   └─────────────────────┘
                             └─────────────────────┘
```

**Key design:** The router handles all DHCP leases. FOG's dnsmasq runs in **Proxy DHCP** mode only — it responds on port 4011 to add PXE boot options without conflicting with the router.

---

## PXE Boot Flow

```
Client powers on (network boot)
        │
        ▼
1. DHCP Discover
        ├─► Router: assigns IP, sends next-server + filename (undionly.kpxe)
        └─► FOG dnsmasq Proxy DHCP: adds PXE service tags
        │
        ▼
2. TFTP: downloads undionly.kpxe from FOG server
        │
        ▼
3. iPXE boots — sends new DHCP Discover with "iPXE" user-class
        │
        ▼
4. FOG dnsmasq detects iPXE tag → responds with HTTP boot URL
        │
        ▼
5. HTTP GET → FOG Apache → boot.php?mac=XX:XX:XX:XX:XX:XX
        │
        ▼
6. FOG menu: Deploy / Capture / Boot local / etc.
```

---

## Repository Structure

```
fog-pxe-infrastructure/
├── configs/
│   └── fog-proxydhcp.conf     # dnsmasq Proxy DHCP config (FOG server)
├── tftpboot/
│   ├── default.ipxe           # TFTP chainloader → fog.ipxe
│   ├── fog.ipxe               # iPXE script → FOG boot.php
│   ├── undionly.kpxe          # iPXE binary (BIOS/legacy)
│   └── ipxe.efi               # iPXE binary (UEFI)
└── docs/
    ├── README.md              # this file
    └── restart_router_dnsmasq.py  # helper: restart dnsmasq on OpenWrt via ubus RPC
```

---

## Setup

### 1. Replace placeholders

Search and replace throughout the configs before deploying:

| Example value         | Replace with                          |
|-----------------------|---------------------------------------|
| `10.0.0.10`           | Static IP of your FOG server          |
| `10.0.0.1`            | IP of your router/gateway             |
| `10.0.0`              | Your LAN subnet prefix                |
| `YOUR_LAN_INTERFACE`  | FOG server's LAN NIC (e.g. `eno1`)    |

### 2. Deploy dnsmasq Proxy DHCP config

```bash
sudo cp configs/fog-proxydhcp.conf /etc/dnsmasq.d/
sudo systemctl restart dnsmasq
```

> **Important:** Do not add `dhcp-authoritative`, full `dhcp-range` with IPs, or `dhcp-option` to this config — those conflict with the router's DHCP server. Proxy mode only.

### 3. Deploy TFTP files

```bash
sudo cp tftpboot/fog.ipxe /tftpboot/
sudo cp tftpboot/default.ipxe /tftpboot/
sudo cp tftpboot/undionly.kpxe /tftpboot/
sudo cp tftpboot/ipxe.efi /tftpboot/
sudo systemctl restart tftpd-hpa
```

### 4. Router DHCP boot options (OpenWrt)

Via UCI on the router:
```bash
uci set dhcp.@dnsmasq[0].dhcp_boot='undionly.kpxe,,10.0.0.10'
uci commit dhcp
/etc/init.d/dnsmasq restart
```

---

## Helper Scripts

### restart_router_dnsmasq.py

Restarts dnsmasq on an OpenWrt router via ubus RPC. Credentials are read from environment variables — never hardcoded.

```bash
ROUTER_IP=10.0.0.1 ROUTER_PASSWORD=yourpassword python3 docs/restart_router_dnsmasq.py
```

---

## Services Reference

| Service       | Port | Protocol | Purpose                            |
|---------------|------|----------|------------------------------------|
| Apache2       | 80   | HTTP/TCP  | FOG web UI & iPXE boot scripts     |
| tftpd-hpa     | 69   | UDP       | Serves undionly.kpxe, ipxe.efi    |
| dnsmasq       | 4011 | UDP       | Proxy DHCP for PXE                 |
| MySQL/MariaDB | 3306 | TCP       | FOG database                       |

---

## Troubleshooting

**"Nothing to boot: No such file or directory"**
TFTP not reachable. Verify router DHCP `next-server` points to your FOG server IP and tftpd-hpa is running.

**dnsmasq stops responding after config change**
You likely added full DHCP options to the proxy config. Remove any `dhcp-range` with IPs, `dhcp-option`, or `dhcp-authoritative` lines — these conflict with the router.

**iPXE file not found (uppercase filenames)**
If building a custom ISO, use `-J -R` flags with genisoimage for Joliet + Rock Ridge extensions to preserve case.

---

## Useful Commands

```bash
# Restart FOG dnsmasq
sudo systemctl restart dnsmasq

# Restart TFTP
sudo systemctl restart tftpd-hpa

# Watch PXE traffic live
sudo tcpdump -i YOUR_LAN_INTERFACE -n 'port 67 or port 68 or port 4011'

# Check FOG services
sudo systemctl status FOGImageReplicator FOGMulticastManager FOGScheduler FOGSnapinReplicator
```

---

## License

MIT — free to use and adapt.

---

*Documented by [GLS Tech Limited](https://glstech.co.uk) — IT support, imaging, and open source consultancy in County Durham, UK.*
