"""Voters released by the poll worker instead of by their fingerprint, in every runoff section of 2026.

Usage: python -I scripts/16_biometria.py <bweb_dir> <processed_2026> <results_dir>

The TSE's tally-report files (boletim de urna, bweb_2t_<UF>_*.zip; see README) carry, per section,
QT_ELEI_BIOM_SEM_HABILITACAO: voters with fingerprints on file who were not released by them, that is,
released manually by the poll worker. The machine logs of the sample (scripts/07_urna_logs.py) check
that reading machine by machine, and give what the tally reports do not: voters with no fingerprints on
file at all.

Ballots are secret, so how these voters voted can only be estimated across sections. Within a polling
place, a section's Lula share is regressed on its share of manual releases (Goodman's ecological
regression): the slope is how much more the released voters lean to Lula than the others, if the other
voters of a section do not lean differently because of it. That condition is doubtful: fingerprints
fail more often with age, so sections with many releases have older voters overall, and the slope also
measures how age relates to the vote in each place. It differs by region (none in the South), so it is
reported by region and as a rough indication, not a share of these voters' votes.

Writes <results_dir>/biometria.json.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

src, proc, out = (Path(a) for a in sys.argv[1:4])
sys.stdout.reconfigure(encoding="utf-8")
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
rng = np.random.default_rng(2026)


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------
# One row per section: turnout, manual releases, Lula and Flávio
cols = SEC + ["NR_LOCAL_VOTACAO", "CD_CARGO_PERGUNTA", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ELEI_BIOM_SEM_HABILITACAO",
              "NR_VOTAVEL", "QT_VOTOS"]
parts = []
for z in sorted(src.glob("bweb_2t_*.zip")):
    with zipfile.ZipFile(z) as f:
        name = next(n for n in f.namelist() if n.endswith(".csv"))
        d = pd.read_csv(io.BytesIO(f.read(name)), sep=";", encoding="latin1", usecols=cols)
    d = d[d.CD_CARGO_PERGUNTA == 1]
    base = d.groupby(SEC).agg(local=("NR_LOCAL_VOTACAO", "first"), aptos=("QT_APTOS", "first"),
                              comp=("QT_COMPARECIMENTO", "first"), manual=("QT_ELEI_BIOM_SEM_HABILITACAO", "first"))
    v = d[d.NR_VOTAVEL.isin([13, 22])].pivot_table(index=SEC, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum")
    v.columns = [f"v{c}" for c in v.columns]
    parts.append(base.join(v, how="left").fillna({"v13": 0, "v22": 0}).reset_index())
s = pd.concat(parts, ignore_index=True)
# 26 states, DF and abroad (the portal's list leaves out Roraima's runoff file, which is on the CDN: see README)
assert len(parts) == 28, f"expected 28 files (26 states, DF and abroad), found {len(parts)}"

# against the official section results the site uses: what the tally-report files leave out
w = pd.read_parquet(proc / "secao_wide.parquet", columns=["NR_TURNO", *SEC, "QT_COMPARECIMENTO", "v13", "v22"])
w = w[w.NR_TURNO == 2]
res = {"files": len(parts), "sections": int(len(s)), "turnout": int(s.comp.sum()), "manual": int(s.manual.sum()),
       "manual_share": float(s.manual.sum() / s.comp.sum()),
       "official_sections": int(len(w)), "official_turnout": int(w.QT_COMPARECIMENTO.sum()),
       "missing_sections": int(len(w) - len(s)),
       "missing_turnout_share": float(1 - s.comp.sum() / w.QT_COMPARECIMENTO.sum())}
m = s.merge(w, on=SEC, suffixes=("", "_off"))
res["matched_equal"] = float(((m.comp == m.QT_COMPARECIMENTO) & (m.v13 == m.v13_off) & (m.v22 == m.v22_off.fillna(0))).mean())
log("sections", res["sections"], "of", res["official_sections"], "; manual", res["manual"], f"{res['manual_share']:.2%}",
    "; same numbers as the official results in", f"{res['matched_equal']:.2%}")

# by state
st = s.groupby("SG_UF").agg(comp=("comp", "sum"), manual=("manual", "sum"))
st["share"] = st.manual / st.comp
res["by_state"] = {uf: float(r.share) for uf, r in st.iterrows()}

# ---------------------------------------------------------------------------------
# Groups: are manual releases concentrated where one candidate took almost everything?
s = s[(s.comp > 0) & (s.v13 + s.v22 > 0)].copy()
s["two"] = s.v13 + s.v22
s["lula"] = s.v13 / s.two
s["t"] = s.comp / s.aptos
s["sh"] = s.manual / s.comp
PLACE = SEC[:3] + ["local"]
g = s.groupby(PLACE)
rest = g.comp.transform("sum") - s.comp
s["place_sh"] = ((g.manual.transform("sum") - s.manual) / rest.where(rest > 0)).where(rest > 0)
big = s.aptos >= 100
groups = {"corner_lula": big & (s.t >= 0.95) & (s.lula >= 0.9), "corner_right": big & (s.t >= 0.95) & (s.lula <= 0.1),
          "lula90": big & (s.lula >= 0.9), "right90": big & (s.lula <= 0.1), "all": s.comp > 0}
res["groups"] = {}
for k, sel in groups.items():
    d = s[sel]
    dp = d.dropna(subset=["place_sh"])
    res["groups"][k] = {"sections": int(len(d)), "share": float(d.manual.sum() / d.comp.sum()),
                        "place_share": float(np.average(dp.place_sh, weights=dp.comp)) if dp.comp.sum() else None}
    log(k, res["groups"][k])


# ---------------------------------------------------------------------------------
# How the released voters leaned: Lula share on manual share, within each group of sections
def lean(by, sel=None):
    """sel: the sections to use (default all)."""
    t0 = s if sel is None else s[sel]
    if by is None:
        d, x, y = t0, t0.sh - np.average(t0.sh, weights=t0.two), t0.lula - np.average(t0.lula, weights=t0.two)
        codes = np.arange(len(t0))
    else:
        k = t0.groupby(by).lula.transform("size")
        d = t0[k > 1]
        gg = d.groupby(by)
        wsum = gg.two.transform("sum")
        x = d.sh - (d.sh * d.two).groupby([d[c] for c in by]).transform("sum") / wsum
        y = d.lula - (d.lula * d.two).groupby([d[c] for c in by]).transform("sum") / wsum
        codes = gg.ngroup().values
    wt = d.two.values
    beta = float(np.sum(wt * x * y) / np.sum(wt * x * x))
    e = y - beta * x
    u = np.bincount(codes, weights=wt * x * e)  # clustered by group
    se = float(np.sqrt(np.sum(u ** 2)) / np.sum(wt * x * x))
    p_all = float(d.v13.sum() / d.two.sum())
    sbar = float(np.average(d.sh, weights=d.two))
    return {"beta": beta, "se": se, "diff_pp": 100 * beta, "sections": int(len(d)), "lula_all": p_all,
            "lula_manual": p_all + beta * (1 - sbar), "lula_manual_lo": p_all + (beta - 1.96 * se) * (1 - sbar),
            "lula_manual_hi": p_all + (beta + 1.96 * se) * (1 - sbar), "lula_rest": p_all - beta * sbar}


res["lean"] = {"place": lean(PLACE), "municipality": lean(SEC[:2]), "state": lean(["SG_UF"]), "country": lean(None)}
REGION = {"ne": {"MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA"}, "se": {"SP", "RJ", "MG", "ES"},
          "s": {"PR", "SC", "RS"}, "nco": {"AC", "AM", "AP", "PA", "RO", "RR", "TO", "DF", "GO", "MS", "MT"}}
for k, ufs in REGION.items():
    res["lean"][f"place|{k}"] = lean(PLACE, s.SG_UF.isin(ufs))
for k, v in res["lean"].items():
    log("lean within", k, {a: round(b, 4) for a, b in v.items()})

# ---------------------------------------------------------------------------------
# The machine logs: the same count machine by machine, and voters with no fingerprints on file
lg = pd.read_csv(out / "urna_logs_sample.csv")
lg = lg[(lg.NR_TURNO == 2) & (lg.status == "ok") & (lg.votes_2 > 0)].merge(s[SEC + ["manual"]], on=SEC)
res["logs_machines"] = int(len(lg))
res["logs_equal"] = float((lg.manual_2 == lg.manual).mean())
res["logs_within_1"] = float(((lg.manual_2 - lg.manual).abs() <= 1).mean())
log("log sample:", len(lg), "machines; log count = tally report in", f"{res['logs_equal']:.1%}", f"(within 1: {res['logs_within_1']:.1%})")
r = lg[lg.group == "random"]
nobio = lambda d: float((d.votes_2 - d.bio_2 - d.manual).sum() / d.votes_2.sum())
boot = [nobio(r.iloc[rng.integers(0, len(r), len(r))]) for _ in range(4000)]
res["no_bio"] = {"machines": int(len(r)), "share": nobio(r), "lo": float(np.percentile(boot, 2.5)),
                 "hi": float(np.percentile(boot, 97.5)), "official_turnout": res["official_turnout"]}
res["no_bio"].update({k2: res["no_bio"][k] * res["official_turnout"] for k, k2 in (("share", "voters"), ("lo", "voters_lo"),
                                                                                    ("hi", "voters_hi"))})
log("no fingerprints on file:", res["no_bio"])

(out / "biometria.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
log("done ->", out / "biometria.json")
