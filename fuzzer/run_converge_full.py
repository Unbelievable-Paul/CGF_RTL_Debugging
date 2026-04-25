#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, division
import subprocess, os, sys, re, shutil, json, random, math
from datetime import datetime

BASE    = "/home/UFAD/atish.maragur/FUZZER_PROJECT"
HEX     = BASE + "/sim_work/sim_input.hex"
BEST    = "/tmp/converge_best.hex"
LOG     = "/tmp/vcs_sim.log"
VDB     = BASE + "/sim_work/coverage.vdb"
SIMV    = BASE + "/sim_work/simv"
RESULTS = "/tmp/converge_results.json"
CORPUS_IN  = "/tmp/fuzzer_corpus"
CORPUS_OUT = "/tmp/converge_corpus"
URG_RPT    = "/tmp/urg_converge"
URG_QUICK  = "/tmp/urg_quick"

MAX_ITER   = 100
ANNEAL_T0  = 2.0
ANNEAL_MIN = 0.05

SIMV_CMD = [SIMV, "-cm", "line+cond+fsm+branch+tgl",
            "-cm_dir", VDB, "-cm_nocopyright"]

def weighted_choice_idx(n, weights):
    total = sum(weights)
    r = random.uniform(0, total)
    acc = 0.0
    for i in range(n):
        acc += weights[i]
        if acc >= r:
            return i
    return n - 1

def weighted_choice(items, weights):
    return items[weighted_choice_idx(len(items), weights)]

def run_sim(iter_name):
    cmd = SIMV_CMD + ["-cm_name", iter_name]
    with open(LOG, "w") as lf:
        ret = subprocess.call(cmd, cwd=BASE, stdout=lf, stderr=lf)
    return ret == 0

def parse_log():
    b = s = e = 0.0; retired = 0; cycles = 0
    if not os.path.exists(LOG):
        return 0.0, 0.0, 0.0, 0, 0
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

def get_code_coverage():
    devnull = open(os.devnull, "w")
    subprocess.call(["urg", "-dir", VDB, "-format", "text", "-report", URG_QUICK],
                    stdout=devnull, stderr=devnull)
    devnull.close()
    result = {"line": 0.0, "cond": 0.0, "branch": 0.0, "toggle": 0.0, "fsm": 0.0}
    hier_path = URG_QUICK + "/hierarchy.txt"
    if not os.path.exists(hier_path):
        hier_path = URG_QUICK + "/dashboard.txt"
    if os.path.exists(hier_path):
        try:
            with open(hier_path) as f:
                for line in f:
                    m = re.search(r'([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+|-)\s+.*testbench', line)
                    if m:
                        result["line"] = float(m.group(1))
                        result["cond"] = float(m.group(2))
                        result["branch"] = float(m.group(3))
                        result["toggle"] = float(m.group(4))
                        if m.group(5) != "-":
                            result["fsm"] = float(m.group(5))
                        break
        except Exception:
            pass
    func = {"cg_branch": 0.0, "cg_store_buf": 0.0, "cg_exception": 0.0}
    for cand in [URG_QUICK + "/groups.txt", URG_QUICK + "/grpinfo/groups.txt"]:
        if os.path.exists(cand):
            try:
                with open(cand) as f:
                    for line in f:
                        m = re.search(r'(\d+\.\d+)\s+\d+\s+\d+.*?(cg_\w+|testbench::\w+)', line)
                        if m:
                            name = m.group(2).replace("testbench::", "")
                            func[name] = float(m.group(1))
            except Exception:
                pass
            break
    return result, func

def get_functional_cumulative():
    devnull = open(os.devnull, "w")
    subprocess.call(["urg", "-dir", VDB, "-format", "text", "-report", URG_RPT],
                    stdout=devnull, stderr=devnull)
    devnull.close()
    result = {}
    for cand in [URG_RPT + "/groups.txt", URG_RPT + "/grpinfo/groups.txt"]:
        if os.path.exists(cand):
            try:
                with open(cand) as f:
                    for line in f:
                        m = re.search(r'(\d+\.\d+)\s+\d+\s+\d+.*?(cg_\w+|testbench::\w+)', line)
                        if m:
                            result[m.group(2).replace("testbench::", "")] = float(m.group(1))
            except Exception:
                pass
            break
    return result

def bar(name, pct):
    f = int(pct / 100.0 * 20)
    return "  {0:<18s} [{1}{2}] {3:.1f}%".format(name, "#" * f, "-" * (20 - f), pct)

def fingerprint(b, s, e):
    return (int(b / 2) * 2, int(s / 2) * 2, int(e / 2) * 2)

def read_hex(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                val = int(line, 16)
                out.append(val & 0xFFFFFFFF)
                out.append((val >> 32) & 0xFFFFFFFF)
    except Exception:
        pass
    return out

def load_corpus(corpus_dir):
    corpus = []
    if not os.path.isdir(corpus_dir):
        return corpus
    for fname in sorted(os.listdir(corpus_dir)):
        if not fname.endswith(".hex"):
            continue
        instrs = read_hex(os.path.join(corpus_dir, fname))
        if instrs:
            corpus.append([instrs, 0.0, 0.0, 0.0, 0.0, fname])
    print("[CORPUS] Loaded {0} seeds from {1}".format(len(corpus), corpus_dir))
    return corpus

def _nop():
    return 0x00000013

def _random_valid_instr():
    SAFE_CSRS = [0xC00, 0xC01, 0xC02]
    def rr(): return random.randint(1, 15)
    def rdbin():
        b = random.randint(0, 7) * 4
        return b + random.randint(1, 3) if b > 0 else random.randint(1, 3)
    r = random.randint(0, 10)
    rd = rdbin()
    if r < 2:
        return (random.randint(0, 1) * 0x20) << 25 | rr() << 20 | rr() << 15 | random.randint(0, 7) << 12 | rd << 7 | 0x33
    elif r < 4:
        return (random.randint(0, 31) & 0xFFF) << 20 | rr() << 15 | random.randint(0, 7) << 12 | rd << 7 | 0x13
    elif r < 5:
        return rr() << 20 | 16 << 15 | random.randint(0, 2) << 12 | 0x23
    elif r < 6:
        return 16 << 15 | random.choice([0, 1, 2, 4, 5]) << 12 | rd << 7 | 0x03
    elif r < 7:
        return rr() << 20 | rr() << 15 | random.choice([0, 1, 4, 5, 6, 7]) << 12 | (4 << 8) | 0x63
    elif r < 8:
        return (random.randint(0, 0xFFFFF) << 12) | rd << 7 | 0x37
    elif r < 9:
        return random.choice(SAFE_CSRS) << 20 | rr() << 15 | random.choice([1, 2, 3, 5, 6, 7]) << 12 | rd << 7 | 0x73
    elif r < 10:
        return random.choice([0, 1]) << 20 | 0x73
    else:
        return 0x0FF0000F

CI_LEN = 20

def mut_bitflip(seed, n=1):
    s = list(seed)
    for _ in range(n):
        idx = random.randint(CI_LEN, len(s) - 1)
        s[idx] ^= (1 << random.randint(0, 31))
        s[idx] &= 0xFFFFFFFF
    return s

def mut_swap(seed):
    s = list(seed)
    s[random.randint(CI_LEN, len(s) - 1)] = _random_valid_instr()
    return s

def mut_swap2(seed):
    s = list(seed)
    a = random.randint(CI_LEN, len(s) - 1)
    b = random.randint(CI_LEN, len(s) - 1)
    s[a], s[b] = s[b], s[a]
    return s

def mut_insert(seed):
    s = list(seed)
    s.insert(random.randint(CI_LEN, len(s) - 1), _random_valid_instr())
    return s[:len(seed)]

def mut_delete(seed):
    s = list(seed)
    del s[random.randint(CI_LEN, len(s) - 1)]
    s.append(_nop())
    return s

def mut_splice(a, b):
    n = min(len(a), len(b))
    cut = random.randint(CI_LEN + 10, max(CI_LEN + 11, n - 10))
    return list(a[:cut]) + list(b[cut:n])

def mut_crossover(a, b):
    n = min(len(a), len(b))
    if n < CI_LEN + 30:
        return mut_splice(a, b)
    start = random.randint(CI_LEN + 5, n - 20)
    end = random.randint(start + 5, min(start + 100, n - 5))
    return (list(a[:start]) + list(b[start:end]) + list(a[end:]))[:n]

def mut_havoc_light(seed):
    s = list(seed)
    for _ in range(random.randint(2, 4)):
        op = random.choice(["bitflip", "swap", "insert", "delete"])
        if op == "bitflip": s = mut_bitflip(s, 1)
        elif op == "swap": s = mut_swap(s)
        elif op == "insert": s = mut_insert(s)
        elif op == "delete": s = mut_delete(s)
    return s

def mut_havoc_heavy(seed):
    s = list(seed)
    for _ in range(random.randint(8, 16)):
        op = random.choice(["bitflip", "swap", "swap2", "insert", "delete"])
        if op == "bitflip": s = mut_bitflip(s, 1)
        elif op == "swap": s = mut_swap(s)
        elif op == "swap2": s = mut_swap2(s)
        elif op == "insert": s = mut_insert(s)
        elif op == "delete": s = mut_delete(s)
    return s

def write_hex_with_trap(instrs, path):
    TRAP_ADDR = 0x2100
    MEPC_CSR = 0x341
    OP_SYSTEM = 0x73
    TRAP_HANDLER = [
        (MEPC_CSR & 0xFFF) << 20 | (0 << 15) | (2 << 12) | (14 << 7) | OP_SYSTEM,
        (4 & 0xFFF) << 20 | (14 << 15) | (14 << 7) | 0x13,
        (MEPC_CSR & 0xFFF) << 20 | (14 << 15) | (1 << 12) | (0 << 7) | OP_SYSTEM,
        0x30200073,
    ]
    instrs = [x if (x & 0x7F) != 0 else 0x00000013 for x in instrs]
    trap_idx = TRAP_ADDR // 4
    while len(instrs) < trap_idx:
        instrs.append(0x00000013)
    instrs = instrs[:trap_idx] + TRAP_HANDLER
    if len(instrs) % 2 == 1:
        instrs.append(0x00000013)
    with open(path, "w") as f:
        for i in range(0, len(instrs), 2):
            lo = instrs[i] & 0xFFFFFFFF
            hi = instrs[i + 1] & 0xFFFFFFFF
            f.write("%016X\n" % ((hi << 32) | lo))

MUT_SCORES = {
    "bitflip1": 1.0, "bitflip2": 1.0, "bitflip3": 1.0,
    "swap": 1.0, "swap2": 1.0, "insert": 1.0, "delete": 1.0,
    "splice": 1.0, "crossover": 1.0,
    "havoc_light": 1.0, "havoc_heavy": 1.0,
}

def pick_mutator():
    names = list(MUT_SCORES.keys())
    weights = [MUT_SCORES[n] for n in names]
    return weighted_choice(names, weights)

def apply_mutator(name, parent, corpus):
    if name == "bitflip1": return mut_bitflip(parent, 1)
    elif name == "bitflip2": return mut_bitflip(parent, 2)
    elif name == "bitflip3": return mut_bitflip(parent, 3)
    elif name == "swap": return mut_swap(parent)
    elif name == "swap2": return mut_swap2(parent)
    elif name == "insert": return mut_insert(parent)
    elif name == "delete": return mut_delete(parent)
    elif name == "splice":
        if len(corpus) > 1:
            return mut_splice(parent, corpus[random.randint(0, len(corpus) - 1)][0])
        return mut_swap(parent)
    elif name == "crossover":
        if len(corpus) > 1:
            return mut_crossover(parent, corpus[random.randint(0, len(corpus) - 1)][0])
        return mut_havoc_light(parent)
    elif name == "havoc_light": return mut_havoc_light(parent)
    elif name == "havoc_heavy": return mut_havoc_heavy(parent)
    else: return mut_swap(parent)

def main():
    random.seed()
    try: os.makedirs(CORPUS_OUT)
    except OSError: pass

    if not os.path.exists(SIMV):
        print("[ERROR] simv not found: {0}".format(SIMV))
        sys.exit(1)

    corpus = load_corpus(CORPUS_IN)
    if not corpus:
        print("[ERROR] No corpus in {0}. Run run_vcs_fuzzer first!".format(CORPUS_IN))
        sys.exit(1)

    print("=" * 64)
    print("  CVA6 Convergence Fuzzer (Code + Functional Coverage)")
    print("  Group 7 | EEE6323 | Synopsys VCS W-2024.09")
    print("  Corpus     : {0} seeds".format(len(corpus)))
    print("  MAX_ITER   : {0}".format(MAX_ITER))
    print("  Annealing  : T0={0} -> T_min={1}".format(ANNEAL_T0, ANNEAL_MIN))
    print("  Started    : {0}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 64)

    print("\n[INIT] Evaluating corpus seeds...")
    for ci, c in enumerate(corpus):
        write_hex_with_trap(c[0], HEX)
        if run_sim("warmup_{0:03d}".format(ci)):
            b, s, e, retired, cycles = parse_log()
            c[1] = (b + s + e) / 3.0
            c[2] = b; c[3] = s; c[4] = e
            print("  seed {0:2d}: total={1:.1f}%  b={2:.1f}  s={3:.1f}  e={4:.1f}  ret={5}".format(
                ci, c[1], b, s, e, retired))
        else:
            print("  seed {0:2d}: SIM FAILED".format(ci))

    print("\n[INIT] Baseline code coverage...")
    base_code, base_func = get_code_coverage()
    print("  Line   : {0:.1f}%".format(base_code["line"]))
    print("  Cond   : {0:.1f}%".format(base_code["cond"]))
    print("  Branch : {0:.1f}%".format(base_code["branch"]))
    print("  Toggle : {0:.1f}%".format(base_code["toggle"]))
    for name in sorted(base_func.keys()):
        print("  {0}: {1:.1f}%".format(name, base_func[name]))

    best_cov = max(c[1] for c in corpus) if corpus else 0.0
    best_line = base_code["line"]
    best_code_total = (base_code["line"] + base_code["cond"] + base_code["branch"] + base_code["toggle"]) / 4.0
    seen_fps = set()
    for c in corpus:
        seen_fps.add(fingerprint(c[2], c[3], c[4]))

    results = []
    promotions = 0
    temperature = ANNEAL_T0
    CODE_COV_INTERVAL = 25

    print("\n" + "=" * 64)
    print("  Starting convergence loop ({0} iterations)".format(MAX_ITER))
    print("=" * 64)

    for i in range(MAX_ITER):
        temperature = max(ANNEAL_MIN, ANNEAL_T0 * math.exp(-0.005 * i))
        weights = [max(0.5, c[4]) for c in corpus]
        parent_idx = weighted_choice_idx(len(corpus), weights)
        parent = corpus[parent_idx][0]
        mut_name = pick_mutator()
        child = apply_mutator(mut_name, parent, corpus)
        action = "{0}(p={1})".format(mut_name, parent_idx)

        if i > 0 and i % 50 == 0:
            print("\n  --- checkpoint i={0} | best={1:.1f}% | corpus={2} | T={3:.2f} | promos={4} ---\n".format(
                i, best_cov, len(corpus), temperature, promotions))

        write_hex_with_trap(child, HEX)
        ok = run_sim("conv_{0:04d}".format(i + 1))
        if not ok:
            results.append({"iter": i + 1, "action": action, "sim_ok": False, "promoted": False})
            continue

        b, s, e, retired, cycles = parse_log()
        total = (b + s + e) / 3.0
        fp = fingerprint(b, s, e)

        code_improved = False
        code_cov = None
        if (i + 1) % CODE_COV_INTERVAL == 0:
            code_cov, _ = get_code_coverage()
            code_total = (code_cov["line"] + code_cov["cond"] + code_cov["branch"] + code_cov["toggle"]) / 4.0
            if code_total > best_code_total + 0.1:
                code_improved = True
                best_code_total = code_total
                best_line = code_cov["line"]

        promoted = False
        reason = ""

        if total > best_cov + 0.05:
            promoted = True
            reason = "func+{0:.1f}%".format(total - best_cov)

        if code_improved and not promoted:
            promoted = True
            reason = "code_improved"

        if fp not in seen_fps:
            seen_fps.add(fp)
            if not promoted and total > best_cov - 3.0:
                promoted = True
                reason = "novel({0},{1},{2})".format(fp[0], fp[1], fp[2])

        if not promoted and corpus:
            cmax_e = max(c[4] for c in corpus)
            if e > cmax_e + 0.3:
                promoted = True
                reason = "except+{0:.1f}%".format(e - cmax_e)

        if not promoted and total > best_cov - 10.0:
            delta = best_cov - total
            if delta < temperature * 5.0 and random.random() < math.exp(-delta / max(temperature, 0.01)):
                promoted = True
                reason = "anneal(d={0:.1f})".format(delta)

        if promoted:
            print("[+] {0:4d}  {1:<28s}  func={2:5.1f}%  e={3:.1f}%  ret={4:5d}  {5}".format(
                i + 1, action, total, e, retired, reason))
            corpus.append([list(child), total, b, s, e, action])
            write_hex_with_trap(child, os.path.join(CORPUS_OUT, "conv_{0:04d}.hex".format(i + 1)))
            if total > best_cov:
                best_cov = total
                shutil.copy(HEX, BEST)
            MUT_SCORES[mut_name] = MUT_SCORES.get(mut_name, 1.0) + 3.0
            promotions += 1
            if len(corpus) > 30:
                corpus.sort(key=lambda c: c[1], reverse=True)
                corpus = corpus[:30]
        else:
            if (i + 1) % 25 == 0:
                print("[ ] {0:4d}  {1:<28s}  func={2:5.1f}%  e={3:.1f}%  (sample)".format(
                    i + 1, action, total, e))

        for k in MUT_SCORES:
            MUT_SCORES[k] = max(0.5, MUT_SCORES[k] * 0.98)

        r = {"iter": i + 1, "action": action, "total": round(total, 2),
             "branch": round(b, 2), "store": round(s, 2), "except": round(e, 2),
             "retired": retired, "promoted": promoted, "reason": reason,
             "temperature": round(temperature, 3)}
        if code_cov:
            r["code_line"] = round(code_cov["line"], 2)
            r["code_cond"] = round(code_cov["cond"], 2)
            r["code_branch"] = round(code_cov["branch"], 2)
            r["code_toggle"] = round(code_cov["toggle"], 2)
        results.append(r)

    print("\n" + "=" * 64)
    print("  Running final URG cumulative merge...")
    final_code, final_func = get_code_coverage()

    print("\n  FUNCTIONAL COVERAGE (cumulative):")
    for name in sorted(final_func.keys()):
        print(bar(name, final_func[name]))
    func_total = sum(final_func.values()) / max(len(final_func), 1)
    print(bar("FUNC TOTAL", func_total))

    print("\n  CODE COVERAGE (cumulative):")
    print(bar("Line", final_code["line"]))
    print(bar("Condition", final_code["cond"]))
    print(bar("Branch", final_code["branch"]))
    print(bar("Toggle", final_code["toggle"]))
    code_total = (final_code["line"] + final_code["cond"] + final_code["branch"] + final_code["toggle"]) / 4.0
    print(bar("CODE AVG", code_total))

    print("\n  CONVERGENCE COMPLETE")
    print("  Per-iter best func : {0:.1f}%".format(best_cov))
    print("  Promotions         : {0}/{1}".format(promotions, MAX_ITER))
    print("  Final corpus       : {0}".format(len(corpus)))

    print("\n  Mutator scores:")
    for name, score in sorted(MUT_SCORES.items(), key=lambda x: x[1], reverse=True):
        print("    {0:<15s} {1:.2f}".format(name, score))

    print("\n  Promotions log:")
    for r in results:
        if r.get("promoted"):
            print("    i={0:4d} {1:<28s} func={2:.1f}% e={3:.1f}% {4}".format(
                r["iter"], r["action"], r.get("total", 0), r.get("except", 0), r.get("reason", "")))

    print("=" * 64)
    output = {
        "iterations": results,
        "final_functional": final_func,
        "final_code": final_code,
        "promotions": promotions,
        "corpus_size": len(corpus),
    }
    with open(RESULTS, "w") as f:
        json.dump(output, f, indent=2)
    print("[OUT] Results    -> {0}".format(RESULTS))
    print("[OUT] Best       -> {0}".format(BEST))
    print("[OUT] Corpus     -> {0}".format(CORPUS_OUT))

if __name__ == "__main__":
    main()
