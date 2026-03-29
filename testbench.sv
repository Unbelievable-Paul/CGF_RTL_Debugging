// testbench.sv — CVA6 RISC-V Fuzzing Testbench
// Group 7 | EEE6323 VLSI II | University of Florida
// Owner: Deep Bhanderi
//
// Connects sim_input.hex → AXI Memory Model → CVA6 DUT
// Collects 5 covergroups per iteration → coverage.ucdb

`timescale 1ns/1ps

module testbench;

  // ── Parameters ─────────────────────────────────────────────────────────────
  parameter string HEX_FILE   = "sim_input.hex";
  parameter int    MAX_CYCLES = 2000;
  parameter int    CLK_PERIOD = 10;  // 100 MHz

  // ── Clock & Reset ──────────────────────────────────────────────────────────
  logic clk  = 0;
  logic rst_n = 0;

  always #(CLK_PERIOD/2) clk = ~clk;

  initial begin
    rst_n = 0;
    repeat(10) @(posedge clk);
    rst_n = 1;
  end

  // ── AXI-Lite signals ───────────────────────────────────────────────────────
  // Instruction fetch port
  logic [63:0] if_addr;
  logic [31:0] if_rdata;
  logic        if_req, if_gnt, if_valid;

  // Data port
  logic [63:0] data_addr;
  logic [63:0] data_wdata, data_rdata;
  logic        data_we, data_req, data_gnt, data_valid;
  logic [7:0]  data_be;

  // ── Memory Model ───────────────────────────────────────────────────────────
  localparam MEM_BASE  = 64'h80000000;
  localparam MEM_WORDS = 65536;  // 256KB

  logic [31:0] mem [0:MEM_WORDS-1];

  initial begin
    $readmemh(HEX_FILE, mem);
    if_gnt    = 1;
    data_gnt  = 1;
  end

  // Instruction fetch — combinational read
  always_comb begin
    if_valid = if_req;
    if (if_addr >= MEM_BASE && if_addr < MEM_BASE + MEM_WORDS*4) begin
      automatic int idx = (if_addr - MEM_BASE) >> 2;
      if_rdata = mem[idx];
    end else begin
      if_rdata = 32'h00000013;  // NOP on out-of-range
    end
  end

  // Data memory — registered read/write
  always_ff @(posedge clk) begin
    data_valid <= data_req;
    if (data_req) begin
      automatic int idx = (data_addr - MEM_BASE) >> 2;
      if (data_we) begin
        if (data_be[0]) mem[idx][7:0]   <= data_wdata[7:0];
        if (data_be[1]) mem[idx][15:8]  <= data_wdata[15:8];
        if (data_be[2]) mem[idx][23:16] <= data_wdata[23:16];
        if (data_be[3]) mem[idx][31:24] <= data_wdata[31:24];
      end else begin
        data_rdata <= {32'b0, mem[idx]};
      end
    end
  end

  // ── CVA6 DUT ───────────────────────────────────────────────────────────────
  // Note: port names match the CVA6 cv64a6_imafdc_sv39 interface.
  // Adjust if your version differs.
  ariane #(
    .ArianeCfg(ariane_pkg::ArianeDefaultConfig)
  ) dut (
    .clk_i          (clk),
    .rst_ni         (rst_n),
    .boot_addr_i    (64'h80000000),
    .hart_id_i      (64'h0),
    .irq_i          (2'b0),
    .ipi_i          (1'b0),
    .time_irq_i     (1'b0),
    .debug_req_i    (1'b0),

    // Instruction fetch
    .instr_if_address_o (if_addr),
    .instr_if_data_req_o(if_req),
    .instr_if_data_gnt_i(if_gnt),
    .instr_if_data_rvalid_i(if_valid),
    .instr_if_data_rdata_i(if_rdata),

    // Data memory
    .data_if_address_o  (data_addr),
    .data_if_data_wdata_o(data_wdata),
    .data_if_data_req_o (data_req),
    .data_if_data_we_o  (data_we),
    .data_if_data_be_o  (data_be),
    .data_if_data_gnt_i (data_gnt),
    .data_if_data_rvalid_i(data_valid),
    .data_if_data_rdata_i(data_rdata)
  );

  // ── Coverage Groups ────────────────────────────────────────────────────────
  // Observe internal signals via hierarchical references
  // Adjust paths to match your CVA6 hierarchy

  // 1. Instruction opcode coverage
  covergroup instr_cg @(posedge clk);
    cp_opcode: coverpoint if_rdata[6:0] iff (if_valid) {
      bins r_type   = {7'b0110011};
      bins i_type   = {7'b0010011};
      bins load     = {7'b0000011};
      bins store    = {7'b0100011};
      bins branch   = {7'b1100011};
      bins jalr     = {7'b1100111};
      bins jal      = {7'b1101111};
      bins lui      = {7'b0110111};
      bins auipc    = {7'b0010111};
      bins system   = {7'b1110011};
      bins illegal  = default;
    }
    cp_funct3: coverpoint if_rdata[14:12] iff (if_valid);
    cx_opcode_funct3: cross cp_opcode, cp_funct3;
  endgroup

  // 2. Branch coverage
  covergroup branch_cg @(posedge clk);
    cp_branch_type: coverpoint if_rdata[14:12] iff (if_valid && if_rdata[6:0] == 7'b1100011) {
      bins beq  = {3'b000};
      bins bne  = {3'b001};
      bins blt  = {3'b100};
      bins bge  = {3'b101};
      bins bltu = {3'b110};
      bins bgeu = {3'b111};
    }
  endgroup

  // 3. Exception coverage — observe mcause via CSR
  logic [63:0] mcause_val;
  logic        exception_valid;

  // These signals come from CVA6 internal — adjust hierarchy as needed
  assign mcause_val     = dut.csr_regfile_i.mcause_q;
  assign exception_valid = dut.ex_stage_i.ex_valid;

  covergroup exception_cg @(posedge clk);
    cp_mcause: coverpoint mcause_val[3:0] iff (exception_valid) {
      bins illegal_instr = {4'd2};
      bins load_misalign = {4'd4};
      bins store_misalign= {4'd6};
      bins ecall_m       = {4'd11};
      bins others        = default;
    }
  endgroup

  // 4. CSR access coverage
  covergroup csr_cg @(posedge clk);
    cp_csr_addr: coverpoint if_rdata[31:20] iff (if_valid && if_rdata[6:0] == 7'b1110011) {
      bins mstatus  = {12'h300};
      bins mie      = {12'h304};
      bins mtvec    = {12'h305};
      bins mepc     = {12'h341};
      bins mcause   = {12'h342};
      bins mscratch = {12'h340};
      bins others   = default;
    }
    cp_csr_op: coverpoint if_rdata[14:12] iff (if_valid && if_rdata[6:0] == 7'b1110011) {
      bins csrrw = {3'b001};
      bins csrrs = {3'b010};
      bins csrrc = {3'b011};
    }
    cx_csr: cross cp_csr_addr, cp_csr_op;
  endgroup

  // 5. Pipeline stage coverage
  logic commit_valid;
  assign commit_valid = dut.commit_stage_i.commit_valid[0];

  covergroup pipeline_cg @(posedge clk);
    cp_commit: coverpoint commit_valid {
      bins active = {1'b1};
      bins stall  = {1'b0};
    }
  endgroup

  // Instantiate covergroups
  instr_cg     cg_instr     = new();
  branch_cg    cg_branch    = new();
  exception_cg cg_exception = new();
  csr_cg       cg_csr       = new();
  pipeline_cg  cg_pipeline  = new();

  // ── Simulation Control ─────────────────────────────────────────────────────
  int cycle_count = 0;

  always_ff @(posedge clk) begin
    if (rst_n) begin
      cycle_count <= cycle_count + 1;
      if (cycle_count >= MAX_CYCLES) begin
        $display("[TB] MAX_CYCLES=%0d reached. Finishing.", MAX_CYCLES);
        $finish;
      end
    end
  end

endmodule
