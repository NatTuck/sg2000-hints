---
title: "Why an OS?"
subtitle: "From Blink to FreeRTOS on the SG2000 Little Core — Reference Notes"
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
    footer: "CS 4250 · Why an OS? — Reference Notes"
    preview-links: auto
    fig-align: center
    width: 1280
    height: 800
    margin: 0.08
---

## Roadmap {.smaller}

**Motivation**

1. The bare-metal model and its limits
2. Six coordination questions → six OS services
3. Why an OS on a *secondary real-time* core
4. Why not Linux there

**Mechanisms**

5. Tasks, priorities, blocking, preemption, the tick
6. Context switch on RISC-V / C906
7. Synchronization and IPC
8. Memory cost of concurrency

**Platform & Practice**

9. The vendor FreeRTOS port and the Linux bridge
10. The four-rung Blink ladder
11. Discussion and lab ladder

::: {.notes}
Condensed companion to the lecture deck. Each slide is one idea with the
minimum facts to reconstruct the argument.
:::

# Part I — Motivation

## The Bare-Metal Model and Its Limits {.smaller}

- Little core: T-Head **C906L**, RV64, ~700 MHz, **no cache**, **M-mode**,
  **no MMU/PMP**, 2 MB carveout at **`0x9fe0_0000`**.
- Arduino model: `setup()` once, `loop()` forever; `delay()` is a **busy-wait**.
- The superloop has **one program counter**, so it cannot express concurrency.
- It still embeds a proto-OS layer: `pinMode`/`digitalWrite` hide pinmux and
  registers.

::: {.notes}
See hints/fishwaldo-arduino.md, hints/physical-memory.md, hints/gpio-software.md.
:::

## Six Questions → Six Services {.smaller}

| Question | OS service |
|---|---|
| Do two things at once | tasks + scheduler |
| Meet a deadline without spinning | timers, blocking delays, tick |
| Run the important thing first | priority + preemption |
| Share data safely | critical sections, mutexes, queues |
| Write portable code | drivers, HAL, standard APIs |
| Cooperate with Linux | message queues / IPC |

> An OS is a **bundle of reusable answers** to coordination problems.

::: {.notes}
The thesis. Each later section is a derivation of one row.
:::

## Why an OS on a Secondary Real-Time Core {.smaller}

- **Real-time = deterministic**, not "fast" or "no OS."
- An RTOS *increases* determinism: fixed tick, priority preemption, bounded
  latency, blocking instead of polling.
- The core is a **service** to the system (camera/ISP/audio/control); a service
  needs a scheduler and an IPC framework.
- OS cost: RAM per task, tick overhead, port/config complexity.

::: {.notes}
Bound the claim: bare metal is right for one trivial job.
:::

## Why Not Linux Here {.smaller}

| Requirement | Little C906L |
|---|---|
| MMU / page tables | none (M-mode, physical) |
| Privilege separation | none configured |
| Memory | 2 MB carveout |
| Cache | none |
| SMP | `nproc` = 1 |

> Linux assumes an MMU and ample RAM. The only OS that fits is a
> **real-time kernel**: FreeRTOS.

::: {.notes}
Sharpest answer to "why an OS here": Linux can't run; an RTOS is the minimal
OS that can.
:::

# Part II — Mechanisms

## Tasks, Priorities, States {.smaller}

```c
xTaskCreate(fn, "name", stack_words, arg, priority, &handle);
vTaskStartScheduler();   // never returns
```

- Priority: higher number wins; highest-priority **ready** task runs.
- States: Running / Ready / Blocked / Suspended.
- Idle task (priority 0) runs when nothing else is ready.
- Vendor port: tasks created in `main_cvirtos()`; **CMDQU** task at priority 5.

::: {.notes}
freertos/cvitek/task/comm/src/riscv64/comm_main.c.
:::

## Blocking vs. Busy-Waiting {.smaller}

- `delay(ms)` — spins; CPU consumed; nothing else runs.
- `vTaskDelay(ticks)` — blocks; CPU released; scheduler runs others.
- `vTaskDelayUntil(&last, period)` — fixed-period task, drift-free.

> `delay()` **consumes** time; `vTaskDelay()` **surrenders** it.

::: {.notes}
The single most important shift for students.
:::

## Preemption and the Tick {.smaller}

```text
mtime ≥ mtimecmp  →  mcause = 0x8000_0000_0000_0007
   ├─ re-arm mtimecmp
   ├─ xTaskIncrementTick()   (wake sleepers)
   └─ vTaskSwitchContext()   (pick next task)
```

- `mtvec` = trap handler (set before scheduler start).
- `mie.MTIE` enables the timer interrupt.
- C906 quirks: `mtimecmp` is two 32-bit halves, **low word written last**; if
  `mtime` is not memory-mapped, read the `time` CSR.
- Modern config: `configMTIME_BASE_ADDRESS`, `configMTIMECMP_BASE_ADDRESS`,
  `portasmHAS_MTIME` (not the old SiFive CLINT constants).

::: {.notes}
Upstream FreeRTOS portable/GCC/RISC-V; Sophgo freertos/cvitek port.
:::

## Context Switch Anatomy {.smaller}

- **Save**: integer registers + `mepc` (resume PC) + `mstatus` → task stack/TCB.
- **Restore**: next task's registers, `mepc`, `mstatus` → **`mret`**.
- `pxPortInitialiseStack()` builds a synthetic frame so task start looks like a
  context restore; `xPortStartFirstTask()` restores it and `mret`s.

> One real PC, many software contexts — the OS swaps register state.

::: {.notes}
FreeRTOS portContext.h / portASM.S.
:::

## Synchronization and IPC {.smaller}

| Primitive | Use |
|---|---|
| Queue | move data + signal a waiter |
| Binary / counting semaphore | signal events / count resources |
| Mutex | mutual exclusion + **priority inheritance** |
| Task notification | fast per-task signal |
| Stream/message buffer | byte/record stream task↔ISR |

- ISRs use **`...FromISR()`** variants and defer work to a task.

::: {.notes}
Priority inheritance prevents priority inversion.
:::

## Memory Cost of Concurrency {.smaller}

- Each task has its own **stack** in the 2 MB carveout.
- `heap_4` is the usual allocator here.
- Stack sizing is a real design task; overflow corrupts silently.
- Check with `uxTaskGetStackHighWaterMark()`.

> Concurrency is not free on a memory-starved core.

::: {.notes}
Ties back to the counterpoint: match tool to workload.
:::

# Part III — Platform & Practice

## The Vendor FreeRTOS Port {.smaller}

- `freertos/cvitek/` — CMake/Ninja → **`cvirtos.bin`**.
- Loaded at **`0x9fe0_0000`** — the **same carveout** as the Arduino sketches.
- Pre-loaded by **BL2** at boot, or by **remoteproc** at runtime.
- Entry **`main_cvirtos()`** → create tasks → `vTaskStartScheduler()`.
- Toolchain: `riscv64-unknown-elf-` (bare-metal, `--specs=nosys.specs`).

::: {.notes}
Same delivery mechanism as Arduino; richer program inside.
:::

## The Linux Bridge {.smaller}

```text
Linux (C920)                     Little core (C906L)
  mailbox 0x0190_0000  ───────►  interrupt
  virtio rings (vdev0vring0/1, vdev0buffer)
  RPMsg message        ───────►  CMDQU task wakes
  ◄───────────────────────────  response
```

- Vendor `rtos_cmdqu` = command queue over RPMsg.
- CMDQU task (priority 5) dispatches to other tasks.

::: {.notes}
The OS turns raw shared memory + mailbox into a message-passing component.
:::

## The Four-Rung Blink Ladder {.smaller}

| Rung | Mechanism | Gains | Costs |
|---|---|---|---|
| 1 | `delay()` superloop | simplicity | blocks; no concurrency |
| 2 | `millis()` state machine | concurrency | cooperative; jitter; manual state |
| 3 | timer ISR | precision | short-ISR rule; races |
| 4 | FreeRTOS tasks | priority, blocking, structure | stacks; complexity |

> Capability ↑, complexity ↑, footprint ↑.

::: {.notes}
Examples: Blink (verified), BlinkMillis / BlinkTimerISR / BlinkRtos (reasoned).
:::

## Discussion & Lab Ladder {.smaller}

**Lab:** Blink → BlinkMillis → timer ISR → FreeRTOS tasks → RPMsg command.

**Discuss:**

- Where is the line between a state machine and an RTOS?
- What is priority inversion; how does a mutex fix it?
- Why is "no OS because real-time" usually a misunderstanding?
- What breaks when two cores share DRAM without cache coherency?

::: {.notes}
Close on judgment: match the tool to the number of concurrent,
timing-constrained, sharing activities.
:::
