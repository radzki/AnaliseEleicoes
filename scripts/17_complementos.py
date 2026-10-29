"""Numbers the page needs to state some results honestly, from the adversarial review of 29/10/2026
(docs/revisao-2026-10-29.md; the item each block serves is in its comment).

Usage: python -I scripts/17_complementos.py <results_dir> <processed_2026> <processed_2022> <processed_2018>

Writes <results_dir>/complementos.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

out, p26, p22, p18 = (Path(a) for a in sys.argv[1:5])
sys.stdout.reconfigure(encoding="utf-8")
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
PLACE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO"]
rng = np.random.default_rng(1729)
res = {}


def log(*a):
    print(*a, flush=True)


def load(proc, year):
    w = pd.read_parquet(proc / "secao_wide.parquet")
    if year == 2018:
        w = w.rename(columns={"v17": "v22"})
    w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)].copy()
    for c in ["v13", "v22", "QT_APTOS", "QT_COMPARECIMENTO", "QT_VOTOS_NOMINAIS"]:
        w[c] = w[c].fillna(0).astype(np.int64)
    w["n"] = w.QT_VOTOS_NOMINAIS
    return w


def loo_z(df, num, den):
    """As in scripts/02_analyze.py: a section against the rest of its polling place."""
    g = df.groupby(PLACE, sort=False)
    rest_num = g[num].transform("sum") - df[num]
    rest_den = g[den].transform("sum") - df[den]
    ok = rest_den > 0
    p_rest = np.where(ok, rest_num / rest_den.where(ok, 1), np.nan)
    pool = (df[num] + rest_num) / (df[den] + rest_den)
    se = np.sqrt(pool * (1 - pool) * (1 / df[den] + 1 / rest_den.where(ok, np.nan)))
    return ((df[num] / df[den] - p_rest) / se).replace([np.inf, -np.inf], np.nan)


W = {2026: load(p26, 2026), 2022: load(p22, 2022), 2018: load(p18, 2018)}

# ---------------------------------------------------------------------------------
# item 3: sections with atypically high turnout for their place (z > 4) that also lean to Lula,
# against the share of all sections that lean to Lula, and whether they already did in round 1
res["tilt"] = {}
for year in (2026, 2022):
    zs = {}
    for t in (1, 2):
        g = W[year][W[year].NR_TURNO == t].copy()
        g["zL"], g["zT"] = loo_z(g, "v13", "n"), loo_z(g, "QT_COMPARECIMENTO", "QT_APTOS")
        zs[t] = g.set_index(SEC)[["zL", "zT"]]
    r2 = zs[2].dropna()
    hi = r2[r2.zT > 4]
    base = float((r2.zL > 0).mean())
    k, n = int((hi.zL > 0).sum()), len(hi)
    z = (k / n - base) / np.sqrt(base * (1 - base) / n)
    both = hi.join(zs[1].add_suffix("_1"), how="inner").dropna()
    res["tilt"][year] = {"n": n, "share_pos": k / n, "base": base, "z_vs_base": float(z),
                         "r1_matched": int(len(both)), "r1_share_pos": float((both.zL_1 > 0).mean()),
                         "r1_already_high": float((both.zT_1 > 4).mean())}
    log("tilt", year, res["tilt"][year])

# ---------------------------------------------------------------------------------
# items 2 and 13i: turnout change from 2022 to 2026, section by section, by how pro-Lula the section was
# in 2022; and how many voters that would be if all of it above the balanced sections' rise were fake
key = SEC
a = W[2026][W[2026].NR_TURNO == 2]
b = W[2022][W[2022].NR_TURNO == 2]
m = a[key + ["QT_APTOS", "QT_COMPARECIMENTO", "v13", "v22"]].merge(
    b[key + ["QT_APTOS", "QT_COMPARECIMENTO", "v13", "v22"]], on=key, suffixes=("", "_22"))
m = m[(m.QT_APTOS >= 100) & (m.QT_APTOS_22 >= 100)].copy()
m["lula22"] = m.v13_22 / (m.v13_22 + m.v22_22)
m["lula26"] = m.v13 / (m.v13 + m.v22)
turnout = lambda d, suf="": d[f"QT_COMPARECIMENTO{suf}"].sum() / d[f"QT_APTOS{suf}"].sum()
EDGES = [0, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0001]
res["gradient"] = []
for lo, hi_ in zip(EDGES[:-1], EDGES[1:]):
    d = m[(m.lula22 >= lo) & (m.lula22 < hi_)]
    res["gradient"].append({"lo": lo, "hi": min(hi_, 1.0), "sections": int(len(d)),
                            "change_pp": 100 * float(turnout(d) - turnout(d, "_22"))})
margin = int(a.v13.sum() - a.v22.sum())
mid = m[(m.lula22 >= 0.4) & (m.lula22 <= 0.6) & (m.lula26 >= 0.4) & (m.lula26 <= 0.6)]
mid_change = float(turnout(mid) - turnout(mid, "_22"))
strong = m[m.lula22 >= 0.7]
# every voter of these sections above what their 2022 turnout gives, and above what the balanced
# sections' rise gives
excess = float((strong.QT_COMPARECIMENTO - strong.QT_APTOS * strong.QT_COMPARECIMENTO_22 / strong.QT_APTOS_22).sum())
excess_mid = float((strong.QT_COMPARECIMENTO - strong.QT_APTOS * (strong.QT_COMPARECIMENTO_22 / strong.QT_APTOS_22 + mid_change)).sum())
res["bound70"] = {"sections": int(len(strong)), "excess": excess, "excess_share": excess / margin,
                  "excess_vs_mid": excess_mid, "excess_vs_mid_share": excess_mid / margin, "mid_change_pp": 100 * mid_change,
                  "margin": margin}
l90 = m[m.lula26 >= 0.9]
res["q4"] = {"lula90_turnout_22": float(turnout(l90, "_22")), "lula90_turnout_26": float(turnout(l90)),
             "lula90_change_pp": 100 * float(turnout(l90) - turnout(l90, "_22")),
             "mid_turnout_22": float(turnout(mid, "_22")), "mid_turnout_26": float(turnout(mid)), "mid_change_pp": 100 * mid_change}
log("gradient", res["gradient"]); log("bound70", res["bound70"]); log("q4", res["q4"])

# ---------------------------------------------------------------------------------
# item 6: the chi-squared dispersion per polling place (as in scripts/10_more_tests.py) when only chance
# acts: each section's Lula votes drawn from its place's pooled share; the median of the dispersion
res["homog_null"] = {}
for year, w in W.items():
    d = w[w.NR_TURNO == 2][PLACE + ["v13", "v22"]].copy()
    d["n"] = d.v13 + d.v22
    d = d[d.n > 0]
    d["place"] = d.groupby(PLACE, sort=False).ngroup()
    g = d.groupby("place")
    P = (g.v13.transform("sum") / g.n.transform("sum")).values
    k = g.n.transform("size").values
    keep = (k > 1) & (P > 0) & (P < 1)
    d, P = d[keep], P[keep]
    n, place = d.n.values, d.place.values
    meds = []
    for _ in range(20):
        L = rng.binomial(n, P)
        # the place's share is estimated from the drawn votes, as the test does with the real ones
        Ps = (pd.Series(L).groupby(place).transform("sum") / pd.Series(n).groupby(place).transform("sum")).values
        ok = (Ps > 0) & (Ps < 1)
        Ps = np.where(ok, Ps, 0.5)
        chi = np.where(ok, (L - n * Ps) ** 2 / (n * Ps) + ((n - L) - n * (1 - Ps)) ** 2 / (n * (1 - Ps)), np.nan)
        s = pd.DataFrame({"chi": chi, "place": place}).dropna().groupby("place").chi.agg(["sum", "size"])
        s = s[s["size"] > 1]
        meds.append(float((s["sum"] / (s["size"] - 1)).median()))
    res["homog_null"][year] = {"median": float(np.mean(meds)), "sims": len(meds)}
    log("homog null", year, res["homog_null"][year])

# ---------------------------------------------------------------------------------
# item 13a: each machine model against the other models in the same polling place, only where a
# place has more than one model (2026 runoff), with a standard error clustered by place
w = W[2026][W[2026].NR_TURNO == 2].copy()
w["lula"] = w.v13 / w.n
w["place"] = w.groupby(PLACE, sort=False).ngroup()
nm = w.groupby("place").DS_MODELO_URNA.transform("nunique")
mx = w[nm > 1]
res["model_mixed"] = {"sections": int(len(mx)), "share_sections": float(len(mx) / len(w)), "places": int(mx.place.nunique()),
                      "models": {}}
for mod, dm in mx.groupby("DS_MODELO_URNA"):
    rows = []
    for pl, gp in mx[mx.place.isin(dm.place.unique())].groupby("place"):
        mine, other = gp[gp.DS_MODELO_URNA == mod], gp[gp.DS_MODELO_URNA != mod]
        if len(mine) and len(other):
            rows.append((mine.v13.sum() / mine.n.sum() - other.v13.sum() / other.n.sum(), mine.n.sum()))
    if len(rows) < 30:
        continue
    diff, wt = np.array(rows).T
    est = float(np.average(diff, weights=wt))
    se = float(np.sqrt(np.sum((wt * (diff - est)) ** 2)) / wt.sum())
    res["model_mixed"]["models"][mod] = {"places": len(rows), "diff_pp": 100 * est, "se_pp": 100 * se}
mm = res["model_mixed"]["models"]
top = max(mm, key=lambda k: abs(mm[k]["diff_pp"]))
res["model_mixed"].update({"max_model": top, "max_diff_pp": mm[top]["diff_pp"], "max_se_pp": mm[top]["se_pp"]})
log("models in mixed places", res["model_mixed"])

# ---------------------------------------------------------------------------------
# item 11: Lula's share between the two along the 2026 and 2022 runoff counts, in the order the tally
# reports reached the TSE: where it starts, its low point and where it passes 50% for good
res["count"] = {}
for year in (2026, 2022):
    d = W[year][W[year].NR_TURNO == 2].copy()
    d["arr"] = pd.to_datetime(d.DT_RECEBIMENTO_BU_HOR_TSE, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    d = d.sort_values("arr")
    two = (d.v13 + d.v22).values
    frac = np.cumsum(two) / two.sum()
    share = np.cumsum(d.v13.values) / np.cumsum(two)
    after1 = frac >= 0.01
    i = int(np.argmin(np.where(after1, share, np.inf)))
    below = np.where(share < 0.5)[0]
    last_below = int(below.max()) if len(below) else -1
    res["count"][year] = {"start": float(share[np.searchsorted(frac, 0.01)]), "low": float(share[i]), "low_at": float(frac[i]),
                          "above_50_from": float(frac[last_below + 1]) if last_below + 1 < len(frac) else None,
                          "final": float(share[-1])}
    log("count", year, res["count"][year])

(out / "complementos.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
log("done ->", out / "complementos.json")
