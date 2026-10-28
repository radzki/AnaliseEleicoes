"""Check the section-level data against two more official TSE sources, alongside 03_consistency.py
(which compares turnout, blank, null and valid votes per municipality-zone):

1. votacao_candidato_munzona: each candidate's votes per municipality-zone unit, every round in the file.
2. The official totalization report of the 2026 runoff (results/totalizacao_T2_BR.txt, the text of
   6258_BR_BRASIL_2026_T2_PRESIDENTE.pdf), which gives the national total and one summary per state
   and for voters abroad.

Usage: python -I scripts/08_runoff_totals.py <raw_t2_dir> <processed_dir> <results_dir>
"""
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

raw, proc, res = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8")

KEY = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA"]
FIELDS = ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "v13", "v22"]


def stats(sec, off):
    d = sec - off
    return {"units_with_difference": int((d != 0).sum()), "total_abs_difference": int(d.abs().sum()),
            "total_section_sum": int(sec.sum()), "total_aggregate": int(off.sum())}


# 1. candidate votes per municipality-zone ----------------------------------------------------------
with zipfile.ZipFile(raw / "votacao_candidato_munzona_2026.zip") as z:
    cand = pd.read_csv(z.open("votacao_candidato_munzona_2026_BR.csv"), sep=";", encoding="latin1",
                       usecols=KEY + ["DT_GERACAO", "HH_GERACAO", "CD_CARGO", "NR_CANDIDATO", "QT_VOTOS_NOMINAIS"])
cand = cand[cand.CD_CARGO == 1]
generated = f"{cand.DT_GERACAO.iloc[0]} {cand.HH_GERACAO.iloc[0]}"
off = cand.groupby(KEY + ["NR_CANDIDATO"]).QT_VOTOS_NOMINAIS.sum()

votes = pd.read_parquet(proc / "votos_long.parquet")
votes = votes[votes.CD_CARGO == 1].rename(columns={"NR_VOTAVEL": "NR_CANDIDATO"})
sec = votes.groupby(KEY + ["NR_CANDIDATO"]).QT_VOTOS.sum()

munzona = {"source": "votacao_candidato_munzona_2026.zip", "generated": generated, "rounds": {}}
for t in sorted(off.index.get_level_values("NR_TURNO").unique()):
    o = off[off.index.get_level_values("NR_TURNO") == t]
    # the file lists every candidate on the ballot in every unit (0 where no one voted for them);
    # votos_long only has rows with votes, and also carries a withdrawn candidate the file leaves out
    s = sec[(sec.index.get_level_values("NR_TURNO") == t) &
            sec.index.get_level_values("NR_CANDIDATO").isin(o.index.get_level_values("NR_CANDIDATO").unique())]
    j = pd.concat([o.rename("off"), s.rename("sec")], axis=1).fillna(0)
    units = j.reset_index()[KEY].drop_duplicates()
    per_unit = j.groupby(level=KEY).sum()
    r = {"units": int(len(units)), "units_without_votes": int((per_unit["off"] == 0).sum()),
         "unit_candidate_rows": int(len(j)), "all": stats(j.sec, j["off"]), "candidates": {}}
    for c, g in j.groupby(level="NR_CANDIDATO"):
        r["candidates"][int(c)] = stats(g.sec, g["off"])
    munzona["rounds"][int(t)] = r

# 2. the official runoff report: national total and one summary per state --------------------------
UF = {"ACRE": "AC", "ALAGOAS": "AL", "AMAPÁ": "AP", "AMAZONAS": "AM", "BAHIA": "BA", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
      "ESPÍRITO SANTO": "ES", "GOIÁS": "GO", "MARANHÃO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
      "MINAS GERAIS": "MG", "PARÁ": "PA", "PARAÍBA": "PB", "PARANÁ": "PR", "PERNAMBUCO": "PE", "PIAUÍ": "PI",
      "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDÔNIA": "RO",
      "RORAIMA": "RR", "SANTA CATARINA": "SC", "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO",
      "EXTERIOR": "ZZ", "BRASIL": "BR"}


def num(s):
    return int(s.replace(".", ""))


lines = (res / "totalizacao_T2_BR.txt").read_text(encoding="utf-8").splitlines()
rep, cur = {}, None
for i, line in enumerate(lines):
    if m := re.match(r"Resumo Geral (?:do )?\(?(.+?)\)?$", line):
        cur = UF.get(m.group(1).upper())
        if cur:
            rep.setdefault(cur, {})
        continue
    if cur is None:
        continue
    d = rep[cur]
    if m := re.match(r"2\.2 Eleitorado apto a votar ([\d.]+)", line):
        d["QT_APTOS"] = num(m.group(1))
    elif m := re.match(r"2\.3 Comparecimento ([\d.]+)", line):
        d["QT_COMPARECIMENTO"] = num(m.group(1))
    elif m := re.match(r"2\.4 Abstenção\s+[\d,]+%\s+([\d.]+)", line):
        d["QT_ABSTENCOES"] = num(m.group(1))
    elif re.match(r"[bc]\) Votos nulos$", line):
        # the four totals follow on their own lines: total, candidates, blank, null
        total, d["QT_VOTOS_NOMINAIS"], d["QT_VOTOS_BRANCOS"], d["QT_VOTOS_NULOS"] = (num(x) for x in lines[i + 1:i + 5])
    elif m := re.match(r"([\d.]+) [\d,]+% ?(?:Eleito\*|Não eleito)?(13|22) - ", line):
        d.setdefault("v" + m.group(2), num(m.group(1)))

incomplete = {k: sorted(set(FIELDS) - set(v)) for k, v in rep.items() if set(FIELDS) - set(v)}
if incomplete or len(rep) != 29:
    sys.exit(f"Could not read the report: {len(rep)} summaries, missing fields {incomplete}")

wide = pd.read_parquet(proc / "secao_wide.parquet")
wide = wide[(wide.CD_CARGO == 1) & (wide.NR_TURNO == 2)]
by_uf = wide.groupby("SG_UF")[FIELDS].sum()
states = pd.DataFrame({k: v for k, v in rep.items() if k != "BR"}).T[FIELDS].loc[by_uf.index]
report = {"source": "Relatorio_Resultado_Totalizacao_2026_BR.zip (6258_BR_BRASIL_2026_T2_PRESIDENTE.pdf)", "round": 2,
          "units": int(len(states)), "fields": {}}
for f in FIELDS:
    report["fields"][f] = {**stats(by_uf[f], states[f]), "national_section_sum": int(wide[f].sum()),
                           "national_official": rep["BR"][f]}

out = {"year": 2026, "munzona_candidates": munzona, "report_t2": report}
(res / "consistency_2026_t2.json").write_text(json.dumps(out), encoding="utf-8")
print(json.dumps(out, indent=1))
