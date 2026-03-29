"""
main.py — Top-level fuzzing loop for CVA6 Coverage-Guided Hardware Fuzzer
Group 7 | EEE6323 VLSI II | University of Florida

Orchestrates 3 strategies:
  - random:           new random seed every iteration (baseline)
  - mutation_only:    always mutate from corpus, always save
  - coverage_guided:  mutate from corpus, save only if delta > 0

Usage:
  python main.py --strategy coverage_guided --iterations 200
"""

import argparse
import os
import random

from seed_generator   import SeedGenerator
from mutation_engine  import MutationEngine
from input_formatter  import write_hex
from xcelium_runner   import XceliumRunner
from coverage_analyzer import CoverageAnalyzer
from results_logger   import ResultsLogger

# ── PATHS — edit these for your machine ──────────────────────────────────────
CVA6_RTL_PATH  = "/path/to/cva6/rtl"          # cloned CVA6 rtl/ directory
XCELIUM_HOME   = "/path/to/cadence/xcelium"   # Xcelium install root
IMC_HOME       = "/path/to/cadence/imc"       # Cadence IMC install root
WORK_DIR       = "./sim_work"                  # working dir for sim outputs
# ─────────────────────────────────────────────────────────────────────────────

INITIAL_CORPUS_SIZE = 10
HEX_FILE            = os.path.join(WORK_DIR, "sim_input.hex")
UCDB_FILE           = os.path.join(WORK_DIR, "coverage.ucdb")
LOG_FILE            = "./results/iterations.jsonl"
SUMMARY_FILE        = "./results/summary.json"


def build_initial_corpus(gen, size=INITIAL_CORPUS_SIZE):
    """Generate random seeds to seed the corpus."""
    return [{"instructions": gen.generate(), "score": 1.0} for _ in range(size)]


def weighted_select(corpus):
    """Select a seed from corpus weighted by score."""
    scores = [s["score"] for s in corpus]
    total  = sum(scores)
    probs  = [s / total for s in scores]
    return random.choices(corpus, weights=probs, k=1)[0]


def run(strategy: str, n_iterations: int):
    os.makedirs(WORK_DIR,          exist_ok=True)
    os.makedirs("./results",       exist_ok=True)

    gen      = SeedGenerator()
    mutator  = MutationEngine()
    runner   = XceliumRunner(CVA6_RTL_PATH, XCELIUM_HOME, WORK_DIR)
    analyzer = CoverageAnalyzer(IMC_HOME, WORK_DIR)
    logger   = ResultsLogger(LOG_FILE)

    print(f"[main] Strategy: {strategy}  |  Iterations: {n_iterations}")

    # Compile CVA6 + testbench once
    print("[main] Compiling CVA6 RTL (this takes 5-15 min)...")
    runner.compile_once()
    print("[main] Compile complete.")

    # Build initial corpus
    corpus       = build_initial_corpus(gen)
    prev_metrics = {m: 0.0 for m in ["statement","branch","condition",
                                      "expression","toggle","fsm"]}

    for i in range(n_iterations):
        # ── 1. Generate stimulus ──────────────────────────────────────────
        if strategy == "random":
            seed = gen.generate()
        else:
            parent = weighted_select(corpus)
            seed   = mutator.mutate(parent["instructions"].copy())

        # ── 2. Write hex file ─────────────────────────────────────────────
        write_hex(seed, HEX_FILE)

        # ── 3. Simulate ───────────────────────────────────────────────────
        success = runner.run_simulation(HEX_FILE, UCDB_FILE)
        if not success:
            print(f"[main] Iter {i:04d}: simulation failed, skipping")
            continue

        # ── 4. Extract coverage ───────────────────────────────────────────
        metrics = analyzer.extract(UCDB_FILE)
        delta   = analyzer.weighted_delta(metrics, prev_metrics)

        print(f"[main] Iter {i:04d}: delta={delta:.4f}  "
              f"fsm={metrics['fsm']:.1f}%  branch={metrics['branch']:.1f}%")

        # ── 5. Update corpus ──────────────────────────────────────────────
        if strategy == "mutation_only":
            corpus.append({"instructions": seed, "score": max(delta, 0.01)})
            prev_metrics = metrics
        elif strategy == "coverage_guided" and delta > 0:
            corpus.append({"instructions": seed, "score": delta})
            prev_metrics = metrics

        # ── 6. Log ────────────────────────────────────────────────────────
        logger.log(i, strategy, metrics, delta, len(corpus))

    logger.save_summary(strategy, n_iterations, prev_metrics, SUMMARY_FILE)
    print(f"[main] Done. Results in {LOG_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy",   default="coverage_guided",
                        choices=["random","mutation_only","coverage_guided"])
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()
    run(args.strategy, args.iterations)
