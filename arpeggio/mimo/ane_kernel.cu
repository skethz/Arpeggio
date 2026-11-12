// Batched small dense Anechoic (DESIGN.md B3): fixed-point arithmetic and Philox4x32-10, bit-exact with
// anefx.anechoic_fx. One block per instance, one warp per anneal (a warp loops over anneals w, w + W, ...), the
// coupling matrix in shared memory (int16), lane L holding spins t*32 + L (t < MPL = N/32), warp-uniform spin masks,
// incremental field updates for the flipped spins (integers: equal to recomputation), the energy updated per flip
// (2 dE0 = 4 s_j u0_j, applied sequentially; one warp reduction per anneal at the start), the best state kept in
// registers. v2: no integer division in the step loop (phase and update counters kept incrementally). mode 0: per-anneal best state and energy; mode 1: the
// best anneal per instance (first minimum). stats (optional, 4 counters): flips, energy evaluations, Philox blocks,
// steps x anneals.
#include <stdint.h>
#include <limits.h>

#define FULL 0xffffffffu

__device__ __forceinline__ void philox10(uint32_t& c0, uint32_t& c1, uint32_t& c2, uint32_t& c3, uint32_t k0,
                                         uint32_t k1) {
#pragma unroll
  for (int i = 0; i < 10; ++i) {
    if (i) { k0 += 0x9E3779B9u; k1 += 0xBB67AE85u; }
    const uint32_t hi0 = __umulhi(0xD2511F53u, c0), lo0 = 0xD2511F53u * c0;
    const uint32_t hi1 = __umulhi(0xCD9E8D57u, c2), lo1 = 0xCD9E8D57u * c2;
    const uint32_t n0 = hi1 ^ c1 ^ k0, n2 = hi0 ^ c3 ^ k1;
    c0 = n0; c1 = lo1; c2 = n2; c3 = lo0;
  }
}

extern "C" __global__ void philox_kat(const uint32_t* in, uint32_t* out, int n) {
  const int t = blockIdx.x * blockDim.x + threadIdx.x;
  if (t >= n) return;
  uint32_t c0 = in[6 * t], c1 = in[6 * t + 1], c2 = in[6 * t + 2], c3 = in[6 * t + 3];
  philox10(c0, c1, c2, c3, in[6 * t + 4], in[6 * t + 5]);
  out[4 * t] = c0; out[4 * t + 1] = c1; out[4 * t + 2] = c2; out[4 * t + 3] = c3;
}

__device__ __forceinline__ int warp_sum(int v) {
#pragma unroll
  for (int o = 16; o; o >>= 1) v += __shfl_xor_sync(FULL, v, o);
  return v;
}

template <int MPL>
__device__ __forceinline__ void ane_body(const int16_t* __restrict__ Jg, const int32_t* __restrict__ hg,
                                         const int32_t* __restrict__ h0g, const int32_t* __restrict__ Tq,
                                         const int32_t* __restrict__ Cq, int q, int S, int P, int R, int N,
                                         uint32_t k0, uint32_t k1, int inst0, int mode, int32_t* __restrict__ out_e,
                                         int8_t* __restrict__ out_s, unsigned long long* __restrict__ stats) {
  extern __shared__ __align__(16) unsigned char smem[];
  int16_t* J = reinterpret_cast<int16_t*>(smem);
  int32_t* sh = reinterpret_cast<int32_t*>(smem + ((N * N * 2 + 15) & ~15));
  int32_t* sh0 = sh + N;
  int32_t* red_e = sh0 + N;     // 32 warps
  int32_t* red_r = red_e + 32;  // 32 warps
  const int b = blockIdx.x;
  const int lane = threadIdx.x & 31, w = threadIdx.x >> 5, W = blockDim.x >> 5;
  {
    const int4* src = reinterpret_cast<const int4*>(Jg + (size_t)b * N * N);
    int4* dst = reinterpret_cast<int4*>(J);
    for (int x = threadIdx.x; x < N * N / 8; x += blockDim.x) dst[x] = src[x];
    for (int x = threadIdx.x; x < N; x += blockDim.x) { sh[x] = hg[(size_t)b * N + x]; sh0[x] = h0g[(size_t)b * N + x]; }
  }
  __syncthreads();
  const uint32_t inst = (uint32_t)(inst0 + b);
  const int tpc = (N / P) >> 5;  // slots t per copy
  int32_t hv[MPL], hc[MPL], cp[MPL];
#pragma unroll
  for (int t = 0; t < MPL; ++t) { const int i = t * 32 + lane; hv[t] = sh[i]; hc[t] = sh[i] - 2 * sh0[i]; cp[t] = t / tpc; }
  int32_t wbest_e = INT_MAX, wbest_r = INT_MAX;
  uint32_t wbest_bits = 0;
  unsigned long long n_flip = 0, n_eval = 0, n_rng = 0;
  for (int r = w; r < R; r += W) {
    uint32_t Sm[MPL];
#pragma unroll
    for (int t = 0; t < MPL; ++t) {
      uint32_t c0 = 0xFFFFFFFFu, c1 = (uint32_t)(t * 32 + lane), c2 = (uint32_t)r, c3 = inst;
      philox10(c0, c1, c2, c3, k0, k1);
      Sm[t] = __ballot_sync(FULL, c0 >= 0x80000000u);
    }
    int32_t u[MPL];
#pragma unroll
    for (int t = 0; t < MPL; ++t) {
      const int16_t* Ji = J + (t * 32 + lane) * N;
      int32_t acc = 0;
#pragma unroll
      for (int tt = 0; tt < MPL; ++tt) {
        const uint32_t m = Sm[tt];
        for (int l = 0; l < 32; ++l) { const int32_t v = Ji[tt * 32 + l]; acc += ((m >> l) & 1u) ? v : -v; }
      }
      u[t] = hv[t] + 2 * acc;
    }
    uint32_t r0[MPL], r1[MPL], r2[MPL], r3[MPL];
    uint32_t pf = 0, best_bits = 0;
    int32_t best_e = INT_MAX;
    int32_t e = 0;                                   // 2 E0 of the current state
#pragma unroll
    for (int t = 0; t < MPL; ++t) e += (((Sm[t] >> lane) & 1u) ? 1 : -1) * (hc[t] - u[t]);
    e = warp_sum(e);
    int p = 0, n = 0;
    for (int k = 0; k < S; ++k) {
      const int nm = n & 3;
      const int32_t T = Tq[k], c = Cq[k];
      const long long T4 = 4LL * T;
      uint32_t fl = 0;
#pragma unroll
      for (int t = 0; t < MPL; ++t) {
        if (cp[t] != p) continue;
        if (nm == 0) {
          uint32_t c0 = (uint32_t)(n >> 2), c1 = (uint32_t)(t * 32 + lane), c2 = (uint32_t)r, c3 = inst;
          philox10(c0, c1, c2, c3, k0, k1);
          r0[t] = c0; r1[t] = c1; r2[t] = c2; r3[t] = c3;
          if (stats) ++n_rng;
        }
        const uint32_t x = nm == 0 ? r0[t] : nm == 1 ? r1[t] : nm == 2 ? r2[t] : r3[t];
        const int32_t s = ((Sm[t] >> lane) & 1u) ? 1 : -1;
        const int32_t z = s * u[t] + q - c * (((pf >> t) & 1u) ? -1 : 1);
        if ((long long)x * T4 > (long long)(z + 2 * T) * 4294967296LL) fl |= 1u << t;
      }
      pf = fl;
      bool any = false;
#pragma unroll
      for (int t = 0; t < MPL; ++t) {
        const uint32_t F = __ballot_sync(FULL, (fl >> t) & 1u);
        if (F) {
          any = true;
          uint32_t m = F;
          while (m) {
            const int l = __ffs(m) - 1;
            m &= m - 1;
            const int j = t * 32 + l;
            const int16_t* Jj = J + j * N;
            const int32_t sj4 = ((Sm[t] >> l) & 1u) ? 4 : -4;
            const int32_t uj = __shfl_sync(FULL, u[t], l);
            e += sj4 * (uj - sh[j] + sh0[j]);         // 2 dE0 = 4 s_j u0_j, u0 = u - (h - h0)
#pragma unroll
            for (int tt = 0; tt < MPL; ++tt) u[tt] -= sj4 * (int32_t)Jj[tt * 32 + lane];
            if (stats) ++n_flip;
          }
          Sm[t] ^= F;
        }
      }
      if (++p == P) { p = 0; ++n; }
      if (any || k == 0) {
        if (stats) ++n_eval;
        if (e < best_e) {
          best_e = e;
          best_bits = 0;
#pragma unroll
          for (int t = 0; t < MPL; ++t) best_bits |= ((Sm[t] >> lane) & 1u) << t;
        }
      }
    }
    if (mode == 0) {
      if (lane == 0) out_e[(size_t)b * R + r] = best_e;
#pragma unroll
      for (int t = 0; t < MPL; ++t) out_s[((size_t)b * R + r) * N + t * 32 + lane] = ((best_bits >> t) & 1u) ? 1 : -1;
    } else if (best_e < wbest_e) {
      wbest_e = best_e; wbest_r = r; wbest_bits = best_bits;
    }
  }
  if (stats && lane == 0) {
    atomicAdd(&stats[0], n_flip); atomicAdd(&stats[1], n_eval);
    atomicAdd(&stats[3], (unsigned long long)S * ((R - w + W - 1) / W));
  }
  if (stats) { unsigned long long v = n_rng; for (int o = 16; o; o >>= 1) v += __shfl_xor_sync(FULL, v, o); if (lane == 0) atomicAdd(&stats[2], v); }
  if (mode == 1) {
    if (lane == 0) { red_e[w] = wbest_e; red_r[w] = wbest_r; }
    __syncthreads();
    int be = INT_MAX, br = INT_MAX;
    for (int v = 0; v < W; ++v)
      if (red_e[v] < be || (red_e[v] == be && red_r[v] < br)) { be = red_e[v]; br = red_r[v]; }
    if (wbest_r == br) {
      if (lane == 0) out_e[b] = be;
#pragma unroll
      for (int t = 0; t < MPL; ++t) out_s[(size_t)b * N + t * 32 + lane] = ((wbest_bits >> t) & 1u) ? 1 : -1;
    }
  }
}

#define ENTRY(M)                                                                                                    \
  extern "C" __global__ void __launch_bounds__(256) ane_m##M(                                                        \
      const int16_t* J, const int32_t* h, const int32_t* h0, const int32_t* Tq, const int32_t* Cq, int q, int S,     \
      int P, int R, int N, uint32_t k0, uint32_t k1, int inst0, int mode, int32_t* out_e, int8_t* out_s,              \
      unsigned long long* stats) {                                                                                   \
    ane_body<M>(J, h, h0, Tq, Cq, q, S, P, R, N, k0, k1, inst0, mode, out_e, out_s, stats);                         \
  }
ENTRY(1) ENTRY(2) ENTRY(3) ENTRY(4) ENTRY(6) ENTRY(8)
