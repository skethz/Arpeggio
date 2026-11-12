// A5.13 (PROTOCOL_A513.md): fixed-point first-accept SA on the GPU, one thread per anneal.
// Statement for statement the integer arithmetic of fa_ref59.anneal, mode 'fa' (rtl_a59/src/fa_ref59.py, sha256 b595b56c...), which
// the first-accept RTL matched event for event in A5.5 and A5.9: Philox4x32-10 numbers, one per (sweep, copy, lane); lanes scanned in
// index order; a flip updates every field before the next lane is tested; best state after each pass.
// G is passed transposed: Gt[j * D + i] = G[i][j], so a flip of lane j reads one contiguous row.
#include <stdint.h>
#define DMAX 128
#define PMAX 6

__device__ __forceinline__ uint32_t philox_w(uint32_t c0, uint32_t c1, uint32_t c2, uint32_t c3, uint32_t k0, uint32_t k1, uint32_t w)
{
#pragma unroll
    for (int i = 0; i < 10; i++) {
        if (i) { k0 += 0x9E3779B9u; k1 += 0xBB67AE85u; }
        uint64_t p0 = (uint64_t)0xD2511F53u * c0;
        uint64_t p1 = (uint64_t)0xCD9E8D57u * c2;
        uint32_t n0 = (uint32_t)(p1 >> 32) ^ c1 ^ k0;
        uint32_t n2 = (uint32_t)(p0 >> 32) ^ c3 ^ k1;
        c1 = (uint32_t)p1; c3 = (uint32_t)p0; c0 = n0; c2 = n2;
    }
    return w == 0 ? c0 : (w == 1 ? c1 : (w == 2 ? c2 : c3));
}

__device__ int bal_pat(int P, uint32_t i)                                 // fa_ref59.bal_pat: the i-th P-bit word with P/2 ones
{
    uint32_t n = 0;
    for (int v = 0; v < (1 << P); v++)
        if (__popc(v) == P / 2) {
            if (n == i) return v;
            n++;
        }
    return 0;
}

extern "C" __global__ void fa_fx(const int32_t* __restrict__ Gt, const int32_t* __restrict__ h, const int32_t* __restrict__ T, int L,
                                 int q, int P, int R, int D, int B, const uint32_t* __restrict__ inst, uint32_t k0, uint32_t k1,
                                 int start, int8_t* __restrict__ out_s, long long* __restrict__ out_de, long long* __restrict__ out_st)
{
    int t = blockIdx.x * blockDim.x + threadIdx.x;
    if (t >= B * R) return;
    int b = t / R;
    uint32_t r = (uint32_t)(t % R), in = inst[b];
    const int32_t* g = Gt + (size_t)b * D * D;
    const int32_t* hb = h + (size_t)b * D;
    int8_t s[PMAX * DMAX], bs[PMAX * DMAX];
    int32_t w[DMAX];
    int C = P == 2 ? 2 : (P == 4 ? 6 : 20);
    for (int j = 0; j < D; j++) {
        if (start == 0) {
            for (int p = 0; p < P; p++)
                s[p * D + j] = philox_w(0xFFFFFFFFu, (uint32_t)(p * D + j), r, in, k0, k1, 0) >= 0x80000000u ? 1 : -1;
        } else {
            uint32_t w0 = philox_w(0xFFFFFFFFu, (uint32_t)j, r, in, k0, k1, 0);
            int pat = bal_pat(P, (uint32_t)(((uint64_t)w0 * (uint64_t)C) >> 32));
            for (int p = 0; p < P; p++) s[p * D + j] = ((pat >> p) & 1) ? 1 : -1;
        }
    }
    for (int i = 0; i < D; i++) w[i] = hb[i];                             // w_i = h_i - 2 sum_j G_ij m_j, m_j summed over copies
    for (int j = 0; j < D; j++) {
        int m = 0;
        for (int p = 0; p < P; p++) m += s[p * D + j];
        if (m) {
            const int32_t* gj = g + (size_t)j * D;
            for (int i = 0; i < D; i++) w[i] -= 2 * gj[i] * m;
        }
    }
    long long de = 0, best = 1LL << 62, flips = 0, tests = 0;
    for (int k = 0; k < L; k++) {
        int p = k % P;
        uint32_t n = (uint32_t)(k / P);
        long long A = 4LL * T[k], Bk = (long long)q + 2LL * T[k];
        int8_t* sp = s + p * D;
        long long tt = 1;
        for (int j = 0; j < D; j++) {
            uint32_t u = philox_w(n >> 2, (uint32_t)(p * D + j), r, in, k0, k1, n & 3);
            long long dj = g[(size_t)j * D + j];
            long long lhs = (long long)u * A;
            long long rhs = ((long long)sp[j] * (long long)w[j] + 2LL * dj + Bk) * 4294967296LL;   // (...) << 32, as in Python
            if (lhs > rhs) {                                                // lanes after a flip see the updated field
                int so = sp[j];
                de += 4LL * so * (long long)w[j] + 8LL * dj;
                const int32_t* gj = g + (size_t)j * D;
                for (int i = 0; i < D; i++) w[i] += 4 * so * gj[i];
                sp[j] = (int8_t)(-so);
                flips++;
                if (j < D - 1) tt++;
            }
        }
        tests += tt;
        if (de < best) {
            best = de;
            for (int x = 0; x < P * D; x++) bs[x] = s[x];
        }
    }
    size_t o = (size_t)t * P * D;
    for (int x = 0; x < P * D; x++) out_s[o + x] = bs[x];
    out_de[t] = best;
    out_st[2 * t] = flips;
    out_st[2 * t + 1] = tests;
}
