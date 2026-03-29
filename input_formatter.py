"""
input_formatter.py — Write instruction list to $readmemh-compatible hex file
Group 7 | EEE6323 VLSI II | University of Florida

$readmemh word address = byte address >> 2
CVA6 boot address: 0x80000000 → word address @20000000
"""

BOOT_BYTE_ADDR = 0x80000000
BOOT_WORD_ADDR = BOOT_BYTE_ADDR >> 2   # = 0x20000000


def write_hex(instructions: list, path: str) -> str:
    """
    Write a list of 32-bit instruction integers to a $readmemh hex file.

    Args:
        instructions: list of 32-bit integers (CI block + TI block)
        path:         output file path (e.g. 'sim_work/sim_input.hex')

    Returns:
        path (for chaining)
    """
    with open(path, 'w') as f:
        f.write(f"@{BOOT_WORD_ADDR:08X}\n")
        for instr in instructions:
            f.write(f"{instr & 0xFFFFFFFF:08X}\n")
    return path


def read_hex(path: str) -> list:
    """
    Read a $readmemh hex file back to a list of 32-bit integers.
    Skips the @address line.
    """
    instrs = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('@') or line.startswith('//'):
                continue
            instrs.append(int(line, 16))
    return instrs
