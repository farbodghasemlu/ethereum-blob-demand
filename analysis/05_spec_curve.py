"""05 — Specification curve for the headline (PRESPEC.md §6) and per-rollup heterogeneity. ROBUSTNESS.

Reduced forms are fitted once per (window, trend, activity, estimator, dow, zerofill); first stages once per
(window, price, trend, dow); eta = beta/pi for every combination. ols_log uses positive days only, so its
zerofill variants coincide and are kept once. SEs: CRV1 by rollup (few clusters; see PRESPEC §4).

Outputs: output/tables/spec_curve.csv, output/tables/heterogeneity_pectra.csv,
         output/figures/fig3_spec_curve.{pdf,png}, output/figures/fig4_heterogeneity.{pdf,png},
         output/logs/05_spec_curve.md
"""
import itertools
import numpy as np
import pandas as pd
import pyfixest as pf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import TAB, FIG, LOG
from est import load, window_sample, reduced_form, first_stage

T0 = pd.Timestamp("2025-05-07")
HEAD = dict(w=28, trend="linear", activity="offset", estimator="ppml", price="mean", dow=True, zerofill=True)
DIMS = dict(w=[14, 21, 28, 42, 56], trend=["none", "linear", "quadratic"], activity=["offset", "control", "none"],
            estimator=["ppml", "ols_log", "ols_log1p"], price=["mean", "median", "paid"], dow=[True, False],
            zerofill=[True, False])

panel, day = load()
samples = {w: window_sample(panel, T0, w) for w in DIMS["w"]}

rf = {}
for w, tr, act, est, dw, zf in itertools.product(DIMS["w"], DIMS["trend"], DIMS["activity"], DIMS["estimator"],
                                                 DIMS["dow"], DIMS["zerofill"]):
    if est == "ols_log" and not zf:
        continue
    rf[(w, tr, act, est, dw, zf)] = reduced_form(samples[w], tr, act, est, dw, zf, twoway=False)
fs = {(w, pr, tr, dw): first_stage(day, T0, w, pr, tr, dw)
      for w, pr, tr, dw in itertools.product(DIMS["w"], DIMS["price"], DIMS["trend"], DIMS["dow"])}

rows = []
for (w, tr, act, est, dw, zf), r in rf.items():
    for pr in DIMS["price"]:
        f = fs[(w, pr, tr, dw)]
        eta = r["beta"] / f["pi"]
        se = np.sqrt((r["se_beta_rollup"] / f["pi"]) ** 2 + (r["beta"] * f["se_pi"] / f["pi"] ** 2) ** 2)
        rows.append(dict(w=w, trend=tr, activity=act, estimator=est, price=pr, dow=dw, zerofill=zf,
                         beta=r["beta"], se_beta=r["se_beta_rollup"], p_beta=r["p_beta_rollup"], pi=f["pi"],
                         eta=eta, se_eta=se, eps=eta * f["p_pre"], n_obs=r["n_obs"], n_rollups=r["n_rollups"]))
sc = pd.DataFrame(rows)
sc["headline"] = np.all([sc[k] == v for k, v in HEAD.items()], axis=0)
sc.to_csv(TAB / "spec_curve.csv", index=False)

# The 'activity' dimension changes the estimand (none = total demand, confounded by the ETH rally; D-14),
# so summaries are reported for the DA-intensity specs (offset/control) and for 'none' separately.
def summ(s):
    return dict(n_specs=len(s), share_beta_neg=(s.beta < 0).mean(), share_eta_neg=(s.eta < 0).mean(),
                share_beta_sig5=(s.p_beta < 0.05).mean(), share_sig5_expected_sign=((s.p_beta < 0.05) & (s.eta < 0)).mean(),
                eta_p05=s.eta.quantile(.05), eta_median=s.eta.median(), eta_p95=s.eta.quantile(.95),
                eps_median=s.eps.median(), N_min=s.n_obs.min(), N_max=s.n_obs.max())
S = pd.DataFrame({"DA intensity (offset/control)": summ(sc[sc.activity != "none"]),
                  "offset only": summ(sc[sc.activity == "offset"]),
                  "total demand (none)": summ(sc[sc.activity == "none"])}).T
hr = sc[sc.headline].iloc[0]
pct = (sc[sc.activity != "none"].eta < hr.eta).mean()

# ---- per-rollup heterogeneity (headline spec, one rollup at a time) ---------------------------------
d = samples[28]
het = []
for r_, g in d.groupby("rollup"):
    m = pf.fepois("n_blobs ~ post + t + C(dow)", data=g, offset="lT", vcov="hetero")
    het.append(dict(rollup=r_, beta=m.coef()["post"], se=m.se()["post"], n_obs=int(m._N),
                    blobs_pre=g[g.t < 0].n_blobs.sum(), blobs_post=g[g.t > 0].n_blobs.sum(),
                    l2tx_growth=np.log(g[g.t > 0].l2_txcount.mean() / g[g.t < 0].l2_txcount.mean()),
                    blob_growth=np.log(g[g.t > 0].n_blobs.mean() / g[g.t < 0].n_blobs.mean())))
het = pd.DataFrame(het).sort_values("beta")
het.to_csv(TAB / "heterogeneity_pectra.csv", index=False)

(LOG / "05_spec_curve.md").write_text("\n".join([
    "# 05 — Specification curve (robustness)", "",
    f"{len(sc)} specifications ({len(rf)} reduced forms x first-stage price measures). Unit: rollup x day.",
    f"Headline: eta = {hr.eta:.4f} (beta {hr.beta:.4f}, N = {hr.n_obs}); percentile among DA-intensity specs: {pct:.2f}.", "",
    S.to_markdown(floatfmt=".4g"), "",
    "Significance uses CRV1-by-rollup SEs (15 clusters), which the placebo test shows are too small; treat shares as upper bounds.", "",
    "## Per-rollup (headline spec fitted separately; PPML, own trend, DOW, HC SEs; unit = day)", "",
    het.to_markdown(index=False, floatfmt=".4g")]) + "\n")
print(S.to_string()); print(het.to_string())

# ---- Figure 3: specification curve ------------------------------------------------------------------
INK, INK2, S1C, S2C = "#0b0b0b", "#52514e", "#2a78d6", "#eb6834"
s = sc[sc.activity != "none"].sort_values("eta").reset_index(drop=True)
fig, (a, b) = plt.subplots(2, 1, figsize=(7.2, 6.0), sharex=True, gridspec_kw={"height_ratios": [1.1, 1.5]})
x = np.arange(len(s))
sig = s.p_beta < 0.05
a.vlines(x, s.eta - 1.96 * s.se_eta, s.eta + 1.96 * s.se_eta, color="#d6d5d0", lw=0.6)
a.scatter(x[~sig], s.eta[~sig], s=3, color=S1C, label="β not significant at 5% (CRV1)")
a.scatter(x[sig], s.eta[sig], s=3, color=S2C, label="β significant at 5% (CRV1)")
hx = s.index[s.headline][0]
a.scatter([hx], [s.eta[hx]], s=40, facecolor="none", edgecolor=INK, lw=1.2, zorder=5)
a.annotate("headline", (hx, s.eta[hx]), xytext=(8, 14), textcoords="offset points", fontsize=7.5, color=INK)
a.axhline(0, color=INK2, lw=0.8)
lim = np.nanpercentile(np.abs(np.r_[s.eta - 1.96 * s.se_eta, s.eta + 1.96 * s.se_eta]), 98)
a.set_ylim(-lim, lim)
a.set_ylabel("η (log points per\nmETH/blob)", color=INK2)
a.legend(frameon=False, fontsize=7, loc="upper left")
labels = []
for i, (k, vals) in enumerate([("w", DIMS["w"]), ("trend", DIMS["trend"]), ("activity", ["offset", "control"]),
                               ("estimator", DIMS["estimator"]), ("price", DIMS["price"]), ("dow", [True, False]),
                               ("zerofill", [True, False])]):
    for v in vals:
        labels.append(f"{k}={v}")
        yy = len(labels)
        b.scatter(x[s[k] == v], np.full((s[k] == v).sum(), -yy), s=1.2, color=INK2, marker="|")
b.set_yticks(-np.arange(1, len(labels) + 1))
b.set_yticklabels(labels, fontsize=6.5)
b.set_xlabel(f"specification (sorted by η), N specs = {len(s)}", color=INK2)
for ax_ in (a, b):
    for sp in ("top", "right"):
        ax_.spines[sp].set_visible(False)
fig.text(0.01, 0.005, "DA-intensity specifications only (L2 activity as offset or control). Unit: rollup × day. "
         "Bars: 95% delta-method CI.", fontsize=6.5, color=INK2)
fig.tight_layout(rect=(0, 0.02, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig3_spec_curve.{ext}", dpi=200)

# ---- Figure 4: heterogeneity -------------------------------------------------------------------------
# a rollup with no blobs on one side has no finite per-rollup beta: listed in the note, kept in the pooled fit
degenerate = het[(het.blobs_pre == 0) | (het.blobs_post == 0)].rollup.tolist()
het = het[~het.rollup.isin(degenerate)].reset_index(drop=True)
fig, ax = plt.subplots(figsize=(6.4, 4.2))
y = np.arange(len(het))
ax.hlines(y, het.beta - 1.96 * het.se, het.beta + 1.96 * het.se, color="#b5b4ae", lw=1)
ax.scatter(het.beta, y, s=18, color=S1C, zorder=3)
ax.axvline(0, color=INK2, lw=0.8)
ax.axvline(hr.beta, color=INK, lw=1, ls=(0, (3, 2)))
ax.text(hr.beta, len(het) - 0.2, " pooled", fontsize=7.5, color=INK, va="bottom")
ax.set_yticks(y)
ax.set_yticklabels(het.rollup, fontsize=7.5)
ax.set_xlabel("β: change in blobs per L2 tx at Pectra (log points), 95% CI", color=INK2)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.text(0.01, 0.01, "Unit: day, one PPML per rollup (offset ln L2 txs, own linear trend, DOW), ±28 days, HC SEs.\n"
         f"Not shown (no blobs on one side, beta undefined; in pooled fit): {', '.join(degenerate) or 'none'}.",
         fontsize=6.5, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig4_heterogeneity.{ext}", dpi=200)
print("done")

from common import save_numbers
save_numbers("05_spec_curve", {
    "n_specs_total": len(sc), "n_specs_intensity": int((sc.activity != "none").sum()), "head_pctile": pct,
    **{f"int_{k}": v for k, v in summ(sc[sc.activity != "none"]).items()},
    **{f"off_{k}": v for k, v in summ(sc[sc.activity == "offset"]).items()},
    **{f"tot_{k}": v for k, v in summ(sc[sc.activity == "none"]).items()},
    "het_n": len(het), "het_n_pos": int((het.beta > 0).sum()), "het_mean_beta": het.beta.mean(),
    "het_base_beta": het.set_index("rollup").beta.get("base"), "het_degenerate": ", ".join(degenerate),
})
