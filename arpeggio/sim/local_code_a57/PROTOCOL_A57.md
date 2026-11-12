# Amendment 7 to PROTOCOL_A56: first-accept SA with the same early stop and reinvestment

Author's go, 6 Nov 2026 ("<instruction>"), to my proposal: test whether the early stop with reinvestment fixes Antiphase's weak point, namely that first-accept SA on the same comparators ties (P2) or wins (P1) at equal modeled cycles (A5.5, model F). Frozen before any HQ result; exploratory; nothing in the paper changes without the author.

## 1. Question
Both detectors get the same first-pass stop and the same multiplication of anneals. Does Antiphase then have lower BER than first-accept SA at no more mean modeled cycles?

## 2. Arms (set HQ, seed 102, the draws and lengths of Antiphase's HN arms and of amendment 4's HR arms)
| Point | Antiphase (existing HN pick) | First-accept SA arm (rule (2), apx55 `abl_far_*`) | Why this arm |
|---|---|---|---|
| P1, x16 20 dB, 17 batches of 2,000 | `a56_128_0.3_0.3_0.4_0_alt_384` | Q1 `abl_far_64_0.1_0.1_0_rand_384` | A5.5 F-R budget-1 pick (x_F 0.86), Ns times 12 as Antiphase (32 to 384) |
| | | Q2 `abl_far_128_0.1_0.1_0_rand_248` | A5.5 F-R budget-2/3 pick (x_F 1.51), Ns = floor(384 / 1.51 / 8) x 8 = 248, about Antiphase's budget |
| P2, x32 22 dB, 20 batches of 1,000 | `a56_128_0.3_0.3_0.4_0_alt_128` | Q1 `abl_far_32_0.1_0.1_0_rand_128` | A5.5 F-R budget-1 pick (x_F 0.65), Ns times 16 (8 to 128) |
| | | Q2 `abl_far_128_0.1_0.1_0_rand_80` | A5.5 F-R budget-2/3 pick (x_F 1.57), Ns = floor(128 / 1.57 / 8) x 8 = 80 |

Cells are A5.5's picks at Ns 32 and 8, not re-tuned at the larger Ns, as for Antiphase and amendment 4. The arms were fixed from A5.5's analysis only, before any HQ batch.

## 3. Stop and cost
- Stop: amendment 4's first-pass stop at the c of `select.json` (P1 c = 2, P2 c = 4), threshold Nr + c sqrt(Nr) on ||y - Hx||^2 / N0 at the start and after each MDI stage, N0 known.
- Cost per anneal at K:
  - first-accept SA: (tests + flips) / anneals, measured on the run. This is A5.5's model F, C_FA.
  - Antiphase: L_K + F_K (a56an.cyc_table), as in amendment 4.
  - Cycles are summed up to the stop. Modeled cycles only, no time and no energy.

## 4. Runs
`src/trace_a56.py` with `results/a56/plan_a57.json`, unchanged worker code. Root `results/a56`, set HQ.

Code checks before launch, on a scratch root:
- Replay through the trace path of A5.5's saved seed-102 batch 0 of `abl_far_64_0.1_0.1_0_rand_32` (P1) and `abl_far_32_0.1_0.1_0_rand_8` (P2). Bit errors and erroneous x_hat must be identical.
- One batch of each HQ arm on dev seed 9600, for rate, memory and test counts.

## 5. Analysis (`analyze_a57.py`, written before any HQ result)
- Paired cluster bootstrap (4,000) of the bit-error ratio SA/Antiphase, both with the stop, on the common prefix. Exact McNemar on erroneous uses.
- x = mean SA cycles / mean Antiphase cycles.
- Also reported: p99, maximum, stop share at the start, and the no-stop ratio.

## 6. Wording rule
An arm is within budget if x <= 1.10. The per-point verdict uses only arms within budget:
- **Antiphase leads at Pk:** every arm within budget has a lower bound above 1.
- **SA leads:** any arm within budget has an upper bound below 1.
- **No detected difference:** otherwise.
- Arms over budget are reported as "at more cycles".

What I propose afterwards:
- If Antiphase leads at both P1 and P2: adopting stop and reinvestment would replace "first-accept SA ties or wins" with "with the same stop, Antiphase leads first-accept SA". It stays the author's decision, with PROTOCOL_A56 section 10's costs: rerun Tables II-IV, Figs. 3-4, the ASIC replays and the B200 timing; N0 known; worst case about 10x.
- Otherwise: I advise against adopting it for DAC 2027.

## 7. Predictions (SA/Antiphase with stop)
| Claim | P |
|---|---|
| P1 Q1 SA leads (hi < 1) | .65 |
| P1 Q1 Antiphase leads (lo > 1) | .05 |
| P1 Q2 SA leads | .6 |
| P2 Q1 Antiphase leads | .35 |
| P2 Q1 SA leads | .2 |
| P2 Q2 SA leads | .4 |
| Antiphase leads at both points | .05 |
| Both Q2 arms within budget (x <= 1.10) | .7 |

## 8. Compute
- hostB GPU0-3, checked by UUID, idle required; one worker per GPU, nice 10, 2 threads, 20% GPU memory.
- <USER> stays within its 24-core cap. Other users' processes are never touched.
- Untimed: no 5090 time is reported.
- A job failing 3 times is left, logged and diagnosed.
