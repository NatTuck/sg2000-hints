---
title: "SG2000 Boot Sequence"
subtitle: "Reference Notes"
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
    footer: "CS 4250 · Milk-V Duo S Boot Sequence — Reference"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Lecture Roadmap {.smaller}

**Motivation & Architecture**

1. The chicken-and-egg problem of bootstrapping
2. The SG2000 memory hierarchy
3. The RISC-V privilege hierarchy
4. Heterogeneous cores on the Duo S

**Stage-by-Stage Boot Pipeline**

5. Stage 0 — Power-On Reset & BootROM
6. Stage 1 — First-Stage Bootloader (FSBL / BL2)
7. Stage 2 — OpenSBI
8. Stage 3 — Das U-Boot
9. Stage 4 — Linux kernel bring-up
10. Stage 5 — User space

**Discussion** — high-yield questions for students

::: {.notes}
Frame the lecture: a single concrete SoC lets us trace every layer of the
boot chain, from hard-etched mask ROM to `sret` into a shell prompt.
:::

# Part I — Motivation & Architectural Overview

## Why Is Booting Hard? {.smaller}

At reset, a CPU has almost nothing to work with:

- **Registers exist**, but there is no meaningful program state.
- **Caches exist**, but main memory (DRAM) is *not* usable.
- DRAM needs complex **timing, training, and PHY** configuration before it
  can hold a single byte reliably.

::: {.fragment}
The "chicken-and-egg" problem:

> To run a program large enough to initialize DRAM, we need memory large
> enough to hold that program — which does not exist yet.
:::

::: {.fragment}
**The universal solution:** a *chain* of progressively larger and more
capable loaders, each one setting up enough of the platform for the next.
:::

::: {.notes}
Ask students: what does the very first instruction execute out of? The
answer is on-chip ROM, not DRAM. This motivates every subsequent stage.
:::

## The Boot Chain at a Glance

| Stage | Executes from | Privilege |
|---|---|---|
| Power-On Reset | — | — |
| BootROM (BL1) | on-chip mask ROM | M-mode |
| FSBL / BL2 | internal SRAM | M-mode |
| OpenSBI | DDR | M-mode (resident) |
| U-Boot | DDR | S-mode |
| Linux kernel | DDR | S-mode |
| User space | DDR | U-mode |

Each step crosses a real architectural boundary: a new execution medium, a new
privilege level, or both.

## The SG2000 Memory Hierarchy at Boot {.smaller}

| Medium | Size / Nature | Role in boot |
|---|---|---|
| On-chip Mask ROM | Tiny, immutable | BootROM (zero-stage) |
| Internal SRAM (dedicated scratchpad) | 24 + 64 + 100 KiB, volatile | FSBL / BL2 execution |
| SiP DDR3 | 512 MB, external | OpenSBI, U-Boot, kernel, user |

::: {.fragment}
The progression mirrors the boot chain itself:
**ROM → SRAM → DRAM.**
:::

::: {.notes}
The SG2000 has real dedicated on-chip SRAM (scratchpad/TCM-like), not
"cache-as-RAM": the C906 has no cache-as-RAM mode. BL2 is loaded into
VC_SRAM and executed there before DRAM is trained.
:::

## The RISC-V Privilege Hierarchy {.smaller}

| Mode | Name | Typical occupant |
|---|---|---|
| **M-mode** | Machine | BootROM, FSBL, OpenSBI (resident) |
| **S-mode** | Supervisor | U-Boot, Linux kernel |
| **U-mode** | User | Applications, BusyBox, systemd |

::: {.fragment}
Rules of the ladder:

- You can only **drop** privilege deliberately (e.g., `mret`, `sret`).
- To go **up**, you must **trap** (e.g., `ecall` for a system call).
:::

::: {.notes}
This table is the spine of the entire lecture. Every stage slide should
be mapped back to a row and a privilege transition.
:::

## Heterogeneous Computing on the Duo S {.smaller}

The SG2000 is deliberately *not* a single-core story:

- **Primary core** — 1.0 GHz 64-bit T-Head **C906** (RISC-V)
  - *or* an ARM **Cortex-A53**, selected by a **strap pin** at reset.
- **Secondary core** — 700 MHz **C906**, intended for a small RTOS
  (FreeRTOS / Zephyr) alongside Linux.

::: {.fragment}
Why teach with this chip?

- Heterogeneous cores + RISC-V privilege modes + an open boot chain make
  every layer of the architecture **visible and inspectable**.
:::

::: {.notes}
The dual-architecture switch is a hardware decode/strap decision, not a
software one. The interconnect and peripherals stay identical either way.
:::

# Part II — Stage-by-Stage Boot Breakdown

## Stage 0 — Power-On Reset & BootROM {.smaller}

**The zero-stage bootloader.**

- **Executes from:** internal Mask ROM (hard-etched silicon)
- **Privilege:** M-mode
- **Hardware state:** slow baseline oscillator; no DRAM; limited SRAM

**What it does:**

1. Latches **strapping pins** (SD vs eMMC; RISC-V vs ARM).
2. Brings up the internal SRAM (dedicated scratchpad, not cache-as-RAM) that
   the next stage will run from.
3. Probes the boot media (microSD FAT partition or raw sectors).
4. Reads the header of the firmware bundle (`fip.bin`).
5. Loads the **FSBL** into SRAM and transfers control.

::: {.notes}
The BootROM is immutable and tiny — it cannot be patched. That is exactly
why it does the minimum and hands off immediately.
:::

## Stage 1 — FSBL / BL2 {.smaller}

**First-Stage Bootloader — bring up main memory.**

- **Executes from:** on-chip SRAM (`VC_SRAM` @ `0x3BC0_0000`, 100 KiB)
- **Privilege:** M-mode

**What it does:**

1. **Clock & power:** ramps PLLs up from the baseline oscillator.
2. **Pinmux & console:** configures GPIO; inits UART0 for early debug
   (e.g. the `C.SCS...` banner).
3. **DDR bring-up:** selects the DRAM config from `conf_info`/eFuse and runs
   the compiled-in PHY/controller init and training → full 512 MB available.
4. **Payload unpacking (`fip.bin`):**
   - OpenSBI → DDR at `0x80000000`
   - U-Boot → DDR
   - (optionally) the secondary core's RTOS → top of DRAM
5. **Handoff:** releases secondary cores, sets PC to the OpenSBI entry.

::: {.notes}
Key point: FSBL is a *disposable* initializer. Once DRAM is up and the
payloads are in place, its job is done and it is overwritten.
:::

## Stage 2 — OpenSBI {.smaller}

**Supervisor Binary Interface — the permanent M-mode runtime.**

- **Executes from:** DDR
- **Privilege:** M-mode (stays resident)

**What it does:**

1. **PMP setup:** locks down M-mode memory so S/U-mode cannot tamper with
   firmware or protected regions.
2. **Delegation:** programs `mideleg` / `medeleg` to hand timer, software,
   external interrupts, and page faults down to S-mode.
3. **Hart management:** initializes Hart 0 and provides SBI runtime
   services — console I/O, IPIs, system reset, CLINT timer emulation.
4. **Drop to S-mode:** sets `a0` = hart ID, `a1` = DTB pointer, sets
   `mstatus.MPP` = S-mode, and executes `mret` into U-Boot.

::: {.notes}
Contrast with FSBL: OpenSBI must remain because S-mode still needs its
services later (e.g. timer emulation via `ecall`).
:::

## Stage 3 — Das U-Boot {.smaller}

**Second-stage bootloader — flexible, device-aware loading.**

- **Executes from:** DDR
- **Privilege:** S-mode

**What it does:**

1. Initializes high-level peripherals: SD/MMC host controller, Ethernet,
   USB, full interactive console.
2. Reads user boot scripts / environment (`bootcmd`).
3. Loads OS assets from the boot partition (ext4 or FAT):
   - Linux kernel (`Image` / `uImage`)
   - Board DTB (`cv181x_milkv_duos.dtb`)
   - Optional initramfs / rootfs
4. Prepares `bootargs`, passes the DTB address, jumps to the kernel entry.

::: {.notes}
U-Boot is the last stage a user typically sees or modifies — hence its
role as the natural teaching hook for `bootargs` and DTBs.
:::

## Stage 4 — Linux Kernel Bring-Up {.smaller}

**OS kernel initialization.**

- **Executes from:** DDR
- **Privilege:** S-mode

**What it does:**

1. **Enable the MMU:** moves from bare physical addressing to paging
   (configures `satp` for Sv39/Sv48).
2. **Parse the DTB:** enumerate platform hardware — PLIC, pin controllers,
   I2C, SPI, DMA.
3. **Multi-core / IPC:** initialize Mailbox interrupts and shared memory
   (e.g. RPMsg) to talk to the secondary core's RTOS.
4. **Mount root filesystem** from SD/eMMC.
5. Spawn **PID 1** (`/sbin/init` or `/bin/sh`).

::: {.notes}
The MMU slide is the natural place to connect back to the virtual-memory
unit of the course: same hardware, now configured by software.
:::

## Stage 5 — User Space {.smaller}

**U-mode — where our programs finally run.**

- **Privilege:** User Mode (U-mode)
- The kernel drops privilege via `sret` to run unprivileged processes
  (BusyBox, systemd, ...).
- Any privileged operation — hardware access, I/O — must **trap** back up
  to S-mode via `ecall` (a system call).

::: {.fragment}
We have now walked the full ladder:
**M-mode → S-mode → U-mode**, across **ROM → SRAM → DRAM**.
:::

::: {.notes}
Close the loop: the shell prompt is the end of a chain that began in
mask ROM executing with no memory at all.
:::

# Part III — Discussion Prompts

## Why Not Run U-Boot Directly from BootROM?

::: {.fragment}
**BootROM is tiny and immutable.**

- U-Boot is several megabytes.
- It needs complex DRAM timing routines that cannot fit in ROM — and
  cannot run before the DDR controller is configured.
:::

::: {.fragment}
Hence the staged chain: each loader is only as large as the environment it
runs in allows.
:::

::: {.notes}
Tie back to the chicken-and-egg slide: size and memory availability drive
the number of stages.
:::

## Why Does OpenSBI Stay Resident?

::: {.fragment}
**FSBL's job is purely initialization** — bootstrap and disappear.

**OpenSBI provides ongoing M-mode services** that S-mode cannot perform
directly due to architectural privilege restrictions:

- timer emulation via `ecall`
- inter-hart management (IPIs, start/stop)
- system reset
:::

::: {.notes}
Ask: what would break if OpenSBI were overwritten by the kernel? Answer:
the kernel would lose its only path to M-mode operations.
:::

## What Is the Significance of the Device Tree?

::: {.fragment}
Unlike x86 (ACPI + runtime bus enumeration such as PCIe), embedded RISC-V
and ARM SoCs have **non-discoverable memory-mapped peripherals**.
:::

::: {.fragment}
The **DTB** passes the physical topology — register addresses, IRQ lines —
dynamically from the bootloader to the kernel.
:::

::: {.notes}
Good bridge to a lab: dump the live device tree with `dtc` and compare it
to the source `.dts`.
:::

## How Does Dual-Architecture Switching Work?

::: {.fragment}
At the **silicon level**, the primary core's instruction decoder/pipeline
is selected via **strap pins** during Stage 0 reset.
:::

::: {.fragment}
The rest of the SoC — interconnect, bus, peripherals — remains identical.
:::

::: {.notes}
This is why the same board support package can target either a RISC-V or
an ARM primary core with minimal changes.
:::

## Summary

- Booting is a **staged chain**: ROM → SRAM → DRAM.
- Each stage crosses a **privilege** and/or **execution-medium** boundary.
- **M-mode** (BootROM, FSBL, OpenSBI) sets up the platform.
- **S-mode** (U-Boot, Linux) manages devices and the OS.
- **U-mode** runs our code — and traps back up for anything privileged.
- The SG2000 makes all of this **visible, inspectable, and teachable**.

::: {.notes}
Preview the lab/exercise: identify each stage's banner on a real serial
console and map it to the slides.
:::
