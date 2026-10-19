---
title: "Caches and the Memory Hierarchy"
subtitle: "The Stock Story and Four Cores — Reference Notes"
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
    footer: "CS 4250 · Caches and the Memory Hierarchy — Reference Notes"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Roadmap {.smaller}

**The condensed version. Same arc as the deck, tables and facts only.**

1. Technologies — why a hierarchy is forced
2. Locality — the load-bearing assumption
3. AMAT — the equation
4. Mechanisms — search, block size, evict, write
5. Our four cores
6. Numbers and sources

::: {.notes}
Use this as the revision sheet. Every number that appears in the deck appears here,
with a note on whether it is quoted or derived.
:::

# Part I — Technologies

## Four Ways to Store a Bit {.smaller}

| | Devices per bit | Access | Volatile | Write endurance |
|---|---|---|---|---|
| **SRAM** | 6 transistors | 1–10 ns | yes | unlimited |
| **DRAM** | 1 transistor + 1 capacitor | ~80 ns | yes | unlimited |
| **Flash** | 1 floating gate | 10–100 µs | no | ~10³–10⁵ |
| **Disk** | magnetic domain | 10 ms | no | unlimited |

::: {.notes}
Six devices versus two — roughly 20× density, which is the entire reason DRAM exists.
:::

## Mechanism Notes {.smaller}

- **SRAM cell**: two cross-coupled inverters = bistable loop; two access transistors.
  Read = precharge bitlines high, raise wordline, cell pulls one bitline down, sense amp
  resolves. **Non-destructive.** Write = drive bitlines hard and **overpower** the loop.
  Access-transistor sizing is a compromise: strong enough to write, weak enough that a
  precharged bitline does not corrupt a stored 0 on read.
- **Multiported SRAM**: *N* wordlines, *2N* bitlines → wire area **O(N²)**.
- **DRAM**: capacitor leaks → **refresh every few ms**; read shares charge →
  **destructive**, must write back; tiny swing → **sense amplifier per bitline**.
- **Flash**: trapped charge in a floating gate; non-volatile; write damages the oxide.

::: {.notes}
The O(N²) wire cost is why "just make the L1 bigger" is not free, and why register
files are tiny and multiported while caches are large and single-ported.
:::

## Size Is a Fundamental Limit {.smaller}

> Bigger array → longer bitlines → more capacitance → smaller voltage swing → longer
> to sense.

Latency grows with capacity **by physics**. There is no process node at which a 512 MB
SRAM with 1-cycle access appears.

**The 2026 escape hatch:** don't scale the array — stack a die on it.
AMD 3D V-Cache bonds a **64 MB SRAM die** under the compute die: 32 MB on-die L3 +
64 MB stacked = **96 MB** on the Ryzen 7 9850X3D.

::: {.notes}
Packaging, not scaling. The hierarchy got deeper without the array getting wider.
:::

# Part II — Locality

## The Principle {.smaller}

> Access to *X* at time *t* implies access to *X + ΔX* at time *t + Δt* becomes more
> probable as *ΔX* and *Δt* approach zero.

- **Temporal**: ΔX = 0 — same address again soon.
- **Spatial**: Δt = 0 — nearby address soon.

Empirical, not a theorem. Programmers and compilers create it — and can destroy it.

**Working set** *S*: distinct addresses touched in a window Δt. |S| grows with Δt then
**saturates** at the program's true footprint. A cache larger than the saturated working
set sees mostly hits.

::: {.notes}
If programs accessed memory uniformly at random, caches would buy exactly nothing.
:::

## Hierarchy, Ours {.smaller}

| Level | Size | Latency | Managed by |
|---|---|---|---|
| Registers | 1 KB | 0 cycles | compiler |
| L1 I / D | 32 KB / 64 KB | 1–4 cycles | hardware |
| L2 | 128 KB *(A53 only)* | ~10 cycles | hardware |
| L3 | **none** | — | — |
| DRAM | 512 MB DDR3 | 60–100 cycles | OS + hardware |
| NAND / eMMC | 16 GB – 2 TB | 50–100 µs | OS |

Each level is a cache for the level below. **Expose** (scratchpad, ION carveouts) versus
**hide** (caches) — every real system does both.

::: {.notes}
Registers are allocated by the compiler: a replacement policy implemented in software.
:::

# Part III — AMAT

## The Equation {.smaller}

$$\text{AMAT} = \text{HitTime} + \text{MissRatio} \times \text{MissPenalty}$$

Composes: the miss penalty of one level is the AMAT of the next.

$$\text{AMAT} = \text{HT}_1 + \text{MR}_1 \times
  \bigl(\text{HT}_2 + \text{MR}_2 \times \text{Penalty}_{\text{mem}}\bigr)$$

| Core | Hierarchy | AMAT at HR₁ = 0.95 |
|---|---|---|
| C906 | L1 → DDR3 | `2 + 0.05 × 80` = **6.0** |
| A53 | L1 → L2 → DDR3 | `2 + 0.05 × (10 + 0.20 × 80)` = **3.3** |

::: {.notes}
The A53 wins with *smaller* L1 caches, because it has something behind them.
:::

## Required Hit Ratio {.smaller}

Hit 2 cycles, miss 100 cycles:

| Target | Required HR |
|---|---|
| Beat no cache (AMAT < 100) | **2%** |
| AMAT = 10 | **92%** |
| AMAT = 5 | **97%** |

Break-even is just `HitTime / MissPenalty`. A faster hit time makes the cache more
forgiving.

::: {.notes}
MIT's version uses 4 cycles for a hit, giving 4% and 99%. Diminishing returns set up
the associativity curve.
:::

## Derived Numbers — Labelled as Derived {.smaller}

| Quantity | Value | How |
|---|---|---|
| Peak DRAM bandwidth | **3.73 GB/s** | 1866 Mbps × 16 bit |
| One 64 B line at peak | **~17 ns ≈ 17 cycles @ 1 GHz** | 64 B ÷ 3.73 GB/s |
| Random DDR3 latency | **~60–100 cycles** | estimate: CL + tRCD + controller |

::: {.notes}
The 17-cycle figure is a **bandwidth floor**, not a latency. A single random cache line
cannot use peak bandwidth, so the real miss penalty is several times larger. The AMAT
examples use 80 cycles as an illustrative round number, not a measurement.
:::

# Part IV — Mechanisms

## The Two Questions {.smaller}

```text
on each access to A:
    if cache holds the block containing A:  HIT
    else:  choose a victim; fetch the block; place it; return
```

1. **How do we search?** → direct-mapped / set-associative / fully-associative
2. **Whom do we evict?** → replacement policy

Plus, for writes: **when do we write to memory?** → write policy.

::: {.notes}
Everything in this part answers one of these three.
:::

## Three Fields {.smaller}

```text
 31                    14 13        6 5      0
+------------------------+-----------+--------+
|         tag (18)       | index (8) | off (6)|
+------------------------+-----------+--------+
```

| | Direct-mapped | N-way set assoc. | Fully assoc. |
|---|---|---|---|
| Blocks per set | 1 | N | all |
| Comparators | 1 | N | N |
| Conflict misses | many | fewer | **none** |
| Data select | none | N:1 mux | N:1 mux |

The **index bits are not stored** — they are implied by which line you looked in.
Metadata for our 64 KB D-cache: 256 × 4 × 20 bits = **2.5 KB** (≈4% overhead).

::: {.notes}
The address is partly encoded in the location. That is what makes a one-comparator
search possible, and it is the source of conflict misses.
:::

## Block Size {.smaller}

| Block size | Miss rate | Miss penalty | AMAT |
|---|---|---|---|
| too small | high | small | worse |
| **~64 B** | minimum | moderate | **best** |
| too large | low | large | worse |

Optimum ≈ 64 B (MIT slide 28). **Our line is exactly 64 B on both caches** — and on all
four comparison cores.

::: {.notes}
Set by DRAM burst granularity and the spatial locality of real code, not by the cache.
:::

## Misses and Replacement {.smaller}

| Miss type | Cause | Avoidable? |
|---|---|---|
| Compulsory | first touch | no |
| Capacity | working set > cache | no (at that size) |
| **Conflict** | working set fits, maps to too few sets | **yes** |

| Policy | Rule | Cost |
|---|---|---|
| Belady MIN | evict furthest-in-future | optimal, unimplementable; a bound |
| LRU | least recently used | ~log₂(N!) bits; a stack algorithm |
| **FIFO** | longest resident | log₂(N) bits; **not** a stack algorithm |
| Random | — | no state |

**Belady's anomaly**: FIFO with 4 frames can fault *more* than with 3 (9 → 10 faults on
`1 2 3 4 1 2 5 1 2 3 4 5`). LRU cannot do this.

**None of our cores implements true LRU**: C906 = FIFO, A53 = pseudo-random, x86 =
approximation. LRU is the reference, not the implementation.

::: {.notes}
Our C906 uses FIFO on both caches, so it gives up the inclusion guarantee.
:::

## Write Policy {.smaller}

| Policy | On a write | Cost |
|---|---|---|
| Write-through | cache + memory | simple, no dirty bit, every store costs bandwidth |
| Write-behind | buffer, drain later | no stall, still full bandwidth |
| **Write-back** | cache only; memory on eviction | fastest, lowest bandwidth, needs dirty bit |

Write miss: **allocate** (fetch first) or **no-allocate** (write through)?

Dirty bit: WRITE sets it, eviction writes back only if set, fill clears it.
**Consequence: main memory can be stale** — hence cache maintenance instructions, and
hence the DMA coherency problem.

::: {.notes}
Our D-cache is write-back with configurable allocate / no-allocate, plus an adaptive
mode.
:::

# Part V — Our Four Cores

## The Comparison {.smaller}

| | **C906 @ 1 GHz** | **C906 @ 700 MHz** | **A53 @ 1 GHz** | **Ryzen 7 9850X3D** |
|---|---|---|---|---|
| L1 I | 32 KB, 2-way | 16 KB, 2-way | 32 KB, 2-way | 32 KB, 8-way |
| L1 D | 64 KB, 4-way | 16 KB, 4-way | 32 KB, 4-way | 48 KB, 12-way |
| L2 | — | — | 128 KB, 16-way | 1 MB, 16-way |
| L3 | — | — | — | 96 MB |
| Line | 64 B | 64 B | 64 B | 64 B |
| Replacement | FIFO | FIFO | pseudo-random | n/d |
| Prefetch | both | both | n/d | yes |

Associativity **2 → 4 → 8 → 12**. L3 **none → none → none → 96 MB**.

::: {.notes}
`n/d` = not documented in our sources (x86 replacement policy); `—` = level does not
exist. Kept distinct on purpose.

**C906 and A53 have identical L1 geometry:** 2-way instruction, 4-way data, 64-byte
lines. The C906 has the larger D-cache (64 KB vs 32 KB); the A53 has the L2.
:::

## C906 L1 I-Cache — §7.1 {.smaller}

| Property | Value |
|---|---|
| Size | 8 / 16 / 32 / 64 KB, hardware-configurable |
| Associativity | **2-way** |
| Line | 64 B |
| Indexing | **VIPT** |
| Read width | 32 bits |
| Refill width | 128 bits |
| Replacement | **FIFO** |
| Maintenance | whole-cache and single-line invalidate |
| Prefetch | `MHINT.IPLD`, **same page only** |

Plus: BHT 8/16 Kb GSHARE; BTB 16-entry fully associative; RAS 4 levels deep.

::: {.notes}
The same-page prefetch restriction is a correctness constraint, not a performance one.
:::

## C906 L1 D-Cache — §7.2 {.smaller}

| Property | Value |
|---|---|
| Size | 8 / 16 / 32 / 64 KB, hardware-configurable |
| Associativity | **4-way** |
| Line | 64 B |
| Indexing | **VIPT** |
| Read / write width | 64 / 128 bits |
| Write policy | **write-back**; write-allocate or write-no-allocate |
| Replacement | **FIFO** |
| Prefetch | sequential **and strided** (≤ 16 lines, ± stride) |
| Adaptive write-allocate | after *N* consecutive line writes (`HINT.AMRL1`) |
| Exclusive access | **LR/SC**, local monitor in the D-cache |

::: {.notes}
§7.2.2 adaptive write-allocate: the streaming-store problem solved in hardware.
§7.2.3: SC fails if the D-cache is disabled.
:::

## C906 §7.3 — Cache Operations {.smaller}

**After reset both caches are invalidated and disabled by default.**

| Register | Purpose |
|---|---|
| `mhcr` | enable I/D cache; write-allocate and write-back mode (`shcr` = S-mode read-only mirror) |
| `mcor` | clean-dirty and invalidate |
| `mcins` / `mcindex` / `mcdata0-1` | read cache contents |

| Instruction | Action |
|---|---|
| `DCACHE.CALL` / `CVA` / `CPA` / `CSW` | clean (all / by VA / by PA / by way-set) |
| `DCACHE.IALL` / `IVA` / `IPA` / `ISW` | invalidate |
| `DCACHE.CIALL` / `CIVA` / `CIPA` / `CISW` | clean **and** invalidate |
| `ICACHE.IALL` / `IALLS` / `IVA` / `IPA` | invalidate (`IALLS` broadcasts) |

::: {.notes}
"Invalidate by PA" exists for the DMA case: you know the physical address, not the
virtual one.
:::

## Bit Arithmetic — Derived {.smaller}

Line = 64 B everywhere, so offset = 6 bits.

| Core | Cache | Size | Ways | Sets | index | tag (32-bit addr) |
|---|---|---|---|---|---|---|
| C906 1 GHz | I | 32 KB | 2 | 256 | 8 | 18 |
| C906 1 GHz | D | 64 KB | 4 | 256 | 8 | 18 |
| C906 700 MHz | I | 16 KB | 2 | 128 | 7 | 19 |
| C906 700 MHz | D | 16 KB | 4 | 64 | 6 | 20 |

`sets = size ÷ (ways × line)`. The C906 is RV64, so a full 64-bit address gives a 50-bit
tag; 32-bit addresses are used here for consistency with the rest of the deck.

::: {.notes}
Both 1 GHz caches land on 256 sets / 8 index bits. The 64 KB D-cache buys its capacity
with a fourth way, not with more sets.
:::

## VIPT {.smaller}

Virtual index, physical tag: the set is selected from the virtual address while the TLB
translates in parallel. A physical index would serialise translation and indexing.

**Constraint:** the index must lie inside the page offset.

$$\text{sets} \times \text{line size} \le \text{page size}$$

Our 1 GHz caches: `256 × 64 = 16 KB` against a **4 KB** page. The constraint is
violated, so two index bits would come from the VPN. **Unresolved** — either "VIPT" is
used loosely, or cacheable mappings need ≥16 KB pages, or there is undocumented
anti-aliasing.

::: {.notes}
This is our derivation from two documented facts (cache geometry, page size), not a
claim the manual makes. Flagged as open rather than smoothed over.
:::

# Part VI — Numbers and Sources

## Quoted vs Derived {.smaller}

| Number | Status | Source |
|---|---|---|
| L1 sizes, ways, line size, FIFO | **quoted** | C906 manual §7.1–7.2 |
| VIPT, prefetch, adaptive write-allocate | **quoted** | C906 manual §7.2 |
| Caches disabled at reset | **quoted** | C906 manual §7.3 |
| Core configurations (32/64 KB etc.) | **quoted** | SG2000 / SG2002 TRM |
| A53 L2 = 128 KB | **quoted** | SG2002 TRM §3.1 |
| A53 associativity (2/4-way), pseudo-random | **quoted** | Arm Cortex-A53 TRM (DDI 0500) |
| Zen 5 caches, 96 MB L3 | **quoted** | AMD / Zen 5 microarchitecture tables |
| Set/index/tag counts | **derived** | `sets = size ÷ (ways × line)` |
| 3.73 GB/s, 17 cycles/line | **derived** | 1866 Mbps × 16 bit |
| 60–100 cycle DRAM latency | **estimate** | CL + tRCD + controller |
| AMAT examples (2 / 10 / 80) | **illustrative** | round numbers, not measured |

::: {.notes}
Teach them to ask which column a number came from. The derived and illustrative rows are
where errors live.
:::

## Sources {.smaller}

- **XuanTie C906 User Manual** (openc906), XeLaTeX, 337 pp. §5 MMU, §7 memory
  subsystem. Printed page = PDF page − 17. Text-extractable with `pdftotext`.
- **SG2000 TRM** (920 pp.) and **SG2002 TRM** (841 pp.). Printed page = PDF − 29.
- **MIT 6.004** *Computation Structures*, Spring 2017, lecture 14 — the stock story and
  the AMAT framing.
- **Hennessy & Patterson**, *Computer Architecture* — associativity tradeoffs
  (Fig. 5.9), replacement policies.
- **Arm Cortex-A53 TRM** (DDI 0500) — L1 geometry and replacement policy. Note the
  document is now behind an Arm login.
- **AMD Zen 5** microarchitecture tables; Ryzen 7 9850X3D product page (8 cores,
  96 MB L3, launched 29 Jan 2026).

::: {.notes}
Note: Opteron was discontinued in 2017; AMD's server line is EPYC. Not used in this
deck.
:::
