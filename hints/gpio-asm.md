# Controlling GPIOs with assembly from an Arduino sketch

**Assessment date:** 2026-09-20
**Board:** Milk-V DuoS (SG2000 / CV181x), little core `cv181x-c906_1` ("RT core")
**Status:** **Verified on hardware.** Both sketches below were built with the
`sophgo:SG200X` core, loaded via remoteproc, and measured at **9.97 Hz** on the
J3 pin 7 LED (Arduino pin 7 = `VIVO_D3` = `XGPIOB_18`).

> Build/load background is in [`fishwaldo-arduino.md`](fishwaldo-arduino.md);
> the M-mode / physical-addressing story is in
> [`physical-memory.md`](physical-memory.md).

## Summary

There is nothing special to "enable" for assembly: the GPIO block is
memory-mapped, so controlling a pin is just a load or store to a fixed physical
address. `digitalWrite()` already compiles down to exactly those instructions —
writing them by hand lets you see the ISA-level mechanics (`lui`/`addi` to
materialize the address, `sw`/`lw` to drive the pin).

The only work beyond the data store is **pinmux** (selecting the GPIO function
on the pad) and **direction** (output vs input). You can either let
`pinMode()` do those once, or write them yourself.

## Register map for the LED (Arduino pin 7)

Pin 7 resolves to `VIVO_D3`, which muxes to `XGPIOB_18` — GPIO bank 1, channel
18. Bank 1 (`DW_GPIO1_BASE`) is at `0x03021000`:

| Register | Address | Meaning |
|---|---|---|
| `SWPORTA_DR` | `0x03021000` | output data (write bit 18) |
| `SWPORTA_DDR` | `0x03021004` | direction (1 = output) |
| `EXT_PORTA` | `0x03021050` | pad input (read-only, the ground truth) |
| pinmux for `VIVO_D3` | `0x03001150` | bits `[2:0] = 3` (`PIN_FUNC_GPIO`) |

The bit for `XGPIOB_18` is `1 << 18` = `0x40000`.

### Where these numbers come from

In the installed core (`~/.arduino15/packages/sophgo/hardware/SG200X/0.2.5/`):

- `variants/duo/variant_soc.h`:
  `PIN_MUX_BASE 0x03001000`, `DW_GPIO1_BASE 0x03021000`.
- `variants/duos/variant_pin_maps.c`:
  - `out_pin_map[7] = VIVO_D3`, `out_pin_func_map[7] = VIVO_D3__XGPIOB_18`.
  - `csi_gpio_pinmap[]` entry `{VIVO_D3, 1, 18, PIN_FUNC_GPIO}` →
    **bank 1, channel 18**.
  - `csi_pin_reg_offset[]` entry `{VIVO_D3, 0xC1C, 0x150}` — the struct is
    `{pin_name, cfg_reg_offset, mux_reg_offset}`, so the **mux** offset is
    `0x150`, i.e. `0x03001000 + 0x150 = 0x03001150`.
- `cores/sg200x/bsp/include/hal/dw_gpio_ll.h`: `SWPORTA_DR` at `+0x00`,
  `SWPORTA_DDR` at `+0x04`, `EXT_PORTA` at `+0x50`.
- `cores/sg200x/bsp/include/hal/hal_pin.h`: the mux field is bits `[2:0]`
  (`PIN_MUX_Msk = 0x7`).

### Generalizing to other pins

For any Arduino pin `N`, `out_pin_func_map[N]` names `XGPIOx_y`. The bank base
is `DW_GPIO0_BASE + x*0x1000`, and the bit is `y`. The mux offset comes from
`csi_pin_reg_offset[]`. A few examples:

| Arduino pin | Pin name | GPIO | Bank base | Bit | Mux offset |
|---|---|---|---|---|---|
| 7 | `VIVO_D3` | `XGPIOB_18` | `0x03021000` | 18 | `0x150` |
| 8 | `UART0_TX` | `XGPIOA_16` | `0x03020000` | 16 | `0x040` |
| 11 | `VIVO_D10` | `XGPIOB_11` | `0x03021000` | 11 | `0x134` |
| 12 | `VIVO_D2` | `XGPIOB_19` | `0x03021000` | 19 | `0x154` |
| 13 | `VIVO_D9` | `XGPIOB_12` | `0x03021000` | 12 | `0x138` |

## Stage 1 — asm data writes, `pinMode()` for setup

`hints/work/GpioAsm/GpioAsm.ino` lets `pinMode(7, OUTPUT)` do the one-time
pinmux and direction, then toggles the pin with explicit asm:

```cpp
#define GPIOB_BASE 0x03021000UL
#define LED_BIT    (1u << 18)

void setup() { pinMode(7, OUTPUT); }

static inline void led_high() {                 // one store
  uint32_t base = GPIOB_BASE, bit = LED_BIT;
  asm volatile("sw %1, 0(%0)" : : "r"(base), "r"(bit) : "memory");
}

static inline void led_low() {                  // read-modify-write
  uint32_t base = GPIOB_BASE, bit = LED_BIT;
  asm volatile(
      "lw  t0, 0(%0)\n\t"
      "not t1, %1\n\t"
      "and t0, t0, t1\n\t"
      "sw  t0, 0(%0)"
      : : "r"(base), "r"(bit) : "t0", "t1", "memory");
}

void loop() { led_high(); delay(50); led_low(); delay(50); }
```

`objdump -d` shows the compiler emitting precisely this — `lui s0,0x3021`
builds `0x03021000`, `lui s1,0x40` builds `0x40000`, then `sw`/`lw`:

```
9fe00274: 03021437   lui  s0,0x3021
9fe00278: 000404b7   lui  s1,0x40
9fe0027c: 00942023   sw   s1,0(s0)      # LED high
9fe00288: 00042283   lw   t0,0(s0)
9fe0028c: fff4c313   not  t1,s1
9fe00290: 0062f2b3   and  t0,t0,t1
9fe00294: 00542023   sw   t0,0(s0)      # LED low
```

Note `andi` only takes a 12-bit immediate, so the clear uses a register temp
(`li`/`not`/`and`) rather than `andi ... , ~bit`.

## Stage 2 — fully raw (pinmux + direction + data)

`hints/work/GpioAsmRaw/GpioAsmRaw.ino` makes no Arduino GPIO calls. It selects
the GPIO function on `VIVO_D3`, sets the direction, then toggles the data bit —
all through `raw_read`/`raw_write` asm helpers:

```cpp
#define PINMUX_VIVO_D3 0x03001150UL
#define GPIOB_DR       0x03021000UL
#define GPIOB_DDR      0x03021004UL
#define LED_BIT        (1u << 18)

static inline uint32_t raw_read(uint32_t addr) {
  uint32_t v;
  asm volatile("lw %0, 0(%1)" : "=r"(v) : "r"(addr) : "memory");
  return v;
}
static inline void raw_write(uint32_t addr, uint32_t val) {
  asm volatile("sw %1, 0(%0)" : : "r"(addr), "r"(val) : "memory");
}

void setup() {
  uint32_t mux = raw_read(PINMUX_VIVO_D3);          // mux VIVO_D3 -> GPIO
  raw_write(PINMUX_VIVO_D3, (mux & ~0x7u) | 0x3u);  // bits[2:0] = 3
  raw_write(GPIOB_DDR, raw_read(GPIOB_DDR) | LED_BIT);
}

void loop() {
  raw_write(GPIOB_DR, raw_read(GPIOB_DR) | LED_BIT);
  delay(50);
  raw_write(GPIOB_DR, raw_read(GPIOB_DR) & ~LED_BIT);
  delay(50);
}
```

`delay()` is still the Arduino timing helper; only the **GPIO path** is raw.

## Build and load

```sh
arduino-cli compile --fqbn sophgo:SG200X:duos \
  --build-path work/build-gpioasm work/GpioAsm

# sanity-check the instruction stream
riscv-none-elf-objdump -d work/build-gpioasm/GpioAsm.ino.elf | grep -A12 '<loop>'
```

Load and start it as in [`fishwaldo-arduino.md`](fishwaldo-arduino.md) step 3:
copy the image into `/lib/firmware`, get the core to `offline` (stop it if it
is `running`), select the file by name, and start it.

```sh
scp work/build-gpioasm/GpioAsm.ino.elf debian@10.42.0.1:/tmp/gpioasm.elf
ssh debian@10.42.0.1 'sudo cp /tmp/gpioasm.elf /lib/firmware/gpioasm.elf'
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'   # want: offline
ssh debian@10.42.0.1 'echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state'
ssh debian@10.42.0.1 'echo gpioasm.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware'
ssh debian@10.42.0.1 'echo start | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

## Live verification

Sample the pad register `EXT_PORTA` (`0x03021050`, bit 18) over `/dev/mem` —
this is the actual pad level, not the Linux GPIO abstraction:

```sh
ssh debian@10.42.0.1 'sudo python3 -' <<'PY'
import mmap, struct, os, time
f = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
g = mmap.mmap(f, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x03021000)
def bit18():
    g.seek(0x50); return (struct.unpack("<I", g.read(4))[0] >> 18) & 1
prev, t0, edges = bit18(), time.time(), []
while time.time() - t0 < 3.0:
    v = bit18()
    if v != prev: edges.append(time.time()); prev = v
    time.sleep(0.001)
hp = [edges[i+1]-edges[i] for i in range(len(edges)-1)]
m = sum(hp)/len(hp)
print("mean half-period %.4f s -> %.2f Hz" % (m, 1/(2*m)))
PY
```

**Observed:** both `GpioAsm` and `GpioAsmRaw` gave
`mean half-period 0.0502 s -> 9.97 Hz` (nominal 10 Hz from `delay(50)`),
distinct from the stock 1 Hz Blink.

### Proving the pinmux write matters

With Stage 2 running, clearing the mux from Linux and restarting the sketch
shows the sketch's raw pinmux write is what enables the pin:

```sh
# stop the remote, force mux bits[2:0] to 0 via /dev/mem, start again
#   mux before      = 0x00000003 (bits[2:0]=3)
#   mux forced to 0 = 0x00000000 (bits[2:0]=0)
#   mux after start = 0x00000003 (bits[2:0]=3)  -> blinks again at 9.97 Hz
```

## Caveats

- **`stop` before every firmware change.** In one observed run, setting the
  firmware and starting while the remote was already `offline` did not actually
  run the new image (its `dmesg` lines appeared, but the core did not execute
  `loop()`); an explicit `stop` followed by `start` fixed it. The reproduction
  attempt was inconclusive, so treat this as a practical rule: always `stop`,
  and if an image appears not to run, `stop`/`start` once more.
- **`volatile` and the `"memory"` clobber.** Without them the compiler is free
  to reorder or elide the stores, since from C's point of view nothing reads
  that address. The `asm volatile` and `"memory"` clobber are load-bearing.
- **Pinmux is SoC-global.** `0x03001150` is shared with Linux. Setting
  `VIVO_D3` to GPIO affects the whole system's view of that pad; don't clobber
  a pad another peripheral is using.
- **No isolation.** The little core is M-mode with no MMU page tables and no
  PMP (see [`physical-memory.md`](physical-memory.md)); these stores go straight
  to physical addresses with no fault if you get the address wrong.
- **Not persistent.** remoteproc is not auto-started; after a reboot the remote
  is `offline` and the stock `c906-mcu.elf` Blink does not run until started.
- **The LED pin is the safe test pad.** Keep raw experiments on `VIVO_D3` or
  another documented-unused pad; arbitrary peripheral writes can wedge the SoC.

## Open questions

- Root cause of the one `offline` → `start` run that booted but did not execute
  `loop()` (race in the remoteproc state machine, or a one-off).
- Whether a pure busy-wait (no Arduino `delay()`) is worth demonstrating, and
  how to calibrate it against `mtime`.
