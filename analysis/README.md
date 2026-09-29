# Analysis — run order

Setup: `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.lock`
Run everything: `./run_all.sh` (≈2 min). Inputs are read from `../release/` only; nothing is written there.

| script | produces |
|---|---|
| `00_verify_release.py` | `output/logs/00_verify_release.txt` — SHA-256 check of the deposit; aborts on mismatch |
| `01_data_audit.py` | `output/tables/audit_*.csv`, `output/logs/01_data_audit.md` — data problems later scripts must handle |
| `02_build_panels.py` | `data/day_panel.parquet` (unit: UTC day), `data/rollup_day_panel.parquet` (unit: rollup × day, posting days only) |
| `03_descriptives.py` | `output/tables/table1_regimes.{csv,md}`, `output/figures/fig1_market_timeseries.{pdf,png}` |

`common.py` holds paths, the fork table, and the pricing-regime split (EIP-4844 floor vs EIP-7918 reserve).
