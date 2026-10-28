"""Write the report's store documents (page files + dataset entries) as JSON for ArtifactData.

Usage: python -I report/build_store.py <report_dir>
"""
import json
import sys
from pathlib import Path

rep = Path(sys.argv[1])
out = rep / "store"
out.mkdir(exist_ok=True)
UPDATED = {"at": "2026-10-27T01:25:45Z", "by": "Claude, a partir dos dados abertos do TSE (scripts/04_export.py)"}
SRC = "Calculado a partir dos resultados presidenciais por seção do TSE (votacao_secao e detalhe_votacao_secao, 2026 e 2022)."
DATASETS = {
    "summary": ("feae4b606441a4b88cef0f750b19a854", "Totais nacionais por turno", "Eleitores aptos, comparecimento, votos válidos e votos de cada finalista nos dois turnos de 2026 e 2022, somados a partir de todas as seções."),
    "scorecard": ("b4e1ff14911a4eb3beb45b41e2ba54b4", "Resultados dos testes forenses", "Uma linha por teste, medida, turno e ano: o valor observado, o que só o acaso daria e a estatística do teste."),
    "last_digit": ("228b570c7294c23a9889155aa6666c88", "Frequência do último dígito", "Fração das contagens por seção terminadas em cada dígito de 0 a 9, para Lula, o candidato Bolsonaro e o comparecimento, por turno e ano."),
    "pct_hist": ("310e5719ab02338bcf7e8a4c9214381d", "Percentuais em faixas de 0,1 ponto", "Seções do 2º turno por faixa de 0,1 ponto do percentual de Lula e do comparecimento, com a quantidade esperada por reamostragem binomial das próprias contagens."),
    "z_hist": ("0df60168c118bf51510f4bafb2c1947e", "Desvio da seção frente ao local", "Histograma do desvio de cada seção em relação ao restante do seu local de votação (z), para o percentual de Lula, o comparecimento e a variação entre turnos, com o esperado pela curva normal."),
    "states": ("7c98d2752630bc499081197a837f3736", "Comparecimento e migração por UF", "Por UF: seções, comparecimento em cada turno, percentual de Lula no 2º turno e variação do percentual de Lula entre os turnos."),
    "fingerprint": ("c6a5f260d9d625cbc53df17afef2913a", "Grade comparecimento × % de Lula", "Seções do 2º turno contadas em células de 1 ponto de comparecimento e de percentual de Lula, 2026 e 2022."),
    "corner": ("f626e357501a38d10fc42763841f768b", "Seções quase unânimes", "Seções do 2º turno de 2026 com comparecimento ≥ 95% e 90% ou mais dos votos para um candidato (Lula ou Flávio), com pelo menos 100 eleitores aptos, com os valores do 1º turno e o local de votação."),
    "timing": ("a6ffa75bed1ffacd6e5d9f8e5ebac9c4", "Progressão da apuração", "Fração dos votos recebidos e percentual de Lula entre os dois finalistas, em passos de 10 minutos a partir das 17h, por turno e ano."),
    "urna": ("be7704617c40d8c3469ee7afb8bfb098", "Resultados por modelo de urna", "Seções e percentual de Lula por modelo de urna, bruto e comparado com outras urnas do mesmo local de votação."),
    "consistency": ("1243a9b36bf84e5e31307154ce8e1f24", "Seções vs. totais oficiais", "Boletins das seções somados por unidade município-zona, comparados aos totais publicados separadamente pelo TSE, campo a campo e, em 2026, turno a turno, incluindo os votos de cada finalista."),
    "strongholds": ("4383205ada88579925d457050b3709f2", "Redutos e comparecimento quase total", "Por ano e turno, seções com 100 ou mais eleitores aptos: todas, as com Lula ≥ 90% e as com o candidato Bolsonaro ≥ 90% (eleitores aptos, votantes, comparecimento e quantas chegaram a 95% ou mais de comparecimento); e as mesmas seções do 2º turno comparadas uma a uma entre 2022 e 2026 (variação mediana de aptos e de votantes)."),
    "more_tests": ("PENDENTE", "Mais testes", "Testes de outros métodos, em 2026 e em 2022: tamanho da seção, migração proporcional entre turnos, homogeneidade no local de votação, Shpilkin, segundo dígito de Benford e modelo de mistura (Klimek), com o que mostrariam fraudes plantadas nos dados; e, nos registros de uma amostra de urnas, rajadas de votos e liberações pelo mesário por grupo."),
    "size_curve": ("PENDENTE", "% de Lula por tamanho da seção", "Diferença entre o percentual de Lula na seção e no restante do seu local de votação, por faixa de 25 votantes, no 2º turno de 2026 e de 2022, e com uma fraude plantada que só age em urnas com mais de 250 votantes."),
    "urna_assinaturas": ("PENDENTE", "Assinaturas e RDV de uma amostra de urnas", "Mesma amostra de urnas do 2º turno de 2026: assinaturas digitais do boletim de urna, do registro digital do voto (RDV) e do registro (log) verificadas, boletim comparado com os dados publicados e votos do RDV recontados."),
    "urna_logs": ("PENDENTE", "Registros (logs) de uma amostra de urnas", "Amostra de urnas do 2º turno de 2026 lida no site de resultados do TSE: por grupo (urnas quase unânimes, redutos de Lula e de Flávio, urnas sorteadas no país) e turno, votos computados depois das 17h (horário de Brasília), horário de encerramento e como os eleitores foram identificados (digital ou liberação manual pelo mesário); estimativa nacional de votos depois das 17h; conferência do número de votos com o comparecimento oficial."),
}
UPDATED_AT = {"corner": "2026-10-27T02:22:38Z", "strongholds": "2026-10-27T05:59:06Z", "consistency": "2026-10-28T01:00:28Z"}
docs = [("dash", "meta", {"title": "Eleições 2026 - Estatística Forense"}), ("dash", "params", {"cand": "ambos"})]
for i, (aid, title, desc) in DATASETS.items():
    docs.append(("datasets", i, {"title": title, "description": f"{desc} {SRC}",
                                  "source": {"kind": "file", "url": f"/_blob/{aid}", "name": f"{i}.json"},
                                  "updated": {**UPDATED, "at": UPDATED_AT.get(i, UPDATED["at"])}, "fixed": True}))
for f in ("index.html", "core.js", "charts.js", "tables.js", "simple.js", "sim.js"):
    docs.append(("files", f, {"text": (rep / f).read_text(encoding="utf-8")}))
for coll, doc_id, data in docs:
    p = out / f"{coll}__{doc_id}.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"{coll}/{doc_id}\t{p.stat().st_size:>7} B\t{p.as_posix()}")
