// Verilator harness of tb_arpeggio: replays stim.txt ("<op> <addr> <hex data>"), one command per cycle until accepted, then waits for idle.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
#include "Vtb_arpeggio.h"
#include "verilated.h"
struct C { int op, addr; std::string hex; };
static Vtb_arpeggio* t;
static void edge() { t->clk = 0; t->eval(); t->clk = 1; t->eval(); }
static void drive(const C& c) {
    t->in_valid = 1; t->in_op = c.op; t->in_addr = c.addr;
    const int W = sizeof(t->in_data) / 4;
    for (int i = 0; i < W; i++) t->in_data[i] = 0;
    int n = c.hex.size();
    for (int i = 0; i < n; i++) {                 // hex digit i from the right
        char ch = c.hex[n - 1 - i];
        unsigned v = (ch <= '9') ? ch - '0' : (ch | 32) - 'a' + 10;
        if (i / 8 < W) t->in_data[i / 8] |= v << ((i % 8) * 4);
    }
}
int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    t = new Vtb_arpeggio;
    std::vector<C> v;
    std::ifstream f("stim.txt"); C c;
    while (f >> c.op >> c.addr >> c.hex) v.push_back(c);
    t->rst_n = 0; t->in_valid = 0; t->in_op = 0;
    for (int i = 0; i < 4; i++) edge();
    t->rst_n = 1;
    size_t idx = 0; int idle = 0; long long cyc = 0, cap = getenv("TB_CAP") ? atoll(getenv("TB_CAP")) : 2000000000LL;
    while (cyc < cap) {
        t->clk = 0; t->eval();
        if (idx < v.size()) drive(v[idx]); else { t->in_valid = 0; t->in_op = 0; }
        t->eval();
        bool acc = t->in_valid && t->in_ready;
        t->clk = 1; t->eval();
        if (acc) idx++;
        cyc++;
        if (idx >= v.size() && !t->busy && !t->out_valid) { if (++idle > 4) break; } else idle = 0;
    }
    t->final();
    printf("%s commands %zu cycles %lld\n", cyc >= cap ? "TB_CAP_HIT" : "TB_DONE", v.size(), cyc);
    delete t;
    return cyc >= cap;
}
