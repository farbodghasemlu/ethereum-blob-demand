"""02 — Build the analysis panels from the read-only deposit.

data/day_panel.parquet         unit: UTC day. Market-level supply, price and demand.
data/rollup_day_panel.parquet  unit: rollup x UTC day (days with >=1 post only; no zero-filling).
data/est_panel.parquet         unit: rollup x UTC day, estimation panel: labelled rollups, zero-filled within
                               each rollup's active span, transition/partial days dropped, growthepie txcount.

Data-handling rules (all flagged, none silently applied to estimation samples):
- Blob txs past the last header block have no date/regime and are excluded (audit table undated_txs).
- A day's regime is the regime of the majority of its blocks; `transition_day` marks the four fork
  days that span two regimes, `partial_day` the first and last day of the sample.
- Price is in wei per unit of blob gas. `price_block_mean_wei` averages the header-implied blob base
  fee over ALL blocks (including blocks with no blobs); `price_paid_wei` is the blob-gas-weighted
  mean of `observed_blob_gas_price_wei` over txs. The audit shows the two fee fields agree to within
  max(0.1%, 1 wei) in every regime, so the header series is valid post-Fusaka too.
- USD uses the ETH daily close; it is NULL after the last available close (2026-09-23), never imputed.
"""
from common import BLOB_TXS, BLOCKS, ROLLUP_DAILY, PRICES, GROWTHEPIE, DATA, LOG, GAS_PER_BLOB, PRICING_REGIME, con

c = con()
c.execute(f"CREATE TEMP TABLE eth AS SELECT date::DATE AS date, close AS eth_usd FROM '{PRICES}' WHERE asset = 'ETH'")
c.execute("CREATE TEMP TABLE pr AS SELECT * FROM (VALUES " +
          ", ".join(f"('{k}', '{v}')" for k, v in PRICING_REGIME.items()) + ") t(regime, pricing_regime)")

# ---- day panel (supply side from headers, demand side from txs) -------------------------------
c.execute(f"""
CREATE TEMP TABLE blk AS
SELECT date,
       mode(regime) AS regime,                              -- majority regime of the day's blocks
       count(DISTINCT regime) > 1 AS transition_day,
       count(*) AS n_blocks,
       sum(blob_count) AS blobs_header,
       avg(blob_count) AS avg_blobs_per_block,
       avg(target_blobs) AS target_blobs, avg(max_blobs) AS max_blobs,
       avg(at_floor::INT) AS share_blocks_at_floor,
       avg(at_max::INT) AS share_blocks_at_max,
       avg(computed_blob_base_fee_wei) AS price_block_mean_wei,
       median(computed_blob_base_fee_wei) AS price_block_median_wei,
       avg(base_fee_per_gas) AS exec_base_fee_mean_wei
FROM '{BLOCKS}' GROUP BY 1""")
c.execute(f"""
CREATE TEMP TABLE txd AS
SELECT date,
       count(*) AS n_txs, sum(blob_count) AS blobs_txs,
       sum(blob_count) FILTER (WHERE rollup = 'unknown') AS blobs_unknown,
       sum(observed_blob_gas_price_wei * blob_gas_used) / sum(blob_gas_used) AS price_paid_wei,
       sum(blob_fee_wei) / 1e18 AS blob_fee_eth,
       count(DISTINCT rollup) FILTER (WHERE rollup <> 'unknown') AS n_active_rollups
FROM '{BLOB_TXS}' WHERE date IS NOT NULL GROUP BY 1""")
day = c.sql(f"""
SELECT b.*, pr.pricing_regime,
       b.date = (SELECT min(date) FROM blk) OR b.date = (SELECT max(date) FROM blk) AS partial_day,
       t.n_txs, t.blobs_txs, t.blobs_unknown, t.blobs_unknown / t.blobs_txs AS unknown_share_blobs,
       b.blobs_header - t.blobs_txs AS blobs_without_tx_record,
       b.blobs_header * {GAS_PER_BLOB} / 1024.0 / 1024 / 1024 AS capacity_purchased_gib,
       t.price_paid_wei, t.blob_fee_eth, t.n_active_rollups,
       e.eth_usd, t.blob_fee_eth * e.eth_usd AS blob_fee_usd,
       -- USD per blob at the block-mean price: price (wei/gas) * gas per blob / 1e18 * ETH/USD
       b.price_block_mean_wei * {GAS_PER_BLOB} / 1e18 * e.eth_usd AS usd_per_blob_block_mean
FROM blk b JOIN txd t USING (date) LEFT JOIN eth e USING (date) JOIN pr USING (regime)
ORDER BY date""")
day.write_parquet(str(DATA / "day_panel.parquet"))
dd = day.df()

# ---- rollup x day panel -------------------------------------------------------------------------
# Rebuilt from txs (not rollup_daily.parquet) so the day's regime flags and the exclusion of
# undated txs are applied in one place; script 01 checks it reconciles with rollup_daily.
# growthepie origin_key crosswalk: only names that differ; everything else maps to itself if present.
XWALK = {"world": "worldchain", "robinhood-chain": "robinhood", "zksync": "zksync_era"}
c.execute("CREATE TEMP TABLE xw AS SELECT * FROM (VALUES " +
          ", ".join(f"('{k}', '{v}')" for k, v in XWALK.items()) + ") t(rollup, origin_key)")
c.execute(f"CREATE TEMP TABLE gkeys AS SELECT DISTINCT origin_key FROM '{GROWTHEPIE}'")
c.execute(f"""
CREATE TEMP TABLE rd AS
WITH tx AS (
  SELECT rollup, date, block_ts, blob_count, blob_gas_used, blob_fee_wei, observed_blob_gas_price_wei,
         block_ts - lag(block_ts) OVER (PARTITION BY rollup ORDER BY block_ts, tx_index) AS gap_s
  FROM '{BLOB_TXS}' WHERE date IS NOT NULL)
SELECT rollup, date, count(*) AS n_txs, sum(blob_count) AS n_blobs, sum(blob_gas_used) AS blob_gas_used,
       avg(blob_count) AS avg_blobs_per_tx,
       sum(observed_blob_gas_price_wei * blob_gas_used) / sum(blob_gas_used) AS price_paid_wei,
       sum(blob_fee_wei) / 1e18 AS blob_fee_eth,
       median(gap_s) AS med_interpost_s
FROM tx GROUP BY 1, 2""")
rpan = c.sql(f"""
SELECT r.*, d.regime, d.pricing_regime, d.transition_day, d.partial_day,
       r.n_blobs / d.blobs_txs AS share_of_day_blobs,
       d.price_block_mean_wei, d.eth_usd, r.blob_fee_eth * d.eth_usd AS blob_fee_usd,
       r.rollup = 'unknown' AS is_unknown,
       CASE WHEN g.origin_key IS NOT NULL THEN g.origin_key END AS growthepie_key
FROM rd r JOIN day d USING (date)
LEFT JOIN xw USING (rollup)
LEFT JOIN gkeys g ON g.origin_key = coalesce(xw.origin_key, r.rollup)
ORDER BY rollup, date""")
rpan.write_parquet(str(DATA / "rollup_day_panel.parquet"))

# ---- estimation panel: zero-filled rollup x day (DECISIONS D-04, D-05, D-06, D-11, D-14) ---------------
# Labelled rollups only; every day from first to last posting date; transition and partial days dropped.
# Prices converted to milli-ETH per blob: wei/blob-gas * 131072 gas/blob / 1e15 wei/mETH.
MWEI = f"* {GAS_PER_BLOB} / 1e15"
est = c.sql(f"""
WITH span AS (SELECT rollup, any_value(growthepie_key) AS growthepie_key, min(date) AS first_post, max(date) AS last_post
              FROM rpan WHERE NOT is_unknown GROUP BY 1),
grid AS (SELECT s.rollup, s.growthepie_key, s.first_post, s.last_post, d.date
         FROM span s JOIN day d ON d.date BETWEEN s.first_post AND s.last_post
         WHERE NOT d.transition_day AND NOT d.partial_day),
tc AS (SELECT origin_key, date, value AS l2_txcount FROM '{GROWTHEPIE}' WHERE metric_key = 'txcount')
SELECT g.rollup, g.date, g.growthepie_key, g.first_post, g.last_post,
       coalesce(r.n_blobs, 0) AS n_blobs, coalesce(r.n_txs, 0) AS n_blob_txs, r.n_blobs IS NULL AS zero_filled,
       r.avg_blobs_per_tx, r.med_interpost_s, coalesce(r.blob_fee_eth, 0) AS blob_fee_eth,
       tc.l2_txcount,
       d.regime, d.pricing_regime,
       d.price_block_mean_wei {MWEI} AS p_mean_meth, d.price_block_median_wei {MWEI} AS p_median_meth,
       d.price_paid_wei {MWEI} AS p_paid_meth, d.share_blocks_at_floor, d.share_blocks_at_max,
       d.exec_base_fee_mean_wei / 1e9 AS exec_base_fee_gwei, d.eth_usd
FROM grid g JOIN day d USING (date)
LEFT JOIN rpan r ON r.rollup = g.rollup AND r.date = g.date
LEFT JOIN tc ON tc.origin_key = g.growthepie_key AND tc.date = g.date
ORDER BY g.rollup, g.date""")
est.write_parquet(str(DATA / "est_panel.parquet"))
est_n = c.sql("SELECT count(*) AS rollup_days, sum(zero_filled::INT) AS zero_filled, count(DISTINCT rollup) AS rollups, "
              "count(l2_txcount) AS with_txcount FROM est").df()

# ---- log -----------------------------------------------------------------------------------------
rec = c.sql(f"""SELECT count(*) AS rows_joined,
                       count(*) FILTER (WHERE o.n_txs IS DISTINCT FROM r.n_txs OR o.n_blobs IS DISTINCT FROM r.n_blobs) AS rows_differing
                FROM rpan r JOIN '{ROLLUP_DAILY}' o USING (rollup, date)""").df()
gaps = c.sql("""SELECT sum(span - n) AS rollup_days_without_post_inside_active_span, sum(n) AS rollup_days
                FROM (SELECT rollup, count(*) n, max(date) - min(date) + 1 AS span FROM rpan WHERE NOT is_unknown GROUP BY 1)""").df()
cov = c.sql("""SELECT count(DISTINCT rollup) FILTER (WHERE growthepie_key IS NOT NULL) AS rollups_matched,
                      count(DISTINCT rollup) FILTER (WHERE NOT is_unknown) AS rollups_labelled,
                      sum(n_blobs) FILTER (WHERE growthepie_key IS NOT NULL) / sum(n_blobs) AS blob_share_matched
               FROM rpan""").df()
lines = ["# 02 — Panels", "",
         f"day_panel: {len(dd)} days, {dd.date.min().date()} .. {dd.date.max().date()}; "
         f"transition days {int(dd.transition_day.sum())}, partial days {int(dd.partial_day.sum())}, "
         f"days without ETH/USD {int(dd.eth_usd.isna().sum())}",
         f"rollup_day_panel: {c.sql('SELECT count(*) FROM rpan').fetchone()[0]} rollup-days, "
         f"{c.sql('SELECT count(DISTINCT rollup) FROM rpan').fetchone()[0]} rollup labels incl. 'unknown'",
         "", "Reconciliation with release/rollup_daily.parquet (n_txs, n_blobs):", rec.to_markdown(index=False),
         "", "Zero-post days inside each labelled rollup's first..last posting date (NOT in the panel):",
         gaps.to_markdown(index=False),
         "", "growthepie coverage:", cov.to_markdown(index=False),
         "", "Estimation panel (zero-filled, transition/partial days dropped):", est_n.to_markdown(index=False),
         "", "Days by regime:", dd.groupby("regime", sort=False).size().rename("days").to_frame().to_markdown()]
(LOG / "02_build_panels.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
