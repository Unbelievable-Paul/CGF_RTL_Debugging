#!/usr/bin/env python
import subprocess, re, os

class UncoveredBin(object):
    def __init__(self, covergroup, coverpoint, bin_name, hits, target):
        self.covergroup = covergroup
        self.coverpoint = coverpoint
        self.bin_name   = bin_name
        self.hits       = hits
        self.target     = target

    @property
    def priority(self):
        return 1.0 - (self.hits / float(max(self.target, 1)))

    def __repr__(self):
        return "{0}.{1}.{2} {3}/{4}".format(
            self.covergroup, self.coverpoint,
            self.bin_name, self.hits, self.target)

def load_ucdb(vdb_path):
    """Read VCS coverage.vdb using urg tool"""
    if not os.path.exists(vdb_path):
        print("[PARSE] VDB not found: {0}".format(vdb_path))
        return _parse_from_log()

    report_dir = "/tmp/urg_report"
    cmd = ["urg", "-dir", vdb_path, "-format", "text", "-report", report_dir]
    r = devnull = open(os.devnull, "w"); subprocess.call(cmd, stdout=devnull, stderr=devnull); devnull.close()

    cov_file = report_dir + "/testbench.txt"
    if not os.path.exists(cov_file):
        # Try groups.txt
        cov_file = report_dir + "/groups.txt"

    if os.path.exists(cov_file):
        bins = _parse_urg(cov_file)
        if bins:
            return bins

    print("[PARSE] urg parse empty - using log fallback")
    return _parse_from_log()

def _parse_urg(path):
    """Parse URG text report for functional coverage bins"""
    bins=[]; cg=""; cp=""
    cg_re = re.compile(r'^\s*(\w+)\s+(?:Cover Group|Covergroup)', re.IGNORECASE)
    cp_re = re.compile(r'^\s*(\w+)\s+(?:Cover Point|Coverpoint)', re.IGNORECASE)
    bin_re = re.compile(r'^\s+(\w+)\s+(\d+)\s+(\d+)')
    try:
        with open(path) as f:
            for line in f:
                m = re.search(r'TYPE\s+(\w+)', line)
                if m: cg=m.group(1); cp=""; continue
                m = re.search(r'Coverpoint\s+(\w+)', line)
                if m: cp=m.group(1); continue
                m = bin_re.match(line)
                if m and cg and cp:
                    name=m.group(1); hits=int(m.group(2)); tgt=int(m.group(3))
                    if hits < tgt:
                        bins.append(UncoveredBin(cg,cp,name,hits,tgt))
    except Exception as e:
        print("[PARSE] Error: {0}".format(e))
    bins.sort(key=lambda b: b.priority, reverse=True)
    print("[PARSE] {0} unhit bins from VDB (urg)".format(len(bins)))
    return bins

def get_covergroup_summary(vdb_path):
    """Get covergroup coverage percentages from URG"""
    result = {}
    if not os.path.exists(vdb_path): return result
    report_dir = "/tmp/urg_report_sum"
    cmd = ["urg", "-dir", vdb_path, "-format", "text", "-report", report_dir]
    devnull = open(os.devnull, "w"); subprocess.call(cmd, stdout=devnull, stderr=devnull); devnull.close()
    # Parse dashboard.txt for summary
    dash = report_dir + "/dashboard.txt"
    if not os.path.exists(dash):
        dash = report_dir + "/hierarchy.txt"
    try:
        with open(dash) as f:
            for line in f:
                # Look for covergroup lines
                m = re.search(r'(\d+\.\d+)\s+(\w+_cg|branch_cg|store_cg|except_cg)', line)
                if m:
                    result[m.group(2)] = float(m.group(1))
    except: pass
    return result

def _parse_from_log():
    """Fallback: parse coverage from simulation log"""
    log = "/home/UFAD/atish.maragur/FUZZER_PROJECT/questa_sim.log"
    if not os.path.exists(log):
        log = "/home/UFAD/atish.maragur/FUZZER_PROJECT/vcs_sim.log"
    bins = []
    if not os.path.exists(log): return bins
    branch=store=excpt=0.0
    with open(log) as f:
        for line in f:
            m=re.search(r'\[COV\] branch_cg\s*:\s*([\d\.]+)%', line)
            if m: branch=float(m.group(1))
            m=re.search(r'\[COV\] store_cg\s*:\s*([\d\.]+)%', line)
            if m: store=float(m.group(1))
            m=re.search(r'\[COV\] except_cg\s*:\s*([\d\.]+)%', line)
            if m: excpt=float(m.group(1))
    if branch < 100.0:
        bins.append(UncoveredBin("cg_branch","cp_taken","taken",int(branch),100))
        bins.append(UncoveredBin("cg_branch","cp_mispredict","mispredict",0,1))
    if store < 100.0:
        bins.append(UncoveredBin("cg_store_buf","cp_pending","busy",int(store),100))
    if excpt < 100.0:
        bins.append(UncoveredBin("cg_exception","cp_trap","trap",int(excpt),100))
    bins.sort(key=lambda b: b.priority, reverse=True)
    print("[PARSE] {0} synthetic bins from log".format(len(bins)))
    return bins

def get_total_coverage(vdb_path):
    """Get total line/branch coverage from URG"""
    if not os.path.exists(vdb_path): return 0.0
    report_dir = "/tmp/urg_total"
    cmd = ["urg", "-dir", vdb_path, "-format", "text", "-report", report_dir]
    devnull = open(os.devnull, "w"); subprocess.call(cmd, stdout=devnull, stderr=devnull); devnull.close()
    try:
        hier = report_dir + "/hierarchy.txt"
        with open(hier) as f:
            for line in f:
                m = re.search(r'([\d\.]+)\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+testbench', line)
                if m: return float(m.group(1))
    except: pass
    return 0.0

if __name__=="__main__":
    vdb="/home/UFAD/atish.maragur/FUZZER_PROJECT/sim_work/coverage.vdb"
    print("VDB exists: {0}".format(os.path.exists(vdb)))
    print("")
    print("=== Coverage Summary ===")
    total = get_total_coverage(vdb)
    print("  Total score: {0:.2f}%".format(total))
    print("")
    print("=== Unhit Bins ===")
    bins = load_ucdb(vdb)
    for b in bins:
        print("  [{0:.2f}] {1}".format(b.priority, b))

