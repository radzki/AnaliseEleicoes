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

# strongholds: how often a candidate's 90%+ sections reach turnout >= 95%, per year and round (>= 100 eligible),
# and the same runoff sections compared one by one between 2022 and 2026
def wide(p):
    w = pd.read_parquet(p / "secao_wide.parquet", columns=["NR_TURNO", *SEC, "QT_APTOS", "QT_COMPARECIMENTO",
                                                           "QT_VOTOS_NOMINAIS", "v13", "v22"])
    w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0) & (w.QT_APTOS >= 100)].copy()
    w["turnout"] = w.QT_COMPARECIMENTO / w.QT_APTOS
    w["lula"] = w.v13 / w.QT_VOTOS_NOMINAIS
    w["right"] = w.v22.fillna(0) / w.QT_VOTOS_NOMINAIS
    return w


WY = {2026: wide(p26), 2022: wide(p22)}
rows = []
for y, w in WY.items():
    for t, g in w.groupby("NR_TURNO"):
        for grp, s in (("all", g), ("lula90", g[g.lula >= 0.9]), ("right90", g[g.right >= 0.9])):
            rows.append({"id": f"{y}|{t}|{grp}", "kind": "group", "year": y, "round": int(t), "group": grp,
                         "sections": len(s), "eligible": int(s.QT_APTOS.sum()), "voters": int(s.QT_COMPARECIMENTO.sum()),
                         "turnout": s.QT_COMPARECIMENTO.sum() / s.QT_APTOS.sum(),
                         "t95_sections": int((s.turnout >= 0.95).sum()), "t95_share": (s.turnout >= 0.95).mean()})
m = WY[2026][WY[2026].NR_TURNO == 2].merge(WY[2022][WY[2022].NR_TURNO == 2], on=SEC, suffixes=("", "_22"))
for grp, s in (("lula90", m[(m.lula >= 0.9) & (m.lula_22 >= 0.9)]),
               ("mid", m[m.lula.between(0.4, 0.6) & m.lula_22.between(0.4, 0.6)])):
    rows.append({"id": f"matched|{grp}", "kind": "matched", "year": 2026, "round": 2, "group": grp, "sections": len(s),
                 "eligible_change": (s.QT_APTOS / s.QT_APTOS_22 - 1).median(),
                 "voters_change": (s.QT_COMPARECIMENTO / s.QT_COMPARECIMENTO_22 - 1).median(),
                 "turnout_2022": s.turnout_22.mean(), "turnout_2026": s.turnout.mean()})
dump("strongholds", rows)

# machine logs, from the sample read by scripts/07_urna_logs.py: votes after 17h (Brasília), closing times
# and how voters were identified, per group and round, on machines whose log holds both rounds and whose
# runoff vote count matches the official turnout (abroad excluded: it votes on local time)
lp = res_dir / "urna_logs_sample.csv"
if lp.exists():
    L0 = pd.read_csv(lp)
    ok = L0[L0.status == "ok"]
    L = ok[(ok.votes_2 == ok.QT_COMPARECIMENTO) & (ok.SG_UF != "ZZ") & ok.votes_1.notna()]
    rows = [{"id": "check", "kind": "check", "sampled": len(L0), "read": len(ok),
             "matched": int((ok.votes_2 == ok.QT_COMPARECIMENTO).sum()), "replaced": int((ok.votes_2 != ok.QT_COMPARECIMENTO).sum())}]
    for g, d in L.groupby("group"):
        for t in (1, 2):
            v = d[f"votes_{t}"].sum()
            rows.append({"id": f"{g}|{t}", "kind": "group", "group": g, "round": t, "machines": len(d), "votes": int(v),
                         "late": int(d[f"late_{t}"].sum()), "late_pct": 100 * d[f"late_{t}"].sum() / v,
                         "nofp_share": 1 - d[f"bio_{t}"].sum() / v, "manual_share": d[f"manual_{t}"].sum() / v,
                         "close_median": d[f"close_brt_{t}"].median(), "open_after_18": (d[f"close_brt_{t}"] > 18).mean()})
    rnd = L[L.group == "random"]
    late_share = lambda d: d.late_2.sum() / d.votes_2.sum()
    rng = np.random.default_rng(2026)
    boots = np.array([late_share(rnd.iloc[rng.integers(0, len(rnd), len(rnd))]) for _ in range(2000)])
    voters = R[2026]["totals"]["2"]["comparecimento"]
    margin = R[2026]["totals"]["2"]["lula"] - R[2026]["totals"]["2"]["right"]
    est = late_share(rnd) * voters
    rows.append({"id": "national", "kind": "estimate", "votes_est": est, "est_low": np.percentile(boots, 2.5) * voters,
                 "est_high": np.percentile(boots, 97.5) * voters, "margin_share": est / margin})
    lo = rnd[rnd.close_brt_2 > 18.5]
    rows.append({"id": "open_late", "kind": "open_late", "machines": len(lo), "late": int(lo.late_2.sum()), "max_late": int(lo.late_2.max())})
    c = L[L.group == "corner_lula"]
    rows.append({"id": "corner_change", "kind": "change", "machines": len(c), "added": int(c.votes_2.sum() - c.votes_1.sum()),
                 "added_fp": int(c.bio_2.sum() - c.bio_1.sum())})
    dump("urna_logs", rows)

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
         "QT_VOTOS_BRANCOS": "Blank votes", "QT_VOTOS_NULOS": "Null votes", "QT_VOTOS_NOMINAIS": "Valid votes",
         "13": "Lula votes", "22": "Flávio votes"}


def cons_row(id_, y, rounds, field, units, v):
    return {"id": id_, "year": y, "rounds": rounds, "field": names[field], "units": units,
            "units_with_difference": v["units_with_difference"], "abs_difference": v["total_abs_difference"],
            "section_sum": v["total_section_sum"], "official": v["total_aggregate"]}


# 2026: one row per round and field, plus each finalist's votes per municipality-zone from
# scripts/08_runoff_totals.py. 2022: both rounds together, as before.
T2 = json.loads((res_dir / "consistency_2026_t2.json").read_text(encoding="utf-8"))
rows = []
for t, b in C[2026]["by_round"].items():
    for f, v in b["fields"].items():
        rows.append(cons_row(f"2026|{t}|{f}", 2026, t, f, b["units"], v))
    cand = T2["munzona_candidates"]["rounds"][t]
    for c in ("13", "22"):
        rows.append(cons_row(f"2026|{t}|{c}", 2026, t, c, cand["units"], cand["candidates"][c]))
c22 = C[2022]
for f, v in c22["fields"].items():
    rows.append(cons_row(f"2022|{f}", 2022, "+".join(str(r) for r in c22["rounds_available"]), f, c22["units"], v))
dump("consistency", rows)

# more tests: scripts/10_more_tests.py, 12_urna_bursts.py, 13_mixture.py --------------------------
# one row per test and year (or planted fraud, or machine group), read by the "Mais testes" section
# 2018 (Jair Bolsonaro elected) is a second reference year for these tests
MT = {y: json.loads((res_dir / f"more_tests_{y}.json").read_text(encoding="utf-8")) for y in (2026, 2022, 2018)}
MX = {y: json.loads((res_dir / f"mixture_{y}.json").read_text(encoding="utf-8")) for y in (2026, 2022, 2018)}
margin = R[2026]["totals"]["2"]["lula"] - R[2026]["totals"]["2"]["right"]
rows, curve = [], []
for y, m in MT.items():
    s = m["size"]["real"]["max_step"]
    rows.append({"id": f"size|{y}", "step_pp": s["step_pp"], "at": s["at"], "t": s["t"]})
    curve += [{"series": str(y), **c} for c in m["size"]["real"]["curve"]]
    p = m["prop_swing"]["real"]
    rows.append({"id": f"prop|{y}", "slope": p["slope"], "se": p["se"]})
    h = m["homogeneity"]
    rows.append({"id": f"homog|{y}", "phi_median": h["phi_median"], "p001": h["share_p_below_001"],
                 "p05": h["share_p_below_005"], "places": h["places"]})
    sh = m["shpilkin"]["2"]
    rows.append({"id": f"shpilkin|{y}", "state_lula": sh["by_state"]["lula"], "state_right": sh["by_state"]["right"],
                 "national_lula": sh["national"]["lula"], "national_right": sh["national"]["right"]})
    b = m["benford2"]["2"]
    rows.append({"id": f"benford2|{y}", "lula_mean": b["lula"]["mean"], "right_mean": b["right"]["mean"],
                 "expected": b["lula"]["expected_mean"], "lula_p": b["lula"]["p"], "right_p": b["right"]["p"]})
    x = MX[y]["real"]
    rows.append({"id": f"mixture|{y}", "f_i": x["f_i"], "f_e": x["f_e"], "sections_extreme": x["sections_extreme"],
                 "votes_incremental": x["votes_incremental"], "fit_gain": 1 - x["loss"] / x["loss_no_fraud"]})
m = MT[2026]
for p in m["size"]["planted"]:
    rows.append({"id": f"size|planted|{p['above']}", "step_pp": p["step_pp"], "flip_share": p["flip_share"], "machines": p["machines"]})
    if p["above"] == 250:
        curve += [{"series": "planted", **c} for c in p["curve"]]
rows.append({"id": "size|bigonly", "above": 350, "possible": any(p["above"] == 350 for p in m["size"]["planted"])})
real, ref = m["prop_swing"]["real"]["slope"], MT[2022]["prop_swing"]["real"]["slope"]
pl = next(p for p in m["prop_swing"]["planted"] if p["from"] == "right")
gap_votes = (real - ref) / (pl["slope"] - real) * m["move"]
rows.append({"id": "prop|planted", "slope": pl["slope"], "flip_share": pl["flip_share"], "gap": real - ref,
             "gap_votes": gap_votes, "move": m["move"], "margin_without": margin - 2 * gap_votes,
             "added": pl["slope"] - real})
# the same slope state by state: how much it moves between the two elections without a program, which
# would add the same amount in every state
g = pd.Series(m["prop_swing"]["by_state"]) - pd.Series(MT[2022]["prop_swing"]["by_state"])
g = g.dropna()
rows.append({"id": "prop|states", "units": len(g), "gap_min": g.min(), "gap_max": g.max(), "gap_sd": g.std(),
             "negative": int((g < 0).sum())})
g18 = (pd.Series(m["prop_swing"]["by_state"]) - pd.Series(MT[2018]["prop_swing"]["by_state"])).dropna()
rows.append({"id": "prop|states|2018", "units": len(g18), "gap_min": g18.min(), "gap_max": g18.max(), "gap_sd": g18.std(),
             "negative": int((g18 < 0).sum())})
# how far the slope moved between the two reference elections, with no program in either
moved = MT[2018]["prop_swing"]["real"]["slope"] - MT[2022]["prop_swing"]["real"]["slope"]
rows.append({"id": "prop|years", "moved_2018_2022": moved, "times_added": moved / (pl["slope"] - real)})
# why 2018's slope is so much steeper: across states, it rises with the round-1 vote for neither finalist
ps18 = MT[2018]["prop_swing"]
o18 = pd.DataFrame({"others": ps18["others_by_state"], "slope": ps18["by_state"]}).dropna()
top = o18.others.idxmax()
assert top == "CE", top  # the text names Ceará (Ciro Gomes)
rows.append({"id": "prop|others", **{f"others_{y}": MT[y]["prop_swing"]["others"] for y in MT},
             "corr_2018": o18.corr().iloc[0, 1], "top_others": o18.others[top], "top_slope": o18.slope[top],
             "top_rank": int((o18.slope >= o18.slope[top]).sum())})
assert rows[-1]["top_rank"] == 1  # and calls its slope the steepest
rows.append({"id": "shpilkin|bound", "margin_after": margin - m["shpilkin"]["2"]["national"]["lula"]})
# the national figure comes from differences between states: runoff turnout change 2022 -> 2026 in the states
# where Lula had 60% or more in 2026, and in the others
t2 = {y: ST[y][ST[y].turno == 2].set_index("uf") for y in (2026, 2022)}
chg = t2[2026].turnout_pct - t2[2022].turnout_pct
strong = t2[2026].lula_pct >= 60
rows.append({"id": "shpilkin|states", "lula60_states": int(strong.sum()), "lula60_change_pp": chg[strong].mean(),
             "other_change_pp": chg[~strong].mean(), "corr": float(np.corrcoef(chg, t2[2026].lula_pct.loc[chg.index])[0, 1])})
for y in MX:
    for p in MX[y]["planted"]:
        rows.append({"id": f"mixture|planted|{p['planted_sections']}|{y}", "planted_sections": p["planted_sections"],
                     "found_sections": p["sections_extreme"], "f_e": p["f_e"]})
B = json.loads((res_dir / "urna_bursts.json").read_text(encoding="utf-8"))
for g in B["groups"]:
    rows.append({"id": f"bursts|{g['group']}|{g['round']}", **{k: v for k, v in g.items() if k not in ("group", "round")}})
for how in ("run", "mixed"):
    rows.append({"id": f"bursts|planted|{how}", "extra_votes": B["planted"]["extra_votes"],
                 "extra_median": B["planted"].get("extra_median"), **B["planted"][how]})
dump("more_tests", rows)
dump("size_curve", curve)

# three elections: scripts/14_three_elections.py ------------------------------------------------
# one row per test and year (or planted fraud), read by the "Com 2018 também" section
T = json.loads((res_dir / "three_elections.json").read_text(encoding="utf-8"))
rows = []
for y in map(str, T["years"]):
    rows.append({"id": f"ref|{y}", "year": int(y), **T["reference"][y]})
    q = T["quadrant"][y]
    rows.append({"id": f"quad|{y}", "year": int(y), **q, "both_up_share": q["both_up"] / q["sections"]})
    for t, c in T["concentration"][y].items():
        rows.append({"id": f"conc|{y}|{t}", "year": int(y), "round": int(t), **{k: v for k, v in c.items() if k != "hist_lula"},
                     # of the sections with 90% or more for the PT, the share that also had 90% or more turnout
                     "t90_of_lula90": c["turnout_90_lula_90"] / c["lula_90"] if c.get("lula_90") else None})
    e = {k: v for k, v in T["expected"][y].items() if k not in ("mun_top", "mun_hist")}
    rows.append({"id": f"exp|{y}", "year": int(y), **e})
    i = T["isolation"]["years"][y]
    rows.append({"id": f"iso|{y}", "year": int(y), **{k: v for k, v in i.items() if k not in ("kinds", "score_hist", "drivers", "drivers_other")},
                 **{f"kind_{k}": v for k, v in i["kinds"].items()}, **{f"driver_{k}": v for k, v in i["drivers"].items()},
                 **{f"driver_other_{k}": v for k, v in i["drivers_other"].items()}})
for p in T["expected_planted"]:
    rows.append({"id": f"exp|planted|{'all' if p['all'] else p['municipalities']}|{p['flip_share']}",
                 **{k: v for k, v in p.items() if k != "mun_hist"}})
rows.append({"id": "exp|planted|refit", **T["expected_planted_refit"]})
t5 = T["isolation"]["top50"]
rows.append({"id": "iso|top50", **{k: v for k, v in t5.items() if k not in ("rows", "kinds")},
             **{f"kind_{k}": v for k, v in t5["kinds"].items()}})
for p in T["isolation_planted"]:
    rows.append({"id": f"iso|planted|{p['how']}", **{k: v for k, v in p.items() if k != "score_hist"}})
for p in T["quadrant_planted"]:
    rows.append({"id": f"quad|planted|{p['how']}", **p})
rows.append({"id": "meta", "move": T["move"], "cut": T["isolation"]["cut"]})
dump("tres_eleicoes", rows)

# chart series for the "Ver gráfico" panels of "Mais testes" and "Com 2018 também" -----------------
# long format: one row per chart, series and point; charts whose numbers are already in more_tests or
# tres_eleicoes read them there
rows = []
for y, m in MT.items():
    # the sections behind each national slope, in 20 groups; for 2026, also with the planted program
    rows += [{"chart": "prop_bins", "series": str(y), "x": b["x"], "y": b["y"]} for b in m["prop_swing"]["real"]["bins"]]
    if y == 2026:
        pl = next(p for p in m["prop_swing"]["planted"] if p["from"] == "right")
        rows += [{"chart": "prop_bins", "series": "planted", "x": b["x"], "y": b["y"]} for b in pl["bins"]]
    for ref in (2022, 2018):
        for uf, v in m["prop_swing"]["by_state"].items():
            if uf in MT[ref]["prop_swing"]["by_state"] and y == 2026:
                rows.append({"chart": "prop_states", "series": str(ref), "uf": uf, "y": v - MT[ref]["prop_swing"]["by_state"][uf]})
    h = np.array(m["homogeneity"]["p_hist"], float)
    rows += [{"chart": "homog_p", "series": str(y), "x": i * 0.05, "y": v} for i, v in enumerate(h / h.sum())]
    sh = m["shpilkin"]["2"]["national"]
    tot = sum(c["votes"] for c in sh["curve"])
    rows += [{"chart": "shpilkin", "series": str(y), "x": c["turnout"], "lula": c["lula"], "right": c["right"],
              "votes": c["votes"], "y": c["votes"] / tot} for c in sh["curve"]]
    rows.append({"chart": "shpilkin_peak", "series": str(y), "x": sh["peak_turnout"], "lula": sh["peak_lula"], "right": sh["peak_right"]})
    for t in ("2",):
        for cand in ("lula", "right"):
            rows += [{"chart": "benford2", "series": str(y), "cand": cand, "x": d, "y": f}
                     for d, f in enumerate(m["benford2"][t][cand]["freq"])]
rows += [{"chart": "benford2", "series": "expected", "x": d, "y": f} for d, f in enumerate(MT[2026]["benford2_expected"])]
E3 = {k: np.array(v) for k, v in T["edges"].items()}
for y in map(str, T["years"]):
    h = np.array(T["concentration"][y]["2"]["hist_lula"], float)
    rows += [{"chart": "conc_hist", "series": y, "x": float(E3["share"][i]), "y": v} for i, v in enumerate(h / h.sum())]
    rows += [{"chart": "exp_mun", "series": y, "x": float(E3["mun"][i]), "y": int(v)}
             for i, v in enumerate(T["expected"][y]["mun_hist"])]
    h = np.array(T["isolation"]["years"][y]["score_hist"], float)
    rows += [{"chart": "iso_score", "series": y, "x": float(E3["score"][i]), "y": v} for i, v in enumerate(h / h.sum())]
# the chart shows the 10% case: with the model refitted, smaller flips barely move the distribution
p5 = next(p for p in T["expected_planted"] if p["municipalities"] == 1000 and p["flip_share"] == 0.1)
rows += [{"chart": "exp_mun", "series": "planted", "x": float(E3["mun"][i]), "y": int(v)} for i, v in enumerate(p5["mun_hist"])]
rows.append({"chart": "exp_mun_sd", "series": "planted", "y": p5["mun_robust_sd_pp"]})
for p in T["isolation_planted"]:
    h = np.array(p["score_hist"], float)
    rows += [{"chart": "iso_score", "series": f"planted_{p['how']}", "x": float(E3["score"][i]), "y": v} for i, v in enumerate(h / h.sum())]
# long format: each row keeps only its own fields (dump would give every row every column)
(out / "graficos.json").write_text(json.dumps([{k: v for k, v in r.items()} for r in rows], ensure_ascii=False,
                                              separators=(",", ":")), encoding="utf-8")
print(f"graficos: {len(rows)} rows, {(out / 'graficos.json').stat().st_size / 1024:.0f} KB")

# digital signatures and RDV recount of the same sample (scripts/11_urna_assinaturas.py) -----------
sp = res_dir / "urna_assinaturas.csv"
if sp.exists():
    S = pd.read_csv(sp)
    t = S[S.fileset == "Totalizado"]
    F = ["aptos", "comparecimento", "13", "22", "branco", "nulo"]
    bu_pub = (t[[f"bu_{f}" for f in F]].values == t[[f"pub_{f}" for f in F]].values).all(1)
    rdv_bu = ((t[[f"rdv_{f}" for f in F[2:]]].values == t[[f"bu_{f}" for f in F[2:]]].values).all(1)
              & (t.rdv_votos == t.bu_comparecimento).values)
    dump("urna_assinaturas", [{
        "id": "summary", "sampled": len(S), "checked": len(t), "not_totalized": int((S.fileset != "Totalizado").sum()),
        "signatures_valid": int((t.signatures == "valid").sum()), "certificates_ok": int((t.cert_ok == True).sum()),
        "bu_equals_published": int(bu_pub.sum()), "rdv_equals_bu": int(rdv_bu.sum()),
        "tamper_rejected": int((t.tamper_rejected == True).sum()), "votes": int(t.bu_comparecimento.sum()),
        "contingency": int((t.bu_tipo_urna == 4).sum()) if "bu_tipo_urna" in t else None}])

# manual releases by the poll worker in every runoff section (scripts/16_biometria.py) ---------------
bp = res_dir / "biometria.json"
if bp.exists():
    B = json.loads(bp.read_text(encoding="utf-8"))
    rows = [{"id": "national", **{k: B[k] for k in ("sections", "turnout", "manual", "manual_share", "official_sections",
                                                     "missing_sections", "missing_turnout_share", "logs_machines",
                                                     "logs_equal", "logs_within_1")}},
            {"id": "no_bio", **B["no_bio"]}]
    rows += [{"id": f"group|{k}", **v} for k, v in B["groups"].items()]
    rows += [{"id": f"lean|{k}", **v} for k, v in B["lean"].items()]
    st = pd.Series(B["by_state"]).drop("ZZ", errors="ignore")  # no fingerprints are taken abroad
    rows.append({"id": "states", "max_share": st.max(), "max_uf": st.idxmax(), "min_share": st.min(), "min_uf": st.idxmin()})
    dump("biometria", rows)

# numbers asked for by the adversarial review of 29/10/2026 (scripts/17_complementos.py) ------------
cp = res_dir / "complementos.json"
if cp.exists():
    C = json.loads(cp.read_text(encoding="utf-8"))
    rows = [{"id": f"tilt|{y}", **v} for y, v in C["tilt"].items()]
    rows += [{"id": f"gradient|{i}", **g} for i, g in enumerate(C["gradient"])]
    rows += [{"id": "bound70", **C["bound70"]}, {"id": "q4", **C["q4"]}]
    rows += [{"id": f"homog_null|{y}", **v} for y, v in C["homog_null"].items()]
    mm = C["model_mixed"]
    rows.append({"id": "model_mixed", **{k: v for k, v in mm.items() if k != "models"}})
    rows += [{"id": f"model_mixed|{k}", **v} for k, v in mm["models"].items()]
    rows += [{"id": f"count|{y}", **v} for y, v in C["count"].items()]
    dump("complementos", rows)
