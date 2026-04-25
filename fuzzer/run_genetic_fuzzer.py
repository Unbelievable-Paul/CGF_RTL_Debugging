#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, division
import subprocess, os, sys, re, shutil, json, random, math
from datetime import datetime

BASE    = "/home/UFAD/atish.maragur/FUZZER_PROJECT"
HEX     = BASE + "/sim_work/sim_input.hex"
BEST    = "/tmp/genetic_best.hex"
LOG     = "/tmp/vcs_sim.log"
VDB     = BASE + "/sim_work/coverage.vdb"
SIMV    = BASE + "/sim_work/simv"
RESULTS = "/tmp/genetic_results.json"
CORPUS_IN  = "/tmp/fuzzer_corpus"
CORPUS_OUT = "/tmp/genetic_corpus"
URG_RPT    = "/tmp/urg_genetic"

POPULATION_SIZE = 20
ELITE_COUNT     = 4
TOURNAMENT_SIZE = 3
MAX_GENERATIONS = 75
INDIVIDUALS_PER_GEN = 20
CROSSOVER_PROB  = 0.7
MUTATION_RATE_START = 0.8
MUTATION_RATE_END   = 0.2
DIVERSITY_BONUS = 2.0

MAX_ITER = MAX_GENERATIONS * INDIVIDUALS_PER_GEN

SIMV_CMD = [SIMV, "-cm", "line+cond+fsm+branch+tgl",
            "-cm_dir", VDB, "-cm_nocopyright"]

def run_sim(iter_name):
    cmd = SIMV_CMD + ["-cm_name", iter_name]
    with open(LOG, "w") as lf:
        ret = subprocess.call(cmd, cwd=BASE, stdout=lf, stderr=lf)
    return ret == 0

def parse_log():
    b = s = e = 0.0
    retired = 0
    cycles = 0
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

def fingerprint(b, s, e):
    return (int(b / 2) * 2, int(s / 2) * 2, int(e / 2) * 2)

def read_hex(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line: continue
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
        if not fname.endswith(".hex"): continue
        instrs = read_hex(os.path.join(corpus_dir, fname))
        if instrs: corpus.append(instrs)
    return corpus

def _nop():
    return 0x00000013

SAFE_CSRS = [0xC00, 0xC01, 0xC02]

def _rand_reg():
    return random.randint(1, 15)

def _rand_rd():
    base = random.randint(0, 7) * 4
    return base + random.randint(1, 3) if base > 0 else random.randint(1, 3)

def _random_instr_by_class(cls):
    rd = _rand_rd()
    if cls == "arith":
        return ((random.randint(0, 1) * 0x20) << 25) | (_rand_reg() << 20) | (_rand_reg() << 15) | (random.randint(0, 7) << 12) | (rd << 7) | 0x33
    elif cls == "imm":
        return ((random.randint(0, 31) & 0xFFF) << 20) | (_rand_reg() << 15) | (random.randint(0, 7) << 12) | (rd << 7) | 0x13
    elif cls == "store":
        return (_rand_reg() << 20) | (16 << 15) | (random.randint(0, 2) << 12) | 0x23
    elif cls == "load":
        return (16 << 15) | (random.choice([0, 1, 2, 4, 5]) << 12) | (rd << 7) | 0x03
    elif cls == "branch":
        return (_rand_reg() << 20) | (_rand_reg() << 15) | (random.choice([0, 1, 4, 5, 6, 7]) << 12) | (4 << 8) | 0x63
    elif cls == "lui":
        return ((random.randint(0, 0xFFFFF)) << 12) | (rd << 7) | 0x37
    elif cls == "csr":
        return (random.choice(SAFE_CSRS) << 20) | (_rand_reg() << 15) | (random.choice([1, 2, 3, 5, 6, 7]) << 12) | (rd << 7) | 0x73
    elif cls == "system":
        return (random.choice([0, 1]) << 20) | 0x73
    elif cls == "fence":
        return 0x0FF0000F
    return _nop()

_CLASS_WEIGHTS = [
    ("arith",  20), ("imm",    25), ("branch", 18), ("store",  10),
    ("load",   10), ("csr",     8), ("system",  4), ("lui",     3), ("fence",   2),
]

def _random_valid_instr():
    total = sum(w for _, w in _CLASS_WEIGHTS)
    r = random.uniform(0, total)
    acc = 0.0
    for cls, w in _CLASS_WEIGHTS:
        acc += w
        if acc >= r:
            return _random_instr_by_class(cls)
    return _nop()

def _classify(instr):
    op = instr & 0x7F
    return {0x33: "arith", 0x13: "imm", 0x23: "store", 0x03: "load",
            0x63: "branch", 0x37: "lui", 0x17: "auipc", 0x73: "system",
            0x0F: "fence", 0x6F: "jal", 0x67: "jalr"}.get(op, "nop")

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

def mut_swap_positions(seed):
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

def mut_class_preserve(seed):
    s = list(seed)
    idx = random.randint(CI_LEN, len(s) - 1)
    cls = _classify(s[idx])
    if cls in ("nop", "auipc", "jal", "jalr"):
        cls = random.choice(["arith", "imm", "branch", "csr"])
    s[idx] = _random_instr_by_class(cls)
    return s

def mut_class_diversify(seed):
    s = list(seed)
    idx = random.randint(CI_LEN, len(s) - 1)
    old_cls = _classify(s[idx])
    choices = [c for c, _ in _CLASS_WEIGHTS if c != old_cls]
    new_cls = random.choice(choices)
    s[idx] = _random_instr_by_class(new_cls)
    return s

def mut_funct3_flip(seed):
    s = list(seed)
    idx = random.randint(CI_LEN, len(s) - 1)
    op = s[idx] & 0x7F
    if op in (0x33, 0x13, 0x03, 0x23, 0x63, 0x73):
        f3_old = (s[idx] >> 12) & 0x7
        f3_new = random.randint(0, 7)
        while f3_new == f3_old:
            f3_new = random.randint(0, 7)
        s[idx] = (s[idx] & ~(0x7 << 12)) | (f3_new << 12)
    return s

def mut_reg_shuffle(seed):
    s = list(seed)
    idx = random.randint(CI_LEN, len(s) - 1)
    op = s[idx] & 0x7F
    if op == 0x33 or op == 0x63:
        rs1 = (s[idx] >> 15) & 0x1F
        rs2 = (s[idx] >> 20) & 0x1F
        s[idx] = (s[idx] & ~(0x1F << 15) & ~(0x1F << 20)) | (rs2 << 15) | (rs1 << 20)
    return s

def mut_dependency_chain(seed):
    s = list(seed)
    start = random.randint(CI_LEN, len(s) - 5)
    r1 = random.randint(1, 15)
    r2 = random.randint(1, 15)
    while r2 == r1: r2 = random.randint(1, 15)
    s[start]   = (0 << 25) | (r1 << 20) | (r2 << 15) | (0 << 12) | (r1 << 7) | 0x33
    s[start+1] = (0 << 25) | (r2 << 20) | (r1 << 15) | (0 << 12) | (r2 << 7) | 0x33
    s[start+2] = (0 << 25) | (r1 << 20) | (r2 << 15) | (0 << 12) | (r1 << 7) | 0x33
    s[start+3] = (0 << 25) | (r2 << 20) | (r1 << 15) | (0 << 12) | (r2 << 7) | 0x33
    return s

def mut_branch_pattern(seed):
    s = list(seed)
    start = random.randint(CI_LEN, len(s) - 10)
    r1 = 1; r2 = 1
    for i in range(6):
        if i % 2 == 0:
            s[start + i] = (r2 << 20) | (r1 << 15) | (0 << 12) | (4 << 8) | 0x63
        else:
            s[start + i] = (r2 << 20) | (r1 << 15) | (1 << 12) | (4 << 8) | 0x63
    return s

def mut_havoc(seed, intensity="light"):
    s = list(seed)
    n = random.randint(2, 5) if intensity == "light" else random.randint(8, 16)
    all_muts = [mut_bitflip, mut_swap, mut_insert, mut_delete,
                mut_class_preserve, mut_funct3_flip, mut_reg_shuffle]
    for _ in range(n):
        op = random.choice(all_muts)
        if op == mut_bitflip: s = op(s, 1)
        else: s = op(s)
    return s

def crossover_single_point(a, b):
    n = min(len(a), len(b))
    cut = random.randint(CI_LEN + 10, n - 10)
    return list(a[:cut]) + list(b[cut:n])

def crossover_two_point(a, b):
    n = min(len(a), len(b))
    if n < CI_LEN + 50: return crossover_single_point(a, b)
    p1 = random.randint(CI_LEN + 5, n // 2)
    p2 = random.randint(p1 + 10, n - 5)
    return list(a[:p1]) + list(b[p1:p2]) + list(a[p2:n])

def crossover_uniform(a, b):
    n = min(len(a), len(b))
    child = []
    for i in range(n):
        if i < CI_LEN: child.append(a[i])
        else: child.append(a[i] if random.random() < 0.5 else b[i])
    return child

def crossover_three_parent(a, b, c):
    n = min(len(a), len(b), len(c))
    child = []
    for i in range(n):
        if i < CI_LEN: child.append(a[i])
        else:
            if a[i] == b[i]: child.append(a[i])
            elif a[i] == c[i]: child.append(a[i])
            elif b[i] == c[i]: child.append(b[i])
            else: child.append(random.choice([a[i], b[i], c[i]]))
    return child

MUTATORS = [
    ("bitflip1",        lambda s: mut_bitflip(s, 1)),
    ("bitflip2",        lambda s: mut_bitflip(s, 2)),
    ("swap",            mut_swap),
    ("swap_pos",        mut_swap_positions),
    ("insert",          mut_insert),
    ("delete",          mut_delete),
    ("class_preserve",  mut_class_preserve),
    ("class_diversify", mut_class_diversify),
    ("funct3_flip",     mut_funct3_flip),
    ("reg_shuffle",     mut_reg_shuffle),
    ("dep_chain",       mut_dependency_chain),
    ("branch_pattern",  mut_branch_pattern),
    ("havoc_light",     lambda s: mut_havoc(s, "light")),
    ("havoc_heavy",     lambda s: mut_havoc(s, "heavy")),
]

def fitness(ind, seen_fps):
    b = ind["branch"]; s = ind["store"]; e = ind["except"]
    base = 0.4 * e + 0.3 * b + 0.3 * s
    fp = fingerprint(b, s, e)
    bonus = DIVERSITY_BONUS if fp not in seen_fps else 0.0
    return base + bonus

def tournament_select(population, k):
    candidates = random.sample(population, min(k, len(population)))
    return max(candidates, key=lambda x: x["fitness"])

def write_hex_with_trap(instrs, path):
    TRAP_ADDR = 0x2100; MEPC_CSR = 0x341; OP_SYSTEM = 0x73
    TRAP_HANDLER = [
        (MEPC_CSR & 0xFFF) << 20 | (0 << 15) | (2 << 12) | (14 << 7) | OP_SYSTEM,
        (4 & 0xFFF) << 20 | (14 << 15) | (14 << 7) | 0x13,
        (MEPC_CSR & 0xFFF) << 20 | (14 << 15) | (1 << 12) | (0 << 7) | OP_SYSTEM,
        0x30200073,
    ]
    instrs = [x if (x & 0x7F) != 0 else 0x00000013 for x in instrs]
    trap_idx = TRAP_ADDR // 4
    while len(instrs) < trap_idx: instrs.append(0x00000013)
    instrs = instrs[:trap_idx] + TRAP_HANDLER
    if len(instrs) % 2 == 1: instrs.append(0x00000013)
    with open(path, "w") as f:
        for i in range(0, len(instrs), 2):
            lo = instrs[i] & 0xFFFFFFFF
            hi = instrs[i + 1] & 0xFFFFFFFF
            f.write("%016X\n" % ((hi << 32) | lo))

def evaluate(instrs, iter_name):
    write_hex_with_trap(instrs, HEX)
    ok = run_sim(iter_name)
    if not ok: return None
    b, s, e, retired, cycles = parse_log()
    return {"instrs": instrs, "branch": b, "store": s, "except": e,
            "retired": retired, "cycles": cycles}

def main():
    random.seed()
    try: os.makedirs(CORPUS_OUT)
    except OSError: pass

    if not os.path.exists(SIMV):
        print("[ERROR] simv not found: {0}".format(SIMV)); sys.exit(1)

    raw_corpus = load_corpus(CORPUS_IN)
    if not raw_corpus:
        print("[ERROR] No corpus. Run run_vcs_fuzzer first!"); sys.exit(1)

    print("=" * 68)
    print("  CVA6 Genetic Algorithm Fuzzer")
    print("  Group 7 | EEE6323 | Synopsys VCS W-2024.09")
    print("  Reference     : Squillero & Tonda, MicroGP (2005)")
    print("  Population    : {0}".format(POPULATION_SIZE))
    print("  Generations   : {0}".format(MAX_GENERATIONS))
    print("  Per gen       : {0}".format(INDIVIDUALS_PER_GEN))
    print("  Total evals   : {0}".format(MAX_ITER))
    print("  Started       : {0}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 68)

    print("\n[INIT] Evaluating seed corpus ({0} seeds)...".format(len(raw_corpus)))
    population = []
    seen_fps = set()
    eval_counter = 0

    for idx, instrs in enumerate(raw_corpus[:POPULATION_SIZE]):
        eval_counter += 1
        r = evaluate(instrs, "init_{0:03d}".format(idx))
        if r is None: continue
        fp = fingerprint(r["branch"], r["store"], r["except"])
        seen_fps.add(fp)
        r["fitness"] = fitness(r, seen_fps)
        r["origin"]  = "seed_{0}".format(idx)
        population.append(r)
        print("  seed {0:2d}: fit={1:5.2f}  b={2:5.1f}  s={3:5.1f}  e={4:5.1f}  ret={5}".format(
            idx, r["fitness"], r["branch"], r["store"], r["except"], r["retired"]))

    while len(population) < POPULATION_SIZE and raw_corpus:
        parent = random.choice(raw_corpus)
        child = mut_havoc(parent, "light")
        eval_counter += 1
        r = evaluate(child, "pad_{0:03d}".format(eval_counter))
        if r is None: continue
        fp = fingerprint(r["branch"], r["store"], r["except"])
        seen_fps.add(fp)
        r["fitness"] = fitness(r, seen_fps)
        r["origin"]  = "init_pad"
        population.append(r)

    population.sort(key=lambda x: x["fitness"], reverse=True)
    print("\n[INIT] Population ready: best fitness = {0:.2f}".format(population[0]["fitness"]))

    all_evals = []
    best_ever = dict(population[0])
    mutator_usage   = {name: 0 for name, _ in MUTATORS}
    mutator_success = {name: 0 for name, _ in MUTATORS}
    generation_best = []

    print("\n" + "=" * 68)
    print("  Evolving for {0} generations x {1} individuals...".format(
        MAX_GENERATIONS, INDIVIDUALS_PER_GEN))
    print("=" * 68)

    for gen in range(MAX_GENERATIONS):
        mut_rate = MUTATION_RATE_START - (MUTATION_RATE_START - MUTATION_RATE_END) * (gen / float(MAX_GENERATIONS))
        population.sort(key=lambda x: x["fitness"], reverse=True)
        new_pop = [dict(p) for p in population[:ELITE_COUNT]]
        gen_improvements = 0

        for i in range(INDIVIDUALS_PER_GEN):
            p1 = tournament_select(population, TOURNAMENT_SIZE)
            if random.random() < CROSSOVER_PROB:
                p2 = tournament_select(population, TOURNAMENT_SIZE)
                r = random.random()
                if r < 0.4:
                    child = crossover_uniform(p1["instrs"], p2["instrs"])
                    origin = "xover_uniform"
                elif r < 0.7:
                    child = crossover_two_point(p1["instrs"], p2["instrs"])
                    origin = "xover_2point"
                elif r < 0.9:
                    p3 = tournament_select(population, TOURNAMENT_SIZE)
                    child = crossover_three_parent(p1["instrs"], p2["instrs"], p3["instrs"])
                    origin = "xover_3parent"
                else:
                    child = crossover_single_point(p1["instrs"], p2["instrs"])
                    origin = "xover_1point"
            else:
                child = list(p1["instrs"])
                origin = "clone"

            mut_used = None
            if random.random() < mut_rate:
                mut_name, mut_fn = random.choice(MUTATORS)
                child = mut_fn(child)
                mutator_usage[mut_name] += 1
                origin = origin + "+" + mut_name
                mut_used = mut_name

            eval_counter += 1
            r = evaluate(child, "g{0:03d}i{1:02d}".format(gen, i))
            if r is None: continue

            fp = fingerprint(r["branch"], r["store"], r["except"])
            is_novel = fp not in seen_fps
            seen_fps.add(fp)
            r["fitness"] = fitness(r, seen_fps)
            r["origin"]  = origin

            if r["fitness"] > best_ever["fitness"]:
                gen_improvements += 1
                if mut_used: mutator_success[mut_used] += 1
                best_ever = dict(r)
                shutil.copy(HEX, BEST)
                write_hex_with_trap(r["instrs"],
                    os.path.join(CORPUS_OUT, "best_g{0:03d}.hex".format(gen)))

            new_pop.append(r)
            all_evals.append({
                "gen": gen, "idx": i, "eval_n": eval_counter,
                "origin": origin,
                "branch": round(r["branch"], 2),
                "store":  round(r["store"], 2),
                "except": round(r["except"], 2),
                "total":  round((r["branch"] + r["store"] + r["except"]) / 3.0, 2),
                "fitness": round(r["fitness"], 3),
                "retired": r["retired"],
                "novel": is_novel,
                "mut_rate": round(mut_rate, 2),
            })

        population = new_pop[:POPULATION_SIZE]
        population.sort(key=lambda x: x["fitness"], reverse=True)

        gen_best = population[0]
        avg = sum(p["fitness"] for p in population) / len(population)
        generation_best.append({
            "gen": gen,
            "best_fitness": round(gen_best["fitness"], 3),
            "best_except":  round(gen_best["except"], 2),
            "avg_fitness":  round(avg, 3),
            "improvements": gen_improvements,
        })

        if gen % 5 == 0 or gen_improvements > 0:
            print("  gen {0:3d}  best={1:5.2f}  avg={2:5.2f}  e={3:5.1f}%  improv={4}  mr={5:.2f}".format(
                gen, gen_best["fitness"], avg, gen_best["except"], gen_improvements, mut_rate))

    print("\n" + "=" * 68)
    print("  EVOLUTION COMPLETE")
    print("  Best individual:")
    print("    fitness  : {0:.2f}".format(best_ever["fitness"]))
    print("    branch   : {0:.1f}%".format(best_ever["branch"]))
    print("    store    : {0:.1f}%".format(best_ever["store"]))
    print("    except   : {0:.1f}%".format(best_ever["except"]))
    print("    origin   : {0}".format(best_ever.get("origin", "?")))

    print("\n  Running final URG cumulative merge...")
    devnull = open(os.devnull, "w")
    subprocess.call(["urg", "-dir", VDB, "-format", "text", "-report", URG_RPT],
                    stdout=devnull, stderr=devnull)
    devnull.close()

    final_func = {}
    for cand in [URG_RPT + "/groups.txt", URG_RPT + "/grpinfo/groups.txt"]:
        if os.path.exists(cand):
            try:
                with open(cand) as f:
                    for line in f:
                        m = re.search(r'(\d+\.\d+)\s+\d+\s+\d+.*?(cg_\w+)', line)
                        if m: final_func[m.group(2)] = float(m.group(1))
            except Exception:
                pass
            break

    print("\n  CUMULATIVE FUNCTIONAL COVERAGE:")
    for name in sorted(final_func.keys()):
        f = int(final_func[name] / 100.0 * 20)
        print("  {0:<20s} [{1}{2}] {3:.1f}%".format(
            name, "#" * f, "-" * (20 - f), final_func[name]))
    if final_func:
        cum = sum(final_func.values()) / len(final_func)
        f = int(cum / 100.0 * 20)
        print("  {0:<20s} [{1}{2}] {3:.1f}%".format(
            "FUNC TOTAL", "#" * f, "-" * (20 - f), cum))

    print("\n  Mutator usage & success:")
    for name, _ in MUTATORS:
        used = mutator_usage[name]
        succ = mutator_success[name]
        rate = (100.0 * succ / used) if used > 0 else 0.0
        print("    {0:<17s} used={1:4d}  success={2:3d}  rate={3:5.1f}%".format(
            name, used, succ, rate))

    output = {
        "method": "genetic_algorithm",
        "reference": "Squillero & Tonda, MicroGP (2005)",
        "config": {
            "population_size": POPULATION_SIZE,
            "max_generations": MAX_GENERATIONS,
            "individuals_per_gen": INDIVIDUALS_PER_GEN,
            "elite_count": ELITE_COUNT,
            "tournament_size": TOURNAMENT_SIZE,
            "crossover_prob": CROSSOVER_PROB,
            "mutation_rate_start": MUTATION_RATE_START,
            "mutation_rate_end": MUTATION_RATE_END,
        },
        "evaluations": all_evals,
        "generation_stats": generation_best,
        "final_functional": final_func,
        "best_ever": {
            "fitness": round(best_ever["fitness"], 3),
            "branch":  round(best_ever["branch"], 2),
            "store":   round(best_ever["store"], 2),
            "except":  round(best_ever["except"], 2),
            "retired": best_ever["retired"],
            "origin":  best_ever.get("origin", "?"),
        },
        "mutator_usage":   mutator_usage,
        "mutator_success": mutator_success,
        "total_evaluations": eval_counter,
    }
    with open(RESULTS, "w") as f:
        json.dump(output, f, indent=2)
    print("\n[OUT] Results -> {0}".format(RESULTS))
    print("[OUT] Best    -> {0}".format(BEST))
    print("[OUT] Corpus  -> {0}".format(CORPUS_OUT))
    print("=" * 68)

if __name__ == "__main__":
    main()
