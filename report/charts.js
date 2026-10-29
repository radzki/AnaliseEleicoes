// Charts: last digits, whole-percentage spikes, section-vs-place z-scores, fingerprint, count progression.
// In the runoff valid votes are Lula + Flávio only, so Flávio's share is exactly 1 − Lula's: his share-based
// panels mirror Lula's rows (a share bin [p, p+w) becomes (100−p−w, 100−p], a z bin [z, z+w) becomes (−z−w, −z]).
(() => {
  const MUTED = 'var(--cds-chart-muted)';
  const REF = 'var(--cds-chart-reference)';
  const FG = 'var(--color-fg)';
  const tr = vf.t;
  const pct0 = vf.f('.0%');
  const pct1 = vf.f('.1%');
  const pct2 = vf.f('.2%');
  const nf = vf.f(',');
  const d1 = vf.f('.1f');

  // 1. Last digit of each section's count, runoff, 2026 beside 2022 ------------------
  const ldBox = document.getElementById('ld-chart');
  function drawLastDigits() {
    if (!vf.gate(ldBox, 'last_digit')) return;
    const rows = dash.data('last_digit').data.filter((r) => r.round === 2);
    const half = Math.max(0.004, d3.max(rows, (r) => Math.abs(r.share - 0.1)) * 1.25);
    const shown = [
      ...vf.cands().map((c) => ({ v: c === 'lula' ? 'Lula' : 'Right candidate',
        title: c === 'lula' ? tr('charts.ld.lula_title') : tr('charts.ld.right_title'), color: vf.cand[c].color() })),
      { v: 'Turnout', title: tr('charts.ld.turnout_title'), color: FG },
    ];
    ldBox.replaceChildren();
    const tip = vf.tooltip(ldBox);
    const cells = vf.panels(ldBox, shown.map((p) => p.title), 'vf-multiples');
    shown.forEach(({ v, title, color }, i) => {
      const pick = (year, digit) => rows.find((r) => r.variable === v && r.year === year && r.digit === digit);
      const cell = cells[i];
      const { s, w, h } = vf.svg(cell, 170);
      const y = d3.scaleLinear([0.1 - half, 0.1 + half], [h - 22, 8]);
      const ticks = y.ticks(4);
      const ml = vf.textWidth(s, ticks.map(pct1)) + 8;
      const x = d3.scaleBand(d3.range(10), [ml, w - 4]).padding(0.15);
      s.append('g').attr('transform', `translate(${ml},0)`)
        .call(d3.axisLeft(y).tickValues(ticks).tickFormat(pct1).tickSize(-(w - ml - 4))).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 22})`)
        .call(d3.axisBottom(x).tickSize(0).tickPadding(8)).call(vf.axis);
      // Range chance alone gives 95% of the time for one digit's share over n sections.
      const se = 1.96 * Math.sqrt(0.09 / pick(2026, 0).n);
      s.append('rect').attr('x', ml).attr('width', w - 4 - ml)
        .attr('y', y(0.1 + se)).attr('height', y(0.1 - se) - y(0.1 + se)).style('fill', 'var(--cds-chart-grid)');
      s.append('line').attr('x1', ml).attr('x2', w - 4).attr('y1', y(0.1)).attr('y2', y(0.1))
        .style('stroke', REF).attr('stroke-dasharray', '4 3');
      for (const [year, c, dx] of [[2022, MUTED, 0.32], [2026, color, 0.68]]) {
        s.append('g').selectAll('circle').data(rows.filter((r) => r.variable === v && r.year === year)).join('circle')
          .attr('cx', (d) => x(d.digit) + x.bandwidth() * dx).attr('cy', (d) => y(d.share)).attr('r', 3.5).style('fill', c);
      }
      s.append('g').selectAll('rect').data(d3.range(10)).join('rect')
        .attr('x', (d) => x(d)).attr('width', x.bandwidth()).attr('y', 0).attr('height', h).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev, d) => tip.show(ev, tr('charts.ld.tip_head', { title, digit: d }), [
          { label: '2026', value: pct2(pick(2026, d).share), color },
          { label: '2022', value: pct2(pick(2022, d).share), color: MUTED },
        ]))
        .on('pointerleave', tip.leave);
      const p = document.createElement('div');
      p.className = 'vf-mnote';
      p.textContent = tr('charts.ld.uniformity', {
        p26: vf.f('.2f')(pick(2026, 0).p_uniform), p22: vf.f('.3f')(pick(2022, 0).p_uniform) });
      cell.append(p);
    });
    vf.legend(ldBox, [{ label: tr('charts.ld.legend_2026'), color: FG }, { label: '2022', color: MUTED },
      { label: tr('charts.ld.legend_chance'), color: 'var(--cds-chart-grid)' }]);
  }
  vf.draw(drawLastDigits);

  // 2. Sections by share in 0.1-point bins, observed vs expected ----------------------
  const pctBox = document.getElementById('pct-chart');
  let pctVar = 'share';
  vf.segmented(document.getElementById('pct-pick'), (v) => { pctVar = v; drawPct(); });
  function drawPct() {
    if (!vf.gate(pctBox, 'pct_hist')) return;
    const all = dash.data('pct_hist').data.filter((r) => r.year === 2026 && r.variable === (pctVar === 'Turnout' ? 'Turnout' : 'Lula share'));
    const total = d3.sum(all, (r) => r.observed);
    let cum = 0;
    const cut = all.map((r) => (cum += r.observed) / total);
    const lo = all[cut.findIndex((c) => c >= 0.003)].pct;
    const hi = all[cut.findIndex((c) => c >= 0.997)].pct + 0.1;
    const kept = all.filter((r) => r.pct >= lo && r.pct < hi);
    const views = pctVar === 'Turnout'
      ? [{ title: tr('charts.pct.turnout_title'), color: FG, rows: kept.map((r) => ({ ...r, x: r.pct + 0.05, a: r.pct })), dom: [lo, hi] }]
      : vf.cands().map((c) => ({
        title: tr('charts.pct.share_title', { name: vf.cand[c].name }), color: vf.cand[c].color(),
        rows: c === 'lula' ? kept.map((r) => ({ ...r, x: r.pct + 0.05, a: r.pct }))
          : kept.map((r) => ({ ...r, x: 99.95 - r.pct, a: 99.9 - r.pct })).reverse(),
        dom: c === 'lula' ? [lo, hi] : [100 - hi, 100 - lo],
      }));
    pctBox.replaceChildren();
    const tip = vf.tooltip(pctBox);
    const cells = vf.panels(pctBox, views.map((v) => v.title));
    const y = d3.scaleLinear([0, d3.max(kept, (r) => Math.max(r.observed, r.expected))], [220 - 24, 8]).nice();
    views.forEach((v, i) => {
      const { s, w, h } = vf.svg(cells[i], 220);
      const ml = vf.textWidth(s, y.ticks(5).map(nf)) + 8;
      const x = d3.scaleLinear(v.dom, [ml, w - 8]);
      s.append('g').attr('transform', `translate(${ml},0)`)
        .call(d3.axisLeft(y).ticks(5).tickFormat(nf).tickSize(-(w - ml - 8))).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).ticks(Math.max(3, Math.floor((w - ml) / 70))).tickFormat((d) => `${vf.f('~f')(d)}%`).tickSize(0).tickPadding(8)).call(vf.axis);
      const line = (f) => d3.line().x((r) => x(r.x)).y((r) => y(r[f]));
      s.append('path').datum(v.rows).attr('d', line('observed')).style('fill', 'none').style('stroke', v.color).attr('stroke-width', 1);
      s.append('path').datum(v.rows).attr('d', line('expected')).style('fill', 'none').style('stroke', FG).attr('stroke-width', 1.25).style('opacity', 0.6);
      const dot = s.append('circle').attr('r', 3.5).style('fill', v.color).style('display', 'none');
      const bis = d3.bisector((r) => r.x).center;
      s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const r = v.rows[bis(v.rows, x.invert(d3.pointer(ev)[0]))];
          dot.style('display', null).attr('cx', x(r.x)).attr('cy', y(r.observed));
          tip.show(ev, tr('charts.pct.tip_head', { title: v.title, from: d1(r.a), to: d1(r.a + 0.1) }), [
            { label: tr('charts.pct.tip_sections'), value: nf(r.observed), color: v.color },
            { label: tr('charts.pct.tip_expected'), value: nf(Math.round(r.expected)), color: FG },
          ]);
        })
        .on('pointerleave', (ev) => { if (ev.pointerType === 'touch') return; dot.style('display', 'none'); tip.hide(); });
    });
    vf.legend(pctBox, [{ label: tr('charts.pct.legend_sections'), color: views[0].color, line: true },
      { label: tr('charts.pct.legend_expected'), color: FG, line: true }]);
  }
  vf.draw(drawPct);

  // 3. Distance of each section from its polling place, log scale ---------------------
  const zBox = document.getElementById('z-chart');
  let zVar = 'share';
  vf.segmented(document.getElementById('z-pick'), (v) => { zVar = v; drawZ(); });
  function drawZ() {
    if (!vf.gate(zBox, 'z_hist')) return;
    const step = 0.25;
    const variable = { share: 'Lula share', Turnout: 'Turnout', Swing: 'Swing' }[zVar];
    const rows = dash.data('z_hist').data.filter((r) => r.round === 2 && r.variable === variable);
    const mirror = (rs) => rs.map((r) => ({ ...r, z: -r.z - step })).reverse();
    const byYear = (year) => rows.filter((r) => r.year === year);
    const views = zVar === 'Turnout'
      ? [{ title: tr('charts.z.turnout_title'), color: FG, r26: byYear(2026), r22: byYear(2022) }]
      : vf.cands().map((c) => ({
        title: tr(zVar === 'Swing' ? 'charts.z.swing_title' : 'charts.z.share_title', { name: vf.cand[c].name }), color: vf.cand[c].color(),
        r26: c === 'lula' ? byYear(2026) : mirror(byYear(2026)), r22: c === 'lula' ? byYear(2022) : mirror(byYear(2022)),
      }));
    zBox.replaceChildren();
    const tip = vf.tooltip(zBox);
    const cells = vf.panels(zBox, views.map((v) => v.title));
    const y = d3.scaleLog([0.5, d3.max(rows, (r) => Math.max(r.count, r.normal)) * 1.5], [240 - 24, 8]);
    const ticks = [1, 10, 100, 1000, 10000, 100000].filter((t) => t <= y.domain()[1]);
    views.forEach((v, i) => {
      const { s, w, h } = vf.svg(cells[i], 240);
      const ml = vf.textWidth(s, ticks.map(nf)) + 8;
      const x = d3.scaleLinear([-10, 10], [ml, w - 8]);
      for (const [a, b] of [[-10, -4], [4, 10]]) {
        s.append('rect').attr('x', x(a)).attr('width', x(b) - x(a)).attr('y', 8).attr('height', h - 32).style('fill', 'var(--cds-chart-grid)').style('opacity', 0.6);
      }
      s.append('g').attr('transform', `translate(${ml},0)`)
        .call(d3.axisLeft(y).tickValues(ticks).tickFormat(nf).tickSize(-(w - ml - 8))).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).tickValues([-8, -4, 0, 4, 8]).tickFormat((d) => (d > 0 ? '+' : '') + vf.f('')(d))
          .tickSize(0).tickPadding(8)).call(vf.axis);
      s.append('g').selectAll('rect').data(v.r26.filter((r) => r.count > 0)).join('rect')
        .attr('x', (r) => x(r.z) + 0.5).attr('width', Math.max(1, x(step) - x(0) - 1))
        .attr('y', (r) => y(r.count)).attr('height', (r) => y(0.5) - y(r.count)).style('fill', v.color);
      s.append('path').datum(v.r22.filter((r) => r.count > 0)).attr('d', d3.line().x((r) => x(r.z + step / 2)).y((r) => y(r.count)))
        .style('fill', 'none').style('stroke', MUTED).attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
      s.append('path').datum(v.r26.filter((r) => r.normal >= 0.5)).attr('d', d3.line().x((r) => x(r.z + step / 2)).y((r) => y(r.normal)))
        .style('fill', 'none').style('stroke', FG).attr('stroke-width', 1.5);
      s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const i = Math.max(0, Math.min(v.r26.length - 1, Math.floor((x.invert(d3.pointer(ev)[0]) + 10) / step)));
          const a = v.r26[i];
          tip.show(ev, tr('charts.z.tip_head', { title: v.title, from: vf.f('+.2f')(a.z), to: vf.f('+.2f')(a.z + step) }), [
            { label: '2026', value: nf(a.count), color: v.color },
            { label: tr('charts.z.tip_normal'), value: nf(Math.round(a.normal)), color: FG },
            { label: '2022', value: nf(v.r22[i]?.count ?? 0), color: MUTED },
          ]);
        })
        .on('pointerleave', tip.leave);
    });
    vf.legend(zBox, [{ label: tr('charts.z.legend_sections'), color: views[0].color },
      { label: tr('charts.z.legend_normal'), color: FG, line: true }, { label: tr('charts.z.legend_2022'), color: MUTED, line: true },
      { label: tr('charts.z.legend_beyond'), color: 'var(--cds-chart-grid)' }]);
  }
  vf.draw(drawZ);

  // 4. Fingerprint: turnout × candidate's share, runoff, 2026 beside 2022 -------------
  const fpBox = document.getElementById('fp-chart');
  function drawFp() {
    if (!vf.gate(fpBox, 'fingerprint')) return;
    const all = dash.data('fingerprint').data;
    const t = d3.scaleLog([1, d3.max(all, (r) => r.sections)], [0.16, 1]).clamp(true);
    const byT = d3.rollup(all, (v) => d3.sum(v, (r) => r.sections), (r) => r.turnout);
    const total = d3.sum(byT.values());
    let cum = 0;
    const lo = d3.sort(byT.keys()).find((k) => (cum += byT.get(k)) / total >= 0.002);
    const bg = vf.resolve('var(--color-panel)');
    const views = vf.cands().flatMap((c) => [2026, 2022].map((year) => ({
      title: tr('charts.fp.panel_title', { who: year === 2026 ? vf.cand[c].name : vf.cand[c].name22, year }),
      ramp: d3.interpolateRgb(bg, vf.resolve(vf.cand[c].color())),
      rows: all.filter((r) => r.year === year).map((r) => (c === 'lula' ? r : { ...r, share: 99 - r.share })),
      who: year === 2026 ? vf.cand[c].name : vf.cand[c].name22,
    })));
    fpBox.replaceChildren();
    const tip = vf.tooltip(fpBox);
    const cells = vf.panels(fpBox, views.map((v) => v.title));
    views.forEach((v, i) => {
      const cellOf = new Map(v.rows.map((r) => [`${r.turnout}|${r.share}`, r]));
      const { s, w, h } = vf.svg(cells[i], 260);
      const ml = vf.textWidth(s, ['100%']) + 8;
      const x = d3.scaleLinear([lo, 100], [ml, w - 6]);
      const y = d3.scaleLinear([0, 100], [h - 24, 6]);
      s.append('g').attr('transform', `translate(${ml},0)`)
        .call(d3.axisLeft(y).ticks(5).tickFormat((d) => `${d}%`).tickSize(0).tickPadding(6)).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).ticks(Math.max(2, Math.floor((w - ml) / 70))).tickFormat((d) => `${d}%`).tickSize(0).tickPadding(8)).call(vf.axis);
      s.append('g').selectAll('rect').data(v.rows.filter((r) => r.turnout >= lo)).join('rect')
        .attr('x', (r) => x(r.turnout)).attr('width', x(lo + 1) - x(lo) + 0.4)
        .attr('y', (r) => y(r.share + 1)).attr('height', y(0) - y(1) + 0.4)
        .style('fill', (r) => v.ramp(t(r.sections)));
      s.append('rect').attr('x', x(95)).attr('width', x(100) - x(95)).attr('y', y(100)).attr('height', y(90) - y(100))
        .style('fill', 'none').style('stroke', 'var(--color-fg)').attr('stroke-width', 1.5).attr('stroke-dasharray', '4 3');
      s.append('rect').attr('x', ml).attr('width', w - 6 - ml).attr('y', 6).attr('height', h - 30).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const [px, py] = d3.pointer(ev);
          const i = Math.floor(x.invert(px));
          const j = Math.floor(y.invert(py));
          tip.show(ev, tr('charts.fp.tip_head', { title: v.title, t0: i, t1: i + 1, who: v.who, s0: j, s1: j + 1 }), [
            { label: tr('charts.fp.tip_sections'), value: nf(cellOf.get(`${i}|${j}`)?.sections ?? 0) },
          ]);
        })
        .on('pointerleave', tip.leave);
    });
    const key = document.createElement('div');
    key.className = 'vf-legend';
    const corner = document.createElement('i');
    corner.className = 'vf-sw vf-sw-box';
    const c = document.createElement('span');
    c.append(corner, tr('charts.fp.legend_corner'));
    key.append(tr('charts.fp.legend_scale', { max: nf(d3.max(all, (r) => r.sections)) }), c);
    fpBox.append(key);
  }
  vf.draw(drawFp);

  // 5. Count progression: each candidate's share of the votes counted so far ----------
  // keep: which year|round pairs to draw (the simple tab shows only the two runoffs).
  function drawTiming(tBox, keep = ['2022|2', '2026|1', '2026|2']) {
    if (!vf.gate(tBox, 'timing')) return;
    const rows = dash.data('timing').data.filter((r) => r.lula_2p !== null);
    const series = vf.cands().flatMap((c) => keep.map((k) => {
      const [year, round] = k.split('|').map(Number);
      const who = year === 2026 ? vf.cand[c].name : vf.cand[c].name22;
      return {
        label: tr(round === 1 ? 'charts.timing.series_r1' : 'charts.timing.series', { who, year }),
        color: year === 2026 ? vf.cand[c].color() : MUTED,
        width: round === 2 && year === 2026 ? 2.5 : 1.75, dash: round === 1 ? '5 4' : null,
        pts: rows.filter((r) => r.year === year && r.round === round)
          .map((r) => ({ ...r, v: c === 'lula' ? r.lula_2p : 1 - r.lula_2p })),
      };
    }));
    tBox.replaceChildren();
    const tip = vf.tooltip(tBox);
    const { s, w, h } = vf.svg(tBox, 280);
    const [y0, y1] = d3.extent(series.flatMap((sr) => sr.pts), (r) => r.v);
    const y = d3.scaleLinear([Math.min(y0, 0.48), Math.max(y1, 0.52)], [h - 24, 10]).nice();
    const ml = vf.textWidth(s, y.ticks(5).map(pct0)) + 8;
    const ends = series.map((sr) => ({ sr, last: sr.pts.at(-1), text: `${sr.label}: ${pct1(sr.pts.at(-1).v)}` }));
    // Narrow (a phone): the end labels would squeeze the plot, so they become a legend below it.
    const labelW = vf.textWidth(s, ends.map((e) => e.text)) + 14;
    const narrow = w - ml - labelW < 260;
    const mr = narrow ? 8 : labelW;
    const x = d3.scaleLinear([0, 1], [ml, w - mr]);
    s.append('g').attr('transform', `translate(${ml},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(pct0).tickSize(-(w - ml - mr))).call(vf.axis);
    s.append('g').attr('transform', `translate(0,${h - 24})`)
      .call(d3.axisBottom(x).ticks(Math.max(2, Math.floor((w - ml) / 70))).tickFormat(pct0).tickSize(0).tickPadding(8)).call(vf.axis);
    s.append('line').attr('x1', ml).attr('x2', w - mr).attr('y1', y(0.5)).attr('y2', y(0.5))
      .style('stroke', REF).attr('stroke-dasharray', '4 3');
    for (const sr of series) {
      s.append('path').datum(sr.pts).attr('d', d3.line().x((r) => x(r.pct_counted)).y((r) => y(r.v)))
        .style('fill', 'none').style('stroke', sr.color).attr('stroke-width', sr.width)
        .attr('stroke-dasharray', sr.dash).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    }
    // End labels, nudged apart so they never touch.
    const placed = narrow ? [] : ends.map((e) => ({ ...e, y: y(e.last.v) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < placed.length; i++) placed[i].y = Math.max(placed[i].y, placed[i - 1].y + 14);
    for (const e of placed) {
      s.append('text').attr('class', 'vf-tick').attr('x', w - mr + 6).attr('y', e.y).attr('dy', '0.32em').text(e.text)
        .style('fill', e.sr.color === MUTED ? 'var(--color-fg-muted)' : e.sr.color);
    }
    if (narrow) vf.legend(tBox, ends.map((e) => ({ label: e.text, color: e.sr.color, line: true, dash: e.sr.dash })));
    const clock = (m) => tr('charts.timing.clock', { h: 17 + Math.floor(m / 60), m: String(m % 60).padStart(2, '0') });
    s.append('rect').attr('x', ml).attr('width', w - mr - ml).attr('height', h).style('fill', 'transparent')
      .on('pointermove pointerdown', (ev) => {
        const at = x.invert(d3.pointer(ev)[0]);
        tip.show(ev, tr('charts.timing.tip_head', { pct: pct1(Math.max(0, Math.min(1, at))) }), series.map((sr) => {
          const p = sr.pts.reduce((a, b) => (Math.abs(b.pct_counted - at) < Math.abs(a.pct_counted - at) ? b : a));
          return { label: tr('charts.timing.tip_line', { label: sr.label, time: clock(p.minutes) }), value: pct1(p.v),
            color: sr.color, line: true, dash: sr.dash };
        }));
      })
      .on('pointerleave', tip.leave);
  }
  vf.draw(() => drawTiming(document.getElementById('time-chart')));
  vf.timingChart = drawTiming;

  // 6. Section size: Lula's share minus the rest of the polling place, by number of voters -----
  const sizeBox = document.getElementById('size-chart');
  function drawSize() {
    if (!sizeBox || !vf.gate(sizeBox, 'size_curve')) return;
    const rows = dash.data('size_curve').data.filter((r) => r.sections >= 500);
    const series = [
      { key: '2026', label: '2026', color: FG, width: 2.5 },
      { key: '2022', label: '2022', color: MUTED, width: 1.75 },
      { key: '2018', label: '2018', color: REF, width: 1.5, dash: '2 3' },
      { key: 'planted', label: tr('charts.size.planted'), color: 'var(--color-bad)', width: 1.75, dash: '5 4' },
    ].map((s) => ({ ...s, pts: rows.filter((r) => r.series === s.key).map((r) => ({ x: r.from + 12.5, v: r.mean_pp, n: r.sections })) }));
    sizeBox.replaceChildren();
    const tip = vf.tooltip(sizeBox);
    const { s, w, h } = vf.svg(sizeBox, 240);
    const [y0, y1] = d3.extent(series.flatMap((sr) => sr.pts), (p) => p.v);
    const y = d3.scaleLinear([Math.min(y0, -0.5), Math.max(y1, 0.5)], [h - 24, 10]).nice();
    const fmtY = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${d1(Math.abs(v))}`;
    const ml = vf.textWidth(s, y.ticks(5).map(fmtY)) + 8;
    const x = d3.scaleLinear([0, 500], [ml, w - 8]);
    s.append('g').attr('transform', `translate(${ml},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(fmtY).tickSize(-(w - ml - 8))).call(vf.axis);
    s.append('g').attr('transform', `translate(0,${h - 24})`)
      .call(d3.axisBottom(x).ticks(Math.max(2, Math.floor((w - ml) / 70))).tickSize(0).tickPadding(8)).call(vf.axis);
    s.append('line').attr('x1', ml).attr('x2', w - 8).attr('y1', y(0)).attr('y2', y(0))
      .style('stroke', REF).attr('stroke-dasharray', '4 3');
    for (const sr of series) {
      s.append('path').datum(sr.pts).attr('d', d3.line().x((p) => x(p.x)).y((p) => y(p.v)))
        .style('fill', 'none').style('stroke', sr.color).attr('stroke-width', sr.width)
        .attr('stroke-dasharray', sr.dash ?? null).attr('stroke-linejoin', 'round');
    }
    vf.legend(sizeBox, series.map((sr) => ({ label: sr.label, color: sr.color, line: true, dash: sr.dash })));
    s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
      .on('pointermove pointerdown', (ev) => {
        const at = x.invert(d3.pointer(ev)[0]);
        const near = (pts) => pts.reduce((a, b) => (Math.abs(b.x - at) < Math.abs(a.x - at) ? b : a));
        const p0 = near(series[0].pts);
        tip.show(ev, tr('charts.size.tip_head', { from: p0.x - 12.5, to: p0.x + 12.5 }), series.map((sr) => {
          const p = near(sr.pts);
          return { label: sr.label, value: tr('charts.size.tip_value', { v: fmtY(p.v) }), color: sr.color, line: true, dash: sr.dash };
        }));
      })
      .on('pointerleave', tip.leave);
  }
  vf.draw(drawSize);

  // 7. One finalist gained votes and the other lost them: ratio in the data and in the null, by year, and
  // the data over the null for the three years and for planted vote flips ----------------------------------
  const quadBox = document.getElementById('quad-chart');
  function drawQuad() {
    if (!quadBox || !vf.gate(quadBox, 'tres_eleicoes')) return;
    const all = dash.data('tres_eleicoes').data;
    const who = { 2026: ['Lula', 'Flávio'], 2022: ['Lula', 'Jair'], 2018: ['Haddad', 'Jair'] };
    const rows = [2026, 2022, 2018].map((y) => {
      const r = all.find((d) => d.id === `quad|${y}`);
      return { y, obs: r.ratio, nul: r.null_ratio, lo: r.null_ratio_min, hi: r.null_ratio_max, left: r.leftover,
        leader: who[y][r.leader === 'lula' ? 0 : 1], other: who[y][r.leader === 'lula' ? 1 : 0] };
    });
    const planted = ['fifth', 'all'].map((h) => all.find((d) => d.id === `quad|planted|${h}`));
    const series = [
      { key: 'obs', label: tr('charts.quad.data'), color: FG },
      { key: 'nul', label: tr('charts.quad.null'), color: MUTED },
    ];
    quadBox.replaceChildren();
    const [c1, c2] = vf.panels(quadBox, [tr('charts.quad.title_ratio'), tr('charts.quad.title_leftover')], 'vf-stack');
    const tip = vf.tooltip(quadBox);
    const fmt = (v) => vf.format('ratio', v);
    {
      const { s, w, h } = vf.svg(c1, 200);
      const labels = rows.map((r) => `${r.y} (${r.leader})`);
      const ml = vf.textWidth(s, labels) + 12;
      const top = d3.max(rows, (r) => Math.max(r.obs, r.nul));
      // room on the right for the value written after the longest bar
      const x = d3.scaleLinear([0, top], [ml, w - 8 - vf.textWidth(s, [fmt(top)]) - 8]);
      const band = d3.scaleBand(rows.map((r) => r.y), [8, h - 24]).paddingInner(0.3);
      const sub = d3.scaleBand(series.map((sr) => sr.key), [0, band.bandwidth()]).padding(0.12);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).ticks(Math.max(2, Math.floor((w - ml) / 70))).tickFormat((v) => `${v}`).tickSize(-(h - 32)).tickPadding(8)).call(vf.axis);
      s.append('g').attr('transform', `translate(${ml - 6},0)`)
        .call(d3.axisLeft(band).tickFormat((y, i) => labels[i]).tickSize(0)).call(vf.axis);
      for (const r of rows) {
        for (const sr of series) {
          const y0 = band(r.y) + sub(sr.key);
          s.append('rect').attr('x', x(0)).attr('y', y0).attr('width', x(r[sr.key]) - x(0)).attr('height', sub.bandwidth())
            .attr('rx', 2).style('fill', sr.color);
          s.append('text').attr('x', x(r[sr.key]) + 5).attr('y', y0 + sub.bandwidth() / 2).attr('dy', '0.35em')
            .attr('class', 'vf-tick').style('fill', 'var(--color-fg)').text(fmt(r[sr.key]));
        }
        s.append('rect').attr('x', ml).attr('y', band(r.y)).attr('width', w - 8 - ml).attr('height', band.bandwidth())
          .style('fill', 'transparent')
          .on('pointermove pointerdown', (ev) => tip.show(ev, tr('charts.quad.tip_head', { year: r.y, leader: r.leader, other: r.other }), [
            { label: tr('charts.quad.data'), value: fmt(r.obs), color: FG },
            { label: tr('charts.quad.null'), value: tr('charts.quad.tip_null', { v: fmt(r.nul), lo: fmt(r.lo), hi: fmt(r.hi) }), color: MUTED },
          ]))
          .on('pointerleave', tip.leave);
      }
    }
    {
      const items = [
        ...rows.map((r) => ({ label: `${r.y}`, v: r.left, color: FG })),
        { label: tr('charts.quad.planted_fifth'), v: planted[0].leftover, color: 'var(--color-bad)' },
        { label: tr('charts.quad.planted_all'), v: planted[1].leftover, color: 'var(--color-bad)' },
      ];
      const { s, w, h } = vf.svg(c2, 30 + items.length * 26);
      const ml = vf.textWidth(s, items.map((d) => d.label)) + 12;
      const dfmt = vf.f('.2f');
      const x = d3.scaleLinear([0, d3.max(items, (d) => d.v) * 1.05], [ml, w - 10 - vf.textWidth(s, ['0,00']) - 8]);
      const band = d3.scaleBand(items.map((d) => d.label), [4, h - 24]).paddingInner(0.3);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).ticks(4).tickFormat(dfmt).tickSize(-(h - 28)).tickPadding(8)).call(vf.axis);
      s.append('g').attr('transform', `translate(${ml - 6},0)`).call(d3.axisLeft(band).tickSize(0)).call(vf.axis);
      for (const d of items) {
        s.append('rect').attr('x', x(0)).attr('y', band(d.label)).attr('width', x(d.v) - x(0)).attr('height', band.bandwidth())
          .attr('rx', 2).style('fill', d.color);
        s.append('text').attr('x', x(d.v) + 5).attr('y', band(d.label) + band.bandwidth() / 2).attr('dy', '0.35em')
          .attr('class', 'vf-tick').style('fill', 'var(--color-fg)').text(dfmt(d.v));
      }
      s.append('line').attr('x1', x(1)).attr('x2', x(1)).attr('y1', 0).attr('y2', h - 24).style('stroke', REF).attr('stroke-dasharray', '4 3');
    }
    vf.legend(quadBox, [...series.map((sr) => ({ label: sr.label, color: sr.color })), { label: tr('charts.quad.legend_planted'), color: 'var(--color-bad)' }]);
  }
  vf.draw(drawQuad);
})();
