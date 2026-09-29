# Demand Under a Mechanical Price: Identification, Elasticity, and Welfare in Ethereum's Data-Availability (Blob) Market

*Working draft. Every number is filled in from `output/numbers/*.json` by `10_render_paper.py`; do not edit numbers by hand.*

## Abstract

EIP-4844 prices Ethereum's data-availability capacity ("blobs") by a mechanical controller rather than a
market-clearing auction. We estimate rollups' demand response using the Pectra hard fork, which doubled blob
capacity on a pre-announced date while the market was congested. The blob price fell from
{h[head_p_pre]:.2f} mETH per blob (about ${h[head_usd_pre]:.2f}) to the 1-wei floor. Blobs purchased per L2
transaction did not change: the pre-specified semi-elasticity is {h[head_eta]:.3f} log points per mETH/blob
(95% CI {h[head_ci_eta_lo]:.3f} to {h[head_ci_eta_hi]:.3f}; placebo-date permutation p = {h[perm_p_beta]:.2f}).
The implied point elasticity at the pre-shock price lies between {h[head_ci_eps_lo]:.3f} and
{h[head_ci_eps_hi]:.3f}. Across {sc[n_specs_intensity]:,} alternative specifications the median is
{sc[int_eta_median]:.3f}, and no specification in the headline family is significant. The volatility of congested
prices implies an elasticity of the same order. Total blob purchases did rise at Pectra. A post-hoc comparison
with chains that do not buy blobs suggests the rise came through L2 fees and L2 activity: blob demand as derived
demand. That evidence is suggestive, not conclusive (placebo p = {pt[p_act]:.2f}). Mempool data show that at the 1-wei floor blob transactions are
not rationed by queueing: waits are shortest there, and almost no transaction is priced out. With demand this
inelastic, the controller's first-order effect is distributional. Of the {w[fees_dencun_eth]:,.0f} ETH
(${w[fees_dencun_usd]:,.0f}) burned under Dencun, {w[fees_cong_share_dencun]:.0%} was paid in two congested
quarters. The deadweight loss of the post-Fusaka reserve price is at most {w[dwl_max_eth]:.1f} ETH even under
the most elastic demand we cannot rule out.

## 1. Introduction

Ethereum sells data-availability capacity to rollups through a posted price that no one sets. EIP-4844 fixes a
per-block target and ceiling for "blobs" and lets a controller move the price exponentially in the cumulative
deviation of usage from target. The design question this raises is old: how much does it matter that a price is
set mechanically rather than by a market-clearing auction? The answer depends on one empirical object, the price
elasticity of demand. If demand is elastic, a mis-set price misallocates capacity. If demand is inelastic, the
price mainly moves money.

Estimating that elasticity is harder than the volume of on-chain data suggests:
- The blob price is common to every buyer in a block, so cross-sectional comparisons carry no price variation.
- Within a regime the price is an outcome of demand by construction.
- For long stretches the price sits at a 1-wei floor where a log-price elasticity is not economically meaningful.

We use a scheduled supply shock, the Pectra hard fork, which doubled capacity while the market was congested and
dropped the price from about ${h[head_usd_pre]:.2f} per blob to effectively zero. We pre-registered the
specification before estimating it, and we report the whole distribution of estimates across the judgement
calls rather than a preferred point.

[To add: literature — EIP-1559 empirics, transaction-fee mechanism design, posted prices vs auctions, rollup
economics.]

Four findings.

1. **Demand for blob capacity is close to perfectly inelastic at the direct margin.** When Pectra cut the blob
   price from about ${h[head_usd_pre]:.2f} per blob to effectively zero, rollups did not buy more blob capacity per
   unit of L2 activity.
1b. **Any responsiveness runs through the rollups' users (post hoc, suggestive).** On OP-Stack chains the blob
   fee passes into L2 fees almost mechanically. Blob-using L2s saw fees fall and activity rise relative to chains
   that do not buy blobs.
2. **The floor regime is excess supply, not queueing.** Transactions seen when the price is at the floor miss
   fewer blocks than in any other state, and are almost never priced out.
3. **The pricing rule's welfare consequences are transfers, not allocation.** Blob fees were a burn paid mostly
   during two congested quarters, and the post-Fusaka reserve price costs almost nothing in allocative terms.

## 2. Institutional setting

- **EIP-4844 (Dencun).** Blob base fee = exp(excess / update fraction), with the excess updated each block by
  (usage − target). The fee is floored at 1 wei per blob gas; 1 blob = 131,072 blob gas = 128 KiB of purchased
  capacity. Target/max: 3/6 blobs.
- **Pectra (EIP-7691).** Target/max 6/9 from 2025-05-07; the same fork includes EIP-7623 (calldata repricing).
- **Fusaka (EIP-7918)** adds a reserve price tied to the execution base fee, acting on the excess-gas
  transition. The blob-parameter-only forks (BPO1 10/15, BPO2 14/21) follow.
- The header's excess already reflects EIP-7918, so the header-implied blob fee is valid in every regime: it
  matches the fee actually paid within max(0.1%, 1 wei) for {a[price_agree_share]:.1%} of
  {a[n_blob_txs_dated]:,} blob transactions.

## 3. Data

- Execution-layer block headers from Dencun activation onward.
- Every blob-carrying transaction, with rollup attribution from Blobscan.
- Daily L2 fundamentals from **growthepie** (CC BY 4.0).
- Mempool first-sighting times from **Xatu / ethPandaOps** (CC BY 4.0).
- ETH/USD daily closes.

Dataset: Harvard Dataverse doi:10.7910/DVN/4AOXKT (version 2).

Unattributed demand (rollup = unknown) is {a[unk_blobs_ALL]:.1%} of blobs, {a[unk_tx_ALL]:.1%} of transactions and
{a[unk_fees_ALL]:.1%} of fees. By regime it ranges from {a[unk_blobs_pectra]:.1%} (Pectra) to {a[unk_blobs_bpo1]:.1%}
(BPO1) of blobs.

Celestia series come from growthepie rather than Celenium, whose API was unreachable from our collection host. Rollup-level Celestia usage is therefore unavailable.

"Blob bytes" on Ethereum measure purchased capacity, not payload; Celestia's figures are bytes posted.

## 4. Descriptive facts (Table 1, Figure 1)

- The blob base fee sat at the floor in {d[dencun_share_blocks_at_floor]:.1%} of Dencun blocks and
  {d[pectra_share_blocks_at_floor]:.1%} of Pectra blocks, and in none after Fusaka.
- Dencun is not one regime. Its floor incidence concentrates in 2024-Q1 to 2024-Q3 (2024-Q3 fees:
  {w[fees_2024q3_eth]:.1g} ETH). In 2024-Q4 and 2025-Q1 usage sat at target and the price was far above the floor. Samples are split by calendar quarter only: floor incidence is an outcome.
- Under the reserve regime utilization fell to {d[bpo1_utilization_vs_target]:.0%} (BPO1) and
  {d[bpo2_utilization_vs_target]:.0%} (BPO2) of target. The reserve, not scarcity, set the price.

## 5. Identification

**Why a fork, and why only Pectra.** The blob price is common to all rollups in a block, so day fixed effects
absorb all price variation, and within-regime price variation is endogenous (the controller responds to demand).
We therefore use a scheduled supply shock.

Pectra doubled capacity while the market was congested. First stage: π = {h[head_pi]:.2f} mETH/blob
(Newey–West SE {h[head_se_pi]:.2f}).

The later capacity increases (BPO1, BPO2) came when usage was already below target. They left the price at the
reserve, so they have no first stage and identify nothing. Post-Fusaka price variation comes from the execution
base fee, which fails exclusion twice:
- It moves with L1 congestion, which co-moves with L2 activity.
- It prices the carrier transaction's own execution gas, so it raises posting costs through a channel other than
  the blob price.

An exploratory intraday regression shows the contamination directly. Within a day, posting rises by
{ix[beta_blobs]:.3f} log points (SE {ix[se_blobs]:.3f}) per log point of execution base fee, the wrong sign for a
cost response.

**Outcome.** ETH/USD rose sharply the day after Pectra, which plausibly raised L2 activity. The pre-specified
outcome is therefore blobs purchased per L2 transaction (PPML with L2 transactions as an offset). This isolates
the direct margins: fill rate, batching and DA-layer choice. The total-demand estimate is reported alongside. The pre-specification assumed the omitted margin, pass-through
of DA costs into L2 activity, was negligible. Section 6b shows that premise was wrong.

**Specification (pre-registered in `notes/PRESPEC.md` before estimation).** Rollup × day. Rollup fixed effects,
rollup-specific linear trends, day-of-week fixed effects. ±28 days around the fork, fork day excluded. Price in
mETH per blob, with the semi-elasticity η = β/π.

A log-price elasticity is not identified in any meaningful sense here. Identified off a move to the floor, it
depends on the arbitrary floor level: the same β gives {h[s5_elast_floor_1]:.4f} with a 1-wei floor and
{h[s5_elast_floor_1000000]:.4f} with a 10⁶-wei floor.

## 6. Results

**Headline (Table 2).**
- β = {h[head_beta]:.3f} (SE {h[head_se_beta_rollup]:.3f} clustered by rollup; {h[head_se_beta_twoway]:.3f} two-way).
- N = {h[head_n_obs]:,} rollup-days ({h[head_n_rollups]} rollups).
- η = {h[head_eta]:.3f} (SE {h[head_se_eta]:.3f}).
- Placebo-date permutation over {h[n_placebo]} placebo dates: p = {h[perm_p_beta]:.2f} (Figure 2).

**Fragility (Figure 3).** Across {sc[n_specs_intensity]} DA-intensity specifications, the median η is
{sc[int_eta_median]:.3f} and the 5th–95th percentile range is {sc[int_eta_p05]:.3f} to {sc[int_eta_p95]:.3f}.
{sc[int_share_beta_sig5]:.0%} are significant at 5% under cluster-robust SEs that the placebo test shows are too
small. None of the {sc[off_n_specs]:.0f} specifications with activity as an offset is significant. The headline sits
at the {sc[head_pctile]:.0%} percentile, on the inelastic side. The median specification implies an elasticity
of {sc[int_eps_median]:.3f} at the pre-shock price. Either way, demand at the direct margin is very inelastic.

**Heterogeneity (Figure 4).** {sc[het_n_pos]} of {sc[het_n]} rollups with a defined estimate have β > 0 (the
equal-weighted mean is {sc[het_mean_beta]:.3f}). The volume-weighted pooled estimate is pulled negative by Base
(β = {sc[het_base_beta]:.3f}).

**Total demand.** Without normalizing by activity, blobs rose by β = {h[s1_beta]:.3f} (SE {h[s1_se_beta_rollup]:.3f})
across {h[s1_n_rollups]} rollups. This is larger than at any of the {h[n_placebo]} placebo dates (p =
{h[s1_perm_p]:.3f}). With DA intensity unchanged, the rise is a rise in L2 activity. Whether that activity rise
is a price response or the ETH rally is the question of Section 6b.

## 6b. Derived demand: pass-through to L2 fees (post hoc)

*This section was not pre-specified. It was added after the data showed that the pre-specification's premise, that
pass-through was negligible, was wrong (DECISIONS D-24).*

Before Pectra, DA cost per L2 transaction on OP-Stack chains was of the same order as the entire median L2 fee.
We compare {pt[n_treated]} blob-DA rollups with {pt[n_control]} L2s and sidechains that do not buy Ethereum blobs.
The design uses chain and day fixed effects, so the day effects absorb the ETH rally; unit = chain × day,
N = {pt[n_obs]:,}.

- **Fees.** Blob users' median L2 fees fell by {pt[b_fee]:.2f} log points (SE {pt[se_fee]:.2f}; placebo p =
  {pt[p_fee]:.2f}).
- **Activity.** Their L2 transactions rose by {pt[b_act]:.2f} (SE {pt[se_act]:.2f}; placebo p = {pt[p_act]:.2f}).
- **Dose-response.** Within blob users, activity rose more where fees fell more: slope {pt[dose_b]:.3f} (SE
  {pt[dose_se]:.3f}, N = {pt[dose_n]} chains).

The activity margin implies a blob-demand semi-elasticity of {pt[eta_activity_margin]:.2f} per mETH/blob. That
is small in absolute terms, but it is where all measurable responsiveness lies.

Limits:
- It is one event, and the activity effect clears the placebo distribution only at the 10% level.
- Most controls use their own gas tokens, so an ETH-ecosystem-specific shock is not ruled out. The dose-response
  argues against it being the whole story.
- OP Stack's Isthmus upgrade arrived the same week.

**Fusaka (low power).** With a ±5-day window, the reserve's introduction raised the price by {h[s2_pi]:.3f}
mETH/blob, and β = {h[s2_beta]:.3f} (two-way SE {h[s2_se_beta_twoway]:.3f}).

**A second, independent check.** In the congested Dencun quarters the daily price had SD {w[cong_sd_p]:.2f}
mETH/blob with capacity pinned at target. If detrended L2 activity (SD {w[l2_resid_sd]:.1%}) were the only
demand shifter, the implied |η| is {w[implied_eta]:.3f}. The spec-curve's elastic tail (|η| ≈
{sc[int_eta_p05]:.2f}) would require daily demand shifts of {w[implied_shift_sd_p5]:.0%}.

## 7. Mechanism: is there queueing at the floor?

The original motivation assumed that at the floor "allocation happens through queueing rather than price". At
the floor the price exceeds the market-clearing price (usage < target), which is excess supply; the prediction
is no queueing.

Xatu mempool sightings match {mp[match_dencun]:.0%} (Dencun) and {mp[match_pectra]:.0%} (Pectra) of blob
transactions (Figure 5).

In Dencun, transactions first seen when the price is at the floor:
- miss on average {mp[dencun_floor_mean_passed_over]:.2f} blocks before inclusion, against
  {mp[dencun_cong_mean_passed_over]:.2f} when the previous block was full;
- are priced out in {mp[dencun_floor_share_passed_blocks_priced_out]:.2%} of the blocks they miss;
- in {mp[dencun_floor_share_passed_blocks_with_spare_capacity]:.0%} of those missed blocks, there was spare blob
  capacity for them.

Within day and rollup, the floor changes the probability of missing the first block by
{mp[reg_dencun_waited_b_floor]:+.3f} (SE {mp[reg_dencun_waited_se_floor]:.3f}), against a base of
{mp[reg_dencun_waited_mean_base]:.2f}.

Delay is common in every state and is not explained by price or capacity. We attribute it to block-building
practice, not rationing. The floor regime is a regime of slack, not of queues.

## 8. Welfare

**Deadweight loss of the reserve.** Under exponential demand calibrated to each day, the reserve's deadweight loss
relative to allocating slack capacity at zero price is:
- {w[dwl_ci_eth]:.3f} ETH at the headline's elastic CI bound;
- at most {w[dwl_max_eth]:.2f} ETH (${w[dwl_max_usd]:,.0f}) over {w[reserve_days]} days at the most elastic total-demand bound;
- in every case at most {w[dwl_max_share]:.0%} of reserve-regime fees.

At the 1-wei floor the deadweight loss is zero to machine precision.

These bounds already cover the activity margin of Section 6b. Its implied semi-elasticity
({pt[eta_activity_margin]:.2f}) is less elastic than the most elastic value used ({w[eta_4]:.2f}), so the
derived-demand channel does not change the conclusion.

**Distributional effect.** The rule's first-order effect is distributional:
- {w[fees_dencun_eth]:,.0f} ETH (${w[fees_dencun_usd]:,.0f}) burned under Dencun, {w[fees_cong_share_dencun]:.0%}
  of it in 2024-Q4 and 2025-Q1;
- {w[fees_pectra_eth]:.1f} ETH under Pectra;
- {w[fees_reserve_eth]:.1f} ETH across all reserve regimes.

The Pectra capacity increase cut fees from {w[pectra_fee_pre_eth_day]:.1f} ETH per day (${w[pectra_fee_pre_usd_day]:,.0f})
to effectively zero, with no change in the blob intensity of L2 activity.

**Counterfactual mechanisms (qualitative; not estimated).** With demand this inelastic at the direct margin, the
mechanisms we can compare differ mainly in who pays, not in who is served.

- **Uniform-price auction at the same target.** In slack periods it would clear at zero, as the floor
  effectively does. In congested periods it would clear where demand meets the target, as the controller does
  on average, but without the controller's lagged, exponential adjustment. That adjustment is what produces the
  large price volatility in Section 6 (daily SD {w[cong_sd_p]:.2f} mETH/blob around a mean of
  {w[cong_mean_p]:.2f}).
- **Fixed posted price.** A price below the clearing level in congested periods would force rationing by other
  means (priority fees, delay). A price above it in slack periods would forgo usage worth only the Harberger
  triangles of Section 8.

Allocative differences between all three are bounded by the same small deadweight-loss numbers. The
first-order differences are revenue (burn) and volatility.

## 9. Limitations

- **One event.** The design rests on one supply shock, so the inference is by placebo dates.
- **EIP-7623** in the same fork raised calldata costs. Rollups posting calldata may have moved to blobs, biasing
  the response toward elastic, which makes the null conservative.
- **Payload not observed.** The deposit records purchased capacity, not payload, so fill rates cannot be
  observed directly.
- **Coverage.** The DA-intensity sample is 15 rollups with growthepie coverage; they carry most blobs but not the
  long tail.
- **Latency costs.** These are measured only as blocks missed, not valued.
- **No rollup-level migration evidence.** Celenium was unreachable from the collection host.

## 10. Conclusion

The rollups that buy Ethereum's blob space barely respond to its price at the margin they control. When the price
fell to zero they did not post more capacity per transaction. The volatility of congested prices implies the
same, and delays at the floor are not queues.

Whatever responsiveness exists appears to run through their users: blob costs pass into L2 fees, and L2 activity
follows. This evidence is suggestive, and a second clean supply shock in a congested market would be needed to
settle it.

For mechanism design the implication is that the pricing rule matters mainly for who pays and how much, not for
who gets capacity. The largest price episode in the sample, which carried {w[fees_cong_share_dencun]:.0%} of
Dencun's fees, ended with a capacity increase, not with a change to the pricing rule.
