"""04 — Headline estimate (PRESPEC.md): Pectra supply shock, DA-intensity semi-elasticity.
Also: placebo-date permutation inference (primary), S1 total demand, S2 Fusaka, S5 log-price version.

Outputs: output/tables/t2_headline.{csv,md}, output/tables/placebo_pectra.csv,
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


# ---- Headline ------------------------------------------------------------------------------------------
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

# ---- S1 total demand (confounded by ETH rally; upper bound on magnitude) --------------------------------
S1 = event_estimate(panel, day, T_PECTRA, w=W, activity="none_all")
show("S1 total demand: no activity offset, all labelled rollups active across window", S1, "rollup x day")
pl1 = []
for tau in days:
    r = event_estimate(panel, day, tau, w=W, activity="none_all", twoway=False)
    pl1.append(r["beta"])
pl1 = np.array(pl1)
p_beta_s1 = (np.abs(pl1) >= abs(S1["beta"])).mean()
log.extend([f"S1 placebo-date permutation ({len(pl1)} dates, same rule): two-sided p = {p_beta_s1:.3f}; "
            f"placebo beta sd {pl1.std():.4f}.", ""])
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

# ---- tables & figure -----------------------------------------------------------------------------------
tab = pd.DataFrame([{"spec": "Headline (PRESPEC)", **H}, {"spec": "S1 total demand", **S1}] +
                   ([{"spec": "S2 Fusaka +-5d", **S2}] if S2 else []))
tab["perm_p_beta"] = [p_beta] + [np.nan] * (len(tab) - 1)
tab["usd_per_meth_pre"] = tab.ethusd_pre / 1000
tab.to_csv(TAB / "t2_headline.csv", index=False)
cols = ["spec", "beta", "se_beta_rollup", "se_beta_twoway", "perm_p_beta", "pi", "se_pi", "eta", "se_eta",
        "eps_at_pre_mean", "p_pre", "p_post", "n_obs", "n_rollups", "n_days"]
(TAB / "t2_headline.md").write_text(
    "Table 2 — Pectra supply shock. beta: PPML coefficient on Post (log points), rollup FE, rollup linear trends, "
    "DOW FE. pi: first-stage change in mean blob base fee (mETH per blob; 1 blob = 131,072 blob gas). eta = beta/pi "
    "(log points per mETH/blob). Unit: rollup x day. perm_p: placebo-date permutation p-value.\n\n"
    + tab[cols].to_markdown(index=False, floatfmt=".4g") + "\n")
(LOG / "04_headline_pectra.md").write_text("\n".join(log) + "\n")

INK2, S1C = "#52514e", "#2a78d6"
fig, ax = plt.subplots(figsize=(6.4, 3.2))
ax.hist(pl.beta, bins=40, color=S1C, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.axvline(H["beta"], color="#0b0b0b", lw=1.4)
ax.text(H["beta"], ax.get_ylim()[1] * 0.95, f"  Pectra  β = {H['beta']:.3f}\n  permutation p = {p_beta:.3f}",
        va="top", fontsize=8, color="#0b0b0b")
ax.set_xlabel("β (PPML coefficient on Post, log points)", color=INK2)
ax.set_ylabel("placebo dates", color=INK2)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.text(0.01, 0.01, f"{len(pl)} placebo break dates in the EIP-4844 regime, identical estimator and ±{W}-day window.",
         fontsize=7, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig2_placebo.{ext}", dpi=200)
print("done")

from common import save_numbers
save_numbers("04_headline", {
    **{f"head_{k}": v for k, v in H.items() if k != "rollups"},
    "head_ci_eta_lo": H["eta"] - 1.96 * H["se_eta"], "head_ci_eta_hi": H["eta"] + 1.96 * H["se_eta"],
    "head_ci_eps_lo": (H["eta"] - 1.96 * H["se_eta"]) * H["p_pre"], "head_ci_eps_hi": (H["eta"] + 1.96 * H["se_eta"]) * H["p_pre"],
    "head_usd_pre": H["p_pre"] * H["ethusd_pre"] / 1000,
    "perm_p_beta": p_beta, "perm_p_eta": p_eta, "n_placebo": len(pl), "placebo_sd_beta": pl.beta.std(),
    "placebo_lo": str(pl.tau.min()), "placebo_hi": str(pl.tau.max()),
    **{f"s1_{k}": v for k, v in S1.items() if k != "rollups"}, "s1_perm_p": p_beta_s1, "s1b_beta": S1b["beta"], "unk_share_window": unk_share,
    **({f"s2_{k}": v for k, v in S2.items() if k != "rollups"} if S2 else {}),
    **{f"s5_elast_floor_{int(r.hypothetical_floor_wei)}": r.log_price_elasticity for r in S5.itertuples()},
})
