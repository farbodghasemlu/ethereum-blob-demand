"""11 — Build the arXiv LaTeX from paper/draft.md (rendered by 10).

paper/arxiv/main.tex        pandoc conversion (natbib citations, abstract in the front matter, PDF figures)
paper/arxiv/figures/*.pdf   figures from output/figures
paper/arxiv/main.pdf        compiled with Tectonic if tools/tectonic exists (skipped with a message otherwise)
paper/arxiv_submission.tar.gz  main.tex + main.bbl + references.bib + figures, the arXiv upload
"""
import re
import shutil
import subprocess
import tarfile
import pypandoc
from common import ROOT, FIG

PAPER = ROOT / "paper"
OUT = PAPER / "arxiv"
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "figures").mkdir(parents=True)

md = (PAPER / "draft.md").read_text()
front, body = md.split("\n---\n", 1)[0] + "\n", md.split("\n---\n", 1)[1]
abstract = re.search(r"# Abstract\n\n(.*?)\n\n# ", body, re.S).group(1)
body = body.replace(f"# Abstract\n\n{abstract}\n\n", "", 1)
body = re.sub(r"\n# References\s*$", "\n", body)                       # natbib prints its own heading
body = re.sub(r"\.\./output/figures/(\w+)\.png", r"figures/\1.pdf", body)
for f in re.findall(r"figures/(\w+)\.pdf", body):
    shutil.copy(FIG / f"{f}.pdf", OUT / "figures" / f"{f}.pdf")
shutil.copy(PAPER / "references.bib", OUT / "references.bib")

meta_abstract = "abstract: |\n" + "\n".join("  " + line for line in abstract.splitlines()) + "\n"
header = r"""header-includes: |
  \usepackage{etoolbox}
  \AtBeginEnvironment{longtable}{\footnotesize}
  \usepackage[margin=1in]{geometry}
  \usepackage{microtype}
biblio-style: plainnat
natbiboptions: authoryear,round
link-citations: true
"""
src = front.rstrip().rstrip("-").rstrip() + "\n" + meta_abstract + header + "---\n" + body
tex = pypandoc.convert_text(src, "latex", format="markdown", extra_args=["--standalone", "--natbib",
                            "--resource-path", str(OUT), "-V", "fontsize=11pt", "-V", "documentclass=article"])
(OUT / "main.tex").write_text(tex)
print("wrote", OUT / "main.tex")

tectonic = ROOT / "tools" / "tectonic"
if not tectonic.exists():
    print("tools/tectonic not found: main.tex written, PDF not compiled (see README)")
else:
    r = subprocess.run([str(tectonic), "--keep-intermediates", "--keep-logs", "main.tex"], cwd=OUT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("LaTeX compilation failed")
    warn = [l for l in (OUT / "main.log").read_text(errors="ignore").splitlines()
            if re.search(r"undefined|Missing character|Overfull \\hbox \((\d{2,})", l)]
    print(f"compiled {OUT / 'main.pdf'}; {len(warn)} warnings worth reading")
    for l in warn[:20]:
        print("  ", l)
    with tarfile.open(PAPER / "arxiv_submission.tar.gz", "w:gz") as tar:
        for name in ["main.tex", "main.bbl", "references.bib"]:
            tar.add(OUT / name, arcname=name)
        tar.add(OUT / "figures", arcname="figures")
    print("wrote", PAPER / "arxiv_submission.tar.gz")
