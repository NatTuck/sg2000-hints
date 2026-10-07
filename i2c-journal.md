# Oz64 I2C OLED — working journal

Goal: drive the ELEGOO SSD1306 I2C OLED on the Oz64 (`ssh debian@oz64-toad`)
using a minimal, no-dependency Python driver.

## Hardware / OS

- Board: Pine64 Oz64 (Sophgo SG2000), Debian GNU/Linux 13 (trixie), riscv64.
- Kernel: `5.10.260-20260911-7+oz64`.
- `/proc/device-tree/model` = `Pine64 Oz64`.
- U-Boot `fdtfile=cv181x_milkv_duos_sd.dtb` and `/boot/board` says
  `id=maixcam` — i.e. the image is a DuoS/MaixCAM-derived build. Header pin
  functions therefore follow the DuoS pinmux, not the Oz64 silkscreen.
- Display: ELEGOO 0.96" SSD1306, 128x64, I2C, 7-bit address `0x3C`
  (silkscreen `0x78` is the 8-bit write address).
- Wired to header pins 1 (3V3), 3, 5 (I2C pair), 9 (GND).
  NOTE: SG2000 headers are commonly pin 3 = SCL, pin 5 = SDA (opposite of the
  Raspberry Pi convention) — if detection fails, swap these two first.

## Board inventory (as found)

- `/dev/i2c-1..4` exist. `i2c-0` is `disabled` in the device tree.
- `/sys/bus/i2c/devices/4-0014` = `gt9xx` touch controller bound on `i2c-4`
  (MIPI-DSI touch bus). So the header bus is probably `i2c-1`, to be confirmed.
- `i2c-tools` is installed but binaries live in `/usr/sbin`
  (`i2cdetect`, `i2cget`, `i2cset`, `i2ctransfer`).
- `duo-pinmux` and `cvi-pinmux` present (need `/dev/mem` -> root).
- `ssd1307fb.ko` available; `python3-smbus` / `python3-luma.oled` in apt.

## Access constraint

- `debian` was **not** in the `i2c` group; `sudo` needed a password.
- Decision: enable passwordless sudo, then `usermod -aG i2c debian` so plain
  Python/`i2cdetect` can talk to the bus without sudo.

## Log

### 2026-10-06 — kickoff
- Created this journal.
- Next: add `debian` to `i2c` group, confirm, detect `0x3c`.

### 2026-10-06 — access
- `id` now shows `106(i2c)`; `sudo` is NOPASSWD.
- `i2cdetect -l` reports adapters `i2c-1..4` (i2c-0 disabled).

### 2026-10-06 — first scans found nothing
- `i2cdetect -y -r 1..4`: no device on any bus.
- Read the Oz64 schematic (sheet 11, connector `J47`, "14 Pi-2 Connector")
  to get the real header netlist:

  | Pin | Net | SoC pad |
  |-----|-----|---------|
  | 1   | 3.3V_A | |
  | 3   | I2C3_SDA/I2C4_SCL net | **XGPIOB[20]** |
  | 5   | I2C3_SCL/I2C4_SDA net | **XGPIOB[21]** |
  | 9   | GND | |
  | 7   | GPCLK0 | XGPIOB[18] |
  | 11/13 | GPIO_17/27 | XGPIOB[11]/[12] |

  (`I2C1_*` text inside the connector symbol is just the generic Raspberry-Pi
  symbol pin name; the real nets are the `XGPIOB` ones. Pin 3 = SDA, pin 5 = SCL.)

- Live pinmux (`cvi-pinmux -l` / `duo-pinmux -l`) showed **only IIC3 active, on
  pads A5 (SCL) / A6 (SDA)** — i.e. the header was still plain GPIO.
- Writing `duo-pinmux -w B20/IIC3_SDA` + `B21/IIC3_SCL` alone did **not** make
  the OLED respond, because IIC3 was *also* still muxed to A5/A6 — two pad
  groups driving the same IIC3 SCL/SDA lines.

### 2026-10-06 — fix (the key step)
Free the default IIC3 pads, then route IIC3 to the header:

```sh
sudo cvi-pinmux -w IIC3_SCL/XGPIOA_5
sudo cvi-pinmux -w IIC3_SDA/XGPIOA_6
sudo duo-pinmux -w B20/IIC3_SDA     # header pin 3 (SDA)
sudo duo-pinmux -w B21/IIC3_SCL     # header pin 5 (SCL)
```

Immediately after, `i2cdetect -y -r 3` shows `3c`. Hardware IIC3 == `/dev/i2c-3`
(verified by watching the B20/B21 pad-input register toggle only when
hammering `i2c-3`).

### 2026-10-06 — drive it
- Minimal no-dependency driver: `hints/work/oled/ssd1306.py`
  (stdlib only: `/dev/i2c-N` + `I2C_SLAVE` ioctl; built-in 5x7 font).
- Test: `python3 hints/work/oled/ssd1306.py "Hello Oz64"` -> `wrote ... to
  /dev/i2c-3 @ 0x3c`.

### Diagnoses that were ruled out
- Header wiring/power: B20/B21 idle high with `-b pull-down` (external pull-ups).
- SoC not driving: pad-input register toggles during transfers.
- Controller vs. bit-bang: a slow Python bit-bang scan also failed before the
  A5/A6 fix, confirming the problem was pinmux, not the DesignWare driver.
- SDA/SCL orientation is correct for IIC3 (pin 3 SDA); IIC4 is the reverse.

### Reboot note
Pinmux from `duo-pinmux`/`cvi-pinmux` is not persistent, so the recipe is
installed as a systemd oneshot:

- `/usr/local/sbin/oz64-oled-setup.sh` (from `hints/work/oled/oz64-oled-setup.sh`)
- `/etc/systemd/system/oz64-oled.service` (from `hints/work/oled/oz64-oled.service`)

`systemctl enable --now oz64-oled` -> `active (exited)`, status 0. The four
pinmux commands now re-run on every boot; the OLED is ready on `/dev/i2c-3`.

### Multi-line confirmation
`python3 /tmp/ssd1306.py "Oz64 + SSD1306\nI2C3 @ 0x3C\nDebian 13 riscv64"`
rendered three lines on the panel. Confirmed visually.

### 2026-10-06 — installed / archived
- Driver installed on the board at `/usr/local/bin/ssd1306.py` (0755); run as
  `ssd1306.py "<text>"` (also `--bus`, `--addr`, `--invert`).
- Archived the working example to `examples/i2c-py/` (driver + setup script +
  systemd unit).

## 2026-10-06 — I2C slide deck + C examples

Goal: a lecture deck (Quarto RevealJS, like `freertos-slides/`) on I2C generally
and on the SG2000/Oz64, with C code for Linux, Arduino, and FreeRTOS.

### Deck
- `i2c-slides/index.qmd`, `refs.md`, `custom.scss`, `Makefile`; added an **I2C**
  menu to `_quarto.yml` and a section to `index.qmd`.
- `quarto render .` is clean (index + refs + site render).

### Code (`examples/`)
- `i2c-c/`: `ssd1306.h` (transport-agnostic device layer), `font5x7.h`
  (generated from the Python font), `linux-i2c-dev.c`, `linux-mmap-bitbang.c`,
  `Makefile`. Cross-built with `riscv64-linux-gnu-gcc -static`.
- `i2c-arduino/oled-bitbang/`: sketch + the same two headers.
- `i2c-freertos/`: `i2c_dw.c/.h`, `i2c_bitbang.c/.h`, `oled_task.c`.

### Findings (new)
- **Verified** on the Oz64: `linux-i2c-dev /dev/i2c-3 "…"` and
  `sudo linux-mmap-bitbang "…"` both refresh the panel; the bit-bang restores the
  pads to IIC3, and `i2cdetect` still sees `3c`.
- **Userspace raw DesignWare registers fail**: with the kernel driver bound,
  `IC_STATUS` reads 0 — the block is runtime clock-gated. This is why the raw
  Linux rung is a GPIO bit-bang, and the FreeRTOS register driver documents an
  `i2c_clock_enable()` step.
- **No `remoteproc` on this Oz64 image**: the DTB has no `cv181x-c906_1` node
  (only `rtos_cmdqu`; `/dev/cvi-mon0`). `cvitek_remoteproc.ko` exists but finds
  no device. So the Arduino sketch **builds** for `sophgo:SG200X:duos` (entry
  `0x9fe00000`) but **cannot be loaded** here. Marked "built" in the deck.
- **Arduino `Wire` cannot reach our OLED** on the `duos` variant: `PIN_IIC3_*`
  is `0xff` (IIC3 unimplemented), and `Wire4` uses IIC4 with `XGPIOB[20]` = SCL /
  `XGPIOB[21]` = SDA — the reverse of the header's pin-3=SDA/pin-5=SCL wiring.
  The verified Arduino path is therefore the bit-bang sketch.
- FreeRTOS examples are **reasoned** (not run).

## 2026-10-06 — remoteproc root cause (why Arduino can't load)

The Oz64 image lacks `remoteproc` not because of config, but because the DTS
stopped describing the C906L:

- Board DTS `configs/oz64/dts/cv181x_milkv_duos_sd.dts` includes
  `soph_default_memmap.dtsi`; the pinned kernel (`scpcom/linux`
  `licheervnano-merged-5.10.y` @ `ef8ba1a…`) ships that as the vendor layout
  (`fast_image`/`rtos_image` + `ion`, **no** `rproc`/`vdev0*`).
- Commit `9dc5f70` ("duos: dts: sync with duo-buildroot-sdk-v2") switched from
  the rproc-bearing `cv181x_default_memmap.dtsi` to `soph_default_memmap.dtsi`
  and deleted the `mbox@0x01900000` and `cv181x-c906_1` nodes. So the rproc
  driver (`compatible = "cvitek,cv181x-c906_1"`) matches nothing.
- `CONFIG_CVITEK_REMOTEPROC=m` and all rproc/mailbox/rpmsg patches are present;
  the older scpcom DuoS image (pre-Feb-2025) worked because it predates the sync.
- Also: the Oz64 image ships no `/lib/firmware/c906-mcu.elf`, and remoteproc is
  not auto-started.

Fix plan written to the image repo:
`/home/nat/Code/sophgo-sg200x-debian/notes/fix-arduino.md` — restore the
rproc memmap + `mbox`/`cv181x-c906_1` nodes, gated on `SECOND_CPU=arduino`, then
rebuild/reflash and verify `/sys/class/remoteproc/remoteproc0`.





