// Antiphase detector engine (DESIGN.md): copy-alternating synchronous stochastic annealing of dDI sub-problems.
// One RTL for ASIC synthesis and the V80 build. Cycle-level twin: model/ape_model.cpp (same registers, same priorities).
// v1.1 (cycle-identical to v1, ape_engine_v1.sv): the flipped spin is read and toggled in F2 instead of F1, and per-context
// 'any pending flip / start row' flags are registers, which shortens the flip-issue path.
// v1.2 (cycle-identical): the decision multiply u * 4T moves from D1 to D2 (D1 registers u and 4T), so the schedule
// table read and the multiplier are in different cycles; the any-flags' next values use x & (x - 1) (the lowest
// pending bit is the one cleared) instead of the priority encoder's output.
// v1.3 (cycle-identical): the flipped spin is read in F1 again (as v1) but through the one-hot of the lowest pending
// bit (x & -x), not through the priority encoder, and registered with mu for F2 (toggle in F2); the seeder's first hash
// multiply is done when a context is assigned, and the per-lane Weyl sums are registers, so no multiplier follows a
// mux or an adder in the same cycle (V80 timing).
// v1.4 (cycle-identical): the best-of-trajectory check of step k-1 moves from D0 to D1 (registered context index, no
// round-robin pick in front of the 36-bit compare). Between D0 and D1 nothing writes that context's energy or spins.
// A5.5 first-accept copy (PROTOCOL_A55.md section 8), behavioural simulation only, not synthesized: a per-context scanned-lane mask,
// the rest of F dropped after F1, a return to D0 with ck held until the pass ends, best check at pass ends only. `define APE_FA_BAL:
// balanced start (m = 0, no I-ops). `define FA_BUG_NOMASK: negative control (must fail).
// Build options: `define APE_PHILOX -> simulation-only Philox streams of the existing reference (anefx); default ->
// production xorshift32 streams (model/antiphase_ref.py, rng='xs'). Memories: ape_gmem (G rows) and ape_tmem (schedule),
// behavioural models in ape_mem_behav.sv, compiler-macro wrappers on the synthesis server only.
`default_nettype none
module ape_engine #(
    parameter int D     = 32,     // lanes = real dimensions (2 Nt)
    parameter int A     = 4,      // anneal contexts in flight
    parameter int SEEDL = 1,      // seeder lanes per cycle (D % SEEDL == 0)
    parameter int PMAX  = 6,      // copies (2 K_max)
    parameter int CW    = 14,     // coefficient width (G, h)
    parameter int WW    = 24,     // lane field width
    parameter int EW    = 36      // energy width
) (
    input  wire logic              clk,
    input  wire logic              rst_n,
    input  wire logic              in_valid,
    output logic                   in_ready,
    input  wire logic [2:0]        in_op,      // 1 LOAD_ROW, 2 LOAD_H, 3 LOAD_TAB, 4 RUN
    input  wire logic [9:0]        in_addr,
    input  wire logic [D*CW-1:0]   in_data,
    output logic                   out_valid,
    output logic [15:0]            out_tag,
    output logic [11:0]            out_r,
    output logic [2:0]             out_p,
    output logic [D-1:0]           out_bits,   // 1 = spin +1
    output logic [EW-1:0]          out_de,     // best energy relative to the anneal's start state (2 E0 units)
    output logic                   busy
);
`ifdef APE_PHILOX
    localparam int RB = 32;
`else
    localparam int RB = 16;
`endif
    localparam int LD   = $clog2(D);
    localparam int LA   = (A > 1) ? $clog2(A) : 1;
    localparam int NG   = D / SEEDL;
    localparam int LG   = (NG > 1) ? $clog2(NG) : 1;
    localparam logic [31:0] PHI = 32'h9E37_79B9;
    localparam logic signed [EW-1:0] EMAX = {1'b0, {(EW-1){1'b1}}};
    localparam logic [2:0] S_IDLE = 3'd0, S_SEEDQ = 3'd1, S_INIT = 3'd2, S_READY = 3'd3,
                           S_DEC = 3'd4, S_FLIP = 3'd5, S_OUTQ = 3'd6, S_OUT = 3'd7;
    localparam logic [2:0] OP_LOAD_ROW = 3'd1, OP_LOAD_H = 3'd2, OP_LOAD_TAB = 3'd3, OP_RUN = 3'd4;

    // ------------------------------------------------------------------ helper functions
    function automatic logic [31:0] fmix_a(input logic [31:0] v); return (v ^ (v >> 16)) * 32'h85EB_CA6B; endfunction
    function automatic logic [31:0] fmix_b(input logic [31:0] v); return (v ^ (v >> 13)) * 32'hC2B2_AE35; endfunction
    function automatic logic [31:0] fmix_f(input logic [31:0] v); return v ^ (v >> 16); endfunction
    function automatic logic [31:0] xs32(input logic [31:0] x0);
        logic [31:0] x;
        x = x0 ^ (x0 << 13); x = x ^ (x >> 17); x = x ^ (x << 5);
        return x;
    endfunction
`ifdef APE_PHILOX
    function automatic logic [31:0] philox_word(input logic [31:0] c0i, c1i, c2i, c3i, k0i, k1i, input int wsel);
        logic [31:0] c0, c1, c2, c3, k0, k1, n0, n2; logic [63:0] p0, p1;
        c0 = c0i; c1 = c1i; c2 = c2i; c3 = c3i; k0 = k0i; k1 = k1i;
        for (int i = 0; i < 10; i++) begin
            if (i != 0) begin k0 = k0 + 32'h9E37_79B9; k1 = k1 + 32'hBB67_AE85; end
            p0 = 64'(32'hD251_1F53) * 64'(c0); p1 = 64'(32'hCD9E_8D57) * 64'(c2);
            n0 = p1[63:32] ^ c1 ^ k0; n2 = p0[63:32] ^ c3 ^ k1;
            c1 = p1[31:0]; c3 = p0[31:0]; c0 = n0; c2 = n2;
        end
        case (wsel) 0: return c0; 1: return c1; 2: return c2; default: return c3; endcase
    endfunction
`endif
    function automatic logic [LD:0] lowbit(input logic [D-1:0] v);     // {found, index of the lowest set bit}
        logic [LD:0] r; r = '0;
        for (int i = D - 1; i >= 0; i--) if (v[i]) r = {1'b1, LD'(i)};
        return r;
    endfunction
    function automatic logic [PMAX-1:0] bal_pat(input logic [2:0] P, input logic [4:0] i);   // i-th pattern of P/2 ones among P copies
        logic [PMAX-1:0] r; int n; r = '0; n = 0;
        for (int v = 0; v < (1 << int'(P)); v++)
            if ($countones(6'(v)) == int'(P) / 2) begin if (n == int'(i)) r = PMAX'(v); n++; end
        return r;
    endfunction
    function automatic logic [LA:0] lowctx(input logic [A-1:0] v);
        logic [LA:0] r; r = '0;
        for (int i = A - 1; i >= 0; i--) if (v[i]) r = {1'b1, LA'(i)};
        return r;
    endfunction

    // ------------------------------------------------------------------ state
    logic [2:0]               st     [A];
    logic [2:0]               cP     [A];
    logic [9:0]               cS     [A];
    logic [9:0]               ctb    [A];
    logic signed [15:0]       cq     [A];
    logic [11:0]              cr     [A];
    logic [15:0]              ctag   [A];
    logic [31:0]              cinst  [A];
    logic [63:0]              cseed  [A];
    logic [9:0]               ck     [A];
    logic [2:0]               cpp    [A];
    logic [9:0]               cn     [A];
    logic signed [EW-1:0]     cde    [A];
    logic signed [EW-1:0]     cbest  [A];
    logic                     csdone [A];
    logic [D-1:0]             cs     [A][PMAX];
    logic [D-1:0]             cbs    [A][PMAX];
    logic signed [WW-1:0]     cw     [A][D];
    logic [31:0]              crng   [A][D];
    logic [D-1:0]             cpend  [A];
    logic [D-1:0]             cipend [A];
    logic [D-1:0]             cscan  [A];     // lanes already scanned in this pass (first-accept)
    logic                     cpany  [A];     // |cpend
    logic                     cipany [A];     // |cipend
    logic signed [CW-1:0]     diag   [D];
    logic signed [CW-1:0]     hh     [D];
    // run queue (entry 0 = head)
    logic                     rqv    [2];
    logic [2:0]               rqP    [2];
    logic [11:0]              rqR    [2];
    logic [9:0]               rqS    [2];
    logic [9:0]               rqtb   [2];
    logic signed [15:0]       rqq    [2];
    logic [31:0]              rqinst [2];
    logic [63:0]              rqseed [2];
    logic [15:0]              rqtag  [2];
    logic [11:0]              rqnr   [2];
    logic [LA-1:0]            rr;
    // decision pipeline
    logic                     d1v;  logic [LA-1:0] d1c; logic [2:0] d1p; logic [9:0] d1n; logic d1chk;
    logic                     d2v;  logic [LA-1:0] d2c;
    logic [RB-1:0]            d2u    [D];
    logic [17:0]              d2a4;
    logic signed [WW:0]       d2sw   [D];
    logic signed [18:0]       d2b;
    // R-port pipeline
    logic                     f2v;  logic [LA-1:0] f2c; logic [LD-1:0] f2i; logic f2flip, f2last;
    logic f2so; logic signed [2:0] f2mu;   // registered in F1 (v1.3)
    // seeder
    logic [1:0]               sst;  logic [LA-1:0] scx; logic [LG-1:0] sgrp; logic [31:0] sW;
    logic                     pav, pab, pbv, pbb; logic [1:0] pabs, pbbs; logic [LA-1:0] pac, pbc; logic [LG-1:0] pag, pbg;
    logic [31:0]              paval [SEEDL];
    logic [31:0]              cfa1  [A];        // fmix_a(seed_lo ^ inst), computed at assignment (v1.3)
    logic [31:0]              sWl   [SEEDL];    // sW + l * PHI (v1.3)
    logic [31:0]              pbval [SEEDL];
    // output unit
    logic                     obusy; logic [LA-1:0] oc; logic [2:0] obeat;

    // ------------------------------------------------------------------ memories
    logic                     g_ce, g_we; logic [LD-1:0] g_addr; logic [D*CW-1:0] g_rdata;
    logic                     t_ce, t_we; logic [9:0] t_addr; logic [31:0] t_wdata, t_rdata;
    ape_gmem #(.D(D), .CW(CW)) u_gmem (.clk(clk), .ce(g_ce), .we(g_we), .addr(g_addr), .wdata(in_data), .rdata(g_rdata));
    ape_tmem u_tmem (.clk(clk), .ce(t_ce), .we(t_we), .addr(t_addr), .wdata(t_wdata), .rdata(t_rdata));

    // ------------------------------------------------------------------ start-of-cycle eligibility
    logic [A-1:0] is_idle, is_seedq, is_ready, is_outq, flip_av, init_av, init_ok;
    always_comb begin
        for (int c = 0; c < A; c++) begin
            is_idle[c]  = (st[c] == S_IDLE);
            is_seedq[c] = (st[c] == S_SEEDQ);
            is_ready[c] = (st[c] == S_READY);
            is_outq[c]  = (st[c] == S_OUTQ);
            flip_av[c]  = (st[c] == S_FLIP) && cpany[c];
            init_av[c]  = (st[c] == S_INIT) && cipany[c];
            init_ok[c]  = (st[c] == S_INIT) && csdone[c] && !cipany[c];
        end
    end
    logic idle_now;
    always_comb begin
        idle_now = !rqv[0] && !rqv[1] && (sst == 2'd0) && !pav && !pbv && !obusy && !d1v && !d2v && !f2v && (&is_idle);
    end
    assign busy = !idle_now;

    // ------------------------------------------------------------------ command intake
    logic acc;
    always_comb begin
        in_ready = (in_op == OP_RUN) ? !(rqv[0] && rqv[1]) : ((in_op == 3'd0) ? 1'b1 : idle_now);
        acc = in_valid && in_ready && (in_op != 3'd0);
    end

    // ------------------------------------------------------------------ output unit pick
    logic [LA:0] o_pk; assign o_pk = lowctx(is_outq);
    // ------------------------------------------------------------------ assignment
    logic [LA:0] a_pk; logic a_do; logic a_pop;
    always_comb begin
        a_pk  = lowctx(is_idle);
        a_do  = rqv[0] && a_pk[LA];
        a_pop = a_do && (rqnr[0] + 12'd1 == rqR[0]);
    end
    // ------------------------------------------------------------------ seeder pop
    logic [LA:0] s_pk; logic s_pop;
    always_comb begin s_pk = lowctx(is_seedq); s_pop = (sst == 2'd0) && s_pk[LA]; end

    // ------------------------------------------------------------------ R-port stage F1
    logic [LA:0] f1_cf, f1_ci; logic f1_flip, f1_init, f1_v; logic [LA-1:0] f1_c; logic [D-1:0] f1_mask;
    logic [LD:0] f1_lb; logic [LD-1:0] f1_i; logic f1_last; logic [D-1:0] f1_oh; logic f1_so; logic signed [3:0] f1_m;
    logic signed [2:0] f1_mu;
    always_comb begin
        f1_cf   = lowctx(flip_av);
        f1_ci   = lowctx(init_av);
        f1_flip = f1_cf[LA];
        f1_init = !f1_flip && f1_ci[LA];
        f1_v    = f1_flip || f1_init;
        f1_c    = f1_flip ? f1_cf[LA-1:0] : f1_ci[LA-1:0];
        f1_mask = f1_flip ? cpend[f1_c] : cipend[f1_c];
        f1_lb   = lowbit(f1_mask);
        f1_i    = f1_lb[LD-1:0];
        f1_last = f1_flip && (f1_i == LD'(D - 1));          // first-accept: no lane left after m
        f1_oh   = f1_mask & (~f1_mask + D'(1));                  // one-hot of the lowest pending bit
        f1_so   = |(cs[f1_c][cpp[f1_c]] & f1_oh);
        f1_m    = '0;
        for (int p = 0; p < PMAX; p++) if (p < cP[f1_c]) f1_m = f1_m + ((|(cs[f1_c][p] & f1_oh)) ? 4'sd1 : -4'sd1);
        f1_mu   = f1_flip ? (f1_so ? 3'sd1 : -3'sd1) : 3'(-(f1_m >>> 1));
    end
    always_comb begin
        g_ce   = (acc && in_op == OP_LOAD_ROW) || f1_v;
        g_we   = acc && in_op == OP_LOAD_ROW;
        g_addr = g_we ? in_addr[LD-1:0] : f1_i;
    end

    // ------------------------------------------------------------------ R-port stage F2 (combinational part)
    logic signed [WW-1:0] f2_wnew [D];
    logic signed [EW-1:0] f2_denew;
    always_comb begin
        for (int j = 0; j < D; j++) begin
            logic signed [CW-1:0] gv; logic signed [CW+1:0] m3;
            gv = g_rdata[j*CW +: CW];
            case (f2mu)
                3'sd1, -3'sd1: m3 = (CW+2)'(gv);
                3'sd2, -3'sd2: m3 = (CW+2)'(gv) <<< 1;
                3'sd3, -3'sd3: m3 = (CW+2)'(gv) + ((CW+2)'(gv) <<< 1);
                default:       m3 = '0;
            endcase
            if (f2mu < 0) m3 = -m3;
            f2_wnew[j] = cw[f2c][j] + (WW'(m3) <<< 2);
        end
`ifdef APE_BUG   // negative control: energy update with the field after this flip's row update (must fail the tests)
        f2_denew = cde[f2c] + ((f2mu > 0) ? (EW'(f2_wnew[f2i]) <<< 2) : -(EW'(f2_wnew[f2i]) <<< 2)) + (EW'(diag[f2i]) <<< 3);
`else
        f2_denew = cde[f2c] + ((f2mu > 0) ? (EW'(cw[f2c][f2i]) <<< 2) : -(EW'(cw[f2c][f2i]) <<< 2)) + (EW'(diag[f2i]) <<< 3);
`endif
    end

    // ------------------------------------------------------------------ decision D0
    logic d0_v; logic [LA-1:0] d0_c; logic d0_best;
    always_comb begin
        d0_v = 1'b0; d0_c = '0;
        for (int o = A; o >= 1; o--) begin
            int i; i = (int'(rr) + o) % A;
            if (is_ready[i]) begin d0_v = 1'b1; d0_c = LA'(i); end
        end
        d0_best = d0_v && (ck[d0_c] != 10'd0) && (cscan[d0_c] == '0);   // first test of a pass: state after the last pass, in D1
    end
    // ------------------------------------------------------------------ decision D1 (combinational part)
    logic [31:0] d1_rng [D];
    logic [RB-1:0] d1_u [D];
    logic [17:0] d1_a4;
    logic signed [WW:0] d1_sw [D];
    logic signed [18:0] d1_b;
    always_comb begin
        logic [15:0] T; logic signed [15:0] cc; logic [17:0] A4;
        T  = t_rdata[15:0]; cc = t_rdata[31:16]; A4 = {T, 2'b00}; d1_a4 = A4;
        d1_b = 19'(cq[d1c]) - 19'(cc) + 19'({T, 1'b0});
        for (int j = 0; j < D; j++) begin
            logic [RB-1:0] u;
            d1_rng[j] = xs32(crng[d1c][j]);
`ifdef APE_PHILOX
            u = philox_word(32'(d1n >> 2), 32'(d1p) * D + j, 32'(cr[d1c]), cinst[d1c], cseed[d1c][31:0], cseed[d1c][63:32],
                            int'(d1n[1:0]));
`else
            u = d1_rng[j][31:16];
`endif
            d1_u[j]    = u;
            d1_sw[j]   = cs[d1c][d1p][j] ? (WW+1)'(cw[d1c][j]) : -(WW+1)'(cw[d1c][j]);
        end
    end
    // ------------------------------------------------------------------ decision D2 (combinational part)
    logic [D-1:0] d2_flip, d2_cand;
`ifdef FA_BUG_NOMASK
    assign d2_cand = d2_flip;
`else
    assign d2_cand = d2_flip & ~cscan[d2c];
`endif
    always_comb begin
        for (int j = 0; j < D; j++) begin
            logic signed [WW+2:0] zp; logic [17:0] hi; logic lo_nz; logic [RB+17:0] prod;
            zp    = (WW+3)'(d2sw[j]) + ((WW+3)'(diag[j]) <<< 1) + (WW+3)'(d2b);
            prod  = (RB+18)'(d2u[j]) * (RB+18)'(d2a4);
            hi    = prod[RB+17:RB];
            lo_nz = |prod[RB-1:0];
            if (zp < 0) d2_flip[j] = 1'b1;
            else if (zp >= (WW+3)'(1 << 18)) d2_flip[j] = 1'b0;
            else d2_flip[j] = (hi > zp[17:0]) || ((hi == zp[17:0]) && lo_nz);
        end
    end
    // table port: D0 reads, LOAD_TAB writes (never in the same cycle: loads only when idle)
    always_comb begin
        t_we    = acc && in_op == OP_LOAD_TAB;
        t_ce    = t_we || d0_v;
        t_addr  = t_we ? in_addr : (ctb[d0_c] + ck[d0_c]);
        t_wdata = in_data[31:0];
    end

    // ------------------------------------------------------------------ seeder stage-A input
    logic na_v, na_b; logic [1:0] na_bs; logic [LA-1:0] na_c; logic [LG-1:0] na_g; logic [31:0] na_val [SEEDL];
    logic s_toB; logic [31:0] s_f;
    always_comb begin
        na_v = 1'b0; na_b = 1'b0; na_bs = '0; na_c = scx; na_g = sgrp; s_toB = 1'b0;
        s_f = fmix_f(pbval[0]);
        for (int l = 0; l < SEEDL; l++) na_val[l] = '0;
        if (sst == 2'd1) begin
            if (pbv && pbb) begin
                if (pbbs < 2'd2) begin
                    na_v = 1'b1; na_b = 1'b1; na_bs = pbbs + 2'd1; na_c = scx;
                    na_val[0] = fmix_a(s_f ^ ((pbbs == 2'd0) ? cseed[scx][63:32] : 32'(cr[scx])));
                end else s_toB = 1'b1;
            end
        end else if (sst == 2'd2) begin
            na_v = 1'b1; na_b = 1'b0; na_c = scx; na_g = sgrp;
            for (int l = 0; l < SEEDL; l++) na_val[l] = fmix_a(sWl[l]);
        end else if (s_pop) begin
            na_v = 1'b1; na_b = 1'b1; na_bs = 2'd0; na_c = s_pk[LA-1:0];
            na_val[0] = cfa1[s_pk[LA-1:0]];
        end
    end
    // seeder stage C (combinational per lane)
    logic [31:0] sc_x [SEEDL];
    logic [PMAX-1:0] sc_s [SEEDL];
    logic sc_m [SEEDL];
    always_comb begin
        for (int l = 0; l < SEEDL; l++) begin
            logic [31:0] stt; logic signed [3:0] m; int j;
            j = int'(pbg) * SEEDL + l;
            stt = fmix_f(pbval[l]); if (stt == 32'd0) stt = PHI;
            sc_x[l] = xs32(stt);
            m = '0;
`ifdef APE_FA_BAL
            begin
                logic [31:0] w; logic [63:0] pr; logic [PMAX-1:0] pat; int C;
`ifdef APE_PHILOX
                w = philox_word(32'hFFFF_FFFF, 32'(j), 32'(cr[pbc]), cinst[pbc], cseed[pbc][31:0], cseed[pbc][63:32], 0);
`else
                w = sc_x[l];
`endif
                C = (cP[pbc] == 3'd2) ? 2 : (cP[pbc] == 3'd4) ? 6 : 20;
                pr = 64'(w) * 64'(C);
                pat = bal_pat(cP[pbc], 5'(pr[63:32]));
                for (int p = 0; p < PMAX; p++) sc_s[l][p] = (p < cP[pbc]) ? pat[p] : 1'b1;
            end
`else
            for (int p = 0; p < PMAX; p++) begin
                if (p < cP[pbc]) begin
`ifdef APE_PHILOX
                    sc_s[l][p] = philox_word(32'hFFFF_FFFF, 32'(p) * D + j, 32'(cr[pbc]), cinst[pbc], cseed[pbc][31:0],
                                             cseed[pbc][63:32], 0) >= 32'h8000_0000;
`else
                    sc_s[l][p] = sc_x[l][31 - p];
`endif
                    m = m + (sc_s[l][p] ? 4'sd1 : -4'sd1);
                end else sc_s[l][p] = 1'b1;
            end
`endif
            sc_m[l] = (m != 0);
        end
    end
    logic sc_v; assign sc_v = pbv && !pbb;
    logic [D-1:0] cipend_n [A];
    logic         cipany_n [A];
    always_comb begin
        // next any-flag without the priority encoder: pop clears all; an I-op clears the lowest pending bit
        // (x & (x - 1)); stage C sets its group's lanes (their m != 0 bits)
        for (int c = 0; c < A; c++) begin
            logic grp_any; logic rest_any;
            grp_any = 1'b0;
            if (sc_v && c == int'(pbc)) for (int l = 0; l < SEEDL; l++) grp_any = grp_any | sc_m[l];
            rest_any = (f1_init && c == int'(f1_c)) ? |(cipend[c] & (cipend[c] - D'(1))) : cipany[c];
            if (sc_v && c == int'(pbc)) begin
                // lanes of the stage-C group are overwritten: recompute the rest without them
                logic [D-1:0] keep; keep = cipend[c];
                for (int j = 0; j < D; j++) if ((j / SEEDL) == int'(pbg)) keep[j] = 1'b0;
                if (f1_init && c == int'(f1_c)) keep = keep & (cipend[c] - D'(1));
                rest_any = |keep;
            end
            cipany_n[c] = (s_pop && c == int'(s_pk[LA-1:0])) ? 1'b0 : (grp_any | rest_any);
        end
    end
    always_comb begin
        for (int c = 0; c < A; c++) begin
            cipend_n[c] = cipend[c];
            for (int j = 0; j < D; j++) begin
                if (s_pop && c == int'(s_pk[LA-1:0])) cipend_n[c][j] = 1'b0;
                else if (sc_v && c == int'(pbc) && (j / SEEDL) == int'(pbg)) cipend_n[c][j] = sc_m[j % SEEDL];
                else if (f1_init && c == int'(f1_c) && j == int'(f1_i)) cipend_n[c][j] = 1'b0;
            end
        end
    end

    // ------------------------------------------------------------------ sequential logic
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (int c = 0; c < A; c++) begin st[c] <= S_IDLE; csdone[c] <= 1'b0; cpend[c] <= '0; cipend[c] <= '0; cscan[c] <= '0;
                                              cpany[c] <= 1'b0; cipany[c] <= 1'b0; end
            rqv[0] <= 1'b0; rqv[1] <= 1'b0; rr <= LA'(A - 1);
            d1v <= 1'b0; d2v <= 1'b0; f2v <= 1'b0; sst <= 2'd0; pav <= 1'b0; pbv <= 1'b0; obusy <= 1'b0;
            out_valid <= 1'b0;
        end else begin
            // ---------------- output unit
            out_valid <= 1'b0;
            if (obusy) begin
                out_valid <= 1'b1; out_tag <= ctag[oc]; out_r <= cr[oc]; out_p <= obeat;
                out_bits <= cbs[oc][obeat]; out_de <= cbest[oc];
                if (obeat == cP[oc] - 3'd1) begin st[oc] <= S_IDLE; obusy <= 1'b0; end
                else obeat <= obeat + 3'd1;
            end else if (o_pk[LA]) begin
                if (cde[o_pk[LA-1:0]] < cbest[o_pk[LA-1:0]]) begin
                    cbest[o_pk[LA-1:0]] <= cde[o_pk[LA-1:0]];
                    for (int p = 0; p < PMAX; p++) cbs[o_pk[LA-1:0]][p] <= cs[o_pk[LA-1:0]][p];
                end
                st[o_pk[LA-1:0]] <= S_OUT; obusy <= 1'b1; oc <= o_pk[LA-1:0]; obeat <= 3'd0;
            end
            // ---------------- assignment and run queue
            if (a_do) begin
                cP[a_pk[LA-1:0]] <= rqP[0]; cS[a_pk[LA-1:0]] <= rqS[0]; ctb[a_pk[LA-1:0]] <= rqtb[0];
                cq[a_pk[LA-1:0]] <= rqq[0]; cinst[a_pk[LA-1:0]] <= rqinst[0]; cseed[a_pk[LA-1:0]] <= rqseed[0];
                ctag[a_pk[LA-1:0]] <= rqtag[0]; cr[a_pk[LA-1:0]] <= rqnr[0];
                cfa1[a_pk[LA-1:0]] <= fmix_a(rqseed[0][31:0] ^ rqinst[0]);
                st[a_pk[LA-1:0]] <= S_SEEDQ;
            end
            begin
                logic v0, v1;
                v0 = rqv[0]; v1 = rqv[1];
                if (a_do && !a_pop) rqnr[0] <= rqnr[0] + 12'd1;
                if (a_pop) begin
                    rqv[0] <= rqv[1]; rqP[0] <= rqP[1]; rqR[0] <= rqR[1]; rqS[0] <= rqS[1]; rqtb[0] <= rqtb[1];
                    rqq[0] <= rqq[1]; rqinst[0] <= rqinst[1]; rqseed[0] <= rqseed[1]; rqtag[0] <= rqtag[1];
                    rqnr[0] <= rqnr[1]; rqv[1] <= 1'b0;
                    v0 = rqv[1]; v1 = 1'b0;
                end
                if (acc && in_op == OP_RUN) begin
                    if (!v0) begin
                        rqv[0] <= 1'b1; rqP[0] <= in_data[2:0]; rqR[0] <= in_data[14:3]; rqS[0] <= in_data[24:15];
                        rqtb[0] <= in_data[34:25]; rqq[0] <= in_data[50:35]; rqinst[0] <= in_data[82:51];
                        rqseed[0] <= in_data[146:83]; rqtag[0] <= in_data[162:147]; rqnr[0] <= 12'd0;
                    end else begin
                        rqv[1] <= 1'b1; rqP[1] <= in_data[2:0]; rqR[1] <= in_data[14:3]; rqS[1] <= in_data[24:15];
                        rqtb[1] <= in_data[34:25]; rqq[1] <= in_data[50:35]; rqinst[1] <= in_data[82:51];
                        rqseed[1] <= in_data[146:83]; rqtag[1] <= in_data[162:147]; rqnr[1] <= 12'd0;
                    end
                end
            end
            // ---------------- coefficient loads
            if (acc && in_op == OP_LOAD_ROW) diag[in_addr[LD-1:0]] <= in_data[in_addr[LD-1:0]*CW +: CW];
            if (acc && in_op == OP_LOAD_H) for (int j = 0; j < D; j++) hh[j] <= in_data[j*CW +: CW];
            // ---------------- seeder: stage C writes
            if (sc_v) begin
                for (int l = 0; l < SEEDL; l++) begin
                    int j; j = int'(pbg) * SEEDL + l;
                    crng[pbc][j] <= sc_x[l];
                    for (int p = 0; p < PMAX; p++) cs[pbc][p][j] <= sc_s[l][p];
                end
                if (pbg == LG'(NG - 1)) csdone[pbc] <= 1'b1;
            end
            // stage B
            pbv <= pav; pbb <= pab; pbbs <= pabs; pbc <= pac; pbg <= pag;
            for (int l = 0; l < SEEDL; l++) pbval[l] <= fmix_b(paval[l]);
            // stage A and FSM
            pav <= na_v; pab <= na_b; pabs <= na_bs; pac <= na_c; pag <= na_g;
            for (int l = 0; l < SEEDL; l++) paval[l] <= na_val[l];
            if (sst == 2'd1) begin
                if (s_toB) begin
                    sW <= s_f + PHI; sst <= 2'd2; sgrp <= '0;
                    for (int l = 0; l < SEEDL; l++) sWl[l] <= s_f + PHI + 32'(l) * PHI;
                end
            end else if (sst == 2'd2) begin
                sW <= sW + 32'(SEEDL) * PHI;
                for (int l = 0; l < SEEDL; l++) sWl[l] <= sWl[l] + 32'(SEEDL) * PHI;
                if (sgrp == LG'(NG - 1)) sst <= 2'd0;
                sgrp <= sgrp + LG'(1);
            end else if (s_pop) begin
                sst <= 2'd1; scx <= s_pk[LA-1:0];
                for (int j = 0; j < D; j++) cw[s_pk[LA-1:0]][j] <= WW'(hh[j]);
                cde[s_pk[LA-1:0]] <= '0; cbest[s_pk[LA-1:0]] <= EMAX;
                ck[s_pk[LA-1:0]] <= '0; cpp[s_pk[LA-1:0]] <= '0; cn[s_pk[LA-1:0]] <= '0; csdone[s_pk[LA-1:0]] <= 1'b0;
                cscan[s_pk[LA-1:0]] <= '0;
                st[s_pk[LA-1:0]] <= S_INIT;
            end
            // ipend: seeder pop clears, stage C sets its lanes, an I-op clears its row (distinct bits); any-flag registered
            for (int c = 0; c < A; c++) begin cipend[c] <= cipend_n[c]; cipany[c] <= cipany_n[c]; end
            // ---------------- R-port F2
            f2v <= 1'b0;
            if (f2v) begin
                for (int j = 0; j < D; j++) cw[f2c][j] <= f2_wnew[j];
                if (f2flip) begin cde[f2c] <= f2_denew; cs[f2c][cpp[f2c]][f2i] <= !f2so; end
                if (f2flip && !f2last) st[f2c] <= S_READY;       // re-test the lanes after m; ck held
                if (f2flip && f2last) begin
                    cscan[f2c] <= '0;
                    ck[f2c] <= ck[f2c] + 10'd1;
                    if (cpp[f2c] + 3'd1 == cP[f2c]) begin cpp[f2c] <= 3'd0; cn[f2c] <= cn[f2c] + 10'd1; end
                    else cpp[f2c] <= cpp[f2c] + 3'd1;
                    st[f2c] <= (ck[f2c] == cS[f2c] - 10'd1) ? S_OUTQ : S_READY;
                end
            end
            // ---------------- R-port F1
            if (f1_v) begin
                f2v <= 1'b1; f2c <= f1_c; f2i <= f1_i; f2flip <= f1_flip; f2last <= f1_last; f2mu <= f1_mu; f2so <= f1_so;
                if (f1_flip) begin
                    cpend[f1_c] <= '0;                                       // first-accept: the rest of F is dropped
                    cpany[f1_c] <= 1'b0;
                    cscan[f1_c] <= f1_oh | (f1_oh - D'(1));                  // lanes up to m are scanned
                end
            end
            // ---------------- INIT -> READY
            for (int c = 0; c < A; c++) if (init_ok[c]) st[c] <= S_READY;
            // ---------------- D2
            d2v <= 1'b0;
            if (d2v) begin
                cpend[d2c] <= d2_cand;
                cpany[d2c] <= |d2_cand;
                if (|d2_cand) st[d2c] <= S_FLIP;
                else begin
                    cscan[d2c] <= '0;
                    ck[d2c] <= ck[d2c] + 10'd1;
                    if (cpp[d2c] + 3'd1 == cP[d2c]) begin cpp[d2c] <= 3'd0; cn[d2c] <= cn[d2c] + 10'd1; end
                    else cpp[d2c] <= cpp[d2c] + 3'd1;
                    st[d2c] <= (ck[d2c] == cS[d2c] - 10'd1) ? S_OUTQ : S_READY;
                end
            end
            // ---------------- D1
            d1v <= 1'b0;
            if (d1v && d1chk && (cde[d1c] < cbest[d1c])) begin   // best check of the state after step k-1 (v1.4)
                cbest[d1c] <= cde[d1c];
                for (int p = 0; p < PMAX; p++) cbs[d1c][p] <= cs[d1c][p];
            end
            if (d1v) begin
`ifndef APE_PHILOX
                for (int j = 0; j < D; j++) crng[d1c][j] <= d1_rng[j];
`endif
                for (int j = 0; j < D; j++) begin d2u[j] <= d1_u[j]; d2sw[j] <= d1_sw[j]; end
                d2a4 <= d1_a4;
                d2b <= d1_b; d2v <= 1'b1; d2c <= d1c;
            end
            // ---------------- D0
            if (d0_v) begin
                st[d0_c] <= S_DEC; rr <= d0_c;
                d1v <= 1'b1; d1c <= d0_c; d1p <= cpp[d0_c]; d1n <= cn[d0_c]; d1chk <= d0_best;
            end
        end
    end
endmodule
`default_nettype wire
