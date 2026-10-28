"""More forensic tests on section-level results, run the same way on each election year.

Usage: python -I scripts/10_more_tests.py <processed_dir> <out_dir> <year>

Writes <out_dir>/more_tests_<year>.json.

Tests (runoff unless noted)
  A. Section size. A program that flips votes only in machines above N voters would make Lula's
     share, relative to the rest of the polling place, jump at N. Scanned over N.
  B. Proportional swing. A program that flips a fixed share of a candidate's runoff votes takes more
     where that candidate is strong, so the round-1 -> round-2 swing grows with the opponent's
     round-1 share, within the polling place. Compared with the other year.
  C. Homogeneity within the polling place: chi-squared of each place's sections (Lula x right).
  D. Shpilkin: votes beyond the share found at the most common turnout, nationally and per state.
  E. Second-digit Benford (Mebane), both rounds, shown only as a contrast between years.

For A and B, the fraud each test looks for is also planted in the real data, sized to move enough
votes to change the 2026 result, to show what the test would have seen.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

proc, out, year = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8")
rng = np.random.default_rng(year + 10)
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
PLACE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO"]
# votes the 2026 runoff winner would have needed to lose (half the margin, plus one): the size of
# the planted frauds, in both years, so they are comparable
MOVE = 4_430_191 // 2 + 1

w = pd.read_parquet(proc / "secao_wide.parquet")
w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)].copy()
for c in ["v13", "v22", "QT_APTOS", "QT_COMPARECIMENTO", "QT_VOTOS_NOMINAIS"]:
    w[c] = w[c].fillna(0).astype(np.int64)
w["n"] = w.QT_VOTOS_NOMINAIS
r1 = w[w.NR_TURNO == 1].reset_index(drop=True)
r2 = w[w.NR_TURNO == 2].reset_index(drop=True)
res = {"year": year, "move": MOVE}


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------
# A. Section size
SIZE_EDGES = np.arange(0, 501, 25)


def size_scan(L, R, size, place):
    """Lula's share minus the rest of its polling place, by section size; the largest step."""
    n = L + R
    df = pd.DataFrame({"L": L, "n": n, "size": size, "place": place})
    g = df.groupby("place", sort=False)
    rest_n = g.n.transform("sum") - df.n
    ok = (rest_n > 0) & (df.n > 0)
    d = (df.L / df.n - (g.L.transform("sum") - df.L) / rest_n)[ok]
    s = df["size"][ok]
    b = np.clip(np.digitize(s, SIZE_EDGES) - 1, 0, len(SIZE_EDGES) - 1)
    by = pd.DataFrame({"d": d.values, "b": b}).groupby("b").d.agg(["mean", "std", "size"])
    curve = [{"from": int(SIZE_EDGES[i]), "mean_pp": float(r["mean"] * 100),
              "se_pp": float(r["std"] / np.sqrt(r["size"]) * 100), "sections": int(r["size"])}
             for i, r in by.iterrows()]
    # step at N: mean above minus mean below, for N with at least 2% of the sections on each side
    order = np.argsort(s.values)
    ds, ss = d.values[order], s.values[order]
    cs, cs2 = np.cumsum(ds), np.cumsum(ds ** 2)
    best = {"t": 0.0}
    tot, tot2, m = cs[-1], cs2[-1], len(ds)
    for N in range(50, 451, 5):
        k = int(np.searchsorted(ss, N, side="right"))
        if k < 0.02 * m or m - k < 0.02 * m:
            continue
        mb, ma = cs[k - 1] / k, (tot - cs[k - 1]) / (m - k)
        vb = cs2[k - 1] / k - mb ** 2
        va = (tot2 - cs2[k - 1]) / (m - k) - ma ** 2
        t = (ma - mb) / np.sqrt(vb / k + va / (m - k))
        if abs(t) > abs(best["t"]):
            best = {"t": float(t), "at": N, "step_pp": float((ma - mb) * 100)}
    return {"curve": curve, "max_step": best, "sections": int(m)}


log("A. section size")
size = r2.QT_COMPARECIMENTO.values
place = r2.groupby(PLACE, sort=False).ngroup().values
L, R = r2.v13.values, r2.v22.values
res["size"] = {"real": size_scan(L, R, size, place), "planted": []}
for N in (150, 250, 350):
    big = size > N
    q = MOVE / R[big].sum()  # share of the right candidate's votes to flip above N
    if q >= 1:
        continue
    k = rng.binomial(R * big, q)
    scan = size_scan(L + k, R - k, size, place)
    res["size"]["planted"].append({"above": N, "flip_share": float(q), "machines": int(big.sum()),
                                   **scan["max_step"], "curve": scan["curve"]})
    log(f"  planted above {N}: flip {q:.1%} ->", scan["max_step"])
log("  real:", res["size"]["real"]["max_step"])


# ---------------------------------------------------------------------------------
# B. Proportional swing, within the polling place
s = r1[SEC + ["v13", "v22", "n"]].merge(r2[SEC + PLACE[3:] + ["v13", "v22", "n"]], on=SEC, suffixes=("_1", "_2"))
s = s[(s.v13_1 + s.v22_1 > 0) & (s.v13_2 + s.v22_2 > 0)].reset_index(drop=True)
s["place"] = s.groupby(PLACE, sort=False).ngroup()


def prop_slope(L2, R2, rows=None):
    """Within-place slope of Lula's two-party swing on the right candidate's round-1 two-party share,
    with the round-1 share of the other candidates as a control (rows: a subset of s, e.g. one state)."""
    p1 = s.v13_1 / (s.v13_1 + s.v22_1)
    df = pd.DataFrame({"swing": L2 / (L2 + R2) - p1, "x": 1 - p1,
                       "o1": 1 - (s.v13_1 + s.v22_1) / s.n_1, "place": s.place})
    if rows is not None:
        df = df[rows]
    g = df.groupby("place")
    k = g.swing.transform("size")
    df = df[k > 1]
    g = df.groupby("place")
    X = np.column_stack([df.x - g.x.transform("mean"), df.o1 - g.o1.transform("mean")])
    y = (df.swing - g.swing.transform("mean")).values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    # standard errors clustered by polling place
    codes = pd.factorize(df.place)[0]
    U = np.zeros((codes.max() + 1, 2))
    np.add.at(U, codes, X * e[:, None])
    bread = np.linalg.inv(X.T @ X)
    V = bread @ (U.T @ U) @ bread
    return {"slope": float(beta[0]), "se": float(np.sqrt(V[0, 0])), "others_coef": float(beta[1]),
            "sections": int(len(df))}


log("B. proportional swing")
L2, R2 = s.v13_2.values, s.v22_2.values
res["prop_swing"] = {"real": prop_slope(L2, R2), "planted": [],
                     # the same slope state by state: how much it moves between elections without a program,
                     # which would add the same amount in every state
                     "by_state": {uf: prop_slope(L2, R2, (s.SG_UF == uf).values)["slope"] for uf in sorted(s.SG_UF.unique())}}
for who in ("right", "lula"):
    # a program flipping a fixed share of one candidate's runoff votes, in every machine, round 2 only
    src = R2 if who == "right" else L2
    q = MOVE / src.sum()
    k = rng.binomial(src, q)
    L2p, R2p = (L2 + k, R2 - k) if who == "right" else (L2 - k, R2 + k)
    res["prop_swing"]["planted"].append({"from": who, "flip_share": float(q), **prop_slope(L2p, R2p)})
    log(f"  planted, {q:.1%} of {who}'s runoff votes:", res["prop_swing"]["planted"][-1])
log("  real:", res["prop_swing"]["real"])


# ---------------------------------------------------------------------------------
# C. Homogeneity within the polling place (runoff): chi-squared of the place's sections
log("C. within-place chi-squared")
df = pd.DataFrame({"L": r2.v13, "R": r2.v22, "place": place})
df["n"] = df.L + df.R
df = df[df.n > 0]
g = df.groupby("place")
P = g.L.transform("sum") / g.n.transform("sum")
k = g.n.transform("size")
df = df[(k > 1) & (P > 0) & (P < 1)]
P = P[df.index]
eL, eR = df.n * P, df.n * (1 - P)
df["chi"] = (df.L - eL) ** 2 / eL + (df.R - eR) ** 2 / eR
pl = df.groupby("place").agg(chi=("chi", "sum"), k=("chi", "size"))
pl["df"] = pl.k - 1
pl["phi"] = pl.chi / pl.df
pl["p"] = stats.chi2.sf(pl.chi, pl.df)
res["homogeneity"] = {
    "places": int(len(pl)), "sections": int(pl.k.sum()),
    "phi_median": float(pl.phi.median()), "phi_mean": float(pl.phi.mean()),
    "share_p_below_001": float((pl.p < 0.001).mean()), "share_p_below_005": float((pl.p < 0.05).mean()),
    "p_hist": np.histogram(pl.p, np.linspace(0, 1, 21))[0].tolist(),
    "phi_quantiles": {str(q): float(pl.phi.quantile(q)) for q in (0.5, 0.9, 0.99, 0.999)},
}
log("  ", {k: v for k, v in res["homogeneity"].items() if k != "p_hist"})


# ---------------------------------------------------------------------------------
# D. Shpilkin: shares above the turnout peak, extrapolated from the share at the peak
T_EDGES = np.arange(0.5, 1.0001, 0.005)


def shpilkin(g):
    t = g.QT_COMPARECIMENTO / g.QT_APTOS
    b = pd.cut(t, T_EDGES, labels=False, include_lowest=True)
    a = g.assign(b=b).groupby("b")[["v13", "v22", "n", "QT_COMPARECIMENTO"]].sum()
    if a.empty:
        return None
    peak = a.QT_COMPARECIMENTO.idxmax()
    sl, sr = a.v13[peak] / a.n[peak], a.v22[peak] / a.n[peak]
    above = a[a.index > peak]
    return {"peak_turnout": float(T_EDGES[int(peak)]), "lula": float((above.v13 - sl * above.n).clip(lower=0).sum()),
            "right": float((above.v22 - sr * above.n).clip(lower=0).sum())}


log("D. Shpilkin")
res["shpilkin"] = {}
for t, g in w.groupby("NR_TURNO"):
    nat = shpilkin(g)
    per_uf = [shpilkin(gu) for _, gu in g.groupby("SG_UF")]
    res["shpilkin"][int(t)] = {"national": nat, "by_state": {"lula": float(sum(p["lula"] for p in per_uf if p)),
                                                             "right": float(sum(p["right"] for p in per_uf if p))},
                               "valid_votes": int(g.n.sum())}
    log(f"  round {t}:", res["shpilkin"][int(t)])


# ---------------------------------------------------------------------------------
# E. Second-digit Benford
B2 = np.array([sum(np.log10(1 + 1 / (10 * k + d)) for k in range(1, 10)) for d in range(10)])


def second_digit(x):
    x = np.asarray(x, np.int64)
    x = x[x >= 10]
    d2 = (x // 10 ** (np.floor(np.log10(x)).astype(int) - 1)) % 10
    obs = np.bincount(d2, minlength=10)
    chi, p = stats.chisquare(obs, B2 * obs.sum())
    return {"n": int(obs.sum()), "freq": (obs / obs.sum()).round(5).tolist(), "mean": float(d2.mean()),
            "expected_mean": float((np.arange(10) * B2).sum()), "chi2": float(chi), "p": float(p)}


log("E. second-digit Benford")
res["benford2"] = {int(t): {"lula": second_digit(g.v13), "right": second_digit(g.v22)} for t, g in w.groupby("NR_TURNO")}
res["benford2_expected"] = B2.round(5).tolist()
for t, d in res["benford2"].items():
    log(f"  round {t}:", {k: (round(v["mean"], 3), f"p={v['p']:.2g}") for k, v in d.items()})

(out / f"more_tests_{year}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
log("done ->", out / f"more_tests_{year}.json")
