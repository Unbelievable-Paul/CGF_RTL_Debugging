"""
seed_generator.py — RV32IM bare-metal seed generator
Group 7 | EEE6323 VLSI II | University of Florida

Generates a bare-metal RV32IM program as two blocks:
  CI block (Context Initialization, CI_SIZE instructions):
    Sets up a valid execution environment. NEVER mutated.
    - SP = 0x80010000
    - Clear x1-x15
    - Set mtvec to trap handler
  TI block (Test Instructions, TI_SIZE instructions):
    Random RV32IM instructions. The mutation target.
"""

import random

CI_SIZE = 10   # Context Initialization instructions — never mutated
TI_SIZE = 20   # Test Instructions — mutation target

# ── RV32IM opcode / funct3 / funct7 tables ───────────────────────────────────
R_TYPES = [  # (funct7, funct3, opcode)
    (0x00, 0x0, 0x33),  # ADD
    (0x20, 0x0, 0x33),  # SUB
    (0x00, 0x4, 0x33),  # XOR
    (0x00, 0x6, 0x33),  # OR
    (0x00, 0x7, 0x33),  # AND
    (0x00, 0x1, 0x33),  # SLL
    (0x00, 0x5, 0x33),  # SRL
    (0x20, 0x5, 0x33),  # SRA
    (0x00, 0x2, 0x33),  # SLT
    (0x00, 0x3, 0x33),  # SLTU
    # M extension
    (0x01, 0x0, 0x33),  # MUL
    (0x01, 0x4, 0x33),  # DIV
    (0x01, 0x6, 0x33),  # REM
]

I_TYPES = [  # (funct3, opcode)
    (0x0, 0x13),  # ADDI
    (0x4, 0x13),  # XORI
    (0x6, 0x13),  # ORI
    (0x7, 0x13),  # ANDI
    (0x0, 0x03),  # LW   (load)
    (0x1, 0x03),  # LH
    (0x2, 0x03),  # LB
    (0x0, 0x67),  # JALR
]

S_TYPES = [  # (funct3, opcode)
    (0x2, 0x23),  # SW
    (0x1, 0x23),  # SH
    (0x0, 0x23),  # SB
]

B_TYPES = [  # (funct3, opcode)
    (0x0, 0x63),  # BEQ
    (0x1, 0x63),  # BNE
    (0x4, 0x63),  # BLT
    (0x5, 0x63),  # BGE
    (0x6, 0x63),  # BLTU
    (0x7, 0x63),  # BGEU
]

CSR_OPS = [  # (funct3, opcode)
    (0x1, 0x73),  # CSRRW
    (0x2, 0x73),  # CSRRS
    (0x3, 0x73),  # CSRRC
]

COMMON_CSRS = [0x300, 0x304, 0x305, 0x341, 0x342, 0x340]  # mstatus,mie,mtvec,mepc,mcause,mscratch


def _r(funct7, rs2, rs1, funct3, rd, opcode):
    return ((funct7 & 0x7F) << 25 | (rs2 & 0x1F) << 20 |
            (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 |
            (rd  & 0x1F) << 7  | (opcode & 0x7F))

def _i(imm, rs1, funct3, rd, opcode):
    return ((imm & 0xFFF) << 20 | (rs1 & 0x1F) << 15 |
            (funct3 & 0x7) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F))

def _s(imm, rs2, rs1, funct3, opcode):
    imm11_5 = (imm >> 5) & 0x7F
    imm4_0  = imm & 0x1F
    return (imm11_5 << 25 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 |
            (funct3 & 0x7) << 12 | imm4_0 << 7 | (opcode & 0x7F))

def _b(imm, rs2, rs1, funct3, opcode):
    b12  = (imm >> 12) & 0x1
    b11  = (imm >> 11) & 0x1
    b10_5= (imm >> 5)  & 0x3F
    b4_1 = (imm >> 1)  & 0xF
    return (b12 << 31 | b10_5 << 25 | (rs2&0x1F) << 20 | (rs1&0x1F) << 15 |
            (funct3&0x7) << 12 | b4_1 << 8 | b11 << 7 | (opcode&0x7F))

def _u(imm, rd, opcode):
    return ((imm & 0xFFFFF) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F))


class SeedGenerator:

    def _ci_block(self):
        """Build Context Initialization block — stable execution environment."""
        instrs = []
        # LUI x2, 0x80010  → SP upper bits
        instrs.append(_u(0x80010, 2, 0x37))
        # ADDI x2, x2, 0   → SP = 0x80010000
        instrs.append(_i(0, 2, 0x0, 2, 0x13))
        # Clear x1-x7
        for reg in range(1, 8):
            instrs.append(_i(0, 0, 0x0, reg, 0x13))  # ADDI xN, x0, 0
        # Set mtvec = 0x80000080 (simple trap handler offset)
        instrs.append(_i(0x080, 0, 0x0, 5, 0x13))    # ADDI x5, x0, 0x80
        instrs.append((0x305 << 20) | (5 << 15) | (0x1 << 12) | 0x73)  # CSRRW x0,mtvec,x5
        # Pad to CI_SIZE
        while len(instrs) < CI_SIZE:
            instrs.append(_i(0, 0, 0x0, 0, 0x13))    # NOP
        return instrs[:CI_SIZE]

    def _random_instr(self):
        """Generate one random RV32IM instruction."""
        kind = random.choices(
            ["R","I","S","B","U","CSR"],
            weights=[30, 30, 10, 15, 5, 10], k=1
        )[0]

        rd  = random.randint(1, 15)
        rs1 = random.randint(1, 15)
        rs2 = random.randint(1, 15)
        imm = random.randint(-2048, 2047) & 0xFFF

        if kind == "R":
            f7, f3, op = random.choice(R_TYPES)
            return _r(f7, rs2, rs1, f3, rd, op)
        elif kind == "I":
            f3, op = random.choice(I_TYPES)
            return _i(imm, rs1, f3, rd, op)
        elif kind == "S":
            f3, op = random.choice(S_TYPES)
            return _s(imm & 0xFFF, rs2, rs1, f3, op)
        elif kind == "B":
            f3, op = random.choice(B_TYPES)
            return _b((random.randint(-16, 16) * 4) & 0x1FFE, rs2, rs1, f3, op)
        elif kind == "U":
            return _u(random.randint(0, 0xFFFFF), rd,
                      random.choice([0x37, 0x17]))  # LUI or AUIPC
        else:  # CSR
            f3, op = random.choice(CSR_OPS)
            csr = random.choice(COMMON_CSRS)
            return _i(csr, rs1, f3, rd, op)

    def generate(self):
        """Return a full seed: CI_SIZE + TI_SIZE instructions."""
        ci = self._ci_block()
        ti = [self._random_instr() for _ in range(TI_SIZE)]
        # Terminate with JAL x0, 0 (infinite loop / halt)
        ti[-1] = 0x0000006F
        return ci + ti
