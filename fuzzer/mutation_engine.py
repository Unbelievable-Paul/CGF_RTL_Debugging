import random

OP_ALU_REG=0x33;OP_ALU_IMM=0x13;OP_LOAD=0x03;OP_STORE=0x23;OP_BRANCH=0x63
OP_JAL=0x6F;OP_JALR=0x67;OP_LUI=0x37;OP_AUIPC=0x17;OP_SYSTEM=0x73;OP_FENCE=0x0F

def _addi(rd,rs1,imm): return (imm&0xFFF)<<20|(rs1&0x1F)<<15|(rd&0x1F)<<7|OP_ALU_IMM
def _alu_imm(rd,rs1,imm,f3): return (imm&0xFFF)<<20|(rs1&0x1F)<<15|(f3&7)<<12|(rd&0x1F)<<7|OP_ALU_IMM
def _alu_reg(rd,rs1,rs2,f3,f7=0): return (f7&0x7F)<<25|(rs2&0x1F)<<20|(rs1&0x1F)<<15|(f3&7)<<12|(rd&0x1F)<<7|OP_ALU_REG
def _load(rd,rs1,imm,f3): return (imm&0xFFF)<<20|(rs1&0x1F)<<15|(f3&7)<<12|(rd&0x1F)<<7|OP_LOAD
def _store(rs1,rs2,imm,f3): return ((imm>>5)&0x7F)<<25|(rs2&0x1F)<<20|(rs1&0x1F)<<15|(f3&7)<<12|(imm&0x1F)<<7|OP_STORE
def _branch(rs1,rs2,imm,f3):
    imm=imm&0x1FFE
    return ((imm>>12)&1)<<31|((imm>>5)&0x3F)<<25|(rs2&0x1F)<<20|(rs1&0x1F)<<15|(f3&7)<<12|((imm>>1)&0xF)<<8|((imm>>11)&1)<<7|OP_BRANCH
def _lui(rd,imm): return ((imm&0xFFFFF)<<12)|(rd&0x1F)<<7|OP_LUI
def _auipc(rd,imm): return ((imm&0xFFFFF)<<12)|(rd&0x1F)<<7|OP_AUIPC
def _jal(rd,imm):
    i=imm&0x1FFFFF
    return (((i>>20)&1)<<31)|(((i>>1)&0x3FF)<<21)|(((i>>11)&1)<<20)|(((i>>12)&0xFF)<<12)|((rd&0x1F)<<7)|OP_JAL
def _jalr(rd,rs1,imm): return (imm&0xFFF)<<20|(rs1&0x1F)<<15|(rd&0x1F)<<7|OP_JALR
def _system(imm12): return (imm12&0xFFF)<<20|OP_SYSTEM
def _csr(rd,rs1,f3,csr): return (csr&0xFFF)<<20|(rs1&0x1F)<<15|(f3&7)<<12|(rd&0x1F)<<7|OP_SYSTEM
def _mret(): return 0x30200073
def _fence(): return 0x0FF0000F
def _fencei(): return 0x0000100F
def _nop(): return 0x00000013

SAFE_CSRS=[0xC00,0xC01,0xC02]   # cycle, time, instret (read-only, always safe)
MTVEC_CSR=0x305
MEPC_CSR=0x341
MSTATUS_CSR=0x300
PROG_LEN=2048     # 4x longer than before -> deeper pipeline exercise
TRAP_ADDR=0x2100  # byte address of trap handler, past the main program

# ---------------------------------------------------------------------------
# Boot block: sets up registers, configures mtvec for clean exception handling
# This is prepended to EVERY program and NEVER mutated.
# ---------------------------------------------------------------------------
CI_BLOCK = [
    # -- Set up mtvec to point to our trap handler at TRAP_ADDR --
    # LUI x15, upper20(TRAP_ADDR)   -> x15 = TRAP_ADDR & 0xFFFFF000
    _lui(15, TRAP_ADDR >> 12),
    # ADDI x15, x15, lower12        -> x15 = TRAP_ADDR
    _addi(15, 15, TRAP_ADDR & 0xFFF),
    # CSRRW x0, mtvec, x15          -> mtvec = x15  (f3=1)
    _csr(0, 15, 1, MTVEC_CSR),

    # -- Initialize registers with known values --
    _addi(1,0,1), _addi(2,0,2), _addi(3,0,3), _addi(4,0,4),
    _addi(5,0,5), _addi(6,0,6), _addi(7,0,7), _addi(8,0,8),
    _addi(9,0,9), _addi(10,0,10), _addi(11,0,11), _addi(12,0,12),
    _addi(13,0,13), _addi(14,0,14),

    # -- x16 = 0x400 (valid aligned memory base for loads/stores) --
    _lui(16, 0), _addi(16, 16, 0x400),

    _nop(), _nop(),  # pipeline settle
]

# Trap handler: placed AFTER the main program in the hex file.
# mepc += 4 (skip the faulting instruction), then MRET.
# This lets exceptions resolve cleanly so the program continues executing
# past ECALL/EBREAK/illegal instructions instead of hanging.
TRAP_HANDLER = [
    # csrrs x14, mepc, x0    -> x14 = mepc  (read mepc, f3=2)
    _csr(14, 0, 2, MEPC_CSR),
    # addi x14, x14, 4       -> x14 = mepc + 4  (skip faulting instr)
    _addi(14, 14, 4),
    # csrrw x0, mepc, x14    -> mepc = x14  (write back, f3=1)
    _csr(0, 14, 1, MEPC_CSR),
    # mret                   -> return to mepc
    _mret(),
]

def _rd_for_bin(b):
    base=b*4; return base+random.randint(1,3) if base>0 else random.randint(1,3)

def _random_valid_instr():
    r=random.randint(0,10);rd=_rd_for_bin(random.randint(0,7))
    if r<2: return _alu_reg(rd,random.randint(1,10),random.randint(1,10),random.randint(0,7))
    elif r<4: return _alu_imm(rd,random.randint(1,10),random.randint(0,31),random.randint(0,7))
    elif r<5: return _store(16,random.randint(1,10),0,random.randint(0,2))
    elif r<6: return _load(rd,16,0,random.choice([0,1,2,4,5]))
    elif r<7: return _branch(random.randint(1,5),random.randint(1,5),8,random.choice([0,1,4,5,6,7]))
    elif r<8: return _lui(rd,random.randint(0,0xFFFFF))
    elif r<9: return _csr(rd,random.randint(0,10),random.choice([1,2,3,5,6,7]),random.choice(SAFE_CSRS))
    elif r<10: return _system(random.choice([0,1]))
    else: return _fence()

# ===========================================================================
# STRATEGIES
# ===========================================================================
def strategy_cross_sweep(n=PROG_LEN):
    out=list(CI_BLOCK)
    for f3 in range(8): out.append(_alu_reg(_rd_for_bin(f3),1,2,f3,0))
    out.append(_alu_reg(5,1,2,0,0x20)); out.append(_alu_reg(6,1,2,5,0x20))
    for f3 in range(8): out.append(_alu_imm(_rd_for_bin(f3),1,random.randint(1,15),f3))
    for f3 in [0,1,4,5,6,7]: out.append(_branch(1,2,8,f3));out.append(_nop())
    for f3 in [0,1,2]: out.append(_store(16,_rd_for_bin(f3),0,f3))
    for f3 in [0,1,2,4,5]: out.append(_load(_rd_for_bin(f3 if f3<4 else f3-4),16,0,f3))
    for fb in range(8): out.append(_lui(_rd_for_bin(fb),(fb|(random.randint(1,0x1FFFF)<<3))&0xFFFFF))
    for fb in range(8): out.append(_auipc(_rd_for_bin(fb),(fb|(random.randint(1,0x1FFFF)<<3))&0xFFFFF))
    for fb in range(8): out.append(_jal(_rd_for_bin(fb),8|(fb<<12)));out.append(_nop())
    for rb in range(8): out.append(_jalr(_rd_for_bin(rb),0,0));out.append(_nop())
    out.append(_fence());out.append(_fencei())
    out.append(_system(0));out.append(_system(1))  # ECALL, EBREAK -> trap handler catches
    for f3 in [1,2,3,5,6,7]: out.append(_csr(_rd_for_bin(f3),random.randint(0,10),f3,SAFE_CSRS[f3%3]))
    while len(out)<n:
        rd=_rd_for_bin(random.randint(0,7));r=random.randint(0,11)
        if r<2: out.append(_alu_reg(rd,random.randint(1,10),random.randint(1,10),random.randint(0,7)))
        elif r<4: out.append(_alu_imm(rd,random.randint(1,10),random.randint(0,31),random.randint(0,7)))
        elif r<5: out.append(_store(16,random.randint(1,10),0,random.randint(0,2)))
        elif r<6: out.append(_load(rd,16,0,random.choice([0,1,2,4,5])))
        elif r<7: out.append(_branch(random.randint(1,5),random.randint(1,5),8,random.choice([0,1,4,5,6,7])));out.append(_nop())
        elif r<8: out.append(_lui(rd,random.randint(0,0xFFFFF)))
        elif r<9: out.append(_csr(rd,random.randint(0,10),random.choice([1,2,3,5,6,7]),random.choice(SAFE_CSRS)))
        elif r<10: out.append(_system(random.choice([0,1])))  # will trap -> handler catches
        elif r<11: out.append(_fence())
        else: out.append(0xFFFFFFFF)  # illegal instr -> trap handler catches
    return out[:n]

def strategy_always_taken_branch(n=PROG_LEN):
    out=list(CI_BLOCK)
    while len(out)<n:
        r=len(out)%4
        if r==0: out.append(_branch(1,1,8,0x0))
        elif r==1: out.append(_nop())
        elif r==2: out.append(_addi(random.randint(1,15),random.randint(1,10),random.randint(1,31)))
        else: out.append(_alu_reg(random.randint(1,15),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]

def strategy_always_not_taken(n=PROG_LEN):
    out=list(CI_BLOCK)
    while len(out)<n:
        r=len(out)%3
        if r==0: out.append(_branch(1,1,8,0x1))
        elif r==1: out.append(_alu_imm(random.randint(1,10),random.randint(1,10),random.randint(0,31),random.randint(0,7)))
        else: out.append(_nop())
    return out[:n]

def strategy_data_dependent_branch(n=PROG_LEN):
    out=list(CI_BLOCK);k=1
    while len(out)<n:
        r=len(out)%8
        if r==0: out.append(_addi(3,0,k&0xFFF))
        elif r==1: out.append(_addi(4,0,k&0xFFF))
        elif r==2: out.append(_branch(3,4,8,0x0))
        elif r==3: out.append(_nop())
        elif r==4: out.append(_addi(3,0,(k+1)&0xFFF))
        elif r==5: out.append(_addi(4,0,k&0xFFF))
        elif r==6: out.append(_branch(3,4,8,0x1))
        else: k=(k+7)%511+1;out.append(_nop())
    return out[:n]

def strategy_mispredict_force(n=PROG_LEN):
    out=list(CI_BLOCK);count=0
    while len(out)<n:
        sub=count%24
        if sub<20: out.append(_branch(1,1,8,0x0));out.append(_nop())
        else: out.append(_branch(1,1,8,0x1));out.append(_nop())
        out.append(_addi(random.randint(1,10),random.randint(1,10),random.randint(0,15)));count+=1
    return out[:n]

def strategy_store_buffer_fill(n=PROG_LEN):
    out=list(CI_BLOCK);offsets=[0,8,16,24,32,40,48,56]
    while len(out)<n:
        r=len(out)%10
        if r<6: out.append(_store(16,(r%9)+1,offsets[r%8],0x2))
        elif r<8: out.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
        elif r==8: out.append(_store(16,random.randint(1,9),0,0x1))
        else: out.append(_store(16,random.randint(1,9),0,0x0))
    return out[:n]

def strategy_deliberate_ecall(n=PROG_LEN):
    out=list(CI_BLOCK)
    while len(out)<n:
        r=len(out)%8
        if r==4: out.append(_system(0))
        elif r==6: out.append(_system(1))
        else: out.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]

def strategy_ecall_with_branches(n=PROG_LEN):
    out=list(CI_BLOCK)
    while len(out)<n:
        r=len(out)%12
        if r<3: out.append(_branch(1,1,8,0x0));out.append(_nop())
        elif r==3: out.append(_system(0))
        elif r==4: out.append(_addi(random.randint(1,10),0,random.randint(1,31)))
        elif r<8: out.append(_store(16,(r%9)+1,(r%8)*8,0x2))
        elif r==8: out.append(_branch(1,2,8,0x4))
        elif r==9: out.append(_nop())
        else: out.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]

def strategy_branch_and_store(n=PROG_LEN):
    out=list(CI_BLOCK);offsets=[0,8,16,24,32,40,48,56];k=1
    while len(out)<n:
        r=len(out)%9
        if r<4: out.append(_store(16,(r%9)+1,offsets[r],0x2))
        elif r==4: out.append(_branch(1,1,8,0x0))
        elif r==5: out.append(_nop())
        elif r==6: out.append(_branch((k%9)+1,((k+1)%9)+1,8,0x1))
        elif r==7: out.append(_addi((k%14)+1,0,(k*7)&0xFFF));k+=1
        else: out.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]

def strategy_illegal_instructions(n=PROG_LEN):
    out=list(CI_BLOCK)
    illegal=[0xFFFFFFFF,0x06000000,0x0C000000,0x5C000000,0x7C000000,0xA0000000]
    while len(out)<n:
        r=len(out)%12
        if r<4: out.append(_store(16,(r%9)+1,r*8,0x2))
        elif r==4: out.append(illegal[(len(out)//12)%len(illegal)])
        elif r==5: out.append(_branch(1,1,8,0x0))
        elif r==6: out.append(_nop())
        elif r==7: out.append(_branch(1,1,8,0x0))
        elif r==8: out.append(_nop())
        else: out.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]

def strategy_branch_sweep(n=PROG_LEN):
    out=list(CI_BLOCK);bf3=[0,1,4,5,6,7]
    while len(out)<n:
        f3=bf3[len(out)%len(bf3)];phase=(len(out)//len(bf3))%4
        if phase==0: out.append(_addi(3,0,1));out.append(_addi(4,0,2))
        elif phase==1: out.append(_addi(3,0,2));out.append(_addi(4,0,2))
        elif phase==2: out.append(_addi(3,0,5));out.append(_addi(4,0,1))
        else: out.append(_addi(3,0,0));out.append(_addi(4,0,0))
        out.append(_branch(3,4,8,f3));out.append(_nop())
        out.append(_alu_reg(_rd_for_bin(f3%8),1,2,random.randint(0,7)))
    return out[:n]

def strategy_load_sweep(n=PROG_LEN):
    out=list(CI_BLOCK);lf3=[0,1,2,4,5]
    while len(out)<n:
        f3=lf3[len(out)%len(lf3)]
        out.append(_load(_rd_for_bin(random.randint(0,7)),16,0,f3))
        out.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]

def strategy_csr_sweep(n=PROG_LEN):
    out=list(CI_BLOCK);cf3=[1,2,3,5,6,7]
    while len(out)<n:
        f3=cf3[len(out)%len(cf3)]
        out.append(_csr(_rd_for_bin(random.randint(0,7)),random.randint(0,10),f3,SAFE_CSRS[len(out)%3]))
        out.append(_alu_imm(random.randint(1,10),random.randint(1,10),random.randint(0,15),random.randint(0,7)))
    return out[:n]

def strategy_exception_heavy(n=PROG_LEN):
    out=list(CI_BLOCK);flat=[]
    for f in range(8): flat.append(_alu_imm(random.randint(1,10),random.randint(1,10),random.randint(0,15),f))
    for f in range(8): flat.append(_alu_reg(random.randint(1,10),random.randint(1,10),random.randint(1,10),f))
    for f in [0,1,4,5,6,7]: flat.append(_branch(1,2,8,f))
    for f in range(3): flat.append(_store(16,random.randint(1,10),0,f))
    for f in [0,1,2,4,5]: flat.append(_load(random.randint(1,15),16,0,f))
    for f in [1,2,3,5,6,7]: flat.append(_csr(random.randint(1,15),random.randint(0,10),f,0xC00))
    flat+=[_system(0),_system(1),_lui(1,0x100),_fence(),_fencei(),0xFFFFFFFF]
    idx=0
    while len(out)<n: out.append(flat[idx%len(flat)]);idx+=1
    return out[:n]

def strategy_mixed_coverage(n=PROG_LEN):
    out=list(CI_BLOCK);idx=0;BF3=[0,1,4,5,6,7]
    fns=[
        lambda i:_alu_reg(_rd_for_bin(i%8),1,2,i%8),
        lambda i:_alu_imm(_rd_for_bin(i%8),1,i%32,i%8),
        lambda i:_store(16,i%10+1,0,i%3),
        lambda i:_load(_rd_for_bin(i%8),16,0,[0,1,2,4,5][i%5]),
        lambda i:_branch(1,2,8,BF3[i%len(BF3)]),
        lambda i:_branch(1,1,8,0x0),
        lambda i:_lui(_rd_for_bin(i%8),i%0xFFFFF),
        lambda i:_auipc(_rd_for_bin(i%8),i%0xFFFFF),
        lambda i:_system(i%2),
        lambda i:_csr(_rd_for_bin(i%8),i%10,[1,2,3,5,6,7][i%6],0xC00),
        lambda i:_fence(),
    ]
    while len(out)<n: out.append(fns[idx%len(fns)](idx));idx+=1
    return out[:n]

def strategy_random_mix(n=PROG_LEN):
    out=list(CI_BLOCK)
    while len(out)<n:
        r=random.randint(0,10);rd=_rd_for_bin(random.randint(0,7))
        if r<2: out.append(_alu_reg(rd,random.randint(1,10),random.randint(1,10),random.randint(0,7)))
        elif r<4: out.append(_alu_imm(rd,random.randint(1,10),random.randint(0,31),random.randint(0,7)))
        elif r<5: out.append(_store(16,random.randint(1,10),0,random.randint(0,2)))
        elif r<6: out.append(_load(rd,16,0,random.choice([0,1,2,4,5])))
        elif r<7: out.append(_branch(random.randint(1,5),random.randint(1,5),8,random.choice([0,1,4,5,6,7])));out.append(_nop())
        elif r<8: out.append(_lui(rd,random.randint(0,0xFFFFF)))
        elif r<9: out.append(_auipc(rd,random.randint(0,0xFFFFF)))
        elif r<10: out.append(_csr(rd,random.randint(0,10),random.choice([1,2,3,5,6,7]),random.choice(SAFE_CSRS)))
        else: out.append(_system(random.choice([0,1])))
    return out[:n]

def strategy_full_sweep(n=PROG_LEN):
    chunk=(n-len(CI_BLOCK))//6
    strats=[strategy_cross_sweep,strategy_ecall_with_branches,strategy_branch_sweep,
            strategy_store_buffer_fill,strategy_load_sweep,strategy_csr_sweep]
    out=list(CI_BLOCK)
    for fn in strats:
        seg=fn(chunk+len(CI_BLOCK));out.extend(seg[len(CI_BLOCK):len(CI_BLOCK)+chunk])
    while len(out)<n: out.append(_alu_reg(random.randint(1,15),random.randint(1,10),random.randint(1,10),random.randint(0,7)))
    return out[:n]


STRATEGY_MAP={
    "cross_sweep":strategy_cross_sweep,"full_sweep":strategy_full_sweep,
    "ecall_with_branches":strategy_ecall_with_branches,"branch_and_store":strategy_branch_and_store,
    "branch_sweep":strategy_branch_sweep,"load_sweep":strategy_load_sweep,
    "csr_sweep":strategy_csr_sweep,"mixed_coverage":strategy_mixed_coverage,
    "random_mix":strategy_random_mix,"data_dependent_branch":strategy_data_dependent_branch,
    "always_taken_branch":strategy_always_taken_branch,"always_not_taken":strategy_always_not_taken,
    "store_buffer_fill":strategy_store_buffer_fill,"deliberate_ecall":strategy_deliberate_ecall,
    "mispredict_force":strategy_mispredict_force,"illegal_instructions":strategy_illegal_instructions,
    "exception_heavy":strategy_exception_heavy,
}

# ===========================================================================
# AFL-STYLE MUTATORS
# ===========================================================================
def mutate_bitflip(seed,num_flips=None):
    s=list(seed);p=len(CI_BLOCK)
    for _ in range(num_flips or random.randint(1,3)):
        i=random.randint(p,len(s)-1);s[i]^=(1<<random.randint(0,31));s[i]&=0xFFFFFFFF
    return s
def mutate_swap(seed):
    s=list(seed);s[random.randint(len(CI_BLOCK),len(s)-1)]=_random_valid_instr();return s
def mutate_insert(seed):
    s=list(seed);s.insert(random.randint(len(CI_BLOCK),len(s)-1),_random_valid_instr());return s[:len(seed)]
def mutate_delete(seed):
    s=list(seed);del s[random.randint(len(CI_BLOCK),len(s)-1)];s.append(_nop());return s
def mutate_splice(a,b):
    n=min(len(a),len(b));p=len(CI_BLOCK);cut=random.randint(p+5,max(p+6,n-5))
    return list(a[:cut])+list(b[cut:n])
def mutate_havoc(seed,num_ops=None):
    s=list(seed)
    for _ in range(num_ops or random.randint(4,12)):
        op=random.choice(["bitflip","swap","insert","delete"])
        if op=="bitflip":s=mutate_bitflip(s,1)
        elif op=="swap":s=mutate_swap(s)
        elif op=="insert":s=mutate_insert(s)
        elif op=="delete":s=mutate_delete(s)
    return s

MUTATOR_MAP={"bitflip":mutate_bitflip,"swap":mutate_swap,"insert":mutate_insert,
             "delete":mutate_delete,"havoc":mutate_havoc}

# ===========================================================================
# HEX I/O -- writes main program + trap handler into a single hex file
# ===========================================================================
def write_hex(instrs, path):
    """Write program + trap handler. Trap handler placed at TRAP_ADDR."""
    instrs = [x if (x & 0x7F) != 0 else 0x00000013 for x in instrs]

    # Calculate how many instructions fit before the trap handler address
    trap_instr_idx = TRAP_ADDR // 4  # instruction index where handler starts

    # Pad program to reach trap handler location
    while len(instrs) < trap_instr_idx:
        instrs.append(_nop())

    # Append trap handler
    instrs = instrs[:trap_instr_idx] + TRAP_HANDLER
    # Pad to even for 64-bit packing
    if len(instrs) % 2 == 1:
        instrs.append(_nop())

    with open(path, "w") as f:
        for i in range(0, len(instrs), 2):
            lo = instrs[i] & 0xFFFFFFFF
            hi = instrs[i+1] & 0xFFFFFFFF
            f.write("%016X\n" % ((hi << 32) | lo))
    print("[HEX] {0} instrs + trap@0x{1:X} -> {2}".format(
          min(len(instrs), trap_instr_idx), TRAP_ADDR, path))

def read_hex(path):
    out=[]
    with open(path) as f:
        for line in f:
            line=line.strip()
            if not line:continue
            val=int(line,16);out.append(val&0xFFFFFFFF);out.append((val>>32)&0xFFFFFFFF)
    return out

def mutate(targets,iteration=0,skip_strategies=None):
    skip=skip_strategies or set()
    for t in targets:
        s=t.get("strategy") if isinstance(t,dict) else getattr(t,"strategy",None)
        if s and s not in skip: return STRATEGY_MAP.get(s,strategy_random_mix)(PROG_LEN)
    return strategy_random_mix(PROG_LEN)

if __name__=="__main__":
    print("Strategies ({0} instr programs):".format(PROG_LEN))
    for name,fn in sorted(STRATEGY_MAP.items()):
        instrs=fn(PROG_LEN);print("  {0:25s}: {1} instrs".format(name,len(instrs)))
    print("\nTrap handler test:")
    write_hex(strategy_cross_sweep(PROG_LEN), "/tmp/test_trap.hex")
    with open("/tmp/test_trap.hex") as f:
        lines = f.readlines()
    print("  Total hex lines: {0} (= {1} instructions)".format(len(lines), len(lines)*2))
    print("  Trap handler at word index {0} (byte addr 0x{1:X})".format(TRAP_ADDR//8, TRAP_ADDR))
