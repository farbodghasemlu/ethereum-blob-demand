"""10 — Render the paper draft: fills paper/draft_template.md with numbers from output/numbers/*.json.
Output: paper/draft.md. Fails loudly on any placeholder without a number, so no number is ever typed by hand.
"""
import json
from common import ROOT, NUM

SOURCES = {"a": "01_audit", "d": "03_descriptives", "h": "04_headline", "sc": "05_spec_curve",
           "mp": "06_mempool", "ix": "07_intraday", "w": "08_welfare", "pt": "09_passthrough"}
vals = {k: json.loads((NUM / f"{f}.json").read_text()) for k, f in SOURCES.items()}
tpl = (ROOT / "paper" / "draft_template.md").read_text()
vals["pinv"] = 1 / vals["h"]["n_placebo"]         # smallest attainable permutation p-value
(ROOT / "paper" / "draft.md").write_text(tpl.format_map(vals))
print("wrote paper/draft.md")
