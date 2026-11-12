// Princeton's AHC-CIM (Singh et al. 2024, Eqs. 9-10; RK4, 512 steps of 0.005, p 0.98, a 2, beta 1, eps ramped to
// 1000; auxiliary spin; every step's state a candidate) as a CUDA kernel with the same structure as ane_kernel.cu:
// one block per instance, one warp per anneal (warps loop over anneals), the couplings Jt ((N+1) x (N+1), fp32) in
// shared memory, lane L holding state rows 32 t + L. Bit-exact with ahcfx.ahc_od: fp32, every product and sum rounded
// separately (__fmul_rn / __fadd_rn / __fsub_rn; built with -fmad=false), mat-vec sums in j order, the energy in the
// reference's slot-then-xor-tree order. Inputs: Jt, h0, the start states x0, e0 (B, R, N+1), the per-stage fp32
// scalars gamma*t (steps, 4). Outputs: per anneal the best spins (int8 +-1) and their energy.
#include <stdint.h>
#include <math_constants.h>

#define FULL 0xffffffffu

__device__ __forceinline__ float fmul(float a, float b) { return __fmul_rn(a, b); }
__device__ __forceinline__ float fadd(float a, float b) { return __fadd_rn(a, b); }
__device__ __forceinline__ float fsub(float a, float b) { return __fsub_rn(a, b); }

template <int M>   // M = N / 32 energy slots; state slots M + 1 (the last holds the auxiliary row N on lane 0)
__device__ __forceinline__ void ahc_body(const float* __restrict__ Jtg, const float* __restrict__ h0g,
                                         const float* __restrict__ x0g, const float* __restrict__ e0g,
                                         const float* __restrict__ gts, int N, int R, int steps,
                                         float cpm1, float ca, float cnb, float chalf, float cdt, float c6,
                                         int8_t* __restrict__ out_s, float* __restrict__ out_e) {
  constexpr int MS = M + 1;
  extern __shared__ __align__(16) float sm[];
  const int Np = N + 1;
  float* Jt = sm;                       // Np * Np
  float* h0 = Jt + Np * Np;             // N
  const int lane = threadIdx.x & 31, w = threadIdx.x >> 5, W = blockDim.x >> 5;
  float* xs = h0 + N + w * 2 * Np;      // per warp: state broadcast buffer (Np)
  float* ss = xs + Np;                  // per warp: spins (N)
  const int b = blockIdx.x;
  for (int i = threadIdx.x; i < Np * Np; i += blockDim.x) Jt[i] = Jtg[(size_t)b * Np * Np + i];
  for (int i = threadIdx.x; i < N; i += blockDim.x) h0[i] = h0g[(size_t)b * N + i];
  __syncthreads();
  for (int r = w; r < R; r += W) {
    float x[MS], e[MS];
    const size_t base = ((size_t)b * R + r) * Np;
#pragma unroll
    for (int t = 0; t < MS; ++t) {
      const int i = t * 32 + lane;
      x[t] = i < Np ? x0g[base + i] : 0.f;
      e[t] = i < Np ? e0g[base + i] : 0.f;
    }
    float best_e = CUDART_INF_F;
    uint32_t best_bits = 0;
    for (int k = 0; k < steps; ++k) {
      float sx[MS], se[MS], kx[MS], ke[MS], ys[MS], es[MS];
#pragma unroll
      for (int t = 0; t < MS; ++t) { ys[t] = x[t]; es[t] = e[t]; }
#pragma unroll
      for (int st = 0; st < 4; ++st) {
        const float gt = gts[4 * k + st];
        __syncwarp();
#pragma unroll
        for (int t = 0; t < MS; ++t) { const int i = t * 32 + lane; if (i < Np) xs[i] = ys[t]; }
        __syncwarp();
#pragma unroll
        for (int t = 0; t < MS; ++t) {
          const int i = t * 32 + lane;
          if (i < Np) {
            const float* Ji = Jt + i * Np;
            float acc = fmul(Ji[0], xs[0]);
            for (int j = 1; j < Np; ++j) acc = fadd(acc, fmul(Ji[j], xs[j]));
            const float xv = ys[t], ev = es[t];
            const float fx = fadd(fsub(fmul(cpm1, xv), fmul(fmul(xv, xv), xv)), fmul(fmul(gt, ev), acc));
            const float fe = fmul(fmul(cnb, fsub(fmul(xv, xv), ca)), ev);
            kx[t] = fx; ke[t] = fe;
            if (st == 0) { sx[t] = fx; se[t] = fe; }
            else if (st == 3) { sx[t] = fadd(sx[t], fx); se[t] = fadd(se[t], fe); }
            else { sx[t] = fadd(sx[t], fmul(2.f, fx)); se[t] = fadd(se[t], fmul(2.f, fe)); }
          }
        }
        if (st < 3) {
          const float c = st < 2 ? chalf : cdt;
#pragma unroll
          for (int t = 0; t < MS; ++t) { ys[t] = fadd(x[t], fmul(c, kx[t])); es[t] = fadd(e[t], fmul(c, ke[t])); }
        }
      }
#pragma unroll
      for (int t = 0; t < MS; ++t) { x[t] = fadd(x[t], fmul(c6, sx[t])); e[t] = fadd(e[t], fmul(c6, se[t])); }
      // spins and the candidate's energy
      const float xa = __shfl_sync(FULL, x[M], 0);                       // auxiliary row N = 32 M on lane 0
      __syncwarp();
#pragma unroll
      for (int t = 0; t < M; ++t) ss[t * 32 + lane] = fmul(x[t], xa) >= 0.f ? 1.f : -1.f;
      __syncwarp();
      float v = 0.f;
#pragma unroll
      for (int t = 0; t < M; ++t) {
        const int i = t * 32 + lane;
        const float* Ji = Jt + i * Np;
        float acc = fmul(Ji[0], ss[0]);
        for (int j = 1; j < N; ++j) acc = fadd(acc, fmul(Ji[j], ss[j]));
        v = fadd(v, fmul(ss[i], fadd(h0[i], acc)));
      }
#pragma unroll
      for (int o = 16; o; o >>= 1) v = fadd(v, __shfl_xor_sync(FULL, v, o));
      const float en = -v;
      if (en < best_e) {
        best_e = en;
        best_bits = 0;
#pragma unroll
        for (int t = 0; t < M; ++t) best_bits |= (ss[t * 32 + lane] > 0.f ? 1u : 0u) << t;
      }
    }
    if (lane == 0) out_e[(size_t)b * R + r] = best_e;
#pragma unroll
    for (int t = 0; t < M; ++t) out_s[((size_t)b * R + r) * N + t * 32 + lane] = ((best_bits >> t) & 1u) ? 1 : -1;
  }
}

#define ENTRY(M)                                                                                                  \
  extern "C" __global__ void __launch_bounds__(256) ahc_m##M(                                                      \
      const float* Jt, const float* h0, const float* x0, const float* e0, const float* gts, int N, int R, int steps, \
      float cpm1, float ca, float cnb, float chalf, float cdt, float c6, int8_t* out_s, float* out_e) {             \
    ahc_body<M>(Jt, h0, x0, e0, gts, N, R, steps, cpm1, ca, cnb, chalf, cdt, c6, out_s, out_e);                    \
  }
ENTRY(1) ENTRY(2) ENTRY(3) ENTRY(4) ENTRY(5) ENTRY(6)
