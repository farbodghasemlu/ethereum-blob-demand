"""00 — Verify the read-only deposit against MANIFEST-SHA256.txt before any analysis.
Output: output/logs/00_verify_release.txt. Exits non-zero on any mismatch."""
import hashlib, sys, platform
from common import REL, LOG
import duckdb, pandas, pyfixest

lines, bad = [], 0
for row in (REL / "MANIFEST-SHA256.txt").read_text().splitlines():
    want, name = row.split(maxsplit=1)
    h = hashlib.sha256()
    with open(REL / name, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    ok = h.hexdigest() == want
    bad += not ok
    lines.append(f"{'OK  ' if ok else 'FAIL'} {name}")
lines += ["", f"python {platform.python_version()}  duckdb {duckdb.__version__}  pandas {pandas.__version__}  pyfixest {pyfixest.__version__}",
          f"{len(lines) - bad} OK, {bad} FAILED"]
(LOG / "00_verify_release.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
sys.exit(1 if bad else 0)
