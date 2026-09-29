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
failures retried. Script 09 `rm -rf`s its output directory, which would destroy `release/`. The new deposit
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
