"""
mutation_engine.py — Basic mutation operators for RV32IM instruction sequences
Group 7 | EEE6323 VLSI II | University of Florida

Owner: Atish Maragur

3 basic operators (Phase 1 — framework verification):
  1. bit_flip      — flip 1-3 bits in data fields (preserve opcode bits[6:0])
  2. byte_swap     — swap 2 non-opcode bytes within an instruction word
  3. random_opcode — replace opcode field with a random 7-bit value

Rules:
  - Only applied to TI block (instruction index >= CI_BOUNDARY)
  - CI block (bare-metal setup) is NEVER mutated
  - Multiple operators can be applied per call (1-3 randomly)
"""

import random
import copy

CI_BOUNDARY = 10   # Instructions 0-9 are the CI block — never touch


class MutationEngine:

    def mutate(self, instructions: list) -> list:
        """Apply 1-3 random operators to the TI block of an instruction list."""
        result = copy.deepcopy(instructions)
        n_ops  = random.randint(1, 3)
        ops    = random.choices(
            [self._bit_flip, self._byte_swap, self._random_opcode],
            weights=[50, 30, 20],
            k=n_ops
        )
        for op in ops:
            result = op(result)
        return result

    # ── Operator 1: Bit-Flip ─────────────────────────────────────────────────
    def _bit_flip(self, instructions: list) -> list:
        """
        Flip 1-3 bits in a TI instruction.
        Only touches bits[31:7] — opcode field bits[6:0] is preserved.
        Goal: explore nearby data paths without changing instruction type.
        """
        idx  = random.randint(CI_BOUNDARY, len(instructions) - 1)
        n    = random.randint(1, 3)
        bits = random.sample(range(7, 32), n)  # bits 7-31 only
        for b in bits:
            instructions[idx] ^= (1 << b)
        return instructions

    # ── Operator 2: Byte-Swap ────────────────────────────────────────────────
    def _byte_swap(self, instructions: list) -> list:
        """
        Swap 2 non-opcode bytes within a 32-bit instruction word.
        Byte 0 = bits[7:0]  = contains opcode — never swapped.
        Bytes 1,2,3 are eligible for swapping.
        Goal: change register fields / immediates while preserving opcode.
        """
        idx   = random.randint(CI_BOUNDARY, len(instructions) - 1)
        instr = instructions[idx]
        b1, b2 = random.sample([1, 2, 3], 2)

        def get_byte(word, n):
            return (word >> (n * 8)) & 0xFF

        def set_byte(word, n, val):
            mask = ~(0xFF << (n * 8)) & 0xFFFFFFFF
            return (word & mask) | ((val & 0xFF) << (n * 8))

        byte_b1 = get_byte(instr, b1)
        byte_b2 = get_byte(instr, b2)
        instr   = set_byte(instr, b1, byte_b2)
        instr   = set_byte(instr, b2, byte_b1)

        instructions[idx] = instr & 0xFFFFFFFF
        return instructions

    # ── Operator 3: Random Opcode ────────────────────────────────────────────
    def _random_opcode(self, instructions: list) -> list:
        """
        Replace opcode field (bits[6:0]) with a random 7-bit value.
        May create an illegal instruction — this forces the CVA6 trap path
        and exercises the exception pipeline (mcause=2: illegal instruction).
        Goal: cover illegal instruction exception path in CVA6.
        """
        idx        = random.randint(CI_BOUNDARY, len(instructions) - 1)
        new_opcode = random.randint(0, 127)
        instructions[idx] = (instructions[idx] & 0xFFFFFF80) | new_opcode
        return instructions
