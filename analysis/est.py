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
