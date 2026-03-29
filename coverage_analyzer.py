"""
coverage_analyzer.py — Cadence IMC coverage extraction and weighted delta scoring
Group 7 | EEE6323 VLSI II | University of Florida

Owner: Ke-Wei Tung

Extracts 6 coverage metrics from a Xcelium UCDB file via Cadence IMC:
  statement, branch, condition, expression, toggle, fsm

Weighted delta scoring:
  FSM        × 3.0  (highest — most indicative of deep state exploration)
  Branch     × 2.0
  Condition  × 2.0
  Expression × 2.0
  Toggle     × 1.0
  Statement  × 1.0
"""

import os
import re
import subprocess
import tempfile

WEIGHTS = {
    "fsm":        3.0,
    "branch":     2.0,
    "condition":  2.0,
    "expression": 2.0,
    "toggle":     1.0,
    "statement":  1.0,
}

ZERO_METRICS = {m: 0.0 for m in WEIGHTS}

TCL_TEMPLATE = """\
load -run {ucdb}
report -detail -metrics all -out {report}
exit
"""


class CoverageAnalyzer:

    def __init__(self, imc_home: str, work_dir: str):
        self.imc      = os.path.join(imc_home, "bin", "imc")
        self.work_dir = work_dir

    def extract(self, ucdb_file: str) -> dict:
        """
        Run Cadence IMC to extract all 6 metrics from a UCDB file.

        Returns dict with keys: statement, branch, condition,
                                expression, toggle, fsm (all 0.0-100.0).
        """
        report_file = os.path.join(self.work_dir, "coverage_report.txt")
        tcl_file    = os.path.join(self.work_dir, "extract_coverage.tcl")

        # Write TCL script
        with open(tcl_file, 'w') as f:
            f.write(TCL_TEMPLATE.format(
                ucdb=os.path.abspath(ucdb_file),
                report=os.path.abspath(report_file)
            ))

        # Run IMC
        result = subprocess.run(
            [self.imc, "-exec", tcl_file, "-quiet"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0 or not os.path.exists(report_file):
            print(f"[coverage] IMC failed: {result.stderr[:500]}")
            return ZERO_METRICS.copy()

        return self._parse_report(report_file)

    def _parse_report(self, report_file: str) -> dict:
        """
        Parse the IMC text report for coverage percentages.

        IMC report lines look like:
          Statement Coverage:   87.3%
          Branch Coverage:      62.1%
          etc.
        """
        metrics = ZERO_METRICS.copy()
        mapping = {
            "statement":  r"statement\s+coverage[:\s]+([\d.]+)%",
            "branch":     r"branch\s+coverage[:\s]+([\d.]+)%",
            "condition":  r"condition\s+coverage[:\s]+([\d.]+)%",
            "expression": r"expression\s+coverage[:\s]+([\d.]+)%",
            "toggle":     r"toggle\s+coverage[:\s]+([\d.]+)%",
            "fsm":        r"fsm\s+coverage[:\s]+([\d.]+)%",
        }

        try:
            text = open(report_file).read().lower()
            for metric, pattern in mapping.items():
                m = re.search(pattern, text)
                if m:
                    metrics[metric] = float(m.group(1))
        except Exception as e:
            print(f"[coverage] Parse error: {e}")

        return metrics

    def weighted_delta(self, new_metrics: dict, prev_metrics: dict) -> float:
        """
        Compute weighted coverage improvement.
        Only positive improvements count — no penalty for regression.

        delta = sum( weight * max(0, new% - prev%) )  for each metric
        """
        delta = 0.0
        for metric, weight in WEIGHTS.items():
            improvement = new_metrics.get(metric, 0.0) - prev_metrics.get(metric, 0.0)
            delta += weight * max(0.0, improvement)
        return delta
