# How a GPIO pin is controlled: Linux, Arduino, `mmap`, and pure asm

**Assessment date:** 2026-09-21
**Board:** Milk-V DuoS (SG2000 / CV181x), little core `cv181x-c906_1` ("RT core")
**Status:** **Verified on hardware.** Every command and listing below was typed and
run on the board; observed output is shown as `# ->` comments or in a separate
block. All four control paths drive the same physical pin.

This is a self-contained, type-it-yourself runbook. Everything you need to type
is reproduced inline; the cross-links at the end are background reading only.

We follow **one pin** the whole way down:

| Context | Name |
|---|---|
| Silkscreen | J3 pin 7 (external LED on the J3 header) |
| Silicon pad | `VIVO_D3` |
| GPIO function | `XGPIOB_18` |
| Linux global number | `gpio466` |
| Arduino | `pin 7` |

---

## 1. The hardware both ends must agree on

Driving a pin involves **two separate blocks**. Mixing them up is the most common
source of confusion.

1. **Pinmux / I/O controller** at `0x03001000`. It decides which peripheral is
   connected to the pad. For `VIVO_D3` the mux register is `0x03001150` and
   bits `[2:0]` select the function: `3` = GPIO.
2. **GPIO controller** at `0x03021000` (bank B, `XGPIOB`). It holds the data and
   direction bits. The DT `compatible` is `snps,dw-apb-gpio` (Synopsys
   DesignWare APB GPIO).

GPIO bank B registers (the bit for `XGPIOB_18` is `1 << 18` = `0x40000`):

| Register | Address | Meaning |
|---|---|---|
| `SWPORTA_DR` | `0x03021000` | output data |
| `SWPORTA_DDR` | `0x03021004` | direction (1 = output) |
| `EXT_PORTA` | `0x03021050` | pad input (read-only) |

The whole SoC peripheral space is memory-mapped. A "GPIO write" is just a store
to one of those addresses, after the mux has selected GPIO.

### Type this

```bash
ssh debian@10.42.0.1 'cat /proc/iomem | grep -i gpio'
```

```text
00000000-00000000 : 3020000.gpio gpio@03020000
00000000-00000000 : 3021000.gpio gpio@03021000
```

---

## 2. From Linux (the most abstract layer)

### 2.1 What the kernel gives you

The kernel enumerates each GPIO bank as a **gpiochip** and exposes it three ways:

- **libgpiod** (modern, preferred): the `gpiodetect`/`gpioinfo`/`gpioget`/`gpioset` tools.
- **sysfs** (legacy): `/sys/class/gpio`.
- **pinmux helper**: `duo-pinmux` writes the mux registers through `/dev/mem`.

The stack is `gpioset -> libgpiod -> gpiolib -> pinctrl -> MMIO store`.

### Type this

```bash
ssh debian@10.42.0.1 'sudo gpiodetect'
```

```text
gpiochip0 [3020000.gpio] (32 lines)
gpiochip1 [3021000.gpio] (32 lines)
gpiochip2 [3022000.gpio] (32 lines)
gpiochip3 [3023000.gpio] (32 lines)
gpiochip4 [5021000.gpio] (32 lines)
```

`gpiochip1` is `3021000.gpio` = `XGPIOB`; line 18 is our pin.

```bash
ssh debian@10.42.0.1 'sudo gpioinfo gpiochip1'
```

```text
gpiochip1 - 32 lines:
	line   0:      unnamed       unused   input  active-high
	...
	line  18:      unnamed       unused  output  active-high
	...
```

### 2.2 libgpiod

Set the line high, hold it, read the pad, then set it low. The `-m time -s 3`
holds the line for three seconds so we can observe it.

Create `readpin.py` (used by several demos):

```python
import mmap, struct, os
f = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
g = mmap.mmap(f, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x03021000)
g.seek(0x50)
print((struct.unpack("<I", g.read(4))[0] >> 18) & 1)
```

```bash
scp readpin.py debian@10.42.0.1:/tmp/readpin.py
```

```bash
ssh debian@10.42.0.1 'sudo gpioset -m time -s 3 gpiochip1 18=1'
```

While that holds, from another shell:

```bash
ssh debian@10.42.0.1 'sudo python3 /tmp/readpin.py'
```

```text
1
```

```bash
ssh debian@10.42.0.1 'sudo gpioset -m time -s 3 gpiochip1 18=0'
```

```bash
ssh debian@10.42.0.1 'sudo python3 /tmp/readpin.py'
```

```text
0
```

Observed sequence for the two `gpioset` calls:

```text
before          : EXT bit18 = 0
during 18=1     : EXT bit18 = 1
after  release  : EXT bit18 = 1
during 18=0     : EXT bit18 = 0
after  release  : EXT bit18 = 0
```

### 2.3 sysfs (legacy)

`gpiochip448` is bank B; global number `448 + 18 = 466`.

```bash
ssh debian@10.42.0.1 'cat /sys/class/gpio/gpiochip448/label'
ssh debian@10.42.0.1 'cat /sys/class/gpio/gpiochip448/base'
```

```text
3021000.gpio
448
```

```bash
ssh debian@10.42.0.1 'echo 466 | sudo tee /sys/class/gpio/export'
ssh debian@10.42.0.1 'echo out | sudo tee /sys/class/gpio/gpio466/direction'
ssh debian@10.42.0.1 'echo 1 | sudo tee /sys/class/gpio/gpio466/value'
ssh debian@10.42.0.1 'sudo python3 /tmp/readpin.py'
ssh debian@10.42.0.1 'echo 0 | sudo tee /sys/class/gpio/gpio466/value'
ssh debian@10.42.0.1 'sudo python3 /tmp/readpin.py'
ssh debian@10.42.0.1 'cat /sys/class/gpio/gpio466/value'
ssh debian@10.42.0.1 'echo 466 | sudo tee /sys/class/gpio/unexport'
```

```text
466
out
1
1          # pad bit18
0
0          # pad bit18
0          # value read back
466
```

### 2.4 The vendor pinmux tool

`duo-pinmux` reads/writes the mux registers directly through `/dev/mem`. It is
built for the original Duo, so it names pins `GP0..GP27`; it does **not** expose
`VIVO_D3`/`XGPIOB18` on the DuoS. It is still the standard way to see the mux.

```bash
ssh debian@10.42.0.1 'sudo duo-pinmux -l'
```

```text
GP0 function:
[ ] JTAG_TDI
[v] UART1_TX
[ ] UART2_TX
[ ] GP0
[ ] IIC0_SCL
[ ] WG0_D0
[ ] DBG_10

GP4 function:
[ ] PWR_SD1_D2
[ ] IIC1_SCL
[ ] UART2_TX
[v] GP4
...
```

On this board the mux for our pin is set with the register write shown in
section 4 (or, on the RT core, by the Arduino core's `pinMode`). Check it with:

```bash
ssh debian@10.42.0.1 'sudo duo-pinmux -p'
```

### Key idea

Every Linux path ends in the kernel driver doing a 32-bit read-modify-write of
`SWPORTA_DR`. The abstraction buys safety and arbitration (the kernel owns the
MMU and the pinctrl state), at the cost of a syscall and several layers per
transition.

---

## 3. From a standard Arduino sketch (RT core, no OS)

The sketch does not run on Linux. It is bare-metal firmware for the little C906
core, linked at `0x9fe00000` and loaded by remoteproc.

### 3.1 Blink

`Blink/Blink.ino`:

```c
#define LED_PIN 7

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  delay(1000);
}
```

Save each sketch as `<name>/<name>.ino` (Arduino requires the folder name to
match the file name). Build it (host side):

```bash
arduino-cli compile --fqbn sophgo:SG200X:duos --build-path build-blink Blink
```

```bash
riscv-none-elf-readelf -h build-blink/Blink.ino.elf | grep Entry
```

```text
Entry point address:               0x9fe00000
```

The little core is controlled through `/sys/class/remoteproc`. Work through the
steps below in order.

**See the state.** It prints `offline` (not running) or `running` (executing the
selected firmware):

```bash
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'
```

There is normally a single remote processor; `ls /sys/class/remoteproc/` lists
the ones that exist.

**The state you want before loading is `offline`.** You can only change the
firmware while the core is offline. If the state above was `running`, stop it:

```bash
ssh debian@10.42.0.1 'echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

Running `stop` on a core that is already `offline` prints `Invalid argument`;
that is expected and harmless. Confirm the state:

```bash
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'
```

You want to see `offline` before continuing.

**Copy the image where the driver looks for it.** The firmware loader reads
files from `/lib/firmware`. Copy your build in under a short name:

```bash
scp build-blink/Blink.ino.elf debian@10.42.0.1:/tmp/blink.elf
ssh debian@10.42.0.1 'sudo cp /tmp/blink.elf /lib/firmware/blink.elf'
```

Check that the copy is your build — the two hashes must match:

```bash
ssh debian@10.42.0.1 'md5sum /tmp/blink.elf /lib/firmware/blink.elf'
```

**Select that file as the firmware.** The `firmware` attribute holds a file
**name**, not a path; the driver resolves it under `/lib/firmware`. See the
current selection (it may be the factory `c906-mcu.elf`):

```bash
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/firmware'
```

The name you want is `blink.elf`. Set it:

```bash
ssh debian@10.42.0.1 'echo blink.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware'
```

Read it back to confirm:

```bash
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/firmware'
```

**Start it.**

```bash
ssh debian@10.42.0.1 'echo start | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

The state you want now is `running`:

```bash
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'
```

The kernel log should show the image being handed to the core:

```bash
ssh debian@10.42.0.1 'sudo dmesg | grep -iE "Booting fw image|is now up" | tail -2'
```

```text
[...] remoteproc remoteproc0: Booting fw image blink.elf, size 98256
[...] remoteproc remoteproc0: remote processor cv181x-c906_1 is now up
```

**Check the result.** The LED on J3 pin 7 should blink at the sketch's rate. If
it does not, re-check, in order: the state is `offline` before the load, the
file exists in `/lib/firmware`, and the `firmware` name matches the file. No
reboot or driver reload is needed.

**Stop it.**

```bash
ssh debian@10.42.0.1 'echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

The state you want is `offline`, and the LED goes dark:

```bash
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'
```

### 3.2 What `digitalWrite` actually does

`digitalWrite(7, HIGH)` walks this chain:

```text
digitalWrite (wiring_digital.c)
  -> csi_gpio_pin_write (csi_gpio_pin.c)
    -> csi_gpio_write (csi_gpio.c)
      -> dw_gpio_write_output_port  =>  port->SWPORTA_DR = ...
```

Pin 7 resolves through the variant tables:

```text
out_pin_map[7]      = VIVO_D3
out_pin_func_map[7] = VIVO_D3__XGPIOB_18     # PIN_FUNC_GPIO == 3
csi_gpio_pinmap     = { VIVO_D3, bank 1, channel 18 }
```

`objdump` shows the same store at the bottom of the chain. This is
`csi_gpio_write` — load `SWPORTA_DR`, OR/AND the bit, store it back:

```bash
riscv-none-elf-objdump -d build-blink/Blink.ino.elf | sed -n '/<csi_gpio_write>:/,/^$/p'
```

```text
9fe02ee8:  ld    a4,0(a0)          # a4 = reg base
9fe02ef0:  lw    a5,0(a4)          # a5 = SWPORTA_DR
9fe02efc:  or    a1,a1,a5          # high: set bit
9fe02f00:  sw    a1,0(a4)          # store back
...
9fe02f08:  not   a1,a1             # low: clear bit
9fe02f0c:  and   a1,a1,a5
9fe02f10:  j     9fe02f00          # sw
```

And the `loop()` itself is just calls:

```bash
riscv-none-elf-objdump -d build-blink/Blink.ino.elf | sed -n '/<_Z4loopv>:/,/^$/p'
```

```text
9fe00268:  li    a1,1
9fe0026c:  li    a0,7
9fe00274:  jal   digitalWrite
9fe00278:  li    a0,1000
9fe0027c:  jal   delay
9fe00280:  li    a0,7
9fe00284:  li    a1,0
9fe00288:  jal   digitalWrite
9fe00290:  li    a0,1000
9fe00294:  j     delay
```

`pinMode(7, OUTPUT)` is where the **pinmux** is written: it calls
`csi_pin_set_mux`, which writes the mux register (`0x03001150`) to select GPIO,
then sets the direction bit in `SWPORTA_DDR`.

### 3.3 A faster blink

`Blink4/Blink4.ino` is the same sketch with `delay(125)`:

```c
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

```bash
arduino-cli compile --fqbn sophgo:SG200X:duos --build-path build-blink4 Blink4
```

Load and start it exactly as in §3.1, using `Blink4`, `build-blink4/Blink4.ino.elf`
and `blink4.elf` in place of the `Blink` names. A `Blink3` sketch with
`delay(167)` (≈ 3 Hz) works the same way and is even easier to tell apart at a
glance.

Measured with the sampler from section 4:

```text
edges=24 mean half-period 0.1255 s -> 3.98 Hz cycle
```

### Key idea

No OS, no MMU, no syscall — but still a library (`pinMode`/`digitalWrite`). The
pinmux and the register store are done for you.

---

## 4. How `mmap` actually works

### 4.1 Why you cannot just dereference a physical address

In a Linux process, `0x03021000` as a pointer is a **virtual** address. The MMU
translates every access through the process page tables. To touch a physical
address you must first **install a translation** for it. That is what `/dev/mem`
plus `mmap` does:

- `/dev/mem` is a character device that exposes the physical address space
  (`CONFIG_DEVMEM=y` on this kernel).
- `mmap(fd, length, PROT_READ|PROT_WRITE, MAP_SHARED, fd, offset)` asks the
  kernel to map the physical page at `offset` into your virtual address space.

Constraints that matter:

- `offset` must be **page-aligned** (4 KiB). You map a whole page and index into
  it, e.g. map `0x03021000` and use `+0x50` for `EXT_PORTA`.
- MMIO must be accessed with **`volatile` 32-bit loads/stores** and no compiler
  reordering. A plain C pointer to a cached page will not behave.

### 4.2 Read path: the sampler

`sampler.py` maps the GPIO page, samples `EXT_PORTA` bit 18, and computes the
frequency from the edge times.

```python
import mmap, os, struct, time

GPIOB_BASE = 0x03021000
DURATION = 3.0

f = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
g = mmap.mmap(f, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=GPIOB_BASE)


def bit18():
    g.seek(0x50)
    return (struct.unpack("<I", g.read(4))[0] >> 18) & 1


prev, t0, edges = bit18(), time.time(), []
while time.time() - t0 < DURATION:
    v = bit18()
    if v != prev:
        edges.append(time.time())
        prev = v
    time.sleep(0.001)

half = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
m = sum(half) / len(half)
print("edges=%d mean half-period %.4f s -> %.2f Hz cycle" % (len(edges), m, 1 / (2 * m)))
```

```bash
scp sampler.py debian@10.42.0.1:/tmp/sampler.py
ssh debian@10.42.0.1 'sudo python3 /tmp/sampler.py'
```

With the RT core running an image, this is the ground truth:

```text
edges=24 mean half-period 0.1255 s -> 3.98 Hz cycle
```

### 4.3 Write path: a userspace blinker in C

`mmap_blink.c` maps the mux and GPIO pages, selects GPIO, sets the direction,
and toggles the data bit. `volatile` is essential.

```c
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

#define PAGE 0x1000UL
#define MUX_BASE   0x03001000UL
#define GPIOB_BASE 0x03021000UL
#define BIT18 (1u << 18)

int main(void) {
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("open"); return 1; }

    volatile uint32_t *mux = mmap(NULL, PAGE, PROT_READ | PROT_WRITE,
                                  MAP_SHARED, fd, MUX_BASE);
    volatile uint32_t *g = mmap(NULL, PAGE, PROT_READ | PROT_WRITE,
                                MAP_SHARED, fd, GPIOB_BASE);
    if (mux == MAP_FAILED || g == MAP_FAILED) { perror("mmap"); return 1; }

    volatile uint32_t *muxreg = mux + 0x150 / 4;  /* VIVO_D3 function select */
    volatile uint32_t *dr  = g + 0x00 / 4;         /* SWPORTA_DR */
    volatile uint32_t *ddr = g + 0x04 / 4;         /* SWPORTA_DDR */

    *muxreg = (*muxreg & ~0x7u) | 0x3u;   /* select GPIO */
    *ddr |= BIT18;                         /* output */

    for (int i = 0; i < 25; i++) {         /* ~5 s at 5 Hz */
        *dr |= BIT18;
        usleep(100000);
        *dr &= ~BIT18;
        usleep(100000);
    }
    *dr &= ~BIT18;
    return 0;
}
```

Cross-compile (host) and run on the board:

```bash
riscv64-linux-gnu-gcc -static -O2 -o mmap_blink mmap_blink.c
scp mmap_blink debian@10.42.0.1:/tmp/mmap_blink
```

```bash
ssh debian@10.42.0.1 '(sudo /tmp/mmap_blink &) ; sleep 0.4; sudo python3 /tmp/sampler.py'
```

```text
edges=30 mean half-period 0.1001 s -> 5.00 Hz cycle
```

The same program printing intermediate state confirms reads and writes are live:

```text
mux=0x3 DDR=0x40000 DR=0 EXT=0xb10052
after setup: mux=0x3 DDR=0x40000
set high: DR=0x40000 EXT=0xb50052 (bit18=1)
set low : DR=0 EXT=0xb10052 (bit18=0)
```

### Caveat: MMIO writes need care

A Python `mmap` write to the GPIO registers was unreliable on this kernel: a
write that should have set bit 18 did not take, and readback was stale. The
identical C program with `volatile` stores worked on every run, and Python's
`os.pwrite` also worked. For MMIO writes prefer C with `volatile` (or
`libgpiod`); the Python read-only sampler is fine.

### The pivot to assembly

`mmap` exists only because Linux userspace runs behind an MMU. The little C906
core runs in **M-mode with no page tables and no PMP**, so it needs no mapping at
all: a load or store to `0x03021000` *is* a physical access. That is the next
section.

---

## 5. Pure assembly

### 5.1 Stage 1 — asm for the data, `pinMode` for setup

`GpioAsm/GpioAsm.ino`:

```c
#define GPIOB_BASE 0x03021000UL
#define LED_BIT    (1u << 18)

void setup() {
  pinMode(7, OUTPUT);  // mux VIVO_D3 -> XGPIOB_18 and set direction
}

static inline void led_high() {
  uint32_t base = GPIOB_BASE;
  uint32_t bit = LED_BIT;
  asm volatile("sw %1, 0(%0)" : : "r"(base), "r"(bit) : "memory");
}

static inline void led_low() {
  uint32_t base = GPIOB_BASE;
  uint32_t bit = LED_BIT;
  asm volatile(
      "lw  t0, 0(%0)\n\t"
      "not t1, %1\n\t"
      "and t0, t0, t1\n\t"
      "sw  t0, 0(%0)"
      : : "r"(base), "r"(bit) : "t0", "t1", "memory");
}

void loop() {
  led_high();
  delay(50);
  led_low();
  delay(50);
}
```

```bash
arduino-cli compile --fqbn sophgo:SG200X:duos --build-path build-gpioasm GpioAsm
riscv-none-elf-objdump -d build-gpioasm/GpioAsm.ino.elf | sed -n '/<_Z4loopv>:/,/^$/p'
```

```text
9fe00274:  03021437   lui  s0,0x3021     # 0x03021000
9fe00278:  000404b7   lui  s1,0x40       # 0x40000
9fe0027c:  00942023   sw   s1,0(s0)      # LED high
9fe00280:  03200513   li   a0,50
9fe00284:  jal  delay
9fe00288:  00042283   lw   t0,0(s0)
9fe0028c:  fff4c313   not  t1,s1
9fe00290:  0062f2b3   and  t0,t0,t1
9fe00294:  00542023   sw   t0,0(s0)      # LED low
```

Note `andi` takes only a 12-bit immediate, so the clear uses a register temp.

### 5.2 Stage 2 — everything raw

`GpioAsmRaw/GpioAsmRaw.ino` writes the pinmux, direction, and data with no
Arduino GPIO calls:

```c
#define PINMUX_VIVO_D3 0x03001150UL
#define GPIOB_DR       0x03021000UL
#define GPIOB_DDR      0x03021004UL
#define LED_BIT        (1u << 18)
#define MUX_GPIO       0x3u

static inline uint32_t raw_read(uint32_t addr) {
  uint32_t v;
  asm volatile("lw %0, 0(%1)" : "=r"(v) : "r"(addr) : "memory");
  return v;
}

static inline void raw_write(uint32_t addr, uint32_t val) {
  asm volatile("sw %1, 0(%0)" : : "r"(addr), "r"(val) : "memory");
}

void setup() {
  uint32_t mux = raw_read(PINMUX_VIVO_D3);
  mux = (mux & ~0x7u) | MUX_GPIO;
  raw_write(PINMUX_VIVO_D3, mux);

  raw_write(GPIOB_DDR, raw_read(GPIOB_DDR) | LED_BIT);
}

void loop() {
  raw_write(GPIOB_DR, raw_read(GPIOB_DR) | LED_BIT);
  delay(50);
  raw_write(GPIOB_DR, raw_read(GPIOB_DR) & ~LED_BIT);
  delay(50);
}
```

```bash
arduino-cli compile --fqbn sophgo:SG200X:duos --build-path build-gpioasmraw GpioAsmRaw
riscv-none-elf-objdump -d build-gpioasmraw/GpioAsmRaw.ino.elf | sed -n '/<_Z5setupv>:/,/^$/p'
```

```text
9fe00258:  lui   a4,0x3001
9fe0025c:  addw  a4,a4,336     # 0x03001150
9fe00260:  lw    a5,0(a4)      # read mux
9fe00264:  and   a5,a5,-8      # clear bits[2:0]
9fe00268:  or    a5,a5,3       # select GPIO
9fe0026c:  sw    a5,0(a4)      # write mux
9fe00270:  lui   a5,0x3021
9fe00274:  addw  a5,a5,4       # 0x03021004 (DDR)
9fe00278:  lw    a4,0(a5)
9fe0027c:  lui   a3,0x40       # 0x40000
9fe00280:  or    a4,a4,a3
9fe00284:  sw    a4,0(a5)      # direction = output
```

### 5.3 Load and measure

```bash
scp build-gpioasm/GpioAsm.ino.elf debian@10.42.0.1:/tmp/gpioasm.elf
ssh debian@10.42.0.1 'sudo cp /tmp/gpioasm.elf /lib/firmware/gpioasm.elf'
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'   # want: offline
ssh debian@10.42.0.1 'echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state'
ssh debian@10.42.0.1 'echo gpioasm.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware'
ssh debian@10.42.0.1 'echo start | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

```bash
ssh debian@10.42.0.1 'sudo python3 /tmp/sampler.py'
```

```text
edges=60 mean half-period 0.0502 s -> 9.97 Hz cycle
```

### Key idea

On the RT core there is no translation to install. `lui`/`addi` build the
physical address, `sw`/`lw` access the register. The only thing `pinMode` did
that matters here is the one-time pinmux and direction setup.

---

## 6. Synthesis

All four layers end at the same place: a 32-bit store to `SWPORTA_DR` bit 18.

| Layer | Runs on | Address translation | Who sets the pinmux | Code that matters | Risk |
|---|---|---|---|---|---|
| `gpioset` | big core, userspace | MMU + kernel driver | pinctrl/`duo-pinmux` | syscall | safe, arbitrated |
| sysfs | big core, userspace | MMU + kernel driver | pinctrl/`duo-pinmux` | syscall | safe, slow |
| `mmap` + C | big core, userspace | MMU + `/dev/mem` mapping | your code | `volatile` store | can corrupt the SoC |
| pure asm | little C906, M-mode | none (physical) | your code | `sw`/`lw` | no isolation at all |

The abstractions differ in **who writes and how safely**, not in what the
hardware does. `digitalWrite(7, HIGH)` and `sw` to `0x03021000` set the same bit.

---

## 7. Cross-links (background)

- [`fishwaldo-arduino.md`](fishwaldo-arduino.md) — building and loading sketches on the RT core.
- [`physical-memory.md`](physical-memory.md) — M-mode, no MMU/PMP, physical access.
- [`gpio-asm.md`](gpio-asm.md) — the two asm sketches in detail.

---

## 8. Appendix: one-time setup

Flash the DuoS image and enable passwordless SSH/sudo (`setup.md`):

```bash
ssh-copy-id debian@10.42.0.1
```

On the board:

```bash
sudo visudo
```

Add:

```text
%sudo   ALL=(ALL:ALL) NOPASSWD: ALL
```

Install `arduino-cli` on the host (example, Linux x86-64):

```bash
curl -fsSL https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Linux_64bit.tar.gz -o arduino-cli.tgz
tar xzf arduino-cli.tgz arduino-cli
sudo mv arduino-cli /usr/local/bin/
arduino-cli version
```

Install the Sophgo board core (downloads the RISC-V toolchain):

```bash
arduino-cli config add board_manager.additional_urls \
  https://github.com/kubuds/sophgo-arduino/releases/download/v0.2.5/package_sg200x_index.json
arduino-cli core update-index
arduino-cli core install sophgo:SG200X
arduino-cli board listall | grep sophgo:SG200X:duos
```

Find the bundled toolchain (for `objdump`/`readelf`):

```bash
ls ~/.arduino15/packages/sophgo/tools/xpack-riscv-none-elf-gcc/*/bin/
```
