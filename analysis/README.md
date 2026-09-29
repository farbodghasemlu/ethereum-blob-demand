# Analysis — run order

Setup: `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.lock`
Run everything: `./run_all.sh`. Inputs are read from the deposit directory set in `common.py` (read-only).

| script | produces |
|---|---|
| `00_verify_release.py` | SHA-256 check of the deposit against its manifest; aborts on mismatch |
| `01_data_audit.py` | `output/tables/audit_*.csv`, `output/logs/01_data_audit.md` |
| `02_build_panels.py` | `data/day_panel.parquet`, `data/rollup_day_panel.parquet`, `data/est_panel.parquet` (zero-filled rollup × day) |
| `03_descriptives.py` | Table 1, Figure 1 |
| `04_headline_pectra.py` | Table 2 (headline, PRESPEC), placebo inference (Figure 2), S1 total demand, S2 Fusaka, S5 log price |
| `05_spec_curve.py` | specification curve (Figure 3), per-rollup heterogeneity (Figure 4) — robustness |
| `06_mempool_mechanism.py` | mempool-to-inclusion delay by market state (Figure 5, Table 4) — mechanism (S3) |
| `07_exploratory_intraday.py` | intraday execution-base-fee analysis, BPO2 — exploratory (S4) |
| `08_welfare.py` | transfers, reserve deadweight loss, consistency check (Table 3) |
| `09_passthrough_posthoc.py` | POST HOC: L2 fee pass-through and L2 activity at Pectra, blob users vs non-blob chains (D-24, D-25) |
| `10_render_paper.py` | `paper/draft.md` from `paper/draft_template.md` + `output/numbers/*.json` |

`est.py` holds the shared event-design estimator; `common.py` paths, fork table and pricing-regime split.
`notes/PRESPEC.md` is the locked pre-specification; `notes/DECISIONS.md` the judgement-call log.
