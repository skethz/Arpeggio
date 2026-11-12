// Testbench of the Antiphase engine: replays a command stimulus (stim.txt: "<op> <addr> <hex data>" per line, data =
// D*CW bits), one command presented per cycle until accepted, then waits for idle. Logs every acceptance
// ("A <index> <cycle>") and every output beat ("B <cycle> <tag> <r> <p> <bits hex> <de>") to rtl_out.txt; the
// comparison with the model and the references is done by tb/compare.py. Cycle 0 = first edge after reset release.
`timescale 1ns/1ps
`default_nettype none
module tb_ape;
    parameter int D = 32;
    parameter int A = 4;
    parameter int SEEDL = 1;
    parameter int CW = 14;
    parameter int EW = 36;
`ifndef CLK_HALF_NS
    `define CLK_HALF_NS 0.5
`endif
    logic clk = 1'b0, rst_n = 1'b0;
    always #(`CLK_HALF_NS) clk = ~clk;
    logic in_valid, in_ready; logic [2:0] in_op; logic [9:0] in_addr; logic [D*CW-1:0] in_data;
    logic out_valid; logic [15:0] out_tag; logic [11:0] out_r; logic [2:0] out_p; logic [D-1:0] out_bits;
    logic [EW-1:0] out_de; logic busy;
    ape_engine #(.D(D), .A(A), .SEEDL(SEEDL), .CW(CW), .EW(EW)) dut (.*);

    int fin, fout, n, code, idx; longint cyc;
    int ops [$]; int addrs [$]; logic [D*CW-1:0] datas [$];
    initial begin
        int op, ad; logic [D*CW-1:0] dv;
        fin = $fopen("stim.txt", "r");
        if (fin == 0) begin $display("TB_ERROR no stim.txt"); $finish; end
        while (!$feof(fin)) begin
            code = $fscanf(fin, "%d %d %h\n", op, ad, dv);
            if (code == 3) begin ops.push_back(op); addrs.push_back(ad); datas.push_back(dv); end
        end
        $fclose(fin);
        fout = $fopen("rtl_out.txt", "w");
        $display("TB_INFO commands %0d", ops.size());
    end
    // drive
    initial begin
        in_valid = 1'b0; in_op = '0; in_addr = '0; in_data = '0; idx = 0; cyc = 0;
        repeat (4) @(posedge clk);
        #0.1 rst_n = 1'b1;
        forever begin
            @(negedge clk);
            if (idx < ops.size()) begin in_valid = 1'b1; in_op = ops[idx][2:0]; in_addr = addrs[idx][9:0]; in_data = datas[idx]; end
            else begin in_valid = 1'b0; in_op = '0; end
            @(posedge clk);
            if (in_valid && in_ready) begin $fdisplay(fout, "A %0d %0d", idx, cyc); idx++; end
            if (out_valid) $fdisplay(fout, "B %0d %0d %0d %0d %h %0d", cyc, out_tag, out_r, out_p, out_bits, $signed(out_de));
            cyc++;
            if (idx >= ops.size() && !busy && !out_valid) begin
                n++;
                if (n > 4) begin $fdisplay(fout, "E %0d", cyc); $fclose(fout); $display("TB_DONE cycles %0d", cyc); $finish; end
            end else n = 0;
        end
    end
    initial begin n = 0; end
endmodule
`default_nettype wire
