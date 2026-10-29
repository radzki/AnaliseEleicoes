"""Pack the 2026 runoff, one row per section, for the "Tente fraudar!" simulator on the page.

Usage: python -I scripts/09_sim_data.py <processed_dir> <results_dir>

Writes <results_dir>/sim/secoes_2026_t2.bin (gzip-compressed columns, read in the browser with
DecompressionStream) and <results_dir>/sim/meta.json (column layout, labels and the reference values
from 2026, 2022 and, where it exists, 2018 that the simulator compares against).

Sections are the ones the forensic tests use (02_analyze.py: votes for Lula present, valid votes > 0),
sorted by polling place, so a polling place is a run of `place_size` consecutive sections.

The encoding keeps the download small (about 2.8 MB):
- columns that fit in a byte are stored as bytes; larger ones ("u16p") as two byte planes, all low bytes
  then all high bytes, which compresses better than interleaved 16-bit values;
- turnout is not stored: comparecimento = lula + flavio + other (blank and null) in the runoff, and
  aptos = comparecimento + abstencao;
- round 1 is stored as the difference from round 2 ("zigzag": 0, -1, 1, -2, ... -> 0, 1, 2, 3, ...), which is
  mostly small.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

proc, res = Path(sys.argv[1]), Path(sys.argv[2])
sys.stdout.reconfigure(encoding="utf-8")
out = res / "sim"
out.mkdir(parents=True, exist_ok=True)

SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
PLACE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO"]

w = pd.read_parquet(proc / "secao_wide.parquet")
w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)]
r2 = w[w.NR_TURNO == 2].sort_values(PLACE + ["NR_SECAO"]).reset_index(drop=True)
r1 = w[w.NR_TURNO == 1].set_index(SEC)[["v13", "v22", "QT_COMPARECIMENTO", "QT_APTOS"]].add_suffix("_1")
r2 = r2.join(r1, on=SEC)
n = len(r2)
assert r2.QT_APTOS_1.notna().all(), "every runoff section should exist in round 1"

i64 = lambda s: s.astype(np.int64).to_numpy()
lula, flavio, comp, aptos = i64(r2.v13), i64(r2.v22), i64(r2.QT_COMPARECIMENTO), i64(r2.QT_APTOS)
other = comp - lula - flavio  # blank + null
assert (r2.QT_VOTOS_NOMINAIS == r2.v13 + r2.v22).all() and (other >= 0).all()

ufs = sorted(r2.SG_UF.unique())
models = sorted(r2.DS_MODELO_URNA.unique())
place_size = r2.groupby(PLACE, sort=False).size().to_numpy()
assert place_size.sum() == n and place_size.max() < 256


def zigzag(d):
    return np.where(d >= 0, 2 * d, -2 * d - 1)


cols = {
    "place_size": (place_size, None),
    "lula": (lula, None), "flavio": (flavio, None), "other": (other, None), "abstencao": (aptos - comp, None),
    "lula_1": (zigzag(i64(r2.v13_1) - lula), "lula"), "flavio_1": (zigzag(i64(r2.v22_1) - flavio), "flavio"),
    "comparecimento_1": (zigzag(i64(r2.QT_COMPARECIMENTO_1) - comp), "comparecimento"),
    "aptos_1": (zigzag(i64(r2.QT_APTOS_1) - aptos), "aptos"),
    "model": (r2.DS_MODELO_URNA.map({m: i for i, m in enumerate(models)}).to_numpy(), None),
    "uf": (r2.SG_UF.map({u: i for i, u in enumerate(ufs)}).to_numpy(), None),
}
layout, blob = [], bytearray()
for name, (a, base) in cols.items():
    assert a.min() >= 0 and a.max() < 65536, name
    kind = "u8" if a.max() < 256 else "u16p"
    layout.append({"name": name, "type": kind, "offset": len(blob), "length": int(len(a)),
                   **({"zigzag_from": base} if base else {})})
    blob += a.astype("u1").tobytes() if kind == "u8" else (a & 255).astype("u1").tobytes() + (a >> 8).astype("u1").tobytes()
packed = gzip.compress(bytes(blob), compresslevel=9, mtime=0)
(out / "secoes_2026_t2.bin").write_bytes(packed)

R = {y: json.loads((res / f"results_{y}.json").read_text(encoding="utf-8")) for y in (2026, 2022)}


def refs(r):
    pz, sw, fp = r["place_z"]["2"]["Lula share"], r["swing"]["residual_pp"], r["fingerprint"]["2"]
    return {"place_pos4": pz["pos_4"], "place_neg4": pz["neg_4"], "corner_lula": fp["corner_lula"],
            "corner_right": fp["corner_right"], "swing_pos4": sw["pos_4"], "swing_neg4": sw["neg_4"],
            "corr_dturn_swing": r["swing"]["corr_dturn_swing_within_place"]}


T18 = json.loads((out.parent / "three_elections.json").read_text(encoding="utf-8"))["reference"]["2018"]
meta = {
    "source": "TSE, votacao_secao e detalhe_votacao_secao 2026, 2º turno (scripts/09_sim_data.py)",
    "sections": n, "places": int(len(place_size)), "raw_bytes": len(blob), "packed_bytes": len(packed),
    "columns": layout, "ufs": ufs, "models": models,
    "totals": {"lula": int(lula.sum()), "flavio": int(flavio.sum()), "aptos": int(aptos.sum()),
               "comparecimento": int(comp.sum())},
    # reference values computed by 02_analyze.py; the simulator must reproduce the 2026 ones untouched
    # (2018, from 14_three_elections.py, has the polling-place and near-unanimous counts but not the swing ones)
    "reference": {"2026": refs(R[2026]), "2022": refs(R[2022]),
                  "2018": {k: T18[k] for k in ("place_pos4", "place_neg4", "corner_lula", "corner_right")}},
    # TSE's integrity test (votação paralela): machines drawn by lot and replaced on election day.
    # News reports for the 2026 runoff give 20 to 33 per state; 540 is a conservative national total.
    "integrity_test_machines": 540,
    # of them, the share voted on with real voters' fingerprints, which a program that recognised the test
    # could not tell from an election: 10% in 2026 (OAS observation mission, preliminary runoff report)
    "integrity_biometric_share": 0.10,
}
(out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{n} sections, {meta['places']} polling places; {len(blob) / 1e6:.1f} MB raw, {len(packed) / 1e6:.2f} MB packed")
