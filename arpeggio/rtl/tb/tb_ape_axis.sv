// Testbench of the V80 stream wrapper (rtl/ape_axis.v): converts stim.txt commands into 512-bit beats (+ END),
// drives them with optional random input gaps (GAP_PCT) and random output back-pressure (BP_PCT), and logs every output
// word to axis_out.txt ("W <hex>"). tb/compare_axis.py checks the results against expected.json.
`timescale 1ns/1ps
`default_nettype none
module tb_ape_axis;
    parameter int D = 32, A = 4, SEEDL = 1, GAP_PCT = 0, BP_PCT = 0, SEED = 1;
    localparam int CW = 14, PW = 16 + D * CW, NB = (PW + 511) / 512;
    logic clk = 1'b0, rst_n = 1'b0;
    always #0.5 clk = ~clk;
    logic [511:0] s_tdata; logic s_tvalid, s_tready; logic [255:0] m_tdata; logic m_tvalid, m_tready;
    ape_axis #(.D(D), .A(A), .SEEDL(SEEDL)) dut (.clk(clk), .rst_n(rst_n), .s_axis_tdata(s_tdata), .s_axis_tvalid(s_tvalid),
        .s_axis_tready(s_tready), .m_axis_tdata(m_tdata), .m_axis_tvalid(m_tvalid), .m_axis_tready(m_tready));
    logic [511:0] beats [$];
    int fin, fout, code, rnd; int unsigned st;
    initial begin
        int op, ad; logic [D*CW-1:0] dv; logic [NB*512-1:0] cb;
        st = SEED;
        fin = $fopen("stim.txt", "r");
        while (!$feof(fin)) begin
            code = $fscanf(fin, "%d %d %h\n", op, ad, dv);
            if (code == 3) begin
                cb = '0; cb[2:0] = op; cb[12:3] = ad; cb[16 +: D*CW] = dv;
                for (int b = 0; b < NB; b++) beats.push_back(cb[b*512 +: 512]);
            end
        end
        $fclose(fin);
        cb = '0; cb[2:0] = 3'd7;
        for (int b = 0; b < NB; b++) beats.push_back(cb[b*512 +: 512]);
        fout = $fopen("axis_out.txt", "w");
    end
    function automatic int urand100(); st = st * 1103515245 + 12345; return int'((st >> 16) % 100); endfunction
    int bi = 0; bit done = 0;
    initial begin
        s_tvalid = 0; s_tdata = '0; m_tready = 0;
        repeat (4) @(posedge clk); #0.1 rst_n = 1'b1;
        forever begin
            @(negedge clk);
            if (!s_tvalid) begin            // a presented beat is held until accepted (AXI-Stream rule)
                if (bi < beats.size() && urand100() >= GAP_PCT) begin s_tvalid = 1; s_tdata = beats[bi]; end
            end
            m_tready = (urand100() >= BP_PCT);
            @(posedge clk);
            if (m_tvalid && m_tready) begin           // sample both handshakes before any time advances
                $fdisplay(fout, "W %h", m_tdata);
                if (m_tdata[255:248] == 8'hFF) done = 1;
            end
            if (s_tvalid && s_tready) begin bi++; #0.01 s_tvalid = 0; end
        end
    end
    initial begin
        wait (done == 1);
        repeat (5) @(posedge clk);
        $fclose(fout); $display("TB_DONE"); $finish;
    end
    initial begin #200000000; $display("TB_TIMEOUT"); $finish; end
endmodule
`default_nettype wire
