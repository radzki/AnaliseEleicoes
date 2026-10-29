// Shared helpers for the report: formatting, load states, tooltips, filled text, tables and chart frames.
window.vf = (() => {
  // Text in the page's language: window.VF_I18N, the "js." strings of locales/<lang>.json, written to i18n.js by
  // scripts/05_site.py. {name} in a string is replaced by vars.name.
  const I18N = window.VF_I18N ?? {};
  function t(key, vars) {
    const s = I18N[`js.${key}`];
    if (s === undefined) {
      console.warn('i18n: no text for', key);
      return key;
    }
    return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m)) : s;
  }
  // Number format of the page's language; in Portuguese: 499.205 · 51,8% · 4,43 mi
  const f = d3.formatLocale({ decimal: t('locale.decimal'), thousands: t('locale.thousands'), grouping: [3], currency: ['R$', ''], minus: '−', percent: '%' }).format;
  const nf = f(',');
  const compact = new Intl.NumberFormat(t('locale.intl'), { notation: 'compact', maximumFractionDigits: 2 });
  const compact0 = new Intl.NumberFormat(t('locale.intl'), { notation: 'compact', maximumFractionDigits: 0 });
  const signed = (v, s) => (v > 0 ? '+' : v < 0 ? '−' : '') + s;
  const dec = (v, n) => f(`.${n}f`)(Math.abs(v));
  const fmt = {
    str: (v) => String(v),
    int: (v) => nf(Math.round(v)),
    sint: (v) => signed(v, nf(Math.abs(Math.round(v)))),
    compact: (v) => compact.format(v),
    compact0: (v) => compact0.format(v),
    signedCompact: (v) => signed(v, compact.format(Math.abs(v))),
    absCompact: (v) => compact.format(Math.abs(v)),
    pct: (v) => f('.1%')(v),
    pctv: (v) => `${f('.2f')(v)}%`,
    pp: (v) => signed(v, t('fmt.pp', { v: dec(v, 1) })),
    pp2: (v) => t('fmt.pp', { v: dec(v, 2) }),
    spp2: (v) => signed(v, t('fmt.pp', { v: dec(v, 2) })),
    pph: (v) => signed(v, t('fmt.pph', { v: dec(v, 2) })),
    hm: (v) => t('fmt.hm', { h: Math.floor(v), m: String(Math.floor((v % 1) * 60 + 1e-9)).padStart(2, '0') }),
    dec2: (v) => f('.2f')(v),
    dec3: (v) => f('.3f')(v),
    ratio: (v) => t('fmt.ratio', { v: f('.1f')(v) }),
    dec1x: (v) => t('fmt.times', { v: f('.1f')(v) }),
    times2: (v) => t(v < 2 ? 'fmt.time' : 'fmt.times', { v: f('.2f')(v) }),
  };
  const format = (kind, v) => (v === null || v === undefined || Number.isNaN(v) ? '—' : (fmt[kind] ?? fmt.str)(v));

  // data-where="a=1&b=2": the first row whose cells equal those values.
  function where(rows, w) {
    const conds = w.split('&').map((p) => p.split('=').map(decodeURIComponent));
    return rows.find((r) => conds.every(([k, v]) => String(r[k]) === v));
  }

  // Fills every marked text element that carries a data-fmt.
  function fill() {
    for (const el of document.querySelectorAll('#dash-root [data-fmt][data-source]')) {
      const d = dash.data(el.dataset.source);
      el.classList.toggle('dash-skeleton', d.status === 'loading');
      if (d.status !== 'ok') {
        el.textContent = '—';
        continue;
      }
      const rows = Array.isArray(d.data) ? d.data : [d.data];
      const row = el.dataset.where ? where(rows, el.dataset.where) : rows[Number(el.dataset.row ?? 0)];
      el.textContent = row ? format(el.dataset.fmt, row[el.dataset.field]) : '—';
    }
  }

  // True when el is on the visible tab and every source is ready; otherwise shows the skeleton or the failed line.
  function gate(el, ...ids) {
    if (el.closest('[hidden]')) return false;
    const st = ids.map((id) => dash.data(id).status);
    if (st.every((s) => s === 'ok')) {
      el.classList.remove('dash-skeleton');
      return true;
    }
    el.replaceChildren();
    const loading = st.some((s) => s === 'loading');
    el.classList.toggle('dash-skeleton', loading);
    if (!loading) {
      const f = document.createElement('div');
      f.className = 'vf-fail';
      const dot = document.createElement('span');
      dot.className = 'vf-dot';
      f.append(dot, t('load.failed'));
      el.append(f);
    }
    return false;
  }

  // Draws rows into a marked <table>: one cell per <th data-field>, formatted by its data-fmt.
  function table(tbl, rows, keyOf) {
    const ths = [...tbl.querySelectorAll('thead th')];
    const s = tbl._sort;
    if (s) {
      const k = s.dir === 'asc' ? 1 : -1;
      rows = [...rows].sort((a, b) => {
        const x = a[s.field], y = b[s.field];
        return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y))) * k;
      });
      for (const th of ths) th.setAttribute('aria-sort', th.dataset.field === s.field ? (s.dir === 'asc' ? 'ascending' : 'descending') : 'none');
    }
    const body = tbl.tBodies[0] ?? tbl.createTBody();
    body.replaceChildren(...rows.map((r) => {
      const tr = document.createElement('tr');
      tr.dataset.key = keyOf(r);
      for (const th of ths) {
        const td = document.createElement('td');
        td.textContent = format(th.dataset.fmt ?? 'str', r[th.dataset.field]);
        if (th.classList.contains('vf-n')) td.className = 'vf-n';
        td.dataset.label = th.textContent;
        if (th.dataset.cand) td.dataset.cand = th.dataset.cand;
        tr.append(td);
      }
      return tr;
    }));
  }

  // Turns each header into a sort button; redraw() draws the table again.
  function sortable(tbl, redraw, field, dir = 'desc') {
    tbl._sort = { field, dir };
    for (const th of tbl.querySelectorAll('thead th')) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'vf-sort';
      b.append(...th.childNodes);
      th.append(b);
      b.addEventListener('click', () => {
        const f = th.dataset.field;
        tbl._sort = { field: f, dir: tbl._sort.field === f && tbl._sort.dir === 'desc' ? 'asc' : 'desc' };
        redraw();
      });
    }
  }

  // A line swatch with the same dashes as an SVG stroke-dasharray such as '5 4'.
  function swatch(color, dash) {
    if (!dash) return color;
    const [on, off] = dash.split(' ').map(Number);
    return `repeating-linear-gradient(to right, ${color} 0 ${on}px, transparent ${on}px ${on + off}px)`;
  }

  function tooltip(box) {
    const t = document.createElement('div');
    t.className = 'vf-tip';
    t.hidden = true;
    box.append(t);
    return {
      show(ev, head, lines) {
        const h = document.createElement('div');
        h.className = 'vf-tip-h';
        h.textContent = head;
        t.replaceChildren(h, ...lines.map((l) => {
          const r = document.createElement('div');
          r.className = 'vf-tip-r';
          if (l.color) {
            const sw = document.createElement('i');
            if (l.line) sw.className = 'vf-sw-line';
            sw.style.background = swatch(l.color, l.dash);
            r.append(sw);
          }
          const b = document.createElement('b');
          b.textContent = l.value;
          r.append(l.label ? `${l.label} ` : '', b);
          return r;
        }));
        t.hidden = false;
        const [x, y] = d3.pointer(ev, box);
        const left = x + 14 + t.offsetWidth > box.clientWidth ? x - 14 - t.offsetWidth : x + 14;
        t.style.left = `${Math.max(0, left)}px`;
        t.style.top = `${Math.max(0, y - t.offsetHeight - 10)}px`;
      },
      hide() { t.hidden = true; },
      // A finger lifting also "leaves": keep the tip up until the next tap elsewhere.
      leave(ev) { if (ev.pointerType !== 'touch') t.hidden = true; },
    };
  }
  document.getElementById('dash-root').addEventListener('pointerdown', (ev) => {
    if (ev.target.closest('.vf-chart')) return;
    for (const t of document.querySelectorAll('#dash-root .vf-tip')) t.hidden = true;
  });

  function svg(box, height) {
    const w = Math.max(240, box.clientWidth);
    // The chart box carries the description for screen readers (role="img" in index.html), not the drawing.
    const s = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${w} ${height}`).attr('class', 'vf-svg')
      .attr('aria-hidden', 'true');
    return { s, w, h: height };
  }

  // Small multiples: appends one titled cell per title before any is drawn, so each chart
  // measures its final width (a cell drawn while alone in its row would later shrink and scale down).
  function panels(box, titles, cls = titles.length > 1 ? 'vf-multiples vf-two' : 'vf-single') {
    const grid = document.createElement('div');
    grid.className = cls;
    box.append(grid);
    return titles.map((title) => {
      const cell = document.createElement('div');
      const head = document.createElement('div');
      head.className = 'vf-mtitle';
      head.textContent = title;
      cell.append(head);
      grid.append(cell);
      return cell;
    });
  }

  function textWidth(s, strings) {
    const t = s.append('text').attr('class', 'vf-tick');
    let m = 0;
    for (const str of strings) m = Math.max(m, t.text(str).node().getComputedTextLength());
    t.remove();
    return m;
  }

  function axis(g) {
    g.attr('font-size', null).attr('font-family', null).attr('class', 'vf-axis');
    g.select('.domain').remove();
    return g;
  }

  function legend(box, items) {
    const l = document.createElement('div');
    l.className = 'vf-legend';
    for (const it of items) {
      const span = document.createElement('span');
      const sw = document.createElement('i');
      sw.className = it.line ? 'vf-sw-line' : 'vf-sw';
      sw.style.background = swatch(it.color, it.dash);
      span.append(sw, it.label);
      l.append(span);
    }
    box.append(l);
  }

  // A theme color as rgb(), for d3 interpolation.
  function resolve(color) {
    const p = document.createElement('span');
    p.style.color = color;
    document.getElementById('dash-root').append(p);
    const c = getComputedStyle(p).color;
    p.remove();
    return c;
  }

  // Wires a segmented control: calls onPick(value) with the pressed button's data-v.
  function segmented(el, onPick) {
    el.addEventListener('click', (ev) => {
      const b = ev.target.closest('button[data-v]');
      if (!b) return;
      for (const x of el.querySelectorAll('button')) x.setAttribute('aria-pressed', String(x === b));
      onPick(b.dataset.v);
    });
  }

  // Charts register here so a tab switch can draw them at their real width.
  const charts = [];
  // chart box -> its draw function, for charts inside a "Ver gráfico" panel, drawn when the panel opens
  const boxes = new Map();
  function draw(fn, box) {
    charts.push(fn);
    if (box) boxes.set(box, fn);
    dash.onData(fn);
  }

  // Tabs: one [data-page] shown at a time; any [data-goto] button switches and scrolls to data-target.
  function tabs() {
    const bar = document.getElementById('vf-tabs');
    const pages = [...document.querySelectorAll('#dash-root [data-page]')];
    const tabsList = [...bar.querySelectorAll('[data-tab]')];
    const mark = (id) => {
      for (const b of tabsList) {
        b.setAttribute('aria-selected', String(b.dataset.tab === id));
        b.tabIndex = b.dataset.tab === id ? 0 : -1;
      }
    };
    const show = (id, target) => {
      for (const p of pages) p.hidden = p.id !== id;
      mark(id);
      for (const fn of charts) fn();
      const el = target && document.getElementById(target);
      if (el) el.scrollIntoView();
      dash.setLink(target ?? id);
    };
    document.getElementById('dash-root').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-tab], [data-goto]');
      if (b) show(b.dataset.tab ?? b.dataset.goto, b.dataset.target);
    });
    // Arrow keys, Home and End move between tabs, as screen-reader users expect of a tab list.
    bar.addEventListener('keydown', (ev) => {
      const i = tabsList.indexOf(document.activeElement);
      const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabsList.length - 1 }[ev.key];
      if (i < 0 || to === undefined) return;
      ev.preventDefault();
      const b = tabsList[(to + tabsList.length) % tabsList.length];
      b.focus();
      show(b.dataset.tab);
    });
    mark(tabsList.find((b) => b.getAttribute('aria-selected') === 'true')?.dataset.tab);
    const named = document.getElementById(location.hash.slice(1));
    const page = named?.closest('[data-page]');
    if (page && page.hidden) show(page.id, named.id);
    else if (named) named.scrollIntoView();
  }

  // Candidate filter: dash.params().cand is 'lula', 'flavio' or 'ambos'. The page root carries it as
  // data-show, and CSS hides every [data-cand] element of the candidate not shown.
  const CANDS = { lula: ['lula'], flavio: ['flavio'], ambos: ['lula', 'flavio'] };
  const cands = () => CANDS[dash.params().cand] ?? CANDS.ambos;
  // Party colors, not palette slots: Lula red, Flávio blue (--vf-lula / --vf-flavio in index.html, light and dark).
  const cand = {
    lula: { name: t('cand.lula'), name22: t('cand.lula22'), color: () => 'var(--vf-lula)' },
    flavio: { name: t('cand.flavio'), name22: t('cand.flavio22'), color: () => 'var(--vf-flavio)' },
  };
  const pick = document.getElementById('cand-pick');
  pick.addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-v]');
    if (b) dash.setParams({ cand: b.dataset.v });
  });
  dash.onData(() => {
    const c = CANDS[dash.params().cand] ? dash.params().cand : 'ambos';
    document.querySelector('#dash-root .vf').dataset.show = c;
    for (const b of pick.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.v === c));
  });

  // Theme switch: only where the host lets the page pick its theme (the static site's dash.js);
  // on claude.ai the viewer's own setting applies.
  const themeBox = document.querySelector('#dash-root .vf-theme');
  if (themeBox && dash.setTheme) {
    const tp = document.getElementById('theme-pick');
    for (const b of tp.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.v === dash.theme()));
    segmented(tp, (v) => dash.setTheme(v));
    themeBox.hidden = false;
  }

  // "pergunta 4" anywhere in the text, now or later (the "Tente fraudar!" text is rebuilt on every change),
  // becomes a button that shows that question's title, with a way to jump to it: the questions are on the
  // first tab, and most references to them are on the others.
  const root = document.getElementById('dash-root');
  const QUESTIONS = new Map([...root.querySelectorAll('.vf-q')].map((a) => [
    a.querySelector('.vf-q-n').textContent.trim(), { id: a.id, title: a.querySelector('h3').textContent.trim() }]));
  // the word for question(s) and for "and" come from the language: "perguntas 3 e 4", "questions 3 and 4"
  const QREF = new RegExp(`\\b(${t('qref.word')})(\\s+)(\\d+(?:\\s*(?:,|${t('qref.and')})\\s*\\d+)*)`, 'gi');
  const hasQref = new RegExp(QREF.source, 'i');
  // a direct child of #dash-root, outside the .vf container, so position: fixed follows the viewport
  const qpop = document.createElement('div');
  qpop.className = 'vf-qpop';
  qpop.id = 'vf-qpop';
  qpop.hidden = true;
  root.append(qpop);
  let qOpen = null;
  function qButton(n, text) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'vf-qref';
    b.dataset.q = n;
    b.textContent = text;
    b.setAttribute('aria-label', t('qref.aria', { n, title: QUESTIONS.get(n).title }));
    b.setAttribute('aria-expanded', 'false');
    b.setAttribute('aria-controls', 'vf-qpop');
    return b;
  }
  function linkQuestions() {
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (hasQref.test(n.data) && !n.parentElement.closest('.vf-q-head, .vf-qref, .vf-qpop, button, a, script, style, svg, textarea')
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    const nodes = [];
    while (walk.nextNode()) nodes.push(walk.currentNode);
    for (const node of nodes) {
      const frag = document.createDocumentFragment();
      let at = 0;
      for (const m of node.data.matchAll(QREF)) {
        frag.append(node.data.slice(at, m.index));
        const [, word, space, list] = m;
        const parts = list.split(/(\s*(?:,|e)\s*)/);
        if (parts.length === 1 && QUESTIONS.has(list)) frag.append(qButton(list, `${word}${space}${list}`));
        else {
          frag.append(word + space);
          parts.forEach((p, i) => frag.append(i % 2 === 0 && QUESTIONS.has(p) ? qButton(p, p) : p));
        }
        at = m.index + m[0].length;
      }
      frag.append(node.data.slice(at));
      node.replaceWith(frag);
    }
  }
  function closeQuestion() {
    if (!qOpen) return;
    qOpen.setAttribute('aria-expanded', 'false');
    qpop.hidden = true;
    qOpen = null;
  }
  function openQuestion(b) {
    const q = QUESTIONS.get(b.dataset.q);
    const head = document.createElement('div');
    head.className = 'vf-tip-h';
    head.textContent = `Pergunta ${b.dataset.q}`;
    const title = document.createElement('p');
    title.textContent = q.title;
    const go = document.createElement('button');
    go.type = 'button';
    go.className = 'vf-link';
    go.dataset.goto = 'simples';
    go.dataset.target = q.id;
    go.textContent = t('qref.go');
    qpop.replaceChildren(head, title, go);
    qpop.hidden = false;
    qOpen = b;
    b.setAttribute('aria-expanded', 'true');
    // below the reference, or above it when there is no room; inside the viewport with a 16px gutter
    const r = b.getBoundingClientRect();
    const w = qpop.offsetWidth;
    const h = qpop.offsetHeight;
    qpop.style.left = `${Math.max(16, Math.min(r.left, innerWidth - 16 - w))}px`;
    qpop.style.top = `${r.bottom + 6 + h > innerHeight - 8 ? r.top - 6 - h : r.bottom + 6}px`;
  }
  root.addEventListener('click', (ev) => {
    const b = ev.target.closest('.vf-qref');
    if (b) {
      const same = b === qOpen;
      closeQuestion();
      if (!same) openQuestion(b);
      return;
    }
    const go = ev.target.closest('.vf-qpop [data-goto]');
    if (go) {
      // the tab switch itself is the [data-goto] handler in tabs(); mark where the reader lands
      const target = document.getElementById(go.dataset.target);
      closeQuestion();
      target.classList.remove('vf-flash');
      // after the tab switch has shown the page: a hidden element cannot take focus
      requestAnimationFrame(() => {
        target.classList.add('vf-flash');
        const h = target.querySelector('h3');
        h.setAttribute('tabindex', '-1');
        h.focus({ preventScroll: true });
      });
      return;
    }
    if (!ev.target.closest('.vf-qpop')) closeQuestion();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && qOpen) {
      const b = qOpen;
      closeQuestion();
      b.focus();
    }
  });
  addEventListener('scroll', closeQuestion, { passive: true });
  addEventListener('resize', closeQuestion);
  // "Ver gráfico" under a test: opens its chart, which is drawn then, once its width can be measured
  root.addEventListener('click', (ev) => {
    const b = ev.target.closest('.vf-showchart');
    if (!b) return;
    const panel = document.getElementById(b.getAttribute('aria-controls'));
    const open = b.getAttribute('aria-expanded') !== 'true';
    b.setAttribute('aria-expanded', String(open));
    b.textContent = open ? t('chart.hide') : t('chart.show');
    panel.hidden = !open;
    if (open) for (const [box, fn] of boxes) if (panel.contains(box)) fn();
  });

  linkQuestions();
  let pending = false;
  new MutationObserver(() => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; linkQuestions(); });
  }).observe(root, { childList: true, subtree: true, characterData: true });

  dash.onData(fill);
  return { t, f, format, gate, table, sortable, tooltip, svg, panels, textWidth, axis, legend, resolve, segmented, draw, tabs, cands, cand };
})();
