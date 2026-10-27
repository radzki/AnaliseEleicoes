// The plain-language tab: its calculations and its four simple charts. Loads last, then starts the tabs.
(() => {
  const MUTED = 'var(--cds-chart-muted)';
  const REF = 'var(--cds-chart-reference)';
  const pct0 = vf.f('.0%');
  const pct1 = vf.f('.1%');
  const nf = vf.f(',');
  const compact = (v) => vf.format('signedCompact', v);

  dash.calc('digit_range', {
    inputs: ['last_digit'],
    title: 'Faixa do último dígito, 2026',
    description: 'Menor e maior fração de urnas cujos votos terminam num mesmo dígito, para Lula e Flávio no 2º turno de 2026.',
    fn: (last_digit) => {
      const s = last_digit.filter((r) => r.year === 2026 && r.round === 2 && r.variable !== 'Turnout').map((r) => r.share);
      return [{ min: Math.min(...s), max: Math.max(...s) }];
    },
  });

  dash.calc('corner_vs_margin', {
    inputs: ['corner', 'summary'],
    title: 'Urnas do quadro vermelho frente à margem',
    description: 'Eleitores aptos nas urnas com comparecimento ≥ 95% e Lula ≥ 90%, como fração da margem de Lula no 2º turno de 2026.',
    fn: (corner, summary) => {
      const margin = summary.find((r) => r.year === 2026 && r.round === 2).margin;
      const eligible = corner.filter((r) => r.candidate === 'lula').reduce((s, r) => s + r.eligible, 0);
      return [{ eligible, margin, share: eligible / margin }];
    },
  });

  // 1. Last digit, as plain bars from zero: every digit near 1 in 10 ------------------
  const dBox = document.getElementById('s-digits');
  vf.draw(() => {
    if (!vf.gate(dBox, 'last_digit')) return;
    const rows = dash.data('last_digit').data.filter((r) => r.year === 2026 && r.round === 2);
    dBox.replaceChildren();
    const tip = vf.tooltip(dBox);
    const shown = vf.cands();
    const cells = vf.panels(dBox, shown.map((c) => `Votos de ${vf.cand[c].name}`));
    shown.forEach((c, i) => {
      const v = c === 'lula' ? 'Lula' : 'Right candidate';
      const { s, w, h } = vf.svg(cells[i], 180);
      const y = d3.scaleLinear([0, 0.12], [h - 24, 10]);
      const ml = vf.textWidth(s, ['12%']) + 8;
      const x = d3.scaleBand(d3.range(10), [ml, w - 4]).padding(0.25);
      s.append('g').attr('transform', `translate(${ml},0)`)
        .call(d3.axisLeft(y).tickValues([0, 0.05, 0.1]).tickFormat(pct0).tickSize(-(w - ml - 4))).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).tickSize(0).tickPadding(8)).call(vf.axis);
      const bars = rows.filter((r) => r.variable === v);
      s.append('g').selectAll('rect').data(bars).join('rect')
        .attr('x', (r) => x(r.digit)).attr('width', x.bandwidth())
        .attr('y', (r) => y(r.share)).attr('height', (r) => y(0) - y(r.share)).attr('rx', 3)
        .style('fill', vf.cand[c].color())
        .on('pointermove pointerdown', (ev, r) => tip.show(ev, `Votos terminados em ${r.digit}`, [{ label: '', value: `${pct1(r.share)} das urnas` }]))
        .on('pointerleave', tip.leave);
      s.append('line').attr('x1', ml).attr('x2', w - 4).attr('y1', y(0.1)).attr('y2', y(0.1))
        .style('stroke', REF).attr('stroke-dasharray', '4 3');
      s.append('text').attr('class', 'vf-tick').attr('x', w - 4).attr('y', y(0.1) - 6).attr('text-anchor', 'end').text('1 em cada 10');
    });
  });

  // 2. Sections far from their neighbours, 2026 vs 2022 -------------------------------
  const oBox = document.getElementById('s-outliers');
  vf.draw(() => {
    if (!vf.gate(oBox, 'scorecard')) return;
    const sc = dash.data('scorecard').data;
    const val = (id) => sc.find((r) => r.id === id).observed;
    const groups = vf.cands().map((c) => ({
      label: c === 'lula' ? 'A favor de Lula' : 'A favor de Flávio (em 2022, Jair)',
      key: c === 'lula' ? 'pz|pos|2' : 'pz|neg|2', color: vf.cand[c].color(),
    }));
    const bars = groups.flatMap((g) => [2026, 2022].map((year) => ({ g: g.label, year, n: val(`${g.key}|${year}`) })));
    oBox.replaceChildren();
    // Each group: its label on a line of its own, then a bar for 2026 and one for 2022.
    const { s, w } = vf.svg(oBox, groups.length * 84);
    const valueW = vf.textWidth(s, bars.map((b) => `${nf(b.n)} em ${b.year}`)) + 8;
    const x = d3.scaleLinear([0, d3.max(bars, (b) => b.n)], [0, w - valueW]);
    groups.forEach((g, gi) => {
      const top = gi * 84;
      s.append('text').attr('class', 'vf-tick vf-strong').attr('x', 0).attr('y', top + 9).attr('dy', '0.32em').text(g.label);
      [2026, 2022].forEach((year, i) => {
        const b = bars.find((d) => d.g === g.label && d.year === year);
        const y0 = top + 22 + i * 26;
        s.append('rect').attr('x', 0).attr('y', y0).attr('height', 20).attr('rx', 4)
          .attr('width', Math.max(2, x(b.n))).style('fill', year === 2026 ? g.color : MUTED);
        s.append('text').attr('class', 'vf-tick').attr('x', x(b.n) + 6).attr('y', y0 + 10).attr('dy', '0.32em').text(`${nf(b.n)} em ${year}`);
      });
    });
  });

  // 3. The count through the night, runoffs only --------------------------------------
  vf.draw(() => vf.timingChart(document.getElementById('s-progress'), ['2022|2', '2026|2']));

  // 4. Net change between rounds, as bars either side of zero -------------------------
  const bBox = document.getElementById('s-balance');
  vf.draw(() => {
    if (!vf.gate(bBox, 'between_rounds')) return;
    const order = ['lula', 'flavio', 'others', 'absent', 'blank_null'];
    const label = { lula: 'Lula', flavio: 'Flávio', others: 'Candidatos que saíram', absent: 'Abstenções', blank_null: 'Brancos e nulos' };
    const rows = order.map((id) => dash.data('between_rounds').data.find((r) => r.id === id));
    bBox.replaceChildren();
    // Narrow (a phone): each label goes on its own line above its bar instead of to the left.
    const narrow = bBox.clientWidth < 480;
    const rowH = narrow ? 52 : 34;
    const { s, w } = vf.svg(bBox, rows.length * rowH + 10);
    const ml = narrow ? 0 : vf.textWidth(s, Object.values(label)) + 12;
    const vw = vf.textWidth(s, rows.map((r) => compact(r.change))) + 8;
    const x = d3.scaleLinear(d3.extent([0, ...rows.map((r) => r.change)]), [ml + vw, w - vw]);
    rows.forEach((r, i) => {
      const y0 = 6 + i * rowH + (narrow ? 20 : 0);
      const color = r.id === 'lula' ? dash.colors[0] : r.id === 'flavio' ? dash.colors[1] : MUTED;
      s.append('text').attr('class', 'vf-tick vf-strong').attr('x', 0).attr('y', narrow ? y0 - 10 : y0 + 11).attr('dy', '0.32em').text(label[r.id]);
      s.append('rect').attr('x', Math.min(x(0), x(r.change))).attr('y', y0).attr('height', 22).attr('rx', 4)
        .attr('width', Math.max(2, Math.abs(x(r.change) - x(0)))).style('fill', color);
      const right = r.change >= 0;
      s.append('text').attr('class', 'vf-tick').attr('x', x(r.change) + (right ? 6 : -6)).attr('y', y0 + 11).attr('dy', '0.32em')
        .attr('text-anchor', right ? 'start' : 'end').text(compact(r.change));
    });
    s.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', narrow ? 20 : 0).attr('y2', rows.length * rowH + 4).style('stroke', 'var(--cds-chart-axis)');
  });

  vf.tabs();
})();
