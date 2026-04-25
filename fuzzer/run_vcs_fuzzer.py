#!/usr/bin/env python
# run_vcs_fuzzer.py -- CVA6 Grey-Box Fuzzer 500-iter optimised
# Group 7 EEE6323 | University of Florida
import subprocess, os, sys, re, shutil, json
from datetime import datetime

BASE    = "/home/UFAD/atish.maragur/FUZZER_PROJECT"
HEX     = BASE + "/sim_work/sim_input.hex"
BEST    = "/tmp/best_input.hex"
LOG     = "/tmp/vcs_sim.log"
VDB     = BASE + "/sim_work/coverage.vdb"
SIMV    = BASE + "/sim_work/simv"
RESULTS = "/tmp/fuzzer_results.json"

MAX_ITER      = 100
COVERAGE_GOAL = 100.0
MIN_IMPROVE   = 0.1

# -- Strategy ordering: new optimised strategies FIRST ------------
# Rationale:
#   max_coverage      - designed to hit ALL bins simultaneously
#   trap_trigger      - specifically targets cp_trap=1 bin
#   opcode_funct3_sweep - targets cx_op_f3 cross bins
#   adaptive_opcode   - systematic (opcode x f3 x rd) sweep
#   genetic_combine   - stochastic variation of top strategies
#   rd_sweep          - targets cp_rd bins specifically
#   ecall_with_branches - proven best single strategy (84%)
#   full_sweep        - proven best overall (85%)
#   branch_and_store  - reliable 80%+
#   mispredict_force  - mispredict bin
#   data_dependent_branch - branch variation
#   exception_heavy   - opcode diversity
#   mixed_coverage    - broad opcode coverage
#   always_taken_branch, always_not_taken - branch bins
#   store_buffer_fill - store busy bin
#   deliberate_ecall  - system instructions
#   illegal_instructions - trap trigger backup
#   random_mix        - diversity fallback

STRATEGIES = [
    "max_coverage",
    "trap_trigger",
    "opcode_funct3_sweep",
    "adaptive_opcode",
    "genetic_combine",
    "rd_sweep",
    "ecall_with_branches",
    "full_sweep",
    "branch_and_store",
    "mispredict_force",
    "data_dependent_branch",
    "exception_heavy",
    "mixed_coverage",
    "always_taken_branch",
    "always_not_taken",
    "store_buffer_fill",
    "deliberate_ecall",
    "illegal_instructions",
    "random_mix",
]

def run_sim(iter_name):
    cmd = [SIMV, "-cm", "line+cond+fsm+branch+tgl",
           "-cm_dir", VDB, "-cm_name", iter_name, "-cm_nocopyright"]
    print("[SIM] simv iter={0}".format(iter_name))
    with open(LOG, "w") as lf:
        ret = subprocess.call(cmd, cwd=BASE, stdout=lf, stderr=lf)
    if ret != 0:
        print("[SIM] FAILED rc={0}".format(ret))
    return ret == 0

def get_cov_from_log():
    b = s = e = 0.0; retired = cycles = 0
    if not os.path.exists(LOG): return 0.0,0.0,0.0,0,0
    with open(LOG) as f:
        for line in f:
            m = re.search(r'\[COV\] branch_cg\s*:\s*([\d.]+)%', line)
            if m: b = float(m.group(1))
            m = re.search(r'\[COV\] store_cg\s*:\s*([\d.]+)%', line)
            if m: s = float(m.group(1))
            m = re.search(r'\[COV\] except_cg\s*:\s*([\d.]+)%', line)
            if m: e = float(m.group(1))
            m = re.search(r'\[COV\] retired\s*:\s*(\d+)', line)
            if m: retired = int(m.group(1))
            m = re.search(r'\[COV\] cycles\s*:\s*(\d+)', line)
            if m: cycles = int(m.group(1))
    return b, s, e, retired, cycles

def pick_strategy(b, s, e, failed, i, stagnant_count):
    """
    Smart strategy picker with 3 modes:
    1. GAP-TARGETED: picks strategy addressing biggest uncovered group
    2. STAGNATION-BREAKER: after 15 rollbacks, force new strategies
    3. GENETIC: after 30 rollbacks, use genetic_combine for diversity
    """
    # Stagnation breaking: force genetic or random after long runs
    if stagnant_count >= 30:
        for c in ["genetic_combine", "random_mix", "adaptive_opcode"]:
            if c not in failed:
                print("[PICK] Stagnation({0}) -> forcing {1}".format(stagnant_count, c))
                return c
        failed.clear()
        return "max_coverage"

    if stagnant_count >= 15:
        # Try new strategies not yet tried
        new_strats = ["max_coverage","trap_trigger","opcode_funct3_sweep",
                      "adaptive_opcode","rd_sweep","genetic_combine"]
        for c in new_strats:
            if c not in failed:
                print("[PICK] Stagnation({0}) -> new strat {1}".format(stagnant_count, c))
                return c

    # Gap-targeted selection
    gaps = [
        (100.0 - e, ["max_coverage","trap_trigger","opcode_funct3_sweep",
                     "adaptive_opcode","ecall_with_branches","rd_sweep",
                     "exception_heavy","genetic_combine"]),
        (100.0 - b, ["mispredict_force","data_dependent_branch",
                     "always_taken_branch","always_not_taken","branch_and_store"]),
        (100.0 - s, ["store_buffer_fill","branch_and_store","max_coverage"]),
    ]
    gaps.sort(key=lambda x: x[0], reverse=True)
    for gap, strats in gaps:
        if gap > 0.1:
            for c in strats:
                if c not in failed:
                    return c

    # All targeted failed: rotate full list
    for c in STRATEGIES:
        if c not in failed:
            return c

    # Total exhaustion: reset and restart
    print("[PICK] All strategies exhausted - resetting blacklist")
    failed.clear()
    return STRATEGIES[i % len(STRATEGIES)]

def bar(name, pct):
    f = int(pct / 100.0 * 20)
    return "  {0:<22s} [{1}{2}] {3:.1f}%".format(name, "#"*f, "-"*(20-f), pct)

def main():
    sys.path.insert(0, BASE + "/fuzzer")
    from mutation_engine import STRATEGY_MAP, write_hex

    # Verify all new strategies are available
    missing = [s for s in STRATEGIES if s not in STRATEGY_MAP]
    if missing:
        print("[WARN] Missing strategies: {0}".format(missing))
        for s in missing:
            STRATEGIES.remove(s)

    try: os.makedirs(BASE + "/results")
    except: pass

    if not os.path.exists(SIMV):
        print("[ERROR] simv not found: {0}".format(SIMV))
        sys.exit(1)

    best_cov = best_b = best_s = best_e = 0.0
    failed = set()
    results = []
    strat = STRATEGIES[0]
    stagnant_count = 0  # consecutive rollbacks since last improvement

    print("=" * 64)
    print("  CVA6 Grey-Box Fuzzer  --  Group 7 EEE6323")
    print("  Simulator : Synopsys VCS  (simv)")
    print("  MAX_ITER={0}  GOAL={1}%  MIN_IMPROVE={2}%".format(
          MAX_ITER, COVERAGE_GOAL, MIN_IMPROVE))
    print("  Strategies: {0} available".format(len(STRATEGIES)))
    print("  Started   : {0}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 64)

    for i in range(MAX_ITER):
        print("\n" + "=" * 64)
        print("  ITER {0}/{1}  strategy={2}  best={3:.1f}%  stagnant={4}".format(
              i+1, MAX_ITER, strat, best_cov, stagnant_count))
        print("=" * 64)

        # 1. Generate hex
        fn = STRATEGY_MAP.get(strat, STRATEGY_MAP["random_mix"])
        instrs = fn(511)
        br   = sum(1 for x in instrs if (x&0x7F)==0x63)
        sys_ = sum(1 for x in instrs if (x&0x7F)==0x73)
        ill  = sum(1 for x in instrs if (x&0x7F) not in
                   [0x33,0x13,0x03,0x23,0x63,0x6F,0x67,0x37,0x17,0x73,0x0F,0x00])
        write_hex(instrs, HEX)
        print("[GEN] {0} instrs  BR={1}  SYS={2}  ILL={3}".format(
              len(instrs), br, sys_, ill))

        # 2. Simulate
        ok = run_sim("iter{0}".format(i+1))
        if not ok:
            failed.add(strat)
            stagnant_count += 1
            results.append({"iter":i+1,"strategy":strat,"action":"sim_error"})
            if os.path.exists(BEST): shutil.copy(BEST, HEX)
            strat = pick_strategy(best_b, best_s, best_e, failed, i+1, stagnant_count)
            continue

        # 3. Coverage
        b, s, e, retired, cycles = get_cov_from_log()
        total = (b + s + e) / 3.0
        imp   = total - best_cov
        print(bar("branch_cg", b))
        print(bar("store_cg",  s))
        print(bar("except_cg", e))
        print(bar("TOTAL",     total))
        print("[COV] retired={0}  cycles={1}  imp={2:+.2f}%".format(
              retired, cycles, imp))

        # 4. Hill-climb decision
        if total >= best_cov + MIN_IMPROVE:
            print("[CTRL] PROMOTION  +{0:.2f}%".format(imp))
            best_cov = total
            best_b, best_s, best_e = b, s, e
            shutil.copy(HEX, BEST)
            failed.clear()
            stagnant_count = 0
            action = "improved"
        else:
            print("[CTRL] ROLLBACK (stagnant={0})".format(stagnant_count))
            if os.path.exists(BEST): shutil.copy(BEST, HEX)
            failed.add(strat)
            stagnant_count += 1
            action = "rollback"

        results.append({
            "iter":i+1, "strategy":strat,
            "branch":round(b,2), "store":round(s,2), "except":round(e,2),
            "total":round(total,2), "best":round(best_cov,2),
            "retired":retired, "cycles":cycles, "action":action,
        })

        strat = pick_strategy(b, s, e, failed, i+1, stagnant_count)
        print("[NEXT] -> {0}".format(strat))

        # Progress checkpoint every 50 iters
        if (i+1) % 50 == 0:
            print("\n[CHECKPOINT] iter={0}  best={1:.2f}%  branch={2:.1f}%  store={3:.1f}%  except={4:.1f}%".format(
                  i+1, best_cov, best_b, best_s, best_e))
            with open(RESULTS, "w") as f:
                json.dump(results, f, indent=2)
            print("[CHECKPOINT] Results saved -> {0}".format(RESULTS))

        if best_cov >= COVERAGE_GOAL:
            print("[FUZZER] Goal {0}% reached at iter {1}!".format(COVERAGE_GOAL, i+1))
            break

    # Final report
    print("\n" + "=" * 64)
    print("  FUZZER COMPLETE  --  Best: {0:.2f}%".format(best_cov))
    print(bar("branch_cg", best_b))
    print(bar("store_cg",  best_s))
    print(bar("except_cg", best_e))
    print("")

    # Strategy performance summary
    strat_scores = {}
    for r in results:
        sn = r.get("strategy","")
        if sn not in strat_scores:
            strat_scores[sn] = {"best":0.0, "count":0, "improved":0}
        strat_scores[sn]["count"] += 1
        if r.get("total",0) > strat_scores[sn]["best"]:
            strat_scores[sn]["best"] = r.get("total",0)
        if r.get("action") == "improved":
            strat_scores[sn]["improved"] += 1

    print("  Strategy Performance Summary:")
    print("  {0:<26s} {1:>8s} {2:>6s} {3:>8s}".format(
          "strategy","best%","runs","improved"))
    print("  " + "-"*52)
    for sn,sc in sorted(strat_scores.items(), key=lambda x:-x[1]["best"]):
        print("  {0:<26s} {1:7.1f}%  {2:4d}   {3:4d}".format(
              sn, sc["best"], sc["count"], sc["improved"]))

    print("")
    print("  {0:>4s}  {1:<26s}  {2:>7s}  {3:>7s}  {4}".format(
          "iter","strategy","total%","retird","action"))
    print("  " + "-"*58)
    for r in results:
        mk = "+" if r.get("action") == "improved" else "-"
        print("  {0} {1:03d}  {2:<26s}  {3:5.1f}%  {4:6d}   {5}".format(
              mk, r["iter"], r.get("strategy",""),
              r.get("total",0.0), r.get("retired",0), r.get("action","")))
    print("=" * 64)

    with open(RESULTS, "w") as f:
        json.dump(results, f, indent=2)
    print("[OUT] Results -> {0}".format(RESULTS))
    print("[OUT] Best    -> {0}".format(BEST))

if __name__ == "__main__":
    main()
