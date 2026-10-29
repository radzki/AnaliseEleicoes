"""Render the link-preview image (Open Graph card, 1200x630) for the static site.

Usage: python -I scripts/06_og_image.py <repo_dir> <chrome_exe>

Writes web/og-card.html (the card, with the real last-digit shares of the 2026 runoff) and
renders it with headless Chrome to web/og.png. The card uses the site's own font from web/fonts.
Its text is in locales/ ("og." keys); each translation gets its own card, web/og-<lang>.png, from
the texts translated from the current Portuguese (the rest stays Portuguese, as on the page).
"""
import functools
import hashlib
import http.server
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

repo, chrome = Path(sys.argv[1]).resolve(), sys.argv[2]
web, loc = repo / "web", repo / "locales"
PT = json.loads((loc / "pt-BR.json").read_text(encoding="utf-8"))


def texts(lang):
    """The card's text in one language; as in scripts/05_site.py, a translation counts only if it was
    made from the current Portuguese."""
    if lang == "pt-BR":
        return PT
    tr = json.loads((loc / f"{lang}.json").read_text(encoding="utf-8"))
    current = lambda k: k in tr and tr[k]["from"] == hashlib.sha256(PT[k].encode("utf-8")).hexdigest()[:10]
    return {k: tr[k]["text"] if current(k) else v for k, v in PT.items()}


rows = json.loads((repo / "results" / "dash" / "last_digit.json").read_text(encoding="utf-8"))
share = {v: [r["share"] for r in sorted((r for r in rows if r["year"] == 2026 and r["round"] == 2 and r["variable"] == v),
                                        key=lambda r: r["digit"])]
         for v in ("Lula", "Right candidate")}

# Ten bars per candidate on a 0-12% scale, with the 10% line every bar should reach.
W, H, TOP = 168, 190, 12
y = lambda v: TOP + H * (1 - v / 0.12)


def bars(values, x0, color):
    bw = W / 10
    return "".join(f'<rect x="{x0 + i * bw + 2:.1f}" y="{y(v):.1f}" width="{bw - 4:.1f}" height="{y(0) - y(v):.1f}" rx="2" fill="{color}"/>'
                   for i, v in enumerate(values))


def card(T):
    svg = f"""<svg viewBox="0 0 400 250" width="400" height="250" aria-hidden="true">
  <line x1="0" x2="400" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#b9bec6"/>
  {bars(share["Lula"], 0, "#c62f2f")}
  {bars(share["Right candidate"], 232, "#1d64c2")}
  <line x1="0" x2="400" y1="{y(0.1):.1f}" y2="{y(0.1):.1f}" stroke="#14171c" stroke-dasharray="6 5" stroke-width="1.5"/>
  <text x="400" y="{y(0.1) - 10:.1f}" text-anchor="end" class="ref">{T["og.ref"]}</text>
  <text x="0" y="{y(0) + 30:.1f}" class="who">Lula</text>
  <text x="232" y="{y(0) + 30:.1f}" class="who">Flávio</text>
</svg>"""
    return f"""<!doctype html>
<html lang="{T["shell.lang"]}">
<head>
<meta charset="utf-8">
<title>{T["og.title"]}</title>
<style>
  @font-face {{ font-family: "Atkinson Hyperlegible Next"; src: url("fonts/AtkinsonHyperlegibleNext-latin.woff2") format("woff2"); font-weight: 200 800; }}
  html, body {{ margin: 0; }}
  body {{ width: 1200px; height: 630px; overflow: hidden; background: #ffffff; color: #14171c;
          font-family: "Atkinson Hyperlegible Next", system-ui, sans-serif; }}
  .card {{ box-sizing: border-box; height: 100%; padding: 64px 72px 56px; display: grid;
           grid-template-columns: 1fr 400px; grid-template-rows: 1fr auto; column-gap: 64px; }}
  h1 {{ margin: 0; font-size: 58px; line-height: 1.08; font-weight: 750; letter-spacing: -0.015em; }}
  .answer {{ margin: 36px 0 0; padding-top: 28px; border-top: 3px solid #14171c; font-size: 31px; line-height: 1.3; font-weight: 500; }}
  .chart {{ align-self: center; }}
  .chart p {{ margin: 0 0 18px; font-size: 21px; line-height: 1.3; color: #4a515c; }}
  .ref {{ font-size: 18px; fill: #14171c; }}
  .who {{ font-size: 22px; font-weight: 650; fill: #14171c; }}
  .foot {{ grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: baseline;
           font-size: 22px; color: #4a515c; }}
  .foot b {{ color: #14171c; font-weight: 650; }}
</style>
</head>
<body>
<div class="card">
  <div>
    <h1>{T["og.h1"]}</h1>
    <p class="answer">{T["og.answer"]}</p>
  </div>
  <div class="chart">
    <p>{T["og.chart"]}</p>
    {svg}
  </div>
  <div class="foot"><b>eleicoes.radzkitech.com</b><span>{T["og.foot"]}</span></div>
</div>
</body>
</html>
"""


# Serve web/ so the card loads its font over http, then screenshot it at the exact card size.
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web)))
threading.Thread(target=server.serve_forever, daemon=True).start()
for lang in ["pt-BR"] + sorted(p.stem for p in loc.glob("*.json") if p.stem != "pt-BR"):
    suffix = "" if lang == "pt-BR" else f"-{lang}"
    (web / f"og-card{suffix}.html").write_text(card(texts(lang)), encoding="utf-8")
    profile = tempfile.mkdtemp(prefix="og-chrome-")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", f"--user-data-dir={profile}",
                    "--window-size=1200,630", "--force-device-scale-factor=1", "--virtual-time-budget=5000",
                    f"--screenshot={web / f'og{suffix}.png'}", f"http://127.0.0.1:{server.server_address[1]}/og-card{suffix}.html"],
                   check=True, capture_output=True)
    print("card ->", web / f"og{suffix}.png")
server.shutdown()
