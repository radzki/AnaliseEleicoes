"""Read the voting-machine logs of a sample of 2026 sections and measure, for each machine and round:
when it opened and closed, how many votes came after 17h (Brasília time) and how each voter was
identified (fingerprint or manual release by the poll worker).

Usage: python -I scripts/07_urna_logs.py <processed_2026> <cache_dir> <out_dir>

Sample (fixed seed): every near-unanimous runoff section (turnout >= 95%, a candidate >= 90%,
>= 100 eligible), 250 other Lula strongholds (>= 90%), 150 Flávio strongholds, 1,000 sections at
random. Files come from the TSE results site (resultados.tse.jus.br), runoff pleito 3221; each
machine's log also holds its round-1 day when the same machine served both rounds.
"""
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

proc, cache, out = (Path(a) for a in sys.argv[1:4])
sys.stdout.reconfigure(encoding="utf-8")
cache.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados"
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
DAYS = {1: "04/10/2026", 2: "25/10/2026"}
# Hours to add to the machine's local clock to get Brasília time (Acre and western Amazonas are -2,
# found from a 06:xx opening; Fernando de Noronha, +1, opens at 09:xx).
UF_OFFSET = {"AC": 2, "AM": 1, "RR": 1, "RO": 1, "MT": 1, "MS": 1}

# ---------------------------------------------------------------------------------
# Sample
w = pd.read_parquet(proc / "secao_wide.parquet", columns=["NR_TURNO", *SEC, "QT_APTOS", "QT_COMPARECIMENTO",
                                                           "QT_VOTOS_NOMINAIS", "v13", "v22"])
w = w[(w.NR_TURNO == 2) & w.v13.notna() & (w.QT_VOTOS_NOMINAIS > 0)].copy()
w["lula"] = w.v13 / w.QT_VOTOS_NOMINAIS
w["right"] = w.v22.fillna(0) / w.QT_VOTOS_NOMINAIS
w["turnout"] = w.QT_COMPARECIMENTO / w.QT_APTOS
big = w.QT_APTOS >= 100
corner = big & (w.turnout >= 0.95) & ((w.lula >= 0.9) | (w.right >= 0.9))
groups = {
    "corner_lula": w[corner & (w.lula >= 0.9)],
    "corner_right": w[corner & (w.right >= 0.9)],
    "lula90": w[big & ~corner & (w.lula >= 0.9)].sample(250, random_state=2026),
    "right90": w[big & ~corner & (w.right >= 0.9)].sample(150, random_state=2026),
    "random": w.sample(1000, random_state=2026),
}
sample = pd.concat([g.assign(group=k) for k, g in groups.items()]).drop_duplicates(SEC)
print({k: len(g) for k, g in groups.items()}, "->", len(sample), "sections", flush=True)


# ---------------------------------------------------------------------------------
# Download (cached): the section's file list, then its log
def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** i)
        except Exception:
            time.sleep(2 ** i)
    return None


def fetch(r):
    uf, mu, zn, se = r.SG_UF.lower(), f"{r.CD_MUNICIPIO:05d}", f"{r.NR_ZONA:04d}", f"{r.NR_SECAO:04d}"
    path = cache / uf / f"{mu}-{zn}-{se}-log.jez"
    if path.exists():
        return path
    aux = get(f"{BASE}/{uf}/{mu}/{zn}/{se}/p003221-{uf}-m{mu}-z{zn}-s{se}-aux.json")
    if not aux:
        return None
    meta = json.loads(aux)
    for h in meta.get("hashes", []):
        log = next((a["nm"] for a in h["arq"] if a["tp"] == "log"), None)
        if log and h.get("st") == "Totalizado":
            data = get(f"{BASE}/{uf}/{mu}/{zn}/{se}/{h['hash']}/{log}")
            if data:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                return path
    return None


# ---------------------------------------------------------------------------------
# Parse one log: per round, opening, closing, votes, votes after 17h, identification of each voter
def hhmmss(t):
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def parse(path, uf):
    raw = zipfile.ZipFile(path).read("logd.dat").decode("latin1")
    rows = {}
    for t, day in DAYS.items():
        open_t = close_t = None
        votes, bio, manual, late, late_nonbio = 0, 0, 0, 0, 0
        last_vote = None
        flag_bio = flag_manual = False
        lines = [l.split("\t") for l in raw.splitlines() if l.startswith(day)]
        for f in lines:
            if len(f) < 5:
                continue
            msg = f[4]
            if msg == "Urna pronta para receber votos" and open_t is None:
                open_t = hhmmss(f[0][11:19])
            elif msg == "Tipo de habilitação do eleitor [biométrica]":
                flag_bio = True
            elif re.match(r"Mesário \d+ habilitou o eleitor", msg):
                flag_manual = True
            elif msg == "O voto do eleitor foi computado":
                s = hhmmss(f[0][11:19])
                votes += 1
                bio += flag_bio
                manual += flag_manual
                last_vote = s
                rows.setdefault(t, {})["_votes_t"] = rows.get(t, {}).get("_votes_t", []) + [(s, flag_bio)]
                flag_bio = flag_manual = False
            elif msg == "Procedimento de encerramento confirmado":
                close_t = hhmmss(f[0][11:19])
        if not votes and open_t is None:
            continue
        off = UF_OFFSET.get(uf, 0)
        if open_t is not None:
            h = open_t // 3600
            off = {6: 2, 7: 1, 8: 0, 9: -1}.get(h, off)
        off_s = off * 3600
        vt = rows.get(t, {}).pop("_votes_t", [])
        late = sum(s + off_s >= 17 * 3600 for s, _ in vt)
        late_nonbio = sum(s + off_s >= 17 * 3600 and not b for s, b in vt)
        rows[t] = {"votes": votes, "bio": bio, "manual": manual, "late": late, "late_nonbio": late_nonbio,
                   "open_brt": None if open_t is None else (open_t + off_s) / 3600,
                   "close_brt": None if close_t is None else (close_t + off_s) / 3600,
                   "last_vote_brt": None if last_vote is None else (last_vote + off_s) / 3600, "offset_h": off}
    return rows


def work(r):
    path = fetch(r)
    if path is None:
        return {**{k: getattr(r, k) for k in SEC}, "status": "missing"}
    try:
        res = parse(path, r.SG_UF)
    except Exception as e:
        return {**{k: getattr(r, k) for k in SEC}, "status": f"parse error: {e}"}
    rec = {**{k: getattr(r, k) for k in SEC}, "status": "ok"}
    for t, d in res.items():
        rec.update({f"{k}_{t}": v for k, v in d.items()})
    return rec


recs = []
with cf.ThreadPoolExecutor(4) as ex:
    for i, rec in enumerate(ex.map(work, sample.itertuples(index=False)), 1):
        recs.append(rec)
        if i % 100 == 0:
            print(f"{i}/{len(sample)}", flush=True)

res = sample.merge(pd.DataFrame(recs), on=SEC, how="left")
res.to_csv(out / "urna_logs_sample.csv", index=False)
ok = res[res.status == "ok"]
print("logs read:", len(ok), "of", len(res), "| status:", res.status.value_counts().to_dict())
print("log votes == official turnout (runoff):", int((ok.votes_2 == ok.QT_COMPARECIMENTO).sum()), "of", int(ok.votes_2.notna().sum()))
