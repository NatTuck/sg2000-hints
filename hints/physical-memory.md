# DuoS little core (C906) — physical memory access from an Arduino sketch

**Assessment date:** 2026-09-19
**Board:** Milk-V DuoS (SG2000 / CV181x), little core `cv181x-c906_1` ("RT core")
**Status:** **Reasoned from source — not yet board-tested.** The mechanism below is
established from the Arduino core's startup and linker script; the test plan is
outlined but has not been run on hardware.

> Build/load background is in [`fishwaldo-arduino.md`](fishwaldo-arduino.md);
> board prep is in [`setup.md`](setup.md).

## Summary

Yes. A sketch running on the little C906 core has direct physical-address access
to memory and peripherals. The core starts in RISC-V **M-mode with no MMU page
tables and no PMP entries configured**, so every load and store is a physical
access and there is no isolation layer between the sketch and the SoC.

The 2 MB carveout at `0x9fe00000` is where the image is *linked and loaded* — it
is **not** a runtime protection boundary. Nothing stops the running sketch from
forming a pointer to any other physical address.

## Why: M-mode, no MMU, no PMP

`cores/sg200x/bsp/startup/start.S` (shipped with the `sophgo:SG200X` core) is
plain machine-mode startup:

- It programs only M-mode CSRs: `mscratch`, `mie`, `mtvec`, `mstatus`, `mepc`,
  `mbadaddr`, and returns via `mret`.
- It **never writes `satp`**, so no page tables are installed. In RISC-V,
  `satp` governs S/U-mode translation only; M-mode always issues physical
  addresses.
- It **never writes `pmpcfg0..15` / `pmpaddr0..15`**. After reset those entries
  are "off", so M-mode has no PMP restriction.

The only addressing constraint comes from the toolchain flags in `platform.txt`:

```
compiler.c_cpp.flags=-mcmodel=medany -mabi=lp64d -march=rv64imfd_zicsr
```

`medany` limits *PC-relative* references (code and static data) to ±2 GiB. A
constant peripheral or RAM address is still materialized as an absolute
`lui`/`addi` pair, which covers the whole 32-bit physical space, so
`*(volatile uint32_t *)0x03021050` compiles fine even though it is ~2.6 GiB
below the load address.

## What "full access" means — and its limits

**Reachable directly**

- Carveout RAM, e.g. `0x9FEF0000` (used in the `fishwaldo-arduino.md` RAM test).
- Any other DRAM address, including memory Linux owns.
- Peripheral registers, e.g. the pad register `EXT_PORTA` at `0x03021050`
  (bit 18 = `XGPIOB18`, the J3 pin 7 LED) — this is how Blink drives the LED
  without a Linux driver.

**Real caveats**

- **No isolation.** A stray write can corrupt the running Linux kernel, other
  processes, or the FSBL region. There is no MMU fault and no notification to
  the big core — the write simply happens.
- **Shared DDR.** The big core and little core share DRAM; there is no
  arbitration you control.
- **Cache coherency.** The C906 has its own L1 I/D caches and is not cache-
  coherent with the C920 Linux core. A physical address written by the sketch
  can sit dirty in the little core's cache; Linux may read stale data (and vice
  versa). Correct sharing needs cache maintenance (`fence`, `cbo.*` if
  available) or an uncached/device mapping.
- **SoC bus access control.** The CV181x has secure/firewalled regions. Some
  addresses can still be rejected by the fabric; that faults through the
  startup's `trap_entry` → `handle_trap`, it does not silently succeed.
- **PMP from earlier stages.** This startup leaves PMP untouched, so default is
  unrestricted. A locked entry left by an earlier boot stage would persist — not
  expected here, but worth knowing if a probe unexpectedly traps.

## Worked examples

Read a peripheral register (safe; same pad Blink uses):

```cpp
#define EXT_PORTA (*(volatile uint32_t *)0x03021050)
uint32_t pad = EXT_PORTA;          // bit 18 = XGPIOB18
```

Write a physical DRAM address by raw pointer:

```cpp
#define PROBE (*(volatile uint32_t *)0x9FEF0000)
PROBE = 0xC0FFEE42;
```

The compiler emits `lui`/`addi` to build the constant, then a plain load/store —
no translation, no driver, no syscall.

## Test plan (outlined, not run)

Goal: show that a sketch's physical writes to carveout RAM are visible from the
big core, and that a physical peripheral read works. Everything here stays
inside the carveout or touches a pad already known safe, so it cannot corrupt
Linux.

### 0. Prerequisites

As in [`fishwaldo-arduino.md`](fishwaldo-arduino.md): `arduino-cli` with the
`sophgo:SG200X` core, passwordless SSH + NOPASSWD `sudo` to `debian@10.42.0.1`.

### 1. The test sketch

`hints/work/PhysMem/PhysMem.ino`:

```cpp
#define MAGIC_VALUE 0xC0FFEE42UL
#define PROBE_BASE  0x9FEF0000UL

static volatile uint32_t *const probe = (volatile uint32_t *)PROBE_BASE;

void setup() {
  probe[0] = MAGIC_VALUE;   // magic, written once
  probe[1] = 0;             // counter
}

void loop() {
  probe[0] = MAGIC_VALUE;
  probe[1]++;               // increments on the little core
  delay(100);
}
```

`0x9FEF0000` is 1 MB into the 2 MB carveout, above the stack (`0x40000`) and
heap (`0x80000`) that `variants/duos/link.ld` reserves. Confirm from the build's
`.map` that `_end` is below `PROBE_BASE` before trusting it; if not, pick a
higher free address.

### 2. Build

```sh
arduino-cli compile --fqbn sophgo:SG200X:duos \
  --build-path work/build-physmem work/PhysMem

readelf -h work/build-physmem/PhysMem.ino.elf | grep Entry   # 0x9fe00000
grep -E '_end|_stack_top' work/build-physmem/PhysMem.ino.map
```

Sanity-check the constant materialization:

```sh
riscv-none-elf-objdump -d work/build-physmem/PhysMem.ino.elf | grep -A3 '<loop>'
# expect lui/addi building 0x9fef0000, then sw/ld
```

Also confirm the shipped startup has no `satp`/`pmp` writes:

```sh
riscv-none-elf-objdump -d work/build-physmem/PhysMem.ino.elf \
  | grep -Ei 'csrw?[[:space:]]+(satp|pmpcfg|pmpaddr)'   # expect no output
```

### 3. Load via remoteproc

Same manual flow as `fishwaldo-arduino.md` step 3 — get the core to `offline`,
copy the image into `/lib/firmware`, select it by name, then start it:

```sh
scp work/build-physmem/PhysMem.ino.elf debian@10.42.0.1:/tmp/physmem.elf
ssh debian@10.42.0.1 'sudo cp /tmp/physmem.elf /lib/firmware/physmem.elf'
ssh debian@10.42.0.1 'cat /sys/class/remoteproc/remoteproc0/state'   # want: offline
ssh debian@10.42.0.1 'echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state'
ssh debian@10.42.0.1 'echo physmem.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware'
ssh debian@10.42.0.1 'echo start | sudo tee /sys/class/remoteproc/remoteproc0/state'
```

### 4. Observe from the big core

Read the same physical page via `/dev/mem`:

```sh
ssh debian@10.42.0.1 'sudo python3 -' <<'PY'
import mmap, struct, os, time
f = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
m = mmap.mmap(f, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x9FEF0000)
for _ in range(20):
    m.seek(0)
    magic, counter = struct.unpack("<II", m.read(8))
    print("magic=%#x counter=%d" % (magic, counter))
    time.sleep(0.2)
PY
```

**Expected:** `magic=0xc0ffee42`, `counter` increasing ~10/s. That proves the
little core wrote physical DRAM and the big core can see it.

**If `counter` is stuck** but the sketch is running, that is the cache-coherency
caveat in action (the little core's dirty line never reaches DRAM). That result
is itself informative; note it rather than assuming failure.

### 5. Peripheral probe (optional)

A variant of `setup()` that reads `EXT_PORTA` (`0x03021050`) and mirrors bit 18
into `probe[2]` would confirm peripheral physical reads. Keep it to the pad
already known safe from Blink.

### 6. Restore the stock firmware

```sh
ssh debian@10.42.0.1 '
  S=/sys/class/remoteproc/remoteproc0/state
  echo stop | sudo tee $S
  echo c906-mcu.elf | sudo tee /sys/class/remoteproc/remoteproc0/firmware
  echo start | sudo tee $S
  sudo rm -f /lib/firmware/physmem.elf
'
```

## Don't probe outside the carveout (without a reservation)

Probing or writing physical DRAM **outside** the carveout on a live system is
how you corrupt the kernel. If that capability needs to be demonstrated, reserve
the region first (a `reserved-memory`/`memmap=` carveout that Linux will not
use) or stop Linux entirely. The test above deliberately stays inside the
carveout.

## Open questions

- Whether the C906 L1 caches are enabled by this startup (would explain either
  coherent or stale `/dev/mem` reads; the test distinguishes them).
- Whether any SoC firewall actually rejects non-carveout DRAM from the little
  core, or whether it is truly unrestricted.
- Whether `cbo.clean`/`cbo.flush` are available on this C906 to make explicit
  coherency possible from the sketch.
