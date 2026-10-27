"""Build the report as a standalone static site (Cloudflare Pages, nginx or any static host).

Usage: python -I scripts/05_site.py <repo_dir> <out_dir>

Wraps report/index.html in web/page.html, adds web/dash.js (a stand-in for the claude.ai dashboard
runtime) and web/theme.css, and copies the report scripts, d3 and the datasets from results/dash.
"""
import ast
import html
import re
import shutil
import sys
from pathlib import Path

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.stdout.reconfigure(encoding="utf-8")
rep, web = repo / "report", repo / "web"

# Dataset ids, titles and descriptions, read from report/build_store.py without running it.
tree = ast.parse((rep / "build_store.py").read_text(encoding="utf-8"))
DATASETS = next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "DATASETS")

if out.exists():
    shutil.rmtree(out)
(out / "data").mkdir(parents=True)
(out / "vendor").mkdir()

for name in ("dash.js", "theme.css", "_headers"):
    shutil.copy2(web / name, out / name)
for f in (web / "vendor").iterdir():
    shutil.copy2(f, out / "vendor" / f.name)
scripts = re.findall(r'<script src="([^"/]+\.js)"></script>', (rep / "index.html").read_text(encoding="utf-8"))
for name in scripts:
    shutil.copy2(rep / name, out / name)
for i in DATASETS:
    shutil.copy2(repo / "results" / "dash" / f"{i}.json", out / "data" / f"{i}.json")

# The report page is a fragment: its leading <style> goes to <head>, the rest into #dash-root.
frag = (rep / "index.html").read_text(encoding="utf-8")
m = re.match(r"\s*<style>\n?(.*?)</style>\n?", frag, re.S)
style, body = m.group(1), frag[m.end():]
items = "\n".join(f'    <li><a href="data/{i}.json" title="{html.escape(desc)}">{html.escape(title)}</a></li>'
                  for i, (_, title, desc) in DATASETS.items())
page = (web / "page.html").read_text(encoding="utf-8")
page = (page.replace("{{dataset_ids}}", " ".join(DATASETS)).replace("{{style}}", style.rstrip())
        .replace("{{datasets}}", items).replace("{{body}}", body.strip()))
(out / "index.html").write_text(page, encoding="utf-8")

size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
print(f"site -> {out}: {sum(1 for p in out.rglob('*') if p.is_file())} files, {size / 1024:.0f} KB")
