"""01 — Data audit. Checks the deposit against the facts the project notes relies on and records
every data problem that a later script has to handle.

Outputs (output/tables/audit_*.csv, output/logs/01_data_audit.md). Aggregates only; nothing
row-level is pulled into memory.
"""
from common import BLOB_TXS, BLOCKS, ROLLUP_DAILY, DA_CROSS, PRICES, TAB, LOG, FORKS, con

c = con()
md = ["# 01 — Data audit", ""]


def save(df, name, title, note=""):
    df.to_csv(TAB / f"audit_{name}.csv", index=False)
    md.extend([f"## {title}", "", note, "", df.to_markdown(index=False, floatfmt=".6g"), ""])
    print(f"\n== {title}\n{df.to_string(index=False)}")


# 1. Regime block counts vs the the project notes table.
claimed = {"dencun": 3_004_497, "pectra": 1_504_610, "fusaka": 40_084, "bpo1": 203_605, "bpo2": 1_897_647}
df = c.sql(f"""SELECT regime, count(*) AS blocks, min(timestamp) AS first_ts, max(timestamp) AS last_ts,
                      avg(at_floor::INT) AS share_blocks_at_floor, avg(at_max::INT) AS share_blocks_at_max
               FROM '{BLOCKS}' GROUP BY 1 ORDER BY first_ts""").df()
df["blocks_claimed_in_notes"] = df.regime.map(claimed)
df["diff"] = df.blocks - df.blocks_claimed_in_notes
act = {f[0]: f[1] for f in FORKS}
df["first_ts_ge_activation"] = df.apply(lambda r: r.first_ts >= act[r.regime], axis=1)
save(df, "regime_blocks", "Blocks per regime vs the project notes",
     "Unit: execution block. `diff` = deposit minus the the project notes table.")

# 2. Blob txs whose block is not in the header panel (no timestamp/date/regime).
df = c.sql(f"""SELECT count(*) AS n_txs, sum(blob_count) AS n_blobs, count(DISTINCT block_number) AS n_blocks,
                      min(block_number) AS min_block, max(block_number) AS max_block,
                      (SELECT max(number) FROM '{BLOCKS}') AS last_panel_block
               FROM '{BLOB_TXS}' WHERE date IS NULL""").df()
df2 = c.sql(f"""SELECT count(*) AS rows_null_date, sum(n_txs) AS txs, sum(n_blobs) AS blobs
                FROM '{ROLLUP_DAILY}' WHERE date IS NULL""").df()
df = df.join(df2.add_prefix("rollup_daily_"))
save(df, "undated_txs", "Blob txs beyond the end of the header panel",
     "These txs have no date/regime and appear in rollup_daily as rows with NULL date. "
     "They must be excluded from every dated analysis.")

# 3. Header blob gas vs sum of tx blob gas, per block.
df = c.sql(f"""WITH t AS (SELECT block_number, sum(blob_gas_used) g FROM '{BLOB_TXS}' GROUP BY 1)
               SELECT b.regime, count(*) FILTER (WHERE coalesce(t.g, 0) <> b.blob_gas_used) AS blocks_mismatch,
                      sum(b.blob_gas_used - coalesce(t.g, 0)) / 131072 AS blobs_missing_from_txs,
                      sum(b.blob_count) AS header_blobs,
                      min(b.date) FILTER (WHERE coalesce(t.g, 0) <> b.blob_gas_used) AS first_date,
                      max(b.date) FILTER (WHERE coalesce(t.g, 0) <> b.blob_gas_used) AS last_date
               FROM '{BLOCKS}' b LEFT JOIN t ON t.block_number = b.number GROUP BY 1 ORDER BY min(b.number)""").df()
save(df, "block_coverage", "Header blob gas vs tx-level blob gas",
     "Unit: block. Blobs present in headers but with no tx record (Blobscan gaps); they carry no rollup label.")

# 4. Unattributed demand ('unknown'), by regime and measure.
df = c.sql(f"""SELECT coalesce(regime, '(undated)') AS regime, count(*) AS n_txs,
                      avg((rollup = 'unknown')::INT) AS unknown_share_txs,
                      sum(blob_count) FILTER (WHERE rollup = 'unknown') / sum(blob_count) AS unknown_share_blobs,
                      sum(blob_fee_wei) FILTER (WHERE rollup = 'unknown') / sum(blob_fee_wei) AS unknown_share_fees
               FROM '{BLOB_TXS}' GROUP BY GROUPING SETS ((regime), ()) ORDER BY min(block_ts) NULLS LAST""").df()
df.loc[df.n_txs == df.n_txs.max(), "regime"] = "ALL"
save(df, "unknown_share", "Unattributed blob demand (rollup = 'unknown')",
     "The validation report's 10.3% is the tx share; the ~4% in the project notes is the blob share. "
     "The share is not stable across regimes.")

# 5. Price fields: computed (header excess) vs observed (Blobscan), by regime.
df = c.sql(f"""SELECT regime, count(*) AS n_txs,
                      avg((observed_blob_gas_price_wei = computed_blob_base_fee_wei)::INT) AS share_exact,
                      avg((abs(observed_blob_gas_price_wei - computed_blob_base_fee_wei)
                           <= greatest(1e-3 * observed_blob_gas_price_wei, 1))::INT) AS share_within_0p1pct_or_1wei,
                      max(abs(observed_blob_gas_price_wei - computed_blob_base_fee_wei)) AS max_abs_diff_wei,
                      avg((effective_blob_gas_price_wei = observed_blob_gas_price_wei)::INT) AS share_effective_eq_observed,
                      avg((observed_blob_gas_price_wei <= 1)::INT) AS share_txs_paying_1wei,
                      avg((max_fee_per_blob_gas < observed_blob_gas_price_wei)::INT) AS share_bid_below_price
               FROM '{BLOB_TXS}' WHERE regime IS NOT NULL GROUP BY 1 ORDER BY min(block_ts)""").df()
save(df, "price_fields", "Computed vs observed blob gas price",
     "Unit: blob tx. Prices in wei per blob gas. `computed` evaluates the fee from the header's "
     "excess_blob_gas; EIP-7918 acts on the excess *update*, which the header already reflects.")

# 6. Partial and fork-transition days (the daily panel has no regime column).
df = c.sql(f"""SELECT date, count(*) AS n_blocks, count(DISTINCT regime) AS n_regimes,
                      string_agg(DISTINCT regime, '+') AS regimes
               FROM '{BLOCKS}' GROUP BY 1 HAVING n_regimes > 1 OR n_blocks < 6500 ORDER BY 1""").df()
save(df, "irregular_days", "Fork-transition and partial days",
     "Unit: UTC day. A full day has ~7,200 blocks. Days spanning two regimes need an explicit assignment rule.")

# 7. USD price coverage.
df = c.sql(f"""SELECT (SELECT max(date) FROM '{PRICES}' WHERE asset = 'ETH') AS eth_close_last_date,
                      (SELECT max(date) FROM '{BLOCKS}') AS blocks_last_date,
                      count(*) FILTER (WHERE blob_fee_usd IS NULL AND date IS NOT NULL) AS rollup_days_missing_usd
               FROM '{ROLLUP_DAILY}'""").df()
save(df, "usd_coverage", "ETH/USD coverage", "")

# 8. Cross-market file completeness.
df = c.sql(f"""SELECT count(*) AS n_days, count(cel_bytes) AS cel_bytes, count(cel_blobs) AS cel_blobs,
                      count(cel_fee_tia) AS cel_fee_tia, count(cel_fee_usd) AS cel_fee_usd
               FROM '{DA_CROSS}'""").df()
save(df, "da_cross_coverage", "Celestia columns in da_cross_daily",
     "Per validation_report notes: Celestia came from growthepie (Celenium unreachable); cel_blobs and "
     "cel_fee_tia are empty, cel_fee_usd is growthepie's, not a TIA conversion. Attribution is growthepie, not Celenium.")

(LOG / "01_data_audit.md").write_text("\n".join(md))
print(f"\nwrote {LOG / '01_data_audit.md'}")

from common import save_numbers
u = c.sql(f"""SELECT CASE WHEN grouping(regime) = 1 THEN 'ALL' ELSE coalesce(regime, 'undated') END AS regime, avg((rollup = 'unknown')::INT) AS tx,
                     sum(blob_count) FILTER (WHERE rollup = 'unknown') / sum(blob_count) AS blobs,
                     sum(blob_fee_wei) FILTER (WHERE rollup = 'unknown') / sum(blob_fee_wei) AS fees
              FROM '{BLOB_TXS}' GROUP BY ROLLUP (regime)""").df().set_index("regime")
pf_ = c.sql(f"""SELECT count(*) AS n, avg((abs(observed_blob_gas_price_wei - computed_blob_base_fee_wei)
                       <= greatest(1e-3 * observed_blob_gas_price_wei, 1))::INT) AS agree FROM '{BLOB_TXS}' WHERE regime IS NOT NULL""").df()
save_numbers("01_audit", {**{f"unk_{m}_{r}": u.loc[r, m] for r in u.index for m in ("tx", "blobs", "fees")},
                          "price_agree_share": pf_.agree[0], "n_blob_txs_dated": pf_.n[0]})
