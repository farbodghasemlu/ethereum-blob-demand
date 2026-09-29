"""Shared paths and constants. Fork table is the established regime table in the project notes."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent
REL = (ROOT / ".." / "release").resolve()   # READ-ONLY archival deposit
OUT = ROOT / "output"
TAB, FIG, LOG = OUT / "tables", OUT / "figures", OUT / "logs"
DATA = ROOT / "data"                          # derived datasets built by scripts here
for d in (TAB, FIG, LOG, DATA):
    d.mkdir(parents=True, exist_ok=True)

def rel(name: str) -> str:
    return str(REL / name)

BLOB_TXS, BLOCKS, ROLLUP_DAILY = rel("blob_txs.parquet"), rel("blocks_panel.parquet"), rel("rollup_daily.parquet")
DA_CROSS, DA_LAYERS = rel("da_cross_daily.parquet"), rel("da_layers_daily.csv")
GROWTHEPIE, PRICES = rel("growthepie_fundamentals.parquet"), rel("prices_daily.csv")

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
