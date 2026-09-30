# Ethereum blob demand: data pipeline and replication package

This repository contains the code that builds a public dataset on Ethereum's data-availability (blob) market and
the analysis behind the working paper *Demand Under a Mechanical Price: Elasticity and Welfare in Ethereum's
Data-Availability Market* (Farbod Ghasemlu, 2026). You can use it to:

- rebuild the dataset from public sources, block by block, from the Dencun upgrade (March 2024) onward;
- reproduce every number, table and figure in the paper from the deposited data;
- reuse the verified blob schedule below, derived from the protocol's own update rule.

**The repository holds no data.** The data are deposited at Harvard Dataverse:
[doi:10.7910/DVN/4AOXKT](https://doi.org/10.7910/DVN/4AOXKT) (CC BY 4.0).

## Verified blob schedule

Activation times and parameters of each blob regime on Ethereum mainnet, verified block by block: every block's
excess blob gas is recomputed from its parent under the regime's own rule (EIP-4844 through Pectra, EIP-7918 from
Fusaka), and every block in the 6,650,444-block panel is explained.

| regime | activation (unix) | activation (UTC) | target | max | update fraction | blocks in panel |
|---|---|---|---|---|---|---|
| dencun | 1710338135 | 2024-03-13 13:55:35 | 3 | 6 | 3,338,477 | 3,004,497 |
| pectra | 1746612311 | 2025-05-07 10:05:11 | 6 | 9 | 5,007,716 | 1,504,610 |
| fusaka | 1764798551 | 2025-12-03 21:49:11 | 6 | 9 | 5,007,716 | 40,084 |
| bpo1 | 1765290071 | 2025-12-09 14:21:11 | 10 | 15 | 8,346,193 | 203,605 |
| bpo2 | 1767747671 | 2026-01-07 01:01:11 | 14 | 21 | 11,684,671 | 1,897,648 |

The panel ends at block 26,077,030 (28 September 2026).

Three details matter if you reuse the schedule:

- **BPO1 activated at 14:21:11 UTC on 9 December 2025.** A date-level reading of the announced activation
  (midnight UTC) puts it 14 hours 21 minutes early. For BPO2 the same reading is 1 hour 1 minute early.
- **Fusaka is identified by the update rule, not only by the fee floor disappearing.** Its target and maximum
  equal Pectra's, but the EIP-4844 rule mispredicts 29.5% of Fusaka blocks; the EIP-7918 reserve rule explains
  all of them.
- **At a fork boundary, clients price the parent block under the new schedule** when evaluating the EIP-7918
  reserve. The BPO1 activation block is consistent only with that convention.

Scripts: [`forks/pin_forks.js`](forks/pin_forks.js) brackets each activation between blocks that fit only the old
or only the new target; [`forks/detect_7918.js`](forks/detect_7918.js) classifies blocks by the rule that explains
them; [`analysis/01_data_audit.py`](analysis/01_data_audit.py) recomputes every block's excess and writes the
verification table (`audit_fork_rules.csv`).

## Reproduce the paper

The paper's numbers, tables and figures are tracked in `analysis/paper/inputs/`, so the paper builds from a clean
clone without the data:

```
cd analysis
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.lock
.venv/bin/python 10_render_paper.py      # paper/draft.md
.venv/bin/python 11_build_latex.py       # paper/arxiv/main.tex, main.pdf and the arXiv bundle
```

Compiling the PDF needs [Tectonic](https://tectonic-typesetting.github.io) on the `PATH` (or at
`analysis/tools/tectonic`); without it, script 11 still writes `main.tex`.

To regenerate every result from the data:

```
# 1. download the deposit into release/ and check it
curl -L -o deposit.zip "https://dataverse.harvard.edu/api/access/dataset/:persistentId/?persistentId=doi:10.7910/DVN/4AOXKT"
unzip deposit.zip -d release && (cd release && sha256sum -c MANIFEST-SHA256.txt)

# 2. regenerate the exchange prices, which the deposit does not redistribute
npm install && npm run prices

# 3. run the analysis (about 6 minutes)
cd analysis && ./run_all.sh
```

`analysis/README.md` lists the scripts and what each produces.

## Rebuild the data

The collection pipeline in the repository root runs on its own; see [`docs/PIPELINE.md`](docs/PIPELINE.md) for
the run order, runtimes and environment variables, and [`DATASETS.md`](DATASETS.md) for every field.

```
npm install
npm run headers && npm run blobtxs && npm run prices && npm run growthepie && npm run labels
npm run mempool      # optional: first mempool sightings from Xatu (Dencun and Pectra in the deposit)
npm run merge        # builds datasets/ and reports/validation_report.json
```

Script 04 (Celestia via Celenium) is optional; Celenium blocks some datacenter networks, and the deposit's
Celestia series come from growthepie instead.

## Methods audit trail

- [`analysis/notes/PRESPEC.md`](analysis/notes/PRESPEC.md): the specification we fixed and committed before
  estimation, with a dated revision note recording why the primary outcome changed.
- [`analysis/notes/DECISIONS.md`](analysis/notes/DECISIONS.md): every judgement call, with alternatives, reasons
  and sensitivity, including the premises that turned out wrong.

## Citation

Please cite both the paper and the dataset. Citation metadata for this repository is in
[`CITATION.cff`](CITATION.cff).

> Ghasemlu, Farbod (2026). *Ethereum Blob (EIP-4844) Data-Availability Market: Block, Transaction, and Rollup
> Panels.* Harvard Dataverse. https://doi.org/10.7910/DVN/4AOXKT

## Attribution

- Blob transactions: [Blobscan](https://blobscan.com) (Blossom Labs).
- Batcher labels: Blobscan and the [blob-list](https://github.com/tirante-dev/blob-list) registry (CC0 1.0).
- Layer-2 fundamentals and data-availability series: [growthepie](https://www.growthepie.xyz), CC BY 4.0.
- Mempool observations: [Xatu / ethPandaOps](https://ethpandaops.io), CC BY 4.0.
- Block headers: public Ethereum chain data.
- Exchange prices (Binance, Coinbase) are regenerated locally and not redistributed.

## Licence

Code: MIT (see [`LICENSE`](LICENSE)). Data: CC BY 4.0, as deposited at Harvard Dataverse.
