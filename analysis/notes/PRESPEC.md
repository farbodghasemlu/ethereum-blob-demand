# Pre-specification: headline elasticity

*Voice edited to first person on 30 September 2026; content unchanged. The version fixed before estimation is
the one in the commit that added this file.*

We fixed this document before running any rollup-level quantity regression. Everything not defined here is a
robustness check or a secondary analysis, and we label it as one. We revise it only for outright error and
record each revision in DECISIONS.md with its reason.

**What we had seen before fixing it (disclosed):** Figure 1 (aggregate blobs per block, block-mean price,
floor share, daily); mean block price and floor/at-max shares in windows around each fork (the first stage);
counts of rollups and growthepie coverage in the Pectra window. We had run no regression of rollup quantities on
the Pectra indicator and no rollup-level quantity comparison across the fork.

## 1. Identifying variation

The Pectra hard fork (activation 2025-05-07 10:05:11 UTC, t₀) doubled the blob target (3 → 6) and raised the
maximum (6 → 9) on a date fixed by client releases weeks in advance. Immediately before the fork the EIP-4844
market was congested: usage at target, floor in <1% of blocks, and a mean block price of 0.82 mETH/blob over
the prior 28 days. Immediately after, the price fell to the floor (≈0; 68% of blocks at the floor). This is a
supply shift that moves the price along rollups' demand curves. It is the only fork with a material first
stage (DECISIONS D-12), so it is the event we use.

Exclusion argument: blob space cannot be stored, so demand one day either side of the fork is not shifted by
the fork except through price. We drop the transition day (D-04).

Known threats:
- (a) ETH/USD rose 22% on t₀+1 and 48% by t₀+6, which likely raised L2 activity. Our headline outcome
  normalizes by L2 transactions to remove this (D-14).
- (b) EIP-7623 raised the calldata cost in the same fork, pushing any calldata-posting rollups toward blobs.
  This biases the response upward in magnitude. It is not observable in the deposit; we state it as a
  limitation.
- (c) One break date: we base inference on placebo dates (D-17).

## 2. Estimand and equations

Outcome B_it: blobs purchased by rollup i on UTC day t (zero-filled within the active span, D-05). L2
activity T_it: growthepie `txcount`. Price P_t: mean header blob base fee over all blocks of day t, in
milli-ETH per blob (D-11, D-16).

Reduced form (PPML, unit = rollup × day):

    E[B_it | ·] = T_it · exp( α_i + γ_i·(t − t₀) + δ_dow(t) + β·Post_t )

- ln T_it enters as an offset (coefficient fixed at 1), so the model is for blobs per L2 transaction.
- α_i: rollup fixed effects. γ_i: rollup-specific linear trends, one slope per rollup across both sides.
- δ_dow: day-of-week fixed effects. Post_t = 1{t > t₀}.

First stage (OLS, unit = day, same window):

    P_t = a + π·Post_t + c·(t − t₀) + δ_dow(t) + u_t

**Headline:** η = β / π, the semi-elasticity of DA intensity with respect to the blob price, in units of
(log points per mETH/blob). Reported with ε = η · P̄_pre, the point elasticity at the pre-window mean price
under exponential demand B = A·exp(η·P).

We interpret it as the average proportional change in blobs purchased per L2 transaction per 1 mETH/blob change in
price, over the price range from the pre-Pectra congestion level down to the floor. This is the direct
margin (fill rate, batching frequency, DA-layer choice) holding L2 activity fixed. It excludes the pass-through
margin, where L2 activity itself responds to DA costs.

## 3. Sample

- Window: t₀ − 28 … t₀ − 1 and t₀ + 1 … t₀ + 28 (56 days).
- Rollups: labelled (not 'unknown'), first post ≤ t₀ − 28 and last post ≥ t₀ + 28, with growthepie `txcount`
  on every window day.
- This rule selects arbitrum, base, ink, linea, lisk, mantle, mode, optimism, scroll, soneium, starknet, taiko,
  unichain, world, zksync (15 rollups, 82% of the window's blobs). Expected N = 15 × 56 = 840 rollup-days,
  less any missing `txcount`. We print the exact N.

## 4. Inference

- **Primary:** placebo-date permutation. We apply the identical estimator (same sample rule, window and FE) at every
  placebo date τ in the EIP-4844 regime whose ±28-day window lies within [2024-03-14, 2025-12-02] and
  excludes t₀. Two-sided p = share of placebo |β| ≥ |β̂|. We do the same for η, using each placebo's own
  first stage.
- **We also report:** β with CRV1 SEs clustered by rollup (15 clusters: few, so flagged) and two-way by rollup
  and day. π with Newey–West SEs (7 lags). η by the delta method, treating β and π as independent.

## 5. Secondary analyses (pre-listed, not headline)

- **S1 Total demand:** same equation without the offset, all labelled rollups active across the window.
  Confounded by the ETH rally, so we report it as an upper bound on the magnitude of the total response.
- **S2 Fusaka:** the same design at 2025-12-03 with a ±5-day window (BPO1 follows 6 days later). Low power.
- **S3 Mechanism:** mempool-to-inclusion delay by block state (floor, interior, at max) in the EIP-4844
  regime. This tests whether allocation at the floor happens by queueing (D-08).
- **S4 Exploratory:** intraday execution-base-fee variation in BPO2 (D-13).
- **S5 Log price:** a log-price version of the headline, to show its dependence on the floor level (D-10).

## 6. Specification curve (robustness; the headline stays the headline)

We re-estimate the headline equation over all combinations of:

| dimension | values |
|---|---|
| window (days each side) | 14, 21, 28, 42, 56 |
| trends | none, rollup-linear, rollup-quadratic |
| L2 activity | offset, free control ln T_it, none |
| estimator | PPML, OLS ln(B) on positive days, OLS ln(1+B) |
| price in first stage | all-block mean, all-block median, blob-weighted paid |
| day-of-week FE | yes, no |
| zero-fill | yes, no |

We re-apply the sample rule for each window, plot the distribution of η, and report the share of
specifications with η < 0 and with η significant at 5%. If the headline sits in a corner of this distribution,
the paper says so.

---

## Revision, 30 September 2026 (recorded after estimation; the text above is unchanged)

Our primary estimate is now the unnormalized specification (pre-listed above as S1, estimated on the same 15
rollups), and we report blobs per L2 transaction as a descriptive intensity measure. Reason: the headline's
premise that L2 activity is unaffected by the blob price turned out to be wrong (DECISIONS D-24). L2 activity rose
at Pectra relative to chains that do not buy blobs (script 09), so the offset normalizes by a variable that responds
to treatment. That is an error in the specification, which the rules above allow us to correct; the correction is
recorded in DECISIONS D-34. Equation, sample, window, fixed effects, trends, first stage and inference are
unchanged; only the offset is dropped.
