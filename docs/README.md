# FOG PXE Boot Infrastructure — Configuration Backup & Documentation

**Date:** 2026-03-08
**FOG Server:** gls-HP-EliteDesk-800-G3-DM-65W
**FOG Server IP:** 192.168.1.132 (static)
**Router (OpenWrt):** 192.168.1.1

---

## Network Diagram

```
                        ┌─────────────────────────────────────────────────────────┐
                        │                    LAN: 192.168.1.0/24                  │
                        └─────────────────────────────────────────────────────────┘
                                                    │
               ┌────────────────────────────────────┼────────────────────────────────────┐
               │                                    │                                    │
               ▼                                    ▼                                    ▼
  ┌────────────────────────┐          ┌─────────────────────────┐          ┌─────────────────────────┐
  │   OpenWrt Router       │          │   FOG Server            │          │   VirtualBox Host       │
  │   192.168.1.1          │          │   192.168.1.132         │          │   (gls-HP-EliteDesk)    │
  │                        │          │   HP EliteDesk 800 G3   │          │   192.168.1.x           │
  │  Services:             │          │                         │          │                         │
  │  • DHCP (main)         │          │  Services:              │          │  VMs (Bridged → eno1):  │
  │    Range: .100–.250    │          │  • FOG Project          │          │  ┌─────────────────┐   │
  │  • DNS                 │          │  • Apache HTTP          │          │  │ linux VM        │   │
  │  • Gateway             │          │    port 80              │          │  │ NIC: 82545EM    │   │
  │                        │          │  • TFTP (tftpd-hpa)     │          │  │ Boot: net first │   │
  │  PXE Boot Config:      │          │    port 69              │          │  └─────────────────┘   │
  │  • next-server=        │          │  • dnsmasq Proxy DHCP   │          │  ┌─────────────────┐   │
  │    192.168.1.132       │◄────────►│    port 4011            │          │  │ win10 VM        │   │
  │  • filename=           │  DHCP    │                         │          │  │ NIC: Am79C973   │   │
  │    undionly.kpxe       │  Proxy   │  IP: 192.168.1.132/24   │          │  │ Boot: dvd/disk  │   │
  └────────────────────────┘          └─────────────────────────┘          └─────────────────────────┘

```

---

## PXE Boot Flow

```
VM Powers On (network boot)
        │
        ▼
1. DHCP Discover (broadcast)
        │
        ├──► OpenWrt Router (192.168.1.1)
        │    Responds with DHCP Offer:
        │    • IP lease (192.168.1.x)
        │    • next-server = 192.168.1.132
        │    • filename = undionly.kpxe
        │
        ├──► FOG dnsmasq Proxy DHCP (192.168.1.132:4011)
        │    Also responds with PXE boot options
        │
        ▼
2. TFTP Request → 192.168.1.132:69
   Downloads: undionly.kpxe (iPXE chainloader)
        │
        ▼
3. iPXE Boots (undionly.kpxe)
   Sends new DHCP Discover with "iPXE" user-class
        │
        ▼
4. FOG dnsmasq detects iPXE tag
   Responds with:
   dhcp-boot = http://192.168.1.132/fog/service/ipxe/boot.php
        │
        ▼
5. HTTP Request → FOG Apache
   GET http://192.168.1.132/fog/service/ipxe/boot.php?mac=XX:XX:XX:XX:XX:XX
        │
        ▼
6. FOG Menu Displayed
   • Deploy image
   • Capture image
   • Boot from local disk
   • Memory test
   • etc.
```

---

## Configuration Files

### 1. FOG Server — dnsmasq Proxy DHCP
**File:** `/etc/dnsmasq.d/fog-proxydhcp.conf`

```
log-dhcp
dhcp-range=192.168.1.0,proxy
dhcp-userclass=set:ipxe,iPXE
pxe-service=tag:!ipxe,x86PC,"Boot from FOG",undionly.kpxe,192.168.1.132
pxe-service=tag:!ipxe,X86-64_EFI,"Boot from FOG",ipxe.efi,192.168.1.132
interface=eno1
except-interface=lo
except-interface=docker0
dhcp-boot=tag:ipxe,http://192.168.1.132/fog/service/ipxe/boot.php
dhcp-boot=tag:!ipxe,undionly.kpxe,,192.168.1.132
```

**Key notes:**
- `dhcp-range=192.168.1.0,proxy` — Proxy DHCP mode only (does NOT assign IPs, that's the router's job)
- `dhcp-userclass=set:ipxe,iPXE` — Tags second-stage iPXE clients
- `pxe-service` — Tells pre-iPXE clients which file to chainload
- `dhcp-boot=tag:ipxe,...` — Sends HTTP boot URL to full iPXE clients
- Do NOT add `dhcp-authoritative`, `dhcp-range` with IPs, or `dhcp-option` — these conflict with the router

### 2. FOG Server — iPXE Boot Script
**File:** `/tftpboot/fog.ipxe`

```ipxe
#!ipxe
echo Starting FOG Boot...
ifstat
set fog-ip 192.168.1.132
set fog-webroot fog
chain --replace http://${fog-ip}/${fog-webroot}/service/ipxe/boot.php?mac=${net0/mac}
```

### 3. FOG Server — Default iPXE Chainloader
**File:** `/tftpboot/default.ipxe`

```ipxe
#!ipxe
chain tftp://192.168.1.132/fog.ipxe
```

### 4. OpenWrt Router — DHCP Boot Config
**File:** `/etc/config/dhcp` (on router 192.168.1.1)

Managed via UCI. The relevant boot section (cfg06b399):
```
config boot
    option filename 'undionly.kpxe'
    option serveraddress '192.168.1.132'
    option servername 'fogserver'
```

**How to view/edit on router:**
```bash
# Via UCI (SSH to router or use LuCI web UI at http://192.168.1.1)
uci show dhcp
uci get dhcp.cfg06b399
```

---

## Services on FOG Server

| Service        | Port | Protocol | Purpose                          |
|----------------|------|----------|----------------------------------|
| Apache2        | 80   | HTTP/TCP | FOG web interface & iPXE scripts |
| tftpd-hpa      | 69   | UDP      | Serves undionly.kpxe, ipxe.efi  |
| dnsmasq        | 4011 | UDP      | Proxy DHCP for PXE               |
| MySQL/MariaDB  | 3306 | TCP      | FOG database                     |

---

## TFTP Files

| File            | Size     | Purpose                                    |
|-----------------|----------|--------------------------------------------|
| undionly.kpxe   | ~363 KB  | iPXE chainloader for BIOS/legacy PXE      |
| ipxe.efi        | ~1.07 MB | iPXE chainloader for UEFI PXE             |
| fog.ipxe        | —        | iPXE script → chains to FOG boot.php      |
| default.ipxe    | —        | Fallback → chains to fog.ipxe via TFTP    |

---

## VirtualBox VMs

| VM Name | OS           | NIC Type   | Boot Order         | Purpose              |
|---------|--------------|------------|--------------------|----------------------|
| linux   | Linux 64-bit | 82545EM    | Net → Floppy → DVD → Disk | PXE test / imaging |
| win10   | Windows 10   | Am79C973   | DVD → Disk         | Image capture target |

**Bridged interface:** `eno1` (FOG server's LAN NIC)

---

## Troubleshooting

### "Nothing to boot: No such file or directory"
- **Cause:** VirtualBox built-in iPXE received next-server pointing to a host with no TFTP
- **Fix:** Ensure router's DHCP sends `next-server=192.168.1.132` and FOG dnsmasq is in proxy mode

### dnsmasq stops responding after config change
- **Cause:** Added full DHCP options (dhcp-range with IPs, dhcp-option, dhcp-authoritative) to proxy config
- **Fix:** Remove lines 11–14 from fog-proxydhcp.conf — proxy mode must not have these

### iPXE file not found via TFTP (uppercase filenames)
- **Cause:** ISO 9660 converting filenames to uppercase
- **Fix:** Use `-J -R` flags with genisoimage for Joliet + Rock Ridge extensions

### VirtualBox ROM injection breaking NIC
- **Cause:** Wrong VBoxInternal path for ROM injection
- **Fix:** Remove with `VBoxManage setextradata <VM> VBoxInternal/...` (set to empty)

---

## Management Commands

```bash
# Restart FOG dnsmasq
sudo systemctl restart dnsmasq

# Check dnsmasq status
sudo systemctl status dnsmasq

# Restart TFTP
sudo systemctl restart tftpd-hpa

# Check FOG services
sudo systemctl status FOGImageReplicator FOGMulticastManager FOGScheduler FOGSnapinReplicator

# View DHCP/PXE traffic (requires sudo)
sudo tcpdump -i eno1 -n 'port 67 or port 68 or port 4011'

# Restart router dnsmasq (via ubus RPC)
python3 /home/gls/Downloads/fog-pxe-backup/docs/restart_router_dnsmasq.py
```

---

## Quick Restore

If config is lost, restore from this backup:

```bash
sudo cp ~/Downloads/fog-pxe-backup/configs/fog-proxydhcp.conf /etc/dnsmasq.d/
sudo cp ~/Downloads/fog-pxe-backup/tftpboot/fog.ipxe /tftpboot/
sudo cp ~/Downloads/fog-pxe-backup/tftpboot/default.ipxe /tftpboot/
sudo systemctl restart dnsmasq
```
