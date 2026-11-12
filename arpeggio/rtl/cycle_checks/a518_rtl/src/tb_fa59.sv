// A5.9 copy (adds C op cyc for every accepted command). A5.5 event logger around the engine (PROTOCOL_A55.md section 8): driven by sim_main.cpp, no delays. Logs per clock:
// T tag r k cyc (a test: decision-port use), F tag r k lane cyc (a flip: R-port use), I tag r cyc (an init op), S tag r cyc (context ready),
// E tag r cyc (context finished stepping), B tag r p bits de cyc (output beat).
`default_nettype none
module tb_fa #(parameter int D = 32, parameter int A = 4, parameter int SEEDL = 1, parameter int CW = 14, parameter int EW = 36) (
    input  wire logic clk, input wire logic rst_n, input wire logic in_valid, output logic in_ready,
    input  wire logic [2:0] in_op, input wire logic [9:0] in_addr, input wire logic [D*CW-1:0] in_data,
    output logic out_valid, output logic busy, output logic [EW-1:0] out_de);
    logic [15:0] out_tag; logic [11:0] out_r; logic [2:0] out_p; logic [D-1:0] out_bits;
    ape_engine #(.D(D), .A(A), .SEEDL(SEEDL), .CW(CW), .EW(EW)) dut (.*);
    integer fo; longint cyc; logic [2:0] pst [A];
    initial begin fo = $fopen("rtl_events.txt", "w"); cyc = 0; for (int c = 0; c < A; c++) pst[c] = '0; end
    always @(posedge clk) if (rst_n) begin
        cyc <= cyc + 1;
        if (in_valid && in_ready && in_op != 3'd0) $fdisplay(fo, "C %0d %0d", in_op, cyc);
        if (dut.d0_v) $fdisplay(fo, "T %0d %0d %0d %0d", dut.ctag[dut.d0_c], dut.cr[dut.d0_c], dut.ck[dut.d0_c], cyc);
        if (dut.f1_v && dut.f1_flip) $fdisplay(fo, "F %0d %0d %0d %0d %0d", dut.ctag[dut.f1_c], dut.cr[dut.f1_c], dut.ck[dut.f1_c], dut.f1_i, cyc);
        if (dut.f1_v && dut.f1_init) $fdisplay(fo, "I %0d %0d %0d", dut.ctag[dut.f1_c], dut.cr[dut.f1_c], cyc);
        for (int c = 0; c < A; c++) begin
            if (dut.init_ok[c]) $fdisplay(fo, "S %0d %0d %0d", dut.ctag[c], dut.cr[c], cyc);
            if (dut.st[c] == 3'd6 && pst[c] != 3'd6) $fdisplay(fo, "E %0d %0d %0d", dut.ctag[c], dut.cr[c], cyc);
            pst[c] <= dut.st[c];
        end
        if (out_valid) $fdisplay(fo, "B %0d %0d %0d %h %0d %0d", out_tag, out_r, out_p, out_bits, $signed(out_de), cyc);
    end
    final $fclose(fo);
endmodule
`default_nettype wire
