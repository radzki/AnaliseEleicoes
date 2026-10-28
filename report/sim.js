// "Tente fraudar!": the reader tampers with the 2026 runoff and sees what the page's tests would say.
// Data: data/sim/ (scripts/09_sim_data.py), every runoff section, loaded when the tab first opens.
// The tests are the same definitions as scripts/02_analyze.py, recomputed here on the tampered copy.
(() => {
  const page = document.getElementById('fraude');
  if (!page) return;
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat('pt-BR');
  const int = (x) => nf.format(Math.round(x));
  const dec = (x, d = 1) => x.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 1) => `${dec(100 * x, d)}%`;
  const NAME = { lula: 'Lula', flavio: 'Flávio' };

  // ---------------------------------------------------------------- numerics
  function gln(xx) {
    const cof = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
    let y = xx;
    let tmp = xx + 5.5;
    tmp -= (xx + 0.5) * Math.log(tmp);
    let ser = 1.000000000190015;
    for (const c of cof) ser += c / ++y;
    return -tmp + Math.log((2.5066282746310005 * ser) / xx);
  }
  // upper regularized incomplete gamma Q(a, x); chi-square survival = Q(df / 2, x / 2)
  function gammq(a, x) {
    if (x <= 0) return 1;
    const lead = Math.exp(-x + a * Math.log(x) - gln(a));
    if (x < a + 1) {
      let ap = a, sum = 1 / a, del = sum;
      for (let i = 0; i < 500; i++) {
        ap += 1; del *= x / ap; sum += del;
        if (Math.abs(del) < Math.abs(sum) * 1e-15) break;
      }
      return Math.max(0, 1 - sum * lead);
    }
    let b = x + 1 - a, c = 1e300, d = 1 / b, h = d;
    for (let i = 1; i < 500; i++) {
      const an = -i * (i - a);
      b += 2;
      d = an * d + b; if (Math.abs(d) < 1e-300) d = 1e-300;
      c = b + an / c; if (Math.abs(c) < 1e-300) c = 1e-300;
      d = 1 / d;
      const del = d * c;
      h *= del;
      if (Math.abs(del - 1) < 1e-15) break;
    }
    return lead * h;
  }
  // k-th smallest by quickselect, O(n) instead of a full sort (a is reordered)
  function select(a, k) {
    let lo = 0, hi = a.length - 1;
    while (lo < hi) {
      const pivot = a[(lo + hi) >> 1];
      let i = lo, j = hi;
      while (i <= j) {
        while (a[i] < pivot) i++;
        while (a[j] > pivot) j--;
        if (i <= j) { const t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
      }
      if (k <= j) hi = j; else if (k >= i) lo = i; else return a[k];
    }
    return a[k];
  }
  const median = (a) => {
    const s = a.slice(), m = s.length >> 1;
    return s.length % 2 ? select(s, m) : (select(s, m - 1) + select(s, m)) / 2;
  };
  const gcd = (a, b) => { while (b) [a, b] = [b, a % b]; return a; };
  function mulberry32(seed) {
    return () => {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) {
    let u = 0;
    while (u === 0) u = r();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
  }
  function binom(n, p, r) {
    if (n <= 0 || p <= 0) return 0;
    if (p >= 1) return n;
    const q = 1 - p, mean = n * p;
    if (mean < 30) {
      const u = r(), ratio = p / q;
      let x = 0, pr = Math.pow(q, n), cdf = pr;
      while (u > cdf && x < n) { pr *= (ratio * (n - x)) / (x + 1); x++; cdf += pr; }
      return x;
    }
    return Math.min(n, Math.max(0, Math.round(mean + Math.sqrt(mean * q) * gauss(r))));
  }

  // ---------------------------------------------------------------- data
  let D = null;
  async function load() {
    const meta = await (await fetch('data/sim/meta.json')).json();
    if (!('DecompressionStream' in window)) throw new Error('Este navegador não consegue abrir os dados compactados. Tente uma versão recente do Chrome, do Firefox, do Edge ou do Safari.');
    const res = await fetch('data/sim/secoes_2026_t2.bin');
    if (!res.ok) throw new Error(`Os dados não foram encontrados (${res.status}).`);
    const bytes = new Uint8Array(await new Response(res.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
    const n = meta.sections;
    const col = {};
    for (const c of meta.columns) {
      if (c.type === 'u8') col[c.name] = bytes.subarray(c.offset, c.offset + c.length);
      else {
        const a = new Uint16Array(c.length), lo = c.offset, hi = c.offset + c.length;
        for (let i = 0; i < c.length; i++) a[i] = bytes[lo + i] | (bytes[hi + i] << 8);
        col[c.name] = a;
      }
    }
    const L = Uint16Array.from(col.lula), F = Uint16Array.from(col.flavio);
    const C = new Uint16Array(n), A = new Uint16Array(n);
    for (let i = 0; i < n; i++) { C[i] = L[i] + F[i] + col.other[i]; A[i] = C[i] + col.abstencao[i]; }
    const base = { lula: L, flavio: F, comparecimento: C, aptos: A };
    const unzig = (name, from) => {
      const z = col[name], b = base[from], out = new Uint16Array(n);
      for (let i = 0; i < n; i++) out[i] = b[i] + (z[i] & 1 ? -(z[i] + 1) / 2 : z[i] / 2);
      return out;
    };
    const P = new Uint32Array(meta.places + 1);
    for (let k = 0; k < meta.places; k++) P[k + 1] = P[k] + col.place_size[k];
    const maxN = A.reduce((m, x) => Math.max(m, x), 0);
    const lf = new Float64Array(maxN + 1);
    for (let k = 1; k <= maxN; k++) lf[k] = lf[k - 1] + Math.log(k);
    D = {
      meta, n, P, L, F, C, A, model: col.model, uf: col.uf, lf,
      L1: unzig('lula_1', 'lula'), F1: unzig('flavio_1', 'flavio'),
      C1: unzig('comparecimento_1', 'comparecimento'), A1: unzig('aptos_1', 'aptos'),
    };
    // chance that a binomial redraw of each section lands on a whole percentage (expected value of
    // the integer-percentage test), for Lula's share and for turnout
    D.pL = new Float64Array(n); D.pT = new Float64Array(n);
    for (let i = 0; i < n; i++) { D.pL[i] = pInt(L[i], L[i] + F[i]); D.pT[i] = pInt(C[i], A[i]); }
    D.order = {};
    D.base = tests(L, F, C, null);
  }

  // P(0 < X < N and 100 X / N is a whole number) for X ~ Binomial(N, x / N)
  function pInt(x, N) {
    if (x <= 0 || x >= N) return 0;
    const p = x / N, q = 1 - p, s = N / gcd(N, 100);
    const mean = N * p, sd = Math.sqrt(mean * q);
    const lo = Math.max(1, Math.ceil((mean - 7 * sd) / s)), hi = Math.min(Math.floor((N - 1) / s), Math.floor((mean + 7 * sd) / s));
    const lp = Math.log(p), lq = Math.log(q), lf = D.lf;
    let sum = 0;
    for (let k = lo; k <= hi; k++) { const v = k * s; sum += Math.exp(lf[N] - lf[v] - lf[N - v] + v * lp + (N - v) * lq); }
    return sum;
  }

  // ---------------------------------------------------------------- tests (02_analyze.py)
  function lastDigit(x) {
    const o = new Float64Array(10);
    let tot = 0;
    for (let i = 0; i < x.length; i++) if (x[i] >= 10) { o[x[i] % 10]++; tot++; }
    const e = tot / 10;
    let chi = 0;
    for (const v of o) chi += ((v - e) * (v - e)) / e;
    return { p: gammq(4.5, chi / 2), pct0: (100 * o[0]) / tot };
  }
  function heaping(x) {
    let mx = 0;
    for (let i = 0; i < x.length; i++) if (x[i] > mx) mx = x[i];
    const f = new Float64Array(mx + 1);
    for (let i = 0; i < x.length; i++) f[x[i]]++;
    let cum = 0, top = 0;
    const tot = x.length;
    for (; top < f.length; top++) { cum += f[top]; if (cum / tot >= 0.995) break; }
    const oe = (vs) => {
      let O = 0, E = 0, k = 0;
      for (const v of vs) if (v >= 1 && v + 1 < f.length && v <= top) { O += f[v]; E += (f[v - 1] + f[v + 1]) / 2; k++; }
      return [O, E, k];
    };
    const r10 = [];
    for (let v = 10; v <= top; v += 10) r10.push(v);
    const [O, E, k] = oe(r10);
    const [Oc, Ec] = oe([...r10.map((v) => v - 3), ...r10.map((v) => v - 2), ...r10.map((v) => v + 2), ...r10.map((v) => v + 3)]);
    const hc = Oc / Ec;
    return { ratio: E ? O / E / hc : NaN, z: k ? (O - E * hc) / Math.sqrt(O + (E / 2) * hc * hc) : NaN };
  }
  function tests(L, F, C, touched, L1 = D.L1, F1 = D.F1) {
    const { n, P, A, C1, A1, model } = D;
    const r = {};
    r.ldL = lastDigit(L); r.ldF = lastDigit(F); r.ldC = lastDigit(C);
    r.hpL = heaping(L); r.hpF = heaping(F); r.hpC = heaping(C);

    // whole percentages: observed vs binomial expectation
    let oL = 0, oT = 0;
    for (let i = 0; i < n; i++) {
      const v = L[i] + F[i];
      if (L[i] > 0 && L[i] < v && (100 * L[i]) % v === 0) oL++;
      if (C[i] > 0 && C[i] < A[i] && (100 * C[i]) % A[i] === 0) oT++;
    }
    let eL = 0, vL = 0, eT = 0, vT = 0;
    if (!touched) {
      for (let i = 0; i < n; i++) { eL += D.pL[i]; vL += D.pL[i] * (1 - D.pL[i]); eT += D.pT[i]; vT += D.pT[i] * (1 - D.pT[i]); }
      D.intBase = { eL, vL, eT, vT };
    } else {
      ({ eL, vL, eT, vT } = D.intBase);
      for (const i of touched) {
        const a = pInt(L[i], L[i] + F[i]);
        eL += a - D.pL[i]; vL += a * (1 - a) - D.pL[i] * (1 - D.pL[i]);
        if (C[i] === D.C[i]) continue; // turnout untouched (vote flips, rewritten numbers)
        const b = pInt(C[i], A[i]);
        eT += b - D.pT[i]; vT += b * (1 - b) - D.pT[i] * (1 - D.pT[i]);
      }
    }
    r.intL = { obs: oL, exp: eL, z: (oL - eL) / Math.sqrt(vL) };
    r.intT = { obs: oT, exp: eT, z: (oT - eT) / Math.sqrt(vT) };

    // each section vs the rest of its polling place (Lula share); round 1 -> 2 swing, same idea
    const z = new Float64Array(n).fill(NaN), dL = new Float64Array(n);
    const sw = new Float64Array(n).fill(NaN), dt = new Float64Array(n).fill(NaN);
    for (let k = 0; k + 1 < P.length; k++) {
      const s = P[k], e = P[k + 1], size = e - s;
      let sl = 0, sn = 0, ss = 0, sd = 0;
      for (let i = s; i < e; i++) {
        sl += L[i]; sn += L[i] + F[i];
        const v1 = L1[i] + F1[i];
        sw[i] = v1 > 0 ? L[i] / (L[i] + F[i]) - L1[i] / v1 : NaN;
        dt[i] = C[i] / A[i] - C1[i] / A1[i];
        if (!Number.isNaN(sw[i])) ss += sw[i];
        if (!Number.isNaN(dt[i])) sd += dt[i];
      }
      const pool = sl / sn;
      for (let i = s; i < e; i++) {
        const ni = L[i] + F[i], rn = sn - ni;
        if (rn > 0) {
          const pr = (sl - L[i]) / rn, pi = L[i] / ni;
          const v = pool * (1 - pool) * (1 / ni + 1 / rn);
          const zi = (pi - pr) / Math.sqrt(v);
          if (Number.isFinite(zi)) { z[i] = zi; dL[i] = pi - pr; }
        }
        if (size > 1) {
          sw[i] = sw[i] - (ss - (Number.isNaN(sw[i]) ? 0 : sw[i])) / (size - 1);
          dt[i] = dt[i] - (sd - (Number.isNaN(dt[i]) ? 0 : dt[i])) / (size - 1);
        } else { sw[i] = NaN; dt[i] = NaN; }
      }
    }
    let pos = 0, neg = 0;
    const zs = [];
    for (let i = 0; i < n; i++) if (!Number.isNaN(z[i])) { zs.push(z[i]); if (z[i] > 4) pos++; if (z[i] < -4) neg++; }
    const zf = Float64Array.from(zs), zmed = median(zf);
    const rsd = 1.4826 * median(zf.map((v) => Math.abs(v - zmed)));
    r.place = { pos, neg, rsd };

    // turnout >= 95% and a candidate >= 90%, sections with 100+ voters
    let cl = 0, cf = 0;
    for (let i = 0; i < n; i++) {
      if (A[i] < 100 || C[i] / A[i] < 0.95) continue;
      const v = L[i] + F[i];
      if (L[i] / v >= 0.9) cl++;
      if (F[i] / v >= 0.9) cf++;
    }
    r.corner = { lula: cl, flavio: cf };

    // machine model vs same polling place: weighted mean of (section share - rest of place). Its noise
    // comes from the spread of the sections themselves, so tampering spread over every model does not
    // read as a model effect; only a gap that stands out from that spread does.
    const nm = D.meta.models.length, num = new Float64Array(nm), den = new Float64Array(nm);
    for (let i = 0; i < n; i++) {
      if (Number.isNaN(z[i])) continue;
      const w = L[i] + F[i];
      num[model[i]] += dL[i] * w; den[model[i]] += w;
    }
    const sq = new Float64Array(nm);
    for (let i = 0; i < n; i++) {
      if (Number.isNaN(z[i])) continue;
      const w = L[i] + F[i], d = dL[i] - num[model[i]] / den[model[i]];
      sq[model[i]] += w * w * d * d;
    }
    // compared with the average of all models: tampering spread evenly over the country shifts every
    // model alike, which is not a model effect
    let all = 0, wAll = 0;
    for (let m = 0; m < nm; m++) { all += num[m]; wAll += den[m]; }
    all /= wAll;
    let gap = 0, t = 0;
    for (let m = 0; m < nm; m++) {
      if (!den[m]) continue;
      const g = num[m] / den[m] - all, s = Math.sqrt(sq[m]) / den[m];
      if (Math.abs(g) > Math.abs(gap)) gap = g;
      if (Math.abs(g / s) > Math.abs(t)) t = g / s;
    }
    r.model = { gap: 100 * gap, t };

    // swing residuals in robust-sd units; turnout rise vs swing within polling place
    const rs = [];
    for (let i = 0; i < n; i++) if (!Number.isNaN(sw[i])) rs.push(sw[i]);
    const rf = Float64Array.from(rs), rmed = median(rf), srsd = 1.4826 * median(rf.map((v) => Math.abs(v - rmed)));
    let sp = 0, sn2 = 0;
    for (const v of rf) { if (v / srsd > 4) sp++; if (v / srsd < -4) sn2++; }
    let k = 0, mx = 0, my = 0;
    for (let i = 0; i < n; i++) if (!Number.isNaN(sw[i]) && !Number.isNaN(dt[i])) { k++; mx += dt[i]; my += sw[i]; }
    mx /= k; my /= k;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) if (!Number.isNaN(sw[i]) && !Number.isNaN(dt[i])) {
      const a = dt[i] - mx, b = sw[i] - my;
      sxy += a * b; sxx += a * a; syy += b * b;
    }
    r.swing = { pos: sp, neg: sn2, corr: sxy / Math.sqrt(sxx * syy), pairs: k };
    return r;
  }

  // ---------------------------------------------------------------- fraud
  // opens on the real result (no fraud); a tampered machine runs the same program in both rounds
  const START = { ben: 'flavio', type: 'software', where: 'random', model: 0, machines: 2000, intensity: 0, both: true };
  const state = { ...START, uf: 0, seed: 1 };
  const SOFTWARE = (type) => type === 'software' || type === 'flip';

  function order(key) {
    if (D.order[key]) return D.order[key];
    const { n, L, F, model, uf } = D;
    let idx;
    if (key.startsWith('random') || key.startsWith('model') || key.startsWith('uf')) {
      const r = mulberry32(state.seed * 7919 + 17);
      idx = new Int32Array(n);
      for (let i = 0; i < n; i++) idx[i] = i;
      for (let i = n - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [idx[i], idx[j]] = [idx[j], idx[i]]; }
      const [kind, v] = key.split(':');
      if (kind === 'model') idx = idx.filter((i) => model[i] === Number(v));
      if (kind === 'uf') idx = idx.filter((i) => uf[i] === Number(v));
    } else {
      // strongholds: highest share first
      const share = new Float64Array(n);
      const num = key === 'lula' ? L : F;
      for (let i = 0; i < n; i++) share[i] = num[i] / (L[i] + F[i]);
      idx = new Int32Array(n);
      for (let i = 0; i < n; i++) idx[i] = i;
      idx.sort((a, b) => share[b] - share[a] || a - b);
    }
    D.order[key] = idx;
    return idx;
  }
  function targets() {
    const victim = state.ben === 'lula' ? 'flavio' : 'lula';
    const key = { random: `random:${state.seed}`, reduto_adv: victim, reduto_ben: state.ben, model: `model:${state.model}:${state.seed}`, uf: `uf:${state.uf}:${state.seed}` }[state.where];
    return order(key);
  }

  // per-machine change in the margin for the "minimum to flip" helper: expected value and variance
  // (each machine's flips are drawn at random; hand-written numbers are rounded to 5 or 10)
  function gainOf(i, B, V, A, C) {
    const x = state.intensity / 100;
    if (state.type === 'stuff') return { mean: Math.max(0, Math.min(A[i], Math.ceil(x * A[i])) - C[i]), var: 0 };
    if (state.type === 'invent') return { mean: 2 * x * V[i], var: 27 };
    return { mean: 2 * x * V[i], var: 4 * V[i] * x * (1 - x) };
  }

  function apply() {
    const { n, L: L0, F: F0, C: C0, A } = D;
    const L = Uint16Array.from(L0), F = Uint16Array.from(F0), C = Uint16Array.from(C0);
    const [B, V] = state.ben === 'lula' ? [L, F] : [F, L];
    const r = mulberry32(state.seed);
    const x = state.intensity / 100;
    let touched = [], moved = 0;
    const list = state.type === 'software' ? null : targets().subarray(0, Math.min(state.machines, targets().length));
    const each = (fn) => { if (list) for (const i of list) fn(i); else for (let i = 0; i < n; i++) fn(i); };
    if (x > 0) each((i) => {
      if (state.type === 'software' || state.type === 'flip') {
        const k = binom(V[i], x, r);
        if (k) { V[i] -= k; B[i] += k; moved += k; touched.push(i); }
      } else if (state.type === 'stuff') {
        const add = Math.max(0, Math.min(A[i], Math.ceil(x * A[i])) - C[i]);
        if (add) { B[i] += add; C[i] += add; moved += add; touched.push(i); }
      } else {
        // numbers rewritten by hand: move part of the victim's votes, then write round-looking numbers
        const tot = B[i] + V[i];
        let b = B[i] + Math.round(x * V[i]);
        const u = r();
        if (u < 0.55) b = Math.round(b / 10) * 10; else if (u < 0.8) b = Math.round(b / 5) * 5;
        b = Math.min(tot, Math.max(B[i], b));
        if (b !== B[i]) { moved += b - B[i]; B[i] = b; V[i] = tot - b; touched.push(i); }
      }
    });
    // the same program in the same machines also flips round-1 votes, unless the reader unticks it
    let L1 = D.L1, F1 = D.F1;
    if (x > 0 && state.both && SOFTWARE(state.type)) {
      L1 = Uint16Array.from(D.L1); F1 = Uint16Array.from(D.F1);
      const [B1, V1] = state.ben === 'lula' ? [L1, F1] : [F1, L1];
      each((i) => { const k = binom(V1[i], x, r); B1[i] += k; V1[i] -= k; });
    }
    // machines carrying the fraud: all of them for the software, the chosen ones otherwise
    const machines = x > 0 ? (list ? list.length : n) : 0;
    return { L, F, C, L1, F1, touched, moved, machines, list: x > 0 ? list : null };
  }

  // smallest number of machines (or software rate) that would hand the win to the trailing candidate
  function minimumToFlip() {
    const { n, L, F, C, A } = D;
    const [B, V] = state.ben === 'lula' ? [L, F] : [F, L];
    let need = 0;
    for (let i = 0; i < n; i++) need += V[i] - B[i];
    // the beneficiary already won: size the fraud that would have manufactured that win. Detection
    // depends on the fraud's size and pattern, not on who won, so it is laid on top of the real data.
    const fabricate = need < 0;
    need = Math.abs(need);
    // ask for 4 standard deviations of room, so the random draw almost never falls short
    if (state.type === 'software') {
      let sv = 0;
      for (let i = 0; i < n; i++) sv += V[i];
      let p = (need / 2 + 1) / sv;
      for (let k = 0; k < 3; k++) p = (need / 2 + 1 + 4 * Math.sqrt(sv * p * (1 - p))) / sv;
      return { rate: Math.ceil(1000 * p) / 10, fabricate };
    }
    const idx = targets();
    let gain = 0, v = 0;
    for (let k = 0; k < idx.length; k++) {
      const g = gainOf(idx[k], B, V, A, C);
      gain += g.mean; v += g.var;
      if (gain > need + 4 * Math.sqrt(v)) return { machines: k + 1, fabricate };
    }
    return { impossible: true, available: idx.length, fabricate };
  }

  const winner = () => (D.meta.totals.lula > D.meta.totals.flavio ? 'lula' : 'flavio');

  // ---------------------------------------------------------------- verdicts
  const REF = () => D.meta.reference;
  function verdicts(t) {
    const b = D.base, r22 = REF()['2022'];
    const pv = (p) => (p < 0.0001 ? 'p < 0,0001' : `p = ${dec(p, p < 0.01 ? 4 : 2)}`);
    const count = (now, base) => now - base > 4 * Math.sqrt(base + 1);
    const rows = [
      { g: 'Números redondos', label: 'Último dígito dos votos de Lula', what: 'Números inventados à mão não terminam em 0 a 9 por igual.', real: pv(b.ldL.p), now: pv(t.ldL.p), bad: t.ldL.p < 0.001 },
      { g: 'Números redondos', label: 'Último dígito dos votos de Flávio', real: pv(b.ldF.p), now: pv(t.ldF.p), bad: t.ldF.p < 0.001 },
      { g: 'Números redondos', label: 'Último dígito do comparecimento', real: pv(b.ldC.p), now: pv(t.ldC.p), bad: t.ldC.p < 0.001 },
      { g: 'Números redondos', label: 'Excesso de 10, 20, 30… nos votos de Lula', what: 'Quantas vezes mais aparecem os números redondos que os vizinhos.', real: `×${dec(b.hpL.ratio, 2)}`, now: `×${dec(t.hpL.ratio, 2)}`, bad: t.hpL.z > 4 },
      { g: 'Números redondos', label: 'Excesso de 10, 20, 30… nos votos de Flávio', real: `×${dec(b.hpF.ratio, 2)}`, now: `×${dec(t.hpF.ratio, 2)}`, bad: t.hpF.z > 4 },
      { g: 'Números redondos', label: 'Excesso de 10, 20, 30… no comparecimento', real: `×${dec(b.hpC.ratio, 2)}`, now: `×${dec(t.hpC.ratio, 2)}`, bad: t.hpC.z > 4 },
      { g: 'Números redondos', label: 'Urnas com percentual exato de Lula (50%, 61%…)', what: 'Comparado com o que o acaso daria.', real: int(b.intL.obs), now: int(t.intL.obs), bad: t.intL.z > 4, note: `o acaso daria cerca de ${int(t.intL.exp)}` },
      { g: 'Números redondos', label: 'Urnas com comparecimento em percentual exato', real: int(b.intT.obs), now: int(t.intT.obs), bad: t.intT.z > 4, note: `o acaso daria cerca de ${int(t.intT.exp)}` },
      { g: 'Urnas vizinhas', label: 'Urnas que destoam do seu local a favor de Lula', what: 'Comparadas às outras urnas do mesmo local de votação (z > 4).', real: int(b.place.pos), now: int(t.place.pos), bad: count(t.place.pos, b.place.pos), note: `em 2022: ${int(r22.place_pos4)}` },
      { g: 'Urnas vizinhas', label: 'Urnas que destoam do seu local a favor de Flávio', real: int(b.place.neg), now: int(t.place.neg), bad: count(t.place.neg, b.place.neg), note: `em 2022: ${int(r22.place_neg4)}` },
      { g: 'Urnas vizinhas', label: 'Comparecimento ≥ 95% e Lula ≥ 90%', what: 'A “impressão digital” de urnas engordadas. Nos dados reais, já chamou atenção (pergunta 4).', real: int(b.corner.lula), now: int(t.corner.lula), bad: count(t.corner.lula, b.corner.lula), note: `em 2022: ${int(r22.corner_lula)}` },
      { g: 'Urnas vizinhas', label: 'Comparecimento ≥ 95% e Flávio ≥ 90%', real: int(b.corner.flavio), now: int(t.corner.flavio), bad: count(t.corner.flavio, b.corner.flavio), note: `em 2022, Jair: ${int(r22.corner_right)}` },
      { g: 'Urnas vizinhas', label: 'Maior diferença entre modelos de urna no mesmo local', what: 'Um programa adulterado em um modelo só apareceria aqui.', real: `${dec(b.model.gap, 2)} p.p.`, now: `${dec(t.model.gap, 2)} p.p.`, bad: Math.abs(t.model.t) > 4 },
      { g: 'Entre os turnos', label: 'Urnas que viraram para Lula bem mais que as vizinhas', what: 'Mudança do 1º para o 2º turno, comparada ao resto do local.', real: int(b.swing.pos), now: int(t.swing.pos), bad: count(t.swing.pos, b.swing.pos), note: `em 2022: ${int(r22.swing_pos4)}` },
      { g: 'Entre os turnos', label: 'Urnas que viraram para Flávio bem mais que as vizinhas', real: int(b.swing.neg), now: int(t.swing.neg), bad: count(t.swing.neg, b.swing.neg), note: `em 2022: ${int(r22.swing_neg4)}` },
      { g: 'Entre os turnos', label: 'Comparecimento subindo junto com a virada, no mesmo local', what: 'Votos “a mais” costumam vir com mais comparecimento.', real: dec(b.swing.corr, 3), now: dec(t.swing.corr, 3), bad: (Math.abs(t.swing.corr) - Math.abs(b.swing.corr)) * Math.sqrt(t.swing.pairs) > 4 },
    ];
    return rows;
  }

  // ---------------------------------------------------------------- UI
  const ui = {};
  function machinesMax() { return state.type === 'software' ? D.n : targets().length; }
  function sliderToMachines(v, max) { return Math.max(1, Math.round(Math.pow(max, v / 1000))); }
  function machinesToSlider(m, max) { return Math.round((1000 * Math.log(Math.max(1, m))) / Math.log(max)); }
  const INTENSITY = {
    software: { label: 'Votos do adversário trocados em cada urna', min: 0, max: 20, step: 0.1, unit: '%' },
    flip: { label: 'Votos do adversário trocados em cada urna adulterada', min: 1, max: 100, step: 1, unit: '%' },
    stuff: { label: 'Comparecimento que as urnas adulteradas passam a ter', min: 80, max: 100, step: 1, unit: '%' },
    invent: { label: 'Votos do adversário passados para o seu candidato', min: 1, max: 100, step: 1, unit: '%' },
  };

  function syncControls() {
    for (const b of ui.ben.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.v === state.ben));
    for (const r of page.querySelectorAll('input[name="sim-type"]')) r.checked = r.value === state.type;
    const some = state.type !== 'software';
    ui.machinesRow.hidden = !some; ui.whereRow.hidden = !some;
    ui.modelSel.hidden = state.where !== 'model'; ui.ufSel.hidden = state.where !== 'uf';
    const it = INTENSITY[state.type];
    ui.intLabel.textContent = it.label;
    Object.assign(ui.intRange, { min: it.min, max: it.max, step: it.step });
    state.intensity = Math.min(it.max, Math.max(it.min, state.intensity));
    ui.intRange.value = state.intensity;
    ui.intOut.value = `${dec(state.intensity, it.step < 1 ? 1 : 0)}${it.unit}`;
    if (some) {
      const max = machinesMax();
      state.machines = Math.min(max, Math.max(1, state.machines));
      ui.machRange.value = machinesToSlider(state.machines, max);
      if (document.activeElement !== ui.machNum) ui.machNum.value = state.machines;
      ui.machNum.max = max;
      ui.machOf.textContent = `de ${int(max)} (${pct(state.machines / D.n, state.machines / D.n < 0.01 ? 2 : 1)} das urnas do país)`;
    }
    ui.where.value = state.where;
    ui.bothRow.hidden = !SOFTWARE(state.type); ui.roundNote.hidden = SOFTWARE(state.type);
    ui.minBtn.textContent = state.ben === winner() ? `Do tamanho da vitória de ${NAME[state.ben]}` : 'Mínimo para virar o resultado';
    ui.both.checked = state.both;
  }

  // a timer, not requestAnimationFrame: the recompute (about 0.2 s) yields first so the busy state paints,
  // and a slider drag only recomputes for the latest value
  let pending = 0;
  function update() {
    clearTimeout(pending);
    ui.app.classList.add('vf-sim-busy');
    pending = setTimeout(() => {
      const f = apply();
      render(f, f.touched.length ? tests(f.L, f.F, f.C, f.touched, f.L1, f.F1) : D.base);
      ui.app.classList.remove('vf-sim-busy');
    }, 30);
  }

  function render(f, t) {
    let l = 0, fl = 0;
    for (let i = 0; i < D.n; i++) { l += f.L[i]; fl += f.F[i]; }
    const tot = l + fl, win = l > fl ? 'lula' : 'flavio', flipped = win !== 'lula';
    const sim = f.moved > 0, tag = sim ? ' · simulação' : '';
    const share = pct(f.machines / D.n, f.machines / D.n < 0.01 ? 2 : 1);
    const how = {
      software: () => `O programa está em todas as ${int(f.machines)} urnas e trocou ${int(f.moved)} votos no 2º turno${state.both ? ' (e também votos no 1º)' : ''}.`,
      flip: () => `${int(f.machines)} urnas adulteradas (${share} das urnas) trocaram ${int(f.moved)} votos no 2º turno${state.both ? ' (e também votos no 1º)' : ''}.`,
      stuff: () => `${int(f.moved)} votos a mais, de eleitores ausentes, em ${int(f.machines)} urnas (${share} das urnas).`,
      invent: () => `${int(f.machines)} boletins reescritos (${share} das urnas) passaram ${int(f.moved)} votos para ${NAME[state.ben]}.`,
    }[state.type];
    const T = D.meta.totals, realTot = T.lula + T.flavio;
    const forWinner = sim && state.ben === winner(), margin = Math.abs(T.lula - T.flavio);
    const needed = state.type === 'stuff' ? `acrescentar pelo menos ${int(margin + 1)} votos` : `mover pelo menos ${int(Math.floor(margin / 2) + 1)} votos`;
    ui.result.innerHTML = `
      <p class="vf-sim-flag${sim ? '' : ' vf-sim-real'}">${sim ? 'SIMULAÇÃO · não é o resultado real' : 'Resultado real do 2º turno, sem fraude'}</p>
      <div class="vf-sim-totals">
        <div class="vf-sim-cand" data-c="lula"><span>Lula${tag}</span><b>${int(l)}</b><span>${pct(l / tot, 2)}</span></div>
        <div class="vf-sim-cand" data-c="flavio"><span>Flávio${tag}</span><b>${int(fl)}</b><span>${pct(fl / tot, 2)}</span></div>
      </div>
      <div class="vf-sim-bar" aria-hidden="true"><i style="width:${(100 * l) / tot}%"></i></div>
      <p class="vf-sim-verdict"><span class="vf-chip ${forWinner ? 'vf-warn' : flipped ? 'vf-bad' : 'vf-ok'}">${forWinner ? `Fraude a favor de ${NAME[state.ben]}` : sim ? (flipped ? 'A simulação virou o resultado' : 'A simulação não virou o resultado') : 'Resultado real'}</span>
      ${sim ? `${how()} Na simulação, vence ${NAME[win]}, por ${int(Math.abs(l - fl))} votos.` : `Lula venceu por ${int(l - fl)} votos.`}</p>
      ${sim ? `<p class="vf-sim-realline">Resultado real: Lula ${int(T.lula)} (${pct(T.lula / realTot, 2)}), Flávio ${int(T.flavio)} (${pct(T.flavio / realTot, 2)}).${forWinner ? ` Uma fraude que tivesse fabricado essa vitória precisaria ${needed}; esta, aplicada por cima dos dados reais, mexe em ${int(f.moved)}.` : ''}</p>` : ''}`;

    const rows = verdicts(t);
    const bad = rows.filter((r) => r.bad).length;
    ui.score.innerHTML = !sim ? 'Sem fraude, não há o que aparecer: os números são os reais. Escolha uma fraude ao lado.'
      : bad ? `<b>A fraude aparece em ${bad} dos ${rows.length} testes.</b>`
        : `<b>A fraude não aparece em nenhum dos ${rows.length} testes.</b> ${state.type === 'software' ? `Uma troca igual em todas as urnas parece um eleitorado que mudou um pouco de ideia: nos números, as duas coisas são idênticas${forWinner ? `, e por isso os números sozinhos não descartam uma fraude assim a favor de ${NAME[state.ben]}` : ''}.` : 'Ela é pequena demais, ou espalhada demais, para deixar marca nos números.'}`;
    if (sim && !bad && state.type === 'software') ui.score.innerHTML += ` <b>Mas o teste de integridade a pegaria:</b> com o programa em todas as urnas, as urnas sorteadas para o teste também estariam adulteradas, e ${swapped()}. Basta um voto trocado para o boletim não bater com as cédulas de papel.`;
    else if (sim && !bad && state.type === 'flip') ui.score.innerHTML += ` Fora destes números, a chance de o teste de integridade sortear pelo menos uma das ${int(f.machines)} urnas adulteradas é de <b>${integrity(f.machines).chance}</b>.`;
    if (forWinner && bad) ui.score.innerHTML += ` Se a vitória de ${NAME[state.ben]} tivesse vindo de uma fraude assim, os números reais teriam essas marcas. Compare a coluna Real com 2022, anotado abaixo de cada número.`;
    let g = '';
    ui.tbody.innerHTML = rows.map((r) => {
      const head = r.g !== g ? `<tr class="vf-sim-group"><th colspan="4" scope="colgroup">${(g = r.g)}</th></tr>` : '';
      return `${head}<tr${r.bad ? ' class="vf-sim-hit"' : ''}><th scope="row">${r.label}${r.what ? `<small>${r.what}</small>` : ''}</th><td class="vf-n">${r.real}</td><td class="vf-n">${r.now}${r.note ? `<small>${r.note}</small>` : ''}</td><td><span class="vf-chip ${r.bad ? 'vf-bad' : 'vf-ok'}">${r.bad ? 'Sim' : 'Não'}</span></td></tr>`;
    }).join('');
    renderOutside(f);
    announce(sim ? `Simulação: vence ${NAME[win]}, por ${int(Math.abs(l - fl))} votos. A fraude aparece em ${bad} dos ${rows.length} testes${!bad && state.type === 'software' ? ', mas o teste de integridade a pegaria' : ''}.` : 'Resultado real, sem fraude.');
  }
  // one short summary for screen readers, once the controls stop moving
  let said = 0;
  function announce(text) {
    clearTimeout(said);
    said = setTimeout(() => { ui.status.textContent = text; }, 900);
  }

  // chance that the integrity test draws at least one of M tampered machines (hypergeometric)
  function integrity(M) {
    const N = D.n, a = D.meta.integrity_test_machines;
    let pMiss = 1;
    for (let j = 0; j < a && pMiss > 1e-300; j++) pMiss *= (N - M - j) / (N - j);
    const pHit = M ? 1 - Math.max(0, pMiss) : 0;
    return { pHit, chance: pHit > 0.999999 ? 'praticamente 100%' : pHit < 0.0001 && M ? 'menos de 0,01%' : pct(pHit, pHit > 0.99 ? 2 : 1) };
  }
  // what a tampered machine does to the known votes typed in during the integrity test
  const swapped = () => `${Number.isInteger(state.intensity) ? state.intensity : dec(state.intensity)}% dos votos de ${NAME[state.ben === 'lula' ? 'flavio' : 'lula']} digitados no teste sairiam no boletim como votos de ${NAME[state.ben]}`;

  function renderOutside(f) {
    const N = D.n, a = D.meta.integrity_test_machines;
    const M = f.machines;
    const { pHit, chance } = integrity(M);
    const sw = SOFTWARE(state.type);
    let html;
    if (!M) html = '<p>Sem fraude, não há nada para os controles de fora destes dados encontrarem.</p>';
    else if (sw) html = `<p class="vf-sim-verdict"><span class="vf-chip ${pHit > 0.99 ? 'vf-bad' : 'vf-warn'}">${M === N ? 'O teste de integridade pegaria' : `${chance} de chance de ser pega`}</span></p>
      <p><b>Teste de integridade:</b> no dia da eleição, cerca de ${int(a)} urnas sorteadas (de 20 a 33 por estado) são trocadas por urnas reservas, e as originais recebem, em um local público e com filmagem, votos conhecidos de cédulas de papel. O boletim tem de bater com as cédulas. ${M === N ? `Com o programa em todas as urnas, todas as urnas do teste estariam adulteradas: ${swapped()}. Basta um voto trocado para o boletim não bater` : `Com ${int(M)} urnas adulteradas entre ${int(N)}, a chance de pelo menos uma ser sorteada é de <b>${chance}</b>; numa urna adulterada, ${swapped()}`}.</p>
      <p class="vf-sim-actions"><button type="button" class="vf-btn" id="sim-draw">Sortear as ${int(a)} urnas do teste</button> <span id="sim-draw-out" aria-live="polite"></span></p>
      <p class="vf-sim-note">Isso vale se o programa adulterado não souber distinguir o teste de uma votação real; por isso o teste é filmado e, desde 2022, usa a biometria de eleitores de verdade. O teste de autenticidade confere, em outras urnas sorteadas, a assinatura digital do programa instalado.</p>`;
    else if (state.type === 'stuff') html = `<p><b>Encher urnas é feito por pessoas, não pelo programa</b>, então o teste de integridade não pega. Quem pega: os fiscais dos partidos dentro da seção, a identificação de cada eleitor (biometria ou liberação manual pelo mesário, registrada no registro de eventos da urna, que é público) e a pergunta 8 desta página, que olha esses registros. Votar no lugar de ${int(f.moved)} ausentes exigiria a cumplicidade dos mesários de ${int(M)} seções.</p>`;
    else html = `<p><b>Reescrever o boletim depois da votação</b> esbarra no boletim impresso: uma via fica afixada na seção ao fim da votação, com QR code, e os fiscais e qualquer eleitor podem fotografá-la. O arquivo publicado tem assinatura digital da urna. Um boletim com números diferentes dos impressos seria descoberto por comparação direta, sem estatística nenhuma.</p>`;
    ui.outside.innerHTML = html;
    const btn = document.getElementById('sim-draw');
    if (btn) btn.addEventListener('click', () => {
      const r = mulberry32((Date.now() & 0xffffffff) ^ state.seed);
      const hit = f.list ? new Set(f.list) : null; // null: the software is in every machine
      let found = 0;
      const seen = new Set();
      while (seen.size < a) { const i = Math.floor(r() * N); if (!seen.has(i)) { seen.add(i); if (!hit || hit.has(i)) found++; } }
      document.getElementById('sim-draw-out').innerHTML = found
        ? `<span class="vf-chip vf-bad">Descoberta</span> ${found === a ? `Todas as ${int(a)} urnas sorteadas` : `${int(found)} das ${int(a)} urnas sorteadas`} estavam adulteradas.`
        : '<span class="vf-chip vf-ok">Passou</span> Nenhuma urna adulterada foi sorteada desta vez.';
    });
  }

  function bind() {
    ui.app = $('sim-app');
    ui.ben = $('sim-ben'); ui.where = $('sim-where'); ui.modelSel = $('sim-model'); ui.ufSel = $('sim-uf');
    ui.machinesRow = $('sim-machines-row'); ui.whereRow = $('sim-where-row');
    ui.machRange = $('sim-machines'); ui.machNum = $('sim-machines-n'); ui.machOf = $('sim-machines-of');
    ui.intRange = $('sim-intensity'); ui.intOut = $('sim-intensity-out'); ui.intLabel = $('sim-intensity-lbl');
    ui.result = $('sim-result'); ui.score = $('sim-score'); ui.tbody = page.querySelector('#sim-tests tbody'); ui.outside = $('sim-outside');
    ui.minNote = $('sim-min-note'); ui.status = $('sim-status'); ui.minBtn = $('sim-min');
    ui.both = $('sim-both'); ui.bothRow = $('sim-both-row'); ui.roundNote = $('sim-round-note');
    page.querySelector('.vf-sim-controls').addEventListener('submit', (ev) => ev.preventDefault());
    ui.modelSel.innerHTML = D.meta.models.map((m, i) => `<option value="${i}">${m}</option>`).join('');
    ui.ufSel.innerHTML = D.meta.ufs.map((u, i) => `<option value="${i}">${u === 'ZZ' ? 'Exterior' : u}</option>`).join('');
    ui.ufSel.value = D.meta.ufs.indexOf('SP');
    state.uf = Number(ui.ufSel.value);

    ui.ben.addEventListener('click', (ev) => { const b = ev.target.closest('button[data-v]'); if (b) { state.ben = b.dataset.v; changed(); } });
    for (const r of page.querySelectorAll('input[name="sim-type"]')) r.addEventListener('change', () => { state.type = r.value; state.intensity = { software: 3.5, flip: 30, stuff: 100, invent: 30 }[r.value]; changed(); });
    ui.where.addEventListener('change', () => { state.where = ui.where.value; changed(); });
    ui.modelSel.addEventListener('change', () => { state.model = Number(ui.modelSel.value); changed(); });
    ui.ufSel.addEventListener('change', () => { state.uf = Number(ui.ufSel.value); changed(); });
    ui.machRange.addEventListener('input', () => { state.machines = sliderToMachines(Number(ui.machRange.value), machinesMax()); changed(); });
    ui.machNum.addEventListener('change', () => { const v = Math.round(Number(ui.machNum.value)); if (v > 0) { state.machines = v; changed(); } });
    ui.intRange.addEventListener('input', () => { state.intensity = Number(ui.intRange.value); changed(); });
    ui.both.addEventListener('change', () => { state.both = ui.both.checked; changed(); });
    $('sim-reseed').addEventListener('click', () => { state.seed += 1; D.order = Object.fromEntries(Object.entries(D.order).filter(([k]) => !/random|model|uf/.test(k))); changed(); });
    $('sim-reset').addEventListener('click', () => { Object.assign(state, START); ui.minNote.textContent = ''; changed(); });
    $('sim-min').addEventListener('click', () => {
      const m = minimumToFlip();
      const who = NAME[state.ben], victim = NAME[state.ben === 'lula' ? 'flavio' : 'lula'];
      const over = ' A simulação aplica essa fraude por cima dos dados reais, para mostrar as marcas que ela deixaria.';
      if (m.impossible) ui.minNote.textContent = m.fabricate
        ? `Nem adulterando todas as ${int(m.available)} urnas deste grupo, com esta intensidade, daria para fabricar a vitória de ${who}. Aumente a intensidade ou escolha outro grupo.`
        : `Nem adulterando todas as ${int(m.available)} urnas deste grupo, com esta intensidade, o resultado viraria. Aumente a intensidade ou escolha outro grupo.`;
      else if (m.rate !== undefined) {
        if (m.rate > INTENSITY.software.max) { ui.minNote.textContent = `Seria preciso trocar ${dec(m.rate)}% dos votos de ${victim} em cada urna.`; return; }
        state.intensity = m.rate;
        ui.minNote.textContent = m.fabricate
          ? `Para fabricar a vitória de ${who}, o programa teria de trocar cerca de ${dec(m.rate)}% dos votos de ${victim} em cada urna.${over}`
          : `Basta trocar ${dec(m.rate)}% dos votos de ${victim} em cada urna do país.`;
      } else {
        state.machines = m.machines;
        ui.minNote.textContent = m.fabricate
          ? `Para fabricar a vitória de ${who} assim, seriam necessárias pelo menos ${int(m.machines)} urnas adulteradas.${over}`
          : `Mínimo: ${int(m.machines)} urnas adulteradas, com uma pequena folga, porque o efeito em cada urna é sorteado.`;
      }
      changed();
    });
    syncControls();
  }
  function changed() { syncControls(); update(); }

  // load once, the first time the tab is shown
  let started = false;
  async function start() {
    if (started || page.hidden) return;
    started = true;
    const box = $('sim-loading');
    try {
      await load();
      box.hidden = true;
      $('sim-app').hidden = false;
      bind();
      update();
    } catch (e) {
      box.innerHTML = `<b>Não foi possível carregar a simulação.</b> ${e.message ?? ''}`;
      started = false;
    }
  }
  new MutationObserver(start).observe(page, { attributes: true, attributeFilter: ['hidden'] });
  start();
  window.vfSim = { state, tests: () => D && D.base, get data() { return D; } };
})();
