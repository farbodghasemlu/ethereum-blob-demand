"""Shared paths and constants. The fork table is verified block by block in script 01 (DECISIONS D-30)."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent
REL = (ROOT / ".." / "release").resolve()   # READ-ONLY archival deposit, version 2 (DECISIONS D-26, D-31)
OUT = ROOT / "output"
TAB, FIG, LOG = OUT / "tables", OUT / "figures", OUT / "logs"
DATA = ROOT / "data"                          # derived datasets built by scripts here
for d in (TAB, FIG, LOG, DATA):
    d.mkdir(parents=True, exist_ok=True)

def rel(name: str) -> str:
    return str(REL / name)

BLOB_TXS, BLOCKS, ROLLUP_DAILY = rel("blob_txs.parquet"), rel("blocks_panel.parquet"), rel("rollup_daily.parquet")
DA_CROSS, DA_LAYERS = rel("da_cross_daily.parquet"), rel("da_layers_daily.csv")
GROWTHEPIE = rel("growthepie_fundamentals.parquet")
# Exchange prices are not redistributed in the deposit (DECISIONS D-36); `npm run prices` (script 05) writes them here.
ETH_PRICES_CSV = (ROOT / ".." / "data" / "raw" / "prices" / "ETH_daily.csv").resolve()
ETH_CLOSE = f"(SELECT date::DATE AS date, close FROM read_csv('{ETH_PRICES_CSV}'))"

GAS_PER_BLOB = 131_072          # blob gas per blob = 128 KiB of purchased capacity
WEI_PER_ETH = 1e18
WEI_PER_GWEI = 1e9

# name, activation unix ts, target, max
FORKS = [
    ("dencun", 1710338135, 3, 6),
    ("pectra", 1746612311, 6, 9),
    ("fusaka", 1764798551, 6, 9),
    ("bpo1", 1765290071, 10, 15),
    ("bpo2", 1767747671, 14, 21),
]
REGIMES = [f[0] for f in FORKS]
# The two pricing experiments. Never pool across them.
PRICING_REGIME = {"dencun": "eip4844_floor", "pectra": "eip4844_floor",
                  "fusaka": "eip7918_reserve", "bpo1": "eip7918_reserve", "bpo2": "eip7918_reserve"}

def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute("SET threads TO 8")
    return c

NUM = OUT / "numbers"          # key results per script, consumed by the paper renderer
NUM.mkdir(parents=True, exist_ok=True)


def save_numbers(name: str, values: dict) -> None:
    import json, numpy as np
    conv = lambda v: v.item() if isinstance(v, np.generic) else (str(v) if hasattr(v, "isoformat") else v)
    (NUM / f"{name}.json").write_text(json.dumps({k: conv(v) for k, v in values.items()}, indent=1) + "\n")
