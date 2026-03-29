"""
xcelium_runner.py — Cadence Xcelium compile and simulation runner
Group 7 | EEE6323 VLSI II | University of Florida

Owner: Deep Bhanderi

Two-phase Xcelium flow:
  Phase 1 — compile_once():    xrun -elaborate → snapshot in xcelium.d/
  Phase 2 — run_simulation():  xrun -R -snapshot → coverage.ucdb per iteration

compile_once() takes 5-15 minutes. run_simulation() takes 1-5 seconds.
"""

import os
import subprocess
import glob


class XceliumRunner:

    def __init__(self, cva6_rtl_path: str, xcelium_home: str, work_dir: str,
                 tb_path: str = "tb/testbench.sv",
                 ccf_path: str = "scripts/coverage.ccf",
                 snapshot: str = "cva6_snapshot",
                 max_cycles: int = 2000,
                 timeout: int = 90):

        self.cva6_rtl    = cva6_rtl_path
        self.xrun        = os.path.join(xcelium_home, "bin", "xrun")
        self.work_dir    = work_dir
        self.tb_path     = tb_path
        self.ccf_path    = ccf_path
        self.snapshot    = snapshot
        self.xlib        = os.path.join(work_dir, "xcelium.d")
        self.max_cycles  = max_cycles
        self.timeout     = timeout

    def _sv_sources(self) -> list:
        """Collect all .sv files from the CVA6 RTL directory."""
        pattern = os.path.join(self.cva6_rtl, "**", "*.sv")
        return glob.glob(pattern, recursive=True)

    def compile_once(self) -> bool:
        """
        Elaborate CVA6 RTL + testbench into a reusable Xcelium snapshot.
        Only needs to run once per session.

        Returns True on success.
        """
        sources = self._sv_sources() + [self.tb_path]

        cmd = [
            self.xrun,
            *sources,
            "-elaborate",
            "-snapshot",    self.snapshot,
            "-xmlibdirname", self.xlib,
            "-coverage",    "all",
            "-covfile",     self.ccf_path,
            "-access",      "+rwc",
            "-sv",
            "-timescale",   "1ns/1ps",
            "-quiet",
        ]

        print("[xcelium] Compiling CVA6 RTL... (5-15 min)")
        result = subprocess.run(
            cmd,
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            timeout=900   # 15-minute hard limit
        )

        if result.returncode != 0:
            print("[xcelium] Compile FAILED:")
            print(result.stderr[-2000:])
            return False

        print("[xcelium] Compile OK — snapshot ready.")
        return True

    def run_simulation(self, hex_file: str, ucdb_file: str) -> bool:
        """
        Run one simulation iteration using the precompiled snapshot.

        Args:
            hex_file:  path to $readmemh hex file (sim_input.hex)
            ucdb_file: output UCDB path (coverage.ucdb)

        Returns True on success (ucdb file produced).
        """
        cmd = [
            self.xrun,
            "-R",
            "-snapshot",     self.snapshot,
            "-xmlibdirname", self.xlib,
            "-defparam",     f'testbench.HEX_FILE="{hex_file}"',
            "-defparam",     f"testbench.MAX_CYCLES={self.max_cycles}",
            "-coverage",     "all",
            "-covfile",      self.ccf_path,
            "-covdb",        ucdb_file,
            "-exit",
            "-quiet",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
        except subprocess.TimeoutExpired:
            print(f"[xcelium] Simulation timed out after {self.timeout}s")
            return False

        if result.returncode != 0:
            print(f"[xcelium] Simulation failed (rc={result.returncode})")
            return False

        return os.path.exists(ucdb_file)
