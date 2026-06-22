`timescale 1ns/1ps

module axi_mem_slave #(
  parameter int     ADDR_WIDTH = 64,
  parameter int     DATA_WIDTH = 64,
  parameter int     MEM_WORDS  = 65536,
  parameter longint BASE_ADDR  = 64'h0
)(
  input  logic                     clk_i,
  input  logic                     rst_ni,
  input  logic [ADDR_WIDTH-1:0]    aw_addr_i,
  input  logic                     aw_valid_i,
  output logic                     aw_ready_o,
  input  logic [DATA_WIDTH-1:0]    w_data_i,
  input  logic [DATA_WIDTH/8-1:0]  w_strb_i,
  input  logic                     w_valid_i,
  output logic                     w_ready_o,
  output logic                     b_valid_o,
  input  logic                     b_ready_i,
  output logic [1:0]               b_resp_o,
  input  logic [ADDR_WIDTH-1:0]    ar_addr_i,
  input  logic [7:0]               ar_len_i,
  input  logic                     ar_valid_i,
  output logic                     ar_ready_o,
  output logic [DATA_WIDTH-1:0]    r_data_o,
  output logic                     r_valid_o,
  output logic                     r_last_o,
  input  logic                     r_ready_i,
  output logic [1:0]               r_resp_o
);
  logic [DATA_WIDTH-1:0] mem [0:MEM_WORDS-1];

  assign aw_ready_o = 1'b1;
  assign w_ready_o  = 1'b1;
  assign b_resp_o   = 2'b00;
  assign r_resp_o   = 2'b00;

  // Write
  logic b_valid_q;
  integer wi;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      b_valid_q <= 0;
    end else begin
      if (aw_valid_i && w_valid_i) begin
        wi = (aw_addr_i - BASE_ADDR) >> 3;
        if (wi >= 0 && wi < MEM_WORDS)
          for (int i=0; i<DATA_WIDTH/8; i++)
            if (w_strb_i[i]) mem[wi][8*i+:8] <= w_data_i[8*i+:8];
        b_valid_q <= 1;
      end else if (b_ready_i) b_valid_q <= 0;
    end
  end
  assign b_valid_o = b_valid_q;

  // Burst read FSM
  logic [ADDR_WIDTH-1:0] rd_base;
  logic [7:0]  rd_len;
  logic [7:0]  rd_cnt;
  logic        rd_active;
  logic        ar_ready_q;
  integer      ri;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rd_active  <= 0;
      rd_base    <= 0;
      rd_len     <= 0;
      rd_cnt     <= 0;
      r_valid_o  <= 0;
      r_last_o   <= 0;
      r_data_o   <= 0;
      ar_ready_q <= 1;
    end else begin
      if (!rd_active) begin
        r_valid_o  <= 0;
        r_last_o   <= 0;
        ar_ready_q <= 1;
        if (ar_valid_i) begin
          rd_base    <= ar_addr_i;
          rd_len     <= ar_len_i;
          rd_cnt     <= 0;
          rd_active  <= 1;
          ar_ready_q <= 0;
          ri = (ar_addr_i - BASE_ADDR) >> 3;
          r_data_o  <= (ri >= 0 && ri < MEM_WORDS) ? mem[ri] : 0;
          r_valid_o <= 1;
          r_last_o  <= (ar_len_i == 0);
        end
      end else begin
        if (r_ready_i && r_valid_o) begin
          if (rd_cnt >= rd_len) begin
            rd_active  <= 0;
            r_valid_o  <= 0;
            r_last_o   <= 0;
            ar_ready_q <= 1;
          end else begin
            rd_cnt <= rd_cnt + 1;
            ri = ((rd_base - BASE_ADDR) >> 3) + rd_cnt + 1;
            r_data_o  <= (ri >= 0 && ri < MEM_WORDS) ? mem[ri] : 0;
            r_valid_o <= 1;
            r_last_o  <= (rd_cnt + 1 >= rd_len);
          end
        end
      end
    end
  end
  assign ar_ready_o = ar_ready_q;

endmodule

module testbench
  import ariane_pkg::*;
  import config_pkg::*;
  import build_config_pkg::*;
();
  localparam config_pkg::cva6_cfg_t CVA6Cfg =
    build_config_pkg::build_config(cva6_config_pkg::cva6_cfg);

  parameter string  HEX_FILE   = "sim_work/sim_input.hex";
  parameter int     MAX_CYCLES = 200000;
  parameter logic [63:0] BOOT_ADDR = 64'h0;

  logic clk=0, rst_n=0;
  always #5 clk=~clk;

  int cycle_cnt=0;
  always @(posedge clk) begin
    cycle_cnt++;
    if (cycle_cnt >= MAX_CYCLES) begin
      $display("[TB] Watchdog hit at cycle %0d", cycle_cnt);
      $finish;
    end
  end

  initial begin
    repeat(20) @(posedge clk);
    rst_n = 1'b1;
    $display("[TB] Reset released at cycle %0d", cycle_cnt);
  end

  // AXI signals
  logic [CVA6Cfg.AxiAddrWidth-1:0]   axi_aw_addr, axi_ar_addr;
  logic                               axi_aw_valid, axi_aw_ready;
  logic [CVA6Cfg.AxiDataWidth-1:0]   axi_w_data, axi_r_data;
  logic [CVA6Cfg.AxiDataWidth/8-1:0] axi_w_strb;
  logic                               axi_w_valid, axi_w_ready;
  logic [1:0]                         axi_b_resp, axi_r_resp;
  logic                               axi_b_valid, axi_b_ready;
  logic                               axi_ar_valid, axi_ar_ready;
  logic                               axi_r_valid, axi_r_ready, axi_r_last;
  logic [7:0]                         axi_ar_len;

  axi_mem_slave #(
    .ADDR_WIDTH (CVA6Cfg.AxiAddrWidth),
    .DATA_WIDTH (CVA6Cfg.AxiDataWidth),
    .MEM_WORDS  (65536),
    .BASE_ADDR  (BOOT_ADDR)
  ) i_mem (
    .clk_i      (clk),
    .rst_ni     (rst_n),
    .aw_addr_i  (axi_aw_addr),  .aw_valid_i (axi_aw_valid), .aw_ready_o (axi_aw_ready),
    .w_data_i   (axi_w_data),   .w_strb_i   (axi_w_strb),   .w_valid_i  (axi_w_valid),
    .w_ready_o  (axi_w_ready),
    .b_resp_o   (axi_b_resp),   .b_valid_o  (axi_b_valid),   .b_ready_i  (axi_b_ready),
    .ar_addr_i  (axi_ar_addr),  .ar_len_i   (axi_ar_len),
    .ar_valid_i (axi_ar_valid), .ar_ready_o (axi_ar_ready),
    .r_data_o   (axi_r_data),   .r_resp_o   (axi_r_resp),
    .r_valid_o  (axi_r_valid),  .r_last_o   (axi_r_last),
    .r_ready_i  (axi_r_ready)
  );

  initial begin
    $readmemh(HEX_FILE, i_mem.mem);
    $display("[TB] Loaded: %s", HEX_FILE);
  end

  // noc_resp_t: {aw_ready,ar_ready,w_ready,b_valid,b{id,resp,user},r_valid,r{id,data,resp,last,user}}
  // Widths: 1+1+1+1+(4+2+64)+1+(4+64+2+1+64) = 210 bits
  logic [209:0] noc_resp_sig;
  assign noc_resp_sig = {
    axi_aw_ready,          // [209]
    axi_ar_ready,          // [208]
    axi_w_ready,           // [207]
    axi_b_valid,           // [206]
    4'b0,                  // [205:202] b.id
    axi_b_resp,            // [201:200] b.resp
    64'b0,                 // [199:136] b.user
    axi_r_valid,           // [135]
    4'b0,                  // [134:131] r.id
    axi_r_data,            // [130:67]  r.data
    axi_r_resp,            // [66:65]   r.resp
    axi_r_last,            // [64]      r.last
    64'b0                  // [63:0]    r.user
  };

  logic [1:0] irq_i=2'b00;
  logic ipi_i=1'b0, time_irq_i=1'b0, debug_req_i=1'b0;

  // Declare noc_req signal to capture CVA6 AXI master outputs
  // noc_req_t fields: {aw_chan,aw_valid,w_chan,w_valid,b_ready,ar_chan,ar_valid,r_ready}
  // Use a wide logic vector to capture all bits
  localparam int NOC_REQ_W =
    CVA6Cfg.AxiAddrWidth + CVA6Cfg.AxiIdWidth + CVA6Cfg.AxiUserWidth + 8 + 3 + // aw
    1 +  // aw_valid
    CVA6Cfg.AxiDataWidth + CVA6Cfg.AxiDataWidth/8 + CVA6Cfg.AxiUserWidth + // w
    1 +  // w_valid
    1 +  // b_ready
    CVA6Cfg.AxiAddrWidth + CVA6Cfg.AxiIdWidth + 8 + 3 + CVA6Cfg.AxiUserWidth + // ar
    1 +  // ar_valid
    1;   // r_ready

  // Declare wire to capture noc_req_o
  // Must match noc_req_t packed struct width
  // aw{addr64,id4,len8,size3,burst2,lock1,cache4,prot3,qos4,region4,atop6,user64}
  // + aw_valid + w{data64,strb8,last1,user64} + w_valid + b_ready
  // + ar{addr64,id4,len8,size3,burst2,lock1,cache4,prot3,qos4,region4,user64}
  // + ar_valid + r_ready
  // Use hierarchical access after connection
  wire [511:0] noc_req_out;

  cva6 #(.CVA6Cfg(CVA6Cfg)) dut (
    .clk_i         (clk),
    .rst_ni        (rst_n),
    .boot_addr_i   (BOOT_ADDR),
    .hart_id_i     ('0),
    .irq_i         (irq_i),
    .ipi_i         (ipi_i),
    .time_irq_i    (time_irq_i),
    .debug_req_i   (debug_req_i),
    .rvfi_probes_o (),
    .noc_req_o     (noc_req_out),
    .noc_resp_i    (noc_resp_sig)
  );

  // Tap AXI signals from DUT noc_req_o port
  assign axi_aw_addr  = dut.noc_req_o.aw.addr;
  assign axi_aw_valid = dut.noc_req_o.aw_valid;
  assign axi_w_data   = dut.noc_req_o.w.data;
  assign axi_w_strb   = dut.noc_req_o.w.strb;
  assign axi_w_valid  = dut.noc_req_o.w_valid;
  assign axi_b_ready  = dut.noc_req_o.b_ready;
  assign axi_ar_addr  = dut.noc_req_o.ar.addr;
  assign axi_ar_len   = dut.noc_req_o.ar.len;
  assign axi_ar_valid = dut.noc_req_o.ar_valid;
  assign axi_r_ready  = dut.noc_req_o.r_ready;

  // Coverage probes - includes AXI activity tracking
  wire bp_valid      = dut.resolved_branch.valid;
  wire bp_taken      = dut.resolved_branch.is_taken;
  wire bp_mispredict = dut.resolved_branch.is_mispredict;
  wire no_st_pending = dut.no_st_pending_commit;
  wire st_pending    = ~dut.no_st_pending_commit;
  wire commit_ack    = dut.commit_ack[0];
  wire commit_ex     = dut.ex_commit.valid;
  wire [6:0] commit_op = 7'h0;

  // AXI-level observations (work even during boot)
  wire [31:0] instr_word = axi_r_data[31:0];
  wire [6:0]  instr_op   = instr_word[6:0];
  wire [2:0]  instr_f3   = instr_word[14:12];
  wire [4:0]  instr_rd   = instr_word[11:7];
  wire [4:0]  instr_rs1  = instr_word[19:15];

  // Branch coverage - toggles with different hex patterns
  covergroup cg_branch;
    cp_taken:      coverpoint bp_taken      { bins taken={1}; bins not_taken={0}; }
    cp_mispredict: coverpoint bp_mispredict { bins correct={0}; bins mispredict={1}; }
    cx: cross cp_taken, cp_mispredict;
  endgroup

  // Store buffer coverage
  covergroup cg_store_buf @(posedge clk iff rst_n);
    cp_pending: coverpoint st_pending { bins idle={0}; bins busy={1}; }
  endgroup

  // Exception coverage - observes instructions as they get fetched
  covergroup cg_exception;
    cp_trap: coverpoint commit_ex           { bins clean={0}; bins trap={1}; }
    cp_op:   coverpoint instr_op            {
      bins system  = {7'h73};
      bins store   = {7'h23};
      bins branch  = {7'h63};
      bins alu_reg = {7'h33};
      bins alu_imm = {7'h13};
      bins load    = {7'h03};
      bins jal     = {7'h6F};
      bins jalr    = {7'h67};
      bins lui     = {7'h37};
      bins auipc   = {7'h17};
      bins fence   = {7'h0F};
      bins other   = default;
    }
    cp_funct3: coverpoint instr_f3          {
      bins f0={3'd0}; bins f1={3'd1}; bins f2={3'd2}; bins f3={3'd3};
      bins f4={3'd4}; bins f5={3'd5}; bins f6={3'd6}; bins f7={3'd7};
    }
    cp_rd:    coverpoint instr_rd[4:2]      {
      bins r0={3'd0}; bins r1={3'd1}; bins r2={3'd2}; bins r3={3'd3};
      bins r4={3'd4}; bins r5={3'd5}; bins r6={3'd6}; bins r7={3'd7};
    }
    cx_op_f3: cross cp_op, cp_funct3;
  endgroup

  cg_branch    branch_cg = new();
  cg_store_buf store_cg  = new();
  cg_exception except_cg = new();

  // Explicit branch sampler - avoids VCS same-cycle race
  always @(posedge clk) begin
    if (rst_n && bp_valid)
      branch_cg.sample();
  end

  // Explicit exception sampler - decouples fetch-time opcode from commit-time exception
  always @(posedge clk) begin
    if (rst_n) begin
      if (axi_r_valid) except_cg.sample();
      if (commit_ex)   except_cg.sample();
    end
  end

  always @(posedge clk)
    if (rst_n && (cycle_cnt % 5000 == 0) && cycle_cnt > 0)
      $display("[MON] cy=%0d branch=%.1f%% store=%.1f%% except=%.1f%%",
               cycle_cnt,
               branch_cg.get_coverage(),
               store_cg.get_coverage(),
               except_cg.get_coverage());

  int retired=0;
  always @(posedge clk) begin
    if (rst_n && commit_ack) begin
      retired++;
      if (retired <= 30)
        $display("[RETIRE] #%0d cy=%0d op=0x%02h ex=%0b",
                 retired, cycle_cnt, commit_op, commit_ex);
    end
    if (rst_n && bp_valid)
      $display("[BP] cy=%0d taken=%0b misp=%0b",
               cycle_cnt, bp_taken, bp_mispredict);
  end

  final begin
    $display("========================================");
    $display("[COV] branch_cg : %.1f%%", branch_cg.get_coverage());
    $display("[COV] store_cg  : %.1f%%", store_cg.get_coverage());
    $display("[COV] except_cg : %.1f%%", except_cg.get_coverage());
    $display("[COV] retired   : %0d instructions", retired);
    $display("[COV] cycles    : %0d", cycle_cnt);
    $display("========================================");
  end
endmodule
