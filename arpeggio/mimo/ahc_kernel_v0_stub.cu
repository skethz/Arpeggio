// RED stub of ahc_kernel.cu: same entry points and signatures, no implementation (outputs zeros).
#include <stdint.h>
#define STUB(M) extern "C" __global__ void ahc_m##M(const float* Jt, const float* h0, const float* x0, const float* e0, \
  const float* gts, int N, int R, int steps, float cpm1, float ca, float cnb, float chalf, float cdt, float c6, \
  int8_t* out_s, float* out_e) { int b = blockIdx.x; \
  for (int x = threadIdx.x; x < R * N; x += blockDim.x) out_s[(size_t)b * R * N + x] = 0; \
  for (int x = threadIdx.x; x < R; x += blockDim.x) out_e[(size_t)b * R + x] = 0.f; }
STUB(1) STUB(2) STUB(3) STUB(4) STUB(5) STUB(6)
