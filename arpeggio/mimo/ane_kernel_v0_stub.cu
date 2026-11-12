// RED stub of ane_kernel.cu: same entry points and signatures, no implementation (outputs zeros). test_kernel.py
// must fail against it before the real kernel is written.
#include <stdint.h>
extern "C" __global__ void philox_kat(const uint32_t* in, uint32_t* out, int n) {
  int t = blockIdx.x * blockDim.x + threadIdx.x; if (t >= n) return;
  for (int j = 0; j < 4; ++j) out[4 * t + j] = 0;
}
#define STUB(M) extern "C" __global__ void ane_m##M(const int16_t* J, const int32_t* h, const int32_t* h0, \
  const int32_t* Tq, const int32_t* Cq, int q, int S, int P, int R, int N, uint32_t k0, uint32_t k1, int inst0, \
  int mode, int32_t* out_e, int8_t* out_s, unsigned long long* stats) { \
  int b = blockIdx.x; int n = mode ? N : R * N; int ne = mode ? 1 : R; \
  for (int x = threadIdx.x; x < n; x += blockDim.x) out_s[(size_t)b * n + x] = 0; \
  for (int x = threadIdx.x; x < ne; x += blockDim.x) out_e[(size_t)b * ne + x] = 0; }
STUB(1) STUB(2) STUB(3) STUB(4) STUB(6) STUB(8)
