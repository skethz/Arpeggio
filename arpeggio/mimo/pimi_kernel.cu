// PIMI (Zhu et al., arXiv:2604.17109v2; the authors' 'tanh_lut' update and 16-bit fixed point, src/pbits_im.py and
// src/aux.py on Zenodo) for DI-MIMO detection as a CUDA kernel, bit-exact with pimi.pimi_fx. Structure as
// ane_kernel.cu / ahc_kernel.cu: one block per instance, one warp per trial (a warp loops over trials w, w + W, ...),
// the couplings in shared memory (int16, symmetric), lane L holding spins t*32 + L (t < MPL = N/32).
// Arithmetic, in integer units of 2^-12 with q(x) = saturate(trunc(x)) to [-2^15, 2^15 - 1]:
//   MVM = q(u) with u = J s (kept exactly, updated incrementally per changed spin: integers, so equal to recomputation);
//   I = q(trunc(beta * (MVM + h) / 2^12)); SI = q(2 I); L = lut(SI) in {-4096, -1365, 1365, 4096} at SI <= -2048, <= 0,
//   <= 2048, > 2048; n = q(trunc(eta_k * r / 2^12)), r = TAB[x >> 16] with x the Philox4x32-10 word k mod 4 of counter
//   (k / 4, spin, trial, instance); s <- sign(q(L + 2^12 s + n)) in {-1, 0, 1} (all spins at once).
// Start: spin +1 iff word 0 of counter (2^32 - 1, spin, trial, instance) >= 2^31. After the last step the energy
// 2E = -sum_i s_i (u_i + 2 h_i). mode 0: every trial's final spins and 2E; mode 1: the trial with the lowest 2E (first).
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

__device__ __forceinline__ int32_t q16(int32_t x) { return x < -32768 ? -32768 : (x > 32767 ? 32767 : x); }

__device__ __forceinline__ int warp_sum(int v) {
#pragma unroll
  for (int o = 16; o; o >>= 1) v += __shfl_xor_sync(FULL, v, o);
  return v;
}

template <int MPL>
__device__ __forceinline__ void pimi_body(const int16_t* __restrict__ Jg, const int32_t* __restrict__ hg,
                                          const int32_t* __restrict__ eta, const int16_t* __restrict__ tab, int beta,
                                          int S, int R, int N, uint32_t k0, uint32_t k1, int inst0, int mode,
                                          int8_t* __restrict__ out_s, int32_t* __restrict__ out_e) {
  extern __shared__ __align__(16) unsigned char smem[];
  int16_t* J = reinterpret_cast<int16_t*>(smem);
  int32_t* sh = reinterpret_cast<int32_t*>(smem + ((N * N * 2 + 15) & ~15));
  int32_t* red_e = sh + N;     // 32 warps
  int32_t* red_r = red_e + 32;  // 32 warps
  const int b = blockIdx.x;
  const int lane = threadIdx.x & 31, w = threadIdx.x >> 5, W = blockDim.x >> 5;
  {
    const int4* src = reinterpret_cast<const int4*>(Jg + (size_t)b * N * N);
    int4* dst = reinterpret_cast<int4*>(J);
    for (int x = threadIdx.x; x < N * N / 8; x += blockDim.x) dst[x] = src[x];
    for (int x = threadIdx.x; x < N; x += blockDim.x) sh[x] = hg[(size_t)b * N + x];
  }
  __syncthreads();
  const uint32_t inst = (uint32_t)(inst0 + b);
  int32_t hv[MPL];
#pragma unroll
  for (int t = 0; t < MPL; ++t) hv[t] = sh[t * 32 + lane];
  int32_t wbest_e = INT_MAX, wbest_r = INT_MAX;
  int8_t wbest_s[MPL];
#pragma unroll
  for (int t = 0; t < MPL; ++t) wbest_s[t] = 0;
  for (int r = w; r < R; r += W) {
    int32_t s[MPL], u[MPL];
    uint32_t Sm[MPL];
#pragma unroll
    for (int t = 0; t < MPL; ++t) {
      uint32_t c0 = 0xFFFFFFFFu, c1 = (uint32_t)(t * 32 + lane), c2 = (uint32_t)r, c3 = inst;
      philox10(c0, c1, c2, c3, k0, k1);
      s[t] = c0 >= 0x80000000u ? 1 : -1;
      Sm[t] = __ballot_sync(FULL, s[t] > 0);
    }
#pragma unroll
    for (int t = 0; t < MPL; ++t) {
      const int16_t* Ji = J + (t * 32 + lane) * N;
      int32_t acc = 0;
#pragma unroll
      for (int tt = 0; tt < MPL; ++tt) {
        const uint32_t m = Sm[tt];
        for (int l = 0; l < 32; ++l) { const int32_t v = Ji[tt * 32 + l]; acc += ((m >> l) & 1u) ? v : -v; }
      }
      u[t] = acc;
    }
    uint32_t r0[MPL], r1[MPL], r2[MPL], r3[MPL];
    for (int k = 0; k < S; ++k) {
      const int nm = k & 3;
      const int32_t ek = eta[k];
      int32_t dl[MPL];
#pragma unroll
      for (int t = 0; t < MPL; ++t) {
        if (nm == 0) {
          uint32_t c0 = (uint32_t)(k >> 2), c1 = (uint32_t)(t * 32 + lane), c2 = (uint32_t)r, c3 = inst;
          philox10(c0, c1, c2, c3, k0, k1);
          r0[t] = c0; r1[t] = c1; r2[t] = c2; r3[t] = c3;
        }
        const uint32_t x = nm == 0 ? r0[t] : nm == 1 ? r1[t] : nm == 2 ? r2[t] : r3[t];
        const int32_t rv = (int32_t)__ldg(tab + (x >> 16));
        const int32_t n = q16((ek * rv) / 4096);                       // C division truncates toward zero
        const int32_t mvm = q16(u[t]);
        const int32_t I = q16((int32_t)(((long long)beta * (long long)(mvm + hv[t])) / 4096));
        const int32_t si = q16(2 * I);
        const int32_t L = si <= -2048 ? -4096 : (si <= 0 ? -1365 : (si <= 2048 ? 1365 : 4096));
        const int32_t tot = q16(L + 4096 * s[t] + n);
        const int32_t ns = tot > 0 ? 1 : (tot < 0 ? -1 : 0);
        dl[t] = ns - s[t];
        s[t] = ns;
      }
#pragma unroll
      for (int t = 0; t < MPL; ++t) {
        uint32_t m = __ballot_sync(FULL, dl[t] != 0);
        while (m) {
          const int l = __ffs(m) - 1;
          m &= m - 1;
          const int32_t dj = __shfl_sync(FULL, dl[t], l);
          const int16_t* Jj = J + (t * 32 + l) * N;                        // row j = column j (J symmetric)
#pragma unroll
          for (int tt = 0; tt < MPL; ++tt) u[tt] += dj * (int32_t)Jj[tt * 32 + lane];
        }
      }
    }
    int32_t e = 0;
#pragma unroll
    for (int t = 0; t < MPL; ++t) e -= s[t] * (u[t] + 2 * hv[t]);
    e = warp_sum(e);
    if (mode == 0) {
      if (lane == 0) out_e[(size_t)b * R + r] = e;
#pragma unroll
      for (int t = 0; t < MPL; ++t) out_s[((size_t)b * R + r) * N + t * 32 + lane] = (int8_t)s[t];
    } else if (e < wbest_e) {
      wbest_e = e; wbest_r = r;
#pragma unroll
      for (int t = 0; t < MPL; ++t) wbest_s[t] = (int8_t)s[t];
    }
  }
  if (mode == 1) {
    if (lane == 0) { red_e[w] = wbest_e; red_r[w] = wbest_r; }
    __syncthreads();
    int be = INT_MAX, br = INT_MAX;
    for (int v = 0; v < W; ++v)
      if (red_e[v] < be || (red_e[v] == be && red_r[v] < br)) { be = red_e[v]; br = red_r[v]; }
    if (wbest_r == br) {
      if (lane == 0) out_e[b] = be;
#pragma unroll
      for (int t = 0; t < MPL; ++t) out_s[(size_t)b * N + t * 32 + lane] = wbest_s[t];
    }
  }
}

#define ENTRY(M, LB)                                                                                               \
  extern "C" __global__ void __launch_bounds__(LB) pimi_m##M(                                                       \
      const int16_t* J, const int32_t* h, const int32_t* eta, const int16_t* tab, int beta, int S, int R, int N,    \
      uint32_t k0, uint32_t k1, int inst0, int mode, int8_t* out_s, int32_t* out_e) {                               \
    pimi_body<M>(J, h, eta, tab, beta, S, R, N, k0, k1, inst0, mode, out_s, out_e);                                \
  }
ENTRY(1, 1024) ENTRY(2, 1024) ENTRY(3, 256) ENTRY(4, 256) ENTRY(6, 256) ENTRY(8, 256)
