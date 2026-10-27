// Stand-in for the claude.ai dashboard runtime, so report/*.js runs as a plain static site.
// Datasets load from data/<id>.json on first use; calcs run once their inputs are loaded;
// filters live in the query string and the open section in the hash. Every onData callback
// runs again when data arrives, a filter changes or the page width changes.
window.dash = (() => {
  const DEFAULTS = JSON.parse(document.currentScript.dataset.params ?? '{}');
  const DATASETS = new Set((document.currentScript.dataset.datasets ?? '').split(' ').filter(Boolean));
  const store = new Map();
  const calcs = new Map();
  const cache = new Map();
  const subs = [];
  let version = 0;

  function fromUrl() {
    const p = {};
    for (const [k, v] of new URLSearchParams(location.search)) p[k] = v;
    return p;
  }
  let params = { ...DEFAULTS, ...fromUrl() };

  // Theme: 'auto' follows the system; 'claro' or 'escuro' is kept for the next visit. Applied here,
  // in <head>, so the page never paints in the wrong theme first.
  const THEMES = { claro: 'light', escuro: 'dark' };
  let theme = 'auto';
  try {
    theme = THEMES[localStorage.getItem('tema')] ? localStorage.getItem('tema') : 'auto';
  } catch {}
  function applyTheme() {
    if (THEMES[theme]) document.documentElement.dataset.theme = THEMES[theme];
    else delete document.documentElement.dataset.theme;
  }
  applyTheme();

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      for (const fn of subs) run(fn);
    });
  }
  function run(fn) {
    try {
      fn();
    } catch (e) {
      console.error(e);
    }
  }

  function load(id) {
    const s = { status: 'loading', data: [] };
    store.set(id, s);
    fetch(`data/${encodeURIComponent(id)}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        s.status = 'ok';
        s.data = d;
      }, (e) => {
        s.status = 'error';
        s.message = String(e.message ?? e);
      })
      .finally(() => {
        version++;
        schedule();
      });
    return s;
  }

  // A calc may be asked for before the script that defines it has run: until the page has
  // parsed, an unknown id is still loading; after that it is missing.
  let parsed = document.readyState !== 'loading';
  document.addEventListener('DOMContentLoaded', () => {
    parsed = true;
    version++;
    schedule();
  });

  function data(id) {
    const c = calcs.get(id);
    if (!c && !DATASETS.has(id)) return { status: parsed ? 'missing' : 'loading', data: [] };
    if (!c) return store.get(id) ?? load(id);
    const ins = c.inputs.map(data);
    const waiting = ins.find((d) => d.status !== 'ok');
    if (waiting) return { status: waiting.status, data: [] };
    let hit = cache.get(id);
    if (!hit || hit.version !== version) {
      try {
        hit = { version, status: 'ok', data: c.fn(...ins.map((d) => d.data)) };
      } catch (e) {
        console.error(e);
        hit = { version, status: 'error', data: [], message: e.message };
      }
      cache.set(id, hit);
    }
    return hit;
  }

  function calc(id, { inputs = [], fn }) {
    calcs.set(id, { inputs, fn });
  }

  // Redraw when the page's width changes (not its height: drawing changes that).
  let width = null;
  function watchWidth() {
    const root = document.getElementById('dash-root');
    if (!root || width !== null) return;
    width = root.clientWidth;
    new ResizeObserver(() => {
      if (root.clientWidth === width) return;
      width = root.clientWidth;
      schedule();
    }).observe(root);
    // Some charts resolve theme colors when drawn, so a light/dark switch redraws too.
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', schedule);
  }

  function onData(fn) {
    subs.push(fn);
    watchWidth();
    run(fn);
  }

  function setParams(next) {
    for (const [k, v] of Object.entries(next)) {
      if (v === null || v === undefined) delete params[k];
      else params[k] = v;
    }
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (DEFAULTS[k] !== v) q.set(k, v);
    const search = q.toString();
    history.replaceState(null, '', `${location.pathname}${search ? `?${search}` : ''}${location.hash}`);
    version++;
    schedule();
  }

  function setTheme(t) {
    theme = THEMES[t] ? t : 'auto';
    try {
      if (theme === 'auto') localStorage.removeItem('tema');
      else localStorage.setItem('tema', theme);
    } catch {}
    applyTheme();
    version++;
    schedule();
  }

  function setLink(name) {
    history.replaceState(null, '', `${location.pathname}${location.search}${name ? `#${name}` : ''}`);
  }

  return {
    data,
    calc,
    onData,
    params: () => ({ ...params }),
    setParams,
    resetParams: () => setParams(Object.fromEntries(Object.keys(params).map((k) => [k, DEFAULTS[k] ?? null]))),
    setLink,
    theme: () => theme,
    setTheme,
    refresh: () => {},
    colors: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `var(--series-${i})`),
  };
})();
