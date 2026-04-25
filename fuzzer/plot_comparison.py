#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, division
import json, os, sys, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE    = "/home/UFAD/atish.maragur/FUZZER_PROJECT"
AFL_RESULTS       = "/tmp/fuzzer_results.json"
CONVERGE_RESULTS  = "/tmp/converge_results.json"
OUTPUT            = BASE + "/results/coverage_comparison.png"

try: os.makedirs(BASE + "/results")
except OSError: pass

C_BG      = "#0F0F1A"
C_PANEL   = "#161628"
C_TEXT    = "#E8E8F0"
C_GRID    = "#2A2A45"
C_BRANCH  = "#FF6B6B"
C_STORE   = "#51CF66"
C_EXCEPT  = "#339AF0"
C_TOTAL   = "#CC5DE8"
C_BEST    = "#FCC419"
C_LINE    = "#FF922B"
C_COND    = "#20C997"
C_TOGGLE  = "#845EF7"
C_PROMO   = "#FCC419"
C_REJECT  = "#495057"

def load_json(path):
    if not os.path.exists(path):
        print("[WARN] Not found: {0}".format(path))
        return None
    with open(path) as f:
        return json.load(f)

afl_data = load_json(AFL_RESULTS)
conv_raw = load_json(CONVERGE_RESULTS)

conv_data = None
conv_final_func = {}
conv_final_code = {}
if conv_raw:
    if isinstance(conv_raw, dict):
        conv_data = conv_raw.get("iterations", [])
        conv_final_func = conv_raw.get("final_functional", {})
        conv_final_code = conv_raw.get("final_code", {})
    elif isinstance(conv_raw, list):
        conv_data = conv_raw

def extract_series(data):
    if not data:
        return {}, 0
    iters    = [r["iter"] for r in data if "iter" in r]
    branch   = [r.get("branch", 0) for r in data if "iter" in r]
    store    = [r.get("store",  0) for r in data if "iter" in r]
    excpt    = [r.get("except", 0) for r in data if "iter" in r]
    total    = [r.get("total",  0) for r in data if "iter" in r]
    retired  = [r.get("retired", 0) for r in data if "iter" in r]
    promoted = [r.get("promoted", False) for r in data if "iter" in r]
    actions  = [r.get("action", "") for r in data if "iter" in r]
    best = []
    bmax = 0.0
    for t in total:
        bmax = max(bmax, t)
        best.append(bmax)
    code_line   = [r.get("code_line", None) for r in data if "iter" in r]
    code_cond   = [r.get("code_cond", None) for r in data if "iter" in r]
    code_toggle = [r.get("code_toggle", None) for r in data if "iter" in r]
    return {
        "iters": iters, "branch": branch, "store": store, "except": excpt,
        "total": total, "best": best, "retired": retired, "promoted": promoted,
        "actions": actions, "code_line": code_line, "code_cond": code_cond,
        "code_toggle": code_toggle,
    }, len(iters)

afl_s, afl_n = extract_series(afl_data)
conv_s, conv_n = extract_series(conv_data)

n_rows = 4
n_cols = 3
fig = plt.figure(figsize=(22, 20), facecolor=C_BG)
fig.suptitle("CVA6 Grey-Box Hardware Fuzzer -- Coverage Progress Dashboard\n"
             "Group 7 | EEE6323 | University of Florida",
             color=C_TEXT, fontsize=17, fontweight='bold', y=0.98)

gs = fig.add_gridspec(n_rows, n_cols, hspace=0.45, wspace=0.35,
                      left=0.06, right=0.97, top=0.93, bottom=0.04)

def style_ax(ax, title=""):
    ax.set_facecolor(C_PANEL)
    ax.set_title(title, color=C_TEXT, fontsize=11, fontweight='bold')
    ax.tick_params(colors=C_TEXT)
    ax.grid(True, color=C_GRID, alpha=0.4)
    for sp in ax.spines.values():
        sp.set_edgecolor(C_GRID)

if afl_s:
    ax1 = fig.add_subplot(gs[0, :2])
    style_ax(ax1, "Phase 1: AFL-Style Fuzzer ({0} iterations)".format(afl_n))
    ax1.plot(afl_s["iters"], afl_s["branch"], '-', color=C_BRANCH, lw=1.5, alpha=0.7, label='branch_cg')
    ax1.plot(afl_s["iters"], afl_s["store"],  '-', color=C_STORE,  lw=1.5, alpha=0.7, label='store_cg')
    ax1.plot(afl_s["iters"], afl_s["except"], '-', color=C_EXCEPT, lw=1.5, alpha=0.7, label='except_cg')
    ax1.plot(afl_s["iters"], afl_s["best"],   '--', color=C_BEST,  lw=2.5, label='best total')
    for j, p in enumerate(afl_s["promoted"]):
        if p:
            ax1.axvline(x=afl_s["iters"][j], color=C_PROMO, alpha=0.15, lw=1)
    ax1.set_xlabel("Iteration", color=C_TEXT)
    ax1.set_ylabel("Coverage %", color=C_TEXT)
    ax1.set_ylim(0, 105)
    ax1.legend(loc='lower right', facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=8)

if afl_s:
    ax2 = fig.add_subplot(gs[0, 2])
    style_ax(ax2, "Phase 1 Final Coverage")
    names = ['branch', 'store', 'except', 'TOTAL']
    vals  = [afl_s["branch"][-1], afl_s["store"][-1], afl_s["except"][-1], afl_s["total"][-1]]
    colors = [C_BRANCH, C_STORE, C_EXCEPT, C_TOTAL]
    bars = ax2.barh(names, vals, color=colors, height=0.55)
    for b, v in zip(bars, vals):
        ax2.text(min(v + 1, 95), b.get_y() + b.get_height() / 2,
                 '{0:.1f}%'.format(v), va='center', color=C_TEXT, fontsize=9)
    ax2.set_xlim(0, 110)
    ax2.set_xlabel("Coverage %", color=C_TEXT)

if conv_s:
    ax3 = fig.add_subplot(gs[1, :2])
    style_ax(ax3, "Phase 2: Convergence Fuzzer ({0} iterations)".format(conv_n))
    ax3.plot(conv_s["iters"], conv_s["except"], '-', color=C_EXCEPT, lw=1.5, alpha=0.7, label='except_cg')
    ax3.plot(conv_s["iters"], conv_s["best"],   '--', color=C_BEST,  lw=2.5, label='best total')
    for j, p in enumerate(conv_s["promoted"]):
        if p:
            ax3.axvline(x=conv_s["iters"][j], color=C_PROMO, alpha=0.2, lw=1)
    cl = [v for v in conv_s["code_line"] if v is not None]
    if cl:
        cl_iters = [conv_s["iters"][j] for j, v in enumerate(conv_s["code_line"]) if v is not None]
        ax3.plot(cl_iters, cl, 's-', color=C_LINE, lw=2, ms=5, label='code line%')
    ax3.set_xlabel("Iteration", color=C_TEXT)
    ax3.set_ylabel("Coverage %", color=C_TEXT)
    ax3.set_ylim(0, 105)
    ax3.legend(loc='lower right', facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=8)
else:
    ax3 = fig.add_subplot(gs[1, :2])
    style_ax(ax3, "Phase 2: Convergence (not yet run)")
    ax3.text(0.5, 0.5, "Run run_vcs_fuzzer then run_converge_full to populate",
             transform=ax3.transAxes, ha='center', va='center', color='#666', fontsize=12)

ax4 = fig.add_subplot(gs[1, 2])
style_ax(ax4, "Code vs Functional Coverage")
if conv_final_code and conv_final_func:
    names_code = ['Line', 'Cond', 'Branch', 'Toggle']
    vals_code  = [conv_final_code.get("line", 0), conv_final_code.get("cond", 0),
                  conv_final_code.get("branch", 0), conv_final_code.get("toggle", 0)]
    names_func = ['cg_branch', 'cg_store', 'cg_except']
    vals_func  = [conv_final_func.get("cg_branch", 0), conv_final_func.get("cg_store_buf", 0),
                  conv_final_func.get("cg_exception", 0)]
    all_names  = names_func + [''] + names_code
    all_vals   = vals_func + [0] + vals_code
    all_colors = [C_BRANCH, C_STORE, C_EXCEPT, C_BG, C_LINE, C_COND, C_BRANCH, C_TOGGLE]
    y_pos = list(range(len(all_names)))
    bars4 = ax4.barh(y_pos, all_vals, color=all_colors[:len(all_names)], height=0.55)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(all_names, color=C_TEXT, fontsize=8)
    for b, v in zip(bars4, all_vals):
        if v > 0:
            ax4.text(min(v + 1, 95), b.get_y() + b.get_height() / 2,
                     '{0:.1f}%'.format(v), va='center', color=C_TEXT, fontsize=8)
    ax4.set_xlim(0, 110)
    ax4.set_xlabel("Coverage %", color=C_TEXT)
    ax4.axhline(y=3, color=C_GRID, lw=1)
else:
    ax4.text(0.5, 0.5, "Available after\nconvergence run",
             transform=ax4.transAxes, ha='center', va='center', color='#666', fontsize=10)

ax5 = fig.add_subplot(gs[2, :2])
style_ax(ax5, "Discovery Timeline (promotions across both phases)")
timeline_iters  = []
timeline_totals = []
timeline_colors = []
offset = 0
if afl_s:
    for j, p in enumerate(afl_s["promoted"]):
        if p:
            timeline_iters.append(afl_s["iters"][j])
            timeline_totals.append(afl_s["total"][j])
            timeline_colors.append(C_EXCEPT)
    offset = afl_s["iters"][-1] if afl_s["iters"] else 0
if conv_s:
    for j, p in enumerate(conv_s["promoted"]):
        if p:
            timeline_iters.append(offset + conv_s["iters"][j])
            timeline_totals.append(conv_s["total"][j])
            timeline_colors.append(C_PROMO)
if timeline_iters:
    ax5.bar(range(len(timeline_iters)), timeline_totals, color=timeline_colors, width=0.7)
    ax5.set_xticks(range(len(timeline_iters)))
    ax5.set_xticklabels([str(i) for i in timeline_iters], rotation=45, fontsize=7, color=C_TEXT)
    ax5.set_ylabel("Total Coverage %", color=C_TEXT)
    ax5.set_xlabel("Iteration (discovery point)", color=C_TEXT)
    phase1_patch = mpatches.Patch(color=C_EXCEPT, label='Phase 1 (AFL)')
    phase2_patch = mpatches.Patch(color=C_PROMO,  label='Phase 2 (Converge)')
    ax5.legend(handles=[phase1_patch, phase2_patch], loc='lower right',
               facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=8)

ax6 = fig.add_subplot(gs[2, 2])
style_ax(ax6, "Mutator Effectiveness")
if conv_data:
    mut_promos = {}
    mut_total  = {}
    for r in conv_data:
        a = r.get("action", "")
        mut = a.split("(")[0] if "(" in a else a
        mut_total[mut]  = mut_total.get(mut, 0) + 1
        if r.get("promoted"):
            mut_promos[mut] = mut_promos.get(mut, 0) + 1
    if mut_total:
        muts   = sorted(mut_total.keys())
        rates  = [100.0 * mut_promos.get(m, 0) / mut_total[m] for m in muts]
        counts = [mut_total[m] for m in muts]
        y = list(range(len(muts)))
        bars6 = ax6.barh(y, rates, color=C_EXCEPT, height=0.6, alpha=0.8)
        ax6.set_yticks(y)
        ax6.set_yticklabels(muts, color=C_TEXT, fontsize=7)
        ax6.set_xlabel("Promotion rate %", color=C_TEXT)
        for b, v, c in zip(bars6, rates, counts):
            ax6.text(v + 0.5, b.get_y() + b.get_height() / 2,
                     '{0:.0f}% ({1})'.format(v, c), va='center', color=C_TEXT, fontsize=7)
elif afl_s:
    action_types = {"explore": 0, "mutate": 0, "anti-stag": 0}
    for a in afl_s["actions"]:
        for key in action_types:
            if key in a:
                action_types[key] += 1
                break
    if sum(action_types.values()) > 0:
        ax6.pie(list(action_types.values()),
                labels=list(action_types.keys()),
                colors=[C_EXCEPT, C_STORE, C_BRANCH],
                textprops={'color': C_TEXT, 'fontsize': 9},
                autopct='%1.0f%%', startangle=90)

ax7 = fig.add_subplot(gs[3, 0])
style_ax(ax7, "Instructions Retired")
if afl_s:
    ax7.plot(afl_s["iters"], afl_s["retired"], '.', color=C_EXCEPT, ms=4, alpha=0.6, label='AFL')
if conv_s:
    ax7.plot([i + offset for i in conv_s["iters"]], conv_s["retired"],
             '.', color=C_PROMO, ms=3, alpha=0.5, label='Converge')
ax7.set_xlabel("Iteration", color=C_TEXT)
ax7.set_ylabel("Retired count", color=C_TEXT)
ax7.legend(facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=8)

ax8 = fig.add_subplot(gs[3, 1])
style_ax(ax8, "except_cg Evolution (the bottleneck)")
all_exc       = []
all_exc_iters = []
if afl_s:
    all_exc.extend(afl_s["except"])
    all_exc_iters.extend(afl_s["iters"])
if conv_s:
    all_exc.extend(conv_s["except"])
    all_exc_iters.extend([i + offset for i in conv_s["iters"]])
if all_exc:
    ax8.plot(all_exc_iters, all_exc, '.', color=C_EXCEPT, ms=3, alpha=0.4)
    rmax = []
    m = 0
    for v in all_exc:
        m = max(m, v)
        rmax.append(m)
    ax8.plot(all_exc_iters, rmax, '-', color=C_BEST, lw=2, label='running max')
    if offset > 0:
        ax8.axvline(x=offset, color='white', ls=':', lw=1, alpha=0.5)
        ax8.text(offset + 2, 10, 'Phase 2 ->', color='#888', fontsize=8)
    ax8.set_xlabel("Iteration", color=C_TEXT)
    ax8.set_ylabel("except_cg %", color=C_TEXT)
    ax8.legend(facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=8)

ax9 = fig.add_subplot(gs[3, 2])
style_ax(ax9, "Run Summary")
ax9.axis('off')
stats = [("Framework", "AFL-style CGF + Convergence"),
         ("Group",     "Group 7 - EEE6323"),
         ("Simulator", "VCS W-2024.09")]
if afl_s:
    n_promos_afl = sum(1 for p in afl_s["promoted"] if p)
    stats.append(("Phase 1 iters",  str(afl_n)))
    stats.append(("Phase 1 best",   "{0:.1f}%".format(max(afl_s["total"]))))
    stats.append(("Phase 1 promos", str(n_promos_afl)))
if conv_s:
    n_promos_conv = sum(1 for p in conv_s["promoted"] if p)
    stats.append(("Phase 2 iters",  str(conv_n)))
    stats.append(("Phase 2 best",   "{0:.1f}%".format(max(conv_s["total"]))))
    stats.append(("Phase 2 promos", str(n_promos_conv)))
if conv_final_func:
    cum = sum(conv_final_func.values()) / max(len(conv_final_func), 1)
    stats.append(("Cumulative func", "{0:.1f}%".format(cum)))
if conv_final_code:
    stats.append(("Code line%",   "{0:.1f}%".format(conv_final_code.get("line", 0))))
    stats.append(("Code branch%", "{0:.1f}%".format(conv_final_code.get("branch", 0))))
y = 0.97
for label, value in stats:
    ax9.text(0.05, y, label + ":", color="#999", fontsize=9,
             transform=ax9.transAxes, va='top')
    ax9.text(0.55, y, value, color=C_TEXT, fontsize=9, fontweight='bold',
             transform=ax9.transAxes, va='top')
    y -= 0.075

plt.savefig(OUTPUT, dpi=150, bbox_inches='tight', facecolor=C_BG)
print("[PLOT] Saved: {0}".format(OUTPUT))
plt.savefig("/tmp/coverage_comparison.png", dpi=150, bbox_inches='tight', facecolor=C_BG)
print("[PLOT] Also saved: /tmp/coverage_comparison.png")
plt.close()
