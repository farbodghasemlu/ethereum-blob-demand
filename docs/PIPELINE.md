# Ethereum blob market: data collection and merge pipeline

A Node.js pipeline that collects, validates, deduplicates and merges public data on Ethereum's data-availability
(blob) market from the Dencun upgrade onward: every execution block header, every blob-carrying transaction with its
rollup label, daily layer-2 fundamentals, and first mempool sightings of blob transactions. It produces the datasets
deposited at Harvard Dataverse, doi:10.7910/DVN/4AOXKT, and can rebuild them from scratch. Field-level documentation
is in `DATASETS.md`.

All sources are free and need no API key. Exchange price data are collected but not redistributed (see
"Redistribution" below).

## Prerequisites

- Node.js 18.17 or later (tested on Node 22).
- `npm install` (one dependency: `duckdb`, with prebuilt binaries for Linux, macOS and Windows).
- Disk: about 1 GB for header CSVs, 3 to 8 GB for Blobscan NDJSON, and up to 5 GB for Xatu mempool CSVs, plus
  working space for the DuckDB merge. Budget about 20 GB.

## Run order

```
npm install
npm run headers      # 01: execution-layer block headers via public JSON-RPC (the longest step)
npm run blobtxs      # 02: every blob (type-3) transaction via Blobscan
npm run blobstats    # 03: Blobscan aggregate statistics (cross-validation, optional)
npm run celestia     # 04: Celestia rollup registry and daily series via Celenium (see Troubleshooting)
npm run prices       # 05: ETH and TIA daily OHLCV (Binance, Coinbase fallback)
npm run growthepie   # 06: layer-2 daily fundamentals (growthepie)
npm run labels       # 11: batcher-address labels from the blob-list registry (writes rollups.json)
npm run mempool      # 07: optional: first mempool sightings from Xatu (type-3 transactions only)
npm run merge        # 08: validate, deduplicate, merge -> datasets/ and reports/
npm run package      # 09: build the deposit bundle (set RELEASE_DIR to a new directory)
npm run deposit      # 10: sync the bundle to a Dataverse installation
```

`npm run all` runs 01 to 06, then 08. Script 07 is excluded from `all`; run it separately for mempool inclusion
delays. `run_pipeline.sh` runs a list of steps with retries.

Every collector is resumable: state lives in `state/*.json`, raw data are appended to shards in `data/raw/`, and
duplicates created by re-runs are removed in the merge. To force a full re-collection, delete the relevant `state/`
file and `data/raw/` subdirectory. Script 08 rebuilds every dataset from `data/raw/` and can be re-run at any time.

## Blob schedule

`config.js` holds the blob schedule (activation timestamp, target, maximum and base-fee update fraction for each
regime). The values were verified from the data, not taken from announcements:

- `forks/pin_forks.js` brackets each activation between the last block that fits only the old target and the
  first block that fits only the new target under the EIP-4844 excess update rule, and lists the beacon-epoch
  boundaries inside the bracket.
- `forks/detect_7918.js` classifies every block by the rule that explains its excess (ordinary EIP-4844 or the
  EIP-7918 reserve), which identifies Fusaka, whose target and maximum equal Pectra's.
- `forks/infer_target.js` and `forks/verify_forks.js` report the implied target per block and simple empirical
  checks (first block above each old maximum, last block at the fee floor).
- `analysis/01_data_audit.py` recomputes every block's excess from its parent under the regime's own rule and
  finds no unexplained block in any regime.

A `forks.json` file in the repository root, with the same shape as `DEFAULT_FORKS`, overrides the defaults; re-run
`npm run merge` after changing it.

## Environment variables

| Variable | Script | Default | Meaning |
|---|---|---|---|
| `RPC_URLS` | 01, 02 | five public endpoints | Comma-separated JSON-RPC URLs, rotated on failure |
| `START_BLOCK` | 01, 02 | 19426587 (Dencun) | First block to collect |
| `END_BLOCK` | 01, 02 | latest | Last block to collect |
| `BATCH` | 01 | 20 | Blocks per JSON-RPC batch request |
| `CONCURRENCY` | 01 | 4 | Parallel batch requests |
| `STRIDE` | 01 | 1 | Collect every Nth block (e.g. 100 for a quick test) |
| `WINDOW` | 02 | 10000 | Blocks per Blobscan query window |
| `PAGE_SIZE` | 02 | 100 | Blobscan page size |
| `RATE_MS` | 02, 04 | 350 / 250 | Pause between API calls (ms) |
| `CEL_FROM` | 04 | 1698710400 | Celestia collection start (unix; mainnet launch) |
| `PRICE_START` | 05 | 2023-10-01 | First price date |
| `XATU_START`, `XATU_END` | 07 | 2024-03-13, two days ago | Mempool date range (YYYY-MM-DD) |
| `XATU_TABLE`, `XATU_BASE` | 07 | mempool_transaction | Xatu table and base URL |
| `DUCKDB_MEMORY_LIMIT` | 07, 08 | 4GB | DuckDB memory cap |
| `BLOBSCAN_API`, `CELENIUM_API`, `GROWTHEPIE_URL` | 02 to 06 | official URLs | Endpoint overrides |
| `BLOBLIST_URL` | 11 | latest blob-list release | Label registry URL |
| `RELEASE_DIR` | 09, 10 | release | Deposit bundle directory |
| `RELEASE_EXCLUDE` | 09 | prices_daily.csv | Datasets left out of the bundle |
| `ALLOW_OVERWRITE_RELEASE` | 09 | unset | `1` lets script 09 replace a non-empty bundle directory |
| `MAX_FILE_MB` | 09 | 2048 | Split Parquet files larger than this |
| `INCLUDE_SOURCE` | 09 | unset | `1` bundles the pipeline source |
| `DATAVERSE_URL` | 10 | dataverse.harvard.edu | Dataverse installation |
| `DATAVERSE_TOKEN` | 10 | none | API token (required unless `DRY_RUN=1`) |
| `DATAVERSE_PARENT` | 10 | none | Collection alias for a new dataset |
| `DATAVERSE_DOI` | 10 | from state | Deposit into an existing dataset |
| `DRY_RUN` | 10 | unset | `1` previews actions without writing |
| `PRUNE` | 10 | unset | `1` deletes draft files that are no longer in the bundle |
| `PUBLISH` | 10 | unset | `major` or `minor` publishes after uploading |

## Runtime

- 01: about 6.6M blocks. Against public RPCs expect 100 to 400 blocks per second, 5 to 18 hours in total. Use
  `STRIDE=25` for a pilot run.
- 02: several million blob transactions at about 3 requests per second, 4 to 10 hours.
- 05, 06, 11: minutes. 06 downloads one large JSON; if Node runs out of memory use
  `NODE_OPTIONS=--max-old-space-size=8192 npm run growthepie`.
- 07: 1 to 20 seconds per day depending on the size of the day's Xatu file.
- 08: minutes to an hour.

## Troubleshooting

- **Binance HTTP 451 or 403**: geo-blocked; script 05 falls back to Coinbase Exchange.
- **Celenium HTTP 403**: Celenium's CDN blocks some datacenter IP ranges. Run script 04 from a residential
  connection. The published deposit contains no Celenium data; its Celestia series come from growthepie.
- **RPC failures**: endpoints rotate automatically; supply your own through `RPC_URLS`.
- **Blobscan 429**: increase `RATE_MS`.
- **DuckDB install problems**: `npm rebuild duckdb`, or use Node LTS.
- **Xatu**: script 07 probes daily and hourly file layouts, decodes the BLOB-typed hash columns, keeps one row per
  transaction, and retries failed days on the next run.

## Outputs

Datasets land in `datasets/` (Parquet and CSV) and the data-quality report in `reports/validation_report.json`.
`DATASETS.md` documents every file and field.

## Building and depositing the archive

Script 09 builds a self-contained bundle: every dataset except those in `RELEASE_EXCLUDE`, the validation
report, this file as `README.md`, `DATASETS.md`, a generated `CODEBOOK.md`, `MANIFEST-SHA256.txt`, a
machine-readable `manifest.json` and `dataverse_dataset.json` (citation metadata). It refuses to overwrite a
non-empty directory, so package a new version into a new directory:

```
RELEASE_DIR=release_v3 npm run package
```

It reads the citation metadata from `deposit.config.json` and creates a template on first run. Script 10 syncs a
bundle to Dataverse: it compares checksums with the server, uploads new files, replaces changed ones, and with
`PRUNE=1` deletes draft files that are no longer in the bundle. Uploads use `tabIngest=false`, which stops
Dataverse converting CSVs into a tabular format that mangles large integers.

```
export DATAVERSE_TOKEN=...
RELEASE_DIR=release_v3 DRY_RUN=1 npm run deposit
RELEASE_DIR=release_v3 npm run deposit
```

The dataset stays an unpublished draft until `PUBLISH=major`. Publishing cannot be undone: a published version can
be deaccessioned but not deleted.

## Redistribution and attribution

- Block headers are public Ethereum chain data.
- Blob transactions come from the Blobscan API (Blossom Labs). Batcher labels come from Blobscan and the blob-list
  registry (CC0 1.0).
- Layer-2 fundamentals and data-availability series come from growthepie, CC BY 4.0.
- Mempool observations come from Xatu / ethPandaOps, CC BY 4.0.
- Exchange prices (Binance, Coinbase) are subject to the exchanges' terms, which restrict redistribution. The
  bundle leaves them out; script 05 regenerates them.

The deposit is released under CC BY 4.0, consistent with the growthepie and Xatu inputs. Please credit these
sources when you use the data.
