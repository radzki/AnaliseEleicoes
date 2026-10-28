"""Tests across three elections (2026, 2022 and 2018), with 2018 as a second reference year.

Usage: python -I scripts/14_three_elections.py <results_dir> <processed_2026> <processed_2022> <processed_2018>

Writes <results_dir>/three_elections.json.

Tests (round 1 -> round 2 unless noted)
  A. Reference. Two tests from 02_analyze.py recomputed for the three years: near-unanimous sections
     (turnout >= 95% and a finalist >= 90%) and sections far from the rest of their polling place
     (|z| > 4). For 2026 and 2022 they must match results_<year>.json.
  B. Sections where one finalist gained votes and the other lost them (the "21 to 1" count). The null
     keeps each municipality's mean gain for each finalist and shuffles the deviations of the sections
     from it, scaled to their size, among sections of the same state whose municipalities had similar mean
     gains (see quad_test); planted vote flips show what a fraud would do to it.
  C. Concentration: sections by a finalist's share (>= 80%, >= 90%), and those with turnout >= 90% and
     the PT candidate >= 90%.
  D. Expected x observed: each section's round-2 result predicted from round 1 by a model trained
     without the section's own municipality (5 folds by municipality), so a change applied to a whole
     municipality cannot hide in the prediction. A planted fraud in whole municipalities shows what
     the test would see.
  E. Isolation Forest and LOF over many measures at once, fitted on the three years together so the
     years share one yardstick: sections above the cut per year, what the most atypical ones are,
     which way they lean, and planted ballot stuffing.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import LocalOutlierFactor

res_dir = Path(sys.argv[1])
PROC = {2026: Path(sys.argv[2]), 2022: Path(sys.argv[3]), 2018: Path(sys.argv[4])}
sys.stdout.reconfigure(encoding="utf-8")
YEARS = (2026, 2022, 2018)
RIGHT = {2026: "v22", 2022: "v22", 2018: "v17"}  # the right-wing finalist: Flávio, Jair, Jair
NAMES = {2026: ("Lula", "Flávio Bolsonaro"), 2022: ("Lula", "Jair Bolsonaro"), 2018: ("Haddad", "Jair Bolsonaro")}
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
PLACE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO"]
MOVE = 4_430_191 // 2 + 1  # as in 10_more_tests.py: half the 2026 margin, plus one
IF_CUT = 0.60  # anomaly score (Liu et al., 2008: 0.5 is an average point, 1 is isolated at once)
# histogram edges for the page's charts: PT share per section, a municipality's gap from the prediction
# (percentage points) and the anomaly score
SHARE_EDGES = np.linspace(0, 1, 51)
MUN_EDGES = np.arange(-12, 12.0001, 0.25)
SCORE_EDGES = np.arange(0.30, 0.80001, 0.005)
rng = np.random.default_rng(14)
res = {"years": list(YEARS), "edges": {"share": SHARE_EDGES.tolist(), "mun": MUN_EDGES.tolist(), "score": SCORE_EDGES.round(3).tolist()}, "names": {y: list(n) for y, n in NAMES.items()}, "move": MOVE}


def log(*a):
    print(*a, flush=True)


def loo_z(df, group, num, den):
    """The section against the rest of its group, as in 02_analyze.py."""
    g = df.groupby(group, sort=False)
    rest_num = g[num].transform("sum") - df[num]
    rest_den = g[den].transform("sum") - df[den]
    ok = rest_den > 0
    p_rest = np.where(ok, rest_num / rest_den.where(ok, 1), np.nan)
    p_i = df[num] / df[den]
    pool = (df[num] + rest_num) / (df[den] + rest_den)
    se = np.sqrt(pool * (1 - pool) * (1 / df[den] + 1 / rest_den.where(ok, np.nan)))
    return ((p_i - p_rest) / se).replace([np.inf, -np.inf], np.nan)


def load(year):
    w = pd.read_parquet(PROC[year] / "secao_wide.parquet")
    w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)].copy()
    vcols = [c for c in w.columns if c.startswith("v") and c[1:].isdigit()]
    w[vcols] = w[vcols].fillna(0).astype(np.int64)
    for c in ["QT_APTOS", "QT_COMPARECIMENTO", "QT_VOTOS_NOMINAIS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS"]:
        w[c] = w[c].fillna(0).astype(np.int64)
    w = w.rename(columns={RIGHT[year]: "vR"})
    w["n"] = w.QT_VOTOS_NOMINAIS
    w["sL"], w["sR"] = w.v13 / w.n, w.vR / w.n
    w["turnout"] = w.QT_COMPARECIMENTO / w.QT_APTOS
    w["bn"] = w.QT_VOTOS_BRANCOS + w.QT_VOTOS_NULOS
    # the four largest other candidates of round 1, nationally
    r1 = w[w.NR_TURNO == 1]
    others = r1[[c for c in vcols if c not in ("v13", RIGHT[year])]].sum().nlargest(4).index.tolist()
    return w, others


W, OTHERS = {}, {}
for y in YEARS:
    W[y], OTHERS[y] = load(y)
    log(y, "sections per round:", W[y].groupby("NR_TURNO").size().to_dict(), "| others in the model:", OTHERS[y])


# ---------------------------------------------------------------------------------
# A. Reference tests, three years
log("A. reference tests")
res["reference"] = {}
for y in YEARS:
    g = W[y][W[y].NR_TURNO == 2].copy()
    big = g[g.QT_APTOS >= 100]
    z = loo_z(g, PLACE, "v13", "n")
    res["reference"][y] = {
        "corner_lula": int(((big.turnout >= 0.95) & (big.sL >= 0.9)).sum()),
        "corner_right": int(((big.turnout >= 0.95) & (big.sR >= 0.9)).sum()),
        "place_pos4": int((z > 4).sum()), "place_neg4": int((z < -4).sum()), "sections": int(len(g)),
    }
    log(f"  {y}:", res["reference"][y])
    pub = res_dir / f"results_{y}.json"
    if pub.exists():  # the same numbers the page already shows
        R = json.loads(pub.read_text(encoding="utf-8"))
        want = (R["fingerprint"]["2"]["corner_lula"], R["fingerprint"]["2"]["corner_right"],
                R["place_z"]["2"]["Lula share"]["pos_4"], R["place_z"]["2"]["Lula share"]["neg_4"])
        got = tuple(res["reference"][y][k] for k in ("corner_lula", "corner_right", "place_pos4", "place_neg4"))
        assert got == want, f"{y}: {got} != results_{y}.json {want}"
        log("    matches", pub.name)


# ---------------------------------------------------------------------------------
# sections matched between the two rounds
def matched(y):
    w = W[y]
    cols = SEC + ["v13", "vR", "n", "bn", "QT_APTOS", "QT_COMPARECIMENTO", "turnout"]
    r1 = w[w.NR_TURNO == 1][cols + OTHERS[y]]
    r2 = w[w.NR_TURNO == 2][cols + ["NR_LOCAL_VOTACAO", "NM_MUNICIPIO", "NM_LOCAL_VOTACAO"]]
    s = r1.merge(r2, on=SEC, suffixes=("_1", "_2"))
    s = s[(s.v13_1 + s.vR_1 > 0) & (s.v13_2 + s.vR_2 > 0)].reset_index(drop=True)
    s["NM_LOCAL_VOTACAO"] = s.NM_LOCAL_VOTACAO.fillna("")
    s["mun"] = s.SG_UF + "|" + s.CD_MUNICIPIO.astype(str)
    s["p1"] = s.v13_1 / (s.v13_1 + s.vR_1)
    s["p2"] = s.v13_2 / (s.v13_2 + s.vR_2)
    return s


S = {y: matched(y) for y in YEARS}


# ---------------------------------------------------------------------------------
# B. One finalist gained votes and the other lost them
def quad(gl, gr):
    return int(((gl > 0) & (gr < 0)).sum()), int(((gr > 0) & (gl < 0)).sum())


def quad_test(s, L2, R2, reps):
    """The count in the data and in two nulls. Both keep each municipality's mean gain for each finalist and
    give each section the deviation of another section, scaled to its size. The first draws that section from
    the whole state; it gets the minority count wrong the same way in the three years (too many where the
    trailing gainer gained a lot on average), because deviations differ between places with small and large
    gains. The second, the one the page uses, draws only among sections of the same state whose
    municipalities had similar mean gains (fifths of each finalist's mean gain)."""
    gl, gr = (L2 - s.v13_1.values).astype(float), (R2 - s.vR_1.values).astype(float)
    n = s.QT_COMPARECIMENTO_1.values.astype(float)
    mun = s.mun.values
    tot = pd.Series(n).groupby(mun).transform("sum").values
    mx = pd.Series(gl).groupby(mun).transform("sum").values / tot
    mz = pd.Series(gr).groupby(mun).transform("sum").values / tot
    rx, rz = (gl / n - mx) * np.sqrt(n), (gr / n - mz) * np.sqrt(n)
    a, b = quad(gl, gr)
    lead = 0 if a >= b else 1
    out = {"lula_up_right_down": a, "right_up_lula_down": b, "ratio": max(a, b) / min(a, b),
           "leader": ["lula", "right"][lead], "both_up": int(((gl > 0) & (gr > 0)).sum()),
           "gain_lula": int(gl.sum()), "gain_right": int(gr.sum())}
    bands = pd.qcut(mx, 5, labels=False, duplicates="drop").astype(str) + "|" + pd.qcut(mz, 5, labels=False, duplicates="drop").astype(str)
    for key, strata in (("null_state", s.SG_UF.values), ("null", (s.SG_UF + "|" + bands).values)):
        codes = pd.factorize(strata)[0]
        groups = [np.where(codes == c)[0] for c in range(codes.max() + 1)]
        sims = []
        for _ in range(reps):
            idx = np.arange(len(s))
            for m in groups:
                idx[m] = rng.permutation(m)
            sims.append(quad(np.rint(mx * n + rx[idx] * np.sqrt(n)), np.rint(mz * n + rz[idx] * np.sqrt(n))))
        sims = np.array(sims)
        ratio = sims[:, lead] / sims[:, 1 - lead]
        out.update({f"{key}_lula_up_right_down": float(sims[:, 0].mean()), f"{key}_right_up_lula_down": float(sims[:, 1].mean()),
                    f"{key}_ratio": float(ratio.mean()), f"{key}_ratio_min": float(ratio.min()), f"{key}_ratio_max": float(ratio.max())})
    out["leftover"] = out["ratio"] / out["null_ratio"]
    out["leftover_state"] = out["ratio"] / out["null_state_ratio"]
    return out


log("B. one gained, the other lost")
res["quadrant"] = {}
for y in YEARS:
    s = S[y][S[y].QT_COMPARECIMENTO_1 >= 20].reset_index(drop=True)
    res["quadrant"][y] = {"sections": int(len(s)), **quad_test(s, s.v13_2.values, s.vR_2.values, 20)}
    q = res["quadrant"][y]
    log(f"  {y}: {q['lula_up_right_down']:,} vs {q['right_up_lula_down']:,} = {q['ratio']:.1f}:1 | null {q['null_ratio']:.1f}:1"
        f" ({q['null_ratio_min']:.1f}-{q['null_ratio_max']:.1f}), data/null {q['leftover']:.2f} | state-only null {q['null_state_ratio']:.1f}:1,"
        f" data/null {q['leftover_state']:.2f}")
# planted, 2026: MOVE of Flávio's runoff votes flipped to Lula, in every section or in a fifth of them
s = S[2026][S[2026].QT_COMPARECIMENTO_1 >= 20].reset_index(drop=True)
L2, R2 = s.v13_2.values.astype(np.int64), s.vR_2.values.astype(np.int64)
res["quadrant_planted"] = []
for how, share in (("all", 1.0), ("fifth", 0.2)):
    pick = (rng.random(len(s)) < share).astype(np.int64)
    q = MOVE / (R2 * pick).sum()
    k = rng.binomial(R2 * pick, q)
    res["quadrant_planted"].append({"how": how, "sections_share": share, "flip_share": float(q), "votes": int(k.sum()),
                                    **quad_test(s, L2 + k, R2 - k, 10)})
    p = res["quadrant_planted"][-1]
    log(f"  planted in {share:.0%} of sections ({q:.1%} of Flávio's votes there, {k.sum():,} votes): {p['ratio']:.1f}:1,"
        f" null {p['null_ratio']:.1f}:1, data/null {p['leftover']:.2f}")


# ---------------------------------------------------------------------------------
# C. Concentration
log("C. concentration")
res["concentration"] = {}
for y in YEARS:
    res["concentration"][y] = {}
    for t, g in W[y].groupby("NR_TURNO"):
        res["concentration"][y][int(t)] = {
            "sections": int(len(g)),
            "lula_80": int((g.sL >= 0.8).sum()), "lula_90": int((g.sL >= 0.9).sum()),
            "right_80": int((g.sR >= 0.8).sum()), "right_90": int((g.sR >= 0.9).sum()),
            "turnout_90_lula_90": int(((g.turnout >= 0.9) & (g.sL >= 0.9)).sum()),
            "turnout_90_right_90": int(((g.turnout >= 0.9) & (g.sR >= 0.9)).sum()),
            "turnout": float(g.QT_COMPARECIMENTO.sum() / g.QT_APTOS.sum()),
            # sections where one finalist had 80% or more: how divided the vote is between places
            "one_sided_80": float(((g.sL >= 0.8) | (g.sR >= 0.8)).mean()),
            "hist_lula": np.histogram(g.sL, SHARE_EDGES)[0].tolist(),
        }
    log(f"  {y}:", res["concentration"][y])


# ---------------------------------------------------------------------------------
# D. Expected x observed, without the section's own municipality
def features(s, y):
    c1 = s.QT_COMPARECIMENTO_1.clip(lower=1)
    X = pd.DataFrame({"sL1": s.v13_1 / s.n_1, "sR1": s.vR_1 / s.n_1, "bn1": s.bn_1 / c1,
                      "t1": s.turnout_1, "dt": s.turnout_2 - s.turnout_1, "logaptos": np.log(s.QT_APTOS_2.clip(lower=1))})
    for i, c in enumerate(OTHERS[y]):
        X[f"o{i}"] = s[c] / s.n_1
    X["uf"] = pd.Categorical(s.SG_UF).codes
    return X


log("D. expected x observed")
res["expected"] = {}
EXP = {}
for y in YEARS:
    s = S[y]
    X = features(s, y)
    yv = logit(((s.v13_2 + 0.5) / (s.v13_2 + s.vR_2 + 1)).values)
    wt = (s.v13_2 + s.vR_2).values.astype(float)
    pred = np.empty(len(s))
    for tr, te in GroupKFold(n_splits=5).split(X, yv, s.mun):
        m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.08, max_leaf_nodes=63,
                                          categorical_features=[X.columns.get_loc("uf")], random_state=y)
        m.fit(X.iloc[tr], yv[tr], sample_weight=wt[tr])
        pred[te] = m.predict(X.iloc[te])
    ph = expit(pred)
    r = (s.p2.values - ph) * 100  # percentage points
    rsd = 1.4826 * np.median(np.abs(r - np.median(r)))
    mun = pd.DataFrame({"mun": s.mun, "name": s.NM_MUNICIPIO, "uf": s.SG_UF, "r": r, "w": wt,
                        "dv": (s.p2.values - ph) * wt})
    mg = mun.groupby("mun").agg(name=("name", "first"), uf=("uf", "first"), w=("w", "sum"), dv=("dv", "sum"),
                                sections=("r", "size"))
    mg["mean_pp"] = mg.dv / mg.w * 100
    mg = mg[mg.sections >= 3]
    msd = 1.4826 * np.median(np.abs(mg.mean_pp - mg.mean_pp.median()))
    EXP[y] = {"s": s, "ph": ph, "wt": wt, "mun": mg}
    res["expected"][y] = {
        "sections": int(len(s)), "rmse_pp": float(np.sqrt(np.average(r ** 2, weights=wt))), "robust_sd_pp": float(rsd),
        "pos_4sd": int((r > 4 * rsd).sum()), "neg_4sd": int((r < -4 * rsd).sum()),
        "net_votes": float(mun.dv.sum()),
        "municipalities": int(len(mg)), "mun_robust_sd_pp": float(msd),
        "mun_pos_4sd": int((mg.mean_pp > 4 * msd).sum()), "mun_neg_4sd": int((mg.mean_pp < -4 * msd).sum()),
        "mun_hist": np.histogram(mg.mean_pp.clip(-11.99, 11.99), MUN_EDGES)[0].tolist(),
        "mun_top": mg.reindex(mg.mean_pp.abs().sort_values(ascending=False).index).head(10)
                     [["name", "uf", "sections", "mean_pp"]].round(3).to_dict("records"),
    }
    e = res["expected"][y]
    log(f"  {y}: rmse {e['rmse_pp']:.2f} pp, robust sd {rsd:.2f} | sections beyond 4 sd: +{e['pos_4sd']} -{e['neg_4sd']}"
        f" | municipalities beyond 4 sd: +{e['mun_pos_4sd']} -{e['mun_neg_4sd']} (sd {msd:.2f} pp) | net {e['net_votes']:+,.0f}")

# planted, 2026: a program that flips a fixed share of Flávio's runoff votes in whole municipalities.
# The model is refitted on the changed data each time: the planted municipalities also sit in the other
# folds' training data, and with the program in every municipality that is what hides it.
def refit(s, y, yv, wt):
    X = features(s, y)
    pred = np.empty(len(s))
    for tr, te in GroupKFold(n_splits=5).split(X, yv, s.mun):
        m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.08, max_leaf_nodes=63,
                                          categorical_features=[X.columns.get_loc("uf")], random_state=y)
        m.fit(X.iloc[tr], yv[tr], sample_weight=wt[tr])
        pred[te] = m.predict(X.iloc[te])
    return expit(pred)


e, s = EXP[2026], EXP[2026]["s"]
res["expected_planted"] = []
for k, q in ((1000, 0.02), (1000, 0.05), (1000, 0.10), (None, 0.05)):
    pick = e["mun"].index.values if k is None else rng.choice(e["mun"].index.values, k, replace=False)
    inm = s.mun.isin(pick).values
    flip = rng.binomial(s.vR_2.values * inm, q)
    L2 = s.v13_2.values + flip
    ph = refit(s, 2026, logit((L2 + 0.5) / (e["wt"] + 1)), e["wt"])
    mg = pd.DataFrame({"mun": s.mun, "dv": (L2 / e["wt"] - ph) * e["wt"], "w": e["wt"]}).groupby("mun").sum()
    mg = mg.loc[e["mun"].index]
    mean = mg.dv / mg.w * 100
    msd = 1.4826 * np.median(np.abs(mean - mean.median()))
    caught = int((mean.loc[pick] > 4 * msd).sum())
    res["expected_planted"].append({"municipalities": len(pick), "all": k is None, "flip_share": q, "votes": int(flip.sum()),
                                    "mun_robust_sd_pp": float(msd),
                                    "mun_hist": np.histogram(mean.clip(-11.99, 11.99), MUN_EDGES)[0].tolist(),
                                    "caught": caught, "flagged_total": int((mean > 4 * msd).sum())})
    log(f"  planted, {q:.0%} of Flávio's votes in {len(pick)} municipalities ({flip.sum():,} votes), model refitted: {caught} of them"
        f" flagged, {res['expected_planted'][-1]['flagged_total']} in all")
p = res["expected_planted"][-1]
res["expected_planted_refit"] = {"flip_share": p["flip_share"], "votes": p["votes"], "flagged": p["flagged_total"]}


# ---------------------------------------------------------------------------------
# E. Isolation Forest and LOF
KIND = [("prison", r"PRES[IÍ]DIO|PENITENCI|CADEIA|PRISIONAL|DETEN[CÇ][AÃ]O|CDP\b|CARCER|SOCIOEDUCA|INTERNA[CÇ][AÃ]O|FUNDA[CÇ][AÃ]O CASA|CASE\b"),
        ("indigenous", r"ALDEIA|IND[IÍ]GENA")]


def place_kind(r):
    """What a flagged section is, in the order checked: abroad, prison or youth detention, indigenous
    village, fewer than 100 voters, turnout changing 20 points or more between rounds, or none of these."""
    if r.SG_UF == "ZZ":
        return "abroad"
    for k, pat in KIND:
        if re.search(pat, r.NM_LOCAL_VOTACAO, re.I):
            return k
    if r.QT_APTOS_2 < 100:
        return "small"
    return "turnout_change" if abs(r.turnout_2 - r.turnout_1) >= 0.2 else "other"


def if_features(s):
    c1, c2 = s.QT_COMPARECIMENTO_1.clip(lower=1), s.QT_COMPARECIMENTO_2.clip(lower=1)
    zl = loo_z(s.assign(L=s.v13_2, N=s.v13_2 + s.vR_2), PLACE, "L", "N").fillna(0).clip(-10, 10)
    zt = loo_z(s.assign(T=s.QT_COMPARECIMENTO_2, A=s.QT_APTOS_2), PLACE, "T", "A").fillna(0).clip(-10, 10)
    return pd.DataFrame({
        "sL1": s.v13_1 / s.n_1, "sR1": s.vR_1 / s.n_1, "bn1": s.bn_1 / c1, "t1": s.turnout_1.clip(0, 1),
        "p2": s.p2, "bn2": s.bn_2 / c2, "t2": s.turnout_2.clip(0, 1), "swing": s.p2 - s.p1,
        "dt": s.turnout_2 - s.turnout_1, "logaptos": np.log(s.QT_APTOS_2.clip(lower=1)), "zL": zl, "zT": zt,
    }), zl


log("E. Isolation Forest and LOF")
F, ZL = {}, {}
for y in YEARS:
    F[y], ZL[y] = if_features(S[y])
# one yardstick for the three years: fit on an equal sample of each, then score every section
fit = pd.concat([F[y].sample(150_000, random_state=y) for y in YEARS])
mu, sd = fit.mean(), fit.std()
med, mad = fit.median(), 1.4826 * (fit - fit.median()).abs().median().replace(0, 1e-9)
iso = IsolationForest(n_estimators=400, max_samples=512, random_state=14).fit(fit)
lof = LocalOutlierFactor(n_neighbors=35, novelty=True).fit(((fit - mu) / sd).sample(60_000, random_state=1).values)
res["isolation"] = {"cut": IF_CUT, "years": {}}
SCORES = {}
for y in YEARS:
    sc = -iso.score_samples(F[y])
    lo = -lof.score_samples(((F[y] - mu) / sd).values)
    SCORES[y] = sc
    flag = sc > IF_CUT
    s = S[y]
    kinds = pd.Series([place_kind(r) for r in s[flag].itertuples()])
    res["isolation"]["years"][y] = {
        "sections": int(len(s)), "flagged": int(flag.sum()), "per_100k": float(flag.mean() * 1e5),
        # sections abroad (few voters, one-sided votes) are most of the flagged ones: the rate without them
        "per_100k_brazil": float(flag[(s.SG_UF != "ZZ").values].mean() * 1e5),
        "kinds": kinds.value_counts().to_dict(),
        "lean_lula": int((flag & (ZL[y] > 2)).sum()), "lean_right": int((flag & (ZL[y] < -2)).sum()),
        "voters": int(s.QT_COMPARECIMENTO_2[flag].sum()),
        "score_q999": float(np.quantile(sc, 0.999)),
        # the measure farthest from typical (robust z against the three years together), per flagged section
        "drivers": pd.Series(np.abs(((F[y][flag] - med) / mad).values).argmax(axis=1)).map(dict(enumerate(F[y].columns))).value_counts().to_dict(),
        "drivers_other": pd.Series(np.abs(((F[y][flag][(kinds == "other").values] - med) / mad).values).argmax(axis=1))
                           .map(dict(enumerate(F[y].columns))).value_counts().to_dict(),
        "score_hist": np.histogram(sc.clip(SCORE_EDGES[0], SCORE_EDGES[-1] - 1e-9), SCORE_EDGES)[0].tolist(),
        # a second cut, the score of the top 1% of 2026, so the comparison does not hang on 0.60
        "per_100k_top1pct": float((sc > np.quantile(SCORES[2026], 0.99)).mean() * 1e5),
    }
    if y == 2026:
        top = np.argsort(-sc)[:50]
        lof5 = np.quantile(lo, 0.95)
        rows = s.iloc[top]
        res["isolation"]["top50"] = {
            "in_lof_top5": int((lo[top] >= lof5).sum()),
            "aptos_median": float(rows.QT_APTOS_2.median()), "aptos_below_100": int((rows.QT_APTOS_2 < 100).sum()),
            "kinds": pd.Series([place_kind(r) for r in rows.itertuples()]).value_counts().to_dict(),
            "lean_lula": int((ZL[y].iloc[top] > 2).sum()), "lean_right": int((ZL[y].iloc[top] < -2).sum()),
            "rows": [{"uf": r.SG_UF, "municipio": r.NM_MUNICIPIO, "local": r.NM_LOCAL_VOTACAO, "aptos": int(r.QT_APTOS_2),
                      "score": float(sc[i]), "kind": place_kind(r),
                      "turnout_1": float(r.turnout_1), "turnout_2": float(r.turnout_2), "p1": float(r.p1), "p2": float(r.p2)}
                     for i, r in zip(top, rows.itertuples())],
        }
        res["isolation"]["share_below_100_all"] = float((s.QT_APTOS_2 < 100).mean())
    log(f"  {y}: {flag.sum():,} above {IF_CUT} ({flag.mean() * 1e5:.0f} per 100k) | kinds {res['isolation']['years'][y]['kinds']}"
        f" | lean Lula {res['isolation']['years'][y]['lean_lula']}, right {res['isolation']['years'][y]['lean_right']}")
t5 = res["isolation"]["top50"]
log(f"  2026 top 50: {t5['in_lof_top5']} in LOF's top 5%, median {t5['aptos_median']:.0f} voters, kinds {t5['kinds']}")

# planted, 2026: ballot stuffing, votes for Lula added until turnout reaches 98% (extreme), or 10% of
# the electorate added for Lula (incremental), in random sections of 100 or more voters
s, base = S[2026], F[2026]
res["isolation_planted"] = []
eligible = np.where(s.QT_APTOS_2.values >= 100)[0]
for how, k in (("extreme", 100), ("incremental", 1000)):
    pick = rng.choice(eligible, k, replace=False)
    p = s.iloc[pick].copy()
    add = (np.floor(0.98 * p.QT_APTOS_2) - p.QT_COMPARECIMENTO_2).clip(lower=0) if how == "extreme" else np.floor(0.10 * p.QT_APTOS_2)
    add = np.minimum(add, (p.QT_APTOS_2 - p.QT_COMPARECIMENTO_2).clip(lower=0))
    s2 = s.copy()
    s2.loc[p.index, "v13_2"] += add.astype(np.int64)
    s2.loc[p.index, "QT_COMPARECIMENTO_2"] += add.astype(np.int64)
    s2["turnout_2"] = s2.QT_COMPARECIMENTO_2 / s2.QT_APTOS_2
    s2["p2"] = s2.v13_2 / (s2.v13_2 + s2.vR_2)
    f2, _ = if_features(s2)
    sc = -iso.score_samples(f2.iloc[pick])
    res["isolation_planted"].append({"how": how, "sections": k, "votes_added": int(add.sum()),
                                     "score_hist": np.histogram(sc.clip(SCORE_EDGES[0], SCORE_EDGES[-1] - 1e-9), SCORE_EDGES)[0].tolist(),
                                     "caught": int((sc > IF_CUT).sum()),
                                     "caught_top1pct": int((sc > np.quantile(SCORES[2026], 0.99)).sum())})
    log("  planted:", res["isolation_planted"][-1])

(res_dir / "three_elections.json").write_text(json.dumps(res, ensure_ascii=False, default=int), encoding="utf-8")
log("done ->", res_dir / "three_elections.json")
