# Coverage-Guided Hardware Fuzzing with Mutation Seeding in RISC-V Processor

**Group 7 | EEE6323 — VLSI Circuits and Technology | University of Florida**

Maragur Atish · Bhanderi Deep Alpeshkumar · Ke-Wei Tung

---

## Overview

A coverage-guided grey-box hardware fuzzer for the **CVA6** (Ariane) RISC-V processor core. The framework generates RISC-V instruction sequences, simulates them on CVA6 using **Synopsys VCS**, reads functional coverage from SystemVerilog covergroups, and uses that feedback to automatically generate better test programs — without modifying the RTL.

Starting from a **25% random baseline**, the three-phase framework reaches **98.0% cumulative functional coverage** across 1,700+ simulation iterations.

| Metric | Result |
|---|---|
| Cumulative functional coverage | **98.0%** |
| `branch_cg` (branch predictor) | 100% |
| `store_cg` (store buffer) | 100% |
| `except_cg` (instruction-type cross product) | 93.9% |
| Total simulations run | 1,700+ |
| RTL modification required | None — black-box, AXI-only |

---

## How It Works

```
Python generates          VCS simulates         Testbench measures
RISC-V instructions  →    CVA6 RTL          →   covergroup %
(sim_input.hex)           (real processor)      (branch/store/except)
        ▲                                              │
        │                                              ▼
   Mutate best         ←   Corpus keeps      ←   Python decides:
   seed from corpus        best-performing       promote / reject /
   (bitflip / swap /       programs              mutate further
    crossover / GA)
```

The fuzzer drives CVA6 entirely through its **AXI memory interface** using generated `.hex` files — no RTL instrumentation, no testbench rewrite beyond standard covergroup definitions.

---

## Three-Phase Framework

| Phase | Method | Reference | Coverage Gain |
|---|---|---|---|
| **1 — Exploration** | 17 hand-written strategy generators + AFL-style mutation | Zalewski, *AFL* (2013) | 25% → 88.3% |
| **2 — Exploitation** | Simulated annealing + adaptive mutator scoring | — | 88.3% → 96.6% |
| **3 — Refinement** | Genetic algorithm — tournament selection, elitism, multi-point crossover | Squillero & Tonda, *MicroGP* (2005) | 96.6% → 98.0% |

**Key insight:** Infrastructure correctness dominated algorithmic sophistication. A single-line fix (`$assertoff`) for a CVA6 FPU arbiter assertion contributed **+63 percentage points** — more than every mutation strategy combined (+9.7 pp).

---

## Repository Structure

```
.
├── fuzzer/
│   ├── mutation_engine.py       # Instruction generation, RV32IM + RV64 support, mutators
│   ├── run_vcs_fuzzer.py        # Phase 1: AFL-style exploration
│   ├── run_converge_full.py     # Phase 2: Convergence + simulated annealing
│   ├── run_genetic_fuzzer.py    # Phase 3: Genetic algorithm (MicroGP-inspired)
│   ├── coverage_analyzer.py     # Coverage bin parsing utilities
│   ├── parse_ucdb.py            # UCDB/VDB parsing helpers
│   └── plot_ieee.py             # IEEE-style result figure generator
│
├── tb/
│   └── testbench.sv             # CVA6 wrapper + 3 functional covergroups
│
├── sim_work/
│   └── files.f                  # VCS compilation file list
│
├── results/
│   ├── *.json                   # Per-phase result logs
│   └── *.png                    # Generated coverage figures
│
├── scripts/
│   ├── compile_vcs.sh           # VCS compilation command
│   └── fix_rtl_issues.py        # Automated CVA6 RTL compatibility fixes
│
└── cva6/                        # CVA6 RTL (git submodule — OpenHW Group)
```

---

## Setup

### Prerequisites
- Synopsys VCS (tested on W-2024.09)
- Python 2.7 (fuzzer scripts) and Python 3 with `matplotlib`/`numpy` (plotting only)
- `urg` (Synopsys Unified Report Generator)

### Clone and initialize
```bash
git clone --recurse-submodules <repo-url>
cd CGF_RTL_Debugging
git submodule update --init --recursive
```

### Compile CVA6 RTL with VCS
```bash
source /apps/settings

vcs -sverilog -full64 -f sim_work/files.f \
  +incdir+cva6/core/include \
  +incdir+cva6/core/cvfpu/src/common_cells/include \
  +incdir+cva6/vendor/pulp-platform/axi/include \
  +incdir+cva6/core/cache_subsystem/hpdcache/rtl/include \
  +incdir+cva6/vendor/pulp-platform/common_cells/include \
  -timescale=1ns/1ps -o sim_work/simv -top testbench \
  +error+30 +define+SYNTHESIS +define+DISABLE_ASSERTIONS +define+XSIM \
  2>&1 | grep "Error-"
```

> **Note:** CVA6's RTL has known VCS-compatibility issues (FPU arbiter assertion, `hpdcache` macro expansion, regfile filename mismatch). See `scripts/fix_rtl_issues.py` for automated fixes, or `docs/TROUBLESHOOTING.md` for the manual walkthrough.

---

## Running the Fuzzer

```bash
# Phase 1 — Exploration (≈100 iterations)
python fuzzer/run_vcs_fuzzer.py

# Phase 2 — Convergence (≈100–500 iterations)
python fuzzer/run_converge_full.py

# Phase 3 — Genetic algorithm (75 generations × 20 individuals)
python fuzzer/run_genetic_fuzzer.py
```

Run long jobs in the background so they survive SSH disconnects:
```bash
nohup python fuzzer/run_genetic_fuzzer.py > /tmp/genetic_log.txt 2>&1 &
tail -f /tmp/genetic_log.txt
```

### Generating result figures
```bash
python3 fuzzer/plot_ieee.py \
  --phase1 /tmp/fuzzer_results.json \
  --phase2 /tmp/converge_results.json \
  --phase3 /tmp/genetic_results.json \
  --out results/
```

---

## Coverage Model

Three SystemVerilog covergroups defined in `tb/testbench.sv`:

| Covergroup | Tracks | Bins | Result |
|---|---|---|---|
| `branch_cg` | Branch predictor outcomes (taken / not-taken / mispredict / correct) | 4 | 100% |
| `store_cg` | Store buffer occupancy (idle / busy) | 2 | 100% |
| `except_cg` | Instruction-type cross product (opcode × funct3) | 96 | 93.9% |

`except_cg` cannot reach 100% because roughly 6% of the (opcode, funct3) combinations do not correspond to valid RISC-V instructions (e.g., `STORE` with `funct3=5`). CVA6 raises an illegal-instruction exception for these, so the instruction never commits and the bin can never be marked covered. The theoretical ceiling is **~93–94%** — the framework reaches it.

---

## Related Work

| | AFL | MicroGP | TheHuzz | This Work |
|---|---|---|---|---|
| Domain | Software | CPU test gen | RTL verification | RTL verification |
| Feedback signal | Code coverage | Fault simulation | Toggle coverage | Functional covergroups |
| Mutation | Byte-level | GA crossover | ISA-aware | Both + GA |
| RTL modification | N/A | No | No | **No** |

`TheHuzz` is the only prior work targeting CVA6 specifically, but reports toggle coverage rather than functional covergroup coverage — the metrics are not directly comparable. This work adapts AFL's corpus-management loop and MicroGP's evolutionary operators to a functional-coverage feedback signal.

---

## Team

| Member | Responsibilities |
|---|---|
| Deep Alpeshkumar Bhanderi | Simulation environment, testbench/covergroup design, strategy generators |
| Atish Maragur | Mutation engine, AFL fuzzing loop, convergence fuzzer, genetic algorithm |
| Ke-Wei Tung | Coverage extraction, URG parsing, RV64 extension, plotting, report |

---

## References

1. M. Zalewski, "American Fuzzy Lop (AFL)," 2013.
2. G. Squillero, "MicroGP — An evolutionary assembly program generator," *GPEM*, vol. 6, no. 3, 2005.
3. R. Kande *et al.*, "TheHuzz: Instruction fuzzing of processors using golden-reference models," *USENIX Security*, 2022.
4. K. Laeufer *et al.*, "RFUZZ: Coverage-directed fuzz testing of RTL on FPGAs," *ICCAD*, 2018.
5. F. Zaruba and L. Benini, "The cost of application-class processing," *IEEE Trans. VLSI Syst.*, vol. 27, no. 11, 2019.

---

## License

This project is for academic purposes (EEE6323, University of Florida). CVA6 RTL is licensed separately under Apache 2.0 / Solderpad Hardware License v2.1 by OpenHW Group.
