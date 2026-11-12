// AXI-Stream wrapper of the Antiphase engine for the V80 build (Verilog top for a Vivado block-design module reference).
// Input: 512-bit command beats from the HLS data mover; a command is NB = ceil((16 + D*14) / 512) beats:
//   bits [2:0] op (1 LOAD_ROW, 2 LOAD_H, 3 LOAD_TAB, 4 RUN, 7 END), [12:3] addr, [15:13] 0, then the D*14-bit
//   payload (the engine's in_data) from bit 16 on, continued in the next beats.
// Output: 256-bit words to the mover: an output beat {8'h01, ..., bits[D-1:0] at 68, de[35:0] at 32, p[2:0] at 28,
//   r[11:0] at 16, tag[15:0] at 0}, and after END and engine idle a final word {8'hFF, overflow at 128,
//   beats[31:0] at 96, bubbles[47:0] at 48, cycles[47:0] at 0}: cycles from the first accepted command to idle,
//   bubbles = cycles in that window with no complete command waiting (input stream slower than the engine).
// The engine has no output back-pressure; a FIFO of FIFO_DEPTH words absorbs bursts (the mover drains continuously);
// overflow is reported, never silent.
`default_nettype none
module ape_axis #(
    parameter integer D = 32,
    parameter integer A = 4,
    parameter integer SEEDL = 1,
    parameter integer FIFO_DEPTH = 512
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET rst_n" *)
    input  wire         clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 rst_n RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire         rst_n,
    input  wire [511:0] s_axis_tdata,
    input  wire         s_axis_tvalid,
    output wire         s_axis_tready,
    output wire [255:0] m_axis_tdata,
    output wire         m_axis_tvalid,
    input  wire         m_axis_tready
);
    localparam integer CW = 14;
    localparam integer EW = 36;
    localparam integer PW = 16 + D * CW;
    localparam integer NB = (PW + 511) / 512;
    localparam integer LF = $clog2(FIFO_DEPTH);

    // ---------------- command assembly
    reg  [NB*512-1:0] cbuf;
    reg  [7:0]        cbeat;
    reg               pend;
    wire [2:0]        p_op   = cbuf[2:0];
    wire [9:0]        p_addr = cbuf[12:3];
    wire [D*CW-1:0]   p_data = cbuf[16 +: D*CW];
    wire              e_valid = pend && (p_op != 3'd7);
    wire              e_ready;
    wire              e_acc = e_valid && e_ready;
    wire              consume = pend && ((p_op == 3'd7) || e_ready);
    assign s_axis_tready = !pend || consume;
    wire              take = s_axis_tvalid && s_axis_tready;
    reg               ended, started, final_sent;
    reg  [47:0]       ncyc, nbub;
    reg  [31:0]       nbeat;
    reg               ovf;
    wire              e_busy;

    wire              o_valid; wire [15:0] o_tag; wire [11:0] o_r; wire [2:0] o_p; wire [D-1:0] o_bits; wire [EW-1:0] o_de;
    ape_engine #(.D(D), .A(A), .SEEDL(SEEDL)) u_eng (
        .clk(clk), .rst_n(rst_n), .in_valid(e_valid), .in_ready(e_ready), .in_op(p_op), .in_addr(p_addr), .in_data(p_data),
        .out_valid(o_valid), .out_tag(o_tag), .out_r(o_r), .out_p(o_p), .out_bits(o_bits), .out_de(o_de), .busy(e_busy));

    always @(posedge clk) begin
        if (!rst_n) begin
            pend <= 1'b0; cbeat <= 8'd0;
        end else begin
            if (consume) pend <= 1'b0;
            if (take) begin
                cbuf[cbeat*512 +: 512] <= s_axis_tdata;
                if (cbeat == NB - 1) begin cbeat <= 8'd0; pend <= 1'b1; end
                else cbeat <= cbeat + 8'd1;
            end
        end
    end

    // ---------------- output FIFO
    reg  [255:0] fmem [0:FIFO_DEPTH-1];
    reg  [LF:0]  wp, rp;
    wire         fempty = (wp == rp);
    wire         ffull  = (wp - rp) == FIFO_DEPTH;
    reg  [255:0] fword; reg fpush;
    always @(*) begin
        fword = 256'd0; fpush = 1'b0;
        if (o_valid) begin
            fpush = 1'b1;
            fword[255:248] = 8'h01;
            fword[15:0] = o_tag; fword[27:16] = o_r; fword[30:28] = o_p; fword[32 +: EW] = o_de; fword[68 +: D] = o_bits;
        end else if (ended && !e_busy && !pend && !final_sent) begin
            fpush = 1'b1;
            fword[255:248] = 8'hFF;
            fword[47:0] = ncyc; fword[95:48] = nbub; fword[127:96] = nbeat; fword[128] = ovf;
        end
    end

    assign m_axis_tdata  = fmem[rp[LF-1:0]];
    assign m_axis_tvalid = !fempty;
    always @(posedge clk) begin
        if (!rst_n) begin
            wp <= 0; rp <= 0; ovf <= 1'b0; ended <= 1'b0; started <= 1'b0; final_sent <= 1'b0;
            ncyc <= 48'd0; nbub <= 48'd0; nbeat <= 32'd0;
        end else begin
            if (fpush) begin
                if (!ffull) begin fmem[wp[LF-1:0]] <= fword; wp <= wp + 1'b1; end
                else ovf <= 1'b1;
                if (fword[255:248] == 8'hFF) final_sent <= 1'b1;
            end
            if (m_axis_tvalid && m_axis_tready) rp <= rp + 1'b1;
            if (final_sent && take) begin           // first beat of the next launch: new statistics window
                ended <= 1'b0; started <= 1'b0; final_sent <= 1'b0; ncyc <= 48'd0; nbub <= 48'd0; nbeat <= 32'd0;
                ovf <= 1'b0;
            end else begin
                if (o_valid) nbeat <= nbeat + 32'd1;
                if (pend && p_op == 3'd7) ended <= 1'b1;
                if (e_acc && !started) started <= 1'b1;
                if ((started || e_acc) && !(ended && !e_busy)) begin
                    ncyc <= ncyc + 48'd1;
                    if (!e_valid && !ended) nbub <= nbub + 48'd1;
                end
            end
        end
    end
endmodule
`default_nettype wire
