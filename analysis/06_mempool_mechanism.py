"""06 — Mechanism (PRESPEC S3; DECISIONS D-08): is allocation at the EIP-4844 floor done by queueing?

Unit: blob tx in the EIP-4844 regime (Dencun, Pectra) matched to its first Xatu mempool sighting.
For each tx, the "first opportunity" block is the first block with timestamp > first_seen. Blocks strictly
between first_seen and inclusion were "passed over". For each passed-over block we record whether it had spare
blob capacity for this tx (blob_count + tx blobs <= max) and whether the tx was priced out (blob base fee > the
tx's max_fee_per_blob_gas). The market state a tx faces uses only predetermined information: 'floor' if the
first-opportunity block's excess is 0 (set by its parent), otherwise split by whether the block before it was full
('previous block full' = congestion). The first-opportunity block's own blob count is NOT used: when the tx is
included immediately that block contains the tx, so its fullness would be mechanically related to inclusion.

Queueing at the floor predicts long waits at the floor with passed-over blocks full. Excess supply predicts
immediate inclusion at the floor, and any delay occurring despite spare capacity (builder/propagation behaviour,
not price rationing).

Outputs: output/tables/t4_mempool_*.csv, output/figures/fig5_mempool.{pdf,png}, output/logs/06_mempool_mechanism.md
"""
import numpy as np
import pandas as pd
import pyfixest as pf
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import BLOB_TXS, BLOCKS, rel, TAB, FIG, LOG, GAS_PER_BLOB, save_numbers, con

warnings.filterwarnings("ignore")
MEMPOOL = rel("mempool_inclusion.parquet")
MAX_WAIT_BLOCKS = 300            # range join limited to waits <= 1 hour; longer waits counted separately
c = con()
TRANSITION = "('2025-05-07', '2025-12-03')"

c.execute(f"""CREATE TEMP TABLE blk AS SELECT number, timestamp, blob_count, max_blobs, at_floor, at_max,
                     lag(at_max) OVER (ORDER BY number) AS prev_at_max,
                     computed_blob_base_fee_wei AS fee FROM '{BLOCKS}' WHERE regime IN ('dencun', 'pectra')""")
c.execute(f"""
CREATE TEMP TABLE m AS
SELECT t.hash, t.rollup, t.date, t.block_number, t.block_ts, t.blob_count, t.max_fee_per_blob_gas AS cap,
       t.regime, mp.first_seen, mp.n_sensors, mp.inclusion_delay_s
FROM '{BLOB_TXS}' t JOIN '{MEMPOOL}' mp USING (hash)
WHERE t.regime IN ('dencun', 'pectra') AND t.date NOT IN {TRANSITION}""")
cov = c.sql(f"""SELECT t.regime, count(*) AS blob_txs, count(m.hash) AS matched, count(m.hash) / count(*) AS match_rate,
                       median(m.n_sensors) AS median_sensors,
                       avg((m.inclusion_delay_s < 0)::INT) AS share_seen_after_inclusion
                FROM '{BLOB_TXS}' t LEFT JOIN m USING (hash)
                WHERE t.regime IN ('dencun', 'pectra') AND t.date NOT IN {TRANSITION} GROUP BY 1 ORDER BY 1""").df()

# first-opportunity block (ASOF: first block strictly after first_seen)
c.execute("""
CREATE TEMP TABLE fo AS
SELECT m.*, b.number AS fo_number, b.at_floor AS fo_floor, b.prev_at_max AS fo_prev_full, b.fee AS fo_fee,
       m.block_number - b.number AS passed_over
FROM m ASOF JOIN blk b ON b.timestamp > epoch(m.first_seen)""")
c.execute("""CREATE TEMP TABLE fo2 AS SELECT *, CASE WHEN fo_floor THEN 'floor' WHEN fo_prev_full THEN 'above floor, previous block full'
                                  ELSE 'above floor, previous block not full' END AS state
             FROM fo WHERE passed_over >= 0""")      # passed_over < 0: sighted after inclusion (sensor lag)

# passed-over blocks, for txs that waited 1..MAX_WAIT_BLOCKS blocks
c.execute(f"""
CREATE TEMP TABLE po AS
SELECT f.hash, count(*) AS n_po,
       sum((b.blob_count + f.blob_count <= b.max_blobs)::INT) AS n_spare,
       sum((b.fee > f.cap)::INT) AS n_priced_out,
       sum(b.at_floor::INT) AS n_po_floor
FROM fo2 f JOIN blk b ON b.number >= f.fo_number AND b.number < f.block_number
WHERE f.passed_over BETWEEN 1 AND {MAX_WAIT_BLOCKS} GROUP BY 1""")

by_state = c.sql(f"""
SELECT f.regime, f.state, count(*) AS n_txs,
       avg((f.passed_over = 0)::INT) AS share_first_opportunity,
       avg((f.passed_over >= 2)::INT) AS share_waited_2plus,
       avg(f.passed_over) FILTER (WHERE f.passed_over <= {MAX_WAIT_BLOCKS}) AS mean_passed_over,
       quantile_cont(f.passed_over, 0.9) AS p90_passed_over,
       avg((f.passed_over > {MAX_WAIT_BLOCKS})::INT) AS share_waited_over_1h,
       sum(p.n_spare) / sum(p.n_po) AS share_passed_blocks_with_spare_capacity,
       sum(p.n_priced_out) / sum(p.n_po) AS share_passed_blocks_priced_out,
       avg((p.n_spare = p.n_po AND p.n_priced_out = 0)::INT) FILTER (WHERE p.n_po > 0)
           AS share_delayed_txs_never_capacity_or_price_constrained
FROM fo2 f LEFT JOIN po p USING (hash) GROUP BY 1, 2 ORDER BY 1, 2""").df()
by_state.to_csv(TAB / "t4_mempool_by_state.csv", index=False)
cov.to_csv(TAB / "t4_mempool_coverage.csv", index=False)

# Regression: waited >= 1 block on first-opportunity state; rollup FE and day FE; unit = blob tx
d = c.sql("""SELECT rollup, CAST(date AS VARCHAR) AS day, state, regime, (passed_over >= 1)::INT AS waited,
                    ln(1 + passed_over) AS ln_wait FROM fo2 WHERE rollup <> 'unknown'""").df()
d["floor"] = (d.state == "floor").astype(int)
d["prevfull"] = (d.state == "above floor, previous block full").astype(int)
reg = []
for rg in ("dencun", "pectra"):
    s = d[d.regime == rg]
    if s.empty:
        continue
    for y in ("waited", "ln_wait"):
        m1 = pf.feols(f"{y} ~ floor + prevfull | rollup + day", data=s, vcov={"CRV1": "rollup+day"})
        reg.append(dict(regime=rg, outcome=y, b_floor=m1.coef()["floor"], se_floor=m1.se()["floor"],
                        b_prevfull=m1.coef()["prevfull"], se_prevfull=m1.se()["prevfull"], mean_base=s[s.state == "above floor, previous block not full"][y].mean(),
                        n_obs=int(m1._N), n_rollups=s.rollup.nunique()))
reg = pd.DataFrame(reg)
reg.to_csv(TAB / "t4_mempool_regression.csv", index=False)

log = ["# 06 — Mechanism: mempool-to-inclusion delay in the EIP-4844 regime", "",
       "## Coverage (unit: blob tx; transition days excluded)", "", cov.to_markdown(index=False, floatfmt=".4g"), "",
       "## By state of the first-opportunity block (unit: blob tx)", "",
       "passed_over = blocks between first sighting and inclusion. Shares of passed-over blocks are pooled over "
       f"txs that waited 1..{MAX_WAIT_BLOCKS} blocks.", "", by_state.to_markdown(index=False, floatfmt=".4g"), "",
       "## Regression (unit: blob tx, labelled rollups; FE rollup + day; SE two-way rollup x day; base = above floor, previous block not full; prevfull = previous block full)", "",
       reg.to_markdown(index=False, floatfmt=".4g"), ""]
(LOG / "06_mempool_mechanism.md").write_text("\n".join(log) + "\n")
print("\n".join(log))

bs = by_state.set_index(["regime", "state"])
save_numbers("06_mempool", {
    **{f"match_{r.regime}": r.match_rate for r in cov.itertuples()},
    **{f"{rg}_{ {'floor': 'floor', 'above floor, previous block full': 'cong', 'above floor, previous block not full': 'interior'}[st]}_{k}": bs.loc[(rg, st), k] for rg, st in bs.index
       for k in ("n_txs", "share_first_opportunity", "share_waited_2plus", "mean_passed_over",
                 "share_passed_blocks_with_spare_capacity", "share_passed_blocks_priced_out",
                 "share_delayed_txs_never_capacity_or_price_constrained")},
    **{f"reg_{r.regime}_{r.outcome}_{k}": getattr(r, k) for r in reg.itertuples()
       for k in ("b_floor", "se_floor", "b_prevfull", "se_prevfull", "mean_base", "n_obs")},
})

# ---- Figure 5 ----------------------------------------------------------------------------------------
INK2, S1C, S2C, S3C = "#52514e", "#2a78d6", "#eb6834", "#1baf7a"
cdf = c.sql(f"""SELECT regime, state, least(passed_over, 20) AS k, count(*) AS n FROM fo2 GROUP BY ALL""").df()
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
for ax, rg in zip(axs, ("dencun", "pectra")):
    for st, col in (("floor", S1C), ("above floor, previous block not full", S3C), ("above floor, previous block full", S2C)):
        s = cdf[(cdf.regime == rg) & (cdf.state == st)].sort_values("k")
        if s.empty:
            continue
        ax.step(s.k, s.n.cumsum() / s.n.sum(), where="post", color=col, lw=1.6, label=st)
    ax.set_title(rg, fontsize=9, color=INK2)
    ax.set_xlabel("blocks passed over before inclusion", color=INK2, fontsize=8)
    ax.set_xlim(0, 12)
    ax.grid(color="#e4e3df", lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
axs[0].set_ylabel("cumulative share of blob txs", color=INK2, fontsize=8)
axs[1].legend(title="state when first seen", title_fontsize=7, fontsize=6.5, frameon=False, loc="lower right")
fig.text(0.01, 0.01, "Unit: blob tx matched to its first Xatu mempool sighting (Xatu / ethPandaOps, CC BY 4.0). "
         "Transition days excluded.", fontsize=6.5, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig5_mempool.{ext}", dpi=200)
