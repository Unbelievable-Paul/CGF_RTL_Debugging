`timescale 1ns/1ps

module pulp_clock_gating (
  input  logic clk_i,
  input  logic en_i,
  input  logic test_en_i,
  output logic clk_o
);
  assign clk_o = clk_i & (en_i | test_en_i);
endmodule

module pulp_sync_wedge (
  input  logic clk_i,
  input  logic rstn_i,
  input  logic en_i,
  input  logic serial_i,
  output logic r_edge_o,
  output logic f_edge_o,
  output logic serial_o
);
  assign serial_o = serial_i;
  assign r_edge_o = 1'b0;
  assign f_edge_o = 1'b0;
endmodule

module fifo_v2 #(
  parameter DATA_WIDTH   = 32,
  parameter DEPTH        = 8,
  parameter ALM_FULL_TH  = 1,
  parameter ALM_EMPTY_TH = 1
)(
  input  logic clk_i,
  input  logic rst_ni,
  input  logic flush_i,
  input  logic testmode_i,
  output logic full_o,
  output logic empty_o,
  output logic alm_full_o,
  output logic alm_empty_o,
  input  logic [DATA_WIDTH-1:0] data_i,
  input  logic push_i,
  output logic [DATA_WIDTH-1:0] data_o,
  input  logic pop_i
);
  assign full_o      = 1'b0;
  assign empty_o     = 1'b1;
  assign alm_full_o  = 1'b0;
  assign alm_empty_o = 1'b1;
  assign data_o      = '0;
endmodule

module sram #(
  parameter int unsigned DATA_WIDTH = 64,
  parameter int unsigned NUM_WORDS  = 1024,
  parameter              OUT_REGS   = 0,
  parameter int unsigned USER_WIDTH = 1,
  parameter              USER_EN    = 0
)(
  input  logic                         clk_i,
  input  logic                         rst_ni,
  input  logic                         req_i,
  input  logic                         we_i,
  input  logic [$clog2(NUM_WORDS)-1:0] addr_i,
  input  logic [DATA_WIDTH-1:0]        wdata_i,
  input  logic [USER_WIDTH-1:0]        wuser_i,
  input  logic [DATA_WIDTH/8-1:0]      be_i,
  output logic [DATA_WIDTH-1:0]        rdata_o,
  output logic [USER_WIDTH-1:0]        ruser_o
);
  logic [DATA_WIDTH-1:0] mem [0:NUM_WORDS-1];
  assign ruser_o = '0;
  always_ff @(posedge clk_i) begin
    if (req_i) begin
      if (we_i) begin
        for (int i=0; i<DATA_WIDTH/8; i++)
          if (be_i[i]) mem[addr_i][8*i+:8] <= wdata_i[8*i+:8];
      end
      rdata_o <= mem[addr_i];
    end
  end
endmodule

module cluster_clock_gating (
  input  logic clk_i,
  input  logic en_i,
  input  logic test_en_i,
  output logic clk_o
);
  assign clk_o = clk_i & (en_i | test_en_i);
endmodule

module instr_tracer #(
  parameter type bp_resolve_t       = logic,
  parameter type scoreboard_entry_t = logic,
  parameter type interrupts_t       = logic,
  parameter type exception_t        = logic,
  parameter      INTERRUPTS         = 1
)(
  input logic        pck,
  input logic        rstn,
  input logic        flush_unissued,
  input logic        flush_all,
  input logic [31:0] instruction,
  input logic        fetch_valid,
  input logic        fetch_ack,
  input logic        issue_ack,
  input logic        issue_sbe,
  input logic [4:0]  waddr,
  input logic [63:0] wdata,
  input logic        we_gpr,
  input logic        we_fpr,
  input logic        commit_instr,
  input logic        commit_ack,
  input logic        st_valid,
  input logic [63:0] st_paddr,
  input logic        ld_valid,
  input logic        ld_kill,
  input logic [63:0] ld_paddr,
  input logic        resolve_branch,
  input logic        commit_exception,
  input logic [1:0]  priv_lvl,
  input logic        debug_mode,
  input logic [63:0] hart_id_i
);
endmodule

module cva6_rvfi_probes #(
  parameter type rvfi_probes_instr_t = logic,
  parameter type rvfi_probes_csr_t   = logic,
  parameter type rvfi_probes_t       = logic
)(
  input  logic flush_i,
  input  logic issue_instr_ack_i,
  input  logic fetch_entry_valid_i,
  input  logic instruction_i,
  input  logic is_compressed_i,
  input  logic issue_pointer_i,
  input  logic commit_pointer_i,
  input  logic flush_unissued_instr_i,
  input  logic decoded_instr_valid_i,
  input  logic decoded_instr_ack_i,
  input  logic rs1_i,
  input  logic rs2_i,
  input  logic commit_instr_i,
  input  logic commit_drop_i,
  input  logic ex_commit_i,
  input  logic priv_lvl_i,
  input  logic lsu_ctrl_i,
  input  logic wbdata_i,
  input  logic commit_ack_i,
  input  logic mem_paddr_i,
  input  logic debug_mode_i,
  input  logic wdata_i,
  input  logic csr_i,
  input  logic irq_i,
  output rvfi_probes_t rvfi_probes_o
);
  assign rvfi_probes_o = '0;
endmodule