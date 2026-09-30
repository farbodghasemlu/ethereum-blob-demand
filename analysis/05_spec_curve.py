"""05 — Specification curves and per-rollup heterogeneity for the Pectra design (PRESPEC.md §6; DECISIONS D-34).

Reduced forms are fitted once per (window, trend, activity, estimator, dow, zerofill) and first stages once per
(window, price, trend, dow); eta = beta/pi for every combination. ols_log uses positive days only, so its zerofill
variants coincide and are kept once. SEs are clustered by rollup (15 clusters; see PRESPEC §4).

Two families: the primary outcome, unnormalized blob purchases (activity = none), and the per-transaction
intensity (L2 activity as offset or control).

Outputs: output/tables/spec_curve.csv, output/tables/heterogeneity_pectra.csv,
         output/figures/fig3_spec_curve.{pdf,png} (primary), figA1_spec_curve_intensity.{pdf,png},
         output/figures/fig4_heterogeneity.{pdf,png}, output/logs/05_spec_curve.md
"""
import itertools
import numpy as np
import pandas as pd
import pyfixest as pf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import TAB, FIG, LOG, save_numbers
from est import load, window_sample, reduced_form, first_stage

T0 = pd.Timestamp("2025-05-07")
BASE = dict(w=28, trend="linear", estimator="ppml", price="mean", dow=True, zerofill=True)
PRIMARY = dict(BASE, activity="none")
INTENSITY = dict(BASE, activity="offset")
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
sc["primary"] = np.all([sc[k] == v for k, v in PRIMARY.items()], axis=0)
sc["intensity_spec"] = np.all([sc[k] == v for k, v in INTENSITY.items()], axis=0)
sc.to_csv(TAB / "spec_curve.csv", index=False)


def summ(s):
    return dict(n_specs=len(s), share_eta_neg=(s.eta < 0).mean(), share_beta_sig5=(s.p_beta < 0.05).mean(),
                eta_p05=s.eta.quantile(.05), eta_median=s.eta.median(), eta_p95=s.eta.quantile(.95),
                eps_p05=s.eps.quantile(.05), eps_median=s.eps.median(), eps_p95=s.eps.quantile(.95),
                share_eps_pos=(s.eps > 0).mean(), share_elastic=(s.eps.abs() > 1).mean(),
                N_min=s.n_obs.min(), N_max=s.n_obs.max())


fam = {"primary": sc[sc.activity == "none"], "intensity": sc[sc.activity != "none"], "offset": sc[sc.activity == "offset"]}
S = pd.DataFrame({k: summ(v) for k, v in fam.items()}).T
prim, ints = sc[sc.primary].iloc[0], sc[sc.intensity_spec].iloc[0]
prim_pct = (fam["primary"].eta < prim.eta).mean()
int_pct = (fam["intensity"].eta < ints.eta).mean()
by_w = fam["primary"].groupby("w").eps.apply(lambda s: (s > 0).mean())

# ---- per-rollup estimates at the main window, one rollup at a time -----------------------------------------
d = samples[28]
het = []
for r_, g in d.groupby("rollup"):
    lv = pf.fepois("n_blobs ~ post + t + C(dow)", data=g, vcov="hetero")
    it = pf.fepois("n_blobs ~ post + t + C(dow)", data=g, offset="lT", vcov="hetero")
    het.append(dict(rollup=r_, beta=lv.coef()["post"], se=lv.se()["post"], beta_intensity=it.coef()["post"],
                    se_intensity=it.se()["post"], n_obs=int(lv._N), blobs_pre=g[g.t < 0].n_blobs.sum(),
                    blobs_post=g[g.t > 0].n_blobs.sum(),
                    l2tx_growth=np.log(g[g.t > 0].l2_txcount.mean() / g[g.t < 0].l2_txcount.mean())))
het = pd.DataFrame(het).sort_values("beta")
het.to_csv(TAB / "heterogeneity_pectra.csv", index=False)
degenerate = het[(het.blobs_pre == 0) | (het.blobs_post == 0)].rollup.tolist()
hd = het[~het.rollup.isin(degenerate)].reset_index(drop=True)

(LOG / "05_spec_curve.md").write_text("\n".join([
    "# 05 — Specification curves", "",
    f"{len(sc)} specifications ({len(rf)} reduced forms x three first-stage price measures). Unit: rollup x day.",
    f"Primary (unnormalized): eta = {prim.eta:.4f}, beta {prim.beta:.4f}, N = {prim.n_obs}; less elastic than "
    f"{prim_pct:.0%} of its family. Intensity spec: eta = {ints.eta:.4f}; less elastic than {int_pct:.0%} of its family.", "",
    S.to_markdown(floatfmt=".4g"), "",
    "Share of primary-family specifications with the wrong sign, by window: " + ", ".join(f"{k} days {v:.0%}" for k, v in by_w.items()), "",
    "Significance uses SEs clustered by rollup, which the placebo test shows are too small.", "",
    "## Per-rollup estimates (PPML, own trend, day of week, HC SEs; unit = day)", "",
    het.to_markdown(index=False, floatfmt=".4g")]) + "\n")
print(S.to_string())

# ---- figures ------------------------------------------------------------------------------------------------
INK, INK2, S1C, S2C = "#0b0b0b", "#52514e", "#2a78d6", "#eb6834"


def curve(s, marked, mark_label, fname, note, activity_levels):
    s = s.sort_values("eta").reset_index(drop=True)
    fig, (a, b) = plt.subplots(2, 1, figsize=(7.2, 6.0), sharex=True, gridspec_kw={"height_ratios": [1.1, 1.5]})
    x = np.arange(len(s))
    sig = (s.p_beta < 0.05).to_numpy()
    a.vlines(x, s.eta - 1.96 * s.se_eta, s.eta + 1.96 * s.se_eta, color="#d6d5d0", lw=0.6)
    a.scatter(x[~sig], s.eta[~sig], s=3, color=S1C, label="β not significant at 5% (clustered SE)")
    a.scatter(x[sig], s.eta[sig], s=3, color=S2C, label="β significant at 5% (clustered SE)")
    hx = s.index[s[marked]][0]
    a.scatter([hx], [s.eta[hx]], s=40, facecolor="none", edgecolor=INK, lw=1.2, zorder=5)
    a.annotate(mark_label, (hx, s.eta[hx]), xytext=(8, 14), textcoords="offset points", fontsize=7.5, color=INK)
    a.axhline(0, color=INK2, lw=0.8)
    lim = np.nanpercentile(np.abs(np.r_[s.eta - 1.96 * s.se_eta, s.eta + 1.96 * s.se_eta]), 98)
    a.set_ylim(-lim, lim)
    a.set_ylabel("η (log points per\nmETH/blob)", color=INK2)
    a.legend(frameon=False, fontsize=7, loc="upper left")
    labels = []
    for k, vals in [("w", DIMS["w"]), ("trend", DIMS["trend"]), ("activity", activity_levels),
                    ("estimator", DIMS["estimator"]), ("price", DIMS["price"]), ("dow", [True, False]),
                    ("zerofill", [True, False])]:
        if len(vals) < 2:
            continue
        for v in vals:
            labels.append(f"{k}={v}")
            b.scatter(x[s[k] == v], np.full((s[k] == v).sum(), -len(labels)), s=1.2, color=INK2, marker="|")
    b.set_yticks(-np.arange(1, len(labels) + 1))
    b.set_yticklabels(labels, fontsize=6.5)
    b.set_xlabel(f"specification (sorted by η), N specs = {len(s)}", color=INK2)
    for ax_ in (a, b):
        for sp in ("top", "right"):
            ax_.spines[sp].set_visible(False)
    fig.text(0.01, 0.005, note, fontsize=6.5, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{fname}.{ext}", dpi=200)


curve(fam["primary"], "primary", "primary", "fig3_spec_curve", "Unnormalized blob purchases. Unit: rollup × day. "
      "Bars: 95% delta-method CI.", ["none"])
curve(fam["intensity"], "intensity_spec", "intensity spec", "figA1_spec_curve_intensity",
      "Blobs per L2 transaction (L2 activity as offset or control). Unit: rollup × day. Bars: 95% delta-method CI.",
      ["offset", "control"])

fig, ax = plt.subplots(figsize=(6.4, 4.2))
y = np.arange(len(hd))
ax.hlines(y, hd.beta - 1.96 * hd.se, hd.beta + 1.96 * hd.se, color="#b5b4ae", lw=1)
ax.scatter(hd.beta, y, s=18, color=S1C, zorder=3)
ax.axvline(0, color=INK2, lw=0.8)
ax.axvline(prim.beta, color=INK, lw=1, ls=(0, (3, 2)))
ax.text(prim.beta, len(hd) - 0.2, " pooled", fontsize=7.5, color=INK, va="bottom")
ax.set_yticks(y)
ax.set_yticklabels(hd.rollup, fontsize=7.5)
ax.set_xlabel("β: change in blob purchases at Pectra (log points), 95% CI", color=INK2)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.text(0.01, 0.01, "Unit: day, one PPML per rollup (own linear trend, day of week), ±28 days, HC SEs.\n"
         f"Not shown (no blobs on one side, β undefined; in pooled fit): {', '.join(degenerate) or 'none'}.",
         fontsize=6.5, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig4_heterogeneity.{ext}", dpi=200)

save_numbers("05_spec_curve", {
    "n_specs_total": len(sc), "prim_pctile": prim_pct, "int_pctile": int_pct,
    **{f"prim_{k}": v for k, v in summ(fam["primary"]).items()},
    **{f"int_{k}": v for k, v in summ(fam["intensity"]).items()},
    **{f"off_{k}": v for k, v in summ(fam["offset"]).items()},
    "prim_wrongsign_w14": by_w.get(14), "prim_wrongsign_other": (fam["primary"][fam["primary"].w != 14].eps > 0).mean(),
    "het_n": len(hd), "het_n_pos": int((hd.beta > 0).sum()), "het_mean_beta": hd.beta.mean(),
    "het_base_beta": hd.set_index("rollup").beta.get("base"), "het_degenerate": ", ".join(degenerate),
    "het_int_n_pos": int((hd.beta_intensity > 0).sum()), "het_int_mean_beta": hd.beta_intensity.mean(),
})
