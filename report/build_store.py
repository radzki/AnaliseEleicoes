"""Write the report's store documents (page files + dataset entries) as JSON for ArtifactData.

Usage: python -I report/build_store.py <report_dir>
"""
import json
import re
import sys
from pathlib import Path

rep = Path(sys.argv[1])
out = rep / "store"
out.mkdir(exist_ok=True)
UPDATED = {"at": "2026-10-27T01:25:45Z", "by": "Claude, a partir dos dados abertos do TSE (scripts/04_export.py)"}
SRC = "Calculado a partir dos resultados presidenciais por seção do TSE (votacao_secao e detalhe_votacao_secao, 2026 e 2022; 2018 na seção “Com 2018 também”)."
# dataset id -> its file in the claude.ai store; names and descriptions are in locales/ (data.<id>.title/.desc)
DATASETS = {
    "summary": "feae4b606441a4b88cef0f750b19a854",
    "scorecard": "b4e1ff14911a4eb3beb45b41e2ba54b4",
    "last_digit": "228b570c7294c23a9889155aa6666c88",
    "pct_hist": "310e5719ab02338bcf7e8a4c9214381d",
    "z_hist": "0df60168c118bf51510f4bafb2c1947e",
    "states": "7c98d2752630bc499081197a837f3736",
    "fingerprint": "c6a5f260d9d625cbc53df17afef2913a",
    "corner": "f626e357501a38d10fc42763841f768b",
    "timing": "a6ffa75bed1ffacd6e5d9f8e5ebac9c4",
    "urna": "be7704617c40d8c3469ee7afb8bfb098",
    "consistency": "1243a9b36bf84e5e31307154ce8e1f24",
    "strongholds": "4383205ada88579925d457050b3709f2",
    "more_tests": "PENDENTE",
    "size_curve": "PENDENTE",
    "tres_eleicoes": "PENDENTE",
    "graficos": "PENDENTE",
    "urna_assinaturas": "PENDENTE",
    "urna_logs": "PENDENTE",
}
UPDATED_AT = {"corner": "2026-10-27T02:22:38Z", "strongholds": "2026-10-27T05:59:06Z", "consistency": "2026-10-28T01:00:28Z"}
docs = [("dash", "meta", {"title": "Eleições 2026 - Estatística Forense"}), ("dash", "params", {"cand": "ambos"})]
TEXT = json.loads((rep.parent / "locales" / "pt-BR.json").read_text(encoding="utf-8"))
for i, aid in DATASETS.items():
    docs.append(("datasets", i, {"title": TEXT[f"data.{i}.title"], "description": f"{TEXT[f'data.{i}.desc']} {SRC}",
                                  "source": {"kind": "file", "url": f"/_blob/{aid}", "name": f"{i}.json"},
                                  "updated": {**UPDATED, "at": UPDATED_AT.get(i, UPDATED["at"])}, "fixed": True}))
# the page's text is in locales/pt-BR.json: {{key}} in index.html is filled from it, and its "js." strings
# become i18n.js, which the scripts read (as in scripts/05_site.py)
page = re.sub(r"\{\{([\w-]+(?:\.[\w-]+)+)\}\}", lambda m: TEXT[m.group(1)], (rep / "index.html").read_text(encoding="utf-8"))
docs.append(("files", "index.html", {"text": page}))
docs.append(("files", "i18n.js", {"text": "window.VF_I18N = " + json.dumps(
    {k: v for k, v in TEXT.items() if k.startswith("js.")}, ensure_ascii=False, indent=0) + ";\n"}))
for f in ("core.js", "charts.js", "testcharts.js", "tables.js", "simple.js", "sim.js"):
    docs.append(("files", f, {"text": (rep / f).read_text(encoding="utf-8")}))
for coll, doc_id, data in docs:
    p = out / f"{coll}__{doc_id}.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"{coll}/{doc_id}\t{p.stat().st_size:>7} B\t{p.as_posix()}")
