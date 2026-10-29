# Eleição presidencial de 2026: os números mostram sinais de fraude?

Testes estatísticos de forense eleitoral aplicados aos boletins de urna de cada seção da eleição
presidencial de 2026 (Lula × Flávio Bolsonaro), com a eleição de 2022 como régua. Tudo parte dos
dados abertos do Tribunal Superior Eleitoral (TSE).

**Relatório publicado:** https://eleicoes.radzkitech.com

**Resposta curta: não foram encontrados sinais de fraude manual capazes de mudar o resultado.** Em quase todos
os testes, 2026 se comporta como uma eleição normal, do mesmo jeito que 2022. A principal exceção
são seções com comparecimento quase total e quase todos os votos em Lula, que ficaram mais comuns
do que em 2022. Estes dados não explicam por quê, mas o efeito é pequeno demais para mudar o
resultado (veja a tabela abaixo).

## Escopo

- Só a eleição para presidente (`CD_CARGO == 1`), 1º e 2º turnos, de 2026 e de 2022; na seção "Com 2018
  também", também de 2018 (Haddad × Jair Bolsonaro), como segunda referência.
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
| Soma das seções × totais oficiais | Votos que somem ou aparecem entre a urna e o total | 2022 bate nos dois turnos. 2026, 1º turno: bate, com exceção dos votos válidos em 2.148 das 6.292 unidades município-zona; em cada uma, a diferença é exatamente o número de votos de Leonardo Alves de Araújo (PRTB, 28), que desistiu da candidatura em 30 de setembro e cujos 5.246 votos o TSE conta como nulos técnicos. Como os totais saem da mesma apuração dos boletins, isso mostra que os arquivos do TSE batem entre si, não que cada boletim registrou corretamente a sua urna. 2026, 2º turno (totais publicados pelo TSE em 27 de outubro): todos os campos e os votos de Lula e de Flávio batem nas 6.292 unidades município-zona, e os mesmos números batem com o relatório oficial de totalização, no país, em cada UF e no exterior |
| Com 2018: seções quase unânimes e que destoam do local | As perguntas 3 e 4 com uma segunda eleição de referência | Quase unânimes para o PT: 92 em 2026, 30 em 2022 e 38 em 2018 (para o candidato Bolsonaro, 5, 3 e 29). Seções que destoam do local a favor do PT: 1.059, 1.105 e 1.281 |
| Um candidato ganhou votos e o outro perdeu, entre os turnos | O "21 para 1" que circulou depois do 2º turno | 21,6 para 1 a favor de Lula em 2026, 9,9 para 1 a favor de Jair em 2022 e 1,6 para 1 a favor de Haddad em 2018 (os dois perderam). Um modelo em que cada seção segue o ganho médio do seu município, com desvios sorteados entre seções do mesmo estado com ganhos parecidos, dá 20,7, 9,5 e 1,7: dados ÷ modelo = 1,04, 1,04 e 0,94. Com fraude plantada em 1 de cada 5 seções, 1,37; em todas as seções, 0,97 (não aparece) |
| Concentração do voto | Votos acrescentados em redutos | Seções com 90% ou mais no 2º turno, para o PT: 6.899 em 2026, 9.538 em 2022 e 15.133 em 2018 (Haddad perdeu); para o adversário: 384, 220 e 1.328 (Jair venceu em 2018). Os dois lados têm o máximo em 2018, o 2º turno com o voto mais dividido entre lugares (18,5% das seções com 80% ou mais para um dos dois, contra 10,0% e 8,7%): seções extremas não acompanham quem vence. As com comparecimento ≥ 90% e PT ≥ 90% subiram de 427 para 761 (eram 786 em 2018), o mesmo sinal da pergunta 4 |
| Esperado × observado, sem ver o município | Mudança aplicada a um município inteiro | Municípios a mais de 4 erros típicos a favor do PT: 11 em 2026, 12 em 2022 e 14 em 2018. Fraco: com o modelo treinado de novo, 5% dos votos de Flávio trocados em 1.000 municípios sorteados são apontados em 9; 10%, em 358; os mesmos 5% em todos os municípios não aparecem |
| Detector automático (Isolation Forest e LOF) | Seções estranhas em vários números ao mesmo tempo | Acima do corte de 0,60: 185 seções por 100 mil em 2026, 162 em 2022 e 477 em 2018; sem as do exterior, 47, 66 e 352. 2018 tem mais por ter outros níveis de brancos, nulos e tamanho de seção; 2026 e 2022 são comparáveis. As mais estranhas são do exterior, pequenas, de presídios e de aldeias. Fraco para fraude: enchimento plantado em 100 seções, 13 passam do corte |

**O que estes testes não conseguem mostrar:** eles encontram números inventados à mão e urnas
"engordadas". Não encontram uma mudança que alterasse todas as urnas na mesma proporção, porque ela
não deixaria nenhum desses rastros. Para isso existem outros controles, fora destes dados: o boletim
impresso de cada urna, que é público, e as auditorias e testes de urna do TSE.

## Estrutura

```
scripts/01_extract.py      zips do TSE -> parquet (só presidente, por seção, dois turnos)
scripts/02_analyze.py      testes forenses -> results/results_<ano>.json, states_<ano>.csv
scripts/03_consistency.py  soma das seções x totais oficiais por município e zona, por turno
scripts/04_export.py       results/*.json -> results/dash/*.json, as tabelas que o relatório lê
scripts/05_site.py         monta o site estático em site/
scripts/06_og_image.py     gera a imagem de compartilhamento (web/og.png)
scripts/07_urna_logs.py    lê os registros (logs) de uma amostra de urnas no site de resultados do TSE
scripts/08_runoff_totals.py  soma das seções x votos de cada candidato por município e zona e x relatório oficial do 2º turno
scripts/09_sim_data.py     empacota as seções do 2º turno de 2026 para a aba "Tente fraudar!" (results/sim)
scripts/10_more_tests.py   mais testes (tamanho da seção, migração proporcional, qui-quadrado por local,
                           Shpilkin, segundo algarismo de Benford), com fraudes plantadas -> more_tests_<ano>.json
scripts/11_urna_assinaturas.py  na mesma amostra de urnas: assinaturas digitais do boletim, do RDV e do
                           registro, boletim x dados publicados e recontagem do RDV -> urna_assinaturas.csv
scripts/12_urna_bursts.py  votos em rajada e liberações pelo mesário nos registros da amostra de urnas, com enchimento plantado
scripts/13_mixture.py      modelo de mistura (Klimek et al., 2012), por estado, com fraude plantada -> mixture_<ano>.json
scripts/14_three_elections.py  2026, 2022 e 2018: testes de referência, um ganhou e o outro perdeu (com modelo nulo),
                           concentração, esperado × observado sem ver o município, Isolation Forest e LOF -> three_elections.json
report/                    a página do relatório (HTML + JavaScript com d3); o texto fica em locales/
locales/pt-BR.json         todo o texto da página: cada {{chave}} de report/index.html, web/page.html e
                           web/404.html, e as chaves "js." que os scripts leem com vf.t() (core.js)
locales/en.json, es.json   as traduções (páginas /en/ e /es/); cada texto guarda o hash do português de que
                           foi traduzido, e onde o português mudou a página mostra o português, marcado
scripts/15_i18n.py         status, textos a traduzir e merge de traduções (com o hash do português atual)
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
(2026), `data/raw2022` (2022) e `data/raw2018` (2018, só `votacao_secao` e `detalhe_votacao_secao`). O CDN do TSE às vezes entrega uma cópia antiga em cache depois de uma
atualização: acrescente um parâmetro qualquer à URL (por exemplo `?v=1`) e confira a data de geração
(`DT_GERACAO`) dentro de cada arquivo; os totais por município do 2º turno de 2026 foram gerados em
27/10/2026.

| Arquivo | Caminho no CDN |
|---|---|
| `votacao_secao_<ano>_BR.zip` | `votacao_secao/` |
| `detalhe_votacao_secao_<ano>.zip` | `detalhe_votacao_secao/` |
| `detalhe_votacao_munzona_<ano>.zip` | `detalhe_votacao_munzona/` |

Depois:

```sh
python -I scripts/01_extract.py data/raw data/processed 2026
python -I scripts/01_extract.py data/raw2022 data/processed2022 2022
python -I scripts/01_extract.py data/raw2018 data/processed2018 2018
python -I scripts/02_analyze.py data/processed results 2026
python -I scripts/02_analyze.py data/processed2022 results 2022
python -I scripts/03_consistency.py data/raw data/processed results 2026
python -I scripts/03_consistency.py data/raw2022 data/processed2022 results 2022
python -I scripts/07_urna_logs.py data/processed data/urna_logs results   # baixa ~250 MB do TSE
python -I scripts/08_runoff_totals.py data/raw_t2 data/processed results
python -I scripts/09_sim_data.py data/processed results
python -I scripts/10_more_tests.py data/processed results 2026
python -I scripts/10_more_tests.py data/processed2022 results 2022
python -I scripts/10_more_tests.py data/processed2018 results 2018
python -I scripts/11_urna_assinaturas.py data/processed data/urna_files results   # baixa ~350 MB do TSE
python -I scripts/12_urna_bursts.py data/urna_logs results
python -I scripts/13_mixture.py data/processed results 2026        # alguns minutos por ano
python -I scripts/13_mixture.py data/processed2022 results 2022
python -I scripts/13_mixture.py data/processed2018 results 2018
python -I scripts/14_three_elections.py results data/processed data/processed2022 data/processed2018   # alguns minutos
python -I scripts/04_export.py results data/processed data/processed2022 results/dash
python -I scripts/05_site.py . site
```

`scripts/11_urna_assinaturas.py` segue o pacote de documentação técnica do TSE
(`formato-arquivos-bu-rdv-ass-digital-v2.zip`: especificações ASN.1 do boletim, do RDV e da assinatura, e scripts
de exemplo). O site do TSE responde 403 a downloads por script, então o pacote vem de uma cópia pública no GitHub e
só é aceito com o SHA-256 publicado em outras cópias independentes (veja a docstring do script). O arquivo de
assinatura de 2026 tem duas diferenças em relação à especificação publicada, descritas no script. A cadeia de
certificados é conferida até as autoridades certificadoras das urnas; os certificados raiz não estão disponíveis
para download.

`results/totalizacao_T1_BR.txt` é o texto do relatório oficial de totalização do 1º turno de 2026
(`relatorio_resultado_totalizacao/Relatorio_Resultado_Totalizacao_2026_BR.zip`), usado para
conferir os votos nulos técnicos.

Para o 2º turno de 2026, `scripts/08_runoff_totals.py` lê dois arquivos em `data/raw_t2`:
`votacao_candidato_munzona/votacao_candidato_munzona_2026.zip` (votos de cada candidato por
município e zona, os dois turnos) e o mesmo `Relatorio_Resultado_Totalizacao_2026_BR.zip`, que desde
27 de outubro traz também o relatório do 2º turno. `results/totalizacao_T2_BR.txt` é o texto desse
relatório (`6258_BR_BRASIL_2026_T2_PRESIDENTE.pdf`), extraído com `pypdf` (`PdfReader`, página a
página); o mesmo método reproduz exatamente o texto do 1º turno.

## Tente fraudar!

A terceira aba da página é um simulador. O leitor escolhe a quem favorecer e como fraudar (um
programa em todas as urnas, trocar votos em algumas urnas, encher urnas ou inventar os números do
boletim), quantas urnas e com que intensidade. O navegador aplica a fraude a uma cópia dos boletins
de todas as 499.205 urnas do 2º turno de 2026 e refaz os testes da página.

- **Dados:** `scripts/09_sim_data.py` grava `results/sim/secoes_2026_t2.bin` (2,8 MB, colunas
  compactadas com gzip e lidas com `DecompressionStream`) e `results/sim/meta.json`. Os dados só
  são baixados quando a aba é aberta.
- **Testes:** `report/sim.js` refaz, com as mesmas definições de `scripts/02_analyze.py`, o último
  dígito, o excesso de números redondos, os percentuais inteiros, as urnas que destoam do seu local, o
  canto comparecimento × percentual, a diferença entre modelos de urna e a mudança entre os turnos.
  Sem fraude, ele reproduz exatamente os números da página. A única aproximação é o número de
  percentuais inteiros esperado ao acaso: o simulador o calcula pela distribuição binomial, enquanto
  a página usa a média de 200 sorteios (10.232 contra 10.234).
- **"A fraude aparece?":** "Sim" quando a fraude muda o número mais do que o acaso explica, em
  comparação com o resultado real: p < 0,001 no último dígito, mais de 4 desvios-padrão nos outros.
  A coluna não diz se o número real é normal (isso é o que a página avalia; nos números reais, a
  pergunta 4 chamou atenção). A diferença entre modelos compara cada modelo com a média de todos, e
  a correlação entre comparecimento e mudança entre turnos só conta quando se afasta de zero.
- **Turnos:** as fraudes feitas por programa (em todas as urnas ou em algumas) agem por padrão nos
  dois turnos, como agiria um programa instalado na urna; o leitor pode limitá-las ao 2º turno, o
  que deixa uma marca a mais na mudança entre os turnos. Encher urnas e reescrever boletins são
  feitos só no 2º turno.
- **Para não virar desinformação:** a aba abre no resultado real. Com qualquer fraude, o quadro
  do resultado diz "SIMULAÇÃO · não é o resultado real", o nome de cada candidato leva
  "· simulação" e o resultado real aparece logo abaixo.
- **A favor de Lula:** Lula venceu, então não há resultado a virar. O botão passa a ser "Do tamanho
  da vitória de Lula": dimensiona a fraude que teria fabricado essa vitória (mover mais da metade
  da diferença, ou acrescentar mais que a diferença ao encher urnas) e a aplica por cima dos dados
  reais, para mostrar as marcas que ela deixaria. Não invertemos os candidatos para criar um
  cenário em que Lula perdeu: os testes tratam os dois lados igualmente, então isso só repetiria o
  lado de Flávio com os nomes trocados, e com a geografia errada (os redutos de Lula iriam parar
  onde Flávio é forte).
- **Gráficos:** a curva normal (cada seção frente ao seu local) e a grade comparecimento × percentual do
  candidato favorecido são refeitas a cada mudança. A grade abre como um analista a veria; "O que a fraude
  mudou" destaca as células que ganharam seções, o que só existe porque a simulação conhece o resultado real.
- **Fora dos dados:** a aba explica o que pegaria cada fraude fora destes números (teste de
  integridade, boletim impresso, fiscais). Quando o programa em todas as urnas passa pelos 16
  testes sem aparecer, o resumo acima da tabela já diz que o teste de integridade a pegaria: todas
  as urnas sorteadas estariam adulteradas, e basta um voto trocado para o boletim não bater com as
  cédulas, desde que o programa não saiba distinguir o teste de uma votação real. Desde 2022, parte
  das urnas do teste (em 2022, 58 de 641, num projeto-piloto, segundo a Gazeta do Povo) é liberada com a biometria de
  eleitores de verdade, para dificultar essa distinção. Segundo reportagens sobre os TREs, o teste de integridade
  sorteia de 20 a 33 urnas por estado. Como o sorteio, a chance de uma urna adulterada ser sorteada
  é calculada estado por estado, com 20 urnas por estado (o mínimo, 540 no país) e nenhuma no
  exterior, o que tende a subestimá-la. Uma conta com 540 urnas sorteadas no país inteiro errava
  para fraudes num só estado: 300 urnas em São Paulo davam 27,7% (por estado: 5,6%), e 300 em
  Roraima também 27,7% (por estado: 98,8%).

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
