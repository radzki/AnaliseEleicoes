"""Check that section-level data sums exactly to TSE's separately published municipality/zone totals.

Usage: python -I scripts/03_consistency.py <raw_dir> <processed_dir> <out_dir> <year>
"""
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

raw, proc, out, year = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sys.stdout.reconfigure(encoding="utf-8")

KEY = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA"]
FIELDS = {"QT_APTOS": "QT_APTOS", "QT_COMPARECIMENTO": "QT_COMPARECIMENTO", "QT_ABSTENCOES": "QT_ABSTENCOES",
          "QT_VOTOS_BRANCOS": "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS": "QT_VOTOS_NULOS",
          "QT_VOTOS_NOMINAIS_VALIDOS": "QT_VOTOS_NOMINAIS"}

with zipfile.ZipFile(raw / f"detalhe_votacao_munzona_{year}.zip") as z:
    agg = pd.read_csv(z.open(f"detalhe_votacao_munzona_{year}_BR.csv"), sep=";", encoding="latin1",
                      usecols=KEY + ["CD_CARGO"] + list(FIELDS))
agg = agg[agg.CD_CARGO == 1].groupby(KEY)[list(FIELDS)].sum().rename(columns=FIELDS)

sec = pd.read_parquet(proc / "secao_wide.parquet")
sec = sec.groupby(KEY)[list(FIELDS.values())].sum()

rounds = sorted(agg.index.get_level_values(0).unique())
sec = sec[sec.index.get_level_values(0).isin(rounds)]
j = agg.join(sec, how="outer", suffixes=("_agg", "_sec"))


def compare(j):
    out = {}
    for f in FIELDS.values():
        d = j[f"{f}_sec"] - j[f"{f}_agg"]
        out[f] = {"units_with_difference": int((d != 0).sum()), "total_abs_difference": int(d.abs().sum()),
                  "total_section_sum": int(j[f"{f}_sec"].sum()), "total_aggregate": int(j[f"{f}_agg"].sum())}
    return out


# all rounds together, and each round on its own
res = {"year": int(year), "rounds_available": [int(r) for r in rounds], "units": int(len(j)),
       "units_missing_either_side": int(j.isna().any(axis=1).sum()), "fields": compare(j), "by_round": {}}
for r in rounds:
    jr = j[j.index.get_level_values(0) == r]
    res["by_round"][int(r)] = {"units": int(len(jr)), "units_missing_either_side": int(jr.isna().any(axis=1).sum()),
                               "fields": compare(jr)}
print(json.dumps(res, indent=1))
(out / f"consistency_{year}.json").write_text(json.dumps(res), encoding="utf-8")
