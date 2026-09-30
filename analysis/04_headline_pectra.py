"""04 — Main estimates: Pectra supply shock.
Column 1 (primary, DECISIONS D-34): unnormalized blob purchases of the 15 rollups with L2 activity data. Column 2: the
same on all labelled rollups. Column 3: blobs per L2 transaction, the intensity margin named as the headline in
PRESPEC; its denominator responds to the treatment, so it is reported as a descriptive intensity measure.
Inference: placebo-date permutation and placebo-quantile (Conley-Taber) intervals (reported, PRESPEC 4), wild cluster
restricted score bootstrap (D-29), clustered and two-way SEs. Minimum detectable effect at 80% power from the placebo
distribution (D-35); largest increase not ruled out (D-27). Also S2 Fusaka and S5 log price.

Outputs: output/tables/t2_main.{csv,md}, output/tables/placebo_pectra.csv,
         output/figures/fig2_placebo.{pdf,png}, output/logs/04_headline_pectra.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import TAB, FIG, LOG, DATA, con
from est import load, event_estimate, window_sample, reduced_form

T_PECTRA, T_FUSAKA = pd.Timestamp("2025-05-07"), pd.Timestamp("2025-12-03")
W = 28
EIP4844_LO, EIP4844_HI = pd.Timestamp("2024-03-14"), pd.Timestamp("2025-12-02")

panel, day = load()
log = ["# 04 — Headline: Pectra supply shock", ""]


def show(title, r, unit):
    log.extend([f"## {title}", "", f"Unit of observation: {unit}. N = {r['n_obs']:,} ({r['n_rollups']} rollups x "
                f"{r['n_days']} days; {r['n_zero']} zero-filled rollup-days). First stage N = {r['n_days_fs']} days.", "",
                f"- beta (Post, log points) = {r['beta']:.4f}; SE CRV1(rollup) = {r['se_beta_rollup']:.4f} "
                f"(p = {r['p_beta_rollup']:.3g}); SE two-way(rollup, day) = {r.get('se_beta_twoway', np.nan):.4f}",
                f"- pi (Post, mETH/blob) = {r['pi']:.4f}; Newey-West SE = {r['se_pi']:.4f}; mean price pre = "
                f"{r['p_pre']:.4f}, post = {r['p_post']:.6f} mETH/blob (ETH/USD pre-window mean {r['ethusd_pre']:,.0f})",
                f"- eta = beta/pi = {r['eta']:.4f} log points per mETH/blob (delta-method SE {r['se_eta']:.4f}); "
                f"point elasticity at pre-window mean price = {r['eps_at_pre_mean']:.4f}",
                f"- rollups: {r['rollups']}", ""])
    print(f"\n== {title}\n" + "\n".join(log[-6:-1]))


# ---- Intensity specification (the PRESPEC headline; column 3 after D-34) -------------------------------
H = event_estimate(panel, day, T_PECTRA, w=W)
show("Headline (PRESPEC): PPML, offset ln(L2 txs), rollup FE + rollup linear trends + DOW, +-28 days", H,
     "rollup x day")

# ---- Placebo-date permutation (primary inference) ------------------------------------------------------
days = day.date[(day.date - pd.Timedelta(days=W) >= EIP4844_LO) & (day.date + pd.Timedelta(days=W) <= EIP4844_HI)]
days = days[(days + pd.Timedelta(days=W) < T_PECTRA) | (days - pd.Timedelta(days=W) > T_PECTRA)]
rows = []
for tau in days:
    try:
        r = event_estimate(panel, day, tau, w=W, twoway=False)
    except Exception as e:           # too few rollups with txcount early in the sample
        continue
    if r["n_rollups"] >= 5:
        rows.append(dict(tau=tau.date(), beta=r["beta"], pi=r["pi"], eta=r["eta"], n_rollups=r["n_rollups"], n_obs=r["n_obs"]))
pl = pd.DataFrame(rows)
pl.to_csv(TAB / "placebo_pectra.csv", index=False)
p_beta = (np.abs(pl.beta) >= abs(H["beta"])).mean()
p_eta = (np.abs(pl.eta) >= abs(H["eta"])).mean()
rank = (pl.beta >= H["beta"]).mean()
log.extend(["## Placebo-date permutation (primary inference)", "",
            f"{len(pl)} placebo dates in the EIP-4844 regime ({pl.tau.min()} .. {pl.tau.max()}), each with its own "
            f"+-{W}-day window excluding Pectra; >= 5 eligible rollups required. Rollups per placebo: "
            f"{pl.n_rollups.min()}-{pl.n_rollups.max()}.", "",
            f"- two-sided permutation p for beta: {p_beta:.3f}  (share of placebo beta >= estimate: {rank:.3f})",
            f"- two-sided permutation p for eta:  {p_eta:.3f}",
            f"- placebo beta: mean {pl.beta.mean():.4f}, sd {pl.beta.std():.4f}, 5%/95% {pl.beta.quantile(.05):.4f}/{pl.beta.quantile(.95):.4f}",
            f"- placebo pi (mETH/blob): mean {pl.pi.mean():.4f}, sd {pl.pi.std():.4f}", ""])
print("\n".join(log[-7:]))

# ---- Primary: unnormalized blob purchases (D-28, D-34) ---------------------------------------------------
L15 = event_estimate(panel, day, T_PECTRA, w=W, activity="none")          # same 15 rollups, no L2-activity term
show("Levels, headline sample: PPML blobs, no normalization, rollup FE + trends + DOW", L15, "rollup x day")
S1 = event_estimate(panel, day, T_PECTRA, w=W, activity="none_all")       # all labelled rollups active in window
show("Levels, all labelled rollups (PRESPEC S1)", S1, "rollup x day")
pl15, pl1 = [], []
for tau in days:
    try:
        pl15.append(event_estimate(panel, day, tau, w=W, activity="none", twoway=False)["beta"])
    except Exception:
        pass
    pl1.append(event_estimate(panel, day, tau, w=W, activity="none_all", twoway=False)["beta"])
pl15, pl1 = np.array(pl15), np.array(pl1)
p_beta_l15 = (np.abs(pl15) >= abs(L15["beta"])).mean()
p_beta_s1 = (np.abs(pl1) >= abs(S1["beta"])).mean()
log.extend([f"Placebo permutation, levels 15-rollup sample ({len(pl15)} dates): p = {p_beta_l15:.3f}; sd {pl15.std():.4f}.",
            f"Placebo permutation, levels all rollups ({len(pl1)} dates): p = {p_beta_s1:.3f}; sd {pl1.std():.4f}.", ""])
# S1b: 'unknown' added as one extra unit (DECISIONS D-06)
c = con()
unk = c.sql(f"SELECT date, n_blobs FROM '{DATA / 'rollup_day_panel.parquet'}' WHERE is_unknown").df()
unk["date"] = pd.to_datetime(unk.date)
d = window_sample(panel, T_PECTRA, W, require_txcount=False)
u = d.drop_duplicates("date")[["date", "t", "t2", "post", "dow", "day_id"]].merge(unk, on="date", how="left").fillna({"n_blobs": 0})
u = u.assign(rollup="unknown", zero_filled=u.n_blobs == 0)
S1b = reduced_form(pd.concat([d, u], ignore_index=True), activity="none")
unk_share = u.n_blobs.sum() / (u.n_blobs.sum() + d.n_blobs.sum())
log.extend([f"S1b with 'unknown' as one extra unit: beta = {S1b['beta']:.4f} (SE rollup {S1b['se_beta_rollup']:.4f}), "
            f"N = {S1b['n_obs']:,}, eta = {S1b['beta'] / S1['pi']:.4f}. 'unknown' share of window blobs = {unk_share:.4f}.", ""])

# ---- S2 Fusaka (+-5 days; BPO1 follows 6 days later) ---------------------------------------------------
try:
    S2 = event_estimate(panel, day, T_FUSAKA, w=5)
    show("S2 Fusaka reserve introduction, +-5 days (low power)", S2, "rollup x day")
except Exception as e:
    log.extend(["## S2 Fusaka", "", f"not estimable: {e}", ""])
    S2 = None

# ---- S5 log-price version: dependence on the floor level ------------------------------------------------
lo, hi = T_PECTRA - pd.Timedelta(days=W), T_PECTRA + pd.Timedelta(days=W)
s = day[(day.date >= lo) & (day.date <= hi) & (day.date != T_PECTRA)]
wei = s.p_mean_meth * 1e15 / 131072                              # back to wei per blob gas
rows5 = []
for floor in (1, 1e3, 1e6):
    lp = np.log(np.maximum(wei, floor))
    dlp = lp[s.date > T_PECTRA].mean() - lp[s.date < T_PECTRA].mean()
    rows5.append(dict(hypothetical_floor_wei=floor, d_log_price=dlp, log_price_elasticity=H["beta"] / dlp))
S5 = pd.DataFrame(rows5)
log.extend(["## S5 log-price elasticity and the floor level", "",
            "Same beta; the log-price change is recomputed as if the floor were F wei. A constant-elasticity estimate "
            "identified off a move to the floor is set by F (DECISIONS D-10, D-11).", "", S5.to_markdown(index=False, floatfmt=".4g"), ""])

# ---- Intervals: placebo-quantile (Conley-Taber), wild score bootstrap, CRV1 (D-27, D-29) ---------------------
from est import wild_ci
def ct_interval(beta, placebo):
    """Invert the placebo distribution of estimation error: beta - q97.5 .. beta - q2.5 (Conley and Taber 2011)."""
    q_lo, q_hi = np.quantile(placebo, [0.025, 0.975])
    return beta - q_hi, beta - q_lo
cols3 = {"(1) Blob purchases, 15 rollups [primary]": (L15, pl15, dict(offset=False), True),
         "(2) Blob purchases, all labelled rollups": (S1, pl1, dict(offset=False), False),
         "(3) Blobs per L2 transaction [intensity]": (H, pl.beta.to_numpy(), dict(offset=True), True)}
rows_t = []
for name, (r, plc, kw, txreq) in cols3.items():
    dd = window_sample(panel, T_PECTRA, W, require_txcount=txreq)
    w_lo, w_hi, _, _ = wild_ci(dd, r["beta"], trend="linear", dow=True, half_width=0.35, step=0.0025, **kw)
    c_lo, c_hi = ct_interval(r["beta"], plc)
    perm_p = (np.abs(plc) >= abs(r["beta"])).mean()
    dlp = np.log(np.maximum(wei, 1))[s.date > T_PECTRA].mean() - np.log(np.maximum(wei, 1))[s.date < T_PECTRA].mean()
    rows_t.append(dict(spec=name, beta=r["beta"], se_crv1=r["se_beta_rollup"], se_twoway=r["se_beta_twoway"],
                       ci_crv1_lo=r["beta"] - 1.96 * r["se_beta_rollup"], ci_crv1_hi=r["beta"] + 1.96 * r["se_beta_rollup"],
                       ci_wild_lo=w_lo, ci_wild_hi=w_hi, ci_placebo_lo=c_lo, ci_placebo_hi=c_hi, perm_p=perm_p,
                       placebo_sd=np.std(plc, ddof=1),
                       n_placebo=len(plc), pi=r["pi"], se_pi=r["se_pi"], eta=r["eta"],
                       eta_placebo_lo=c_hi / r["pi"], eta_placebo_hi=c_lo / r["pi"],
                       eps_pre=r["eps_at_pre_mean"], eps_placebo_lo=c_hi / r["pi"] * r["p_pre"],
                       eps_placebo_hi=c_lo / r["pi"] * r["p_pre"], log_price_elasticity=r["beta"] / dlp,
                       n_obs=r["n_obs"], n_rollups=r["n_rollups"], n_days=r["n_days"], p_pre=r["p_pre"], p_post=r["p_post"]))
T2 = pd.DataFrame(rows_t)
from est import score_shares
_sh = {name: score_shares(window_sample(panel, T_PECTRA, W, require_txcount=txreq), offset=kw["offset"])
       for name, (r, plc, kw, txreq) in cols3.items()}
T2["top_cluster"] = [_sh[n].index[0] for n in T2.spec]
T2["top_cluster_score_share"] = [_sh[n].iloc[0] for n in T2.spec]
T2["mde_pct_placebo"] = 100 * (np.exp(T2.ci_placebo_hi) - 1)     # largest increase in blobs not ruled out
# minimum detectable effect: 80% power, 5% two-sided test, placebo SD as the standard error of the design
T2["mde80_logpts"] = (1.96 + 0.8416) * T2.placebo_sd
T2["mde80_pct"] = 100 * (np.exp(T2.mde80_logpts) - 1)
T2["mde_pct_wild"] = 100 * (np.exp(T2.ci_wild_hi) - 1)
T2["mde_pct_crv1"] = 100 * (np.exp(T2.ci_crv1_hi) - 1)
T2.to_csv(TAB / "t2_main.csv", index=False)
fmt = lambda a, b: f"[{a:.3f}, {b:.3f}]"
view = pd.DataFrame({
    "beta (Post, log points)": T2.beta.map("{:.3f}".format).to_numpy(),
    "SE, CRV1 by rollup": T2.se_crv1.map("{:.3f}".format).to_numpy(),
    "SE, two-way rollup and day": T2.se_twoway.map("{:.3f}".format).to_numpy(),
    "95% CI, placebo quantiles [reported]": [fmt(a, b) for a, b in zip(T2.ci_placebo_lo, T2.ci_placebo_hi)],
    "95% CI, wild cluster score bootstrap": [fmt(a, b) for a, b in zip(T2.ci_wild_lo, T2.ci_wild_hi)],
    "95% CI, CRV1": [fmt(a, b) for a, b in zip(T2.ci_crv1_lo, T2.ci_crv1_hi)],
    "placebo permutation p": T2.perm_p.map("{:.3f}".format).to_numpy(),
    "first stage pi (mETH/blob)": T2.pi.map("{:.3f}".format).to_numpy(),
    "eta = beta/pi (per mETH/blob)": T2.eta.map("{:.3f}".format).to_numpy(),
    "elasticity at pre-shock price": T2.eps_pre.map("{:.3f}".format).to_numpy(),
    "largest increase not ruled out (placebo CI)": T2.mde_pct_placebo.map("{:.1f}%".format).to_numpy(),
    "minimum detectable effect, 80% power": T2.mde80_pct.map("{:.1f}%".format).to_numpy(),
    "log-price elasticity (floor-dependent, D-10)": T2.log_price_elasticity.map("{:.4f}".format).to_numpy(),
    "N (rollup-days)": T2.n_obs.map("{:,}".format).to_numpy(), "rollups": T2.n_rollups.to_numpy(), "days": T2.n_days.to_numpy()},
    index=T2.spec).T
(TAB / "t2_main.md").write_text(
    "Table 2. Pectra supply shock, 2025-04-09 to 2025-06-04 (fork day excluded). Unit: rollup x day. PPML with rollup FE, "
    "rollup-specific linear trends, day-of-week FE. Column 3 adds ln(L2 transactions) as an offset (blobs per L2 "
    "transaction). Reported interval: placebo quantiles (Conley and Taber 2011) from the same estimator at every placebo "
    "break date in the EIP-4844 regime. Wild bootstrap: restricted score bootstrap (Kline and Santos 2012), Rademacher "
    "weights, clusters = rollups (all 2^15 sign vectors in columns 1 and 3; 99,999 draws in column 2). Price in mETH per blob "
    "(1 blob = 131,072 blob gas).\n\n" + view.to_markdown() + "\n")
log.extend(["## Main table", "", view.to_markdown(), ""])

# effective identifying variation (D-27): the first stage comes only from the congested pre-window
pre_days = s[s.date < T_PECTRA]
all4844 = day[day.regime.isin(["dencun", "pectra"])]
feesd = c.sql(f"SELECT date, blob_fee_eth FROM '{DATA / 'day_panel.parquet'}'").df()
feesd["date"] = pd.to_datetime(feesd.date)
a = all4844.merge(feesd, on="date")
above = a.p_mean_meth > pre_days.p_mean_meth.max()
EV = dict(pre_p_min=pre_days.p_mean_meth.min(), pre_p_max=pre_days.p_mean_meth.max(), pre_p_mean=pre_days.p_mean_meth.mean(),
          share_days_above=above.mean(), share_fees_above=a[above].blob_fee_eth.sum() / a.blob_fee_eth.sum(),
          n_days_above=int(above.sum()), sd_p_congested=a[(a.date >= "2024-10-01") & (a.date < "2025-05-07")].p_mean_meth.std(),
          sd_p_rest=a[(a.date < "2024-10-01") | (a.date >= "2025-05-07")].p_mean_meth.std())
log.extend(["## Range of identifying variation (D-27)", "",
            f"Pre-window daily mean price {EV['pre_p_min']:.3f}..{EV['pre_p_max']:.3f} mETH/blob (mean {EV['pre_p_mean']:.3f}); "
            f"post-window ~0. EIP-4844 days with a higher daily price than any pre-window day: {EV['n_days_above']} "
            f"({EV['share_days_above']:.1%} of days, {EV['share_fees_above']:.1%} of fees). SD of daily price: "
            f"{EV['sd_p_congested']:.3f} (2024-10-01..2025-05-06) vs {EV['sd_p_rest']:.4f} (rest of EIP-4844 regime).", ""])

(LOG / "04_headline_pectra.md").write_text("\n".join(log) + "\n")

INK2, S1C = "#52514e", "#2a78d6"
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
for ax, (plc, b, title) in zip(axs, [(pl15, L15["beta"], "Blob purchases (primary)"),
                                     (pl.beta.to_numpy(), H["beta"], "Blobs per L2 transaction")]):
    ax.hist(plc, bins=40, color=S1C, alpha=0.85, edgecolor="white", linewidth=0.6)
    ax.axvline(b, color="#0b0b0b", lw=1.4)
    ax.text(b, ax.get_ylim()[1] * 0.95, f" Pectra\n β = {b:.3f}", va="top", fontsize=7.5, color="#0b0b0b")
    ax.set_title(title, fontsize=8.5, color=INK2)
    ax.set_xlabel("β (PPML coefficient on Post, log points)", color=INK2, fontsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
axs[0].set_ylabel("placebo dates", color=INK2)
fig.text(0.01, 0.01, f"{len(pl)} placebo break dates in the EIP-4844 regime, identical estimator and ±{W}-day window.",
         fontsize=7, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig2_placebo.{ext}", dpi=200)
print("done")

from common import save_numbers
t2 = T2.set_index(pd.Index(["l15", "lall", "head"]))
save_numbers("04_headline", {
    **{f"head_{k}": v for k, v in H.items() if k != "rollups"},
    **{f"l15_{k}": v for k, v in L15.items() if k != "rollups"},
    **{f"s1_{k}": v for k, v in S1.items() if k != "rollups"},
    **{f"{i}_{k}": t2.loc[i, k] for i in t2.index for k in t2.columns if k != "spec"},
    "head_usd_pre": H["p_pre"] * H["ethusd_pre"] / 1000,
    "perm_p_beta": p_beta, "perm_p_eta": p_eta, "n_placebo": len(pl), "placebo_sd_beta": pl.beta.std(),
    "placebo_sd_l15": np.std(pl15, ddof=1),
    "placebo_lo": str(pl.tau.min()), "placebo_hi": str(pl.tau.max()),
    "s1_perm_p": p_beta_s1, "l15_perm_p": p_beta_l15, "s1b_beta": S1b["beta"], "unk_share_window": unk_share,
    **({f"s2_{k}": v for k, v in S2.items() if k != "rollups"} if S2 else {}),
    **{f"s5_elast_floor_{int(r.hypothetical_floor_wei)}": r.log_price_elasticity for r in S5.itertuples()},
    **{f"ev_{k}": v for k, v in EV.items()},
})
