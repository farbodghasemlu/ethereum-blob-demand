"""10 — Render the paper: fills paper/draft_template.md with numbers from output/numbers/*.json and tables built
from output/tables/*.csv. Output: paper/draft.md. Any placeholder without a number raises, so no number in the
paper is typed by hand. Derived quantities (percent versions of log-point estimates) are computed here, not typed.
"""
import json
import math
import pandas as pd
from common import ROOT, NUM, TAB

SOURCES = {"a": "01_audit", "fr": "01_forkrules", "d": "03_descriptives", "h": "04_headline", "sc": "05_spec_curve",
           "mp": "06_mempool", "ix": "07_intraday", "w": "08_welfare", "pt": "09_passthrough"}
vals = {k: json.loads((NUM / f"{f}.json").read_text()) for k, f in SOURCES.items()}
h = vals["h"]
pct = lambda x: 100 * (math.exp(x) - 1)
vals["x"] = {
    "pinv": 1 / h["n_placebo"],
    **{f"{c}_pct": pct(h[f"{c}_beta"]) for c in ("head", "l15", "s1")},
    "l15_ci_pct_lo": pct(h["l15_ci_placebo_lo"]), "l15_ci_pct_hi": pct(h["l15_ci_placebo_hi"]),
    **{f"{c}_{b}_pct": pct(h[f"{c}_ci_placebo_{b}"]) for c in ("head", "l15", "lall") for b in ("lo", "hi")},
    **{f"{c}_wild_{b}_pct": pct(h[f"{c}_ci_wild_{b}"]) for c in ("head", "l15") for b in ("lo", "hi")},
    "s2_usd": h["s2_p_post"] * h["s2_ethusd_pre"] / 1000,
    "floor_full_share": 1 - vals["mp"]["dencun_floor_share_delayed_txs_never_capacity_or_price_constrained"],
    "act_pct": pct(vals["pt"]["b_act"]), "fee_pct": pct(vals["pt"]["b_fee"]),
    "n_blocks_checked": sum(vals["fr"][f"{r}_blocks_checked"] for r in ("dencun", "pectra", "fusaka", "bpo1", "bpo2")),
    "n_matched": sum(vals["mp"][f"matched_{r}"] for r in ("dencun", "pectra")) / 1e6,
    "n_mempool": sum(vals["mp"][f"{r}_{s}_n_txs"] for r in ("dencun", "pectra") for s in ("floor", "interior", "cong")) / 1e6,
}


def md_table(df, caption, label):
    # label kept for readability of this script; pandoc numbers tables by order of appearance
    return f"{df.to_markdown(index=False)}\n\nTable: {caption}\n"


# Table 1: regimes
t1 = pd.read_csv(TAB / "table1_regimes.csv").set_index("regime")
T1 = pd.DataFrame({
    "Blocks": t1.blocks.map("{:,.0f}".format),
    "Target / max (blobs)": [f"{a} / {b}" for a, b in zip(t1.target, t1["max"])],
    "Blobs per block": t1.blobs_per_block.map("{:.2f}".format),
    "Usage / target": t1.utilization_vs_target.map("{:.2f}".format),
    "Blocks at floor": t1.share_blocks_at_floor.map("{:.1%}".format),
    "Blocks at max": t1.share_blocks_at_max.map("{:.1%}".format),
    "Median fee (wei/blob gas)": t1.price_block_median_wei.map("{:,.0f}".format),
    "Fees (ETH)": t1.fees_eth.map("{:,.1f}".format),
    "Fees (USD)": t1.fees_usd.map("{:,.0f}".format),
    "USD per blob": t1.usd_per_blob_paid.map("{:.4f}".format),
    "Unattributed blobs": t1.unknown_share_blobs.map("{:.1%}".format),
}).T.reset_index().rename(columns={"index": ""})
T1_md = md_table(T1, "Blob market by fork regime. Blocks and fees from block headers and blob transactions. The "
                 "floor is 1 wei per unit of blob gas; one blob is 131,072 units of blob gas (128 KiB of purchased "
                 "capacity). USD at the daily ETH close.", "tbl:regimes")

# Table 2: main estimates
t2 = pd.read_csv(TAB / "t2_main.csv").set_index("spec")
ci = lambda lo, hi: f"[{lo:.3f}, {hi:.3f}]"
T2 = pd.DataFrame({
    "Coefficient on Post (log points)": t2.beta.map("{:.3f}".format),
    "SE, clustered by rollup": t2.se_crv1.map("{:.3f}".format),
    "SE, two-way (rollup, day)": t2.se_twoway.map("{:.3f}".format),
    "95% CI, placebo quantiles (reported)": [ci(a, b) for a, b in zip(t2.ci_placebo_lo, t2.ci_placebo_hi)],
    "95% CI, wild score bootstrap": [ci(a, b) for a, b in zip(t2.ci_wild_lo, t2.ci_wild_hi)],
    "95% CI, clustered": [ci(a, b) for a, b in zip(t2.ci_crv1_lo, t2.ci_crv1_hi)],
    "Placebo permutation p": t2.perm_p.map("{:.3f}".format),
    "Largest increase not ruled out": t2.mde_pct_placebo.map("{:.1f}%".format),
    "Minimum detectable effect, 80% power": t2.mde80_pct.map("{:.1f}%".format),
    "Semi-elasticity (per mETH/blob)": t2.eta.map("{:.3f}".format),
    "Elasticity at pre-shock price, elastic bound": t2.eps_placebo_lo.map("{:.2f}".format),
    "Log-price coefficient (floor-dependent)": t2.log_price_elasticity.map("{:.4f}".format),
    "N (rollup-days)": t2.n_obs.map("{:,}".format),
    "Rollups": t2.n_rollups.map(str),
}).T.reset_index()
T2.columns = ["", "(1) Blobs bought, 15 rollups (primary)", "(2) Blobs bought, all rollups", "(3) Blobs per L2 tx (intensity)"]
T2_md = md_table(T2, "Pectra supply shock, 28 days either side of 7 May 2025, fork day excluded. PPML with rollup "
                 "fixed effects, rollup-specific linear trends and day-of-week effects. Column 3 includes log L2 "
                 "transactions as an offset; its denominator responds to the treatment (Section 11), so it describes "
                 "the intensity margin and is not the primary estimate. First stage: the mean blob fee fell by "
                 f"{abs(h['head_pi']):.2f} mETH per blob (Newey-West SE {h['head_se_pi']:.2f}). Reported interval: "
                 f"quantiles of the same estimator at {h['n_placebo']} placebo break dates. Wild bootstrap: restricted "
                 "score bootstrap, Rademacher weights, all 32,768 sign vectors in columns 1 and 3, 99,999 draws in "
                 "column 2. Minimum detectable effect: 2.8 placebo standard deviations (80% power, 5% test). The elasticity bound is the elastic end of the reported interval divided by the first "
                 "stage, times the pre-shock price.", "tbl:main")

# Table 3: mempool
m = pd.read_csv(TAB / "t4_mempool_by_state.csv")
T3 = pd.DataFrame({"Regime": m.regime, "State when first seen": m.state, "Blob txs": m.n_txs.map("{:,}".format),
                   "Mean blocks missed": m.mean_passed_over.map("{:.2f}".format),
                   "Missed 2+ blocks": m.share_waited_2plus.map("{:.1%}".format),
                   "Missed blocks with room": m.share_passed_blocks_with_spare_capacity.map("{:.1%}".format),
                   "Missed blocks pricing tx out": m.share_passed_blocks_priced_out.map("{:.2%}".format)})
T3_md = md_table(T3, "Mempool-to-inclusion delay by market state, Dencun and Pectra, fork days excluded. Unit: blob "
                 "transaction matched to its first Xatu mempool sighting. A missed block is one proposed after the "
                 "first sighting and before inclusion. Shares of missed blocks are pooled over transactions that "
                 "missed between 1 and 300 blocks.", "tbl:mempool")

# Table 4: welfare
tr = pd.read_csv(TAB / "t3_welfare_transfers.csv")
T4a = pd.DataFrame({"Period": tr.period, "Days": tr.days, "Blobs": tr.blobs.map("{:,.0f}".format),
                    "Fees (ETH)": tr.fees_eth.map("{:,.2f}".format), "Fees (USD)": tr.fees_usd.map("{:,.0f}".format),
                    "Share of all fees": tr.share_of_all_fees_eth.map("{:.1%}".format)})
T4a_md = md_table(T4a, "Blob fees by period, with Dencun split by calendar quarter. Fees are burned, a transfer from "
                  "rollups to ETH holders.", "tbl:transfers")
dw = pd.read_csv(TAB / "t3_welfare_dwl.csv")
DWL_LABEL = {"primary, point estimate": "Primary specification, point estimate",
             "primary, elastic end of reported interval": "Primary specification, elastic end of reported interval",
             "intensity, elastic end of reported interval": "Intensity specification, elastic end of reported interval",
             "primary spec curve, 5th percentile": "Primary specification curve, 5th percentile",
             "intensity spec curve, 5th percentile": "Intensity specification curve, 5th percentile"}
T4b = pd.DataFrame({"Demand assumption": dw.eta_label.map(DWL_LABEL), "Semi-elasticity (per mETH/blob)": dw.eta.map("{:.3f}".format),
                    "Deadweight loss (ETH)": dw.dwl_eth.map("{:.3f}".format), "Deadweight loss (USD)": dw.dwl_usd.map("{:,.0f}".format),
                    "Share of fees": dw.dwl_as_share_of_fees.map("{:.1%}".format)})
T4b_md = md_table(T4b, f"Deadweight loss of the EIP-7918 reserve price over {vals['w']['reserve_days']} days from "
                  f"Fusaka onward, when usage averaged {vals['w']['reserve_util']:.0%} of target. Exponential demand "
                  "calibrated to each day's price and quantity; the counterfactual prices slack capacity at zero.",
                  "tbl:dwl")

# Table A1: fork rules
fr = pd.read_csv(TAB / "audit_fork_rules.csv")
TA = pd.DataFrame({"Regime": fr.regime, "Blocks checked": fr.blocks_checked.map("{:,}".format),
                   "Unexplained, own rule": fr.share_unexplained_own_rule.map("{:.4%}".format),
                   "Mispredicted by EIP-4844 rule": fr.share_mismatch_under_4844_rule.map("{:.1%}".format),
                   "Mispredicted by EIP-7918 rule": fr.share_mismatch_under_7918_rule.map("{:.1%}".format),
                   "Reserve comparisons within 3 wei": fr.share_reserve_ties.map("{:.4%}".format)})
TA_md = md_table(TA, "Excess blob gas recomputed for every block from its parent. Own rule: EIP-4844 for Dencun and "
                 "Pectra, EIP-7918 from Fusaka. The parent's blob fee is priced with the child block's update "
                 "fraction. Comparisons within 3 wei are not scored.", "tbl:forkrules")

vals["tbl"] = {"t1": T1_md, "t2": T2_md, "t3": T3_md, "t4a": T4a_md, "t4b": T4b_md, "ta": TA_md}
tpl = (ROOT / "paper" / "draft_template.md").read_text()
(ROOT / "paper" / "draft.md").write_text(tpl.format_map(vals))
print("wrote paper/draft.md")
