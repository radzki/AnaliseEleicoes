"""Build the report as a standalone static site (Cloudflare Pages, nginx or any static host).

Usage: python -I scripts/05_site.py <repo_dir> <out_dir>

Wraps report/index.html in web/page.html, adds web/dash.js (a stand-in for the claude.ai dashboard
runtime) and web/theme.css, and copies the report scripts, d3 and the datasets from results/dash.

The page's text is in locales/: each {{key}} in report/index.html, web/page.html and web/404.html is
filled from it, and its "js." strings go to i18n.js for the scripts (vf.t in core.js). pt-BR.json is
the source and builds the page at /; every other locales/<lang>.json builds /<lang>/. A translated
entry is {"text": ..., "from": <hash of the Portuguese it was translated from>}: when the Portuguese
has changed since, or the entry is missing, the page shows the Portuguese, marked, until it is
translated again. A translation whose tags or {placeholders} differ from the Portuguese stops the build.
"""
import ast
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.stdout.reconfigure(encoding="utf-8")
rep, web, loc = repo / "report", repo / "web", repo / "locales"
SITE = "https://eleicoes.radzkitech.com/"

# Dataset ids, read from report/build_store.py without running it (names and descriptions: locales/, data.<id>.*).
tree = ast.parse((rep / "build_store.py").read_text(encoding="utf-8"))
DATASETS = next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "DATASETS")

if out.exists():
    shutil.rmtree(out)
(out / "data").mkdir(parents=True)
for name in ("dash.js", "theme.css", "_headers", "robots.txt", "404.html", "og.png"):
    shutil.copy2(web / name, out / name)
for d in ("vendor", "fonts"):
    shutil.copytree(web / d, out / d)
for f in web.glob("og-*.png"):  # the link-preview card of each translation (scripts/06_og_image.py)
    shutil.copy2(f, out / f.name)
scripts = re.findall(r'<script src="([^"/]+\.js)"></script>', (rep / "index.html").read_text(encoding="utf-8"))
for name in scripts:
    if name != "i18n.js":  # written per language below
        shutil.copy2(rep / name, out / name)
for i in DATASETS:
    shutil.copy2(repo / "results" / "dash" / f"{i}.json", out / "data" / f"{i}.json")
# "Tente fraudar!" reads every runoff section from here (scripts/09_sim_data.py)
shutil.copytree(repo / "results" / "sim", out / "data" / "sim")


# --- text --------------------------------------------------------------------------------------------
PT = json.loads((loc / "pt-BR.json").read_text(encoding="utf-8"))
# the language links name each language in itself; the order is the order of the links
NAMES = {"pt-BR": "Português", "en": "English", "es": "Español"}
LANGS = ["pt-BR"] + sorted(p.stem for p in loc.glob("*.json") if p.stem != "pt-BR")
for lang in LANGS:
    assert lang in NAMES, f"locales/{lang}.json: add its name to NAMES"
KEY = re.compile(r"\{\{([\w-]+(?:\.[\w-]+)+)\}\}")
TEXT_ATTRS = ("aria-label", "title", "alt", "placeholder")


def source_hash(text):
    """What a translated entry's "from" must equal: the Portuguese it was made from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def shape(s):
    """What a translation must keep: each tag with its attributes (but not the text of the attributes
    readers see) and each {placeholder}, in any order."""
    tags = [re.sub(r'\s(?:%s)="[^"]*"' % "|".join(TEXT_ATTRS), "", t) for t in re.findall(r"<[^>]+>", s)]
    return Counter(tags), Counter(re.findall(r"\{\w+\}", s))


def pending(key, text, note):
    """Portuguese shown in a translated page: marked where it is element content, as is where it is
    an attribute, a <title> or <meta>, an <option> or a script string."""
    kind = key.split(".")[-2] if key.count(".") >= 2 else ""
    if key.startswith(("js.", "shell.", "404.", "data.", "og.")) or kind in ("arialabel", "placeholder", "title", "alt", "option"):
        return text
    return f'<span class="vf-pending" lang="pt-BR" title="{html.escape(note)}">{text}</span>'


def texts(lang):
    if lang == "pt-BR":
        return PT, []
    tr = json.loads((loc / f"{lang}.json").read_text(encoding="utf-8"))
    bad = [k for k, e in tr.items() if k in PT and e["from"] == source_hash(PT[k]) and shape(e["text"]) != shape(PT[k])]
    if bad:
        sys.exit(f"locales/{lang}.json: tags or placeholders differ from the Portuguese in {', '.join(bad[:10])}")
    note = tr.get("shell.pending", {}).get("text", "")
    T, stale = {}, []
    for k, v in PT.items():
        e = tr.get(k)
        if k.startswith("404."):  # one 404 page for the whole site, in Portuguese
            T[k] = v
        elif e and e["from"] == source_hash(v):
            T[k] = e["text"]
        else:
            T[k] = pending(k, v, note)
            stale.append(k)
    return T, stale


def fill(text, T, where):
    def one(m):
        if m.group(1) not in T:
            sys.exit(f"{where}: no text for {{{{{m.group(1)}}}}} in locales/pt-BR.json")
        return T[m.group(1)]
    return KEY.sub(one, text)


def fingerprint(text, page_dir):
    """Link each local stylesheet and script with a hash of its contents (theme.css?v=1a2b3c4d5e).

    The host revalidates the HTML on every visit but lets browsers keep CSS and JS for hours, so
    without this a deploy could run new HTML with yesterday's stylesheet or scripts.
    """
    def stamp(m):
        path = m.group(2)
        f = out / path.lstrip("/") if path.startswith("/") else page_dir / path
        if not f.is_file():
            return m.group(0)
        return f'{m.group(1)}="{path}?v={hashlib.sha256(f.read_bytes()).hexdigest()[:10]}"'
    return re.sub(r'(href|src)="(/?[\w./-]+\.(?:css|js))"', stamp, text)


def up_one(text):
    """A page in /<lang>/: its links to the site's own files point one folder up (its i18n.js is its own)."""
    return re.sub(r'(href|src)="(?![a-z]+:|/|#|\.\./|i18n\.js)([^"]+)"', r'\1="../\2"', text)


# "Última atualização" in the footer: the time of the last commit (what was published), or of this
# build outside git. Brasília has had no daylight saving time since 2019, so UTC-3 all year.
try:
    stamp = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cI"], capture_output=True, text=True,
                           check=True).stdout.strip()
    updated = datetime.fromisoformat(stamp)
except (OSError, subprocess.CalledProcessError, ValueError):
    updated = datetime.now(timezone.utc)
updated = updated.astimezone(timezone(timedelta(hours=-3)))

url = {lang: SITE if lang == "pt-BR" else f"{SITE}{lang}/" for lang in LANGS}
alternates = "\n".join([f'<link rel="alternate" hreflang="{lang}" href="{url[lang]}">' for lang in LANGS]
                       + [f'<link rel="alternate" hreflang="x-default" href="{SITE}">'])
frag_src, page_src = (rep / "index.html").read_text(encoding="utf-8"), (web / "page.html").read_text(encoding="utf-8")

for lang in LANGS:
    T, stale = texts(lang)
    page_dir = out if lang == "pt-BR" else out / lang
    page_dir.mkdir(exist_ok=True)
    (page_dir / "i18n.js").write_text(
        f"// Written by scripts/05_site.py from locales/{lang}.json: the text of the report scripts.\n"
        "window.VF_I18N = " + json.dumps({k: v for k, v in T.items() if k.startswith("js.")}, ensure_ascii=False,
                                         indent=0) + ";\n", encoding="utf-8")
    current = ' aria-current="page"'
    links = "".join(f'<a href="{url[l].removeprefix(SITE[:-1])}" hreflang="{l}" lang="{l}"{current if l == lang else ""}>'
                    f'{NAMES[l]}</a>' for l in LANGS)
    langs = f'<nav class="vf-langs" aria-label="{html.escape(T["shell.langs"])}">{links}</nav>' if len(LANGS) > 1 else ""
    # The report page is a fragment: its leading <style> goes to <head>, the rest into #dash-root.
    frag = fill(frag_src, T, "report/index.html").replace("{{langs}}", langs)
    m = re.match(r"\s*<style>\n?(.*?)</style>\n?", frag, re.S)
    style, body = m.group(1), frag[m.end():]
    items = "\n".join(f'    <li><a href="data/{i}.json" title="{html.escape(T[f"data.{i}.desc"])}">{html.escape(T[f"data.{i}.title"])}</a></li>'
                      for i in DATASETS)
    page = fill(page_src, T, "web/page.html")
    og = "og.png" if lang == "pt-BR" else f"og-{lang}.png"
    assert (out / og).is_file(), f"no {og}: run scripts/06_og_image.py"
    page = (page.replace("{{url}}", url[lang]).replace("{{og_image}}", SITE + og).replace("{{alternates}}", alternates if len(LANGS) > 1 else "")
            .replace("{{updated_iso}}", updated.isoformat(timespec="minutes"))
            .replace("{{updated}}", updated.strftime(T["shell.date_fmt"])))
    page = (page.replace("{{dataset_ids}}", " ".join(DATASETS)).replace("{{style}}", style.rstrip())
            .replace("{{datasets}}", items).replace("{{body}}", body.strip()))
    if lang != "pt-BR":
        page = up_one(page)
    (page_dir / "index.html").write_text(fingerprint(page, page_dir), encoding="utf-8")
    if stale:
        print(f"{lang}: {len(stale)} of {len(PT)} texts not translated from the current Portuguese, shown in Portuguese:"
              f" {', '.join(stale[:8])}{' …' if len(stale) > 8 else ''}")

(out / "404.html").write_text(fingerprint(fill((out / "404.html").read_text(encoding="utf-8"), PT, "web/404.html"), out),
                              encoding="utf-8")
# one entry per language, each listing the others, as search engines read hreflang in sitemaps
sm = "".join(f"  <url>\n    <loc>{url[lang]}</loc>\n    <lastmod>{updated:%Y-%m-%d}</lastmod>\n"
             + "".join(f'    <xhtml:link rel="alternate" hreflang="{l}" href="{url[l]}"/>\n' for l in LANGS if len(LANGS) > 1)
             + "  </url>\n" for lang in LANGS)
(out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
                                 ' xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + sm + "</urlset>\n", encoding="utf-8")

size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
print(f"site -> {out}: {', '.join(LANGS)}; {sum(1 for p in out.rglob('*') if p.is_file())} files, {size / 1024:.0f} KB")
