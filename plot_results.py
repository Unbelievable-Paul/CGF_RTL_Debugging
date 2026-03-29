"""
plot_results.py — Generate coverage comparison plots from iterations.jsonl
Group 7 | EEE6323 VLSI II | University of Florida

Owner: Ke-Wei Tung

Usage:
  python plot_results.py --log results/iterations.jsonl --out results/comparison.png
  python plot_results.py --log results/iterations.jsonl --strategies random coverage_guided
"""

import argparse
import json
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from collections import defaultdict


COLORS = {
    "random":           "#E74C3C",
    "mutation_only":    "#F39C12",
    "coverage_guided":  "#2ECC71",
}

LABELS = {
    "random":           "Random (baseline)",
    "mutation_only":    "Mutation-Only",
    "coverage_guided":  "Coverage-Guided",
}


def load_log(log_file: str) -> dict:
    """Load iterations.jsonl and group by strategy."""
    data = defaultdict(list)
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if line:
                data[json.loads(line)["strategy"]].append(json.loads(line))
    return data


def plot(log_file: str, out_file: str, strategies: list = None):
    data = load_log(log_file)

    if strategies:
        data = {k: v for k, v in data.items() if k in strategies}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("CVA6 Hardware Fuzzer — Coverage Comparison", fontsize=16, fontweight='bold')

    for strategy, records in data.items():
        iters   = [r["iter"]              for r in records]
        deltas  = [r["delta"]             for r in records]
        branch  = [r["metrics"]["branch"] for r in records]
        fsm     = [r["metrics"]["fsm"]    for r in records]
        corpus  = [r["corpus_size"]       for r in records]

        # Cumulative delta
        cum_delta = []
        total = 0.0
        for d in deltas:
            total += d
            cum_delta.append(total)

        color = COLORS.get(strategy, "#333333")
        label = LABELS.get(strategy, strategy)

        axes[0][0].plot(iters, cum_delta, color=color, label=label, linewidth=2)
        axes[0][1].plot(iters, branch,    color=color, label=label, linewidth=2)
        axes[1][0].plot(iters, fsm,       color=color, label=label, linewidth=2)
        axes[1][1].plot(iters, corpus,    color=color, label=label, linewidth=2)

    # Formatting
    titles  = ["Cumulative Coverage Delta", "Branch Coverage %",
               "FSM Coverage %",            "Corpus Size"]
    ylabels = ["Weighted Delta (cumulative)", "Branch Coverage (%)",
               "FSM Coverage (%)",            "Seeds in Corpus"]

    for ax, title, ylabel in zip(axes.flat, titles, ylabels):
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel("Iteration", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
    plt.savefig(out_file, dpi=150, bbox_inches='tight')
    print(f"[plot] Saved to {out_file}")
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log",        default="results/iterations.jsonl")
    parser.add_argument("--out",        default="results/comparison.png")
    parser.add_argument("--strategies", nargs="+",
                        default=["random", "mutation_only", "coverage_guided"])
    args = parser.parse_args()
    plot(args.log, args.out, args.strategies)
