"""Event-design estimator shared by the headline (04), specification curve (05) and placebo inference.
Implements PRESPEC.md §2: reduced form PPML/OLS at rollup x day, first stage OLS at day level, eta = beta/pi.
"""
import warnings
import numpy as np
import pandas as pd
import pyfixest as pf
import statsmodels.api as sm
from common import DATA

warnings.filterwarnings("ignore")

PRICE_COL = {"mean": "p_mean_meth", "median": "p_median_meth", "paid": "p_paid_meth"}


def load():
    """Estimation panel (rollup x day, already an aggregate) and the day panel with prices in mETH/blob."""
    panel = pd.read_parquet(DATA / "est_panel.parquet")
    panel["date"] = pd.to_datetime(panel["date"])
    for c in ("first_post", "last_post"):
        panel[c] = pd.to_datetime(panel[c])
    day = (panel.drop_duplicates("date")[["date", "p_mean_meth", "p_median_meth", "p_paid_meth", "eth_usd",
                                         "share_blocks_at_floor", "regime"]]
           .sort_values("date").reset_index(drop=True))
    return panel, day


def window_sample(panel, t0, w, require_txcount=True):
    """PRESPEC §3: labelled rollups active across the whole window; optionally txcount on every window day."""
    lo, hi = t0 - pd.Timedelta(days=w), t0 + pd.Timedelta(days=w)
    d = panel[(panel.date >= lo) & (panel.date <= hi) & (panel.date != t0)]
    d = d[(d.first_post <= lo) & (d.last_post >= hi)]
    if require_txcount:
        ok = d.groupby("rollup").l2_txcount.apply(lambda s: s.notna().all() and (s > 0).all())
        d = d[d.rollup.isin(ok[ok].index)]
    d = d.copy()
    d["t"] = (d.date - t0).dt.days
    d["t2"] = d.t ** 2
    d["post"] = (d.t > 0).astype(int)
    d["dow"] = d.date.dt.dayofweek
    d["day_id"] = d.date.dt.strftime("%Y%m%d").astype(int)
    d["lT"] = np.log(d.l2_txcount) if require_txcount else np.nan
    return d


def reduced_form(d, trend="linear", activity="offset", estimator="ppml", dow=True, zerofill=True, twoway=True):
    if not zerofill:
        d = d[~d.zero_filled]
    rhs = ["post"]
    if trend in ("linear", "quadratic"):
        rhs.append("C(rollup):t")
    if trend == "quadratic":
        rhs.append("C(rollup):t2")
    if dow:
        rhs.append("C(dow)")
    if activity == "control":
        rhs.append("lT")
    offset = activity == "offset"
    if estimator == "ppml":
        fml = f"n_blobs ~ {' + '.join(rhs)} | rollup"
        fit = lambda v: pf.fepois(fml, data=d, offset="lT" if offset else None, vcov=v)
    else:
        d = d[d.n_blobs > 0].copy() if estimator == "ols_log" else d.copy()
        d["y"] = np.log(d.n_blobs) if estimator == "ols_log" else np.log1p(d.n_blobs)
        if offset:
            d["y"] = d.y - d.lT
        fml = f"y ~ {' + '.join(rhs)} | rollup"
        fit = lambda v: pf.feols(fml, data=d, vcov=v)
    m = fit({"CRV1": "rollup"})
    out = dict(beta=m.coef()["post"], se_beta_rollup=m.se()["post"], p_beta_rollup=m.pvalue()["post"],
               n_obs=int(m._N), n_rollups=d.rollup.nunique(), n_days=d.date.nunique(), n_zero=int((d.n_blobs == 0).sum()))
    if twoway:
        m2 = fit({"CRV1": "rollup+day_id"})
        out["se_beta_twoway"] = m2.se()["post"]
    return out


def _rhs_controls(trend, dow):
    rhs = []
    if trend in ("linear", "quadratic"):
        rhs.append("C(rollup):t")
    if trend == "quadratic":
        rhs.append("C(rollup):t2")
    if dow:
        rhs.append("C(dow)")
    return rhs


def wild_score_test(d, beta0, trend="linear", offset=True, dow=True, draws=None, seed=0):
    """Wild cluster restricted score bootstrap for the PPML coefficient on `post` (Kline and Santos 2012), clusters =
    rollups. Imposes beta = beta0, forms the efficient score for beta from the partialled-out regressor, and compares
    its studentised value with the Rademacher-perturbed distribution. With G <= 16 clusters all 2^G sign vectors are
    enumerated; otherwise `draws` random vectors. Returns the two-sided bootstrap p-value."""
    d = d.copy()
    d["off0"] = beta0 * d.post + (d.lT if offset else 0.0)
    ctrl = _rhs_controls(trend, dow)
    fml = f"n_blobs ~ {' + '.join(ctrl) if ctrl else '1'} | rollup"
    mr = pf.fepois(fml, data=d, offset="off0", vcov="iid")
    mu = np.asarray(mr.predict(type="response"), dtype=float)
    d["wt"] = mu
    # partial out the restricted model's regressors from `post` with Poisson weights mu
    xr = pf.feols(f"post ~ {' + '.join(ctrl) if ctrl else '1'} | rollup", data=d, weights="wt")
    xt = np.asarray(xr.resid(), dtype=float)
    s_i = xt * (d.n_blobs.to_numpy(dtype=float) - mu)
    S = pd.Series(s_i).groupby(d.rollup.to_numpy()).sum().to_numpy()
    G = len(S)
    t_obs = S.sum() / np.sqrt((S ** 2).sum())
    if G <= 16:
        W = 1 - 2 * ((np.arange(2 ** G)[:, None] >> np.arange(G)) & 1)
    else:
        W = np.random.default_rng(seed).choice([-1, 1], size=(draws or 99_999, G))
    t_star = (W @ S) / np.sqrt((S ** 2).sum())
    return float((np.abs(t_star) >= abs(t_obs) - 1e-12).mean())


def score_shares(d, trend="linear", offset=True, dow=True):
    """Share of each cluster in the variance of the restricted score at beta = 0 (how few the effective clusters are)."""
    d = d.copy()
    d["off0"] = d.lT if offset else 0.0
    ctrl = _rhs_controls(trend, dow)
    rhs = " + ".join(ctrl) if ctrl else "1"
    mr = pf.fepois(f"n_blobs ~ {rhs} | rollup", data=d, offset="off0", vcov="iid")
    d["wt"] = np.asarray(mr.predict(type="response"), dtype=float)
    xt = np.asarray(pf.feols(f"post ~ {rhs} | rollup", data=d, weights="wt").resid(), dtype=float)
    S = pd.Series(xt * (d.n_blobs.to_numpy(dtype=float) - d.wt.to_numpy())).groupby(d.rollup.to_numpy()).sum()
    return (S ** 2 / (S ** 2).sum()).sort_values(ascending=False)


def wild_ci(d, beta_hat, trend="linear", offset=True, dow=True, half_width=0.5, step=0.0025, level=0.95):
    """Bootstrap confidence set by test inversion over a grid around beta_hat: all beta0 with p >= 1 - level."""
    grid = np.arange(beta_hat - half_width, beta_hat + half_width + step / 2, step)
    p = np.array([wild_score_test(d, b, trend, offset, dow) for b in grid])
    keep = grid[p >= 1 - level]
    if keep.size == 0:
        return np.nan, np.nan, grid, p
    if keep.min() <= grid.min() + step or keep.max() >= grid.max() - step:
        raise RuntimeError("confidence set reaches the grid edge; widen half_width")
    return float(keep.min()), float(keep.max()), grid, p


def first_stage(day, t0, w, price="mean", trend="linear", dow=True):
    """PRESPEC §2 first stage: day-level OLS of price (mETH/blob) on Post, trend, DOW; Newey-West (7 lags)."""
    lo, hi = t0 - pd.Timedelta(days=w), t0 + pd.Timedelta(days=w)
    s = day[(day.date >= lo) & (day.date <= hi) & (day.date != t0)].copy()
    s["t"] = (s.date - t0).dt.days
    X = pd.DataFrame({"const": 1.0, "post": (s.t > 0).astype(float)}, index=s.index)
    if trend in ("linear", "quadratic"):
        X["t"] = s.t
    if trend == "quadratic":
        X["t2"] = s.t ** 2
    if dow:
        X = X.join(pd.get_dummies(s.date.dt.dayofweek, prefix="dow", drop_first=True).astype(float))
    y = s[PRICE_COL[price]]
    r = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    pre = s[s.t < 0]
    return dict(pi=r.params["post"], se_pi=r.bse["post"], n_days_fs=len(s),
                p_pre=pre[PRICE_COL[price]].mean(), p_post=s[s.t > 0][PRICE_COL[price]].mean(),
                ethusd_pre=pre.eth_usd.mean())


def event_estimate(panel, day, t0, w=28, trend="linear", activity="offset", estimator="ppml", price="mean",
                   dow=True, zerofill=True, twoway=True, require_txcount=True):
    d = window_sample(panel, t0, w, require_txcount=require_txcount and activity != "none_all")
    act = "none" if activity == "none_all" else activity
    rf = reduced_form(d, trend, act, estimator, dow, zerofill, twoway)
    fs = first_stage(day, t0, w, price, trend, dow)
    eta = rf["beta"] / fs["pi"]
    se_eta = np.sqrt((rf["se_beta_rollup"] / fs["pi"]) ** 2 + (rf["beta"] * fs["se_pi"] / fs["pi"] ** 2) ** 2)
    return {**rf, **fs, "eta": eta, "se_eta": se_eta, "eps_at_pre_mean": eta * fs["p_pre"],
            "rollups": ",".join(sorted(d.rollup.unique()))}
