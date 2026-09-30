---
title: "Porting the SG200x Debian Image to the Pine64 Oz64"
subtitle: "Reference Notes"
author: "CS 4250 — Computer Architecture"
date: today
format:
  revealjs:
    theme: [default, custom.scss]
    slide-number: true
    incremental: false
    controls: true
    progress: true
    hash: true
    center: false
    code-line-numbers: true
    chalkboard: true
    footer: "CS 4250 · Oz64 Image Port — Reference"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Porting Checklist {.smaller}

**Board identity**

1. Create `configs/<board>/` (copy the closest existing board).
2. `settings.mk`: chip, arch, DDR, U-Boot board, ION size, addons.
3. Device tree: model string + board-specific GPIO/pin fixes.
4. Reuse the boot chain if there is no U-Boot port; keep the DTB filename.

**Peripherals**

5. For each radio/peripheral: power pin, bus, driver build options, firmware.

**Image behavior**

6. Build-time config (`preconfigure`), init-script ordering, naming.

::: {.notes}
Everything below expands one of these six lines.
:::

## Repo Layout {.smaller}

| Component | Location |
|---|---|
| Board config | `configs/<board>/` |
| Shared build | `scripts/Makefile`, `configs/chip/<chip>/chip.mk` |
| Addons (rootfs) | `scripts/addons/*/addon.mk` |
| Patches | `configs/{common,chip/<chip>,<board>}/patches/<component>/` |
| Distro pins | `configs/settings.mk`, `configs/distro.mk` |

Selected by `make BOARD=oz64 image`; the builder runs in a container whose
paths are `/configs`, `/builder`, `/rootfs`.

::: {.notes}
The Makefile is board-agnostic. The board directory is the port.
:::

## The Oz64 Config Deltas {.smaller}

| File | Change |
|---|---|
| `dts/cv181x_milkv_duos_sd.dts` | `model="Pine64 Oz64"`; WiFi hog `porta 15`→`porta 30` |
| `patches/osdrv/0001-aic8800-disable-sdio-bt.patch` | `CONFIG_SDIO_BT=n`, `CONFIG_COEX=n` |
| `addons/aic8800-firmware/addon.mk` | also package `aic8800DC/` (and `D80X2`) |
| `settings.mk` | drop `usb-switch`, `ethernet-leds`, `hciattach-uart`; `SECOND_CPU` |

Kernel `defconfig` is identical to the Duo S. U-Boot is the Duo S U-Boot.

::: {.notes}
The port is a data problem plus one driver patch plus firmware packaging.
:::

## Device Tree — The Key Change {.smaller}

```dts
/ { model = "Pine64 Oz64"; };

&porta {
    wifi_chip_en {                 /* was: wifi_pwr @ porta 15 */
        gpio-hog;
        gpios = <30 GPIO_ACTIVE_HIGH>;   /* XGPIOA[30] = AUX0 = GPIO 510 */
        output-high;
    };
};
```

- `gpio-hog` = the GPIO controller drives the pin **at probe**, before drivers.
- Powers the AIC8800DC **`CHIP_EN`** before **`mmc1` (`wifisd`)** probes.
- Wrong pin (Duo S PA15 = `SPK_EN` here) ⇒ no SDIO card ⇒ "power on fail".

::: {.notes}
`cat /sys/kernel/debug/gpio | grep wifi` → `gpio-510 (wifi_chip_en) out hi`.
:::

## DTB Reuse Trick {.smaller}

- Built DTB keeps the name **`cv181x_milkv_duos_sd.dtb`**.
- The reused Duo S U-Boot's `fdtfile` points at exactly that path.
- The only thing that changes is the **contents** (`model`, hog).

```sh
strings .../cv181x_milkv_duos_sd.dtb | grep -i oz64     # Pine64 Oz64
cat /proc/device-tree/model                            # Pine64 Oz64
```

::: {.notes}
Keep bootloader-expected identifiers stable; override what the kernel reads.
:::

## WiFi: Four Independent Requirements {.smaller}

| # | Layer | Requirement | Fix |
|---|---|---|---|
| 1 | Board | power `CHIP_EN` before MMC probe | DT `wifi_chip_en` hog, PA30 |
| 2 | Bus | SDIO card enumerates | (follows from 1) |
| 3 | Driver | BT-over-SDIO must be off | patch `CONFIG_SDIO_BT=n`, `CONFIG_COEX=n` |
| 4 | Firmware | AIC8800**DC** blobs in the one `aic_fw_path` | `aic8800-firmware` addon |
| 5 | RF | external 2.4 GHz antenna | attach **u.FL / IPEX MHF1** |

::: {.notes}
Miss any one and the symptom is still "no WiFi". Debug them independently.
:::

## Failure Signatures {.smaller}

| Symptom | Meaning |
|---|---|
| `aicbsp: fail to set AIC_WIFI power state to 1` | chip unpowered ⇒ no SDIO card |
| `mmc1` absent in `/sys/bus/mmc/devices` | card not enumerated |
| `TDLS_SDIO_BT_SEND_CFM` + `intstatus=ff`, `-110` | BT-over-SDIO wedged the bus |
| `wlan0` up, `RSSI ≈ -80 dBm`, ARP FAILED | no antenna / dead RF path |
| `ping <name>` fails, `ping -4 <name>` works | stale IPv6 AAAA / dual-homing |

::: {.notes}
Each row points at exactly one layer in the previous slide.
:::

## Driver Patch and Module Load {.smaller}

```text
OSDRV patch (configs/chip/sg200x/patches/osdrv/0001-aic8800-disable-sdio-bt.patch)
  aic8800_bsp/Makefile : CONFIG_SDIO_BT  y -> n
  aic8800_fdrv/Makefile: CONFIG_SDIO_BT  y -> n
                         CONFIG_COEX     y -> n
```

Runtime (`load-systemko` addon):

```sh
# S00kmod   : base modules (+ ISP/vcodec only if ion_size != 0)
# S25wifimod:
insmod cfg80211.ko
insmod 3rd/aic8800_bsp.ko
insmod 3rd/aic8800_fdrv.ko
```

::: {.notes}
Verify the rebuild: `strings aic8800_fdrv.ko | grep -ci btsdio` → 0.
:::

## Firmware Path {.smaller}

Driver default (hard-coded):

```text
/usr/lib/firmware/aic8800_sdio/aic8800_and_aic8800D80
```

The addon clones `scpcom/aic8800-sdio-firmware` and copies
`aic8800/`, `aic8800_and_aic8800D80/`, `aic8800DC/`, `aic8800D80X2/`, and
**also drops the DC blobs into `aic8800_and_aic8800D80/`** (the single path).

```sh
find /lib/firmware -iname '*8800dc*'      # must be non-empty
```

::: {.notes}
`aic8800DC` files include `fmacfw_patch_8800dc_u02.bin`,
`aic_userconfig_8800dc.txt`, etc.
:::

## Connector Cheat-Sheet {.smaller}

| Name | Aliases | Size (receptacle) | Use |
|---|---|---|---|
| **MHF1** | Hirose **U.FL**, AMC, UMCC | ~3.0 × 3.1 mm | most WiFi boards |
| MHF2 | I-PEX MHF II | small | uncommon |
| **MHF3** | Hirose **W.FL**, AMMC | ~55% smaller than U.FL | niche |
| **MHF4** | I-PEX MHF 4, HSC | smallest | laptop/M.2 cards |

Oz64 schematic part `ZX-RF-3-Z1.30.85X`, measured ~2.95 mm ⇒ **MHF1 / Gen 1**.
Gen 1 ≠ Gen 3 ≠ Gen 4; they do not intermate.

::: {.notes}
The VisionFive 2 pigtail fits the Oz64 — both are MHF1-class.
:::

## Build-Time Knobs (`preconfigure`) {.smaller}

| Variable | Writes | Effect |
|---|---|---|
| `IMAGE_HOSTNAME` | `/boot/hostname` | exact hostname |
| `IMAGE_HOSTNAME_PREFIX` | `/boot/hostname.prefix` | `<prefix>-<hash>` |
| `WIFI_MODE` | `/boot/wifi.sta`/`.ap` | station/AP/none |
| `WIFI_SSID`/`WIFI_PASS` | `/boot/wifi.ssid`/`.pass` | creds (empty ⇒ open) |
| `WIFI_WPA_CONF` | `/boot/wpa_supplicant.conf` | raw config |
| `SECOND_CPU` | `/boot/arduino` | C906L policy |

```sh
make BOARD=oz64 SECOND_CPU=arduino IMAGE_HOSTNAME=oz64-nat \
     WIFI_MODE=sta WIFI_SSID=domenet image
```

::: {.notes}
Files land on `/boot` (FAT), so they persist and are read by init scripts.
:::

## Second CPU: camera vs arduino {.smaller}

| `SECOND_CPU` | `ION_SIZE` | camera addons | C906L |
|---|---|---|---|
| `camera` | 74 | `sensor-config`, `tpusdk` | runs ISP |
| `arduino` | 0 | none | free for `remoteproc` |

`ION_SIZE=0` ⇒ `chip.mk` zeroes the ISP heap and `S00kmod` skips the
ISP/vcodec `insmod`s; `CONFIG_CVITEK_REMOTEPROC` + mailbox remain, so Arduino
firmware loads via `/sys/class/remoteproc/`.

::: {.notes}
Changing the memory map ⇒ separate full image per personality.
:::

## Runtime Gotchas {.smaller}

- **systemd ordering:** `Before=ifup@wifi0.service` (typo) → `ifup@wlan0`
  read the default `inet manual` before `S30wifi` wrote the config.
- **`echo -e` under dash:** generated `wlan0` config got literal `-e`;
  use `printf`.
- **Open network:** empty pass ⇒ `wpa-key-mgmt NONE` (not empty `wpa-psk`).
- **Hostname:** `/etc/hostname` is rewritten each boot; use `/boot/hostname`.
- **Dual-homing:** same subnet on `end0`+`wlan0` breaks ARP; distinct DHCP
  names + `arp_ignore=1`/`arp_announce=2` if both must be up.

::: {.notes}
These are the "config is right but behavior is wrong" class of bugs.
:::

## Deterministic Networking {.smaller}

`preconfigure` edits `/etc/dhcpcd.conf`:

```ini
duid ll                      # stable DHCPv6 DUID
slaac hwaddr                 # stable EUI-64 SLAAC
nohook hostname              # don't rename the system host
interface wlan0
    hostname oz64-nat-wifi   # ethernet keeps "oz64-nat"
```

⇒ `oz64-nat.lan` (eth) / `oz64-nat-wifi.lan` (WiFi), each with stable A/AAAA;
`oz64-nat.local` still resolves both via mDNS.

::: {.notes}
Address selection prefers IPv6, so one stale AAAA makes a v4 fix look broken.
:::

## Command Reference {.smaller}

```sh
# build / flash
docker run --privileged -it --rm -v "$PWD/configs":/configs \
  -v "$PWD/image":/output ghcr.io/scpcom/sophgo-sg200x-debian:debian \
  make BOARD=oz64 SECOND_CPU=arduino IMAGE_HOSTNAME=oz64-nat \
       WIFI_MODE=sta WIFI_SSID=domenet image
lz4 -cd image/oz64-e_sd.img.lz4 | sudo dd of=/dev/sdX bs=4M status=progress

# diagnose on board
cat /proc/device-tree/model; ls /sys/bus/mmc/devices
lsmod | grep -E 'aic|cfg80211'; dmesg | grep -iE 'aicbsp|mmc1'
wpa_cli -i wlan0 signal_poll; ip neigh; ping -I wlan0 <gw>
```

::: {.notes}
Keep this slide as the one-page crib sheet.
:::
