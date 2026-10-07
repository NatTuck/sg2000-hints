---
title: "I²C: Two Wires, Many Chips"
subtitle: "From a serial protocol to an OLED on the SG2000 / Pine64 Oz64 — Reference Notes"
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
    footer: "CS 4250 · I²C on the SG2000 — Reference Notes"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Roadmap {.smaller}

**Protocol**

1. Buses, serial vs parallel, synchronous vs asynchronous
2. What I²C is for; open-drain + pull-ups; addressing
3. START/STOP, address/ACK, repeated START, clock stretching, arbitration

**Platform**

4. SG2000 DesignWare controllers; pinmux vs controller
5. The Oz64 header mapping and the A5/A6 pinmux trap
6. Clock gating: why userspace raw registers fail

**Device & Code**

7. SSD1306: control bytes, GDDRAM, init
8. One protocol, four layers (C); verified vs reasoned

::: {.notes}
Condensed companion. Each slide is one idea with the minimum facts to rebuild
the argument.
:::

# Part I — The Protocol

## Buses and Framing {.smaller}

- A **bus** shares wires among devices; **addressing** selects the listener.
- **Serial > parallel** at modern clocks (skew/cost); I²C is the low end.
- **Synchronous** (I²C/SPI) ships a **clock**; **asynchronous** (UART) does not.
- A serial protocol must define: framing, addressing, direction, ACK, speed,
  sharing (arbitration), and stretching.

::: {.notes}
Every later slide answers one of these seven.
:::

## I²C at a Glance {.smaller}

| | |
|---|---|
| Wires | **SCL** (clock) + **SDA** (data), half-duplex |
| Topology | multi-drop; master/slave; multi-master allowed |
| Addressing | 7-bit (112 usable), 10-bit extension |
| Speed | 100 k / 400 k / 1 M / 3.4 M |
| Typical devices | sensors, EEPROM, RTC, expanders, ADCs, **SSD1306 OLED** |

- Our panel: **7-bit `0x3C`**; on the wire the write frame is **`0x78`**
  (`0x3C << 1`, same on every bus).

::: {.notes}
0x3C vs 0x78 is the single most common OLED confusion. Pass 0x3C; the wire shows
0x78.
:::

## Open-Drain + Pull-Ups {.smaller}

- Both lines are **open-drain**: a device pulls low or **releases**; pull-up
  resistors make a released line **high**.
- Result: a **wired-AND** — low wins. Idle = both high.
- No contention by construction; enables **multi-master arbitration**.
- Speed is limited by **rise time** through Rp × bus capacitance.

::: {.notes}
Everything distinctive about I²C — sharing, arbitration, stretching — is a
consequence of open-drain.
:::

## The Frame {.smaller}

```text
 [S][ A6..A0 ][R/W][A] [ D7..D0 ][A] [ D7..D0 ][A] ... [P]
      address byte      data byte       data byte
 S = START (SDA falls while SCL high)
 P = STOP  (SDA rises while SCL high)
 A = ACK   (receiver pulls SDA low on 9th clock)
```

- MSB first, 9 clocks per byte (8 data + ACK).
- Data changes only while SCL is low; sampled while SCL is high.
- **Repeated START** changes direction without releasing the bus.
- **Clock stretching**: a slave holds SCL low when it needs time.
- **Arbitration**: transmitters compare SDA to what they sent; a mismatch means
  they lost and back off.

::: {.notes}
Recite the frame from memory; it is the whole protocol.
:::

# Part II — The Platform

## SG2000 I²C {.smaller}

- Five **Synopsys DesignWare** controllers: `0x04000000 … 0x04040000`
  → Linux `i2c-0 … i2c-4`.
- Key registers: `IC_CON`(0x00), `IC_TAR`(0x04), `IC_DATA_CMD`(0x10),
  `IC_ENABLE`(0x6C), `IC_STATUS`(0x70), `IC_TX_ABRT_SOURCE`(0x80).
- Linux view: `/dev/i2c-N`, `i2cdetect`, `ioctl(fd, I2C_SLAVE, 0x3C)`.
- **Two blocks**: the **controller** (protocol engine) and the **pad mux**
  (`0x03001000`, tools `cvi-pinmux`/`duo-pinmux`).

::: {.notes}
Controller ≠ pin. This distinction drives the next two slides.
:::

## The Oz64 Header and the Pinmux Trap {.smaller}

| Header pin | Pad | IIC3 | IIC4 |
|---|---|---|---|
| 1 | — | 3V3 | 3V3 |
| **3** | `XGPIOB[20]` | **IIC3_SDA** | IIC4_SCL |
| **5** | `XGPIOB[21]` | **IIC3_SCL** | IIC4_SDA |
| 9 | — | GND | GND |

- The connector's printed `I2C1_*` names are generic RPi symbol labels — ignore.
- FSBL booted with **IIC3 on pads A5/A6** (not the header). Enabling IIC3 was not
  enough; the fix:

```bash
cvi-pinmux -w IIC3_SCL/XGPIOA_5 ; cvi-pinmux -w IIC3_SDA/XGPIOA_6
duo-pinmux -w B20/IIC3_SDA      ; duo-pinmux -w B21/IIC3_SCL
i2cdetect -y -r 3      # -> 3c
```

::: {.notes}
Two pad groups on one controller = broken bus. Freeing the default pads fixed it.
:::

## Clock Gating {.smaller}

- With the kernel driver bound, a userspace mmap of `0x04030000` reads
  `IC_STATUS = 0` — the block's **clock is runtime-gated** when idle.
- Therefore:
  - Linux userspace raw registers are not usable without waking the block;
  - use **i2c-dev** (ask the kernel) or **bit-bang GPIO** (always clocked);
  - the little core must **ungate the IIC clock** before its raw driver runs.
- Also on this Oz64 image: **no `remoteproc`** (no `cv181x-c906_1` DT node, only
  `rtos_cmdqu`), so little-core images build but do not load here.

::: {.notes}
Memory-mapped ≠ accessible. The clock is part of the interface.
:::

# Part III — Device and Code

## SSD1306 {.smaller}

- 128×64 mono, 1 bpp, I²C, **0x3C**.
- After the address byte, a **control byte**: `0x00` = command, `0x40` = data.
- GDDRAM = **1024 bytes**, 8 pages × 128 columns, bit 0 = top of page.
- Init = fixed command list (`0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0x00,0x40,0x8D,0x14,
  0x20,0x00,0xA1,0xC8,0xDA,0x12,0x81,0xCF,0xD9,0xF1,0xDB,0x40,0xA4,0xA6,0x2E,0xAF`).
- Flush = set window (`0x21 0 127`, `0x22 0 7`) then stream 1024 `0x40` bytes.

::: {.notes}
The entire device layer is the two control bytes plus a 1 KB buffer.
:::

## One Protocol, Four Layers {.smaller}

| Rung | Mechanism | Status |
|---|---|---|
| Linux `i2c-dev` | kernel driver, `/dev/i2c-3` | **verified** |
| Linux raw mmap | bit-bang B20/B21 | **verified** |
| Arduino bit-bang | MMIO on the C906L | built (no remoteproc on image) |
| Arduino `Wire` | vendor `csi_iic` | reasoned — pin map does not fit |
| FreeRTOS (DesignWare) | MMIO + task + clock enable | reasoned |
| FreeRTOS (bit-bang) | MMIO bit-bang + task | reasoned |

- `examples/i2c-c/ssd1306.h` is transport-agnostic; each rung supplies a
  `oled_write_fn`. The upper layer is identical everywhere.

::: {.notes}
`Wire3` (IIC3) is unimplemented on `duos`; `Wire4` uses IIC4 with SDA/SCL swapped
versus the Oz64 header wiring.
:::

## Verified vs Reasoned {.smaller}

- **Verified**: command + observed result (panel refreshed, `3c` detected, pads
  restored).
- **Built**: cross-compiled and linked for the target, but blocked by the image
  (missing remoteproc) — entry `0x9fe00000`.
- **Reasoned**: teaching code; the reasoning and the required steps are shown,
  but it was not executed.

> State which is which. It is the difference between an experiment and a claim.

::: {.notes}
The platform surprises are the most transferable lessons: pinmux, clock gating,
remoteproc availability, variant pin maps.
:::

## Lab Ladder & Discussion {.smaller}

1. `i2cdetect -y -r 3`; explain `-r` vs `-y`.
2. `./linux-i2c-dev /dev/i2c-3 "text"`; modify `ssd1306.h`.
3. `./linux-mmap-bitbang "text"`; compare on an analyser.
4. Break the pinmux; predict the failure.
5. (DuoS image) load the Arduino sketch via remoteproc.

**Discuss:** why data changes only while SCL is low; why the clock is open-drain;
when bit-banging is the right call; where the driver/transport boundary belongs.

::: {.notes}
Close on judgment and abstraction boundaries.
:::
