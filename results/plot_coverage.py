#!/usr/bin/env python
import json, os, sys
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE    = "/home/UFAD/atish.maragur/FUZZER_PROJECT"
RESULTS = BASE + "/results/fuzzer_results.json"
OUTPUT  = BASE + "/results/coverage_report.png"

# -- Load results ------------------------------------------------------
with open(RESULTS) as f:
    data = json.load(f)

iters     = [r["iter"]     for r in data]
branch    = [r.get("branch", 0) for r in data]
store     = [r.get("store",  0) for r in data]
excpt     = [r.get("except", 0) for r in data]
total     = [r.get("total",  0) for r in data]
best      = [r.get("best",   0) for r in data]
strategies= [r.get("strategy","") for r in data]
retired   = [r.get("retired", 0) for r in data]
actions   = [r.get("action", "") for r in data]

# -- Colors ------------------------------------------------------------
C_BRANCH = "#E74C3C"
C_STORE  = "#2ECC71"
C_EXCEPT = "#3498DB"
C_TOTAL  = "#9B59B6"
C_BEST   = "#F39C12"
C_BG     = "#1A1A2E"
C_PANEL  = "#16213E"
C_TEXT   = "#EAEAEA"
C_GRID   = "#2C2C54"

# -- Figure setup ------------------------------------------------------
fig = plt.figure(figsize=(18, 14), facecolor=C_BG)
fig.suptitle("CVA6 Grey-Box Hardware Fuzzer  Coverage Report\nGroup 7 | EEE6323 | University of Florida",
             color=C_TEXT, fontsize=16, fontweight='bold', y=0.98)

gs = fig.add_gridspec(3, 3, hspace=0.45, wspace=0.35,
                      left=0.07, right=0.97, top=0.92, bottom=0.07)

# -- Plot 1: Coverage per iteration (line) -----------------------------
ax1 = fig.add_subplot(gs[0, :2])
ax1.set_facecolor(C_PANEL)
ax1.plot(iters, branch, 'o-', color=C_BRANCH, linewidth=2, markersize=6, label='branch_cg')
ax1.plot(iters, store,  's-', color=C_STORE,  linewidth=2, markersize=6, label='store_cg')
ax1.plot(iters, excpt,  '^-', color=C_EXCEPT, linewidth=2, markersize=6, label='except_cg')
ax1.plot(iters, total,  'D-', color=C_TOTAL,  linewidth=2, markersize=6, label='total')
ax1.plot(iters, best,   '--', color=C_BEST,   linewidth=2, markersize=4, label='best')
ax1.axhline(y=60, color='white', linestyle=':', linewidth=1, alpha=0.5, label='goal 60%')
# Mark improved iterations
for i, (it, act) in enumerate(zip(iters, actions)):
    if act == "improved":
        ax1.axvline(x=it, color=C_BEST, alpha=0.3, linewidth=1)
        ax1.annotate('+', (it, total[i]+1), color=C_BEST,
                    fontsize=10, ha='center', fontweight='bold')
ax1.set_xlabel("Iteration", color=C_TEXT)
ax1.set_ylabel("Coverage %", color=C_TEXT)
ax1.set_title("Coverage Progression per Iteration", color=C_TEXT, fontsize=12)
ax1.set_xlim(0.5, len(iters)+0.5)
ax1.set_ylim(0, 105)
ax1.set_xticks(iters)
ax1.tick_params(colors=C_TEXT)
ax1.grid(True, color=C_GRID, alpha=0.5)
ax1.legend(loc='upper right', facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=9)
for spine in ax1.spines.values():
    spine.set_edgecolor(C_GRID)

# -- Plot 2: Final covergroup bar chart --------------------------------
ax2 = fig.add_subplot(gs[0, 2])
ax2.set_facecolor(C_PANEL)
cg_names  = ['branch_cg', 'store_cg', 'except_cg', 'TOTAL']
cg_values = [branch[-1] if branch else 0,
             store[-1]  if store  else 0,
             excpt[-1]  if excpt  else 0,
             total[-1]  if total  else 0]
cg_colors = [C_BRANCH, C_STORE, C_EXCEPT, C_TOTAL]
bars = ax2.barh(cg_names, cg_values, color=cg_colors, height=0.5)
ax2.axvline(x=60, color='white', linestyle=':', linewidth=1, alpha=0.5)
for bar, val in zip(bars, cg_values):
    ax2.text(min(val+1, 95), bar.get_y()+bar.get_height()/2,
             '{0:.1f}%'.format(val), va='center', color=C_TEXT, fontsize=10)
ax2.set_xlim(0, 110)
ax2.set_xlabel("Coverage %", color=C_TEXT)
ax2.set_title("Final Coverage\nby Covergroup", color=C_TEXT, fontsize=11)
ax2.tick_params(colors=C_TEXT)
ax2.grid(True, axis='x', color=C_GRID, alpha=0.5)
for spine in ax2.spines.values():
    spine.set_edgecolor(C_GRID)

# -- Plot 3: Strategy used per iteration -------------------------------
ax3 = fig.add_subplot(gs[1, :2])
ax3.set_facecolor(C_PANEL)
unique_strats = list(set(strategies))
strat_colors = plt.cm.Set3(np.linspace(0, 1, len(unique_strats)))
strat_color_map = {s: strat_colors[i] for i,s in enumerate(unique_strats)}
bar_colors = [strat_color_map[s] for s in strategies]
bars3 = ax3.bar(iters, total, color=bar_colors, width=0.7, alpha=0.85)
# Add strategy labels
for it, strat, tot in zip(iters, strategies, total):
    short = strat.replace("_branch","_br").replace("buffer","buf").replace("coverage","cov")
    ax3.text(it, tot+0.5, short, ha='center', va='bottom',
             color=C_TEXT, fontsize=7, rotation=45)
ax3.set_xlabel("Iteration", color=C_TEXT)
ax3.set_ylabel("Total Coverage %", color=C_TEXT)
ax3.set_title("Coverage per Iteration by Strategy", color=C_TEXT, fontsize=12)
ax3.set_xlim(0.5, len(iters)+0.5)
ax3.set_ylim(0, 115)
ax3.set_xticks(iters)
ax3.tick_params(colors=C_TEXT)
ax3.grid(True, axis='y', color=C_GRID, alpha=0.5)
patches = [mpatches.Patch(color=strat_color_map[s], label=s) for s in unique_strats]
ax3.legend(handles=patches, loc='upper right', facecolor=C_PANEL,
           labelcolor=C_TEXT, fontsize=8, ncol=2)
for spine in ax3.spines.values():
    spine.set_edgecolor(C_GRID)

# -- Plot 4: Retired instructions per iteration ------------------------
ax4 = fig.add_subplot(gs[1, 2])
ax4.set_facecolor(C_PANEL)
ret_colors = [C_BEST if r > 1 else C_BRANCH for r in retired]
ax4.bar(iters, retired, color=ret_colors, width=0.6)
ax4.set_xlabel("Iteration", color=C_TEXT)
ax4.set_ylabel("Instructions", color=C_TEXT)
ax4.set_title("Retired Instructions\nper Iteration", color=C_TEXT, fontsize=11)
ax4.set_xticks(iters)
ax4.tick_params(colors=C_TEXT)
ax4.grid(True, axis='y', color=C_GRID, alpha=0.5)
for spine in ax4.spines.values():
    spine.set_edgecolor(C_GRID)

# -- Plot 5: Bin coverage heatmap --------------------------------------
ax5 = fig.add_subplot(gs[2, :2])
ax5.set_facecolor(C_PANEL)
bin_names = [
    'branch.taken', 'branch.not_taken', 'branch.correct',
    'branch.mispredict', 'store.idle', 'store.busy',
    'except.clean', 'except.trap', 'except.system',
    'except.store', 'except.branch', 'except.alu'
]
# Known coverage from vcover report
bin_coverage = [0,0,0,0,100,0,100,0,0,0,0,0]
colors_heat = ['#2ECC71' if v==100 else '#E74C3C' if v==0 else '#F39C12'
               for v in bin_coverage]
bars5 = ax5.barh(range(len(bin_names)), bin_coverage, color=colors_heat, height=0.6)
ax5.set_yticks(range(len(bin_names)))
ax5.set_yticklabels(bin_names, color=C_TEXT, fontsize=9)
ax5.set_xlabel("Hit Count %", color=C_TEXT)
ax5.set_title("Individual Bin Coverage Status", color=C_TEXT, fontsize=12)
ax5.set_xlim(0, 120)
ax5.tick_params(colors=C_TEXT)
ax5.grid(True, axis='x', color=C_GRID, alpha=0.5)
covered_patch   = mpatches.Patch(color='#2ECC71', label='Covered')
uncovered_patch = mpatches.Patch(color='#E74C3C', label='Uncovered (ZERO)')
ax5.legend(handles=[covered_patch, uncovered_patch],
           facecolor=C_PANEL, labelcolor=C_TEXT, fontsize=9, loc='lower right')
for spine in ax5.spines.values():
    spine.set_edgecolor(C_GRID)

# -- Plot 6: Summary stats ---------------------------------------------
ax6 = fig.add_subplot(gs[2, 2])
ax6.set_facecolor(C_PANEL)
ax6.axis('off')
best_total = max(total) if total else 0
improved   = sum(1 for a in actions if a == "improved")
stats_text = [
    ("Framework",      "CVA6 Grey-Box Fuzzer"),
    ("Group",          "Group 7 - EEE6323"),
    ("Tool",           "Questa Sim 2023.3"),
    ("Iterations",     str(len(data))),
    ("Best Coverage",  "{0:.1f}%".format(best_total)),
    ("branch_cg",      "{0:.1f}%".format(max(branch) if branch else 0)),
    ("store_cg",       "{0:.1f}%".format(max(store) if store else 0)),
    ("except_cg",      "{0:.1f}%".format(max(excpt) if excpt else 0)),
    ("Improvements",   "{0}/{1}".format(improved, len(data))),
    ("Strategies",     str(len(set(strategies)))),
    ("Covered Bins",   "2 / 16"),
    ("UCDB",           "coverage.ucdb"),
]
y = 0.97
for label, value in stats_text:
    ax6.text(0.05, y, label + ":", color="#AAAAAA", fontsize=9,
             transform=ax6.transAxes, va='top')
    ax6.text(0.55, y, value, color=C_TEXT, fontsize=9, fontweight='bold',
             transform=ax6.transAxes, va='top')
    y -= 0.075
ax6.set_title("Run Summary", color=C_TEXT, fontsize=11)

# -- Save --------------------------------------------------------------
plt.savefig(OUTPUT, dpi=150, bbox_inches='tight', facecolor=C_BG)
print("[PLOT] Saved: {0}".format(OUTPUT))
plt.close()
