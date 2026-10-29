"""Look for ballot stuffing in the voting-machine logs read by scripts/07_urna_logs.py.

Usage: python -I scripts/12_urna_bursts.py <cache_dir> <results_dir>

Poll workers voting in place of absent voters would leave, in the machine's log, votes packed closer
together than real voters manage (each voter is identified, released and votes), in runs, and
released by the poll worker instead of by the voter's fingerprint. For each machine of the sample and
each round, the log gives every vote's release (fingerprint, poll worker, or neither), the time the
voter was released and the time the vote was counted.

Writes <results_dir>/urna_bursts.csv (one row per machine and round) and urna_bursts.json (by group).
"""
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

cache, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.stdout.reconfigure(encoding="utf-8")
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
DAYS = {1: "04/10/2026", 2: "25/10/2026"}
# a vote counted this soon after the previous one, and runs of them
FAST_GAP_S, RUN_MIN = 30, 5


def secs(stamp):
    h, m, s = (int(x) for x in stamp[11:19].split(":"))
    return h * 3600 + m * 60 + s


def votes(path):
    """Each counted vote, per round: (released at, counted at, release type)."""
    raw = zipfile.ZipFile(path).read("logd.dat").decode("latin1")
    per = {1: [], 2: []}
    for t, day in DAYS.items():
        hab, kind = None, "none"
        for line in raw.splitlines():
            if not line.startswith(day):
                continue
            f = line.split("\t")
            if len(f) < 5:
                continue
            m = f[4]
            if m.startswith("Tipo de habilita") and "[biom" in m:
                kind = "bio"
            # as in scripts/07_urna_logs.py: a manual release starts by asking the voter's personal data
            elif (m.startswith("Solicita") and "habilita" in m and "manual" in m) or re.match(r"Mes.rio \d+ habilitou o eleitor", m) \
                    or m.startswith("Digital coletada bate com uma digital gravada"):
                kind = "poll_worker"
            elif m == "Eleitor foi habilitado":
                hab = secs(f[0])
            elif m == "O voto do eleitor foi computado":
                per[t].append((hab, secs(f[0]), kind))
                hab, kind = None, "none"
    return per


def runs(flags):
    """Lengths of the runs of True in a boolean sequence."""
    out_, k = [], 0
    for x in flags:
        if x:
            k += 1
        elif k:
            out_.append(k)
            k = 0
    if k:
        out_.append(k)
    return out_


def metrics(v):
    """Per machine and round: gaps between votes, runs of fast votes and of poll-worker releases."""
    counted = np.array([c for _, c, _ in v])
    gaps = np.diff(counted)
    booth = np.array([c - h for h, c, _ in v if h is not None])
    kinds = [k for _, _, k in v]
    fast = gaps <= FAST_GAP_S
    fast_runs = [k + 1 for k in runs(fast)]  # k short gaps join k + 1 votes
    pw_runs = runs([k == "poll_worker" for k in kinds])
    # a run of fast votes that were all released by a poll worker or without a fingerprint
    nofp = np.array([k != "bio" for k in kinds])
    fast_nofp = [k + 1 for k in runs(fast & nofp[1:] & nofp[:-1])]
    return gaps, {"votes": len(v), "poll_worker": kinds.count("poll_worker"), "no_type": kinds.count("none"),
                  "gap_median_s": float(np.median(gaps)) if len(gaps) else None,
                  "fast_gap_share": float(fast.mean()) if len(gaps) else None,
                  "booth_median_s": float(np.median(booth)) if len(booth) else None,
                  "longest_fast_run": max(fast_runs, default=1), "fast_runs_5": sum(k >= RUN_MIN for k in fast_runs),
                  "longest_poll_worker_run": max(pw_runs, default=0),
                  "longest_fast_nofp_run": max(fast_nofp, default=0 if not nofp.any() else 1)}


sample = pd.read_csv(out / "urna_logs_sample.csv")
sample = sample[sample.status == "ok"]
rows, gaps_all, corner = [], [], []
for r in sample.itertuples(index=False):
    path = cache / r.SG_UF.lower() / f"{r.CD_MUNICIPIO:05d}-{r.NR_ZONA:04d}-{r.NR_SECAO:04d}-log.jez"
    if not path.exists():
        continue
    for t, v in votes(path).items():
        if not v:
            continue
        gaps, m = metrics(v)
        gaps_all += [(r.group, t, g) for g in gaps]
        rows.append({**{k: getattr(r, k) for k in SEC}, "group": r.group, "round": t, **m})
        if r.group == "corner_lula" and t == 2:
            corner.append(v)

M = pd.DataFrame(rows)
M.to_csv(out / "urna_bursts.csv", index=False)
G = pd.DataFrame(gaps_all, columns=["group", "round", "gap"])
summary = {"fast_gap_s": FAST_GAP_S, "run_min": RUN_MIN, "groups": []}
for (grp, t), d in M.groupby(["group", "round"]):
    g = G[(G.group == grp) & (G["round"] == t)].gap
    summary["groups"].append({
        "group": grp, "round": int(t), "machines": len(d), "votes": int(d.votes.sum()),
        "gap_p01_s": float(g.quantile(0.01)), "gap_p05_s": float(g.quantile(0.05)), "gap_median_s": float(g.median()),
        "fast_gap_share": float((g <= FAST_GAP_S).mean()),
        "machines_with_fast_run_5": float((d.fast_runs_5 > 0).mean()),
        "longest_fast_run_p95": float(d.longest_fast_run.quantile(0.95)), "longest_fast_run_max": int(d.longest_fast_run.max()),
        "poll_worker_share": float(d.poll_worker.sum() / d.votes.sum()),
        "longest_poll_worker_run_p95": float(d.longest_poll_worker_run.quantile(0.95)),
        "longest_poll_worker_run_max": int(d.longest_poll_worker_run.max()),
        "machines_with_fast_nofp_run_5": float((d.longest_fast_nofp_run >= RUN_MIN).mean()),
        "booth_median_s": float(d.booth_median_s.median()),
    })
# Planted stuffing, in the near-unanimous Lula machines (runoff): 20 extra votes per machine, released by
# a poll worker, 25 seconds apart (typing the voter's number, the poll worker's fingerprint, the vote).
# "run": all together at the end of the day; "mixed": one by one, between real voters at random.
# A machine is caught when its longest run of poll-worker releases is longer than any seen in the real
# sample, or when it has 5 fast votes in a row without a fingerprint.
real = M[M["round"] == 2]
pw_max, rng = int(real.longest_poll_worker_run.max()), np.random.default_rng(2026)
summary["planted"] = {"extra_votes": 20, "gap_s": 25, "real_longest_poll_worker_run_max": pw_max}
for how in ("run", "mixed"):
    caught, pw, tot = 0, 0, 0
    for v in corner:
        last = v[-1][1]
        if how == "run":
            p = v + [(last + 25 * i, last + 25 * i + 10, "poll_worker") for i in range(1, 21)]
        else:
            p = list(v)
            for _ in range(20):
                i = int(rng.integers(1, len(p)))
                t0 = (p[i - 1][1] + p[i][1]) / 2
                p.insert(i, (t0 - 10, t0, "poll_worker"))
        _, m = metrics(p)
        caught += m["longest_poll_worker_run"] > pw_max or m["longest_fast_nofp_run"] >= RUN_MIN
        pw += m["poll_worker"]
        tot += m["votes"]
    summary["planted"][how] = {"machines": len(corner), "caught": int(caught), "poll_worker_share": pw / tot}
print("planted stuffing:", summary["planted"])
(out / "urna_bursts.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
cols = ["group", "round", "machines", "gap_p01_s", "gap_median_s", "fast_gap_share", "machines_with_fast_run_5",
        "longest_fast_run_max", "poll_worker_share", "longest_poll_worker_run_max", "machines_with_fast_nofp_run_5", "booth_median_s"]
print(pd.DataFrame(summary["groups"])[cols].round(3).to_string(index=False))
