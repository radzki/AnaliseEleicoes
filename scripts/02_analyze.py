"""Forensic tests on section-level presidential results for one election year.

Usage: python -I scripts/02_analyze.py <processed_dir> <out_dir> <year>

Writes <out_dir>/results_<year>.json (summary numbers + chart data) and
<out_dir>/states_<year>.csv (per-state table).

Tests
  1. Last digit of vote counts (Beber & Scacco 2012), vs uniform and vs a binomial-resampling null.
  2. Integer-percentage spikes in turnout / vote share (Kobak, Shpilkin & Pshenichnikov 2016).
  3. Distribution shape: each section vs. the other sections of its own polling place
     (two-proportion z), its tails and symmetry; turnout x share fingerprint (Klimek et al. 2012).
  4. Round 1 -> round 2 swing per section, within polling place.
  5. Timing of tally arrival and voting-machine model, both within zone / polling place.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

proc, out, year = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8")
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(year)

SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
PLACE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO"]
ZONE = ["SG_UF", "NR_ZONA"]
THIRD = {
    2026: {"v70": "Cury", "v14": "Renan Santos", "v55": "Caiado", "v30": "Zema"},
    2022: {"v15": "Tebet", "v12": "Ciro", "v44": "Soraya", "v30": "D'Avila"},
}[year]
RIGHT = {2026: "Flávio Bolsonaro", 2022: "Jair Bolsonaro"}[year]
res = {"year": year, "right_name": RIGHT, "third": THIRD}


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------
w = pd.read_parquet(proc / "secao_wide.parquet")
w = w[w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)].copy()
vcols = [c for c in w.columns if c.startswith("v") and c[1:].isdigit()]
w[vcols] = w[vcols].fillna(0).astype(np.int64)
for c in ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS",
          "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS"]:
    w[c] = w[c].astype(np.int64)
w["n"] = w.QT_VOTOS_NOMINAIS
w["sL"] = w.v13 / w.n
w["sR"] = w.v22 / w.n
w["turnout"] = w.QT_COMPARECIMENTO / w.QT_APTOS
w["arrival"] = pd.to_datetime(w.DT_RECEBIMENTO_BU_HOR_TSE, format="%d/%m/%Y %H:%M:%S", errors="coerce")
log("sections used per round:", w.groupby("NR_TURNO").size().to_dict())
res["sections"] = {int(k): int(v) for k, v in w.groupby("NR_TURNO").size().items()}
res["totals"] = {
    int(t): {k: int(g[c].sum()) for k, c in [("aptos", "QT_APTOS"), ("comparecimento", "QT_COMPARECIMENTO"),
             ("valid", "n"), ("lula", "v13"), ("right", "v22"), ("brancos", "QT_VOTOS_BRANCOS"),
             ("nulos", "QT_VOTOS_NULOS")]}
    for t, g in w.groupby("NR_TURNO")
}


# ---------------------------------------------------------------------------------
# 1. Round numbers in the counts themselves
# 1a. Last digit (valid only where counts span many tens: Lula, right candidate, turnout, aggregates).
def last_digit(x, min_count=10):
    x = np.asarray(x, np.int64)
    obs = np.bincount(x[x >= min_count] % 10, minlength=10)
    tot = obs.sum()
    _, p_u = stats.chisquare(obs)
    f = obs / tot
    return {"n": int(tot), "freq": f.round(5).tolist(), "p_uniform": float(p_u),
            "pct_ending_0": float(f[0] * 100), "pct_ending_0_or_5": float((f[0] + f[5]) * 100),
            "max_dev_pp": float(np.abs(f - 0.1).max() * 100)}


# 1b. Heaping: is a round value (10, 20, ...) more frequent than its neighbours (v-1, v+1)?
# Compared with the same index at non-round values next to them (10k+-2, 10k+-3), so the
# curvature of the distribution cancels out. Valid for small counts (blank, null, minor candidates).
def heaping(x):
    f = np.bincount(np.asarray(x, np.int64)).astype(float)
    top = int(np.searchsorted(np.cumsum(f) / f.sum(), 0.995))

    def oe(vs):
        vs = vs[(vs >= 1) & (vs + 1 < len(f)) & (vs <= top)]
        return f[vs].sum(), ((f[vs - 1] + f[vs + 1]) / 2).sum(), len(vs)

    r10 = np.arange(10, top + 1, 10)
    r5 = np.arange(5, top + 1, 10)
    O, E, k = oe(r10)
    O5, E5, _ = oe(r5)
    Oc, Ec, _ = oe(np.concatenate([r10 - 3, r10 - 2, r10 + 2, r10 + 3]))
    hc = Oc / Ec
    z = (O - E * hc) / np.sqrt(O + E / 2 * hc ** 2) if k else np.nan
    return {"round_values": int(k), "heap_10": O / E if E else None, "heap_5": O5 / E5 if E5 else None,
            "heap_control": hc, "ratio_10_vs_control": (O / E) / hc if E else None, "z": float(z),
            "pmf": (f[: min(len(f), 61)] / f.sum()).round(6).tolist()}


def count_vars(g, t):
    v = {"Lula": g.v13, RIGHT: g.v22, "Comparecimento": g.QT_COMPARECIMENTO,
         "Brancos": g.QT_VOTOS_BRANCOS, "Nulos": g.QT_VOTOS_NULOS}
    if t == 1:
        v.update({name: g[c] for c, name in THIRD.items() if c in g})
    return v


log("1. last digit and heaping")
res["last_digit"], res["heaping"] = {}, {}
state_digit = []
for t, g in w.groupby("NR_TURNO"):
    t = int(t)
    res["last_digit"][t] = {k: last_digit(g[c]) for k, c in [("Lula", "v13"), (RIGHT, "v22"),
                                                             ("Comparecimento", "QT_COMPARECIMENTO")]}
    for lvl, keys in [("zona", ["SG_UF", "CD_MUNICIPIO", "NR_ZONA"]), ("municipio", ["SG_UF", "CD_MUNICIPIO"])]:
        a = g.groupby(keys)[["v13", "v22", "QT_COMPARECIMENTO"]].sum()
        res["last_digit"][t][f"Lula por {lvl}"] = last_digit(a.v13)
        res["last_digit"][t][f"{RIGHT} por {lvl}"] = last_digit(a.v22)
    res["heaping"][t] = {k: heaping(x) for k, x in count_vars(g, t).items()}
    for uf, gu in g.groupby("SG_UF"):
        for k, c in [("Lula", "v13"), (RIGHT, "v22"), ("Comparecimento", "QT_COMPARECIMENTO")]:
            r = last_digit(gu[c])
            state_digit.append({"turno": t, "uf": uf, "var": k, **{q: r[q] for q in
                                ("n", "p_uniform", "pct_ending_0", "max_dev_pp")}})
state_digit = pd.DataFrame(state_digit)
n_tests = len(state_digit)
state_digit["bonferroni_flag"] = state_digit.p_uniform < 0.05 / n_tests
res["last_digit_states"] = {
    "n_tests": n_tests, "flagged": state_digit[state_digit.bonferroni_flag].to_dict("records"),
    "min_p": float(state_digit.p_uniform.min()),
    "share_p_below_005": float((state_digit.p_uniform < 0.05).mean()),
    "p_values": state_digit.p_uniform.round(5).tolist(),
}
state_digit.to_csv(out / f"last_digit_states_{year}.csv", index=False)


# ---------------------------------------------------------------------------------
# 2. Integer percentages
def int_pct(x, N, sims=200):
    x, N = np.asarray(x, np.int64), np.asarray(N, np.int64)
    p = x / N

    def hits(xx):
        inner = (xx > 0) & (xx < N)
        return np.array([(((100 * xx) % N == 0) & inner).sum(), (((20 * xx) % N == 0) & inner).sum(),
                         ((2 * xx == N)).sum()])

    obs = hits(x)
    sim = np.array([hits(rng.binomial(N, p)) for _ in range(sims)])
    mu, sd = sim.mean(0), sim.std(0)
    names = ["integer_pct", "multiple_of_5pct", "exactly_50pct"]
    return {nm: {"observed": int(obs[i]), "expected": float(mu[i]), "sd": float(sd[i]),
                 "z": float((obs[i] - mu[i]) / sd[i]) if sd[i] > 0 else None,
                 "ratio": float(obs[i] / mu[i]) if mu[i] > 0 else None} for i, nm in enumerate(names)}


def fine_hist(x, N, sims=20):
    """Histogram of 100*x/N in 0.1-point bins: observed and binomial-null mean (for the chart)."""
    edges = np.arange(0, 100.0001, 0.1)
    obs = np.histogram(100 * x / N, edges)[0]
    simh = np.mean([np.histogram(100 * rng.binomial(N, x / N) / N, edges)[0] for _ in range(sims)], 0)
    return {"obs": obs.tolist(), "null": simh.round(1).tolist()}


log("2. integer percentages")
res["int_pct"], res["fine_hist"] = {}, {}
for t, g in w.groupby("NR_TURNO"):
    res["int_pct"][int(t)] = {
        "turnout": int_pct(g.QT_COMPARECIMENTO, g.QT_APTOS),
        "Lula": int_pct(g.v13, g.n),
        RIGHT: int_pct(g.v22, g.n),
    }
    res["fine_hist"][int(t)] = {"turnout": fine_hist(g.QT_COMPARECIMENTO.values, g.QT_APTOS.values),
                                "Lula": fine_hist(g.v13.values, g.n.values)}


# ---------------------------------------------------------------------------------
# 3. Distribution shape: section vs rest of its polling place
def loo_z(df, group, num, den):
    g = df.groupby(group, sort=False)
    rest_num = g[num].transform("sum") - df[num]
    rest_den = g[den].transform("sum") - df[den]
    ok = rest_den > 0
    p_rest = np.where(ok, rest_num / rest_den.where(ok, 1), np.nan)
    p_i = df[num] / df[den]
    pool = (df[num] + rest_num) / (df[den] + rest_den)
    se = np.sqrt(pool * (1 - pool) * (1 / df[den] + 1 / rest_den.where(ok, np.nan)))
    z = (p_i - p_rest) / se
    return z.replace([np.inf, -np.inf], np.nan), p_i - p_rest


Z_EDGES = np.arange(-10, 10.0001, 0.25)


def tail_summary(z):
    z = np.asarray(z, float)
    z = z[np.isfinite(z)]
    med = np.median(z)
    rsd = 1.4826 * np.median(np.abs(z - med))
    r = {"n": int(len(z)), "sd": float(z.std()), "robust_sd": float(rsd), "median": float(med),
         "skew": float(stats.skew(z)), "excess_kurtosis": float(stats.kurtosis(z)),
         "hist": np.histogram(np.clip(z, -9.99, 9.99), Z_EDGES)[0].tolist()}
    for k in (3, 4, 5, 6):
        r[f"pos_{k}"] = int((z > k).sum())
        r[f"neg_{k}"] = int((z < -k).sum())
        r[f"normal_expected_{k}"] = float(len(z) * stats.norm.sf(k / rsd))  # per side, normal w/ robust sd
    return r


log("3. within-polling-place distribution")
parts = []
for t, g in w.groupby("NR_TURNO"):
    g = g.copy()
    g["zL"], g["dL"] = loo_z(g, PLACE, "v13", "n")
    g["zT"], g["dT"] = loo_z(g, PLACE, "QT_COMPARECIMENTO", "QT_APTOS")
    parts.append(g)
w = pd.concat(parts)
res["place_z"] = {}
for t, g in w.groupby("NR_TURNO"):
    d = {"Lula share": tail_summary(g.zL), "Turnout": tail_summary(g.zT)}
    hi = g[g.zT > 4]
    d["lula_z_among_high_turnout_outliers"] = {"n": int(len(hi)), "mean_zL": float(hi.zL.mean()),
                                               "share_zL_pos": float((hi.zL > 0).mean())}
    d["corr_zL_zT"] = float(g[["zL", "zT"]].corr().iloc[0, 1])
    res["place_z"][int(t)] = d

# are the 2nd-round outliers the same sections that stood out in the 1st round?
zz = w.pivot_table(index=SEC, columns="NR_TURNO", values="zL")
zz = zz.dropna()
res["place_z_persistence"] = {
    "corr_round1_round2": float(zz[1].corr(zz[2])),
    "pos4_r2": int((zz[2] > 4).sum()), "pos4_r2_with_r1_above_2": int(((zz[2] > 4) & (zz[1] > 2)).sum()),
    "neg4_r2": int((zz[2] < -4).sum()), "neg4_r2_with_r1_below_m2": int(((zz[2] < -4) & (zz[1] < -2)).sum()),
}

# distribution of shares/turnout by state (raw), plus fingerprint
res["shape"], res["fingerprint"] = {}, {}
edges01 = np.linspace(0, 1, 101)
state_rows = []
for t, g in w.groupby("NR_TURNO"):
    res["shape"][int(t)] = {}
    for uf, gu in g.groupby("SG_UF"):
        lg = np.log(gu.sL.clip(1e-3, 1 - 1e-3) / (1 - gu.sL.clip(1e-3, 1 - 1e-3)))
        res["shape"][int(t)][uf] = {
            "hist_sL": np.histogram(gu.sL, edges01)[0].tolist(),
            "hist_turnout": np.histogram(gu.turnout.clip(0, 1), edges01)[0].tolist(),
            "mean_sL": float(gu.v13.sum() / gu.n.sum()), "sd_sL": float(gu.sL.std()),
            "skew_sL": float(stats.skew(gu.sL)), "skew_logit_sL": float(stats.skew(lg)),
            "kurt_logit_sL": float(stats.kurtosis(lg)),
            "corr_turnout_sL": float(np.corrcoef(gu.turnout, gu.sL)[0, 1]),
        }
    res["shape"][int(t)]["BR"] = {"hist_sL": np.histogram(g.sL, edges01)[0].tolist(),
                                  "hist_turnout": np.histogram(g.turnout.clip(0, 1), edges01)[0].tolist()}
    big = g[g.QT_APTOS >= 100]
    res["fingerprint"][int(t)] = {
        "lula": np.histogram2d(g.turnout.clip(0, 1), g.sL, [edges01, edges01])[0].astype(int).tolist(),
        "right": np.histogram2d(g.turnout.clip(0, 1), g.sR, [edges01, edges01])[0].astype(int).tolist(),
        "corner_lula": int(((big.turnout >= 0.95) & (big.sL >= 0.9)).sum()),
        "corner_right": int(((big.turnout >= 0.95) & (big.sR >= 0.9)).sum()),
        "corr_turnout_sL_within_place": float(np.corrcoef(g.dT.fillna(0), g.dL.fillna(0))[0, 1]),
    }


w1 = w[w.NR_TURNO == 1].set_index(SEC)[["turnout", "sL"]].add_suffix("_r1")
cor = w[(w.NR_TURNO == 2) & (w.QT_APTOS >= 100) & (w.turnout >= 0.95) & (w.sL >= 0.9)].join(w1, on=SEC)
res["corner_sections_r2"] = {
    "n": int(len(cor)), "votes": int(cor.QT_COMPARECIMENTO.sum()),
    "r1_turnout_median": float(cor.turnout_r1.median()), "r1_lula_median": float(cor.sL_r1.median()),
    "r1_turnout_ge_90": float((cor.turnout_r1 >= 0.9).mean()),
    "rows": cor.sort_values("turnout", ascending=False)[SEC + ["NM_MUNICIPIO", "NM_LOCAL_VOTACAO", "QT_APTOS",
                                                                "turnout_r1", "turnout", "sL_r1", "sL"]]
    .round(4).to_dict("records"),
}


# ---------------------------------------------------------------------------------
# 4. Round 1 -> round 2
log("4. swing")
r1 = w[w.NR_TURNO == 1].set_index(SEC)
r2 = w[w.NR_TURNO == 2].set_index(SEC)
s = r1.join(r2, how="inner", suffixes=("_1", "_2"))
s = s.reset_index()
s["p1"] = s.v13_1 / (s.v13_1 + s.v22_1)
s["p2"] = s.v13_2 / (s.v13_2 + s.v22_2)
s["swing"] = s.p2 - s.p1
s["dturn"] = s.turnout_2 - s.turnout_1
place1 = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO_2"]
gp = s.groupby(place1, sort=False)
for col in ("swing", "dturn"):
    k = gp[col].transform("size")
    s[f"{col}_res"] = np.where(k > 1, s[col] - (gp[col].transform("sum") - s[col]) / (k - 1).where(k > 1, 1), np.nan)
rs = s.swing_res.dropna()
rsd = 1.4826 * np.median(np.abs(rs - rs.median()))
res["swing"] = {
    "national_p1": float(s.v13_1.sum() / (s.v13_1.sum() + s.v22_1.sum())),
    "national_p2": float(s.v13_2.sum() / (s.v13_2.sum() + s.v22_2.sum())),
    "turnout_1": float(s.QT_COMPARECIMENTO_1.sum() / s.QT_APTOS_1.sum()),
    "turnout_2": float(s.QT_COMPARECIMENTO_2.sum() / s.QT_APTOS_2.sum()),
    "sections_matched": int(len(s)),
    "aptos_changed_sections": int((s.QT_APTOS_1 != s.QT_APTOS_2).sum()),
    "residual_pp": tail_summary(rs / rsd),
    "residual_robust_sd_pp": float(rsd * 100),
    "hist_swing": np.histogram(s.swing.clip(-0.3, 0.3), np.linspace(-0.3, 0.3, 121))[0].tolist(),
    "corr_dturn_swing_within_place": float(s[["dturn_res", "swing_res"]].dropna().corr().iloc[0, 1]),
}
st = s.groupby("SG_UF").agg(v13_1=("v13_1", "sum"), v22_1=("v22_1", "sum"), v13_2=("v13_2", "sum"),
                            v22_2=("v22_2", "sum"), c1=("QT_COMPARECIMENTO_1", "sum"),
                            c2=("QT_COMPARECIMENTO_2", "sum"), ap=("QT_APTOS_1", "sum"))
st["p1"] = st.v13_1 / (st.v13_1 + st.v22_1)
st["p2"] = st.v13_2 / (st.v13_2 + st.v22_2)
st["swing_pp"] = (st.p2 - st.p1) * 100
st["turnout_change_pp"] = (st.c2 - st.c1) / st.ap * 100
st["lula_gain"] = st.v13_2 - st.v13_1
st["right_gain"] = st.v22_2 - st.v22_1


# ---------------------------------------------------------------------------------
# 5a. Timing of tally arrival
log("5. timing and machine model")
res["timing"] = {}
for t, g in w.groupby("NR_TURNO"):
    g = g[g.arrival.notna()].sort_values("arrival")
    t0 = g.arrival.dt.normalize().iloc[0] + pd.Timedelta(hours=17)
    mins = ((g.arrival - t0).dt.total_seconds() // 600).clip(lower=0, upper=6 * 7)  # 10-min bins, cap 7h
    b = g.groupby(mins).agg(l=("v13", "sum"), r=("v22", "sum"), n=("n", "sum"), k=("n", "size"))
    cum = b.cumsum()
    # within zone: section share minus rest-of-zone share, by arrival bin
    gz = g.groupby(ZONE)
    zrest = (gz.v13.transform("sum") - g.v13) / (gz.n.transform("sum") - g.n)
    g = g.assign(zres=g.sL - zrest, bin=mins)
    hrs = (g.arrival - t0).dt.total_seconds() / 3600
    hz = hrs - hrs.groupby([g[c] for c in ZONE]).transform("mean")
    ok = g.zres.notna() & np.isfinite(g.zres)
    slope = np.polyfit(hz[ok], g.zres[ok], 1)[0]
    res["timing"][int(t)] = {
        "bin_minutes": 10, "start": str(t0),
        "cum_lula_2p": (cum.l / (cum.l + cum.r)).round(5).tolist(),
        "cum_pct_counted": (cum.n / b.n.sum()).round(5).tolist(),
        "bin_lula_2p": (b.l / (b.l + b.r)).round(5).tolist(),
        "within_zone_resid_by_bin": (g[ok].groupby("bin").zres.mean() * 100).round(3).tolist(),
        "within_zone_slope_pp_per_hour": float(slope * 100),
    }

# 5b. machine model, within polling place
res["urna_model"] = {}
for t, g in w.groupby("NR_TURNO"):
    gg = g[g.zL.notna()]
    m = gg.groupby("DS_MODELO_URNA").apply(
        lambda x: pd.Series({"sections": len(x), "mean_z": x.zL.mean(),
                             "share_pp_vs_place": (x.dL * x.n).sum() / x.n.sum() * 100,
                             "raw_lula_share": x.v13.sum() / x.n.sum() * 100}), include_groups=False)
    res["urna_model"][int(t)] = m.round(4).reset_index().to_dict("records")


# ---------------------------------------------------------------------------------
# per-state table
tab = []
for t, g in w.groupby("NR_TURNO"):
    for uf, gu in g.groupby("SG_UF"):
        zl = gu.zL.dropna()
        tab.append({"turno": int(t), "uf": uf, "secoes": len(gu), "aptos": int(gu.QT_APTOS.sum()),
                    "turnout_pct": gu.QT_COMPARECIMENTO.sum() / gu.QT_APTOS.sum() * 100,
                    "lula_pct": gu.v13.sum() / gu.n.sum() * 100, "right_pct": gu.v22.sum() / gu.n.sum() * 100,
                    "placeZ_sd": zl.std(), "placeZ_pos4": int((zl > 4).sum()), "placeZ_neg4": int((zl < -4).sum())})
tab = pd.DataFrame(tab)
tab = tab.merge(st[["swing_pp", "turnout_change_pp", "lula_gain", "right_gain"]].reset_index()
                .rename(columns={"SG_UF": "uf"}).assign(turno=2), on=["turno", "uf"], how="left")
tab.to_csv(out / f"states_{year}.csv", index=False)
res["states"] = tab.round(4).to_dict("records")


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


(out / f"results_{year}.json").write_text(json.dumps(clean(res), ensure_ascii=False), encoding="utf-8")
log("done ->", out / f"results_{year}.json")
