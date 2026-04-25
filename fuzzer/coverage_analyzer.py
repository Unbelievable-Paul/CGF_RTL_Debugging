#!/usr/bin/env python

KNOWLEDGE = {
    ("cg_branch","cp_mispredict","mispredict"): ("Branch Predictor","core/frontend/bht.sv","data_dependent_branch"),
    ("cg_branch","cp_taken","not_taken"):       ("Branch Predictor","core/frontend/bht.sv","always_not_taken_branch"),
    ("cg_branch","cp_taken","taken"):           ("Branch Predictor","core/frontend/bht.sv","always_taken_branch"),
    ("cg_store_buf","cp_pending","busy"):       ("Store Buffer","core/store_unit.sv","store_buffer_fill"),
    ("cg_exception","cp_trap","trap"):          ("Exception Path","core/commit_stage.sv","deliberate_ecall"),
    ("cg_exception","cp_op","system"):          ("Exception Path","core/commit_stage.sv","deliberate_ecall"),
}

class MutationTarget(object):
    def __init__(self, rtl_block, rtl_file, priority, unhit_bins, strategy):
        self.rtl_block  = rtl_block
        self.rtl_file   = rtl_file
        self.priority   = priority
        self.unhit_bins = unhit_bins
        self.strategy   = strategy

def analyze(uncovered):
    targets={}
    for ub in uncovered:
        key=(ub.covergroup, ub.coverpoint, ub.bin_name)
        if key in KNOWLEDGE:
            rtl_block,rtl_file,strategy=KNOWLEDGE[key]
        else:
            rtl_block="unknown({0})".format(ub.covergroup)
            rtl_file="core/cva6.sv"; strategy="random_mix"
        if rtl_block not in targets:
            targets[rtl_block]=MutationTarget(rtl_block,rtl_file,ub.priority,[ub.bin_name],strategy)
        else:
            t=targets[rtl_block]
            t.priority=max(t.priority,ub.priority)
            t.unhit_bins.append(ub.bin_name)
            if strategy!="random_mix": t.strategy=strategy
    result=sorted(targets.values(), key=lambda t: t.priority, reverse=True)
    print("[ANALYZE] Targets:")
    for t in result:
        print("  [{0:.2f}] {1} strategy={2}".format(t.priority, t.rtl_block, t.strategy))
    return result
