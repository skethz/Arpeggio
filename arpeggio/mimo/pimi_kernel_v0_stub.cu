// RED stub of pimi_kernel.cu: the same entry points and signatures, no implementation (outputs zeros).
#include <stdint.h>
extern "C" __global__ void philox_kat(const uint32_t* in, uint32_t* out, int n) {
  const int t = blockIdx.x * blockDim.x + threadIdx.x;
  if (t < n) { out[4 * t] = 0; out[4 * t + 1] = 0; out[4 * t + 2] = 0; out[4 * t + 3] = 0; }
}
#define STUB(M)                                                                                                   \
  extern "C" __global__ void pimi_m##M(const int16_t* J, const int32_t* h, const int32_t* eta, const int16_t* tab, \
                                       int beta, int S, int R, int N, uint32_t k0, uint32_t k1, int inst0, int mode,  \
                                       int8_t* out_s, int32_t* out_e) {                                            \
    const int b = blockIdx.x;                                                                                     \
    const int ns = mode ? N : R * N, ne = mode ? 1 : R;                                                           \
    for (int x = threadIdx.x; x < ns; x += blockDim.x) out_s[(size_t)b * ns + x] = 0;                             \
    for (int x = threadIdx.x; x < ne; x += blockDim.x) out_e[(size_t)b * ne + x] = 0;                             \
  }
STUB(1) STUB(2) STUB(3) STUB(4) STUB(6) STUB(8)
