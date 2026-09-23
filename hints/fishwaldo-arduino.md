# Milk-V DuoS (10.42.0.1) — Running Arduino sketches on the second core at runtime

**Assessment date:** 2026-09-11
**Access:** passwordless SSH as `debian@10.42.0.1`
**Board:** Milk-V DuoS (SG2000 / CV181x), hostname `duos`, `nproc` = 1
**OS:** Debian GNU/Linux trixie/sid, kernel `5.10.4-20240527-2+` (riscv64)

This file has two parts:

1. **Quick start** — build an Arduino sketch and run it on the second (little)
   C906 core, end to end.
2. **Background & evidence** — why this works the way it does.

> Board preparation (flashing the image, `ssh-copy-id`, passwordless `sudo`) is
> in [`setup.md`](setup.md).

## Status

**Under test — no verdict yet.** What is confirmed:

- A compiled Arduino sketch (`Blink.ino.elf` / `Blink4.ino.elf`, FQBN
  `sophgo:SG200X:duos`) **runs on the little C906 core** when loaded via
  remoteproc, driving the user LED on J3 pin 7 (pad `XGPIOB18`, Linux `gpio466`)
  — verified at ~1 Hz and, with a distinct `Blink4.ino` sketch, at **3.98 Hz**,
  proving the freshly uploaded image is what executes.
- The same `.elf` **cannot** be run as a Linux process; `execve` fails with
  `SIGILL` (exit 132).
- The stock image's `/lib/firmware/c906-mcu.elf` is **byte-for-byte identical** to
  the `Blink.ino.elf` built here (`md5 fbd2819d8a644bf4a6c83ee36287e848`), so the
  little core already runs that Blink once remoteproc is started.
- The Arduino IDE upload path is **not** available on this image (no CDC-ACM
  serial gadget, no `burntool.py` receiver), so the sketch is loaded manually via
  remoteproc.

## Quick start

### 0. Prerequisites (one-time, host machine)

- Linux host with `arduino-cli`.
- Passwordless SSH to `debian@10.42.0.1` and NOPASSWD `sudo` on the board
  (see [`setup.md`](setup.md)).
- Install the Sophgo board core:

  ```sh
  arduino-cli config add board_manager.additional_urls \
    https://github.com/kubuds/sophgo-arduino/releases/download/v0.2.5/package_sg200x_index.json
  arduino-cli core update-index
  arduino-cli core install sophgo:SG200X

  arduino-cli board listall | grep 'sophgo:SG200X:duos'
  # DuoS Dev Module  sophgo:SG200X:duos
  ```

### 1. The sketch

`work/Blink4/Blink4.ino` — 4 Hz (125 ms on / 125 ms off), LED on J3 pin 7:

```cpp
#define LED_PIN 7

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(125);
  digitalWrite(LED_PIN, LOW);
  delay(125);
}
```

### 2. Build

```sh
arduino-cli compile --fqbn sophgo:SG200X:duos --build-path work/build4 work/Blink4

# Output:
#   work/build4/Blink4.ino.elf
readelf -h work/build4/Blink4.ino.elf | grep Entry
#   Entry point address: 0x9fe00000
```

The `duos` FQBN links the image at `0x9fe00000` / max 2 MB, matching the kernel's
`rproc` carveout (see [Arduino ELF compatibility](#arduino-elf-compatibility)).

### 3. Load onto the little core

The `.elf` is not a Linux program — it is bare-metal firmware. The core must be
`offline` before you can change its firmware. See the state:

```sh
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'
```

If it prints `running`, stop it (running `stop` when the core is already
`offline` prints `Invalid argument`, which is expected and harmless):

```sh
ssh debian@10.42.0.1 'echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

Copy the image into `/lib/firmware`, select it by file name (not a path), and
start it:

```sh
scp work/build4/Blink4.ino.elf debian@10.42.0.1:/tmp/blink4.elf
ssh debian@10.42.0.1 'sudo cp /tmp/blink4.elf /lib/firmware/blink4.elf'
ssh debian@10.42.0.1 'echo blink4.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware'
ssh debian@10.42.0.1 'echo start | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

### 4. Verify

Kernel log should show the new image:

```sh
ssh debian@10.42.0.1 'sudo dmesg | tail -5'
# Booting fw image sketch.elf, size ...
# Started from 0x9fe00000
# remote processor cv181x-c906_1 is now up
```

Visually, the LED on J3 pin 7 should blink at 4 Hz.

To measure the rate, sample the `XGPIOB18` pad register (`EXT_PORTA`,
`0x03021050`, bit 18) over `/dev/mem` — the ground truth (do **not** trust the
Linux `gpio466` sysfs `value`, which can alias):

```sh
ssh debian@10.42.0.1 'sudo python3 -' <<'PY'
import mmap, struct, os, time
f = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
g = mmap.mmap(f, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x03021000)
def bit18():
    g.seek(0x50)
    return (struct.unpack("<I", g.read(4))[0] >> 18) & 1
prev, t0, edges = bit18(), time.time(), []
while time.time() - t0 < 2.0:
    v = bit18()
    if v != prev:
        edges.append(time.time()); prev = v
    time.sleep(0.005)
hp = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
m = sum(hp) / len(hp)
print("mean half-period %.3f s -> %.2f Hz cycle" % (m, 1 / (2 * m)))
PY
# mean half-period 0.126 s -> 3.98 Hz cycle
```

### 5. Restore the stock firmware

```sh
ssh debian@10.42.0.1 '
  S=/sys/class/remoteproc/remoteproc0/state
  echo stop | sudo tee $S
  echo c906-mcu.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware
  echo start | sudo tee $S
  sudo rm -f /lib/firmware/sketch.elf
'
```

### 6. Caveats

- **Not persistent across reboot.** Remoteproc is not auto-started by any systemd
  unit; after a reboot the remote is `offline` and the stock Blink stops. Re-run
  step 3 (or add your own unit). No boot-persistence service is set up here.
- **No Arduino IDE upload.** USB gadget is RNDIS-only, so the platform's
  `burntool.py -p /dev/ttyACM0 -f ...` pattern has no port and there is no
  receiver running. Loading via remoteproc is the workaround.
- `cvitek_mailbox` taints the kernel (`bad vermagic`), and the driver logs
  `Allocated carveout doesn't fit device address request` on every boot. Neither
  blocked any test here.
- The image must link at `0x9fe00000` (2 MB max). The `duos` FQBN handles this;
  don't build with a different variant's FQBN.

## Background & evidence

### Why `python blink.py` works but `Blink.ino.elf` "doesn't"

They are two different execution models that drive the same physical pad:

| | `python blink.py` | `Blink.ino.elf` |
|---|---|---|
| Runs on | big core, Debian userspace | little core (C906_1), bare metal |
| Mechanism | `duo-pinmux` + sysfs GPIO | direct pinmux/GPIO register writes |
| Delivery | SSH | remoteproc firmware load |
| Pin | B18 / `gpio466` (`blink.py` `GPIO = 466`) | Arduino pin 7 = `VIVO_D3__XGPIOB_18` |

- `blink.py` is an ordinary Linux program; it works because Debian provides
  syscalls, the GPIO driver, and the pinmux helper.
- `Blink.ino.elf` is a statically linked `EXEC` RISC-V ELF with entry
  `0x9fe00000`, no dynamic section and no interpreter, built with
  `--specs=nosys.specs`. It assumes it owns the hardware, so the kernel can load
  it but the first privileged access faults (`SIGILL`).
- To run it you place it in the `rproc` carveout and start the remote processor
  (step 3). This is what the Arduino/burntool flow does with a serial receiver;
  on this image there is no receiver, so it is manual.

### Environment

- `cat /proc/device-tree/model` → `Milk-V DuoS`
- `hostname` → `duos`; `uname -a` → `Linux duos 5.10.4-20240527-2+ #1 ... riscv64`
- Packages of interest: `cvitek-fsbl-duos`, `linux-image-duos-5.10.4-20240527-2+`,
  `duo-pinmux`, `cvi-pinmux-cv181x`.

> `duo-pinmux`'s package description names a different Duo variant, but it is the
> tool `blink.py` uses successfully on this DuoS.

### Kernel-level remoteproc support

- Modules: `cvitek_remoteproc`, `cvitek_mailbox`, `rtc_cvitek`, `adc_cvitek`,
  `pwm_cvitek`; rpmsg modules exist under
  `/lib/modules/5.10.4-20240527-2+/kernel/drivers/{remoteproc,rpmsg,mailbox}`.
- `/sys/class/remoteproc/remoteproc0`: `name` = `cv181x-c906_1`,
  `state` = `running`, `firmware` = `c906-mcu.elf`, `recovery` = `enabled`,
  `coredump` = `disabled`.
- Not auto-started; dmesg shows the boot at t≈365 s, well after kernel init.

### Device tree

- `/proc/device-tree/cv181x-c906_1/`: `compatible: cvitek,cv181x-c906_1`,
  `firmware: c906-mcu.elf`, `status: okay`, `mbox-names: vq_tx vq_rx`.
- `/proc/device-tree/reserved-memory/` contains `rproc`, `vdev0buffer`,
  `vdev0vring0`, `vdev0vring1`, `cvifb`, `mmode_resv0@80000000`.
- The `rproc` region decodes to base `0x9fe00000`, size `0x200000` (2 MB).

Observed boot:

```
remoteproc remoteproc0: powering up cv181x-c906_1
remoteproc remoteproc0: Booting fw image c906-mcu.elf, size 98256
cvitek-rproc cv181x-c906_1: Allocated carveout doesn't fit device address request
cvitek-mailbox 1900000.mbox: phandle args count: 4
cvitek-mailbox 1900000.mbox: Channel 1: direction 1, cpu 2, mask 1
cvitek-mailbox 1900000.mbox: Channel 0: direction 2, cpu 2, mask 1
remoteproc remoteproc0: Started from 0x9fe00000
remoteproc remoteproc0: remote processor cv181x-c906_1 is now up
```

### Arduino ELF compatibility

- `boards.txt`: `duos.build.start_addr=0x9fe00000`,
  `duos.build.image_size=0x200000`, `duos.upload.tool=burntool_py`.
- `variants/duos/link.ld`:
  `MEMORY { psu_ddr_0_MEM_0 : ORIGIN = 0x9fe00000 , LENGTH = 0x200000 }`,
  `ENTRY(Reset_Handler)`, and a `.resource_table` section in that region.
- `readelf -h Blink.ino.elf` → `EXEC`, entry `0x9fe00000`, double-float ABI,
  statically linked, no dynamic section / no `INTERP`.
- `Blink.ino.map` confirms `psu_ddr_0_MEM_0 0x9fe00000 0x200000` and
  `.resource_table` at `0x9fe0e240`, matching the `rproc` carveout.

### Pin identity

Arduino pin 7 resolves through `variants/duos/`:

- `variant_pins.h`: `PIN_XGPIOB18 (7)`
- `variant_pin_maps.c`: `out_pin_map[7] = VIVO_D3`,
  `out_pin_func_map[7] = VIVO_D3__XGPIOB_18`
- Linux maps the same bank to `gpiochip448` (`label=3021000.gpio`), so
  `448 + 18 = 466` = `gpio466` used by `blink.py`.

So the Python script and the Arduino sketch drive the same pad.

### Experiment log

1. **Control (must fail).** Run the ELF as a Linux process:
   ```sh
   scp work/build/Blink.ino.elf debian@10.42.0.1:/tmp/blink.elf
   ssh debian@10.42.0.1 'chmod +x /tmp/blink.elf; /tmp/blink.elf'
   # Illegal instruction, exit code 132 (SIGILL)
   ```
2. **Manual load** (step 3) → dmesg shows `Booting fw image blink.elf` /
   `Started from 0x9fe00000` / `is now up`.
3. **Register proof.** Sampling `EXT_PORTA` bit 18 shows clean 0→1→0
   transitions; the LED blinks by eye too.
4. **RAM proof.** A diagnostic sketch writing `0xDEADBEEF` and an incrementing
   counter to free carveout RAM at `0x9FEF0000` confirmed the little core
   executes the loaded image and stays coherent with the big core.
5. **Stock firmware is the same binary.** `/lib/firmware/c906-mcu.elf` (dated
   2024-05-30) has `md5 fbd2819d8a644bf4a6c83ee36287e848`, identical to a fresh
   deterministic build of `Blink.ino.elf`. Swapping in our `Blink.ino.elf`
   therefore produces no visible change; a **distinct** sketch is required to
   prove the upload took effect.
6. **Distinct-rate check.** `work/Blink4/Blink4.ino` (`delay(125)`) loaded and
   timed: mean half-period `0.126 s` → **3.98 Hz cycle**, distinct from the
   stock 1 Hz Blink. Confirms the uploaded image runs.

## Open questions / next steps

- ~~Verify with a distinct sketch that a fresh upload is what is running.~~
  Done: `work/Blink4` runs at 3.98 Hz vs the stock 1 Hz Blink.
- Decide what `Allocated carveout doesn't fit device address request` means for
  arbitrary images.
- Determine whether the stock `c906-mcu.elf` being a Blink sketch is intentional
  or an image-build artifact.
- Evaluate adding a CDC-ACM gadget + receiver to make the standard Arduino IDE
  upload flow work on this image.
