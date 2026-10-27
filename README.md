# Eleição presidencial de 2026: os números mostram sinais de fraude?

Testes estatísticos de forense eleitoral aplicados aos boletins de urna de cada seção da eleição
presidencial de 2026 (Lula × Flávio Bolsonaro), com a eleição de 2022 como régua. Tudo parte dos
dados abertos do Tribunal Superior Eleitoral (TSE).

**Relatório publicado:** https://eleicao-2026.pages.dev

**Resposta curta: não encontramos sinais de fraude capazes de mudar o resultado.** Em quase todos
os testes, 2026 se comporta como uma eleição normal, do mesmo jeito que 2022. A principal exceção
são seções com comparecimento quase total e quase todos os votos em Lula, que ficaram mais comuns
do que em 2022. Estes dados não explicam por quê, mas o efeito é pequeno demais para mudar o
resultado (veja a tabela abaixo).

## Escopo

- Só a eleição para presidente (`CD_CARGO == 1`), 1º e 2º turnos, de 2026 e de 2022.
- A unidade de análise é a seção eleitoral: uma urna, um boletim de urna.
- O voto é secreto. O relatório mostra apenas contagens observadas e variações líquidas entre os
  turnos; ele não estima como um grupo de eleitores votou (por exemplo, "os eleitores de X foram
  para Y"), porque os dados não permitem saber isso.

## O que foi testado

| Teste | O que procura | Resultado |
|---|---|---|
| Último dígito (Beber & Scacco, 2012) e excesso de múltiplos de 10 | Números inventados à mão | 2026 passa em todos. Em 2022, o último dígito dos votos de Jair Bolsonaro ficou fora do esperado em dois testes (p = 0,002 e 0,044), o que acontece por acaso quando se fazem dezenas de testes |
| Percentuais inteiros (Kobak, Shpilkin & Pshenichnikov, 2016) | Resultados ajustados para 50%, 60%, 70%… | 10.184 urnas com percentual inteiro exato de Lula; o acaso daria cerca de 10.234 |
| Seção comparada às outras do mesmo local de votação | Urnas que destoam das vizinhas | 1.059 urnas destoam a favor de Lula (1.105 em 2022) e 497 a favor de Flávio (494 a favor de Jair em 2022) |
| Comparecimento × percentual (Klimek et al., 2012) | Urnas "engordadas": comparecimento ≥ 95% e candidato ≥ 90% | **Chamou atenção.** 92 seções para Lula (30 em 2022), com 18.280 eleitores, 0,4% da margem; 64 já davam 90% ou mais a Lula no 1º turno. Entre as seções com Lula ≥ 90%, a fatia com comparecimento ≥ 95% foi de 1,4%, contra 0,3% em 2022; nas mesmas seções, os eleitores aptos ficaram estáveis e os votantes subiram 5,1%. Nos redutos de Flávio/Jair a fatia ficou estável (1,4% e 1,5%). Os dados não dizem por quê; se o comparecimento nos redutos de Lula tivesse ficado no nível de 2022, seriam cerca de 62 mil votantes a menos, 1,4% da margem. Para Flávio, 5 seções (3 para Jair em 2022) |
| Ordem de apuração e modelo de urna | Uma virada que dependesse da hora de chegada ou da máquina | Mesmo desenho de 2022; dentro da mesma zona, +0,24 p.p. por hora de atraso; entre modelos de urna no mesmo local, no máximo 0,06 p.p. No 2º turno de 2026, 99,6% dos votos chegaram ao TSE depois das 19h, quando o TSE começou a divulgar a apuração, depois da prorrogação da votação pelo STF |
| Migração entre turnos | Mudanças concentradas em poucas urnas | Lula ganhou de 1,2 a 4,3 p.p. em todas as UFs; dentro do mesmo local, a correlação entre aumento de comparecimento e migração é 0,013 |
| Soma das seções × totais oficiais | Votos que somem ou aparecem entre a urna e o total | 2022 bate nos dois turnos. 2026, 1º turno: bate, com exceção dos votos válidos em 2.148 das 6.292 unidades município-zona; em cada uma, a diferença é exatamente o número de votos de Leonardo Alves de Araújo (PRTB, 28), que desistiu da candidatura em 30 de setembro e cujos 5.246 votos o TSE conta como nulos técnicos. Como os totais saem da mesma apuração dos boletins, isso mostra que os arquivos do TSE batem entre si, não que cada boletim registrou corretamente a sua urna. 2026, 2º turno: o TSE ainda não publicou os totais por município |

**O que estes testes não conseguem mostrar:** eles encontram números inventados à mão e urnas
"engordadas". Não encontram uma mudança que alterasse todas as urnas na mesma proporção, porque ela
não deixaria nenhum desses rastros. Para isso existem outros controles, fora destes dados: o boletim
impresso de cada urna, que é público, e as auditorias e testes de urna do TSE.

## Estrutura

```
scripts/01_extract.py      zips do TSE -> parquet (só presidente, por seção, dois turnos)
scripts/02_analyze.py      testes forenses -> results/results_<ano>.json, states_<ano>.csv
scripts/03_consistency.py  soma das seções x totais oficiais por município e zona
scripts/04_export.py       results/*.json -> results/dash/*.json, as tabelas que o relatório lê
scripts/05_site.py         monta o site estático em site/
report/                    a página do relatório (HTML + JavaScript com d3), em português
web/                       o que o site estático acrescenta: dash.js (carrega os dados e roda os
                           cálculos da página), theme.css (cores, fontes, espaçamentos, claro e
                           escuro), o modelo da página, cabeçalhos HTTP e uma cópia do d3 7.9.0
results/                   saídas dos scripts
data/                      dados brutos e intermediários (2,3 GB, fora do git)
```

O relatório foi feito primeiro como um painel no claude.ai. `report/build_store.py` gera os
documentos desse painel; `scripts/05_site.py` gera a versão independente, que roda em qualquer
servidor de arquivos estáticos.

## Como reproduzir

Python 3.12:

```sh
python -m venv .venv && . .venv/bin/activate   # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Baixe os arquivos do TSE (`https://cdn.tse.jus.br/estatistica/sead/odsele/`) para `data/raw`
(2026) e `data/raw2022` (2022):

| Arquivo | Caminho no CDN |
|---|---|
| `votacao_secao_<ano>_BR.zip` | `votacao_secao/` |
| `detalhe_votacao_secao_<ano>.zip` | `detalhe_votacao_secao/` |
| `detalhe_votacao_munzona_<ano>.zip` | `detalhe_votacao_munzona/` |

Depois:

```sh
python -I scripts/01_extract.py data/raw data/processed 2026
python -I scripts/01_extract.py data/raw2022 data/processed2022 2022
python -I scripts/02_analyze.py data/processed results 2026
python -I scripts/02_analyze.py data/processed2022 results 2022
python -I scripts/03_consistency.py data/raw data/processed results 2026
python -I scripts/03_consistency.py data/raw2022 data/processed2022 results 2022
python -I scripts/04_export.py results data/processed data/processed2022 results/dash
python -I scripts/05_site.py . site
```

`results/totalizacao_T1_BR.txt` é o texto do relatório oficial de totalização do 1º turno de 2026
(`relatorio_resultado_totalizacao/Relatorio_Resultado_Totalizacao_2026_BR.zip`), usado para
conferir os votos nulos técnicos.

## Publicar

`scripts/05_site.py` só usa a biblioteca padrão do Python, e `results/dash` está no repositório,
então o site pode ser montado sem baixar os dados do TSE.

- **Cloudflare Pages (GitHub Actions):** `.github/workflows/deploy.yml` monta e publica o site a
  cada push ou merge em `main`, no projeto `eleicao-2026`. Precisa dos secrets
  `CLOUDFLARE_API_TOKEN` (permissão Account › Cloudflare Pages › Edit) e `CLOUDFLARE_ACCOUNT_ID`
  em Settings › Secrets and variables › Actions.
- **Cloudflare Pages (direto):** `python3 scripts/05_site.py . site && npx wrangler pages deploy site --project-name <nome>`
- **Cloudflare Pages (pelo GitHub):** comando de build `python3 scripts/05_site.py . site`, diretório de saída `site`.
- **nginx ou outro servidor:** sirva a pasta `site/` como arquivos estáticos.

Para ver localmente: `python -m http.server -d site 8000` e abra `http://localhost:8000`.
