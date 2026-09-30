# Data Sources & Dataset Documentation

## 1. Sources

### 1.1 Ethereum execution-layer JSON-RPC (script 01)
- Endpoints (rotated, all free, no key): `ethereum-rpc.publicnode.com`, `eth.drpc.org`, `rpc.flashbots.net`, `eth.llamarpc.com`, `1rpc.io/eth`. Override with `RPC_URLS`.
- Method: batched `eth_getBlockByNumber(hex, false)` from the Dencun activation block 19,426,587 (2024-03-13) to the chain head.
- Handling: request batching, endpoint rotation on error, per-block retry, exponential backoff, checkpointed resume, 50k-block CSV shards in `data/raw/el_headers/`.
- License/terms: public infrastructure endpoints; be polite (defaults are conservative).

### 1.2 Blobscan API (scripts 02, 03)
- Base: `https://api.blobscan.com` (free, open, no key; MIT-licensed indexer by Blossom Labs).
- `GET /transactions?startBlock&endBlock&sort=asc&ps=100&p=N` paginated inside 10k-block windows; raw JSON stored verbatim as NDJSON in `data/raw/blobscan_txs/` so downstream extraction is robust to schema drift. `expand=blob` is attempted once and permanently disabled if the server rejects it.
- `GET /stats/*` endpoints are probed by script 03 and stored raw in `data/raw/blobscan_stats/` purely for cross-validation.
- Rate limits: 429 honored with Retry-After/backoff; default 350 ms between calls.

### 1.3 Celenium API — Celestia indexer (script 04)
- **Status in this deposit:** Celenium's CDN returned HTTP 403 to the collection host, so no Celenium data is included. The Celestia columns of `da_cross_daily` and `da_layers_daily.csv` come from growthepie's DA overview instead (attribute growthepie, CC BY 4.0).
- Base: `https://api-mainnet.celenium.io/v1` (free tier, no key). **Attribution required by their terms: "Data provided by Celenium API" with a link to celenium.io in any publication/app using it.**
- `GET /rollup?limit=100&offset=N` — rollup registry → `data/raw/celestia/rollups.json`.
- `GET /stats/series/{name}/day?from&to` for `blobs_size`, `blobs_count`, `fee` (verified against their OpenAPI spec) → `data/raw/celestia/series_*.json`. Points are `{time: ISO8601, value: string}`.
- `GET /rollup/{id}/stats/{name}/day?from&to` for `size`, `blobs_count`, `fee` per rollup → `data/raw/celestia/rollup_daily.ndjson`.
- Collected in 180-day chunks from Celestia mainnet launch (2023-10-31); checkpointed per rollup.

### 1.4 Prices (script 05)
- Primary: Binance `GET /api/v3/klines?symbol={ETHUSDT|TIAUSDT}&interval=1d` (free, no key, full history, 1000 rows/page).
- Fallback (automatic, e.g. on HTTP 451 geo-block): Coinbase Exchange `GET /products/{ETH-USD|TIA-USD}/candles?granularity=86400` in 300-day windows.
- Output `data/raw/prices/{ETH,TIA}_daily.csv`; the `source` column records which venue supplied each row.
- **Not redistributed.** The exchanges' terms restrict redistribution of their market data, so the deposit does not include `prices_daily.csv`; run `npm run prices` to regenerate it (under a minute). USD figures in the deposited `rollup_daily` and `da_cross_daily` files were computed from this series at build time.

### 1.5 growthepie (script 06)
- `https://api.growthepie.xyz/v1/fundamentals_full.json` — free public JSON of daily per-L2 fundamentals (txcount, DAA, fees, rent paid, stablecoin supply, ... as `metric_key` rows). Used to normalize DA demand by L2 activity (extensive-margin controls).
- growthepie data is published under CC BY 4.0; attribute growthepie (growthepie.xyz).

### 1.6 Xatu / ethPandaOps public data (script 07, EXPERIMENTAL, optional)
- `https://data.ethpandaops.io/xatu/mainnet/databases/default/mempool_transaction/{yyyy}/{m}/{d}.parquet` (hourly fallback probed automatically). Public mempool observations from the ethPandaOps sensor network (CC BY 4.0; attribute "Xatu / ethPandaOps").
- DuckDB `httpfs` reads the remote parquet with column projection and a `type=3` filter and writes one CSV per day (`data/raw/xatu_mempool/`) with one row per tx: earliest sighting across the sensor fleet (`seen_at`), number of sightings and distinct sensors. Xatu stores hashes and addresses as BLOBs holding ASCII hex (decoded to text) and fee caps as 16-byte little-endian UInt128 (kept as hex). Column names are autodetected per file; missing days are skipped and recorded in `state/xatu.json`, and failed days are retried on the next run.
- Collected for the EIP-4844 regime only (Dencun and Pectra, 2024-03-13 to 2025-12-03).
- Used only for mempool→inclusion latency in the floor-regime rationing analysis; the rest of the pipeline does not depend on it.

## 2. Output datasets (`datasets/`)

All Parquet files are ZSTD-compressed. Dates are UTC. Wei quantities that can exceed 2^53 are stored as DOUBLE (documented per column) or decimal strings in raw shards; join keys are exact integers.

### 2.1 `blocks_panel.parquet` — one row per execution block (primary supply-side panel)
| field | type | description |
|---|---|---|
| number | BIGINT | Block number (dedup key; duplicates from resumed runs removed keeping latest) |
| timestamp | BIGINT | Unix seconds |
| ts | TIMESTAMP | `to_timestamp(timestamp)` |
| date | DATE | UTC date |
| hash, fee_recipient | VARCHAR | Block hash; coinbase address (lowercase) |
| gas_limit, gas_used | BIGINT | Execution gas |
| base_fee_per_gas | BIGINT | EIP-1559 execution base fee (wei) |
| blob_gas_used | BIGINT | Blob gas consumed in block (131072 per blob) |
| excess_blob_gas | BIGINT | EIP-4844 excess blob gas (fee-state variable) |
| blob_count | INTEGER | `blob_gas_used / 131072` |
| regime | VARCHAR | Fork regime via as-of join on `timestamp` (dencun/pectra/fusaka/bpo1/bpo2) |
| target_blobs, max_blobs | INTEGER | Blob schedule of the regime |
| update_fraction | BIGINT | BLOB_BASE_FEE_UPDATE_FRACTION of the regime |
| computed_blob_base_fee_wei | DOUBLE | `exp(excess_blob_gas/update_fraction)` rounded, =1 at floor; double-precision approximation of the spec's fake_exponential; **valid in every regime incl. post-Fusaka**: EIP-7918 alters the excess-gas transition, which the header already records, not the fee function (agrees with observed prices within max(0.1%, 1 wei) on 100% of txs) — observed prices from blob_txs remain preferred at tx level where available |
| at_floor | BOOLEAN | `excess_blob_gas = 0` (blob base fee pinned at 1 wei) |
| at_max | BOOLEAN | `blob_count >= max_blobs` (supply constraint binds) |
| utilization | DOUBLE | `blob_count / target_blobs` |
| tx_count | INTEGER | Transactions in block |
| size_bytes | BIGINT | RLP block size |

### 2.2 `blocks_daily.csv` / `.parquet` and `fees_hourly.csv` — aggregates of 2.1
date/hour, regime, n_blocks, blobs, avg_blob_count, avg_utilization, share_at_floor, share_at_max, avg/med/max_computed_fee_wei. share_at_floor and share_at_max are the key boundary-regime incidence series.

### 2.3 `blob_txs.parquet` — one row per blob-carrying (type-3) transaction (primary demand-side micro data; `blob_txs_sample.csv` = first 50k rows for inspection)
| field | type | description |
|---|---|---|
| hash | VARCHAR | Tx hash, lowercase (dedup key) |
| block_number, block_ts, block_time, date | BIGINT/TIMESTAMP/DATE | Inclusion block and its authoritative header timestamp |
| tx_index | INTEGER | Position in block |
| from_address, to_address | VARCHAR | Lowercase; `from` = batcher EOA |
| rollup | VARCHAR | Blobscan's rollup tag, else batcher-address map from `config.js`, else 'unknown' |
| blob_count | INTEGER | Blobs in tx (`blob_gas_used/131072`, fallback: length of listed blobs) |
| blob_gas_used | BIGINT | Blob gas purchased by the tx |
| max_fee_per_blob_gas | HUGEINT | Bid cap (wei per blob gas) — censoring bound for elasticity estimation |
| observed_blob_gas_price_wei | DOUBLE | Actual blob gas price paid: Blobscan `blobGasPrice`, fallback `blobGasBaseFee/blob_gas_used`; authoritative incl. post-Fusaka EIP-7918 |
| computed_blob_base_fee_wei | DOUBLE | Header-derived EIP-4844 fee of inclusion block |
| effective_blob_gas_price_wei | DOUBLE | observed if present else computed |
| blob_fee_wei | DOUBLE | `blob_gas_used × effective_blob_gas_price_wei` |
| regime | VARCHAR | Fork regime of inclusion block |
| blob_as_calldata_gas_used | BIGINT | Counterfactual calldata gas (for calldata-vs-blob substitution and EIP-7623 analysis) |
| gas_price, category, block_timestamp_raw | HUGEINT/VARCHAR | Execution gas price; Blobscan category; raw API timestamp (provenance) |

### 2.4 `rollup_daily.parquet` / `.csv` — rollup × date demand panel (main estimation panel)
rollup, date, n_txs, n_blobs, blob_gas_used, avg_blobs_per_tx (batch-size intensive margin), blob_fee_eth, blob_fee_usd (ETH close join), med_interpost_s and mean_interpost_s (posting-frequency intensive margin, from within-rollup gaps between consecutive posts), share_of_day (rollup's share of that day's blobs).

### 2.5 `da_cross_daily.parquet` / `.csv` — Ethereum vs Celestia daily cross-market panel (extensive margin / migration)
date, eth_blobs, eth_blob_gas, eth_fee_eth, eth_fee_usd, cel_bytes (Celestia blob bytes), cel_blobs, cel_fee_tia (fee series ÷ 1e6 utia/TIA), cel_fee_usd (TIA close join). Celestia's `fee` series is Celenium's daily total fee in utia; we treat it as total DA spend per day — validate this assumption against a few days of per-block data before welfare calculations.

### 2.6 `prices_daily.csv` — asset (ETH/TIA), date, open, high, low, close, volume, source.
Built by the merge in `datasets/` but left out of the deposit bundle (see 1.4); regenerate with script 05.

### 2.7 `celestia_rollup_daily.csv` — rollup_id, slug, metric (size|blobs_count|fee), date, value; long-format per-rollup Celestia usage (deduplicated on rollup_id×metric×date).

### 2.8 `growthepie_fundamentals.parquet` — metric_key, origin_key (L2 slug), date, value; long-format daily L2 fundamentals for demand normalization.

### 2.9 `mempool_inclusion.parquet` (only if script 07 was run)
hash, rollup, block_number, block_ts, date, first_seen (earliest mempool observation across the Xatu sensor fleet), n_sensors (distinct Xatu sensors that saw the tx on its first-seen day), inclusion_delay_s (= block_ts − epoch(first_seen)), blob_count, max_fee_per_blob_gas, effective_blob_gas_price_wei, regime. This is the queueing/latency outcome for the floor-regime rationing analysis. Sensor coverage is partial; treat first_seen as an upper bound on true broadcast time.

### 2.10 `reports/validation_report.json`
- `sources.el_headers`: raw vs dedup rows, duplicate count, block range, `missing_blocks_total` + first 50 gap ranges, non-monotonic timestamp count.
- `sources.blobscan_txs`: raw vs dedup counts, date range, null rates for key fields, `unknown_rollup_share`, and `block_coverage` — per-block sum of tx blob gas reconciled against header `blob_gas_used` (`blocks_gas_mismatch` should be ~0; nonzero indicates Blobscan gaps → re-run 02 for those windows).
- `regimes`: per-regime block counts, blob stats, floor/max shares, max observed blob count (must equal configured max_blobs).
- `weekly_max_blobs`: empirical fork-boundary check (see README.md, section Blob schedule).
- `fork_config`, `errors`, `notes`.

## 2.11 Deposit bundle (`release/`, produced by script 09)

Everything in §2 except `prices_daily.csv` (see 1.4), plus `README.md` (the pipeline documentation) and:

| file | purpose |
|---|---|
| `CODEBOOK.md` | Generated from the deposited files themselves: for each file, its size, SHA-256, row count, and every column with its observed type. Complements this document, which carries the semantics. |
| `MANIFEST-SHA256.txt` | `sha256sum -c` compatible checksum list. |
| `manifest.json` | Machine-readable manifest: per-file bytes, SHA-256/MD5/SHA-1, row and column counts, description, Dataverse categories, plus the `fork_config` in force when the data was built. |
| `validation_report.json` | Copy of `reports/validation_report.json` (see §2.10). |
| `dataverse_dataset.json` | Dataverse citation-metadata payload built from `deposit.config.json`. Not itself deposited as a file — it is the metadata of the dataset record. |
| `pipeline-source.tar.gz` | Pipeline source, only when `INCLUDE_SOURCE=1`. Shipped as a tarball rather than a zip because Dataverse unpacks zip uploads into loose files. |

Oversized Parquet files are split into yearly parts (`blob_txs_2024.parquet`, `blob_txs_2025.parquet`, ...). The parts concatenate back losslessly: `SELECT * FROM read_parquet('blob_txs_*.parquet')` in DuckDB, or `pq.ParquetDataset` in pyarrow.

Provenance for the deposit itself — DOI, landing page, per-file database ids and checksums as accepted by the server — is recorded in `reports/dataverse_deposit.json` by script 10.

## 3. Known caveats (also emitted into the validation report)
1. The blob schedule in `config.js` (activation timestamps, targets, maxima, update fractions) is verified block by block against the excess-blob-gas update rule of each regime; every block in the panel is explained by its regime's rule. See `forks/` and `analysis/01_data_audit.py` in the source repository. Earlier versions of this file called the Fusaka, BPO1 and BPO2 values placeholders; they have since been verified.
2. `computed_blob_base_fee_wei` is valid post-Fusaka: EIP-7918 changes the excess-blob-gas transition, which the header's `excess_blob_gas` already reflects, not the price function. It matches `observed_blob_gas_price_wei` within max(0.1%, 1 wei) on 100% of blob txs in every regime. (Earlier versions of this file said it ignored EIP-7918; that was wrong.) What would be wrong post-Fusaka is re-simulating the excess path with the plain EIP-4844 update rule.
3. "Blob bytes" on Ethereum = blob gas purchased (128 KiB units of capacity), not payload bytes actually used inside blobs; Celestia `blobs_size` is actual bytes posted — account for blob fullness when comparing levels across chains.
4. Blobscan JSON is stored raw and parsed defensively (multiple candidate key names) to survive schema drift; unrecognized fields are simply ignored, never lost (raw NDJSON is kept).
5. Rollup labels come from Blobscan's curated tagging with a static batcher-address fallback; the residual is labeled `unknown` and its share is reported.

## 4. Licence

The deposit is released under CC BY 4.0, consistent with the licences of its growthepie and Xatu / ethPandaOps
inputs (both CC BY 4.0). Batcher labels from the blob-list registry are CC0 1.0. Blob transactions are indexed by
Blobscan (Blossom Labs). Source code: https://github.com/farbodghasemlu/ethereum-blob-demand (MIT).
