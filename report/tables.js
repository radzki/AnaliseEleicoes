// Calculations and tables: test results side by side, corner sections, net change between rounds, states, machine models, consistency.
(() => {
  dash.calc('tests', {
    inputs: ['scorecard'],
    title: 'Testes, 2026 ao lado de 2022',
    description: 'O resultado de cada teste em 2026 e em 2022 lado a lado, pareados por teste, medida e turno, escritos em português com unidade e estatística do teste.',
    fn: (scorecard) => {
      const TEST = {
        ld: 'Contagens terminadas em 0 (por seção)',
        heap: 'Excesso em 10, 20, 30… frente a valores vizinhos',
        int: 'Seções com percentual inteiro exato',
        'ldagg|zona': 'Votos de Lula terminados em 0 (por zona)',
        'ldagg|municipio': 'Votos de Lula terminados em 0 (por município)',
        'ldstate|flag': 'Testes de último dígito por UF reprovados após correção',
        'ldstate|p05': 'Testes de último dígito por UF com p < 0,05',
        'pz|pos': 'Seções muito acima do seu local de votação (z > 4), pró-Lula',
        'pz|neg': 'Seções muito abaixo do seu local de votação (z < −4), pró-Bolsonaro',
        corner: 'Seções com comparecimento ≥ 95% e Lula ≥ 90%',
        hiT: 'Comparecimento atipicamente alto (z > 4) pendendo para Lula',
        persist: 'Seções atípicas pró-Lula no 2º turno que já eram altas no 1º (z > 2)',
        'swing|pos': 'Seções que migraram bem mais para Lula que as vizinhas (> 4σ)',
        'swing|neg': 'Seções que migraram bem mais para Bolsonaro que as vizinhas (> 4σ)',
        'swing|dturn': 'Alta do comparecimento × migração para Lula, no mesmo local',
        time: '% de Lula nas seções que chegaram mais tarde, na mesma zona',
        urna: 'Maior diferença entre modelos de urna no mesmo local',
      };
      const VAR = { 'Right candidate': 'Bolsonaro', Turnout: 'Comparecimento', Blank: 'Brancos', Null: 'Nulos', 'Lula share': '% de Lula', All: 'Todos', Swing: 'Migração', Correlation: 'Correlação', Slope: 'Inclinação' };
      const dec = (v, n) => v.toFixed(n).replace('-', '−').replace('.', ',');
      const int = (v) => Math.round(v).toLocaleString('pt-BR');
      const num = (v, unit) => {
        if (v === null) return '—';
        if (unit === '%') return dec(v, 2) + '%';
        if (unit === 'ratio' || unit === 'r') return dec(v, 3);
        if (unit === 'pp') return dec(v, 2) + ' p.p.';
        if (unit === 'pp / hour') return (v >= 0 ? '+' : '') + dec(v, 2) + ' p.p./h';
        return int(v);
      };
      const stat = (v, name) => {
        if (v === null || name === null) return '';
        if (name.startsWith('p ')) return ' · p = ' + dec(v, 3);
        if (name === 'z') return ' · z = ' + dec(v, 2);
        if (name === 'robust sd') return ' · dp ' + dec(v, 2);
        if (name.startsWith('corr')) return ' · r = ' + dec(v, 2);
        if (name === 'skew') return ' · assimetria ' + dec(v, 2);
        if (name.startsWith('same corner')) return ' · Bolsonaro ' + int(v);
        if (name === 'outliers') return ' · ' + int(v) + ' atípicas';
        if (name === 'tests run') return ' · de ' + int(v) + ' testes';
        if (name === 'models') return ' · ' + int(v) + ' modelos';
        return ' · ' + int(v);
      };
      // Which candidate a row is about, for the page's candidate filter; the rest concern both.
      const CAND = { 'ld|Lula': 'lula', 'ld|Right candidate': 'flavio', 'heap|Lula': 'lula', 'heap|Right candidate': 'flavio', ldagg: 'lula', 'pz|pos': 'lula', 'pz|neg': 'flavio', persist: 'lula', 'swing|pos': 'lula', 'swing|neg': 'flavio' };
      const out = new Map();
      for (const r of scorecard) {
        const p = r.key.split('|');
        const t = out.get(r.key) ?? {
          key: r.key, section: r.section, test: TEST[p[0] + '|' + p[1]] ?? TEST[p[0]] ?? r.test,
          variable: VAR[r.variable] ?? r.variable,
          round: r.round === 1 ? '1º' : r.round === 2 ? '2º' : 'Ambos',
          cand: CAND[p[0] + '|' + p[1]] ?? CAND[p[0]] ?? 'ambos',
        };
        t['y' + r.year] = num(r.observed, r.unit) + stat(r.stat, r.stat_name);
        if (r.year === 2026) t.chance = r.expected === null ? '—' : num(r.expected, r.unit);
        out.set(r.key, t);
      }
      return [...out.values()];
    },
  });

  dash.calc('corner_summary', {
    inputs: ['corner'],
    title: 'Seções do quadro vermelho, em resumo',
    description: 'Para cada candidato: quantas seções do 2º turno tiveram comparecimento ≥ 95% e 90% ou mais dos votos para ele, seus eleitores aptos, quantas já lhe deram 90%+ no 1º turno e quantos locais têm nome de comunidade indígena ou rural.',
    fn: (corner) => ['lula', 'flavio'].map((candidate) => {
      const rows = corner.filter((r) => r.candidate === candidate);
      return {
        candidate,
        sections: rows.length,
        eligible: rows.reduce((s, r) => s + r.eligible, 0),
        strong_r1: rows.filter((r) => r.share_1 >= 0.9).length,
        community: rows.filter((r) => /IND[IÍ]GENA|ALDEIA|POVOADO|COMUNIDADE|QUILOMBO|FAZENDA|ASSENTAMENTO/.test(r.place)).length,
      };
    }),
  });

  dash.calc('corner_view', {
    inputs: ['corner'],
    title: 'Seções do quadro vermelho, com nome do candidato',
    description: 'As seções do quadro vermelho, com o nome do candidato que recebeu 90% ou mais dos votos.',
    fn: (corner) => corner.map((r) => ({ ...r, nome: r.candidate === 'lula' ? 'Lula' : 'Flávio' })),
  });

  dash.calc('stronghold_excess', {
    inputs: ['strongholds', 'summary'],
    title: 'Comparecimento a mais nos redutos de Lula',
    description: 'Votantes a mais nas seções com Lula ≥ 90% no 2º turno de 2026, em relação ao que o comparecimento dessas seções em 2022 daria, e essa quantidade como fração da margem de Lula.',
    fn: (strongholds, summary) => {
      const now = strongholds.find((r) => r.id === '2026|2|lula90');
      const then = strongholds.find((r) => r.id === '2022|2|lula90');
      const excess = now.voters - now.eligible * then.turnout;
      return [{ excess, share: excess / summary.find((r) => r.year === 2026 && r.round === 2).margin }];
    },
  });

  dash.calc('late_share', {
    inputs: ['timing'],
    title: 'Votos recebidos depois das 19h',
    description: 'Fração dos votos do 2º turno de 2026 cujos boletins chegaram ao TSE depois das 19h (horário de Brasília).',
    fn: (timing) => [{ share: 1 - timing.find((r) => r.year === 2026 && r.round === 2 && r.minutes === 120).pct_counted }],
  });

  dash.calc('states_view', {
    inputs: ['states'],
    title: 'UFs no 2º turno de 2026, os dois candidatos',
    description: 'Por UF em 2026: percentual de Lula e de Flávio no 2º turno (os dois somam 100% dos válidos) e a variação de cada um entre os turnos.',
    fn: (states) => states.filter((r) => r.year === 2026)
      .map((r) => ({ ...r, flavio_share_2: 1 - r.lula_share_2, flavio_swing_pp: -r.swing_pp })),
  });

  dash.calc('urna_view', {
    inputs: ['urna'],
    title: 'Modelos de urna no 2º turno de 2026, os dois candidatos',
    description: 'Por modelo de urna: percentual bruto de Lula e de Flávio no 2º turno de 2026 e a diferença frente a outras urnas do mesmo local, para cada um.',
    fn: (urna) => urna.filter((r) => r.year === 2026 && r.round === 2)
      .map((r) => ({ ...r, flavio_raw: 1 - r.raw_share, flavio_vs_place_pp: -r.vs_place_pp })),
  });

  dash.calc('swing_range', {
    inputs: ['states'],
    title: 'Faixa da migração por UF, 2026',
    description: 'Menor e maior variação do percentual de Lula entre os dois finalistas, do 1º para o 2º turno, nas 27 UFs e no exterior, 2026.',
    fn: (states) => {
      const s = states.filter((r) => r.year === 2026).map((r) => r.swing_pp);
      return [{ min: Math.min(...s), max: Math.max(...s) }];
    },
  });

  dash.calc('between_rounds', {
    inputs: ['summary'],
    title: 'Do 1º para o 2º turno, 2026',
    description: 'Votos de cada finalista, dos candidatos eliminados, brancos e nulos, abstenções e comparecimento em cada turno de 2026, e a variação líquida.',
    fn: (summary) => {
      const [a, b] = [1, 2].map((t) => summary.find((r) => r.year === 2026 && r.round === t));
      const row = (id, item, f) => ({ id, item, r1: f(a), r2: f(b), change: f(b) - f(a) });
      return [
        row('lula', 'Lula', (s) => s.lula),
        row('flavio', 'Flávio Bolsonaro', (s) => s.right),
        row('others', 'Candidatos eliminados', (s) => s.valid - s.lula - s.right),
        row('blank_null', 'Brancos e nulos', (s) => s.brancos + s.nulos),
        row('absent', 'Abstenções', (s) => s.aptos - s.comparecimento),
        row('turnout', 'Comparecimento', (s) => s.comparecimento),
      ];
    },
  });

  dash.calc('consistency_pt', {
    inputs: ['consistency'],
    title: 'Seções vs. totais oficiais, por campo',
    description: 'A conferência das seções contra os totais oficiais, com o nome de cada campo em português.',
    fn: (consistency) => {
      const name = { 'Eligible voters': 'Eleitores aptos', Turnout: 'Comparecimento', Abstentions: 'Abstenções', 'Blank votes': 'Votos brancos', 'Null votes': 'Votos nulos', 'Valid votes': 'Votos válidos' };
      return consistency.map((r) => ({ ...r, campo: name[r.field] ?? r.field, turnos: r.rounds.replace('+', ' e ') }));
    },
  });

  const enc = encodeURIComponent;
  const on = (fn) => dash.onData(fn);
  const ready = (tbl, id) => {
    const ok = dash.data(id).status === 'ok';
    if (!ok) (tbl.tBodies[0] ?? tbl.createTBody()).replaceChildren();
    return ok;
  };

  // Test tables, one per section of the page.
  for (const [id, sections] of [['tests-rn', ['Round numbers']], ['tests-dist', ['Distribution']], ['tests-other', ['Swing', 'Timing & machines']]]) {
    const tbl = document.getElementById(id);
    on(() => {
      if (!ready(tbl, 'tests')) return;
      const shown = vf.cands();
      vf.table(tbl, dash.data('tests').data.filter((r) => sections.includes(r.section) && (r.cand === 'ambos' || shown.includes(r.cand))), (r) => r.key);
    });
  }

  // Corner sections, searchable and sortable, for the candidates shown.
  const corner = document.getElementById('corner-table');
  const search = document.getElementById('corner-search');
  const drawCorner = () => {
    if (!ready(corner, 'corner_view')) return;
    const q = search.value.trim().toLowerCase();
    const shown = vf.cands();
    const rows = dash.data('corner_view').data
      .filter((r) => shown.includes(r.candidate) && (!q || `${r.nome} ${r.uf} ${r.municipality} ${r.place}`.toLowerCase().includes(q)));
    vf.table(corner, rows, (r) => r.section_id);
  };
  vf.sortable(corner, drawCorner, 'share_2');
  search.addEventListener('input', drawCorner);
  on(drawCorner);

  const between = document.getElementById('between-table');
  on(() => {
    if (!ready(between, 'between_rounds')) return;
    vf.table(between, dash.data('between_rounds').data, (r) => r.id);
  });

  const states = document.getElementById('states-table');
  const drawStates = () => {
    if (!ready(states, 'states_view')) return;
    vf.table(states, dash.data('states_view').data, (r) => `${enc(r.year)},${enc(r.uf)}`);
  };
  vf.sortable(states, drawStates, 'swing_pp');
  on(drawStates);

  const urna = document.getElementById('urna-table');
  on(() => {
    if (!ready(urna, 'urna_view')) return;
    vf.table(urna, dash.data('urna_view').data, (r) => r.id);
  });

  const cons = document.getElementById('cons-table');
  on(() => {
    if (!ready(cons, 'consistency_pt')) return;
    vf.table(cons, dash.data('consistency_pt').data, (r) => r.id);
  });
})();
