---
title: "GPUs and the Throughput Machine"
subtitle: "Where the accelerator sits, and whose memory it is — Reference Notes"
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
    footer: "CS 4250 · GPUs and the Throughput Machine — Reference Notes"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Roadmap {.smaller}

**The condensed version. Same arc as the deck, tables and facts only.**

1. The two bets, and Little's Law
2. SIMT and divergence
3. The inverted hierarchy, GTT, occupancy
4. The machine, CU to card
5. PCIe: BARs, topology, the wall
6. Programming costs
7. Numbers and sources

::: {.notes}
Use this as the revision sheet. Every number that appears in the deck appears
here, marked **quoted** (from a spec sheet) or **derived** (calculated) or
**measured** (from one of our machines).
:::

# Part I — The Two Bets

## The Two Bets {.smaller}

| | CPU core | GPU compute unit |
|---|---|---|
| Area goes to | not stalling | having something else to run |
| Mechanisms | OoO window, predictor, L1/L2 | 64 lanes, 256 KB VGPR, LDS, 4 schedulers |
| Latency hidden by | prediction | concurrency |
| Breaks when | working set > cache | divergence, uncoalesced access |
| Resident threads | 2 (SMT) | 2,560 (40 waves × 64) |

::: {.notes}
Same transistors, opposite bet. Every later mechanism hangs off this table.
:::

## The One Equation {.smaller}

> **concurrency = latency × throughput**
> equivalently **threads = latency ÷ work-per-thread**

Worked: 500 cycles of DRAM latency ÷ 4 cycles of work = **125 threads**.

MI50 at full occupancy: 60 CU × 40 waves × 64 lanes = **153,600 threads**.

Same equation sizes: a miss-status holding register file, a DMA descriptor ring,
a PCIe pipeline.

::: {.notes}
The analogue of AMAT. Any system sustaining a rate across a latency needs a
buffer of latency × rate.
:::

## Four Attempts at a Throughput Machine {.smaller}

| | SIMD width | Threads per issue slot | Outcome |
|---|---|---|---|
| Itanium (2001) | 3-wide VLIW | 1 | lost — no parallelism to fill the width |
| SPARC T2 (2007) | 1 (scalar) | 8 | lost — too narrow to matter |
| Knights Landing (2016) | 32 (2 × AVX-512) | **2** | lost — wide, nothing to hide latency with |
| GPU (2006–) | 16–32 | **10–16** | **won** |

Each failure got one axis right. KNL got both axes and forgot the **depth** — and
it was also the one that kept x86 compatibility, which proves compatibility was
never the problem.

**The examinable claim:** thread depth per issue slot is the design, and
`threads = latency ÷ work` is the arbiter.

## Archaeology {.smaller}

*Not examinable — for the story only.*

| Machine | Year | Why it is here |
|---|---|---|
| **Tera MTA** | 1999 | 128 thread contexts per CPU, **no data caches**. The GPU's latency strategy in a CPU body, 20 years early |
| **Connection Machine CM-2** | 1987 | 65,536 one-bit processors, no branches. The width axis at its limit |
| **Goodyear MPP** | 1983 | 16,384 bit-serial PEs doing Landsat imagery. The GPU's workload, 40 years early |
| **Cell BE** | 2005 | 8 SPEs with local stores and explicit DMA, no caches. "Expose" taken to its limit; shipped in the PS3 |
| **GreenArrays GA144** | 2010 | 144 asynchronous cores and **no clock tree at all** |
| **Groq TSP** | 2020 | Static compiler scheduling, no caches. Itanium's bet, revived and shipping |

::: {.notes}
The through-line: every machine that hides latency with threads eventually looks
like a GPU. Tera got there first and had no graphics workload to carry it.

Groq closes the loop — the same bet that made Itanium a punchline for twenty
years is a product now, because inference is a workload where the schedule is
knowable at compile time. An idea is not good or bad on its own; it is good or
bad *for a workload*.
:::

## The Fabric Ladder {.smaller}

| Boundary | Width | Status |
|---|---|---|
| Shared memory → lanes | ~13,000 GB/s | derived |
| L2 → CU | ~5,000 GB/s | derived |
| HBM2 → L2 (MI50) | 1,024 GB/s | quoted |
| LPDDR5X fabric (vampire) | 256 GB/s | quoted |
| CPU's share of that fabric | **~140 GB/s** | **measured** |
| PCIe 4.0 ×16 | 31.5 GB/s | quoted |
| PCIe 3.0 ×16 | 15.75 GB/s | quoted |
| USB 2.0 (sg2000) | 0.06 GB/s | quoted |

Five orders of magnitude. Every program is limited by the narrowest row it must
cross.

::: {.notes}
The two measured rows are the interesting ones. Everything else is a spec sheet.
:::

# Part II — SIMT

## SIMT {.smaller}

- 64 lanes share **one PC**: one fetch, one decode, one issue, 64 lanes wide.
- Each lane has **private VGPRs**; the **scalar unit** holds what is uniform
  (base address, stride, loop counter).
- An **exec mask** says which lanes are active.
- NVIDIA: warp = 32. AMD GCN/Vega: wavefront = 64. RDNA: either.

**Why not a PC per lane:** 153,600 independent threads need 153,600 instruction
*fetches* per cycle. The bottleneck is instruction supply, not register storage.

::: {.notes}
The fix is fewer PCs, not more. That is the whole of SIMT.
:::

## Divergence {.smaller}

| | Cost |
|---|---|
| CPU mispredicted branch | flush, ~15 cycles, once |
| GPU divergent branch | **tA + tB**, both paths serialised |
| 64-way data-dependent switch | up to **64×** |

Mitigation is architectural: sort, partition, make the common case uniform.

::: {.notes}
This is the GPU's version of a hazard, and the one students meet most often.
:::

## SIMT vs Vectors {.smaller}

| | Vector (RVV, C906) | SIMT |
|---|---|---|
| One instruction, N lanes | yes | yes |
| One PC | yes | yes |
| Programmer sees lanes | **yes** (`vl`, `vsetvl`) | no |
| Per-lane registers | shared vector regs | **private VGPRs** |
| Divergence | explicit masks | automatic, hidden, costly |

::: {.notes}
A vector unit is one thread doing N things. SIMT is N threads that move
together. Different source code.
:::

# Part III — Memory, Inverted

## The Inverted Hierarchy {.smaller}

| Level | CPU (Zen 5) | GPU (MI50) |
|---|---|---|
| Registers | ~2 KB | **15.0 MiB** (60 × 256 KB) |
| L1 | 32–48 KB | 16 KB × 60 = 960 KB |
| L2 | 1 MB | 4 MB |
| Last level | DRAM | HBM2 32 GB |

**The register file is ~4× the L2.** The ordering is the same as a CPU; the
proportions are nothing like one.

::: {.notes}
Registers hold the state of the threads you are not running. That is why they are
the biggest structure in the core.
:::

## Expose or Hide {.smaller}

| | Cache | Scratchpad (LDS) |
|---|---|---|
| Who decides residency | hardware | **software** |
| Policy | LRU/FIFO/random | whatever you wrote |
| Predictability | statistical | **exact** |
| Size (MI50) | 16 KB L1 | **64 KB per CU** |

Total LDS across an MI50: 60 × 64 KB = **3.75 MiB**, against 4 MB of L2.

::: {.notes}
The GPU ships almost as much programmer-managed memory as cache. That is the
"expose" decision expressed in area.
:::

## The Third Tier: GTT {.smaller}

The GPU has **its own page tables**, so the driver can map system pages into the
GPU's address space — the **GTT**.

| Machine | VRAM | GTT path | Gap |
|---|---|---|---|
| celedyr (dGPU) | 4 GiB, ~256 GB/s | system RAM over PCIe, ~16 GB/s | **16×** |
| kraken (dGPU) | 32 GiB HBM2, 1,024 GB/s | over PCIe, ~16 GB/s | **64×** |
| vampire (APU) | 16 GiB carveout, ~256 GB/s | 104 GiB, same fabric | **1×** |
| typhon (HPU) | 96 GiB HBM2e, 2,450 GB/s | over PCIe 4, 31.5 GB/s | **~78×** |

**The gap is the bus.** Unified memory is not a driver feature — it is the absence
of a PCIe link between the two page-table hierarchies.

::: {.notes}
This table is the bridge between Part III and Part V. Same mechanism, four
attachment strategies.
:::

## Occupancy {.smaller}

> **256 KB of VGPR ÷ (64 lanes × 4 B × registers-per-thread)**

| Registers | Wavefronts/CU | Threads |
|---|---|---|
| 25 | 40 | **153,600** |
| 50 | 20 | 76,800 |
| 100 | 10 | 38,400 |
| 255 | 4 | ~15,360 |

Fewer registers → more occupancy → more hiding, but more **spilling**. The dial
has a bad end in both directions.

::: {.notes}
The GPU's AMAT. Every optimisation moves one term.
:::

## Coalescing {.smaller}

| Pattern | Transactions | Efficiency |
|---|---|---|
| 64 consecutive floats | 2 × 128 B | 100% |
| stride 32 floats | 64 × 64 B | **6.25%** |

The wavefront *is* the block size, and the programmer sets it by choosing the data
layout. Array-of-structs vs struct-of-arrays is a 16× decision.

::: {.notes}
The cache deck's block-size tradeoff, moved from the cache designer to the
programmer.
:::

## Half the Memory Is Not for the CPU {.smaller}

Measured on vampire (copy kernel, 0.5 GiB per thread, `threading.Barrier`):

| Threads | 1 | 2 | 4 | 6 | 8 | 12 | 16 |
|---|---|---|---|---|---|---|---|
| GB/s | 48.9 | 83.5 | 113.7 | 123.9 | 129.6 | 137.9 | **140.4** |

Interface is 256 GB/s (256-bit LPDDR5X-8000). The CPU saturates at ~140 GB/s —
about **55%**.

**It is not a channel count, it is a fabric link.** The memory controller has the
full width; the CPU's path to it is narrower. The iGPU sits on the same die as
the controller and gets all of it.

::: {.notes}
Caveat: 140 versus 128 (half of 256) is within 10%, so "half the fabric" is
consistent with the measurement without being proved by it. Say so.
:::

## Unified Memory {.smaller}

On vampire:

| | |
|---|---|
| Physical LPDDR5X | ~128 GiB (109.7 GiB visible + 16 GiB carveout) |
| Carved out as VRAM | **16 GiB** |
| Visible to Linux | 109.7 GiB (115,012,164 kB) |
| GTT aperture | **104 GiB** (111,669,149,696 B) |
| GPU can address | **~120 GiB** |

A ~100 GiB runtime allocation is routine. On celedyr — 4 GiB VRAM, a 256 MiB
window, 16 GB/s — it is not a plan.

::: {.notes}
`mem_info_vis_vram_total` is 16 GiB and BAR Region 0 is 16 GiB. Same number, two
subsystems. That is the BAR slide arriving early.
:::

# Part IV — The Machine

## One CU to a Card {.smaller}

| Level | Contents |
|---|---|
| **CU** | 4 × SIMD16 (64 lanes), 4 schedulers, 256 KB VGPR, 64 KB LDS, 16 KB L1 |
| **Shader array** | 60 CUs, crossbar, 4 MB L2 |
| **Card** | shader array + 8 HBM2 controllers + command processor + 2 copy engines + display + video |

A GPU is a **SoC**, not a big ALU. Five of those six blocks do not compute.

::: {.notes}
The engine-zoo pattern from the power deck: a control core plus fixed-function
dataflow engines. What makes a GPU a GPU is that its engine is programmable.
:::

## Submission and Supervision {.smaller}

**Submitting work:** driver builds a command buffer → writes its address into a
ring → writes a **doorbell** (one MMIO store) → command processor dispatches →
**fence** (a coherent write) signals completion.

**Supervising the machine:** the GPU has its own MCU (RLC / MEC) that runs the
scheduler, handles preemption and power, and answers the doorbell — the same role
the 8051 plays in the sg2000's always-on island.

::: {.notes}
The doorbell is the single most important interface in the machine: one MMIO
write that crosses PCIe.
:::

## Seven Machines, Seven Answers {.smaller}

| Machine | Accelerator | Attach | Memory | Bandwidth |
|---|---|---|---|---|
| sg2000 | none (TPU/VPU/ISP) | on-die | carveouts of 512 MB | 3.73 GB/s |
| celedyr | Polaris 10 · 2016 | PCIe slot | 4 GiB GDDR5 | ~256 GB/s |
| kraken | 4 × Vega 20 · 2018 | 4 PCIe slots | 32 GiB HBM2 each | 1,024 GB/s |
| typhon | 8 × Gaudi2 · 2022 | 2 sockets × 2 switches | 96 GiB HBM2e each | 2,450 GB/s |
| unicorn | RX 7600 · 2023 | PCIe slot | 8 GiB GDDR6 | ~288 GB/s |
| vampire | Radeon 8060S · 2025 | on-die, **still PCIe** | 16 GiB + 104 GiB GTT | ~200 GB/s |
| pegasus | Arc Battlemage · 2025 | PCIe slot | 32 GiB | n/m |

Ordered by year: the **attach** column has barely changed in nine years. The
memory behind it has. `n/m` = not measured.

::: {.notes}
The attach column is the interesting one, not the lane count. And the honest gap
in the bandwidth column is worth more than an invented number.
:::

# Part V — PCIe

## PCI and PCIe {.smaller}

| | PCI (1992) | PCIe (2003) |
|---|---|---|
| Topology | shared parallel bus | **point-to-point lanes** |
| Bandwidth | 133 MB/s (32/33) | 4 → 63 GB/s (×16, Gen1→5) |
| Duplex | half | **full** |
| Unit | bus cycles | **packets (TLPs)** |
| Arbitration | central | none needed |

PCI's two surviving ideas: **configuration space** (the OS enumerates devices) and
**BARs** (devices get windows into the physical address map). That is the opposite
of a device tree.

::: {.notes}
Enumeration versus description. Both solve "where are the registers"; they make
opposite tradeoffs.
:::

## Lanes {.smaller}

| Gen | Per lane | ×16 |
|---|---|---|
| 1.0 | 250 MB/s | 4 GB/s |
| 2.0 | 500 MB/s | 8 GB/s |
| 3.0 | ~1 GB/s | 15.75 GB/s |
| 4.0 | ~2 GB/s | 31.5 GB/s |
| 5.0 | ~4 GB/s | 63 GB/s |

Per direction; PCIe is full duplex. Even Gen5 ×16 is ~16× slower than the HBM2 it
feeds.

::: {.notes}
Marketing quotes GT/s of signalling; payload is lower after encoding.
:::

## The BAR Is a Policy, Not a Generation {.smaller}

| Machine | Card | Year | Memory | BAR | Visible |
|---|---|---|---|---|---|
| celedyr | Polaris 10 | 2016 | 4 GiB | **256 MiB** | 6% |
| unicorn | RX 7600 | 2023 | 8 GiB | **256 MiB** | **3%** |
| pegasus | Arc Battlemage | 2025 | 32 GiB | **32 GiB** | 100% |
| kraken | MI50 | 2018 | 32 GiB | 32 GiB | 100% |
| typhon | Gaudi2 | 2022 | 96 GiB | 128 GiB | 133% |
| vampire | iGPU | 2025 | 16 GiB carveout | 16 GiB | 100% |

unicorn's driver says it directly:

```text
amdgpu 0000:0c:00.0: Detected VRAM RAM=8176M, BAR=256M
```

A 2023 card with the same window as a 2016 one — and, because its memory doubled,
half the visible fraction. pegasus, two years later, ships a full 32 GiB window.
Same bus. The window is a firmware setting.

typhon's BAR sits at `0x11c000000000` — 19 TB up the address space. Only possible
with 64-bit BARs.

::: {.notes}
A BAR is a window, not a copy. Reading a device register is a bus round trip.
And the window size is negotiated, so "how much of the card can the host see" is
a policy question, not a hardware generation.
:::

## Topology and NUMA {.smaller}

| Machine | Topology |
|---|---|
| sg2000 | no bus — all on-die, described by the device tree |
| celedyr | 1 root complex → 1 slot |
| kraken | 4 root complexes → 4 GPUs, no switches |
| typhon | 2 sockets × 2 PCIe switches × 2 Gaudi2 = 8 |

**A shared bus cannot be a tree.** Switches need point-to-point links and
per-packet addressing.

**NUMA is a PCIe topology:** typhon's cards 0–3 are on node 0 and 4–7 on node 1,
distance 20 between nodes. This answers the open question from the multicore
lecture.

::: {.notes}
The multicore notes asked "can we figure typhon out?" — this is the answer, and it
needs the PCIe topology to state it.
:::

## DMA and Coherency {.smaller}

| Method | CPU cost |
|---|---|
| Programmed I/O | a bus round trip **per word** |
| Interrupt-driven | a round trip per word, sleeping between |
| **DMA** | one round trip **per transfer** |

**PCIe does not provide cache coherency.** The CPU's caches do not snoop device
writes. ATS/PRI are optional extensions. So the driver does it by hand:
invalidate before the device writes, flush before it reads.

::: {.notes}
At ~1 µs of round-trip latency, programmed I/O tops out around 4 MB/s regardless
of link speed. DMA is not an optimisation, it is the difference between working
and not.
:::

## The Wall {.smaller}

| | |
|---|---|
| HBM2 (MI50) | 1,024 GB/s |
| PCIe 3.0 ×16 | 15.75 GB/s |
| Ratio | **64×** |

Same 64× as the VRAM-vs-GTT gap in Part III — because it is the same link.

Consequence: **batch**, **keep resident**, never round-trip per element.

Worked: moving 12 MB for the vector add costs 762 µs at 15.75 GB/s; the add costs
12 µs at 1 TB/s. **98% transfer.**

::: {.notes}
Amdahl applied to a link rather than a core.
:::

## The sg2000 Counterfactual {.smaller}

SG2000 TRM, 75,894 lines of text:

| Search | Hits |
|---|---|
| `pcie`, `serdes`, `root complex` | **0** |
| `gpu`, `shader` | **0** |

| Link | Bandwidth |
|---|---|
| USB 2.0 | 60 MB/s |
| 10/100 Ethernet | 12.5 MB/s |
| One PCIe 3.0 ×16 slot | 15,750 MB/s |

Best external link is **262× short** of one slot. Hence the on-die TPU instead of
a GPU.

**If it did have PCIe:** (1) the GPU becomes discoverable and the device tree
shrinks; (2) a 16 GiB BAR does not fit a 4 GB physical map, so you need a paging
window; (3) the C906's caches are not coherent with a PCIe device; (4) a PCIe PHY
and SerDes on a ~3 W part; (5) a 1 GHz dual-issue C906 could not feed a GPU
anyway.

::: {.notes}
Five consequences, each solvable, together describing a different chip. They are
a design point, not a feature list.
:::

## Three Design Points {.smaller}

| | Integrate | Expand | Network the accelerator |
|---|---|---|---|
| Example | sg2000 | celedyr, kraken | typhon (8 × Gaudi2) |
| Bus | none | PCIe | PCIe **plus 48 MACs per card** (two per port) |
| Wins | cost, power, latency | flexibility, scale | scale-out bandwidth |
| Loses | no expansion | 64× wall | complexity, cost |

Gaudi2 answers the wall with Ethernet; NVIDIA with NVLink. Both say the same
thing: **PCIe is not where the data goes.**

::: {.notes}
Measured: `hl-smi -q -d NET` reports 48 MAC addresses per Gaudi2. On a matrix
accelerator. That is the interconnect being the architecture.
:::

# Part VI — Programming

## Costs {.smaller}

| Failure | Cost |
|---|---|
| Divergence | up to 64× |
| Uncoalesced access | up to 16× |
| Low occupancy | latency fully exposed |

All three are **shape** problems, not arithmetic problems.

| Tuning | Effect |
|---|---|
| Registers per thread | occupancy vs spilling |
| Block size | multiple of 64, or you waste lanes |
| Data layout | coalescing — a 16× decision |

::: {.notes}
A GPU is easy to compute on and hard to feed.
:::

## The Spectrum {.smaller}

| | TPU (sg2000) | GPU (MI50) | HPU (Gaudi2) |
|---|---|---|---|
| Programmable | no | **yes** | yes, for training |
| Peak | 0.5 TOPS INT8 | 13.3 TFLOPS FP32 | — |
| Memory | shared with CPU | 32 GiB HBM2 | 96 GiB HBM2e |
| Attach | on-die, no bus | PCIe | PCIe + 48 MACs (two per port) |
| Power | a few W | 300 W | **600 W** |

Where a chip sits on the spectrum is set by **what it must move**, not by what it
must compute.

::: {.notes}
As accelerators get bigger, the distinguishing feature stops being arithmetic and
starts being data supply.
:::

# Part VII — Numbers and Sources

## Numbers {.smaller}

**Measured on our hardware**

| Machine | Measured |
|---|---|
| celedyr | Polaris 10, 4 GiB, **256 MiB BAR**, 24 cores, 4 NUMA nodes |
| unicorn | RX 7600, 8 GiB, **256 MiB BAR**, 16 GB GTT |
| pegasus | Arc Battlemage G31, 32 GiB, **32 GiB BAR**, 256 EUs, 2.8 GHz |
| kraken | 4 × Vega 20 (2 × 64 CU, 2 × 60 CU), 32 GiB each, 32 GiB BAR |
| typhon | 8 × Gaudi2, 96 GiB, 600 W, 128 GiB BAR, NUMA 4/4, 48 MACs |
| vampire | 16 GiB carveout, 104 GiB GTT, 16 GiB BAR, 109.7 GiB, CPU ~140 GB/s |
| sg2000 | 0 PCIe hits in the TRM; USB 2.0 60 MB/s |

**Quoted / derived**

- MI50: 60 CU, 3,840 lanes, 13.3 TFLOPS, 1,024 GB/s HBM2 — vendor.
- Polaris 10 ~256 GB/s, RX 7600 ~288 GB/s — vendor. pegasus bandwidth **not measured**.
- Opteron 6234 ≈ 0.46 TFLOPS — derived from core count, clock, vector width.
- Gaudi2 24 × 100 GbE RoCE, 2.45 TB/s — vendor; the 48 MACs are measured.
- PCIe generations, and Vega 20 CU internals — vendor specs.

::: {.notes}
Keep the three categories distinct. Conflating a spec sheet with a measurement is
how performance claims go wrong.
:::

## Refs {.smaller}

- **AMD** — Vega 20 ISA reference; MI50 datasheet; RDNA / Strix Halo documentation.
- **PCI-SIG** — PCI Express base specification (config space, BARs, TLPs, lanes).
- **Intel / Habana** — Gaudi2 (HL-225) documentation.
- **XuanTie C906** user manual — RVV 0.7.1.
- Commands: `lspci -vv`, `hl-smi`, `rocminfo`, `clinfo`, and the sysfs
  `mem_info_*` files.
- Companion decks: `../memory-slides/`, `../pipelining-slides/`,
  `../power-slides/`, `../boot-slides/`.

::: {.notes}
Every green number in the deck came from one of those commands on a machine the
students can log into.
:::
