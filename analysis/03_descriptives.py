"""03 — Descriptive statistics by fork regime (Table 1) and the market time series (Figure 1).

Table 1 is computed directly at block level (supply, price) and tx level (demand, fees), so every
block and tx is assigned to its own regime exactly; fork-transition days need no rule here.
Outputs: output/tables/table1_regimes.{csv,md}, output/figures/fig1_market_timeseries.{pdf,png}
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from common import BLOB_TXS, BLOCKS, PRICES, DATA, TAB, FIG, FORKS, GAS_PER_BLOB, PRICING_REGIME, con

c = con()
blk = c.sql(f"""
SELECT regime, count(*) AS blocks, count(DISTINCT date) AS days_touched,
       min(target_blobs) AS target, min(max_blobs) AS max,
       avg(blob_count) AS blobs_per_block, avg(blob_count) / min(target_blobs) AS utilization_vs_target,
       avg(at_floor::INT) AS share_blocks_at_floor, avg(at_max::INT) AS share_blocks_at_max,
       median(computed_blob_base_fee_wei) AS price_block_median_wei,
       avg(computed_blob_base_fee_wei) AS price_block_mean_wei,
       min(timestamp) AS t0
FROM '{BLOCKS}' GROUP BY 1""").df()
# ETH/USD: each tx's fee is converted with its own day's close; txs after the last close are
# counted in the ETH totals but not in USD (reported as fee_eth_without_usd).
tx = c.sql(f"""
SELECT t.regime, count(*) AS blob_txs, sum(blob_count) AS blobs,
       sum(blob_count) FILTER (WHERE rollup = 'unknown') / sum(blob_count) AS unknown_share_blobs,
       sum(observed_blob_gas_price_wei * blob_gas_used) / sum(blob_gas_used) AS price_paid_blobweighted_wei,
       median(observed_blob_gas_price_wei) AS price_paid_median_wei,
       sum(blob_fee_wei) / 1e18 AS fees_eth,
       sum(blob_fee_wei / 1e18 * p.close) AS fees_usd,
       sum(blob_fee_wei) FILTER (WHERE p.close IS NULL) / 1e18 AS fee_eth_without_usd,
       avg(blob_count) AS blobs_per_tx,
       count(DISTINCT rollup) FILTER (WHERE rollup <> 'unknown') AS rollups_active
FROM '{BLOB_TXS}' t LEFT JOIN (SELECT date::DATE AS date, close FROM '{PRICES}' WHERE asset = 'ETH') p USING (date)
WHERE t.regime IS NOT NULL GROUP BY 1""").df()
t1 = blk.merge(tx, on="regime").sort_values("t0").drop(columns="t0")
t1.insert(1, "pricing_regime", t1.regime.map(PRICING_REGIME))
t1["usd_per_blob_paid"] = t1.fees_usd / t1.blobs
t1.to_csv(TAB / "table1_regimes.csv", index=False)

notes = ["Table 1 — Blob market by fork regime.",
         "Units: prices in wei per unit of blob gas (1 blob = 131,072 blob gas = 128 KiB of purchased capacity, not payload used);",
         "fees in ETH and USD (ETH daily close per tx date). Block rows: unit = execution block, price = header-implied blob base fee",
         "over ALL blocks. Tx rows: unit = blob tx, price = observed_blob_gas_price_wei. Blob txs past the last header block (1,128) excluded.",
         "Dencun/Pectra (EIP-4844 floor) and Fusaka onward (EIP-7918 reserve) are separate experiments and are never pooled.", ""]
(TAB / "table1_regimes.md").write_text("\n".join(notes) + t1.T.to_markdown(floatfmt=",.6g") + "\n")
print(t1.T.to_string())

# ---- Figure 1 --------------------------------------------------------------------------------------
d = pd.read_parquet(DATA / "day_panel.parquet")
d["date"] = pd.to_datetime(d.date)
INK, INK2, GRID, S1 = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(3, 1, figsize=(7.2, 6.4), sharex=True, gridspec_kw={"height_ratios": [1.3, 1, 0.8]})

edges = [pd.to_datetime(f[1], unit="s") for f in FORKS] + [d.date.max() + pd.Timedelta(days=1)]
for a in ax:
    for i, (name, *_ ) in enumerate(FORKS):
        if PRICING_REGIME[name] == "eip7918_reserve":
            a.axvspan(edges[i], edges[i + 1], color="#f1f0ec", lw=0, zorder=0)
        a.axvline(edges[i], color="#b5b4ae", lw=0.7, zorder=1)
    a.grid(axis="y", color=GRID, lw=0.6)
    a.set_axisbelow(True)
# Fusaka and BPO1 are 6 days apart: one combined label so they do not collide.
for i, label in [(0, "dencun"), (1, "pectra"), (2, "fusaka/bpo1"), (4, "bpo2")]:
    ax[0].text(edges[i] + pd.Timedelta(days=3 if i != 2 else -3), 1.02, label, transform=ax[0].get_xaxis_transform(),
               fontsize=7.5, color=INK2, va="bottom", ha="left" if i != 2 else "right")

ax[0].plot(d.date, d.price_block_mean_wei, color=S1, lw=1.2)
ax[0].set_yscale("log")
ax[0].set_ylabel("Blob base fee\n(wei / blob gas, log)")
ax[0].axhline(1, color=INK2, lw=0.8, ls=(0, (3, 2)))
ax[0].text(pd.Timestamp("2025-06-01"), 2.2, "1-wei floor", fontsize=7.5, color=INK2, va="bottom")

ax[1].plot(d.date, d.avg_blobs_per_block, color=S1, lw=1.2)
ax[1].step(d.date, d.target_blobs, where="post", color=INK2, lw=0.9, ls=(0, (3, 2)))
ax[1].step(d.date, d.max_blobs, where="post", color=INK2, lw=0.9)
ax[1].text(d.date.iloc[-1], d.target_blobs.iloc[-1], " target", fontsize=7.5, color=INK2, va="center")
ax[1].text(d.date.iloc[-1], d.max_blobs.iloc[-1], " max", fontsize=7.5, color=INK2, va="center")
ax[1].set_ylabel("Blobs per block\n(daily mean)")

ax[2].plot(d.date, d.share_blocks_at_floor, color=S1, lw=1.2)
ax[2].set_ylim(0, 1)
ax[2].set_ylabel("Share of blocks\nat 1-wei floor")
ax[2].xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax[2].xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
ax[2].set_xlim(d.date.min(), d.date.max())
fig.text(0.01, 0.005, "Unit: UTC day (N = %d). Shaded: EIP-7918 reserve-price regime (Fusaka onward). "
         "Blob base fee averaged over all blocks, incl. blocks without blobs." % len(d), fontsize=7, color=INK2)
fig.tight_layout(rect=(0, 0.02, 0.97, 1))
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig1_market_timeseries.{ext}", dpi=200)
print("wrote fig1")
