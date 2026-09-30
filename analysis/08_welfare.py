"""08 — Welfare accounting under the estimated demand (DECISIONS D-11, D-23).

Demand is exponential in the blob price, Q(p) = A·exp(η p), p in mETH/blob, calibrated to each day's observed
(p_t, Q_t). η is taken at several values because the point estimate is ~0: the elastic ends of the reported
(placebo) intervals for the headline and the levels specification, the 5th percentile of the DA-intensity
specification curve, and the 5th percentile of the total-demand specifications (confounded by the ETH rally, so an
upper bound on responsiveness).

(a) Transfers: blob fees paid (burned) by regime and calendar quarter, ETH and USD.
(b) Deadweight loss of the EIP-7918 reserve relative to zero-price allocation of slack capacity (usage < target on
    those days): DWL_t = Q_t [ (1 - exp(-η p_t)) / η - p_t ]  (mETH), i.e. the Harberger triangle under exponential demand.
    The same formula for Dencun/Pectra floor days gives ~0 (p = 1 wei).
(c) Pectra capacity shock: fees per day before/after within the headline window.
(d) Consistency: price volatility in the congested Dencun quarters implies a demand-shift SD of |η|·SD(p).

Outputs: output/tables/t3_welfare_*.csv, output/logs/08_welfare.md
"""
import numpy as np
import pandas as pd
from common import BLOB_TXS, PRICES, GROWTHEPIE, DATA, TAB, LOG, GAS_PER_BLOB, con

c = con()
d = pd.read_parquet(DATA / "day_panel.parquet")
d = d[~d.transition_day & ~d.partial_day].copy()
d["date"] = pd.to_datetime(d.date)
d["p"] = d.price_block_mean_wei * GAS_PER_BLOB / 1e15            # mETH per blob (all-block mean)
d["util"] = d.avg_blobs_per_block / d.target_blobs

# η grid, read from the estimation outputs so the numbers stay in sync with scripts 04-05
t2 = pd.read_csv(TAB / "t2_main.csv").set_index("spec")
sc = pd.read_csv(TAB / "spec_curve.csv")
HEAD, LEV = "(1) DA intensity [headline]", "(2) Levels, same 15 rollups"
ETA = {
    "headline point (≈0; sign wrong)": min(t2.loc[HEAD, "eta"], 0.0),
    "headline, elastic end of reported (placebo) CI": t2.loc[HEAD, "eta_placebo_lo"],
    "levels, elastic end of reported (placebo) CI": t2.loc[LEV, "eta_placebo_lo"],
    "spec curve DA-intensity p5": sc[sc.activity != "none"].eta.quantile(.05),
    "total demand spec-curve p5 (confounded)": sc[sc.activity == "none"].eta.quantile(.05),
}
log = ["# 08 — Welfare accounting", "", "η values used (log points per mETH/blob):", ""] + \
      [f"- {k}: {v:.4f}" for k, v in ETA.items()] + [""]

# ---- (a) transfers -----------------------------------------------------------------------------------
tr = c.sql(f"""
SELECT regime, CASE WHEN regime = 'dencun' THEN strftime(date, '%Y') || '-Q' || quarter(date) ELSE regime END AS period,
       min(date) AS first_day, max(date) AS last_day, count(DISTINCT date) AS days, sum(blob_count) AS blobs,
       sum(blob_fee_wei) / 1e18 AS fees_eth, sum(blob_fee_wei / 1e18 * p.close) AS fees_usd,
       sum(blob_fee_wei) FILTER (WHERE p.close IS NULL) / 1e18 AS fees_eth_without_usd
FROM '{BLOB_TXS}' t LEFT JOIN (SELECT date::DATE AS date, close FROM '{PRICES}' WHERE asset = 'ETH') p USING (date)
WHERE regime IS NOT NULL GROUP BY 1, 2 ORDER BY first_day""").df()
tr["share_of_all_fees_eth"] = tr.fees_eth / tr.fees_eth.sum()
tr["usd_per_blob"] = tr.fees_usd / tr.blobs
tr.to_csv(TAB / "t3_welfare_transfers.csv", index=False)
log += ["## (a) Transfers (blob fees burned). Unit: blob tx aggregated by period; ETH, USD at daily close", "",
        tr.to_markdown(index=False, floatfmt=",.4g"), ""]

# ---- (b) reserve DWL (post-Fusaka) and floor DWL (Dencun/Pectra) ----------------------------------------
def dwl_meth(q, p, eta):
    if eta == 0:
        return np.zeros_like(p)
    return q * ((1 - np.exp(-eta * p)) / eta - p)

d["q"] = d.blobs_header
rows = []
for name, eta in ETA.items():
    for grp, sel in [("EIP-7918 reserve (fusaka, bpo1, bpo2)", d.pricing_regime == "eip7918_reserve")]:
        s = d[sel]
        dw = dwl_meth(s.q.values, s.p.values, eta)
        fees_meth = (s.q * s.p).sum()
        rows.append(dict(eta_label=name, eta=eta, group=grp, days=len(s), mean_util_vs_target=s.util.mean(),
                         dwl_eth=dw.sum() / 1e3, dwl_usd=(dw / 1e3 * s.eth_usd).sum(),
                         fees_eth_at_block_mean_price=fees_meth / 1e3, dwl_as_share_of_fees=dw.sum() / fees_meth if fees_meth else np.nan))
dwl = pd.DataFrame(rows)
dwl.to_csv(TAB / "t3_welfare_dwl.csv", index=False)
log += ["## (b) Deadweight loss relative to zero-price allocation of slack capacity. Unit: day", "",
        "Valid only where capacity is slack (mean utilization vs target reported); marginal cost of blob space below "
        "target taken as zero, which is the protocol's own assumption. At the EIP-4844 floor (1 wei per blob gas = "
        "1.3e-10 mETH/blob) the same formula is zero to machine precision for every η, so floor pricing carries no "
        "deadweight loss relative to zero price.", "",
        dwl.to_markdown(index=False, floatfmt=",.4g"), ""]

# ---- (c) Pectra capacity shock: fees before/after --------------------------------------------------------
t0 = pd.Timestamp("2025-05-07")
w = d[(d.date >= t0 - pd.Timedelta(days=28)) & (d.date <= t0 + pd.Timedelta(days=28))]
pre, post = w[w.date < t0], w[w.date > t0]
cap = pd.DataFrame([dict(side="pre (28 days)", fees_eth_per_day=pre.blob_fee_eth.mean(), blobs_per_day=pre.blobs_header.mean(),
                         mean_price_meth=pre.p.mean(), fees_usd_per_day=pre.blob_fee_usd.mean()),
                    dict(side="post (28 days)", fees_eth_per_day=post.blob_fee_eth.mean(), blobs_per_day=post.blobs_header.mean(),
                         mean_price_meth=post.p.mean(), fees_usd_per_day=post.blob_fee_usd.mean())])
cap.to_csv(TAB / "t3_welfare_pectra_fees.csv", index=False)
log += ["## (c) Fees around the Pectra capacity increase. Unit: day (all rollups incl. unknown)", "",
        cap.to_markdown(index=False, floatfmt=",.4g"), "",
        "With the DA-intensity response indistinguishable from zero, the fall in fees is a reduction in a transfer "
        "(burn), not a change in allocation.", ""]

# ---- (d) consistency: implied demand-shift volatility in congested Dencun quarters -------------------------
cong = d[(d.regime == "dencun") & (d.date >= "2024-10-01") & (d.date < "2025-04-01")]
sd_p = cong.p.std()
lines = [f"Dencun 2024-Q4 and 2025-Q1 (calendar-defined, D-07): SD of daily mean price = {sd_p:.3f} mETH/blob, mean "
         f"{cong.p.mean():.3f}, mean utilization vs target {cong.util.mean():.3f}. With capacity fixed at target, "
         "a price that clears the market moves by Δln(demand shift)/|η|, so the implied SD of daily demand shifts is |η|·SD(p):"]
lines += [f"- {k}: {abs(v) * sd_p:.3%}" for k, v in ETA.items()]
# Benchmark: detrended volatility of aggregate L2 activity (growthepie txcount, rollups with full coverage) over the
# same calendar period. Not causal; a scale check on which η is compatible with the observed price volatility.
l2 = c.sql(f"""SELECT date, sum(value) AS tx FROM '{GROWTHEPIE}' WHERE metric_key = 'txcount'
               AND origin_key IN (SELECT origin_key FROM '{GROWTHEPIE}' WHERE metric_key = 'txcount'
                                  AND date BETWEEN '2024-10-01' AND '2025-03-31' GROUP BY 1 HAVING count(*) = 182)
               AND date BETWEEN '2024-10-01' AND '2025-03-31' GROUP BY 1 ORDER BY 1""").df()
y = np.log(l2.tx.values)
x = np.arange(len(y))
resid_sd = np.std(y - np.polyval(np.polyfit(x, y, 1), x), ddof=2)
lines += ["", f"Benchmark: detrended SD of ln(aggregate L2 txs), same period, N = {len(l2)} days = {resid_sd:.3%}. "
          f"Implied |η| if L2 activity were the only demand shifter: {resid_sd / sd_p:.4f} per mETH/blob "
          "(point elasticity at the mean price " f"{resid_sd / sd_p * cong.p.mean():.4f}). A scale check, not an estimate."]
log += ["## (d) Consistency: congestion-phase price volatility vs demand elasticity", ""] + lines + [""]
(LOG / "08_welfare.md").write_text("\n".join(log) + "\n")
print("\n".join(log))

from common import save_numbers
dd = tr.set_index("period")
dw = dwl.set_index("eta_label")
save_numbers("08_welfare", {
    **{f"eta_{i}": v for i, v in enumerate(ETA.values())},
    "fees_dencun_eth": tr[tr.regime == "dencun"].fees_eth.sum(), "fees_dencun_usd": tr[tr.regime == "dencun"].fees_usd.sum(), "fees_dencun_usd_m": tr[tr.regime == "dencun"].fees_usd.sum() / 1e6,
    "fees_pectra_eth": dd.loc["pectra", "fees_eth"], "fees_pectra_usd": dd.loc["pectra", "fees_usd"],
    "fees_reserve_eth": tr[tr.regime.isin(["fusaka", "bpo1", "bpo2"])].fees_eth.sum(),
    "fees_reserve_usd": tr[tr.regime.isin(["fusaka", "bpo1", "bpo2"])].fees_usd.sum(),
    "fees_cong_share_dencun": dd.loc[["2024-Q4", "2025-Q1"], "fees_eth"].sum() / tr[tr.regime == "dencun"].fees_eth.sum(),
    "fees_2024q3_eth": dd.loc["2024-Q3", "fees_eth"],
    "dwl_max_eth": dw.dwl_eth.max(), "dwl_max_usd": dw.dwl_usd.max(), "dwl_ci_eth": dw.loc["headline, elastic end of reported (placebo) CI", "dwl_eth"],
    "dwl_ci_usd": dw.loc["headline, elastic end of reported (placebo) CI", "dwl_usd"], "dwl_max_share": dw.dwl_as_share_of_fees.max(),
    "reserve_days": int(dw.days.iloc[0]), "reserve_util": dw.mean_util_vs_target.iloc[0],
    "pectra_fee_pre_eth_day": cap.fees_eth_per_day.iloc[0], "pectra_fee_pre_usd_day": cap.fees_usd_per_day.iloc[0],
    "pectra_fee_post_eth_day": cap.fees_eth_per_day.iloc[1],
    "cong_sd_p": sd_p, "cong_mean_p": cong.p.mean(), "l2_resid_sd": resid_sd, "implied_eta": resid_sd / sd_p,
    "implied_shift_sd_ci": abs(ETA["headline, elastic end of reported (placebo) CI"]) * sd_p,
    "dwl_lev_eth": dw.loc["levels, elastic end of reported (placebo) CI", "dwl_eth"], "implied_shift_sd_p5": abs(ETA["spec curve DA-intensity p5"]) * sd_p,
})
