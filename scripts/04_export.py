"""Turn results/*.json into the row tables the report page reads.

Usage: python -I scripts/04_export.py <results_dir> <processed_2026> <processed_2022> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

res_dir, p26, p22, out = (Path(a) for a in sys.argv[1:5])
sys.stdout.reconfigure(encoding="utf-8")
out.mkdir(parents=True, exist_ok=True)
R = {y: json.loads((res_dir / f"results_{y}.json").read_text(encoding="utf-8")) for y in (2026, 2022)}
C = {y: json.loads((res_dir / f"consistency_{y}.json").read_text(encoding="utf-8")) for y in (2026, 2022)}
ST = {y: pd.read_csv(res_dir / f"states_{y}.csv") for y in (2026, 2022)}
Z_EDGES = np.arange(-10, 10.0001, 0.25)


def dump(name, rows):
    rows = json.loads(pd.DataFrame(rows).to_json(orient="records", force_ascii=False))
    (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{name}: {len(rows)} rows, {(out / f'{name}.json').stat().st_size / 1024:.0f} KB")


# summary -------------------------------------------------------------------------
rows = []
for y, r in R.items():
    for t, v in r["totals"].items():
        rows.append({"year": y, "round": int(t), "right_name": r["right_name"], "sections": r["sections"][t],
                     "aptos": v["aptos"], "comparecimento": v["comparecimento"],
                     "turnout": v["comparecimento"] / v["aptos"], "valid": v["valid"], "lula": v["lula"],
                     "right": v["right"], "lula_share": v["lula"] / v["valid"], "right_share": v["right"] / v["valid"],
                     "lula_2p": v["lula"] / (v["lula"] + v["right"]), "margin": v["lula"] - v["right"],
                     "brancos": v["brancos"], "nulos": v["nulos"]})
dump("summary", rows)

# scorecard -----------------------------------------------------------------------
sc = []


def add(key, section, test, variable, rnd, y, observed, expected, stat, stat_name, unit):
    sc.append({"id": f"{key}|{y}", "key": key, "section": section, "test": test, "variable": variable,
               "round": rnd, "year": y, "observed": observed, "expected": expected, "stat": stat,
               "stat_name": stat_name, "unit": unit})


for y, r in R.items():
    rn = r["right_name"].split()[0] if y == 2026 else "Bolsonaro"
    right_label = "Right candidate"  # Flávio (2026) / Jair (2022): compared like for like
    for t in ("1", "2"):
        for var, lab in (("Lula", "Lula"), (r["right_name"], right_label), ("Comparecimento", "Turnout")):
            d = r["last_digit"][t][var]
            add(f"ld|{lab}|{t}", "Round numbers", "Counts ending in 0 (per section)", lab, int(t), y,
                d["pct_ending_0"], 10.0, d["p_uniform"], "p (all 10 digits)", "%")
        for var, lab in (("Lula", "Lula"), (r["right_name"], right_label), ("Comparecimento", "Turnout"),
                         ("Brancos", "Blank"), ("Nulos", "Null")):
            h = r["heaping"][t][var]
            add(f"heap|{lab}|{t}", "Round numbers", "Heaping at 10, 20, 30… vs nearby values", lab, int(t), y,
                h["ratio_10_vs_control"], 1.0, h["z"], "z", "ratio")
        for var, lab in (("turnout", "Turnout"), ("Lula", "Lula share")):
            d = r["int_pct"][t][var]["integer_pct"]
            add(f"int|{lab}|{t}", "Round numbers", "Sections at an exact whole percentage", lab, int(t), y,
                d["observed"], d["expected"], d["z"], "z", "sections")
        for lvl in ("zona", "municipio"):
            d = r["last_digit"][t][f"Lula por {lvl}"]
            add(f"ldagg|{lvl}|{t}", "Round numbers", f"Lula count ending in 0 (per {'zone' if lvl == 'zona' else 'municipality'})",
                "Lula", int(t), y, d["pct_ending_0"], 10.0, d["p_uniform"], "p (all 10 digits)", "%")
    lds = r["last_digit_states"]
    add("ldstate|flag", "Round numbers", "State last-digit tests failing after correction", "All", None, y,
        len(lds["flagged"]), 0, lds["n_tests"], "tests run", "tests")
    add("ldstate|p05", "Round numbers", "State last-digit tests with p < 0.05", "All", None, y,
        lds["share_p_below_005"] * 100, 5.0, lds["n_tests"], "tests run", "%")
    for t in ("1", "2"):
        pz = r["place_z"][t]["Lula share"]
        add(f"pz|pos|{t}", "Distribution", "Sections far above their polling place (z > 4), pro-Lula", "Lula share",
            int(t), y, pz["pos_4"], pz["normal_expected_4"], pz["robust_sd"], "robust sd", "sections")
        add(f"pz|neg|{t}", "Distribution", "Sections far below their polling place (z < −4), pro-right", "Lula share",
            int(t), y, pz["neg_4"], pz["normal_expected_4"], pz["robust_sd"], "robust sd", "sections")
        fp = r["fingerprint"][t]
        add(f"corner|{t}", "Distribution", "Sections with turnout ≥ 95% and Lula ≥ 90%", "Lula", int(t), y,
            fp["corner_lula"], None, fp["corner_right"], "same corner, right candidate", "sections")
        add(f"hiT|{t}", "Distribution", "High-turnout outliers (z > 4) leaning Lula", "Turnout", int(t), y,
            r["place_z"][t]["lula_z_among_high_turnout_outliers"]["share_zL_pos"] * 100, 50.0,
            r["place_z"][t]["lula_z_among_high_turnout_outliers"]["n"], "outliers", "%")
    pp = r["place_z_persistence"]
    add("persist", "Distribution", "Round-2 pro-Lula outliers already high in round 1 (z > 2)", "Lula share", 2, y,
        pp["pos4_r2_with_r1_above_2"] / pp["pos4_r2"] * 100, None, pp["corr_round1_round2"], "corr R1–R2", "%")
    sw = r["swing"]["residual_pp"]
    add("swing|pos", "Swing", "Sections swinging far more to Lula than neighbours (> 4σ)", "Swing", 2, y,
        sw["pos_4"], sw["normal_expected_4"], sw["skew"], "skew", "sections")
    add("swing|neg", "Swing", "Sections swinging far more to the right than neighbours (> 4σ)", "Swing", 2, y,
        sw["neg_4"], sw["normal_expected_4"], sw["skew"], "skew", "sections")
    add("swing|dturn", "Swing", "Turnout rise vs swing to Lula, within polling place", "Correlation", 2, y,
        r["swing"]["corr_dturn_swing_within_place"], 0.0, None, None, "r")
    for t in ("1", "2"):
        add(f"time|{t}", "Timing & machines", "Lula share of later-arriving sections, within zone", "Slope", int(t), y,
            r["timing"][t]["within_zone_slope_pp_per_hour"], 0.0, None, None, "pp / hour")
        um = r["urna_model"][t]
        um = [u for u in um if not u["DS_MODELO_URNA"].startswith("#")]
        add(f"urna|{t}", "Timing & machines", "Largest machine-model gap vs same polling place", "Lula share", int(t), y,
            max(abs(u["share_pp_vs_place"]) for u in um), 0.0, len(um), "models", "pp")
dump("scorecard", sc)

# last digits ---------------------------------------------------------------------
rows = []
for y, r in R.items():
    for t in ("1", "2"):
        for var, lab in (("Lula", "Lula"), (r["right_name"], "Right candidate"), ("Comparecimento", "Turnout")):
            d = r["last_digit"][t][var]
            for dg, f in enumerate(d["freq"]):
                rows.append({"year": y, "round": int(t), "variable": lab, "digit": dg, "share": f,
                             "n": d["n"], "p_uniform": d["p_uniform"]})
dump("last_digit", rows)

# whole-percentage histogram (round 2) --------------------------------------------
rows = []
for y, r in R.items():
    for var, lab in (("turnout", "Turnout"), ("Lula", "Lula share")):
        h = r["fine_hist"]["2"][var]
        for i, (o, e) in enumerate(zip(h["obs"], h["null"])):
            rows.append({"year": y, "variable": lab, "pct": round(i / 10, 1), "observed": o, "expected": e})
dump("pct_hist", rows)

# z histograms ----------------------------------------------------------------------
rows = []
for y, r in R.items():
    for t in ("1", "2"):
        for var, lab in (("Lula share", "Lula share"), ("Turnout", "Turnout")):
            d = r["place_z"][t][var]
            cdf = stats.norm.cdf(Z_EDGES / d["robust_sd"])
            for lo, c, e in zip(Z_EDGES[:-1], d["hist"], d["n"] * np.diff(cdf)):
                rows.append({"year": y, "round": int(t), "variable": lab, "z": round(float(lo), 2),
                             "count": c, "normal": float(e)})
    d = r["swing"]["residual_pp"]
    cdf = stats.norm.cdf(Z_EDGES)
    for lo, c, e in zip(Z_EDGES[:-1], d["hist"], d["n"] * np.diff(cdf)):
        rows.append({"year": y, "round": 2, "variable": "Swing", "z": round(float(lo), 2), "count": c, "normal": float(e)})
dump("z_hist", rows)

# states ------------------------------------------------------------------------------
rows = []
for y, t in ST.items():
    t1 = t[t.turno == 1].set_index("uf")
    for _, s in t[t.turno == 2].iterrows():
        rows.append({"year": y, "uf": s.uf, "sections": int(s.secoes), "turnout_1": t1.turnout_pct[s.uf] / 100,
                     "turnout_2": s.turnout_pct / 100, "turnout_change_pp": s.turnout_change_pp,
                     "lula_share_2": s.lula_pct / 100, "swing_pp": s.swing_pp,
                     "lula_gain": int(s.lula_gain), "right_gain": int(s.right_gain)})
dump("states", rows)

# fingerprint (round 2, non-empty cells) -------------------------------------------
rows = []
for y, r in R.items():
    for side in ("lula",):
        m = np.array(r["fingerprint"]["2"][side])
        for i, j in zip(*np.nonzero(m)):
            rows.append({"year": y, "candidate": "Lula" if side == "lula" else "Right candidate",
                         "turnout": int(i), "share": int(j), "sections": int(m[i, j])})
dump("fingerprint", rows)

# corner sections (2026 runoff, each candidate): turnout >= 95%, candidate >= 90%, >= 100 eligible
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
w = pd.read_parquet(p26 / "secao_wide.parquet", columns=["NR_TURNO", *SEC, "NM_MUNICIPIO", "NM_LOCAL_VOTACAO", "QT_APTOS",
                                                         "QT_COMPARECIMENTO", "QT_VOTOS_NOMINAIS", "v13", "v22"])
w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)].copy()
w["turnout"] = w.QT_COMPARECIMENTO / w.QT_APTOS
w["lula"] = w.v13 / w.QT_VOTOS_NOMINAIS
w["flavio"] = w.v22.fillna(0) / w.QT_VOTOS_NOMINAIS
r1 = w[w.NR_TURNO == 1].set_index(SEC)[["turnout", "lula", "flavio"]].add_suffix("_1")
r2 = w[(w.NR_TURNO == 2) & (w.QT_APTOS >= 100)].join(r1, on=SEC)
rows = []
for cand in ("lula", "flavio"):
    for _, c in r2[(r2.turnout >= 0.95) & (r2[cand] >= 0.9)].sort_values("turnout", ascending=False).iterrows():
        rows.append({"section_id": f"{c.SG_UF}-{c.CD_MUNICIPIO}-{c.NR_ZONA}-{c.NR_SECAO}", "candidate": cand,
                     "uf": c.SG_UF, "municipality": c.NM_MUNICIPIO, "zone": int(c.NR_ZONA), "section": int(c.NR_SECAO),
                     "place": c.NM_LOCAL_VOTACAO, "eligible": int(c.QT_APTOS),
                     "turnout_1": round(c.turnout_1, 4), "turnout_2": round(c.turnout, 4),
                     "share_1": round(c[f"{cand}_1"], 4), "share_2": round(c[cand], 4)})
dump("corner", rows)

# timing (recomputed with explicit 10-minute bins) --------------------------------
rows = []
for y, p in ((2026, p26), (2022, p22)):
    w = pd.read_parquet(p / "secao_wide.parquet", columns=["NR_TURNO", "v13", "v22", "QT_VOTOS_NOMINAIS",
                                                            "DT_RECEBIMENTO_BU_HOR_TSE"])
    w = w[w.v13.notna()]
    w["arr"] = pd.to_datetime(w.DT_RECEBIMENTO_BU_HOR_TSE, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    for t, g in w.groupby("NR_TURNO"):
        g = g[g.arr.notna()]
        t0 = g.arr.dt.normalize().min() + pd.Timedelta(hours=17)
        b = ((g.arr - t0).dt.total_seconds() // 600).clip(lower=0, upper=36).astype(int)
        a = g.groupby(b)[["v13", "v22", "QT_VOTOS_NOMINAIS"]].sum().reindex(range(37), fill_value=0).cumsum()
        for i, s in a.iterrows():
            rows.append({"year": y, "round": int(t), "minutes": int((i + 1) * 10),
                         "pct_counted": s.QT_VOTOS_NOMINAIS / a.QT_VOTOS_NOMINAIS.iloc[-1],
                         "lula_2p": s.v13 / (s.v13 + s.v22) if s.v13 + s.v22 else None})
dump("timing", rows)

# machine model -----------------------------------------------------------------------
rows = []
for y, r in R.items():
    for t in ("1", "2"):
        for u in r["urna_model"][t]:
            if u["DS_MODELO_URNA"].startswith("#"):
                continue
            rows.append({"id": f"{y}|{t}|{u['DS_MODELO_URNA']}", "year": y, "round": int(t),
                         "model": u["DS_MODELO_URNA"], "sections": int(u["sections"]),
                         "raw_share": u["raw_lula_share"] / 100, "vs_place_pp": u["share_pp_vs_place"]})
dump("urna", rows)

# consistency -------------------------------------------------------------------------
names = {"QT_APTOS": "Eligible voters", "QT_COMPARECIMENTO": "Turnout", "QT_ABSTENCOES": "Abstentions",
         "QT_VOTOS_BRANCOS": "Blank votes", "QT_VOTOS_NULOS": "Null votes", "QT_VOTOS_NOMINAIS": "Valid votes"}
rows = []
for y, c in C.items():
    rounds = "+".join(str(r) for r in c["rounds_available"])
    for f, v in c["fields"].items():
        rows.append({"id": f"{y}|{f}", "year": y, "rounds": rounds, "field": names[f], "units": c["units"],
                     "units_with_difference": v["units_with_difference"], "abs_difference": v["total_abs_difference"],
                     "section_sum": v["total_section_sum"], "official": v["total_aggregate"]})
dump("consistency", rows)
