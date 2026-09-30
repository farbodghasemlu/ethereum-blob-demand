# Analysis — run order

Setup: `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.lock`
Run everything: `./run_all.sh` (about 6 minutes; regenerates every output from an empty `output/` and `data/`). Inputs are read from `../release/` (deposit version 2, read-only), set in `common.py`.

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
| `10_render_paper.py` | `paper/draft.md` from `paper/draft_template.md`, `output/numbers/*.json` and `output/tables/*.csv` |
| `11_build_latex.py` | `paper/arxiv/main.tex`, `main.pdf`, and `paper/arxiv_submission.tar.gz` (the arXiv upload) |

`est.py` holds the shared event-design estimator; `common.py` paths, fork table and pricing-regime split.
`notes/PRESPEC.md` is the locked pre-specification; `notes/DECISIONS.md` the judgement-call log.

LaTeX: script 11 uses pandoc (from the `pypandoc_binary` package) and compiles with Tectonic if `tools/tectonic` exists
(`curl --proto '=https' -sSf https://drop-sh.fullyjustified.net | sh`, then move the binary to `tools/`). Without it,
`main.tex` is still written.

Reproducibility note: DuckDB aggregates in parallel, so floating-point sums can differ in the 13th significant digit
between runs. Every number in the paper is rounded well above that level and is stable.

Paper: every number in `paper/draft.md` is filled from `output/numbers/*.json` or `output/tables/*.csv` by script 10;
the specification fixed before estimation is `notes/PRESPEC.md` (commit 65ae268), and every judgement call is in
`notes/DECISIONS.md`. References in `paper/references.bib` were verified against Crossref, arXiv and eips.ethereum.org.
