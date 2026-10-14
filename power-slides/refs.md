---
title: "Beyond the CPU"
subtitle: "Clocks, Power, DMA, and the Engines — Reference Notes"
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
    footer: "CS 4250 · Beyond the CPU — Reference Notes"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Roadmap {.smaller}

**The CPU is a small part of the die.**

1. Clocks — PLLs and the clock tree
2. Power — domains, reset, the always-on island
3. Data movement — DMA
4. Memory — carveouts, ION, cache
5. The engines (quick) — TPU, VPU, ISP, IVE
6. Synthesis and lab ladder

::: {.notes}
The condensed version. Same arc as the deck, tables and facts only.
:::

# Part I — Clocks

## Two Inputs, Eight PLLs {.smaller}

| Input | Freq | Feeds |
|---|---|---|
| `XTAL_XIN` | 25 MHz | all PLLs, `clk_xtal_*` |
| `RTC_XIN` | 32.768 kHz | the always-on RTC |

| PLL | Preset | Type | PLL | Preset | Type |
|---|---|---|---|---|---|
| `FPLL` | 1500 MHz | int | `APLL` | 1050 MHz | int/frac |
| `MPLL` | 1000 MHz | int/frac | `CAM0PLL` | 1050 MHz | int/frac |
| `TPLL` | 1400 MHz | int/frac | `CAM1PLL` | 1025 MHz | int/frac |
| `MIPIMPLL` | 900 MHz | int | `DISPPLL` | 1200 MHz | int/frac |

PLL names are **roles**: FPLL = CPU/AXI fabric, TPLL = TPU, APLL = audio,
CAMxPLL = camera, DISPPLL = display.

## The Tree {.smaller}

```text
25 MHz XTAL ─► FPLL 1500 ─┬─ /2 ─► clk_a53        750 MHz
                          ├─ /3 ─► clk_cpu_axi0   500 MHz
                          ├─ /3 ─► clk_tpu        500 MHz
                          ├─ /5 ─► clk_axi4       300 MHz
                          └─ /5 ─► clk_axi6       100 MHz
```

Shape: **XTAL → PLL → mux → divider → leaf**. ~90 leaf clocks (TRM Table 8.4).

| Clock | Parent/div | Rate |
|---|---|---|
| `clk_a53` | fpll/2 | 750 MHz |
| `clk_cpu_axi0` | fpll/3 | 500 MHz |
| `clk_tpu` | fpll/3 | 500 MHz |
| `clk_axi4` | fpll/5 | 300 MHz |
| `clk_axi6` | fpll/15 | 100 MHz |
| `clk_spi` | fpll/8 | 187.5 MHz |
| `clk_pwm_src` | fpll/10 | 150 MHz |

## PLL Math and the Three Knobs {.smaller}

`VCO = REF x Div_sel / Pre_div_sel`; `FOUT = VCO / Post_div_sel`.
`PLL_VCO` must land in 800–2500 MHz; loop filter constraint
`0.2 < 1.84(1+Mode)(1+Ictrl)/2/Div_sel ≤ 0.35`.

**Retune order:** park consumers on XTAL/other PLL → write `*_pll_csr` → clear
`*_pll_pwd`.

Per-leaf knobs (TRM §8.5):

| Knob | Register | Base + offset |
|---|---|---|
| Gate | `clk_en_0..4` | `0x0300_2000` + `0x000..0x010` |
| Divide | `div_clk_<name>` | — |
| Bypass | `clk_byp_0/1` | `0x0300_2000` + `0x030/0x034` |

## Key Idea {.smaller}

> The clock tree is **programmable**, and a block's clock is part of its
> **interface**.

- Gate a clock → the block reads **0** (the I2C-deck surprise).
- Runtime PM = clock gating + power gating.

# Part II — Power

## Domains and Reset {.smaller}

| Domain | Contents |
|---|---|
| **Active** | CPUs, fabric, most peripherals, DDR |
| **No-die** (`RTCSYS`) | RTC, WDT, ictl, GPIO, SARADC, IRRX, **MCU domain** |
| ├ AO | always-on; never drops while `VDDIO_RTC` is present |
| └ MCU | 8051 + 8 KB SRAM, timers, SPI-NOR, mailbox, I²C, UART |

| Reset level | Scope | Trigger |
|---|---|---|
| L1 | power-on | POR, overheat, watchdog |
| L2 | hard reset | watchdog, `RSTN` pin |
| L3 (`RSTGEN @ 0x0300_3000`) | soft reset | software |

`SOFT_RSTN_0..3` (`+0x000..0x00c`), active-low, sticky. Module must be idle first.

## The RTC: Root Power Controller {.smaller}

`RTC_CORE @ 0x0502_6000`, runs off 32.768 kHz, always alive.

```text
ST_ON ⇄ ST_SUSP        (req_suspend / wake)
ST_ON → ST_OFF         (req_shdn)
ST_ON → ST_PWR_CYC     (req_pwr_cyc)
ST_ON → ST_WARM_RESET  (req_warm_rst)
```

State readable: `rtc_fsm_st` = `RTC_CTRL_STATUS0[29:26]`.

## Request + Enable {.smaller}

`RTC_CTRL0 @ 0x0502_5008` (unlock: `0x0502_5004 = 0xAB18`):

| Bit | Request | Enable (in `RTC_CORE`) |
|---|---|---|
| 7 | `req_suspend` | `RTC_EN_SUSPEND_REQ` |
| 0 | `req_shdn` | `RTC_EN_SHDN_REQ` |
| 3 | `req_pwr_cyc` | `RTC_EN_PWR_CYC_REQ` |
| 4 | `req_warm_rst` | `RTC_EN_WARM_RST_REQ` |
| 5/6 | wdg rst sw/hw | `RTC_EN_WDG_RST_REQ` |
| 1/2 | thermal sw/hw | `RTC_EN_THM_SHDN` |

**Suspend flow:** `RTC_PG_REG=0` (park DDR I/O) → set `RTC_EN_PWR_WAKEUP` →
`req_suspend=1` → (off) → on wake `RTC_PG_REG=1` → re-init DRAM.

Wake sources: `PWR_WAKEUP0/1`, `PWR_ON`, `PWR_BUTTON1`, `PWR_VBAT_DET`, RTC alarm.

## Board Rails and the 8051 {.smaller}

`PWR_SEQ0..3` (timing in `RTC_UP_SEQ*` / `RTC_DN_SEQ*`) drive the board regulators
(Duo S: SEQ1 → 0.9/1.8 V MIPI, SEQ2 → 3V3, SEQ3 → 1.35 V).

**The 8051** (TRM ch. 14): 8-bit, 25–300 MHz, in the MCU domain, ~200 µA idle,
meant to be the always-on supervisor.

> **Capability ≠ usable:** our images hold it **in reset**, ship no firmware, have
> no driver, and its I/O is the `PWR_*` nets. Four CPUs on the die; we use three.

# Part III — Data Movement

## Three Ways to Move a Byte {.smaller}

| Mechanism | CPU cost |
|---|---|
| Programmed I/O | 1 load + 1 store **per word** |
| Interrupt-driven | worse — trap overhead per word |
| DMA | ~0 — **per descriptor** |

## The DMAC {.smaller}

`snps,dmac-bm`, base **`0x0433_0000`**, TRM ch. 11.

- 8 channels, priorities, `RAM↔RAM`, `RAM↔device`, `device↔device`
- configurable burst; block + single; hardware linked list (`LLP`)
- reaches `UART0–4`, `I²C0–4`, `SPI0–3`, `SPI_NAND`, `I2S0–3`
- clock: `CLK_EN_1[1]`; reset: `REG_SOFT_RESET_X_SDMA_INIT`

**Request lines** (TRM Table 9.1, 42 total) are assigned per channel via
`sdma_dma_ch_remap0/1` + an update bit. One line per channel; no sharing.

## Descriptor Fields {.smaller}

`CHx_CTL @ +0x118`:

| Field | Bits |
|---|---|
| `SRC_TR_WIDTH` / `DST_TR_WIDTH` | 10:8 / 13:11 |
| `SRC_MSIZE` / `DST_MSIZE` | 17:14 / 21:18 |
| `TT_FC` | 34:32 |
| `ShadowReg_Or_LLI_Valid`, `LLI_Last` | — |

`src_burst_bytes = SRC_MSIZE * (SRC_TR_WIDTH/8)`;
`block_bytes = BLOCK_TS * (SRC_TR_WIDTH/8)`.

**Basic:** `SRC/DST_MULTBLK_TYPE=0`, `TT_FC=0`, write `SAR/DAR/BLOCK_TS/CTL`,
`ChEnReg=1`, poll `BLOCK_TFR_DONE`, `ChEnReg=0`.

**Linked list:** `MULTBLK_TYPE=3`, `CHx_LLP` = first node; last node clears
`LLI_Last`.

## Coherency {.smaller}

DMA bypasses the cache → the classic stale-data bug. Kernel fixes it with
`dma_map_*` / `dma_sync_*`. Bare metal must do cache maintenance by hand.

The little C906 is **not coherent** with the Linux core (`physical-memory.md`).

# Part IV — Memory

## Carveouts {.smaller}

| Carveout | Purpose |
|---|---|
| `FREERTOS` (top 2 MB) | C906L window |
| `monitor` | OpenSBI |
| `ION` (~74 MB) | multimedia heap |
| `bootlogo` / framebuffer | boot logo |
| `rproc` / `vdev0*` | remoteproc + rings (arduino) |

**ION:** physically-contiguous, DMA-able buffers shared between engines with
**zero copies** (sensor → ISP → VPSS → encoder).

**Three address models over one DRAM:** virtual (Linux), physical (little core),
DMA (engines).

# Part V — Engines

## The Zoo {.smaller}

| Engine | Compatible | Does |
|---|---|---|
| TPU | `cvitek,tpu` | 0.5 TOPS INT8 — **lab later** |
| VPU | `cvitek,asic-vcodec` | H.264/H.265 |
| JPU | `cvitek,asic-jpeg` | JPEG |
| ISP/VI | `cvitek,vi`,`cvitek,cif` | camera — **later deck** |
| VPSS | `cvitek,vpss` | scale/crop |
| IVE | `cvitek,ive` | image ops |
| DWA | `cvitek,dwa` | dewarp |
| RGN | `cvitek,rgn` | OSD overlay |

Engines are **chained**, DMA-fed, sharing ION buffers. The CPU is the conductor.

# Part VI — Synthesis

## Lab Ladder {.smaller}

1. Read `clk_summary`; identify CPU/DDR/TPU/SPI clocks.
2. Find a gated clock; explain why its registers read 0.
3. Read `/sys/class/thermal/thermal_zone*/temp`.
4. DMA benchmark (`dmatest`, or a hand-written descriptor via `/dev/mem`).
5. *(optional)* 8051 mailbox hello — ≤8 KB SDCC firmware.

## Open Questions to Verify on the Board {.smaller}

- Does `/sys/kernel/debug/clk/clk_summary` exist? Is a clk driver registered?
- Is `CONFIG_CPU_FREQ` present on `duos`/`oz64`? (It is in `maixcam2`/`nanokvmpro`.)
- Is the DMAC registered with dmaengine? (`ls /sys/class/dma`)
- Is `CONFIG_DMATEST` set? (not seen in the defconfigs)

## Refs {.smaller}

- TRM ch. 7 (reset), ch. 8 (clock), ch. 11 (DMA), ch. 5–6 (power/RTC), ch. 14 (8051).
- `boot-slides/`, `i2c-slides/`, `hints/physical-memory.md`, `hints/8051-mcu.md`.
