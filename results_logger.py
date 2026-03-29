"""
results_logger.py — Per-iteration JSON-lines logging and summary
Group 7 | EEE6323 VLSI II | University of Florida

Owner: Ke-Wei Tung

Writes one JSON line per iteration to iterations.jsonl.
Writes a final summary.json at end of run.
"""

import json
import os
from datetime import datetime


class ResultsLogger:

    def __init__(self, log_file: str):
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        # Clear log file at start
        open(log_file, 'w').close()

    def log(self, iteration: int, strategy: str,
            metrics: dict, delta: float, corpus_size: int):
        """Append one iteration record to the JSONL file."""
        record = {
            "iter":        iteration,
            "strategy":    strategy,
            "delta":       round(delta, 6),
            "corpus_size": corpus_size,
            "metrics":     {k: round(v, 2) for k, v in metrics.items()},
            "timestamp":   datetime.utcnow().isoformat()
        }
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(record) + '\n')

    def save_summary(self, strategy: str, n_iterations: int,
                     final_metrics: dict, summary_file: str):
        """Write a summary JSON file at end of run."""
        summary = {
            "strategy":       strategy,
            "n_iterations":   n_iterations,
            "final_metrics":  {k: round(v, 2) for k, v in final_metrics.items()},
            "completed_at":   datetime.utcnow().isoformat()
        }
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"[logger] Summary saved to {summary_file}")
