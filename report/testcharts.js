// Charts behind each "Ver gráfico" button of "Mais testes" and "Com 2018 também". Each is drawn when its
// panel opens (vf.draw with its box) and again on data or tab changes while open.
(() => {
  const MUTED = 'var(--cds-chart-muted)';
  const REF = 'var(--cds-chart-reference)';
  const FG = 'var(--color-fg)';
  const BAD = 'var(--color-bad)';
  const LULA = 'var(--vf-lula)';
  const RIGHT = 'var(--vf-flavio)';
  const tr = vf.t;
  const YEAR = { 2026: { color: FG, width: 2.25 }, 2022: { color: MUTED, width: 1.75 }, 2018: { color: REF, width: 1.75, dash: '2 3' } };
  const nf = vf.f(',.0f');
  const pct0 = vf.f('.0%');
  const pct1 = vf.f('.1%');
  const d1 = vf.f('.1f');
  const d3f = vf.f('.3f');
  const rows = (id) => dash.data(id).data;
  const row = (id, key) => rows(id).find((r) => r.id === key);
  const series = (chart, s) => rows('graficos').filter((r) => r.chart === chart && (s === undefined || r.series === s));

  // A frame: left axis, bottom axis, gridlines; returns the scales and the svg.
  function frame(cell, height, xDomain, yDomain, { yLog = false, yFmt = pct0, xFmt = (v) => v, xTicks = 5, yTicks = 4 } = {}) {
    const { s, w, h } = vf.svg(cell, height);
    const y0 = yLog ? d3.scaleLog(yDomain, [h - 24, 8]).clamp(true) : d3.scaleLinear(yDomain, [h - 24, 8]).nice();
    const ticks = yLog ? y0.ticks(yTicks).filter((v) => Number.isInteger(Math.log10(v))) : y0.ticks(yTicks);
    const ml = vf.textWidth(s, ticks.map(yFmt)) + 8;
    const x = d3.scaleLinear(xDomain, [ml, w - 10]);
    s.append('g').attr('transform', `translate(${ml},0)`)
      .call(d3.axisLeft(y0).tickValues(ticks).tickFormat(yFmt).tickSize(-(w - ml - 10))).call(vf.axis);
    s.append('g').attr('transform', `translate(0,${h - 24})`)
      .call(d3.axisBottom(x).ticks(Math.min(xTicks, Math.floor((w - ml) / 60))).tickFormat(xFmt).tickSize(0).tickPadding(8)).call(vf.axis);
    return { s, w, h, x, y: y0, ml };
  }
  const vline = (f, at, color, dash) => f.s.append('line').attr('x1', f.x(at)).attr('x2', f.x(at)).attr('y1', 8).attr('y2', f.h - 24)
    .style('stroke', color).attr('stroke-dasharray', dash ?? null);
  const path = (f, pts, st) => f.s.append('path').datum(pts).attr('d', d3.line().x((p) => f.x(p.x)).y((p) => f.y(p.y)))
    .style('fill', 'none').style('stroke', st.color).attr('stroke-width', st.width ?? 1.75)
    .attr('stroke-dasharray', st.dash ?? null).attr('stroke-linejoin', 'round');
  // a transparent layer that shows, for the point nearest the pointer, one value per series
  function hover(f, tip, xs, head, lines) {
    f.s.append('rect').attr('x', f.ml).attr('width', f.w - 10 - f.ml).attr('height', f.h).style('fill', 'transparent')
      .on('pointermove pointerdown', (ev) => {
        const at = f.x.invert(d3.pointer(ev)[0]);
        const x = xs.reduce((a, b) => (Math.abs(b - at) < Math.abs(a - at) ? b : a));
        tip.show(ev, head(x), lines(x));
      })
      .on('pointerleave', tip.leave);
  }
  function box(id, ...sources) {
    const el = document.getElementById(id);
    if (!el || !vf.gate(el, ...sources)) return null;
    el.replaceChildren();
    return el;
  }

  // Proportional swing: national slopes, and the 2026 − 2022 gap state by state --------------------
  const propBox = document.getElementById('prop-chart');
  vf.draw(function drawProp() {
    const el = box('prop-chart', 'more_tests', 'graficos');
    if (!el) return;
    const pl = row('more_tests', 'prop|planted');
    const nat = [
      { key: '2018', label: '2018', v: row('more_tests', 'prop|2018').slope, ...YEAR[2018] },
      { key: '2022', label: '2022', v: row('more_tests', 'prop|2022').slope, ...YEAR[2022] },
      { key: '2026', label: '2026', v: row('more_tests', 'prop|2026').slope, ...YEAR[2026] },
      { key: 'planted', label: tr('testcharts.prop.planted'), v: pl.slope, color: BAD, width: 1.75, dash: '5 4' },
    ].map((d) => ({ ...d, pts: series('prop_bins', d.key).sort((a, b) => a.x - b.x) }));
    const refs = [{ ref: '2022', title: tr('testcharts.prop.vs_ref', { ref: '2022' }), color: MUTED },
      { ref: '2018', title: tr('testcharts.prop.vs_ref', { ref: '2018' }), color: REF }];
    const gaps = refs.map((r) => series('prop_states', r.ref).sort((a, b) => a.y - b.y));
    const tip = vf.tooltip(el);
    const [c1, c2] = vf.panels(el, [tr('testcharts.prop.title_national'), tr('testcharts.prop.title_states')], 'vf-stack');
    // national: the sections in 20 equal groups by the right's round-1 edge over the rest of their polling
    // place; each line's slope is the test's number
    {
      const pp = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + d1(Math.abs(v * 100));
      vf.legend(c1, nat.map((d) => ({ label: tr('testcharts.prop.slope_legend', { label: d.label, slope: d3f(d.v) }), color: d.color, line: true, dash: d.dash })));
      const all = nat.flatMap((d) => d.pts);
      const f = frame(c1, 260, d3.extent(all, (p) => p.x), d3.extent(all, (p) => p.y), { yFmt: pp, xFmt: pp });
      f.s.append('line').attr('x1', f.x(0)).attr('x2', f.x(0)).attr('y1', 8).attr('y2', f.h - 24).style('stroke', REF);
      for (const d of nat) {
        path(f, d.pts, d);
        f.s.selectAll(null).data(d.pts).join('circle').attr('cx', (p) => f.x(p.x)).attr('cy', (p) => f.y(p.y))
          .attr('r', 2.5).style('fill', d.color);
      }
      f.s.append('text').attr('class', 'vf-tick').attr('x', f.w - 10).attr('y', f.h - 30).attr('text-anchor', 'end')
        .style('fill', 'var(--color-fg)').text(tr('testcharts.prop.x_axis'));
      f.s.append('text').attr('class', 'vf-tick').attr('x', f.ml + 6).attr('y', 14)
        .style('fill', 'var(--color-fg)').text(tr('testcharts.prop.y_axis'));
      const ref = nat.find((d) => d.key === '2026').pts;
      f.s.append('rect').attr('x', f.ml).attr('width', f.w - 10 - f.ml).attr('height', f.h).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const at = f.x.invert(d3.pointer(ev)[0]);
          const i = d3.minIndex(ref, (p) => Math.abs(p.x - at));
          tip.show(ev, tr('testcharts.prop.tip_head', { n: i + 1 }),
            nat.map((d) => ({ label: d.label, value: tr('testcharts.prop.tip_value', { right: pp(d.pts[i].x), pt: pp(d.pts[i].y) }) })));
        })
        .on('pointerleave', tip.leave);
    }
    // states: one strip per reference, one dot per state, stacked where they would overlap; the planted
    // program adds pl.added in every state
    {
      const all = gaps.flat();
      const lo = Math.min(d3.min(all, (d) => d.y), 0);
      const hi = Math.max(d3.max(all, (d) => d.y), pl.added);
      const strip = 64;
      const { s, w } = vf.svg(c2, 30 + strip * refs.length);
      const ml = vf.textWidth(s, refs.map((r) => r.title)) + 12;
      const x = d3.scaleLinear([lo, hi], [ml, w - 12]).nice();
      const yb = (k) => 20 + strip * (k + 1) - 10;
      s.append('g').attr('transform', `translate(0,${yb(refs.length - 1) + 8})`)
        .call(d3.axisBottom(x).ticks(5).tickFormat((v) => (v > 0 ? '+' : '') + d3f(v)).tickSize(0).tickPadding(8)).call(vf.axis);
      s.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 14).attr('y2', yb(refs.length - 1)).style('stroke', REF);
      s.append('line').attr('x1', x(pl.added)).attr('x2', x(pl.added)).attr('y1', 14).attr('y2', yb(refs.length - 1)).style('stroke', BAD).attr('stroke-dasharray', '5 4');
      s.append('text').attr('class', 'vf-tick').attr('x', x(pl.added) - 4).attr('y', 8).attr('text-anchor', 'end')
        .style('fill', 'var(--color-fg)').text(tr('testcharts.prop.program_adds'));
      const r = 4.5;
      refs.forEach((ref, k) => {
        s.append('text').attr('class', 'vf-tick').attr('x', 0).attr('y', yb(k) - 4).style('fill', 'var(--color-fg)').text(ref.title);
        const placed = [];
        for (const d of gaps[k]) {
          let n = 0;
          while (placed.some((p) => p.n === n && Math.abs(p.cx - x(d.y)) < 2 * r + 1)) n += 1;
          placed.push({ n, cx: x(d.y), d });
        }
        for (const p of placed) {
          s.append('circle').attr('cx', p.cx).attr('cy', yb(k) - 4 - p.n * (2 * r + 1)).attr('r', r).style('fill', k ? REF : FG)
            .on('pointermove pointerdown', (ev) => tip.show(ev, p.d.uf, [{ label: tr('testcharts.prop.gap_label', { ref: ref.ref }), value: (p.d.y > 0 ? '+' : '') + d3f(p.d.y) }]))
            .on('pointerleave', tip.leave);
        }
      });
    }
  }, propBox);

  // Chi-squared per polling place: distribution of the p-values ------------------------------------
  const homogBox = document.getElementById('homog-chart');
  vf.draw(function drawHomog() {
    const el = box('homog-chart', 'graficos');
    if (!el) return;
    const yrs = ['2026', '2022', '2018'];
    const data = yrs.map((y) => series('homog_p', y));
    const tip = vf.tooltip(el);
    const f = frame(el, 220, [0, 1], [0, d3.max(data.flat(), (d) => d.y)], { xFmt: (v) => vf.f('.1f')(v) });
    const bw = (f.x(0.05) - f.x(0)) / yrs.length - 0.5;
    yrs.forEach((y, k) => {
      for (const d of data[k]) {
        f.s.append('rect').attr('x', f.x(d.x) + 1 + k * bw).attr('width', bw).attr('y', f.y(d.y)).attr('height', f.y(0) - f.y(d.y))
          .style('fill', YEAR[y].color);
      }
    });
    f.s.append('line').attr('x1', f.x(0)).attr('x2', f.x(1)).attr('y1', f.y(0.05)).attr('y2', f.y(0.05)).style('stroke', BAD).attr('stroke-dasharray', '5 4');
    hover(f, tip, data[0].map((d) => d.x + 0.025), (v) => tr('testcharts.homog.tip_head', { from: vf.f('.2f')(v - 0.025), to: vf.f('.2f')(v + 0.025) }),
      (v) => yrs.map((y, k) => ({ label: y, value: pct1(data[k].find((d) => Math.abs(d.x + 0.025 - v) < 1e-9).y), color: YEAR[y].color })));
    vf.legend(el, [...yrs.map((y) => ({ label: y, color: YEAR[y].color })), { label: tr('testcharts.homog.legend_chance'), color: BAD, line: true, dash: '5 4' }]);
  }, homogBox);

  // Shpilkin: Lula's share by turnout band, the flat line the method assumes, and votes per band -------
  const shpBox = document.getElementById('shp-chart');
  vf.draw(function drawShp() {
    const el = box('shp-chart', 'graficos');
    if (!el) return;
    const yrs = ['2026', '2022', '2018'];
    // bands with at least 0.05% of the votes: the thin tails swing wildly and carry almost no votes
    const data = yrs.map((y) => series('shpilkin', y).filter((d) => d.y >= 0.0005));
    const peaks = yrs.map((y) => series('shpilkin_peak', y)[0]);
    const tip = vf.tooltip(el);
    const [c1, c2] = vf.panels(el, [tr('testcharts.shp.title_share'), tr('testcharts.shp.title_votes')], 'vf-stack');
    const xd = d3.extent(data.flat(), (d) => d.x);
    const f1 = frame(c1, 200, xd, d3.extent(data.flat(), (d) => d.lula), { xFmt: pct0 });
    yrs.forEach((y, k) => {
      path(f1, data[k].map((d) => ({ x: d.x, y: d.lula })), YEAR[y]);
      const p = peaks[k];
      f1.s.append('line').attr('x1', f1.x(p.x)).attr('x2', f1.x(xd[1])).attr('y1', f1.y(p.lula)).attr('y2', f1.y(p.lula))
        .style('stroke', YEAR[y].color).attr('stroke-dasharray', '5 4');
      f1.s.append('circle').attr('cx', f1.x(p.x)).attr('cy', f1.y(p.lula)).attr('r', 4).style('fill', YEAR[y].color);
    });
    const f2 = frame(c2, 120, xd, [0, d3.max(data.flat(), (d) => d.y)], { xFmt: pct0, yFmt: vf.f('.1%'), yTicks: 2 });
    yrs.forEach((y, k) => path(f2, data[k].map((d) => ({ x: d.x, y: d.y })), YEAR[y]));
    const xs = data[0].map((d) => d.x);
    const lines = (v) => yrs.map((y, k) => {
      const d = data[k].find((e) => Math.abs(e.x - v) < 1e-9);
      return { label: y, value: d ? tr('testcharts.shp.tip_value', { pt: pct1(d.lula), votes: pct1(d.y) }) : '—',
        color: YEAR[y].color, line: true, dash: YEAR[y].dash };
    });
    for (const f of [f1, f2]) hover(f, tip, xs, (v) => tr('testcharts.shp.tip_head', { from: pct1(v), to: pct1(v + 0.005) }), lines);
    vf.legend(el, [...yrs.map((y) => ({ label: y, color: YEAR[y].color, line: true, dash: YEAR[y].dash })),
      { label: tr('testcharts.shp.legend_flat'), color: FG, line: true, dash: '5 4' }]);
  }, shpBox);

  // Second digit: frequency per digit, 2026 bars, 2022 line, Benford dashed ---------------------------
  const benBox = document.getElementById('benford-chart');
  vf.draw(function drawBenford() {
    const el = box('benford-chart', 'graficos');
    if (!el) return;
    const exp = series('benford2', 'expected');
    const tip = vf.tooltip(el);
    const cands = [{ key: 'lula', title: tr('testcharts.benford.title_pt'), color: LULA },
      { key: 'right', title: tr('testcharts.benford.title_right'), color: RIGHT }];
    const cells = vf.panels(el, cands.map((c) => c.title));
    const all = rows('graficos').filter((r) => r.chart === 'benford2');
    const top = d3.max(all, (d) => d.y) * 1.1;
    cands.forEach((c, i) => {
      const r26 = all.filter((d) => d.series === '2026' && d.cand === c.key);
      const r22 = all.filter((d) => d.series === '2022' && d.cand === c.key);
      const r18 = all.filter((d) => d.series === '2018' && d.cand === c.key);
      const f = frame(cells[i], 190, [-0.5, 9.5], [0, top], { xFmt: (v) => v, xTicks: 10 });
      const bw = (f.x(1) - f.x(0)) * 0.7;
      for (const d of r26) {
        f.s.append('rect').attr('x', f.x(d.x) - bw / 2).attr('width', bw).attr('y', f.y(d.y)).attr('height', f.y(0) - f.y(d.y)).style('fill', c.color);
      }
      path(f, r22.map((d) => ({ x: d.x, y: d.y })), { color: MUTED, width: 2 });
      path(f, r18.map((d) => ({ x: d.x, y: d.y })), { color: REF, width: 1.75, dash: '2 3' });
      path(f, exp.map((d) => ({ x: d.x, y: d.y })), { color: FG, width: 1.5, dash: '5 4' });
      hover(f, tip, d3.range(10), (v) => tr('testcharts.benford.tip_head', { digit: v }), (v) => [
        { label: '2026', value: pct1(r26[v].y), color: c.color },
        { label: '2022', value: pct1(r22[v].y), color: MUTED, line: true },
        { label: '2018', value: pct1(r18[v].y), color: REF, line: true, dash: '2 3' },
        { label: tr('testcharts.benford.tip_benford'), value: pct1(exp[v].y), color: FG, line: true, dash: '5 4' },
      ]);
    });
    vf.legend(el, [{ label: tr('testcharts.benford.legend_2026'), color: FG }, { label: '2022', color: MUTED, line: true },
      { label: '2018', color: REF, line: true, dash: '2 3' }, { label: tr('testcharts.benford.legend_law'), color: FG, line: true, dash: '5 4' }]);
  }, benBox);

  // Horizontal grouped bars, shared by the mixture and the reference-tests charts --------------------
  function hbars(cell, groups, keys, { fmt = nf, height } = {}) {
    const tip = vf.tooltip(cell);
    const { s, w, h } = vf.svg(cell, height ?? 26 + groups.length * (keys.length * 16 + 14));
    const ml = vf.textWidth(s, groups.map((g) => g.label)) + 12;
    const top = d3.max(groups.flatMap((g) => keys.map((k) => g[k.key] ?? 0)));
    const x = d3.scaleLinear([0, top || 1], [ml, w - 10 - vf.textWidth(s, [fmt(top)]) - 8]);
    const band = d3.scaleBand(groups.map((g) => g.label), [4, h - 4]).paddingInner(0.25);
    const sub = d3.scaleBand(keys.map((k) => k.key), [0, band.bandwidth()]).padding(0.1);
    s.append('g').attr('transform', `translate(${ml - 6},0)`).call(d3.axisLeft(band).tickSize(0)).call(vf.axis);
    for (const g of groups) {
      for (const k of keys) {
        const v = g[k.key];
        if (v === undefined || v === null) continue;
        const y = band(g.label) + sub(k.key);
        s.append('rect').attr('x', x(0)).attr('y', y).attr('width', Math.max(1, x(v) - x(0))).attr('height', sub.bandwidth())
          .attr('rx', 2).style('fill', g.color ?? k.color);
        s.append('text').attr('class', 'vf-tick').attr('x', x(v) + 5).attr('y', y + sub.bandwidth() / 2).attr('dy', '0.35em')
          .style('fill', 'var(--color-fg)').text(fmt(v));
      }
      s.append('rect').attr('x', ml).attr('y', band(g.label)).attr('width', w - 10 - ml).attr('height', band.bandwidth())
        .style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => tip.show(ev, g.label, keys.filter((k) => g[k.key] != null)
          .map((k) => ({ label: k.label, value: fmt(g[k.key]), color: k.color }))))
        .on('pointerleave', tip.leave);
    }
  }

  // Mixture model: planted vs. estimated extreme-fraud sections ---------------------------------------
  const mixBox = document.getElementById('mix-chart');
  vf.draw(function drawMix() {
    const el = box('mix-chart', 'more_tests');
    if (!el) return;
    const groups = [
      ...['2026', '2022', '2018'].map((y) => ({ label: tr('testcharts.mix.real', { year: y }), planted: 0,
        found: row('more_tests', `mixture|${y}`).sections_extreme })),
      ...[92, 250, 1000].map((n) => ({ label: tr('testcharts.mix.planted_label', { n: nf(n) }), planted: n,
        found: row('more_tests', `mixture|planted|${n}|2026`).found_sections })),
    ];
    const keys = [{ key: 'planted', label: tr('testcharts.mix.key_planted'), color: BAD },
      { key: 'found', label: tr('testcharts.mix.key_found'), color: FG }];
    hbars(el, groups, keys);
    vf.legend(el, keys.map((k) => ({ label: k.label, color: k.color })));
  }, mixBox);

  // Vote bursts in the machine logs: fast votes and poll-worker releases by group ---------------------
  const burstsBox = document.getElementById('bursts-chart');
  vf.draw(function drawBursts() {
    const el = box('bursts-chart', 'more_tests');
    if (!el) return;
    const G = [['corner_lula', 'testcharts.bursts.corner_lula'], ['lula90', 'testcharts.bursts.lula90'], ['right90', 'testcharts.bursts.right90'],
      ['corner_right', 'testcharts.bursts.corner_right'], ['random', 'testcharts.bursts.random']];
    const groups = G.map(([k, key]) => {
      const r = row('more_tests', `bursts|${k}|2`);
      return r && { label: tr(key, { n: nf(r.machines) }), fast: r.fast_gap_share, worker: r.poll_worker_share };
    }).filter(Boolean);
    const mixed = row('more_tests', 'bursts|planted|mixed');
    const cells = vf.panels(el, [tr('testcharts.bursts.title_fast'), tr('testcharts.bursts.title_worker')]);
    hbars(cells[0], groups, [{ key: 'fast', label: tr('testcharts.bursts.key_fast'), color: FG }], { fmt: pct1 });
    hbars(cells[1], [...groups, { label: tr('testcharts.bursts.planted'), worker: mixed.poll_worker_share, color: BAD }],
      [{ key: 'worker', label: tr('testcharts.bursts.key_worker'), color: FG }], { fmt: pct1 });
  }, burstsBox);

  // Questions 3 and 4 with 2018 ----------------------------------------------------------------------
  const refBox = document.getElementById('ref-chart');
  vf.draw(function drawRef() {
    const el = box('ref-chart', 'tres_eleicoes');
    if (!el) return;
    const who = { 2026: ['Lula', 'Flávio'], 2022: ['Lula', 'Jair'], 2018: ['Haddad', 'Jair'] };
    const yrs = [2026, 2022, 2018];
    const cells = vf.panels(el, [tr('testcharts.ref.title_corner'), tr('testcharts.ref.title_place')]);
    const keys = [{ key: 'pt', label: tr('testcharts.ref.key_pt'), color: LULA }, { key: 'right', label: tr('testcharts.ref.key_right'), color: RIGHT }];
    hbars(cells[0], yrs.map((y) => { const r = row('tres_eleicoes', `ref|${y}`); return { label: `${y} (${who[y].join(' × ')})`, pt: r.corner_lula, right: r.corner_right }; }), keys);
    hbars(cells[1], yrs.map((y) => { const r = row('tres_eleicoes', `ref|${y}`); return { label: `${y} (${who[y].join(' × ')})`, pt: r.place_pos4, right: r.place_neg4 }; }), keys);
    vf.legend(el, keys.map((k) => ({ label: k.label, color: k.color })));
  }, refBox);

  // Concentration: sections with 90% or more for each side, and the PT share per section, three years -----
  // Party colors throughout: red the PT candidate, blue the opponent; years as line styles.
  const concBox = document.getElementById('conc-chart');
  vf.draw(function drawConc() {
    const el = box('conc-chart', 'graficos', 'tres_eleicoes');
    if (!el) return;
    const yrs = ['2026', '2022', '2018'];
    const won = { 2026: 'Lula', 2022: 'Lula', 2018: 'Jair' };
    const [c1, c2] = vf.panels(el, [tr('testcharts.conc.title_90'), tr('testcharts.conc.title_hist')], 'vf-stack');
    const keys = [{ key: 'pt', label: tr('testcharts.conc.key_pt'), color: LULA }, { key: 'right', label: tr('testcharts.conc.key_right'), color: RIGHT }];
    hbars(c1, yrs.map((y) => {
      const r = row('tres_eleicoes', `conc|${y}|2`);
      return { label: tr('testcharts.conc.year_label', { year: y, who: won[y] }), pt: r.lula_90, right: r.right_90 };
    }), keys);
    const data = yrs.map((y) => series('conc_hist', y).map((d) => ({ x: d.x + 0.01, y: d.y })));
    const tip = vf.tooltip(c2);
    const f = frame(c2, 230, [0, 1], [0, d3.max(data.flat(), (d) => d.y)], { xFmt: pct0, yFmt: vf.f('.0%') });
    // each side's strongholds, shaded in its color: the opponent's at the left (PT 10% or less), the PT's at the right
    for (const [x0, x1, color] of [[0, 0.1, RIGHT], [0.9, 1, LULA]]) {
      f.s.insert('rect', ':first-child').attr('x', f.x(x0)).attr('width', f.x(x1) - f.x(x0)).attr('y', 8).attr('height', f.h - 32)
        .style('fill', color).style('opacity', 0.16);
    }
    yrs.forEach((y, k) => path(f, data[k], YEAR[y]));
    hover(f, tip, data[0].map((d) => d.x), (v) => tr('testcharts.conc.tip_head', { from: pct0(v - 0.01), to: pct0(v + 0.01) }),
      (v) => yrs.map((y, k) => ({ label: y, value: tr('testcharts.conc.tip_value', { pct: pct1(data[k].find((d) => Math.abs(d.x - v) < 1e-9).y) }),
        color: YEAR[y].color, line: true, dash: YEAR[y].dash })));
    vf.legend(el, [...keys.map((k) => ({ label: k.label, color: k.color })),
      ...yrs.map((y) => ({ label: y, color: YEAR[y].color, line: true, dash: YEAR[y].dash }))]);
  }, concBox);

  // Expected x observed: municipalities by distance from the prediction ---------------------------------
  const expBox = document.getElementById('exp-chart');
  vf.draw(function drawExp() {
    const el = box('exp-chart', 'graficos', 'tres_eleicoes');
    if (!el) return;
    const ss = [['2026', YEAR[2026]], ['2022', YEAR[2022]], ['2018', YEAR[2018]], ['planted', { color: BAD, width: 1.75, dash: '5 4' }]];
    const data = ss.map(([k]) => series('exp_mun', k).map((d) => ({ x: d.x + 0.125, y: d.y })));
    const tip = vf.tooltip(el);
    const sd = row('tres_eleicoes', 'exp|2026').mun_robust_sd_pp;
    const f = frame(el, 240, [-8, 8], [0.8, d3.max(data.flat(), (d) => d.y) * 1.4],
      { yLog: true, yFmt: nf, xFmt: (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}` });
    for (const at of [-4 * sd, 4 * sd]) vline(f, at, REF, '4 3');
    ss.forEach(([, st], k) => path(f, data[k].filter((d) => d.x >= -8 && d.x <= 8).map((d) => ({ x: d.x, y: Math.max(d.y, 0.8) })), st));
    const label = { 2026: '2026', 2022: '2022', 2018: '2018', planted: tr('testcharts.exp.planted') };
    hover(f, tip, data[0].filter((d) => d.x >= -8 && d.x <= 8).map((d) => d.x),
      (v) => tr('testcharts.exp.tip_head', { from: vf.f('.2f')(v - 0.125), to: vf.f('.2f')(v + 0.125) }),
      (v) => ss.map(([k, st], i) => ({ label: label[k], value: tr('testcharts.exp.tip_value', { n: nf(data[i].find((d) => Math.abs(d.x - v) < 1e-9).y) }),
        color: st.color, line: true, dash: st.dash })));
    vf.legend(el, [...ss.map(([k, st]) => ({ label: label[k], color: st.color, line: true, dash: st.dash })),
      { label: tr('testcharts.exp.legend_sd'), color: REF, line: true, dash: '4 3' }]);
  }, expBox);

  // Isolation Forest: share of sections scoring above each value, per year and for the planted sections ---
  // (a survival curve: it reads off, at the cut, the share flagged; the planted sets are too small for a histogram)
  const isoBox = document.getElementById('iso-chart');
  vf.draw(function drawIso() {
    const el = box('iso-chart', 'graficos', 'tres_eleicoes');
    if (!el) return;
    const ss = [['2026', YEAR[2026], '2026'], ['2022', YEAR[2022], '2022'], ['2018', YEAR[2018], '2018'],
      ['planted_extreme', { color: BAD, width: 1.75, dash: '5 4' }, tr('testcharts.iso.planted_extreme')],
      ['planted_incremental', { color: BAD, width: 1.25, dash: '2 3' }, tr('testcharts.iso.planted_incremental')]];
    const lo = 1e-5;
    const data = ss.map(([k]) => {
      const h = series('iso_score', k);
      let acc = 0;
      // share at or above the left edge of each bin
      return h.slice().reverse().map((d) => ({ x: d.x, y: (acc += d.y) })).reverse();
    });
    const tip = vf.tooltip(el);
    const cut = row('tres_eleicoes', 'meta').cut;
    const f = frame(el, 240, [0.4, 0.75], [lo, 1], { yLog: true, yFmt: (v) => vf.f('~%')(v), xFmt: vf.f('.2f') });
    vline(f, cut, FG, '4 3');
    ss.forEach(([, st], k) => path(f, data[k].filter((d) => d.x >= 0.4 && d.x <= 0.75).map((d) => ({ x: d.x, y: Math.max(d.y, lo) })), st));
    hover(f, tip, data[0].filter((d) => d.x >= 0.4 && d.x <= 0.75).map((d) => d.x), (v) => tr('testcharts.iso.tip_head', { score: vf.f('.3f')(v) }),
      (v) => ss.map(([, st, label], i) => ({ label, value: pct1(data[i].find((d) => Math.abs(d.x - v) < 1e-9).y), color: st.color, line: true, dash: st.dash })));
    vf.legend(el, [...ss.map(([, st, label]) => ({ label, color: st.color, line: true, dash: st.dash })), { label: tr('testcharts.iso.legend_cut'), color: FG, line: true, dash: '4 3' }]);
  }, isoBox);
})();
