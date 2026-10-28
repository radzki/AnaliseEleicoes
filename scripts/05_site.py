"""Build the report as a standalone static site (Cloudflare Pages, nginx or any static host).

Usage: python -I scripts/05_site.py <repo_dir> <out_dir>

Wraps report/index.html in web/page.html, adds web/dash.js (a stand-in for the claude.ai dashboard
runtime) and web/theme.css, and copies the report scripts, d3 and the datasets from results/dash.
"""
import ast
import hashlib
import html
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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
for name in ("dash.js", "theme.css", "_headers", "robots.txt", "sitemap.xml", "404.html", "og.png"):
    shutil.copy2(web / name, out / name)
for d in ("vendor", "fonts"):
    shutil.copytree(web / d, out / d)
scripts = re.findall(r'<script src="([^"/]+\.js)"></script>', (rep / "index.html").read_text(encoding="utf-8"))
for name in scripts:
    shutil.copy2(rep / name, out / name)
for i in DATASETS:
    shutil.copy2(repo / "results" / "dash" / f"{i}.json", out / "data" / f"{i}.json")
# "Tente fraudar!" reads every runoff section from here (scripts/09_sim_data.py)
shutil.copytree(repo / "results" / "sim", out / "data" / "sim")


def fingerprint(text):
    """Link each local stylesheet and script with a hash of its contents (theme.css?v=1a2b3c4d5e).

    The host revalidates the HTML on every visit but lets browsers keep CSS and JS for hours, so
    without this a deploy could run new HTML with yesterday's stylesheet or scripts.
    """
    def stamp(m):
        f = out / m.group(2).lstrip("/")
        if not f.is_file():
            return m.group(0)
        return f'{m.group(1)}="{m.group(2)}?v={hashlib.sha256(f.read_bytes()).hexdigest()[:10]}"'
    return re.sub(r'(href|src)="(/?[\w./-]+\.(?:css|js))"', stamp, text)


(out / "404.html").write_text(fingerprint((out / "404.html").read_text(encoding="utf-8")), encoding="utf-8")

# The report page is a fragment: its leading <style> goes to <head>, the rest into #dash-root.
frag = (rep / "index.html").read_text(encoding="utf-8")
m = re.match(r"\s*<style>\n?(.*?)</style>\n?", frag, re.S)
style, body = m.group(1), frag[m.end():]
items = "\n".join(f'    <li><a href="data/{i}.json" title="{html.escape(desc)}">{html.escape(title)}</a></li>'
                  for i, (_, title, desc) in DATASETS.items())
# "Última atualização" in the footer: the time of the last commit (what was published), or of this
# build outside git. Brasília has had no daylight saving time since 2019, so UTC-3 all year.
try:
    stamp = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cI"], capture_output=True, text=True,
                           check=True).stdout.strip()
    updated = datetime.fromisoformat(stamp)
except (OSError, subprocess.CalledProcessError, ValueError):
    updated = datetime.now(timezone.utc)
updated = updated.astimezone(timezone(timedelta(hours=-3)))
page = (web / "page.html").read_text(encoding="utf-8")
page = (page.replace("{{updated_iso}}", updated.isoformat(timespec="minutes"))
        .replace("{{updated}}", f"{updated:%d/%m/%Y}, às {updated:%H}h{updated:%M}"))
page = (page.replace("{{dataset_ids}}", " ".join(DATASETS)).replace("{{style}}", style.rstrip())
        .replace("{{datasets}}", items).replace("{{body}}", body.strip()))
(out / "index.html").write_text(fingerprint(page), encoding="utf-8")

size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
print(f"site -> {out}: {sum(1 for p in out.rglob('*') if p.is_file())} files, {size / 1024:.0f} KB")
