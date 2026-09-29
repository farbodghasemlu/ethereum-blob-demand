"""09 — POST HOC (not in PRESPEC; DECISIONS D-24, D-25). Pass-through of the Pectra blob-price fall into L2 fees,
and the L2 activity response. Blob-DA rollups vs L2s/sidechains that do not buy Ethereum blobs.

Unit: chain x day (growthepie), +-28 days around Pectra, fork day excluded. Chain FE and DAY FE: a control group
makes day FE possible, so common shocks (the ETH rally from 2025-05-08) are absorbed.
  (1) fee pass-through:   ln(median L2 tx fee, ETH)  = a_c + d_t + b_fee * Blob_c x Post_t            (OLS)
  (2) activity:           E[txcount]                 = exp(a_c + d_t + b_act * Blob_c x Post_t)      (PPML)
  (3) ratio b_act / b_fee: elasticity of L2 activity w.r.t. the L2 fee (Wald; exclusion = Pectra moves blob users'
      activity only through their fees). Threat: OP Stack's Isthmus upgrade (L2 Pectra features) in the same week.
Implied contribution of the activity margin to total blob demand: b_act / pi (pi = blob price first stage).

Inference: CRV1 by chain and placebo-date permutation (same estimator at every placebo date in the EIP-4844 regime).
Outputs: output/tables/t5_passthrough.csv, output/figures/fig6_passthrough.{pdf,png}, output/logs/09_passthrough_posthoc.md
"""
import json
import numpy as np
import pandas as pd
import pyfixest as pf
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import GROWTHEPIE, DATA, TAB, FIG, LOG, NUM, save_numbers, con

warnings.filterwarnings("ignore")
T0, W = pd.Timestamp("2025-05-07"), 28
# Treated: the headline's blob-DA rollups (growthepie keys), minus mantle (EigenDA; 22 blobs in the window).
TREATED = ["arbitrum", "base", "ink", "linea", "lisk", "mode", "optimism", "scroll", "soneium", "starknet", "taiko",
           "unichain", "worldchain", "zksync_era"]
# Controls: no Ethereum blob DA in the window (DA layer in brackets): arbitrum_nova [AnyTrust DAC], celo [EigenDA],
# mantle [EigenDA], manta [Celestia], gravity [AnyTrust], plume [external DA], polygon_pos [own chain], ronin [own chain].
CONTROL = ["arbitrum_nova", "celo", "mantle", "manta", "gravity", "plume", "polygon_pos", "ronin"]
# Excluded: ethereum (L1, directly treated by Pectra's other EIPs), metis (moved to blobs at Pectra), fraxtal (DA unclear).

c = con()
g = c.sql(f"""SELECT origin_key AS chain, date, metric_key, value FROM '{GROWTHEPIE}'
              WHERE metric_key IN ('txcount', 'txcosts_median_eth', 'txcosts_median_usd')
                AND origin_key IN ({', '.join(f"'{k}'" for k in TREATED + CONTROL)})""").df()
g = g.pivot_table(index=["chain", "date"], columns="metric_key", values="value").reset_index()
g["date"] = pd.to_datetime(g.date)
g["blob"] = g.chain.isin(TREATED).astype(int)
g["day_id"] = g.date.dt.strftime("%Y%m%d").astype(int)
pi = json.loads((NUM / "04_headline.json").read_text())["head_pi"]


def did(t0, w=W, trends=False, drop=()):
    s = g[(g.date >= t0 - pd.Timedelta(days=w)) & (g.date <= t0 + pd.Timedelta(days=w)) & (g.date != t0) & ~g.chain.isin(drop)].copy()
    full = s.groupby("chain").apply(lambda x: len(x) == 2 * w and (x.txcount > 0).all() and (x.txcosts_median_eth > 0).all())
    s = s[s.chain.isin(full[full].index)].copy()
    s["treat_post"] = s.blob * (s.date > t0)
    s["t"] = (s.date - t0).dt.days
    s["ln_fee"] = np.log(s.txcosts_median_eth)
    tr = " + C(chain):t" if trends else ""
    f = pf.feols(f"ln_fee ~ treat_post{tr} | chain + day_id", data=s, vcov={"CRV1": "chain"})
    a = pf.fepois(f"txcount ~ treat_post{tr} | chain + day_id", data=s, vcov={"CRV1": "chain"})
    return dict(b_fee=f.coef()["treat_post"], se_fee=f.se()["treat_post"], b_act=a.coef()["treat_post"],
                se_act=a.se()["treat_post"], n_obs=int(a._N), n_treated=s[s.blob == 1].chain.nunique(),
                n_control=s[s.blob == 0].chain.nunique(), chains=",".join(sorted(s.chain.unique())))


main = did(T0)
main["ratio_act_fee"] = main["b_act"] / main["b_fee"]
main["se_ratio"] = abs(main["ratio_act_fee"]) * np.sqrt((main["se_act"] / main["b_act"]) ** 2 + (main["se_fee"] / main["b_fee"]) ** 2)
main["eta_activity_margin"] = main["b_act"] / pi
trd = did(T0, trends=True)
nopg = did(T0, drop=("plume", "gravity"))          # D-25: DA classification of Plume and Gravity is contestable

# placebo dates in the EIP-4844 regime, windows excluding Pectra
dates = pd.date_range("2024-04-11", "2025-11-04")
dates = dates[(dates + pd.Timedelta(days=W) < T0) | (dates - pd.Timedelta(days=W) > T0)]
pl = []
for tau in dates:
    try:
        r = did(tau)
        pl.append(dict(tau=tau.date(), b_fee=r["b_fee"], b_act=r["b_act"], n_obs=r["n_obs"]))
    except Exception:
        continue
pl = pd.DataFrame(pl)
p_fee = (np.abs(pl.b_fee) >= abs(main["b_fee"])).mean()
p_act = (np.abs(pl.b_act) >= abs(main["b_act"])).mean()

# per-chain changes (descriptive, for the figure)
w_ = g[(g.date >= T0 - pd.Timedelta(days=W)) & (g.date <= T0 + pd.Timedelta(days=W)) & (g.date != T0)]
pc = w_.assign(post=w_.date > T0).groupby(["chain", "blob", "post"])[["txcount", "txcosts_median_eth"]].mean().unstack("post")
pc = pd.DataFrame({"dln_fee": np.log(pc[("txcosts_median_eth", True)] / pc[("txcosts_median_eth", False)]),
                   "dln_act": np.log(pc[("txcount", True)] / pc[("txcount", False)])}).reset_index()
pd.DataFrame([{"spec": "main (chain FE + day FE)", **main}, {"spec": "robustness: + chain trends", **trd},
              {"spec": "robustness: controls without plume, gravity", **nopg}]).to_csv(TAB / "t5_passthrough.csv", index=False)
pc.to_csv(TAB / "t5_passthrough_by_chain.csv", index=False)

log = ["# 09 — POST HOC: L2 fee pass-through and L2 activity at Pectra", "",
       "Not pre-specified (added after D-24). Unit: chain x day; chain FE + day FE; +-28 days; fork day excluded.",
       f"N = {main['n_obs']:,} chain-days; {main['n_treated']} blob-DA rollups vs {main['n_control']} non-blob chains: {main['chains']}", "",
       f"- fee pass-through (ln median L2 fee in ETH): b = {main['b_fee']:.3f} (SE chain {main['se_fee']:.3f}); placebo p = {p_fee:.3f}",
       f"- L2 activity (PPML txcount): b = {main['b_act']:.3f} (SE chain {main['se_act']:.3f}); placebo p = {p_act:.3f} ({len(pl)} placebo dates)",
       f"- ratio (elasticity of L2 activity w.r.t. L2 fee): {main['ratio_act_fee']:.3f} (delta SE {main['se_ratio']:.3f})",
       f"- activity-margin contribution to blob demand: b_act / pi = {main['eta_activity_margin']:.3f} log points per mETH/blob (pi = {pi:.3f})",
       f"- robustness, + chain-specific linear trends: b_fee = {trd['b_fee']:.3f} ({trd['se_fee']:.3f}), b_act = {trd['b_act']:.3f} ({trd['se_act']:.3f})",
       f"- robustness, controls without plume and gravity ({nopg['n_control']} controls): b_fee = {nopg['b_fee']:.3f} ({nopg['se_fee']:.3f}), "
       f"b_act = {nopg['b_act']:.3f} ({nopg['se_act']:.3f})", "",
       "## Per-chain mean changes (descriptive)", "", pc.sort_values("dln_fee").to_markdown(index=False, floatfmt=".3f")]
(LOG / "09_passthrough_posthoc.md").write_text("\n".join(log) + "\n")
print("\n".join(log))
save_numbers("09_passthrough", {**{k: v for k, v in main.items() if k != "chains"}, "p_fee": p_fee, "p_act": p_act,
                                "n_placebo": len(pl), "trend_b_fee": trd["b_fee"], "trend_se_fee": trd["se_fee"],
                                "trend_b_act": trd["b_act"], "trend_se_act": trd["se_act"],
                                "nopg_b_fee": nopg["b_fee"], "nopg_se_fee": nopg["se_fee"], "nopg_b_act": nopg["b_act"],
                                "nopg_se_act": nopg["se_act"], "nopg_n_control": nopg["n_control"]})

INK2, S1C, S2C = "#52514e", "#2a78d6", "#eb6834"
fig, ax = plt.subplots(figsize=(6.0, 4.0))
for b, col, lab in ((1, S1C, "blob-DA rollups"), (0, S2C, "non-blob chains")):
    s = pc[pc.blob == b]
    ax.scatter(s.dln_fee, s.dln_act, s=28, color=col, label=lab, edgecolor="white", linewidth=0.8, zorder=3)
    for r in s.itertuples():
        ax.annotate(r.chain, (r.dln_fee, r.dln_act), xytext=(3, 2), textcoords="offset points", fontsize=6.5, color=INK2)
ax.axhline(0, color="#b5b4ae", lw=0.7)
ax.axvline(0, color="#b5b4ae", lw=0.7)
ax.set_xlabel("Δ ln median L2 tx fee (ETH), 28 days after vs before Pectra", color=INK2, fontsize=8)
ax.set_ylabel("Δ ln L2 transactions", color=INK2, fontsize=8)
ax.legend(frameon=False, fontsize=7.5)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.text(0.01, 0.01, "Unit: chain. Source: growthepie (CC BY 4.0). Post hoc, not pre-specified.", fontsize=6.5, color=INK2)
fig.tight_layout(rect=(0, 0.03, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig6_passthrough.{ext}", dpi=200)
