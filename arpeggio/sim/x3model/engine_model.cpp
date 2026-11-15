// Chord engine: cycle-accurate model of the micro-architecture, the cycle-level twin of the RTL
// (arpeggio/rtl/engine/chord_engine.sv). One call of Engine::cycle() is one clock edge. Results must equal chord_ref.py;
// the RTL's output beats (cycle, tag, anneal, copy, bits, Δbest) and command-accept cycles must equal this model's.
//
// Conventions (also the RTL's):
//  * every value read in a cycle is its start-of-cycle value (snapshots below); writes take effect at the end;
//  * memories: address in cycle t, data in cycle t+1;
//  * priorities: assignment, seeder pop, R-port and output pick the lowest-index eligible context; the decision unit
//    picks round robin after the last context it served; the R-port serves F-ops (flips) before I-ops (start rows).
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace chord {

static const uint32_t PHI = 0x9E3779B9u;
static inline uint32_t fmix_a(uint32_t v) { return (v ^ (v >> 16)) * 0x85EBCA6Bu; }
static inline uint32_t fmix_b(uint32_t h) { return (h ^ (h >> 13)) * 0xC2B2AE35u; }
static inline uint32_t fmix_f(uint32_t h) { return h ^ (h >> 16); }
static inline uint32_t xs32(uint32_t x) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }

static inline uint32_t philox_word(uint32_t c0, uint32_t c1, uint32_t c2, uint32_t c3, uint32_t k0, uint32_t k1, int w) {
  uint32_t c[4] = {c0, c1, c2, c3};
  for (int i = 0; i < 10; ++i) {
    if (i) { k0 += 0x9E3779B9u; k1 += 0xBB67AE85u; }
    uint64_t p0 = (uint64_t)0xD2511F53u * c[0], p1 = (uint64_t)0xCD9E8D57u * c[2];
    uint32_t n0 = (uint32_t)(p1 >> 32) ^ c[1] ^ k0, n2 = (uint32_t)(p0 >> 32) ^ c[3] ^ k1;
    c[1] = (uint32_t)p1; c[3] = (uint32_t)p0; c[0] = n0; c[2] = n2;
  }
  return c[w];
}

enum Op { OP_NOP = 0, OP_LOAD_ROW = 1, OP_LOAD_H = 2, OP_LOAD_TAB = 3, OP_RUN = 4 };
struct Cmd {
  int32_t op, addr, P, R, S, tb, q, tag, T, c;
  uint32_t inst; uint32_t pad; uint64_t seed; int64_t data_off;   // data_off: index into the int16 data buffer (D values)
};
struct Beat { long long cycle; int tag, r, p; long long de; std::vector<uint8_t> bits; };

enum St { IDLE = 0, SEEDQ, INIT, READY, DEC, FLIP, OUTQ, OUT };

static const int PMAX = 6;
static const int TABD = 1024;
static const long long EMAX = (1LL << 35) - 1;   // 36-bit signed maximum
static const int LB = 7;                          // seeder: pop to first lane group entering stage A

struct Ctx {
  int st = IDLE;
  int P = 2, S = 1, tb = 0, q = 0, r = 0, tag = 0; uint32_t inst = 0; uint64_t seed = 0;
  int k = 0, p = 0, n = 0;
  std::vector<int8_t> s, bs;         // [PMAX][D]
  std::vector<int32_t> w;            // [D]
  std::vector<uint32_t> rng;         // [D]
  std::vector<uint8_t> pend, ipend;  // [D]
  long long de = 0, best = EMAX;
  bool seed_done = false;
};
struct Run { int P, R, S, tb, q, tag; uint32_t inst; uint64_t seed; int next_r; };
struct SItem { bool v = false; bool bchain = false; int bstep = 0; int c = 0; int g = 0; std::vector<uint32_t> val; };

struct Engine {
  int D, A, SEEDL, philox, RB;
  long long cyc = 0;
  std::vector<int16_t> G, diag, h, tT, tC;
  std::vector<Ctx> cx;
  std::vector<Run> rq;
  int rr = 0;                          // index of the last context served by D0 (initially A-1 -> context 0 first)
  bool d1v = false; int d1c = 0, d1p = 0, d1n = 0, d1taddr = 0;
  bool d2v = false; int d2c = 0; std::vector<int64_t> d2prod, d2sw; int64_t d2b = 0;
  bool f2v = false; int f2c = 0, f2i = 0, f2mu = 0; bool f2flip = false, f2last = false;
  // seeder FSM: 0 idle, 1 B chain, 2 lanes
  int sst = 0, scx = 0, sgrp = 0; uint32_t sW = 0;
  SItem pa, pb;                        // pipeline registers after stage A and after stage B
  bool obusy = false; int oc = 0, obeat = 0;
  long long n_dop = 0, n_fop = 0, n_iop = 0, n_beats = 0, n_rport_busy = 0;
  bool idle0 = true;                   // engine idle at the start of this cycle

  Engine(int D_, int A_, int SEEDL_, int philox_) : D(D_), A(A_), SEEDL(SEEDL_), philox(philox_) {
    RB = philox ? 32 : 16;
    G.assign(D * D, 0); diag.assign(D, 0); h.assign(D, 0); tT.assign(TABD, 0); tC.assign(TABD, 0);
    cx.resize(A);
    for (auto& c : cx) { c.s.assign(PMAX * D, 1); c.bs.assign(PMAX * D, 1); c.w.assign(D, 0); c.rng.assign(D, 0);
                         c.pend.assign(D, 0); c.ipend.assign(D, 0); }
    d2prod.assign(D, 0); d2sw.assign(D, 0); rr = A - 1;
  }
  bool idle_now() const {
    if (!rq.empty() || sst || pa.v || pb.v || obusy || d1v || d2v || f2v) return false;
    for (auto& c : cx) if (c.st != IDLE) return false;
    return true;
  }
  static bool any(const std::vector<uint8_t>& v) { for (auto x : v) if (x) return true; return false; }
  static int lowest(const std::vector<uint8_t>& v) { for (size_t i = 0; i < v.size(); ++i) if (v[i]) return (int)i; return -1; }

  void advance(Ctx& x) {
    bool last = (x.k == x.S - 1);
    x.k++; if (++x.p == x.P) { x.p = 0; x.n++; }
    x.st = last ? OUTQ : READY;
  }

  // one clock cycle; returns true if *cmd was accepted at this edge
  bool cycle(const Cmd* cmd, const int16_t* dbuf, std::vector<Beat>* out) {
    // ---------------- start-of-cycle snapshots
    std::vector<int> st0(A); std::vector<bool> init_ok(A), flip_av(A), init_av(A);
    for (int c = 0; c < A; ++c) {
      st0[c] = cx[c].st;
      init_ok[c] = (st0[c] == INIT) && cx[c].seed_done && !any(cx[c].ipend);
      flip_av[c] = (st0[c] == FLIP) && any(cx[c].pend);
      init_av[c] = (st0[c] == INIT) && any(cx[c].ipend);
    }
    const size_t rq_n0 = rq.size();
    const bool idle_start = idle0;
    const SItem pa0 = pa, pb0 = pb;      // seeder pipeline registers
    const int sst0 = sst;

    // ---------------- output unit
    if (obusy) {
      Ctx& c = cx[oc];
      if (out) { Beat b; b.cycle = cyc; b.tag = c.tag; b.r = c.r; b.p = obeat; b.de = c.best;
                 b.bits.resize(D); for (int j = 0; j < D; ++j) b.bits[j] = c.bs[obeat * D + j] > 0; out->push_back(b); }
      ++n_beats;
      if (obeat == c.P - 1) { c.st = IDLE; obusy = false; } else ++obeat;
    } else {
      int pk = -1; for (int c = 0; c < A; ++c) if (st0[c] == OUTQ) { pk = c; break; }
      if (pk >= 0) {
        Ctx& c = cx[pk];
        if (c.de < c.best) { c.best = c.de; c.bs = c.s; }          // final best check
        c.st = OUT; obusy = true; oc = pk; obeat = 0;
      }
    }
    // ---------------- assignment
    if (rq_n0 > 0) {
      int c = -1; for (int i = 0; i < A; ++i) if (st0[i] == IDLE) { c = i; break; }
      if (c >= 0) {
        Run& r = rq.front(); Ctx& x = cx[c];
        x.P = r.P; x.S = r.S; x.tb = r.tb; x.q = r.q; x.inst = r.inst; x.seed = r.seed; x.tag = r.tag; x.r = r.next_r;
        x.st = SEEDQ;
        if (++r.next_r == r.R) rq.erase(rq.begin());
      }
    }
    // ---------------- seeder: stage C (finalise, xorshift, write) from pb0
    if (pb0.v && !pb0.bchain) {
      Ctx& x = cx[pb0.c];
      for (int l = 0; l < SEEDL; ++l) {
        int j = pb0.g * SEEDL + l;
        uint32_t stt = fmix_f(pb0.val[l]); if (stt == 0) stt = PHI;
        uint32_t xo = xs32(stt);
        x.rng[j] = xo;
        int m = 0;
        for (int p = 0; p < PMAX; ++p) {
          int sv = 1;
          if (p < x.P) {
            if (philox) sv = philox_word(0xFFFFFFFFu, (uint32_t)(p * D + j), (uint32_t)x.r, x.inst,
                                         (uint32_t)x.seed, (uint32_t)(x.seed >> 32), 0) >= 0x80000000u ? 1 : -1;
            else sv = ((xo >> (31 - p)) & 1u) ? 1 : -1;
            m += sv;
          }
          x.s[p * D + j] = (int8_t)sv;
        }
        x.ipend[j] = (m != 0);
      }
      if (pb0.g == D / SEEDL - 1) x.seed_done = true;
    }
    // stage B: pa0 -> pb
    pb.v = pa0.v; pb.bchain = pa0.bchain; pb.bstep = pa0.bstep; pb.c = pa0.c; pb.g = pa0.g;
    if (pa0.v) { pb.val.resize(pa0.val.size()); for (size_t l = 0; l < pa0.val.size(); ++l) pb.val[l] = fmix_b(pa0.val[l]); }
    // stage A input and FSM
    SItem na; na.v = false;
    if (sst0 == 1) {                                  // B chain: wait for the item leaving stage B (pb0)
      if (pb0.v && pb0.bchain) {
        Ctx& x = cx[scx];
        uint32_t f = fmix_f(pb0.val[0]);
        if (pb0.bstep < 2) {
          uint32_t v = f ^ (pb0.bstep == 0 ? (uint32_t)(x.seed >> 32) : (uint32_t)x.r);
          na.v = true; na.bchain = true; na.bstep = pb0.bstep + 1; na.c = scx; na.val.assign(1, fmix_a(v));
        } else { sW = f + PHI; sst = 2; sgrp = 0; }
      }
    } else if (sst0 == 2) {                           // lane groups
      na.v = true; na.bchain = false; na.c = scx; na.g = sgrp; na.val.resize(SEEDL);
      for (int l = 0; l < SEEDL; ++l) na.val[l] = fmix_a(sW + (uint32_t)l * PHI);
      sW += (uint32_t)SEEDL * PHI;
      if (++sgrp == D / SEEDL) sst = 0;
    }
    if (sst0 == 0) {                                  // pop the lowest SEEDQ context
      int c = -1; for (int i = 0; i < A; ++i) if (st0[i] == SEEDQ) { c = i; break; }
      if (c >= 0) {
        Ctx& x = cx[c];
        sst = 1; scx = c;
        na.v = true; na.bchain = true; na.bstep = 0; na.c = c; na.val.assign(1, fmix_a((uint32_t)x.seed ^ x.inst));
        for (int j = 0; j < D; ++j) { x.w[j] = h[j]; x.ipend[j] = 0; }
        x.de = 0; x.best = EMAX; x.k = 0; x.p = 0; x.n = 0; x.seed_done = false;
        x.st = INIT;
      }
    }
    pa = na;
    // ---------------- R-port stage F2
    int f2_done = -1;
    if (f2v) {
      Ctx& x = cx[f2c];
      const int16_t* row = &G[f2i * D];
      if (f2flip) x.de += 4LL * f2mu * x.w[f2i] + 8LL * diag[f2i];
      for (int j = 0; j < D; ++j) x.w[j] += 4 * f2mu * row[j];
      if (f2flip && f2last) f2_done = f2c;
      f2v = false;
    }
    // ---------------- R-port stage F1
    {
      int cf = -1; for (int c = 0; c < A; ++c) if (flip_av[c]) { cf = c; break; }
      if (cf >= 0) {
        Ctx& x = cx[cf];
        int i = lowest(x.pend); x.pend[i] = 0;
        int so = x.s[x.p * D + i]; x.s[x.p * D + i] = (int8_t)-so;
        f2v = true; f2c = cf; f2i = i; f2mu = so; f2flip = true; f2last = !any(x.pend);
        ++n_fop; ++n_rport_busy;
      } else {
        int ci = -1; for (int c = 0; c < A; ++c) if (init_av[c]) { ci = c; break; }
        if (ci >= 0) {
          Ctx& x = cx[ci];
          int i = lowest(x.ipend); x.ipend[i] = 0;
          int m = 0; for (int p = 0; p < x.P; ++p) m += x.s[p * D + i];
          f2v = true; f2c = ci; f2i = i; f2mu = -m / 2; f2flip = false; f2last = false;
          ++n_iop; ++n_rport_busy;
        }
      }
    }
    // ---------------- INIT -> READY
    for (int c = 0; c < A; ++c) if (init_ok[c]) cx[c].st = READY;
    // ---------------- decision D2
    if (d2v) {
      Ctx& x = cx[d2c];
      bool anyf = false;
      for (int j = 0; j < D; ++j) {
        __int128 zp = (__int128)d2sw[j] + 2 * (int64_t)diag[j] + d2b;
        bool f = (__int128)d2prod[j] > zp * ((__int128)1 << RB);
        x.pend[j] = f; anyf = anyf || f;
      }
      if (anyf) x.st = FLIP; else advance(x);
      d2v = false;
    }
    if (f2_done >= 0) advance(cx[f2_done]);
    // ---------------- decision D1
    if (d1v) {
      Ctx& x = cx[d1c];
      int T = tT[d1taddr], cc = tC[d1taddr];
      int64_t Aq = 4LL * T;
      d2b = (int64_t)x.q - cc + 2LL * T;
      for (int j = 0; j < D; ++j) {
        uint64_t u;
        if (philox) u = philox_word((uint32_t)(d1n >> 2), (uint32_t)(d1p * D + j), (uint32_t)x.r, x.inst,
                                    (uint32_t)x.seed, (uint32_t)(x.seed >> 32), d1n & 3);
        else { x.rng[j] = xs32(x.rng[j]); u = x.rng[j] >> 16; }
        d2prod[j] = (int64_t)u * Aq;
        d2sw[j] = (int64_t)x.s[d1p * D + j] * x.w[j];
      }
      d2v = true; d2c = d1c; d1v = false;
    }
    // ---------------- decision D0
    {
      int c = -1;
      for (int o = 1; o <= A; ++o) { int i = (rr + o) % A; if (st0[i] == READY) { c = i; break; } }
      if (c >= 0) {
        Ctx& x = cx[c];
        if (x.k >= 1 && x.de < x.best) { x.best = x.de; x.bs = x.s; }
        x.st = DEC; rr = c;
        d1v = true; d1c = c; d1p = x.p; d1n = x.n; d1taddr = (x.tb + x.k) & (TABD - 1);
        ++n_dop;
      }
    }
    // ---------------- command intake
    bool acc = false;
    if (cmd && cmd->op != OP_NOP) {
      bool rdy = (cmd->op == OP_RUN) ? (rq_n0 < 2) : idle_start;
      if (rdy) {
        acc = true;
        const int16_t* d = dbuf ? dbuf + cmd->data_off : nullptr;
        if (cmd->op == OP_LOAD_ROW) { for (int j = 0; j < D; ++j) G[cmd->addr * D + j] = d[j]; diag[cmd->addr] = d[cmd->addr]; }
        else if (cmd->op == OP_LOAD_H) { for (int j = 0; j < D; ++j) h[j] = d[j]; }
        else if (cmd->op == OP_LOAD_TAB) { tT[cmd->addr] = (int16_t)cmd->T; tC[cmd->addr] = (int16_t)cmd->c; }
        else if (cmd->op == OP_RUN) {
          Run r; r.P = cmd->P; r.R = cmd->R; r.S = cmd->S; r.tb = cmd->tb; r.q = cmd->q; r.tag = cmd->tag;
          r.inst = cmd->inst; r.seed = cmd->seed; r.next_r = 0; rq.push_back(r);
        }
      }
    }
    idle0 = idle_now();
    ++cyc;
    return acc;
  }
};

}  // namespace chord

// ---------------------------------------------------------------- C interface (ctypes) and a file driver
extern "C" {
struct ApeStats { long long cycles, n_dop, n_fop, n_iop, n_beats, n_rport_busy; };

// Executes the commands in order (one presented per cycle until accepted), then runs until idle.
// acc_cycle[i] = cycle at which command i was accepted. Beats go to the arrays (up to max_beats).
long long engine_exec(int D, int A, int SEEDL, int philox, int ncmd, const chord::Cmd* cmds, const int16_t* dbuf,
                   long long* acc_cycle, int max_beats, int* nbeats, long long* b_cycle, int* b_tag, int* b_r, int* b_p,
                   long long* b_de, uint8_t* b_bits, ApeStats* st) {
  chord::Engine e(D, A, SEEDL, philox);
  std::vector<chord::Beat> beats; beats.reserve(1024);
  int i = 0;
  long long guard = 0;
  while (i < ncmd || !e.idle0 || e.cyc == 0) {
    const chord::Cmd* c = i < ncmd ? &cmds[i] : nullptr;
    bool a = e.cycle(c, dbuf, &beats);
    if (c && a) { if (acc_cycle) acc_cycle[i] = e.cyc - 1; ++i; }
    if (++guard > 2000000000LL) { fprintf(stderr, "engine_exec: no progress\n"); break; }
    if (i >= ncmd && e.idle0) break;
  }
  int nb = 0;
  for (auto& b : beats) {
    if (nb < max_beats) {
      b_cycle[nb] = b.cycle; b_tag[nb] = b.tag; b_r[nb] = b.r; b_p[nb] = b.p; b_de[nb] = b.de;
      for (int j = 0; j < D; ++j) b_bits[(size_t)nb * D + j] = b.bits[j];
    }
    ++nb;
  }
  *nbeats = nb;
  if (st) { st->cycles = e.cyc; st->n_dop = e.n_dop; st->n_fop = e.n_fop; st->n_iop = e.n_iop; st->n_beats = e.n_beats;
            st->n_rport_busy = e.n_rport_busy; }
  return e.cyc;
}
}

// ---------------------------------------------------------------- batch solver for the MDI wrapper
#include <thread>
#include <atomic>
extern "C" {
// Runs B independent sub-problems (one engine each): schedule table load (not counted), G rows, h, one RUN of R anneals.
// spins (B, R, P*D) int8 copy-major, de (B, R) = Δbest, cycles (B) from the first G-row command to idle,
// stats (B, 4) = D-ops, F-ops, I-ops, R-port busy cycles.
int engine_solve_batch(int D, int A, int SEEDL, int philox, int B, const int16_t* G, const int16_t* h, int P, int R, int S,
                    const int16_t* T, const int16_t* c, int q, const uint32_t* inst, uint64_t seed, int8_t* spins,
                    long long* de, long long* cycles, long long* stats, int nthreads) {
  std::atomic<int> next(0);
  auto work = [&]() {
    std::vector<chord::Beat> beats;
    for (;;) {
      int b = next.fetch_add(1);
      if (b >= B) break;
      chord::Engine e(D, A, SEEDL, philox);
      std::vector<chord::Cmd> cmds;
      std::vector<int16_t> dbuf((size_t)(D + 1) * D);
      for (int k = 0; k < S; ++k) { chord::Cmd m{}; m.op = chord::OP_LOAD_TAB; m.addr = k; m.T = T[k]; m.c = c[k]; cmds.push_back(m); }
      int first = (int)cmds.size();
      for (int i = 0; i < D; ++i) {
        for (int j = 0; j < D; ++j) dbuf[(size_t)i * D + j] = G[((size_t)b * D + i) * D + j];
        chord::Cmd m{}; m.op = chord::OP_LOAD_ROW; m.addr = i; m.data_off = (int64_t)i * D; cmds.push_back(m);
      }
      for (int j = 0; j < D; ++j) dbuf[(size_t)D * D + j] = h[(size_t)b * D + j];
      { chord::Cmd m{}; m.op = chord::OP_LOAD_H; m.data_off = (int64_t)D * D; cmds.push_back(m); }
      { chord::Cmd m{}; m.op = chord::OP_RUN; m.P = P; m.R = R; m.S = S; m.tb = 0; m.q = q; m.tag = 0; m.inst = inst[b]; m.seed = seed;
        cmds.push_back(m); }
      beats.clear();
      size_t i = 0; long long c0 = -1;
      while (i < cmds.size() || !e.idle0) {
        const chord::Cmd* cm = i < cmds.size() ? &cmds[i] : nullptr;
        bool a = e.cycle(cm, dbuf.data(), &beats);
        if (cm && a) { if ((int)i == first) c0 = e.cyc - 1; ++i; }
        if (i >= cmds.size() && e.idle0) break;
      }
      cycles[b] = e.cyc - c0;
      long long* sp = stats + (size_t)b * 4;
      sp[0] = e.n_dop; sp[1] = e.n_fop; sp[2] = e.n_iop; sp[3] = e.n_rport_busy;
      for (auto& bt : beats) {
        int8_t* dst = spins + (((size_t)b * R + bt.r) * P + bt.p) * D;
        for (int j = 0; j < D; ++j) dst[j] = bt.bits[j] ? 1 : -1;
        de[(size_t)b * R + bt.r] = bt.de;
      }
    }
  };
  std::vector<std::thread> th;
  for (int t = 0; t < std::max(1, nthreads); ++t) th.emplace_back(work);
  for (auto& x : th) x.join();
  return 0;
}
}
