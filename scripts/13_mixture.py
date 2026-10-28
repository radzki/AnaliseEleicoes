"""Fraud mixture model of the runoff's turnout x winner's share, in the style of Klimek et al. (2012).

Usage: python -I scripts/13_mixture.py <processed_dir> <out_dir> <year>

Each section's turnout and its local winner's share (the candidate who won its state) come from a
clean distribution, a correlated normal in logit scale fitted per state with medians and median
absolute deviations, so that fraud cannot pull the fit. A fraction f_i of the sections then gets
"incremental" fraud: a share x ~ |N(0, 0.1)| of the non-voters is turned into votes for the winner,
and the same share of the opponent's votes is moved to the winner. A fraction f_e gets "extreme"
fraud, the same with x ~ 1 - |N(0, 0.05)|, which drives a section to near-total turnout and share.
f_i and f_e are the values whose simulated turnout x share histogram (2-point cells, all states
together) best matches the real one. A clean distribution that does not fit the real shape shows
up as fraud too, which is why the other year is fitted the same way and why the model is also run
on that year with fraud planted in it.

Writes <out_dir>/mixture_<year>.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit

proc, out, year = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8")
SIMS, BINS = 10, 50
F_I = np.round(np.arange(0, 0.1501, 0.01), 4)
F_E = np.round(np.arange(0, 0.00401, 0.00025), 5)

w = pd.read_parquet(proc / "secao_wide.parquet", columns=["NR_TURNO", "SG_UF", "QT_APTOS", "QT_COMPARECIMENTO",
                                                          "QT_VOTOS_NOMINAIS", "v13", "v22"])
w = w[(w.NR_TURNO == 2) & w.v13.notna() & (w.SG_UF != "ZZ") & (w.QT_APTOS >= 50)].copy()
w[["v13", "v22"]] = w[["v13", "v22"]].fillna(0)
w = w[w.v13 + w.v22 > 0]
lula_wins = w.groupby("SG_UF").v13.transform("sum") > w.groupby("SG_UF").v22.transform("sum")
w["W"] = np.where(lula_wins, w.v13, w.v22)
w["O"] = np.where(lula_wins, w.v22, w.v13)
w["N"] = w.QT_APTOS.astype(float)
w["T"] = w.QT_COMPARECIMENTO.astype(float)


def cells(t, v):
    i = np.clip((t * BINS).astype(int), 0, BINS - 1)
    j = np.clip((v * BINS).astype(int), 0, BINS - 1)
    return np.bincount(i * BINS + j, minlength=BINS * BINS)


def fit(d, seed):
    """Best (f_i, f_e) for one data set, and the votes the fitted fraud adds."""
    rng = np.random.default_rng(seed)
    N, T, W, O = (d[c].values for c in ("N", "T", "W", "O"))
    obs = cells(T / N, W / (W + O))
    # clean distribution per state, robust to the tails
    lt = logit(np.clip(T / N, 0.5 / N, 1 - 0.5 / N))
    lv = logit(np.clip(W / (W + O), 0.5 / (W + O), 1 - 0.5 / (W + O)))
    par = pd.DataFrame({"uf": d.SG_UF.values, "turn": lt, "share": lv})
    mu = par.groupby("uf")[["turn", "share"]].transform("median")
    sd = 1.4826 * (par[["turn", "share"]] - mu).abs().groupby(par.uf).transform("median")
    zt, zv = (par.turn - mu.turn) / sd.turn, (par.share - mu.share) / sd.share
    core = (zt.abs() < 2) & (zv.abs() < 2)
    rho = pd.DataFrame({"zt": zt[core], "zv": zv[core], "uf": par.uf[core]}).groupby("uf").apply(
        lambda g: np.corrcoef(g.zt, g.zv)[0, 1], include_groups=False)
    r = par.uf.map(rho).values
    loss = np.zeros((len(F_I), len(F_E)))
    added = np.zeros((len(F_I), len(F_E), 2))
    for _ in range(SIMS):
        z1, z2 = rng.standard_normal(len(N)), rng.standard_normal(len(N))
        tf = expit(mu.turn.values + sd.turn.values * z1)
        vf = expit(mu.share.values + sd.share.values * (r * z1 + np.sqrt(1 - r ** 2) * z2))
        Tf, Wf = tf * N, vf * tf * N
        Of = Tf - Wf
        u = rng.random(len(N))
        xi = np.clip(np.abs(rng.normal(0, 0.1, len(N))), 0, 1)
        xe = np.clip(1 - np.abs(rng.normal(0, 0.05, len(N))), 0, 1)
        for a, fi in enumerate(F_I):
            for b, fe in enumerate(F_E):
                x = np.where(u < fi, xi, np.where(u < fi + fe, xe, 0.0))
                Ts = Tf + x * (N - Tf)
                Ws = Wf + x * (N - Tf) + x * Of
                sim = cells(Ts / N, Ws / Ts)
                loss[a, b] += ((obs - sim) ** 2 / (obs + sim + 1)).sum()
                inc, ext = u < fi, (u >= fi) & (u < fi + fe)
                added[a, b] += [((x * (N - Tf) + x * Of) * inc).sum(), ((x * (N - Tf) + x * Of) * ext).sum()]
    a, b = np.unravel_index(loss.argmin(), loss.shape)
    return {"f_i": float(F_I[a]), "f_e": float(F_E[b]), "sections": int(len(N)),
            "sections_incremental": float(F_I[a] * len(N)), "sections_extreme": float(F_E[b] * len(N)),
            "votes_incremental": float(added[a, b, 0] / SIMS), "votes_extreme": float(added[a, b, 1] / SIMS),
            "loss": float(loss[a, b] / SIMS), "loss_no_fraud": float(loss[0, 0] / SIMS),
            "f_e_profile": (loss[a] / SIMS).round(1).tolist()}


res = {"year": year, "grid": {"f_i": F_I.tolist(), "f_e": F_E.tolist()}, "sims": SIMS}
res["real"] = fit(w, year)
print("real:", {k: v for k, v in res["real"].items() if k != "f_e_profile"}, flush=True)
# the same data with extreme fraud planted in sections chosen at random: does the model find it, and
# from what size? 92 is the number of near-unanimous runoff sections in 2026 (question 4). The model
# estimates in steps of F_E, about 125 sections, so what it finds is approximate.
res["planted"] = []
for i, count in enumerate((92, 250, 1000)):
    rng = np.random.default_rng(year + 1 + i)
    p = w.copy()
    pick = np.zeros(len(p), bool)
    pick[rng.choice(len(p), count, replace=False)] = True
    x = np.clip(1 - np.abs(rng.normal(0, 0.05, pick.sum())), 0, 1)
    nonv = p.N[pick] - p["T"][pick]
    p.loc[pick, "W"] = p.W[pick] + x * nonv + x * p.O[pick]
    p.loc[pick, "O"] = p.O[pick] * (1 - x)
    p.loc[pick, "T"] = p["T"][pick] + x * nonv
    res["planted"].append({**fit(p, year + 10 + i), "planted_sections": count})
    print(f"planted {count} extreme:", {k: v for k, v in res["planted"][-1].items() if k != "f_e_profile"}, flush=True)
(out / f"mixture_{year}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
