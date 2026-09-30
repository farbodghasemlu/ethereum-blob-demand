# Decisions log

Audit trail of judgement calls. Each entry: decision, alternatives, reason, sensitivity of the headline.
"Headline" = the Pectra DA-intensity semi-elasticity defined in PRESPEC.md. Entries are append-only; a
reversal is a new entry that points back.

---

**D-01 · Regime block counts taken from the deposit.** BPO2 has 1,897,648 blocks in `blocks_panel.parquet`
against 1,897,647 in the original project notes. Used the deposit, corrected the notes. Sensitivity: none.

**D-02 · `computed_blob_base_fee_wei` treated as valid in all regimes.** The project notes said it was wrong
post-Fusaka. It agrees with Blobscan's `observed_blob_gas_price_wei` within max(0.1%, 1 wei) on 100% of 9.29M
txs in every regime (`audit_price_fields.csv`), because EIP-7918 changes the excess-gas transition, which the
header records, not the fee function. Consequence: block-level price series (covering blocks without blob txs)
use the header fee; tx-level work uses the observed fee. Sensitivity: none by construction.

**D-03 · 1,128 blob txs (3,165 blobs, 0.013%) excluded.** They sit in blocks 26,077,033–26,077,465, beyond the
last collected header, so they have no timestamp, date or regime, and appear in `rollup_daily` as 38 NULL-date
rows. Alternative: collect the missing headers and re-deposit. Not worth a re-deposit of the 458 MB tx file for
rows outside every estimation window. Sensitivity: none (outside all windows).

**D-04 · Fork-transition days dropped from all daily estimation samples** (2025-05-07, 2025-12-03, 2025-12-09,
2026-01-07), as are the two partial days (2024-03-13, 2026-09-28). Alternative: assign each day its majority
regime. Dropping costs 6 of 930 days and removes days whose price mixes two rules. Sensitivity: the Pectra
transition day is the day before the post window starts; checked in the specification curve (window variants).

**D-05 · Rollup × day panel zero-filled within each rollup's active span** (first to last posting date). Without
zero-filling the panel conditions on posting, which selects on the extensive margin. Outside the span, a rollup
is treated as not in the market (entry/exit is a separate margin). Zero-filling adds 1,213 rollup-days (3.1%).
Alternative: no zero-fill (log-OLS on positives). Sensitivity: in the specification curve.

**D-06 · 'unknown' excluded from rollup-level regressions, reported everywhere else.** It is a residual mixture
of batchers, not a rollup, so rollup FE and trends are meaningless for it. Its blob share is reported in every
window table. Sensitivity: the total-demand robustness is re-run with 'unknown' as one extra unit.

**D-07 · Descriptive sub-periods of Dencun use calendar quarters, not floor incidence or launch events.**
Splitting on floor share selects on the outcome. Launch-event dates chosen after seeing Figure 1 would not be
ex ante either, so calendar quarters are the only split that is fixed independently of the data. Descriptive
only; no estimate uses it.

**D-08 · The "queueing at the floor" mechanism is treated as a hypothesis, not a fact.** At the 1-wei floor the
blob base fee is above the market-clearing price (usage < target), which is excess supply: every bid is
servable, so the prediction is no queueing. Rationing by delay should instead appear when the controller's
price lags a demand surge and blocks hit max. Tested directly with Xatu mempool inclusion delays (script 07,
analysis script 06). Does not affect the headline.

**D-09 · Celenium rollup-level Celestia data not collected.** Celenium's CDN returns HTTP 403 to our collection host's
IP for every endpoint, with and without a browser user agent. We could not work around it from that host; it needs a
residential connection. Consequence: no rollup-level migration evidence; the aggregate Celestia/EigenDA series
from growthepie are used only as a control series.

**D-10 · The floor is not modelled with a Tobit on price.** We considered treating the 1-wei floor as
censoring and recover a latent (shadow) price on floor days. In a demand equation the price is the regressor,
not the outcome, and on floor days capacity is slack, so the shadow price of blob space is zero: no latent
positive price exists to recover. The latent *excess* is observable exactly (unclipped cumulative
usage − target), so a censoring model adds nothing. The problem the Tobit aimed at is real, but it is a problem
of log price: log(1 wei) is an arbitrary point, and any log-price elasticity identified off a move to the floor
is set by the floor's level. Resolved by D-11 instead.

**D-11 · Price enters in levels (milli-ETH per blob), and the estimand is a semi-elasticity.**
Alternatives: log price (constant elasticity) or USD per blob. Log price is undefined in economic terms at the
floor (see D-10). A semi-elasticity d ln q / dp is well defined at p ≈ 0, maps into exponential demand, and gives
closed-form consumer surplus for the welfare section. ETH rather than USD because rollups earn fees and pay DA in
ETH, and because ETH/USD jumped 22% the day after Pectra, which would move a USD price for reasons unrelated to
the blob market. USD equivalents are reported at the pre-window mean ETH close. Point elasticities are reported
as η·p̄ at the pre-period mean price. Sensitivity: a log-price version is reported as a robustness check, and
its dependence on the floor level is shown explicitly.

**D-12 · BPO1 and BPO2 are not used as supply shocks.** They have no first stage: under the EIP-7918 reserve,
usage is already below target (46% and 34%), so raising capacity does not move the price. Mean block price in
the 28 days before and after BPO2 is 0.0005 vs 0.0015 mETH/blob. The Fusaka boundary moves the price from
≈0 to the reserve, but only 6 days separate Fusaka from BPO1, and the change is about $0.002/blob. It is
estimated as a low-power secondary check only.

**D-13 · Post-Fusaka reserve-driven price variation treated as endogenous.** The reserve is a function of the
execution base fee, which moves with L1 congestion and plausibly shifts rollup demand directly. The instrument we
considered (base-fee variation from non-rollup L1 events such as NFT mints) needs tx-level L1 data that the
deposit does not contain. An intraday version (rollup × day FE absorb daily demand; hourly base-fee deviations
shift the reserve) is run as an exploratory analysis only, labelled as such, and never pooled with Pectra.

**D-14 · Headline outcome is DA intensity: blobs purchased per L2 transaction.** ETH/USD rose 22% on 2025-05-08,
the day after Pectra, and 48% by 2025-05-13. The rally plausibly raised L2 activity at the same moment the blob
price fell, so a raw quantity jump confounds the price response with a demand shift. Normalizing by L2
transactions (growthepie `txcount`, entered as a PPML offset) removes activity-scale shocks. It identifies the
*direct* margin: fill rate, batching and DA-layer choice at given L2 activity. Cost: it omits the indirect margin
where L2 activity responds to pass-through of DA costs into L2 fees. That margin is small here: at 0.82 mETH/blob
and 872 L2 txs per blob (28 pre-Pectra days, 15 rollups), DA cost was $0.0016 per L2 tx. The unnormalized total-demand
estimate is reported alongside and labelled as confounded by the rally (biased toward a larger response). Sample
cost: 15 growthepie-matched rollups active through the ±28-day window (of 49 active labelled rollups; the 15
carry 82% of the window's blobs).

**D-15 · Upstream pipeline fixes (backup: `../backup_20260929_212541/`).** Script 07 wrote Xatu's BLOB-typed
hash as raw bytes (so it never joined to `blob_txs.hash`), kept one row per sensor sighting, and marked failed
days as done so they were never retried. Fixed: hash/address decoded to text, fee caps kept as hex (they are
16-byte little-endian UInt128), one row per tx with the earliest sighting and the number of sensors, and
failures retried. The collector's single DuckDB instance later grew to 25 GB RSS on the 1.6 GB daily files
from mid-2025; it was stopped, capped (memory_limit 4 GB, external file cache off) and resumed from its checkpoint
with no day lost. Script 09 `rm -rf`s its output directory, which would destroy `release/`. The new deposit
version is therefore packaged into `../release_v2/`, and `release/` is never written.

**D-16 · First-stage price = mean header blob base fee over ALL blocks of the day.** Alternatives: the
blob-gas-weighted price actually paid, or the daily median. The paid price is endogenous to posting-time
choices (rollups post when it is cheap). The all-block mean is the price schedule a rollup faces. Sensitivity:
all three appear in the specification curve.

**D-17 · Inference for a single break.** Identification comes from one protocol event, so rollup-clustered SEs
(15 clusters) describe cross-rollup noise only, not the uncertainty from a common shock on the fork date.
Primary inference is a placebo-date permutation: the identical estimator at every placebo break date in the
EIP-4844 regime whose window excludes both real forks. CRV1-by-rollup and two-way (rollup, day) SEs are
reported as well.

**D-18 · Mempool collection covers every Dencun and Pectra day, not only floor days.** Selecting days by floor
incidence selects on the outcome, and the mechanism test needs non-floor days for contrast. The range is
2024-03-13 to 2025-12-03; post-Fusaka is not collected.

**D-19 · Mantle stays in the headline sample although it posted 0 blobs pre-Pectra and 22 post.** It meets the
PRESPEC sample rule (active span covers the window, txcount present), and the rule is not revised after seeing
results. Its weight in the pooled PPML is negligible: dropping it moves β from −0.0286 to −0.0287. Its
per-rollup β is undefined, so it is omitted from the heterogeneity figure (noted there).

**D-20 · Pooled PPML is volume-weighted, and this matters for the sign.** Base (46% of the sample's blobs) has
β = −0.09 and pulls the pooled β negative, while 9 of 14 rollups with a defined per-rollup β have β > 0. An
equal-weighted mean of per-rollup βs is +0.022. Neither weighting changes the substantive conclusion (no
material response), but the headline sign should not be read as meaningful. PPML weighting is kept because the
welfare object is aggregate blob demand.

**D-21 · Documentation fixes upstream (DATASETS.md, 08 notes).** Corrected the computed-fee statement (D-02),
documented the Xatu collector changes (D-15), and recorded that Celenium was unreachable and Celestia columns come
from growthepie (D-09). These change DATASETS.md's checksum, so they ship in deposit version 2.

**D-22 · The execution-base-fee instrument fails exclusion mechanically, not only via L1 congestion.** Every blob
rides in a type-3 tx that pays execution gas at the same base fee, so base-fee variation (including variation
driven by non-rollup events such as NFT mints) raises the cost of posting through two channels: the EIP-7918
reserve and the carrier tx's own execution gas. Both are proportional to the base fee, so no base-fee
instrument can isolate the blob-price effect. What it can identify is the response to the full per-post cost,
and even that requires the base-fee variation to be unrelated to L2 activity. Exploratory estimate (script 07,
BPO2, rollup × hour, rollup×day and rollup×hour-of-day FE): +0.060 (SE 0.020) log points of blobs per log point
of base fee. Posting rises in expensive hours: the wrong sign for a cost response, and what one expects if busy
L1 hours are busy L2 hours. Reported as evidence that intraday base-fee variation is contaminated by demand, not
as an elasticity.

**D-23 · Welfare uses exponential demand calibrated day by day, with η at bounds rather than the point estimate.**
The point estimate is ≈0 (wrong sign), which would mechanically give zero deadweight loss. The DWL table therefore
evaluates η at the elastic 95% CI bound (−0.045), the DA-intensity spec-curve 5th percentile (−0.43), and the
total-demand median (−0.32) and 5th percentile (−1.36), the last two being confounded upper bounds. The
counterfactual for the EIP-7918 reserve is zero-price allocation of slack capacity (usage was 32% of target on
average), with the protocol's own implicit assumption that marginal cost is zero below target. Alternatives: a
positive marginal cost of blob space (node bandwidth/storage) would shrink the reserve's DWL further, possibly
to a gain; a linear demand curve would give the same Harberger triangle to first order at these tiny prices.
Result: DWL ≤ 2.6 ETH (≈$8k) over 296 reserve-regime days even at the most elastic value. The rule's
first-order welfare effect is distributional: 4,704 ETH ($14.8M) of Dencun fees, 67% of them in 2024-Q4 and
2025-Q1. An independent scale check (price volatility in congested quarters vs detrended L2-activity
volatility) implies |η| ≈ 0.07 per mETH/blob, inside the spec-curve range and near the headline CI.

**D-24 · CORRECTION to D-14's reasoning (not to PRESPEC).** D-14 argued the omitted pass-through margin was small
because DA cost was ~$0.0016 per L2 tx. Compared with L2 fees, that is not small. For OP-Stack chains, pre-Pectra
DA cost per tx was of the same order as the whole median L2 tx fee (World $0.0061 vs $0.0019; Base $0.0016 vs
$0.0022), and median fees fell 0.6–1.9 log points at Pectra, while non-blob chains' fees rose 0.1–0.3 with the
ETH price. Blob users' L2 activity also rose more than non-blob chains' activity. The DA-intensity headline
remains a correctly defined estimand (the rollup's own margin), so PRESPEC is not revised. Its interpretation
changes: it is not the total demand response. The total response (S1, +0.19 log points, permutation p < 0.002)
plausibly contains a genuine price effect through L2 fees and L2 activity, not only the rally. Addressed by a
POST-HOC analysis (script 10), labelled as such, with non-blob chains as a control group so that day fixed
effects absorb common shocks.

**D-25 · Post-hoc pass-through design (script 09): control group and classification.** Treated: the headline's
blob-DA rollups (growthepie keys) minus Mantle, whose DA is EigenDA (22 blobs in the window). Controls: L2s and
sidechains not buying Ethereum blobs in the window: Arbitrum Nova (AnyTrust), Celo and Mantle (EigenDA), Manta
(Celestia), Gravity (AnyTrust), Plume (external DA), Polygon PoS and Ronin (own chains). Excluded: Ethereum L1
(directly treated by Pectra's other EIPs), Metis (moved to blobs at Pectra), Fraxtal (DA unclear; its batcher may
be among 'unknown'). Chains lacking complete txcount/fee data in the window drop out by rule (Arbitrum Nova,
zkSync Era), leaving 13 vs 7. Alternatives: a narrower ETH-gas-only control group (Manta alone) is too small to
use; Ethereum L1 as a control is contaminated. Fee outcome in ETH, so ETH/USD does not enter; non-ETH-gas
controls' fees move with their own tokens, which adds noise. Results: activity +0.28 (SE 0.11, placebo p =
0.097); fees −0.37 (SE 0.20, placebo p = 0.35). Reported as suggestive only. A reviewer could reasonably classify Plume and Gravity differently. Dropping them (5 controls): activity
+0.26 (SE 0.11), fees −0.44 (SE 0.20); insensitive.

**D-26 · Analysis inputs moved to deposit version 2 (`../release_v2/`, same DOI doi:10.7910/DVN/4AOXKT, draft).**
v2 = v1 + `mempool_inclusion.parquet` (5.38M blob txs matched to their first Xatu sighting, Dencun and Pectra)
+ corrected DATASETS.md, regenerated CODEBOOK/MANIFEST/validation report. The 13 other data files are
byte-identical to v1. `growthepie_fundamentals.parquet` was rebuilt with identical content but different row
order (the merge wrote it without ORDER BY), so the v1 bytes were kept; the merge now orders it for future runs.
All v1 results are therefore unchanged by construction. Deposit: 1 file added, 4 replaced, 14 unchanged; not
published.

**D-08 result (script 06, full data).** Queueing at the floor is rejected. Transactions first seen at the floor
wait the fewest blocks (mean 1.03 Dencun / 0.89 Pectra, vs 2.25 / 1.26 when the previous block was full), are
priced out by 0.08% / 0.07% of the blocks they miss, and almost never wait over an hour (0.009%). Within
rollup-day, the floor changes P(miss first block) by +1.8 pp (Dencun) / −0.6 pp (Pectra) on bases of 42% / 31%.
About half of delayed floor txs passed at least one full block: usage bursts reach max even when the excess is 0.
The rationing that exists at the floor is about one block (~12 s). Congested states show more waiting, and in
Dencun, being priced out (27% of passed blocks) is where price actually rations. Grace-period definition of
"first opportunity" (block timestamp > first sighting, no allowance for build latency) inflates miss rates
uniformly across states; state comparisons are unaffected.

**D-27 · Magnitude bound (minimum detectable effect) and which interval is reported.** The reported interval
is the placebo-quantile interval (Conley and Taber 2011): β̂ minus the 97.5th and 2.5th percentiles of β at 516
placebo break dates, same estimator. It is the only one of the three procedures that reflects common shocks on the
break date, which is the dominant risk with one event, and PRESPEC §4 named placebo inference as primary. It is
also the widest for the headline. Headline: [−0.222, 0.110] log points, so the Pectra price cut (0.90 mETH/blob,
≈$1.40 to zero) rules out increases in blobs per L2 transaction larger than 11.6%. That bounds the elasticity at the
pre-shock price at about −0.10. The price cut was 100% of the price, so the data do not lack variation; the bound is
tight because the response was small. The bound holds for prices in the identified range [0, 4.45] mETH/blob
(pre-window daily range), which covers 98.6% of EIP-4844 days but only 72.8% of blob fees: 27% of fees were paid
on 9 spike days above that range, where the bound does not apply.

**D-28 · Unnormalized levels promoted to co-primary (2026-09-30).** This is not a PRESPEC revision:
the levels specification was pre-listed as S1 and was estimated as specified. Columns: (2) the headline's 15
rollups, so that columns 1 and 2 differ only by the L2-activity offset; (3) all 49 labelled rollups (S1 as
pre-listed). Same FE and trends as the headline. We considered log price. A log-price coefficient
identified off a move to the 1-wei floor depends on the floor level (D-10; S5), so the table keeps price in
mETH/blob and reports the log-price elasticity in a separate, flagged row (−0.010, 1-wei floor). Result: +0.211
(placebo CI [0.080, 0.337]; wild bootstrap [−0.084, 0.416]). Significance of the levels response depends on the
inference procedure, and that disagreement is reported. Either way the implied elasticity at the pre-shock price
is at most 0.31 in magnitude (placebo bound). Levels mix any price response with the ETH rally (D-14); the bound
is therefore an upper bound on the total price response.

**D-29 · Wild cluster bootstrap for PPML with 15 clusters.** The standard wild cluster bootstrap-t is for OLS;
for PPML we use the restricted wild score bootstrap (Kline and Santos 2012; the ML analogue in boottest).
Rademacher weights with all 2^15 = 32,768 sign vectors enumerated (99,999 random draws for 49 clusters); CI by
test inversion on a 0.0025 grid. A simulation with 15 equal clusters and common day shocks gave 7.3% size at 5%
and 99% power against a 0.4 alternative. Base supplies 94.6% of the headline's score variance, so the effective
number of clusters is close to one. This is why CRV1 SEs are too small and why the placebo interval is reported.
Alternatives: pairs cluster bootstrap (unreliable with few, unequal clusters); Webb six-point weights (not needed
with full enumeration at G = 15).

**D-30 · Blob schedule verified from the update rule, and a correction on the Fusaka boundary.** Script 01
recomputes every block's excess_blob_gas from its parent: the EIP-4844 rule for Dencun and Pectra, the EIP-7918 rule
from Fusaka (BLOB_BASE_COST = 2^13). The parent's blob fee is priced with the child block's update fraction; the BPO1
activation block is consistent only with this convention (a client-implementation detail, not documented in the
deposit). Result: 0 unexplained blocks in every regime among 6,650,443 checked; 5 reserve comparisons within 3 wei
are left unscored. The reserve governs the update in 29.5% (Fusaka), 76.9% (BPO1) and 87.0% (BPO2) of blocks,
reproducing the project notes. Correction: the notes said Fusaka's boundary rests only on the floor disappearing.
The update rule separates the regimes: the EIP-4844 rule mispredicts 29.5% of Fusaka blocks and the EIP-7918 rule
would mispredict 37.6% of Dencun and 46.1% of Pectra blocks. The boundary is as firmly identified as the others.

**D-31 · One replication directory: `../release/` = deposit version 2.** v1 was archived to
`../archive/release_v1_2026-09-29.tar.gz`, verified member by member against v1's manifest, and removed;
`release_v2/` was moved into `release/` and set read-only. The 19 files listed in its manifest match the SHA-256
recorded by the deposit script when each was uploaded to, or confirmed against, the Dataverse draft (the server's
MD5 fixity check). Two files in the directory are deposit tooling and are not uploaded by design:
`manifest.json` (machine-readable manifest used by the deposit script) and `dataverse_dataset.json` (citation
metadata payload). A live re-check against the draft was not possible at that point (no API token in the
environment). Upstream script 09 now refuses to overwrite a non-empty output directory.

**D-32 · Celenium dropped from the plan.** Celenium blocks the collection host and no alternative network is
available. Rollup-level migration between DA layers is therefore unobservable here; the paper says so in its
limitations, names Celenium as the source that would provide it, and uses only growthepie's aggregate
cross-layer series.

**D-33 · Paper framing and presentation (2026-09-30).** (a) The welfare claim is stated regime by regime. The
$14.8M of Dencun fees and the ≤2.6 ETH deadweight loss belong to different regimes: 67% of the fees were paid when
capacity was full (usage 97% of target), where any market-clearing mechanism collects scarcity rents of similar
size, and the 2.6 ETH bound applies to the post-Fusaka reserve when capacity was slack. Comparing the two directly
would overstate the case. (b) The abstract reports the placebo-quantile interval and names the procedure; the wild
bootstrap and clustered intervals are in Table 2. (c) The post-hoc pass-through analysis is labelled post hoc in
the section heading and first paragraph and is kept out of the abstract. (d) Harberger (1964) is not cited because
its bibliographic record could not be verified against Crossref; every other reference was verified. (e) The
mempool counts are stated as matched (5.4M) and analysed (5.1M, first seen before inclusion).
