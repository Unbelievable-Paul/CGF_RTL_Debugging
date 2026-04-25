#!/usr/bin/env python
import subprocess, os, sys, json, shutil, re
from datetime import datetime

BASE    = "/home/UFAD/atish.maragur/FUZZER_PROJECT"
SIM_DIR = BASE + "/sim_work"
HEX     = SIM_DIR + "/sim_input.hex"
BEST    = SIM_DIR + "/best_input.hex"
SNAP    = SIM_DIR + "/xcelium.d"
RESULTS = SIM_DIR + "/fuzzer_results.json"

MAX_ITER      = 5
COVERAGE_GOAL = 80.0
MIN_IMPROVE   = 0.5

def run_sim():
    cmd = [
        "xrun", "-R",
        "-snapshot", "cva6_snapshot",
        "-xmlibdirname", SNAP,
        "-defparam", "testbench.HEX_FILE=\"{0}\"".format(HEX),
        "-defparam", "testbench.MAX_CYCLES=50000",
        "-coverage", "all",
        "-covfile", BASE + "/scripts/coverage.ccf",
        "-covoverwrite", "-exit"
    ]
    r = subprocess.call(cmd, cwd=BASE)
    return r == 0

def get_ucd():
    for root,_,files in os.walk(BASE + "/cov_work"):
        for f in files:
            if f.endswith(".ucd"):
                return os.path.join(root,f)
    return None

def get_cov():
    ucd = get_ucd()
    if not ucd: return 0.0
    script="load -run {0}\nreport -summary -cumulative -all -out /tmp/imc_sum.txt\nexit\n".format(ucd)
    with open("/tmp/q.tcl","w") as f: f.write(script)
    subprocess.call(["imc","-exec","/tmp/q.tcl"])
    try:
        with open("/tmp/imc_sum.txt") as f:
            for line in f:
                m=re.search(r'([\d\.]+)\s*%', line)
                if m and ("Functional" in line or "Total" in line):
                    return float(m.group(1))
    except: pass
    return 0.0

def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from mutation_engine   import strategy_random_mix, write_hex, mutate
    from parse_ucdb        import load_ucdb
    from coverage_analyzer import analyze

    best_cov=0.0; failed=set(); results=[]

    print("="*50)
    print(" CVA6 Coverage Fuzzer - Group 7 EEE6323")
    print(" MAX_ITER={0}  GOAL={1}%".format(MAX_ITER, COVERAGE_GOAL))
    print(" Started: {0}".format(datetime.now().strftime('%H:%M:%S')))
    print("="*50)

    write_hex(strategy_random_mix(511), HEX)
    shutil.copy(HEX, BEST)

    for i in range(MAX_ITER):
        print("\n--- Iter {0}/{1}  best={2:.1f}% ---".format(i+1, MAX_ITER, best_cov))
        ok = run_sim()
        if not ok:
            shutil.copy(BEST, HEX)
            results.append({"iter":i+1,"action":"sim_error"})
            continue

        cov = get_cov()
        imp = cov - best_cov
        print("Coverage={0:.1f}%  improvement={1:+.1f}%".format(cov, imp))

        if cov >= best_cov + MIN_IMPROVE:
            print("IMPROVED - keeping")
            best_cov=cov; shutil.copy(HEX,BEST); failed.clear()
            action="improved"
            ucd=get_ucd()
            if ucd:
                bins=load_ucdb(ucd); targets=analyze(bins)
                write_hex(mutate(targets,i,failed), HEX)
            else:
                write_hex(strategy_random_mix(511), HEX)
        else:
            print("NO IMPROVEMENT - rolling back")
            shutil.copy(BEST, HEX)
            write_hex(strategy_random_mix(511), HEX)
            action="rollback"

        results.append({"iter":i+1,"cov":cov,"best":best_cov,"action":action})
        if best_cov >= COVERAGE_GOAL:
            print("Goal {0}% reached!".format(COVERAGE_GOAL))
            break

    print("\n" + "="*50)
    print(" DONE  final best = {0:.1f}%".format(best_cov))
    for r in results:
        mark="+" if r.get("action")=="improved" else "-"
        print("  {0} iter {1:02d}: {2:.1f}% [{3}]".format(
              mark, r["iter"], r.get("cov",0), r["action"]))
    print("="*50)
    with open(RESULTS,"w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to {0}".format(RESULTS))

if __name__=="__main__":
    main()
