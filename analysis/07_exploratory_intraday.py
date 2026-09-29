"""07 — EXPLORATORY (PRESPEC S4; DECISIONS D-13, D-22). Intraday posting response to execution base fee, BPO2.

Unit: rollup x hour, BPO2 regime (2026-01-08 .. 2026-09-27). Rollup x day FE absorb daily demand (L2 activity,
market conditions); rollup x hour-of-day FE absorb diurnal posting schedules. Remaining variation: hour-to-hour
deviations of the execution base fee within a day.

This is NOT a blob-price elasticity. The execution base fee moves the blob price through the EIP-7918 reserve,
and it also moves the cost of the blob-carrying transaction's own execution gas; both are proportional to the
base fee, so the two channels cannot be separated. The reduced form is the response of posting to the full
per-post cost. The blob-price first stage is reported so the reader can see how much of the cost change runs
through the reserve.

Outputs: output/tables/s4_intraday.csv, output/logs/07_exploratory_intraday.md
"""
import numpy as np
import pandas as pd
import pyfixest as pf
import warnings
from common import BLOB_TXS, BLOCKS, TAB, LOG, GAS_PER_BLOB, con

warnings.filterwarnings("ignore")
c = con()
LO, HI = "2026-01-08", "2026-09-27"

hr = c.sql(f"""
SELECT date_trunc('hour', ts) AS hour, any_value(date) AS date, count(*) AS n_blocks,
       avg(base_fee_per_gas) / 1e9 AS exec_gwei,
       avg(computed_blob_base_fee_wei) * {GAS_PER_BLOB} / 1e15 AS p_meth,
       -- reserve above the current blob fee (EIP-7918 condition with BLOB_BASE_COST = 2^13, same-block approximation)
       avg((8192.0 * base_fee_per_gas > {GAS_PER_BLOB} * computed_blob_base_fee_wei)::INT) AS share_reserve_above
FROM '{BLOCKS}' WHERE regime = 'bpo2' AND date BETWEEN '{LO}' AND '{HI}' GROUP BY 1""").df()
hr = hr[hr.n_blocks >= 250]                    # drop hours with missing/short block coverage
rh = c.sql(f"""
WITH p AS (SELECT rollup, date_trunc('hour', block_time) AS hour, sum(blob_count) AS blobs, count(*) AS posts
           FROM '{BLOB_TXS}' WHERE regime = 'bpo2' AND rollup <> 'unknown' AND date BETWEEN '{LO}' AND '{HI}' GROUP BY 1, 2),
act AS (SELECT DISTINCT rollup, CAST(hour AS DATE) AS date FROM p)
SELECT a.rollup, h.hour, coalesce(p.blobs, 0) AS blobs, coalesce(p.posts, 0) AS posts
FROM act a JOIN (SELECT DISTINCT date_trunc('hour', ts) AS hour FROM '{BLOCKS}' WHERE regime = 'bpo2' AND date BETWEEN '{LO}' AND '{HI}') h
  ON CAST(h.hour AS DATE) = a.date
LEFT JOIN p ON p.rollup = a.rollup AND p.hour = h.hour""").df()
d = rh.merge(hr, on="hour")
d["hod"] = pd.to_datetime(d.hour).dt.hour
d["rday"] = d.rollup + "_" + d.date.astype(str)
d["rhod"] = d.rollup + "_" + d.hod.astype(str)
d["day_id"] = pd.to_datetime(d.date).dt.strftime("%Y%m%d").astype(int)
d["ln_exec"] = np.log(d.exec_gwei)
hr["hod"] = pd.to_datetime(hr.hour).dt.hour
hr["ln_exec"] = np.log(hr.exec_gwei)

# within-day variation available
wd = hr.groupby("date").ln_exec.std().mean()
out, log = [], ["# 07 — EXPLORATORY: intraday response to execution base fee (BPO2)", "",
                f"Mean within-day SD of ln(execution base fee) across hours: {wd:.3f}. "
                f"Share of hour-blocks with reserve above blob fee: {hr.share_reserve_above.mean():.3f}.", ""]
fs = pf.feols("p_meth ~ ln_exec | date + hod", data=hr, vcov={"CRV1": "date"})
log.append(f"First stage (unit: hour, N = {fs._N}): blob price (mETH/blob) on ln exec base fee, date + hour-of-day FE: "
           f"{fs.coef()['ln_exec']:.6f} (SE {fs.se()['ln_exec']:.6f}, clustered by day). Mean price {hr.p_meth.mean():.6f} mETH/blob.")
for y in ("blobs", "posts"):
    m = pf.fepois(f"{y} ~ ln_exec | rday + rhod", data=d, vcov={"CRV1": "rollup"})
    m2 = pf.fepois(f"{y} ~ ln_exec | rday + rhod", data=d, vcov={"CRV1": "rollup+day_id"})
    out.append(dict(outcome=y, beta=m.coef()["ln_exec"], se_rollup=m.se()["ln_exec"], se_twoway=m2.se()["ln_exec"],
                    n_obs=int(m._N), n_rollups=d[d[y] > 0].rollup.nunique(), fs_pi=fs.coef()["ln_exec"], fs_se=fs.se()["ln_exec"]))
    log.append(f"Reduced form, outcome {y} per rollup-hour (unit: rollup x hour, N = {int(m._N):,}; FE rollup x day, rollup x "
               f"hour-of-day): beta = {out[-1]['beta']:.4f} log points per log point of exec base fee; SE rollup "
               f"{out[-1]['se_rollup']:.4f}, two-way {out[-1]['se_twoway']:.4f}.")
res = pd.DataFrame(out)
res.to_csv(TAB / "s4_intraday.csv", index=False)
log += ["", "Interpretation: elasticity of within-day posting timing with respect to the full per-post cost "
        "(blob fee via the reserve plus the carrier tx's execution gas). Not a blob-price elasticity; not causal "
        "if intraday L1 congestion co-moves with intraday L2 activity."]
(LOG / "07_exploratory_intraday.md").write_text("\n".join(log) + "\n")
print("\n".join(log))

from common import save_numbers
b, p_ = res.set_index("outcome").loc["blobs"], res.set_index("outcome").loc["posts"]
save_numbers("07_intraday", {"beta_blobs": b.beta, "se_blobs": b.se_rollup, "se2_blobs": b.se_twoway, "n_obs": b.n_obs,
                             "beta_posts": p_.beta, "se_posts": p_.se_rollup, "fs_pi": b.fs_pi, "fs_se": b.fs_se,
                             "within_day_sd": wd, "share_reserve_above": hr.share_reserve_above.mean(),
                             "mean_price": hr.p_meth.mean()})
