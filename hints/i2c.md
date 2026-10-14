# I2C on the SG2000 boards (Oz64 & DuoS): pinmux + `/dev/i2c-*`

**Boards:** Pine64 Oz64 (SG2000) and Milk-V Duo S (SG2000).
**Status:** the Oz64 paths marked *verified* were run on hardware; the rest are
derived from the header pinout and the live pinmux tables (see notes).

Both boards run a DuoS/MaixCAM-derived device tree, so the **J3 header pads and
their I2C functions are the same**; the main difference is the FSBL default mux
(Oz64 boots with IIC3 already active on pads `A5`/`A6`; the DuoS has no IIC
muxed at all). This doc is the consolidated "get I2C working + use
`/dev/i2c-*`" reference. The working journal (IIC3 on the Oz64, with the
schematic/netlist) is [`../i2c-journal.md`](../i2c-journal.md); the slide deck is
[`../i2c-slides/`](../i2c-slides/).

---

## 1. The two blocks you must get right

1. **Pinmux / I/O controller** (`0x03001000`): decides which peripheral is on a
   pad. Tools: `duo-pinmux` / `cvi-pinmux` (write the mux registers via
   `/dev/mem`, so **root**).
2. **I2C controller** (DesignWare): the kernel driver exposes each controller as
   `/dev/i2c-N`.

`/dev/i2c-N` maps to the controller index:

| Controller | Device | Notes |
|---|---|---|
| IIC0 | `/dev/i2c-0` | `disabled` in the DT (no node) |
| IIC1 | `/dev/i2c-1` | |
| IIC2 | `/dev/i2c-2` | |
| IIC3 | `/dev/i2c-3` | |
| IIC4 | `/dev/i2c-4` | |

So: **get the pads muxed to the right IIC, then talk to `/dev/i2c-N`.**

### Tools and syntax

```sh
sudo duo-pinmux -l              # list pads + functions ([v] = active)
sudo duo-pinmux -r B11          # read one pad
sudo duo-pinmux -w B11/IIC1_SDA # write:  PAD/FUNC

sudo cvi-pinmux -l              # same idea, SoC pad names
sudo cvi-pinmux -w IIC1_SDA/XGPIOB_11   # NOTE: FUNC/PAD (reversed!)
```

`duo-pinmux` names pads `B11`, `B20`, …; `cvi-pinmux` names the SoC pad
(`XGPIOB_11`) and takes the *function first*. Both write the same registers.
Pinmux is **not persistent** — it resets on reboot (see §5).

### Permissions

`/dev/i2c-N` is `root:i2c`. Either prefix commands with `sudo`, or:

```sh
sudo usermod -aG i2c debian   # then log out/in
```

`i2cdetect`/`i2cget`/… live in `/usr/sbin` (not on `debian`'s default PATH);
use `/usr/sbin/i2cdetect` or `sudo i2cdetect`.

---

## 2. J3 header map (26-pin, 3.3V) — same on Oz64 and DuoS

RPi-style numbering. The I2C-relevant pins:

| Pin | Signal | SoC pad | I2C function(s) |
|----:|---|---|---|
| 1 | 3V3 | | power |
| 3 | B20 | `XGPIOB_[20]` | **IIC3_SDA** / IIC4_SCL |
| 5 | B21 | `XGPIOB_[21]` | **IIC3_SCL** / IIC4_SDA |
| 6 | GND | | |
| 7 | B18 | `XGPIOB_[18]` | IIC1_SCL |
| 9 | GND | | (V1.1 DuoS: low-level GPIO; V1.2+: GND) |
| 11 | B11 | `XGPIOB_[11]` | **IIC1_SDA** |
| 13 | B12 | `XGPIOB_[12]` | **IIC1_SCL** |
| 14 | GND | | |
| 17 | 3V3 | | power |
| 19 | B13 | `XGPIOB_[13]` | IIC2_SCL |
| 20 | GND | | |
| 21 | B14 | `XGPIOB_[14]` | IIC2_SDA |
| 25 | GND | | |

Three "modes" are useful on both boards:

| Mode | Header pins | Wiring | Bus | Arduino |
|---|---|---|---|---|
| **IIC1** | 11 / 13 | pin 11 = SDA, pin 13 = SCL | `/dev/i2c-1` | `Wire` (= `Wire1`) |
| **IIC3** | 3 / 5 | pin 3 = SDA, pin 5 = SCL | `/dev/i2c-3` | `Wire3` — **unimplemented** in the duos variant |
| **IIC4** | 3 / 5 | pin 3 = SCL, pin 5 = SDA | `/dev/i2c-4` | `Wire4` |
| IIC2 (DuoS) | 19 / 21 | pin 19 = SCL, pin 21 = SDA | `/dev/i2c-2` | not mapped |

Note IIC3 and IIC4 share the **same two pins (3/5) with SDA/SCL swapped** — so you
can't use both at once, and getting the two wires backwards is the classic
"I2C doesn't respond".

---

## 3. Recipes

Use VCC → pin 1 or 17 (3V3) and GND → pin 9/6/14, then the SDA/SCL pins below.

### Mode IIC1 — pins 11/13 → `/dev/i2c-1`  *(Oz64: verified)*

```sh
sudo duo-pinmux -w B11/IIC1_SDA      # header pin 11 (SDA)
sudo duo-pinmux -w B12/IIC1_SCL      # header pin 13 (SCL)
sudo i2cdetect -y -r 1               # -> 3c
```

This is the bus a stock Arduino library uses with the default `Wire`
(`variants/duos/variant.h`: `#define Wire Wire1`). No default-pad conflict on
either board (B11/B12 power up as PWM/UART, not I2C).

### Mode IIC3 — pins 3/5 (SDA on 3) → `/dev/i2c-3`  *(Oz64: verified)*

On the **Oz64** the FSBL already muxes IIC3 to pads `A5`/`A6`, so you must free
those first, then route IIC3 to the header (`B20`/`B21`):

```sh
sudo cvi-pinmux -w IIC3_SCL/XGPIOA_5    # free the default FSBL mux
sudo cvi-pinmux -w IIC3_SDA/XGPIOA_6
sudo duo-pinmux -w B20/IIC3_SDA         # header pin 3 (SDA)
sudo duo-pinmux -w B21/IIC3_SCL         # header pin 5 (SCL)
sudo i2cdetect -y -r 3                  # -> 3c
```

On the **DuoS** nothing is muxed to IIC by default, so (in principle) only the
two `duo-pinmux` lines are needed — but IIC3 is the CSI camera **J1** bus (1.8V),
so don't fight it if a camera is attached.

### Mode IIC4 — pins 3/5 (SCL on 3) → `/dev/i2c-4`

Same pads as IIC3, swapped — this is what Arduino `Wire4` expects:

```sh
sudo duo-pinmux -w B20/IIC4_SCL         # header pin 3 (SCL)
sudo duo-pinmux -w B21/IIC4_SDA         # header pin 5 (SDA)
sudo i2cdetect -y -r 4
```

If a DSI/LCD touch panel is in use it may already own IIC4; free/avoid it (the
touch shows up as an i2c device on `i2c-4`).

### Mode IIC2 — pins 19/21 → `/dev/i2c-2`  *(DuoS; also the Oz64 pads)*

```sh
sudo duo-pinmux -w B13/IIC2_SCL         # header pin 19 (SCL)
sudo duo-pinmux -w B14/IIC2_SDA         # header pin 21 (SDA)
sudo i2cdetect -y -r 2
```

Caveat: IIC2 is the Raspberry-Pi CSI camera **J2** bus (3.3V); if you use that
camera, IIC2 on J3 is unavailable.

---

## 4. Per-board notes

- **Oz64**
  - Boots with **IIC3 active on `A5`/`A6`** (the "A5/A6 trap"): for header IIC3
    you must free them first (above); for IIC1/IIC4 there's no such conflict.
  - `B11`/`B12` default to PWM_1/PWM_2, `B20`/`B21` default to plain GPIO.
  - Verified on hardware: IIC1 (pins 11/13) and IIC3 (pins 3/5).
  - The physical connector may be silkscreened differently, but the pad mapping
    is the DuoS one (the image ships a DuoS/MaixCAM-derived DTB).
- **DuoS**
  - No IIC is muxed at boot (`duo-pinmux -l` shows none active) — you just mux
    what you need.
  - Header J3 is 3.3V; header **J4 is 1.8V** (IIC2/IIC4 there too — don't mix).
  - IIC3 → CSI **J1** (1.8V), IIC2 → CSI **J2** (3.3V). The pinout labels J3
    pins 3/5 as **I2C4** (SCL on 3, SDA on 5).

### The "A5/A6 trap" (why writes alone can fail)

`duo-pinmux -w B20/IIC3_SDA` on the Oz64 does **nothing useful on its own**,
because IIC3's SCL/SDA lines are *also* still driven by the FSBL default pads
`A5`/`A6` — two pad groups on the same IIC3 lines. Free `A5`/`A6` first
(`cvi-pinmux -w IIC3_SCL/XGPIOA_5` / `IIC3_SDA/XGPIOA_6`). This is specific to
buses whose default pads are elsewhere in the FSBL mux.

---

## 5. Persistence (pinmux resets on reboot)

`duo-pinmux`/`cvi-pinmux` only change registers. To re-apply at boot, use a
`oneshot` unit. Example (Oz64 IIC1 on pins 11/13):

```sh
# /usr/local/sbin/i2c-mux.sh
#!/bin/sh
duo-pinmux -w B11/IIC1_SDA
duo-pinmux -w B12/IIC1_SCL
```

```ini
# /etc/systemd/system/i2c-mux.service
[Unit]
Description=Apply I2C pinmux
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/i2c-mux.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```sh
sudo chmod +x /usr/local/sbin/i2c-mux.sh
sudo systemctl enable --now i2c-mux
```

(The journal uses the same pattern for the Oz64 IIC3 OLED as
`oz64-oled.service`; see [`../examples/i2c-py/`](../examples/i2c-py/).)

---

## 6. Verify and use

```sh
/usr/sbin/i2cdetect -y -r 1     # -r = probe with reads; expect 0x3c (SSD1306)
```

`i2c-tools` is **not installed on every image** (e.g. the DuoS Fishwaldo image has
no `i2cdetect`). Stdlib-only scan fallback:

```sh
sudo python3 - 1 <<'PY'   # bus number as argv[1]
import fcntl, os, sys
bus = int(sys.argv[1])
found = []
for a in range(0x03, 0x78):
    fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
    try:
        fcntl.ioctl(fd, 0x0703, a)          # I2C_SLAVE
        try:
            os.write(fd, b"\x00")
            found.append(hex(a))
        except OSError:
            pass
    finally:
        os.close(fd)
print("devices on i2c-%d:" % bus, found)
PY
```

- **Python** (stdlib only): [`../examples/i2c-py/ssd1306.py`](../examples/i2c-py/ssd1306.py)
  ```sh
  sudo python3 examples/i2c-py/ssd1306.py --bus 1 "Hello Oz64"
  ```
- **C**: [`../examples/i2c-c/linux-i2c-dev.c`](../examples/i2c-c/)
  ```sh
  ./linux-i2c-dev /dev/i2c-1 "Hello"
  ```
- **Bit-bang** (no kernel driver): `examples/i2c-c/linux-mmap-bitbang.c`, or the
  Arduino sketch `examples/i2c-arduino/oled-bitbang/`.

### Arduino bus mapping (duos/oz64 variant)

| Arduino | IIC | Header | Notes |
|---|---|---|---|
| `Wire`/`Wire1` | IIC1 | pins 11/13 | matches most libraries (`Adafruit_SSD1306(...,&Wire)`) |
| `Wire2` | IIC2 | pins 19/21 | |
| `Wire3` | IIC3 | — | **unimplemented** on the duos/oz64 variant (`PIN_IIC3_* = 0xff`) |
| `Wire4` | IIC4 | pins 3/5 (SCL on 3) | reversed vs IIC3 wiring |

So for a stock Arduino library on this header, use **IIC1 (pins 11/13)** with the
default `Wire` — no code changes.

---

## 7. Troubleshooting

- **`i2cdetect` shows nothing.** In order: (1) swap SDA/SCL — IIC3 vs IIC4 on
  pins 3/5 are swapped; (2) check the A5/A6 trap if using IIC3 on the Oz64;
  (3) confirm the mux actually took (`duo-pinmux -l` — is `[v]` on your function?);
  (4) confirm power/GND; (5) most modules include pull-ups, but bare chips need
  them.
- **Worked before a reboot.** Pinmux isn't persistent — re-apply or enable the
  systemd unit (§5).
- **`/dev/i2c-N` permission denied.** Add `debian` to the `i2c` group or use
  `sudo`.
- **Wrong bus.** `IICn` ↔ `/dev/i2c-n`; verify with `i2cdetect -l`.
- **`duo-pinmux: cannot open /dev/mem`.** Run as root.
