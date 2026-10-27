"""Extract presidential section-level results (both rounds) from the TSE zips into parquet.

Usage: python -I scripts/01_extract.py <raw_dir> <out_dir> <year>
"""
import sys
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.compute as pc
import pandas as pd

raw, out, year = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.stdout.reconfigure(encoding="utf-8")
out.mkdir(parents=True, exist_ok=True)

KEY = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO"]


def read_csv_from_zip(zpath, member, columns):
    with zipfile.ZipFile(zpath) as z:
        with z.open(member) as fh:
            header = fh.readline().decode("latin1").strip().replace('"', "").split(";")
        missing = [c for c in columns if c not in header]
        if missing:
            print(f"  {member}: columns not present, skipped: {missing}")
        columns = [c for c in columns if c in header]
    with zipfile.ZipFile(zpath) as z, z.open(member) as fh:
        t = pcsv.read_csv(
            fh,
            read_options=pcsv.ReadOptions(encoding="latin1", block_size=64 << 20),
            parse_options=pcsv.ParseOptions(delimiter=";"),
            convert_options=pcsv.ConvertOptions(include_columns=columns),
        )
    return t


# --- votes per candidate per section -----------------------------------------
cols = KEY + ["CD_CARGO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO"]
t = read_csv_from_zip(raw / f"votacao_secao_{year}_BR.zip", f"votacao_secao_{year}_BR.csv", cols)
t = t.filter(pc.equal(t["CD_CARGO"], 1))
votes = t.to_pandas()
print("vote rows:", len(votes), "| rounds:", sorted(votes.NR_TURNO.unique()))
votes.to_parquet(out / "votos_long.parquet", index=False)

cands = (
    votes.groupby(["NR_TURNO", "NR_VOTAVEL", "NM_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()
    .sort_values(["NR_TURNO", "QT_VOTOS"], ascending=[True, False])
)
print(cands.to_string(index=False))
cands.to_csv(out / "candidatos.csv", index=False)

# --- per-section details (eligible, turnout, blank, null, timing, machine) ---------
dcols = KEY + [
    "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS",
    "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "QT_VOTOS_LEGENDA", "QT_VOTOS_ANULADOS_APU_SEP",
    "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO", "DT_RECEBIMENTO_BU_HOR_TSE", "DS_ORIGEM_VOTO",
    "ST_SECAO_INSTALADA", "ST_SECAO_ANULADA", "DS_MODELO_URNA",
]
d = read_csv_from_zip(raw / f"detalhe_votacao_secao_{year}.zip", f"detalhe_votacao_secao_{year}_BR.csv", dcols)
d = d.filter(pc.equal(d["CD_CARGO"], 1)).to_pandas()
print("detail rows:", len(d), "| rounds:", sorted(d.NR_TURNO.unique()))
d.to_parquet(out / "detalhe_secao.parquet", index=False)

# --- wide table: one row per (round, section) -----------------------------------
wide = votes.pivot_table(index=KEY, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum", fill_value=0)
wide.columns = [f"v{c}" for c in wide.columns]
wide = wide.reset_index()
merged = d.merge(wide, on=KEY, how="outer", indicator=True)
print("merge check:\n", merged["_merge"].value_counts().to_string())
merged = merged.drop(columns="_merge")
merged.to_parquet(out / "secao_wide.parquet", index=False)
print("wide rows:", len(merged))
