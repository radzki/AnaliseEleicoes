// "Tente fraudar!": the reader tampers with the 2026 runoff and sees what the page's tests would say.
// Data: data/sim/ (scripts/09_sim_data.py), every runoff section, loaded when the tab first opens.
// The tests are the same definitions as scripts/02_analyze.py, recomputed here on the tampered copy.
(() => {
  const page = document.getElementById('fraude');
  if (!page) return;
  const $ = (id) => document.getElementById(id);
  // the site's stand-in runtime resolves files from the site root (pages in /en/, /es/); claude.ai has none
  const dataUrl = (path) => (dash.url ? dash.url(path) : path);
  const nf = new Intl.NumberFormat(vf.t('locale.intl'));
  const int = (x) => nf.format(Math.round(x));
  const dec = (x, d = 1) => x.toLocaleString(vf.t('locale.intl'), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 1) => `${dec(100 * x, d)}%`;
  // reader text comes from vf.t, keys "sim.*"; `t` is taken here (test results, temporaries), so the alias is tr
  const tr = vf.t;
  const NAME = { lula: vf.cand.lula.name, flavio: vf.cand.flavio.name };

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
    const meta = await (await fetch(dataUrl('data/sim/meta.json'))).json();
    if (!('DecompressionStream' in window)) throw new Error(tr('sim.error.browser'));
    const res = await fetch(dataUrl('data/sim/secoes_2026_t2.bin'));
    if (!res.ok) throw new Error(tr('sim.error.not_found', { status: res.status }));
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
      C1: unzig('comparecimento_1', 'comparecimento'), A1: unzig('aptos_1', 'aptos'), O1: col.outros_1,
    };
    // sections of each state: the integrity test draws its machines state by state
    D.byUf = meta.ufs.map(() => []);
    for (let i = 0; i < n; i++) D.byUf[col.uf[i]].push(i);
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
    return { p: gammq(4.5, chi / 2), pct0: (100 * o[0]) / tot, freq: Array.from(o, (v) => v / tot) };
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
  // ---------------------------------------------------------------- tests of "Mais testes" (10_more_tests.py)
  // Section size: each section's Lula share minus the rest of its polling place's, then, along the section
  // size (turnout), the cut N with the largest step between the mean above and below it (t statistic)
  function sizeStep(L, F, C) {
    const { P } = D;
    let maxS = 0;
    for (let i = 0; i < C.length; i++) if (C[i] > maxS) maxS = C[i];
    const cnt = new Float64Array(maxS + 1), s1 = new Float64Array(maxS + 1), s2 = new Float64Array(maxS + 1);
    for (let k = 0; k + 1 < P.length; k++) {
      let sl = 0, sn = 0;
      for (let i = P[k]; i < P[k + 1]; i++) { sl += L[i]; sn += L[i] + F[i]; }
      for (let i = P[k]; i < P[k + 1]; i++) {
        const ni = L[i] + F[i], rn = sn - ni;
        if (rn <= 0 || ni <= 0) continue;
        const d = L[i] / ni - (sl - L[i]) / rn;
        cnt[C[i]]++; s1[C[i]] += d; s2[C[i]] += d * d;
      }
    }
    let m = 0, tot = 0, tot2 = 0;
    for (let v = 0; v <= maxS; v++) { m += cnt[v]; tot += s1[v]; tot2 += s2[v]; }
    // for the chart: the mean gap in bands of 25 voters, the last one 500 and over (as on the page)
    const curve = Array.from({ length: 21 }, (_, b) => ({ from: 25 * b, n: 0, sum: 0 }));
    for (let v = 0; v <= maxS; v++) if (cnt[v]) { const c = curve[Math.min(20, Math.floor(v / 25))]; c.n += cnt[v]; c.sum += s1[v]; }
    let best = { t: 0, at: null, step: 0 }, k = 0, c1 = 0, c2 = 0, v = 0;
    for (let N = 50; N <= 450; N += 5) {
      for (; v <= Math.min(N, maxS); v++) { k += cnt[v]; c1 += s1[v]; c2 += s2[v]; }
      if (k < 0.02 * m || m - k < 0.02 * m) continue;
      const mb = c1 / k, ma = (tot - c1) / (m - k);
      const vb = c2 / k - mb * mb, va = (tot2 - c2) / (m - k) - ma * ma;
      const tt = (ma - mb) / Math.sqrt(vb / k + va / (m - k));
      if (Math.abs(tt) > Math.abs(best.t)) best = { t: tt, at: N, step: 100 * (ma - mb) };
    }
    best.curve = curve.map((c) => ({ from: c.from, n: c.n, pp: c.n ? (100 * c.sum) / c.n : NaN }));
    return best;
  }
  // Shpilkin, state by state: in turnout bands of 0.5 point, each candidate's votes above the most common
  // band beyond what their share in that band predicts; summed over the states
  // the band edges as numpy.arange(0.5, 1.0001, 0.005) makes them, with the step taken as the gap between its
  // first two values (0.0050000000000000044): a turnout right on an edge falls in the same band as on the page
  const T_STEP = (0.5 + 0.005) - 0.5, T_EDGES = Array.from({ length: 101 }, (_, i) => 0.5 + i * T_STEP);
  function shpilkin(L, F, C) {
    const { A, uf } = D, nb = 100, ns = D.meta.ufs.length;
    const aL = new Float64Array(ns * nb), aF = new Float64Array(ns * nb), aC = new Float64Array(ns * nb), seen = new Uint8Array(ns * nb);
    for (let i = 0; i < L.length; i++) {
      const tv = C[i] / A[i];
      if (!(tv >= T_EDGES[0] && tv <= T_EDGES[nb])) continue;
      let lo = 0, hi = nb; // the band b with edge[b] < t <= edge[b+1] (the first band also takes t = 0.5)
      while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (T_EDGES[mid] < tv) lo = mid; else hi = mid; }
      const j = uf[i] * nb + lo;
      aL[j] += L[i]; aF[j] += F[i]; aC[j] += C[i]; seen[j] = 1;
    }
    let lula = 0, right = 0;
    for (let s = 0; s < ns; s++) {
      let peak = -1;
      for (let b = 0; b < nb; b++) if (seen[s * nb + b] && (peak < 0 || aC[s * nb + b] > aC[s * nb + peak])) peak = b;
      if (peak < 0) continue;
      const np = aL[s * nb + peak] + aF[s * nb + peak], sl = aL[s * nb + peak] / np, sr = aF[s * nb + peak] / np;
      for (let b = peak + 1; b < nb; b++) {
        const j = s * nb + b;
        if (!seen[j]) continue;
        const n = aL[j] + aF[j];
        lula += Math.max(0, aL[j] - sl * n); right += Math.max(0, aF[j] - sr * n);
      }
    }
    // for the chart: the bands of the whole country (the test itself is state by state)
    const nat = { C: new Float64Array(nb), L: new Float64Array(nb), F: new Float64Array(nb) };
    for (let s = 0; s < ns; s++) for (let b = 0; b < nb; b++) { const j = s * nb + b; nat.C[b] += aC[j]; nat.L[b] += aL[j]; nat.F[b] += aF[j]; }
    return { lula, right, nat };
  }
  // Proportional swing: within each polling place, Lula's swing between rounds against the right's round-1
  // share, controlling for the round-1 share of the other candidates; the slope
  function propSlope(L, F, L1, F1) {
    const { P, O1 } = D;
    let sxx = 0, sxo = 0, soo = 0, sxy = 0, soy = 0;
    const xs = [], os = [], ys = [];
    for (let k = 0; k + 1 < P.length; k++) {
      xs.length = 0; os.length = 0; ys.length = 0;
      for (let i = P[k]; i < P[k + 1]; i++) {
        const v1 = L1[i] + F1[i], v2 = L[i] + F[i];
        if (v1 <= 0 || v2 <= 0) continue;
        const p1 = L1[i] / v1;
        xs.push(1 - p1); os.push(1 - v1 / (v1 + O1[i])); ys.push(L[i] / v2 - p1);
      }
      const m = xs.length;
      if (m < 2) continue;
      let mx = 0, mo = 0, my = 0;
      for (let j = 0; j < m; j++) { mx += xs[j]; mo += os[j]; my += ys[j]; }
      mx /= m; mo /= m; my /= m;
      for (let j = 0; j < m; j++) {
        const x = xs[j] - mx, o = os[j] - mo, y = ys[j] - my;
        sxx += x * x; sxo += x * o; soo += o * o; sxy += x * y; soy += o * y;
      }
    }
    return (sxy * soo - soy * sxo) / (sxx * soo - sxo * sxo);
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

    // for the charts: the z of each section in 0.25 bins from -10 to +10, and sections per 1-point cell of
    // turnout x Lula's share (the page's two pictures, recomputed)
    const zh = new Int32Array(80);
    for (const v of zs) zh[Math.floor((Math.min(9.999, Math.max(-9.999, v)) + 10) / 0.25)]++;
    const fp = new Int32Array(10000);
    for (let i = 0; i < n; i++) {
      const v = L[i] + F[i];
      if (!v || !A[i]) continue;
      fp[Math.min(99, Math.floor((100 * C[i]) / A[i])) * 100 + Math.min(99, Math.floor((100 * L[i]) / v))]++;
    }
    r.zh = zh; r.fp = fp;

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
    r.size = sizeStep(L, F, C);
    r.shp = shpilkin(L, F, C);
    r.slope = propSlope(L, F, L1, F1);

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
  const START = { ben: 'flavio', type: 'software', where: 'random', model: 0, machines: 2000, intensity: 0, both: true, round: false };
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
    } else if (key === 'big') {
      // the largest sections (most voters) first
      idx = new Int32Array(n);
      for (let i = 0; i < n; i++) idx[i] = i;
      idx.sort((a, b) => D.C[b] - D.C[a] || a - b);
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
    const key = { random: `random:${state.seed}`, reduto_adv: victim, reduto_ben: state.ben, model: `model:${state.model}:${state.seed}`, uf: `uf:${state.uf}:${state.seed}`, big: 'big' }[state.where];
    return order(key);
  }

  // per-machine change in the margin for the "minimum to flip" helper: expected value and variance
  // (each machine's flips are drawn at random; hand-written round numbers move by up to 5 or 10)
  function gainOf(i, B, V, A, C) {
    const x = state.intensity / 100;
    if (state.type === 'stuff') return { mean: Math.max(0, Math.min(A[i], Math.ceil(x * A[i])) - C[i]), var: 0 };
    if (state.type === 'invent' && state.round) return { mean: 2 * x * V[i], var: 27 };
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
    // The same program in the same machines also flips round-1 votes, unless the reader unticks it. A
    // careful program flips the votes whose position in the day, mixed with the machine's own key, falls
    // under the share: about that share of them, at random, so the digits stay as natural as real counts;
    // and largely the same positions in both rounds, so the change between rounds hardly moves (flipping
    // a fixed number would skew the last digits; flipping each vote at random in each round would add
    // noise to the change between rounds). For each machine: the flips among the first votes of the
    // smaller round, then the flips among the extra votes of the larger one.
    let L1 = D.L1, F1 = D.F1, B1 = null, V1 = null;
    if (x > 0 && state.both && SOFTWARE(state.type)) {
      L1 = Uint16Array.from(D.L1); F1 = Uint16Array.from(D.F1);
      [B1, V1] = state.ben === 'lula' ? [L1, F1] : [F1, L1];
    }
    if (x > 0) each((i) => {
      if (state.type === 'software' || state.type === 'flip') {
        let k = 0;
        if (V1) {
          const lo = Math.min(V1[i], V[i]), kLo = binom(lo, x, r), kHi = kLo + binom(Math.max(V1[i], V[i]) - lo, x, r);
          const k1 = V1[i] <= V[i] ? kLo : kHi;
          k = V1[i] <= V[i] ? kHi : kLo;
          B1[i] += k1; V1[i] -= k1;
        } else k = binom(V[i], x, r);
        if (k) { V[i] -= k; B[i] += k; moved += k; touched.push(i); }
      } else if (state.type === 'stuff') {
        const add = Math.max(0, Math.min(A[i], Math.ceil(x * A[i])) - C[i]);
        if (add) { B[i] += add; C[i] += add; moved += add; touched.push(i); }
      } else {
        // numbers rewritten by hand: move part of the victim's votes; a careless forger also writes
        // round-looking numbers, which the reader can switch on
        const tot = B[i] + V[i];
        let b = B[i] + binom(V[i], x, r);
        if (state.round) {
          const u = r();
          if (u < 0.55) b = Math.round(b / 10) * 10; else if (u < 0.8) b = Math.round(b / 5) * 5;
        }
        b = Math.min(tot, Math.max(B[i], b));
        if (b !== B[i]) { moved += b - B[i]; B[i] = b; V[i] = tot - b; touched.push(i); }
      }
    });
    // machines carrying the fraud: all of them for the software, the chosen ones otherwise; for stuffing,
    // only the ones that received votes (the others were already above the target turnout)
    const machines = x > 0 ? (state.type === 'stuff' ? touched.length : list ? list.length : n) : 0;
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
  // An analyst never has the true 2026 numbers, only the published ones. So a row says the fraud shows
  // ("yes") when the published number would stand out by the standard the rest of the page uses on the
  // real data: for tests against chance, failing them (p < 0.001, or more than 4 standard deviations);
  // for counts that change from one election to the next, passing 1.5 times the largest value of the
  // reference elections (2022 and, where it was computed, 2018), and by more than chance (4 standard
  // deviations). That standard flags the near-unanimous Lula sections and not the polling-place or swing
  // outliers, as the page does. A row whose real number already stands out says so ("already"): there
  // the test can't tell a fraud from whatever made the real number high.
  function verdicts(t) {
    const b = D.base, R = REF(), r22 = R['2022'], r18 = R['2018'] || {};
    const pv = (p) => (p < 0.0001 ? tr('sim.p.tiny') : tr('sim.p.value', { p: dec(p, p < 0.01 ? 4 : 2) }));
    const pp = (v) => tr('sim.unit.pp', { v: dec(v, 2) });
    const chance = (n) => tr('sim.test.note.chance', { n: int(n) });
    const refNote = (key, jair) => (r18[key] !== undefined
      ? tr(jair ? 'sim.test.note.ref_jair' : 'sim.test.note.ref', { y22: int(r22[key]), y18: int(r18[key]) })
      : tr(jair ? 'sim.test.note.y2022_jair' : 'sim.test.note.y2022', { n: int(r22[key]) }));
    // a count stands out above the largest reference value
    const stands = (v, key) => { const m = Math.max(r22[key], r18[key] ?? 0); return v > 1.5 * m && v - m > 4 * Math.sqrt(m + 1); };
    // when the real number already stands out, the fraud still shows if it multiplies it: 1.5 times the real
    // number and beyond chance (the same rule, with the real number as the reference)
    const grows = (now, real, sd = true) => now > 1.5 * real && (!sd || now - real > 4 * Math.sqrt(real + 1));
    const count = (now, real, key) => (stands(real, key) ? (grows(now, real) ? 'yes' : 'already') : stands(now, key) ? 'yes' : 'no');
    const test = (failsNow, failsReal) => (failsReal ? 'already' : failsNow ? 'yes' : 'no');
    const corr = (v, pairs) => Math.abs(v) > 1.5 * Math.abs(r22.corr_dturn_swing) && (Math.abs(v) - Math.abs(r22.corr_dturn_swing)) * Math.sqrt(pairs) > 4;
    // g groups the rows (an identifier); its heading is tr(`sim.group.…`) via GROUP below
    const rows = [
      { g: 'round', label: tr('sim.test.ld_lula.label'), what: tr('sim.test.ld_lula.what'), real: pv(b.ldL.p), now: pv(t.ldL.p), v: test(t.ldL.p < 0.001, b.ldL.p < 0.001) },
      { g: 'round', label: tr('sim.test.ld_flavio.label'), real: pv(b.ldF.p), now: pv(t.ldF.p), v: test(t.ldF.p < 0.001, b.ldF.p < 0.001) },
      { g: 'round', label: tr('sim.test.ld_turnout.label'), real: pv(b.ldC.p), now: pv(t.ldC.p), v: test(t.ldC.p < 0.001, b.ldC.p < 0.001) },
      { g: 'round', label: tr('sim.test.heap_lula.label'), what: tr('sim.test.heap_lula.what'), real: `×${dec(b.hpL.ratio, 2)}`, now: `×${dec(t.hpL.ratio, 2)}`, v: test(t.hpL.z > 4, b.hpL.z > 4) },
      { g: 'round', label: tr('sim.test.heap_flavio.label'), real: `×${dec(b.hpF.ratio, 2)}`, now: `×${dec(t.hpF.ratio, 2)}`, v: test(t.hpF.z > 4, b.hpF.z > 4) },
      { g: 'round', label: tr('sim.test.heap_turnout.label'), real: `×${dec(b.hpC.ratio, 2)}`, now: `×${dec(t.hpC.ratio, 2)}`, v: test(t.hpC.z > 4, b.hpC.z > 4) },
      { g: 'round', label: tr('sim.test.int_lula.label'), what: tr('sim.test.int_lula.what'), real: int(b.intL.obs), now: int(t.intL.obs), v: test(t.intL.z > 4, b.intL.z > 4), note: chance(t.intL.exp) },
      { g: 'round', label: tr('sim.test.int_turnout.label'), real: int(b.intT.obs), now: int(t.intT.obs), v: test(t.intT.z > 4, b.intT.z > 4), note: chance(t.intT.exp) },
      { g: 'place', label: tr('sim.test.place_lula.label'), what: tr('sim.test.place_lula.what'), real: int(b.place.pos), now: int(t.place.pos), v: count(t.place.pos, b.place.pos, 'place_pos4'), note: refNote('place_pos4') },
      { g: 'place', label: tr('sim.test.place_flavio.label'), real: int(b.place.neg), now: int(t.place.neg), v: count(t.place.neg, b.place.neg, 'place_neg4'), note: refNote('place_neg4') },
      { g: 'place', label: tr('sim.test.corner_lula.label'), what: tr('sim.test.corner_lula.what'), real: int(b.corner.lula), now: int(t.corner.lula), v: count(t.corner.lula, b.corner.lula, 'corner_lula'), note: refNote('corner_lula') },
      { g: 'place', label: tr('sim.test.corner_flavio.label'), real: int(b.corner.flavio), now: int(t.corner.flavio), v: count(t.corner.flavio, b.corner.flavio, 'corner_right'), note: refNote('corner_right', true) },
      { g: 'place', label: tr('sim.test.model.label'), what: tr('sim.test.model.what'), real: pp(b.model.gap), now: pp(t.model.gap), v: test(Math.abs(t.model.t) > 4, Math.abs(b.model.t) > 4) },
      { g: 'rounds', label: tr('sim.test.swing_lula.label'), what: tr('sim.test.swing_lula.what'), real: int(b.swing.pos), now: int(t.swing.pos), v: count(t.swing.pos, b.swing.pos, 'swing_pos4'), note: refNote('swing_pos4') },
      { g: 'rounds', label: tr('sim.test.swing_flavio.label'), real: int(b.swing.neg), now: int(t.swing.neg), v: count(t.swing.neg, b.swing.neg, 'swing_neg4'), note: refNote('swing_neg4') },
      { g: 'rounds', label: tr('sim.test.swing_turnout.label'), what: tr('sim.test.swing_turnout.what'), real: dec(b.swing.corr, 3), now: dec(t.swing.corr, 3), v: corr(b.swing.corr, b.swing.pairs) ? 'already' : corr(t.swing.corr, t.swing.pairs) ? 'yes' : 'no', note: tr('sim.test.note.y2022_corr', { r: dec(r22.corr_dturn_swing, 3) }) },
    ];
    // measures that move with each election, signed (section size, slope): outside the range of the
    // reference elections by more than that range is wide
    const M = D.meta.more, refs = (k) => [M['2022'][k], M['2018'][k]];
    const outside = (v, k) => { const a = refs(k), lo = Math.min(...a), hi = Math.max(...a), w = hi - lo; return v > hi + w || v < lo - w; };
    // the section-size step: the same tolerance for a fraud for either side, the largest step of the reference
    // elections (in either direction) plus their spread
    const sizeLim = () => { const a = refs('size_step'); return Math.max(...a.map(Math.abs)) + Math.max(...a) - Math.min(...a); };
    const sizeOut = (s) => Math.abs(s.step) > sizeLim() && Math.abs(s.t) > 4;
    const shpOut = (v, k) => v > 1.5 * Math.max(...refs(k));
    const big = (v) => (v >= 1e6 ? tr('sim.unit.mi', { v: dec(v / 1e6, 2) }) : v >= 1e3 ? tr('sim.unit.mil', { v: int(v / 1e3) }) : int(v));
    const shpV = (now, real, k) => (shpOut(real, k) ? (grows(now, real, false) ? 'yes' : 'already') : shpOut(now, k) ? 'yes' : 'no');
    const step = (s) => tr('sim.size.value', { v: dec(s.step, 2), n: s.at === null ? '—' : int(s.at) });
    rows.push(
      { g: 'more', label: tr('sim.test.size.label'), what: tr('sim.test.size.what'), real: step(b.size), now: step(t.size), v: sizeOut(b.size) ? 'already' : sizeOut(t.size) ? 'yes' : 'no', note: tr('sim.test.note.ref_pp', { y22: dec(M['2022'].size_step, 2), y18: dec(M['2018'].size_step, 2) }) },
      { g: 'more', label: tr('sim.test.shp_lula.label'), what: tr('sim.test.shp_lula.what'), real: big(b.shp.lula), now: big(t.shp.lula), v: shpV(t.shp.lula, b.shp.lula, 'shp_lula'), note: tr('sim.test.note.ref_txt_haddad', { y22: big(M['2022'].shp_lula), y18: big(M['2018'].shp_lula) }) },
      { g: 'more', label: tr('sim.test.shp_flavio.label'), what: tr('sim.test.shp_flavio.what'), real: big(b.shp.right), now: big(t.shp.right), v: shpV(t.shp.right, b.shp.right, 'shp_right'), note: tr('sim.test.note.ref_txt_jair', { y22: big(M['2022'].shp_right), y18: big(M['2018'].shp_right) }) },
      { g: 'more', label: tr('sim.test.slope.label'), what: tr('sim.test.slope.what'), real: dec(b.slope, 3), now: dec(t.slope, 3), v: outside(b.slope, 'slope') ? 'already' : outside(t.slope, 'slope') ? 'yes' : 'undecided', note: tr('sim.test.note.ref_txt', { y22: dec(M['2022'].slope, 3), y18: dec(M['2018'].slope, 3) }) },
    );
    for (const r of rows) r.bad = r.v === 'yes';
    return rows;
  }

  // ---------------------------------------------------------------- UI
  const ui = {};
  function machinesMax() { return state.type === 'software' ? D.n : targets().length; }
  function sliderToMachines(v, max) { return Math.max(1, Math.round(Math.pow(max, v / 1000))); }
  function machinesToSlider(m, max) { return Math.round((1000 * Math.log(Math.max(1, m))) / Math.log(max)); }
  const INTENSITY = {
    software: { label: tr('sim.intensity.software'), min: 0, max: 20, step: 0.1, unit: '%' },
    flip: { label: tr('sim.intensity.flip'), min: 1, max: 100, step: 1, unit: '%' },
    stuff: { label: tr('sim.intensity.stuff'), min: 80, max: 100, step: 1, unit: '%' },
    invent: { label: tr('sim.intensity.invent'), min: 1, max: 100, step: 1, unit: '%' },
  };
  const GROUP = { round: tr('sim.group.round'), place: tr('sim.group.place'), rounds: tr('sim.group.rounds'), more: tr('sim.group.more') };

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
      ui.machOf.textContent = tr('sim.machines.of', { max: int(max), share: pct(state.machines / D.n, state.machines / D.n < 0.01 ? 2 : 1) });
    }
    ui.where.value = state.where;
    ui.bothRow.hidden = !SOFTWARE(state.type); ui.roundNote.hidden = SOFTWARE(state.type);
    ui.roundRow.hidden = state.type !== 'invent';
    const vk = `${state.type}|${state.where}|${state.round}`;
    if (vk !== viewFor) { viewFor = vk; showView(viewOf()); }
    ui.round.checked = state.round;
    ui.minBtn.textContent = state.ben === winner() ? tr('sim.min.btn_winner', { name: NAME[state.ben] }) : tr('sim.min.btn');
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
    const sim = f.moved > 0, tag = sim ? tr('sim.result.tag') : '';
    const share = pct(f.machines / D.n, f.machines / D.n < 0.01 ? 2 : 1);
    const both = state.both ? tr('sim.how.both') : '';
    const how = {
      software: () => tr('sim.how.software', { machines: int(f.machines), moved: int(f.moved), both }),
      flip: () => tr('sim.how.flip', { machines: int(f.machines), share, moved: int(f.moved), both }),
      stuff: () => tr('sim.how.stuff', { moved: int(f.moved), machines: int(f.machines), share }),
      invent: () => tr('sim.how.invent', { machines: int(f.machines), share, moved: int(f.moved), name: NAME[state.ben] }),
    }[state.type];
    const T = D.meta.totals, realTot = T.lula + T.flavio;
    const forWinner = sim && state.ben === winner(), margin = Math.abs(T.lula - T.flavio);
    const needed = state.type === 'stuff' ? tr('sim.needed.add', { n: int(margin + 1) }) : tr('sim.needed.move', { n: int(Math.floor(margin / 2) + 1) });
    const chip = forWinner ? tr('sim.chip.for_winner', { name: NAME[state.ben] })
      : sim ? (flipped ? tr('sim.chip.flipped') : tr('sim.chip.not_flipped')) : tr('sim.chip.real');
    const fabricated = forWinner ? tr('sim.result.fabricated', { needed, moved: int(f.moved) }) : '';
    ui.result.innerHTML = `
      <p class="vf-sim-flag${sim ? '' : ' vf-sim-real'}">${sim ? tr('sim.result.flag_sim') : tr('sim.result.flag_real')}</p>
      <div class="vf-sim-totals">
        <div class="vf-sim-cand" data-c="lula"><span>${NAME.lula}${tag}</span><b>${int(l)}</b><span>${pct(l / tot, 2)}</span></div>
        <div class="vf-sim-cand" data-c="flavio"><span>${NAME.flavio}${tag}</span><b>${int(fl)}</b><span>${pct(fl / tot, 2)}</span></div>
      </div>
      <div class="vf-sim-bar" aria-hidden="true"><i style="width:${(100 * l) / tot}%"></i></div>
      <p class="vf-sim-verdict"><span class="vf-chip ${forWinner ? 'vf-warn' : flipped ? 'vf-bad' : 'vf-ok'}">${chip}</span>
      ${sim ? tr('sim.result.sim_line', { how: how(), name: NAME[win], n: int(Math.abs(l - fl)) }) : tr('sim.result.real_line', { n: int(l - fl) })}</p>
      ${sim ? `<p class="vf-sim-realline">${tr('sim.result.realline', { lula: int(T.lula), lula_pct: pct(T.lula / realTot, 2), flavio: int(T.flavio), flavio_pct: pct(T.flavio / realTot, 2), fabricated })}</p>` : ''}`;

    const rows = verdicts(t);
    const bad = rows.filter((r) => r.bad).length;
    const why = state.type === 'software'
      ? tr('sim.score.why_software', { winner: forWinner ? tr('sim.score.why_software_winner', { name: NAME[state.ben] }) : '' })
      : tr('sim.score.why_small');
    ui.score.innerHTML = !sim ? tr('sim.score.none')
      : bad ? tr('sim.score.bad', { bad, total: rows.length })
        : tr('sim.score.clean', { total: rows.length, why });
    const caught = integrity(f);
    if (sim && !bad && state.type === 'software') ui.score.innerHTML += ` ${tr('sim.score.integrity_software', { swapped: swapped() })}`;
    else if (sim && !bad && state.type === 'flip') ui.score.innerHTML += ` ${tr('sim.score.integrity_flip', { machines: int(f.machines), chance: caught.chance, chance_bio: caught.chanceBio })}`;
    if (forWinner && bad) ui.score.innerHTML += ` ${tr('sim.score.winner_marks', { name: NAME[state.ben] })}`;
    let g = '';
    ui.tbody.innerHTML = rows.map((r) => {
      const head = r.g !== g ? `<tr class="vf-sim-group"><th colspan="4" scope="colgroup">${GROUP[(g = r.g)]}</th></tr>` : '';
      const chip = { yes: ['vf-bad', tr('sim.test.yes')], already: ['vf-warn', tr('sim.test.already')], no: ['vf-ok', tr('sim.test.no')],
        undecided: ['vf-sim-neutral', tr('sim.test.undecided')] }[r.v];
      return `${head}<tr${r.bad ? ' class="vf-sim-hit"' : ''}><th scope="row">${r.label}${r.what ? `<small>${r.what}</small>` : ''}</th><td class="vf-n">${r.real}</td><td class="vf-n">${r.now}${r.note ? `<small>${r.note}</small>` : ''}</td><td><span class="vf-chip ${chip[0]}">${chip[1]}</span></td></tr>`;
    }).join('');
    renderOutside(f, caught);
    drawCharts(t);
    announce(sim
      ? tr('sim.announce.sim', { name: NAME[win], n: int(Math.abs(l - fl)), bad, total: rows.length, integrity: !bad && state.type === 'software' ? tr('sim.announce.integrity') : '' })
      : tr('sim.announce.real'));
  }
  // The page's curve and fingerprint, redrawn with the fraud, for the favoured candidate's share (for Flávio,
  // Lula's z bins and share cells are mirrored, since in the runoff his share is 1 minus Lula's).
  const phi = (x) => {
    const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
    const e = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x / 2);
    return 0.5 * (1 + Math.sign(x) * e);
  };
  // the fingerprint opens as an analyst would see it; "diff" marks in red the cells that gained sections
  let fpMode = 'plain', lastT = null, view = 'pair', viewFor = '';
  // the chart that shows each kind of fraud best opens with it: the digits for hand-written numbers, the
  // turnout bands for stuffing, the section size for a fraud only in the largest machines
  const viewOf = () => (state.type === 'invent' && state.round ? 'digits' : state.type === 'stuff' ? 'shp' : state.where === 'big' && state.type !== 'software' ? 'size' : 'pair');
  function showView(v) {
    view = v;
    for (const b of ui.view.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.v === v));
    ui.fpMode.hidden = v !== 'pair'; ui.viewNotePair.hidden = v !== 'pair';
    ui.viewNote.hidden = v === 'pair';
    if (v !== 'pair') ui.viewNote.textContent = tr(`sim.view.${v}.note`, { name: NAME[state.ben] });
    ui.pairAria ??= ui.charts.getAttribute('aria-label');
    ui.charts.setAttribute('aria-label', v === 'pair' ? ui.pairAria : tr(`sim.view.${v}.aria`, { name: NAME[state.ben] }));
  }
  function drawCharts(t) {
    lastT = t;
    if (view !== 'pair') return drawView(t);
    const box = ui.charts;
    const flavio = state.ben === 'flavio', name = NAME[state.ben];
    const color = vf.cand[state.ben].color(), MUTED = 'var(--cds-chart-muted)', FG = 'var(--color-fg)', GAIN = 'var(--color-warn)';
    const zMir = (h) => (flavio ? Int32Array.from(h).reverse() : h);
    const fpAt = (fp, i, j) => fp[i * 100 + (flavio ? 99 - j : j)];
    const zs = zMir(t.zh), zr = zMir(D.base.zh);
    const nz = zs.reduce((a, b) => a + b, 0);
    box.replaceChildren();
    const tip = vf.tooltip(box);
    const [c1, c2] = vf.panels(box, [tr('sim.chart.curve.title', { name }), tr('sim.chart.fp.title', { name })]);

    // 1. the curve, log scale, as on the page
    {
      const { s, w, h } = vf.svg(c1, 240);
      const step = 0.25, z0 = (k) => -10 + k * step;
      const normal = (k) => nz * (phi(z0(k + 1) / t.place.rsd) - phi(z0(k) / t.place.rsd));
      const top = Math.max(...zs, ...zr) * 1.5;
      const y = d3.scaleLog([0.5, top], [h - 24, 8]);
      const ticks = [1, 10, 100, 1000, 10000, 100000].filter((v) => v <= top);
      const ml = vf.textWidth(s, ticks.map((v) => v.toLocaleString(vf.t('locale.intl')))) + 8;
      const x = d3.scaleLinear([-10, 10], [ml, w - 8]);
      for (const [a, b] of [[-10, -4], [4, 10]]) {
        s.append('rect').attr('x', x(a)).attr('width', x(b) - x(a)).attr('y', 8).attr('height', h - 32).style('fill', 'var(--cds-chart-grid)').style('opacity', 0.6);
      }
      s.append('g').attr('transform', `translate(${ml},0)`)
        .call(d3.axisLeft(y).tickValues(ticks).tickFormat((v) => v.toLocaleString(vf.t('locale.intl'))).tickSize(-(w - ml - 8))).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`)
        .call(d3.axisBottom(x).tickValues([-8, -4, 0, 4, 8]).tickFormat((d) => (d > 0 ? '+' : '') + d).tickSize(0).tickPadding(8)).call(vf.axis);
      const ks = d3.range(80);
      s.append('g').selectAll('rect').data(ks.filter((k) => zs[k] > 0)).join('rect')
        .attr('x', (k) => x(z0(k)) + 0.5).attr('width', Math.max(1, x(step) - x(0) - 1))
        .attr('y', (k) => y(zs[k])).attr('height', (k) => y(0.5) - y(zs[k])).style('fill', color);
      s.append('path').datum(ks.filter((k) => zr[k] > 0)).attr('d', d3.line().x((k) => x(z0(k) + step / 2)).y((k) => y(zr[k])))
        .style('fill', 'none').style('stroke', MUTED).attr('stroke-width', 2).attr('stroke-linejoin', 'round');
      s.append('path').datum(ks.filter((k) => normal(k) >= 0.5)).attr('d', d3.line().x((k) => x(z0(k) + step / 2)).y((k) => y(normal(k))))
        .style('fill', 'none').style('stroke', FG).attr('stroke-width', 1.5);
      s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const k = Math.max(0, Math.min(79, Math.floor((x.invert(d3.pointer(ev)[0]) + 10) / step)));
          tip.show(ev, tr('sim.chart.curve.tip', { from: dec(z0(k), 2), to: dec(z0(k + 1), 2) }), [
            { label: tr('sim.chart.with_fraud'), value: int(zs[k]), color },
            { label: tr('sim.chart.real'), value: int(zr[k]), color: MUTED, line: true },
            { label: tr('sim.chart.normal'), value: int(Math.round(normal(k))), color: FG, line: true },
          ]);
        })
        .on('pointerleave', tip.leave);
    }

    // 2. the fingerprint: cells drawn as one path per shade; cells that gained sections, in red
    {
      const { s, w, h } = vf.svg(c2, 240);
      let lo = 0, cum = 0;
      const byT = d3.range(100).map((i) => d3.range(100).reduce((a, j) => a + D.base.fp[i * 100 + j], 0));
      const total = d3.sum(byT);
      while (lo < 99 && (cum += byT[lo]) / total < 0.002) lo++;
      const ml = vf.textWidth(s, ['100%']) + 8;
      const x = d3.scaleLinear([lo, 100], [ml, w - 6]);
      const y = d3.scaleLinear([0, 100], [h - 24, 6]);
      s.append('g').attr('transform', `translate(${ml},0)`).call(d3.axisLeft(y).ticks(5).tickFormat((d) => `${d}%`).tickSize(0).tickPadding(6)).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`).call(d3.axisBottom(x).ticks(5).tickFormat((d) => `${d}%`).tickSize(0).tickPadding(8)).call(vf.axis);
      const max = Math.max(...t.fp, ...D.base.fp);
      const level = (v) => Math.min(9, Math.floor((Math.log(v) / Math.log(max + 1)) * 10));
      const paths = { base: Array.from({ length: 10 }, () => []), gain: Array.from({ length: 10 }, () => []) };
      const cw = x(lo + 1) - x(lo) + 0.4, ch = y(0) - y(1) + 0.4;
      for (let i = lo; i < 100; i++) {
        for (let j = 0; j < 100; j++) {
          const v = fpAt(t.fp, i, j);
          if (!v) continue;
          const gain = fpMode === 'diff' ? v - fpAt(D.base.fp, i, j) : 0;
          const d = `M${x(i).toFixed(1)},${y(j + 1).toFixed(1)}h${cw.toFixed(1)}v${ch.toFixed(1)}h${(-cw).toFixed(1)}z`;
          if (gain > 0) paths.gain[level(gain)].push(d); else paths.base[level(v)].push(d);
        }
      }
      const bg = vf.resolve('var(--color-panel)');
      // in "diff" mode the other cells turn grey, so the gained ones stand out for either candidate
      const ramp = d3.interpolateRgb(bg, vf.resolve(fpMode === 'diff' ? MUTED : color)), rampGain = d3.interpolateRgb(bg, vf.resolve(GAIN));
      for (const [kind, rp] of [['base', ramp], ['gain', rampGain]]) {
        paths[kind].forEach((ds, l) => {
          // gained cells start darker: most gain only a few sections and would be too pale to see
          const floor = kind === 'gain' ? 0.5 : 0.16;
          if (ds.length) s.append('path').attr('d', ds.join('')).style('fill', rp(floor + (1 - floor) * (l + 1) / 10));
        });
      }
      s.append('rect').attr('x', x(95)).attr('width', x(100) - x(95)).attr('y', y(100)).attr('height', y(90) - y(100))
        .style('fill', 'none').style('stroke', FG).attr('stroke-width', 1.5).attr('stroke-dasharray', '4 3');
      s.append('rect').attr('x', ml).attr('width', w - 6 - ml).attr('y', 6).attr('height', h - 30).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const [px, py] = d3.pointer(ev);
          const i = Math.max(lo, Math.min(99, Math.floor(x.invert(px)))), j = Math.max(0, Math.min(99, Math.floor(y.invert(py))));
          tip.show(ev, tr('sim.chart.fp.tip', { t0: i, t1: i + 1, name, s0: j, s1: j + 1 }), [
            { label: tr('sim.chart.with_fraud'), value: int(fpAt(t.fp, i, j)) },
            { label: tr('sim.chart.real'), value: int(fpAt(D.base.fp, i, j)) },
          ]);
        })
        .on('pointerleave', tip.leave);
    }
    vf.legend(box, [
      { label: tr('sim.legend.with_fraud'), color },
      { label: tr('sim.legend.real'), color: MUTED, line: true },
      { label: tr('sim.chart.normal'), color: FG, line: true },
      ...(fpMode === 'diff' ? [{ label: tr('sim.legend.gained'), color: GAIN }] : []),
    ]);
  }

  // ---------------------------------------------------------------- the other charts
  function drawView(t) {
    const box = ui.charts, name = NAME[state.ben];
    const color = vf.cand[state.ben].color(), MUTED = 'var(--cds-chart-muted)', FG = 'var(--color-fg)';
    showView(view);
    box.replaceChildren();
    const tip = vf.tooltip(box);
    const real = D.base;
    const axes = (s, w, h, x, y, ml, xf, yf, xt, yt) => {
      s.append('g').attr('transform', `translate(${ml},0)`).call(d3.axisLeft(y).ticks(yt ?? 4).tickFormat(yf).tickSize(-(w - ml - 8))).call(vf.axis);
      s.append('g').attr('transform', `translate(0,${h - 24})`).call(d3.axisBottom(x).ticks(xt ?? 5).tickFormat(xf).tickSize(0).tickPadding(8)).call(vf.axis);
    };
    const ppf = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${dec(Math.abs(v), 1)}`;
    if (view === 'digits') {
      const cands = [['lula', 'ldL'], ['flavio', 'ldF']];
      const cells = vf.panels(box, cands.map(([c]) => tr('sim.view.digits.title', { name: NAME[c] })));
      cands.forEach(([c, k], idx) => {
        const { s, w, h } = vf.svg(cells[idx], 200);
        const now = t[k].freq, was = real[k].freq;
        const top = Math.max(0.15, ...now, ...was) * 1.1;
        const ml = vf.textWidth(s, ['20%']) + 8;
        const x = d3.scaleBand(d3.range(10), [ml, w - 8]).padding(0.25), y = d3.scaleLinear([0, top], [h - 24, 8]);
        s.append('g').attr('transform', `translate(${ml},0)`).call(d3.axisLeft(y).ticks(4).tickFormat((v) => `${dec(100 * v, 0)}%`).tickSize(-(w - ml - 8))).call(vf.axis);
        s.append('g').attr('transform', `translate(0,${h - 24})`).call(d3.axisBottom(x).tickSize(0).tickPadding(8)).call(vf.axis);
        s.append('g').selectAll('rect').data(d3.range(10)).join('rect').attr('x', (d) => x(d)).attr('width', x.bandwidth())
          .attr('y', (d) => y(now[d])).attr('height', (d) => y(0) - y(now[d])).attr('rx', 2).style('fill', vf.cand[c].color());
        s.append('path').datum(d3.range(10)).attr('d', d3.line().x((d) => x(d) + x.bandwidth() / 2).y((d) => y(was[d])))
          .style('fill', 'none').style('stroke', MUTED).attr('stroke-width', 2);
        s.append('line').attr('x1', ml).attr('x2', w - 8).attr('y1', y(0.1)).attr('y2', y(0.1)).style('stroke', FG).attr('stroke-dasharray', '4 3');
        s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
          .on('pointermove pointerdown', (ev) => {
            const d = Math.max(0, Math.min(9, Math.floor((d3.pointer(ev)[0] - ml) / ((w - 8 - ml) / 10))));
            tip.show(ev, tr('sim.view.digits.tip', { d }), [
              { label: tr('sim.chart.with_fraud'), value: pct(now[d], 1), color: vf.cand[c].color() },
              { label: tr('sim.chart.real'), value: pct(was[d], 1), color: MUTED, line: true }]);
          }).on('pointerleave', tip.leave);
      });
      // each panel's bars are in its candidate's color, named in its title: no swatch for them here
      vf.legend(box, [{ label: tr('sim.legend.real'), color: MUTED, line: true }, { label: tr('sim.view.digits.ref'), color: FG, line: true, dash: '4 3' }]);
    } else if (view === 'shp') {
      const [c1, c2] = vf.panels(box, [tr('sim.view.shp.title_votes'), tr('sim.view.shp.title_share', { name })]);
      const B = state.ben === 'lula' ? 'L' : 'F';
      const band = (b) => 50 + b * 0.5;
      const bands = d3.range(100);
      const share = (nat) => bands.map((b) => { const v = nat.L[b] + nat.F[b]; return v ? nat[B][b] / v : NaN; });
      const votes = (nat) => bands.map((b) => nat.L[b] + nat.F[b]);
      const vNow = votes(t.shp.nat), vWas = votes(real.shp.nat), sNow = share(t.shp.nat), sWas = share(real.shp.nat);
      const lo = Math.max(0, bands.findIndex((b) => vWas[b] > 0 || vNow[b] > 0) - 2);
      const peak = d3.maxIndex(bands, (b) => t.shp.nat.C[b]);
      {
        const { s, w, h } = vf.svg(c1, 220);
        const top = Math.max(...vNow, ...vWas) * 1.08;
        const ml = vf.textWidth(s, [tr('sim.unit.mi', { v: '0,0' })]) + 8;
        const x = d3.scaleLinear([band(lo), 100], [ml, w - 8]), y = d3.scaleLinear([0, top], [h - 24, 8]);
        axes(s, w, h, x, y, ml, (v) => `${v}%`, (v) => (v ? tr('sim.unit.mi', { v: dec(v / 1e6, 1) }) : '0'));
        const bw = Math.max(1, x(band(1)) - x(band(0)) - 0.5);
        // all votes, not one candidate's: a neutral color
        s.append('g').selectAll('rect').data(bands.filter((b) => b >= lo && vNow[b] > 0)).join('rect')
          .attr('x', (b) => x(band(b))).attr('width', bw).attr('y', (b) => y(vNow[b])).attr('height', (b) => y(0) - y(vNow[b])).style('fill', FG).style('opacity', 0.55);
        s.append('path').datum(bands.filter((b) => b >= lo)).attr('d', d3.line().x((b) => x(band(b)) + bw / 2).y((b) => y(vWas[b])))
          .style('fill', 'none').style('stroke', MUTED).attr('stroke-width', 2).attr('stroke-linejoin', 'round');
        s.append('line').attr('x1', x(band(peak + 1))).attr('x2', x(band(peak + 1))).attr('y1', 8).attr('y2', h - 24).style('stroke', FG).attr('stroke-dasharray', '4 3');
        s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
          .on('pointermove pointerdown', (ev) => {
            const b = Math.max(lo, Math.min(99, Math.floor((x.invert(d3.pointer(ev)[0]) - 50) / 0.5)));
            tip.show(ev, tr('sim.view.shp.tip', { t0: dec(band(b), 1), t1: dec(band(b + 1), 1) }), [
              { label: tr('sim.chart.with_fraud'), value: int(vNow[b]), color: FG }, { label: tr('sim.chart.real'), value: int(vWas[b]), color: MUTED, line: true }]);
          }).on('pointerleave', tip.leave);
      }
      {
        const { s, w, h } = vf.svg(c2, 220);
        const ok = (a) => bands.filter((b) => b >= lo && Number.isFinite(a[b]) && vWas[b] + vNow[b] > 2000);
        const ml = vf.textWidth(s, ['100%']) + 8;
        const x = d3.scaleLinear([band(lo), 100], [ml, w - 8]), y = d3.scaleLinear([0, 1], [h - 24, 8]);
        axes(s, w, h, x, y, ml, (v) => `${v}%`, (v) => `${dec(100 * v, 0)}%`);
        s.append('path').datum(ok(sWas)).attr('d', d3.line().x((b) => x(band(b) + 0.25)).y((b) => y(sWas[b])))
          .style('fill', 'none').style('stroke', MUTED).attr('stroke-width', 2).attr('stroke-linejoin', 'round');
        s.append('path').datum(ok(sNow)).attr('d', d3.line().x((b) => x(band(b) + 0.25)).y((b) => y(sNow[b])))
          .style('fill', 'none').style('stroke', color).attr('stroke-width', 2).attr('stroke-linejoin', 'round');
        s.append('line').attr('x1', x(band(peak + 1))).attr('x2', x(band(peak + 1))).attr('y1', 8).attr('y2', h - 24).style('stroke', FG).attr('stroke-dasharray', '4 3');
        s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
          .on('pointermove pointerdown', (ev) => {
            const b = Math.max(lo, Math.min(99, Math.floor((x.invert(d3.pointer(ev)[0]) - 50) / 0.5)));
            tip.show(ev, tr('sim.view.shp.tip', { t0: dec(band(b), 1), t1: dec(band(b + 1), 1) }), [
              { label: tr('sim.chart.with_fraud'), value: Number.isFinite(sNow[b]) ? pct(sNow[b], 1) : '—', color }, { label: tr('sim.chart.real'), value: Number.isFinite(sWas[b]) ? pct(sWas[b], 1) : '—', color: MUTED, line: true }]);
          }).on('pointerleave', tip.leave);
      }
      vf.legend(box, [{ label: tr('sim.view.shp.legend_votes'), color: FG }, { label: tr('sim.view.shp.legend_share', { name }), color, line: true },
        { label: tr('sim.legend.real'), color: MUTED, line: true }, { label: tr('sim.view.shp.peak'), color: FG, line: true, dash: '4 3' }]);
    } else {
      const [c1] = vf.panels(box, [tr('sim.view.size.title')]);
      const { s, w, h } = vf.svg(c1, 220);
      const color = vf.cand.lula.color(); // the curve is Lula's share, whoever the fraud favors
      const now = t.size.curve, was = real.size.curve;
      const all = [...now, ...was].filter((c) => c.n >= 200 && Number.isFinite(c.pp)).map((c) => c.pp);
      const ext = Math.max(0.5, ...all.map(Math.abs)) * 1.15;
      const ml = vf.textWidth(s, ['−0,0']) + 8;
      const x = d3.scaleLinear([0, 525], [ml, w - 8]), y = d3.scaleLinear([-ext, ext], [h - 24, 8]);
      axes(s, w, h, x, y, ml, (v) => (v >= 500 ? '500+' : `${v}`), ppf, 6, 5);
      s.append('line').attr('x1', ml).attr('x2', w - 8).attr('y1', y(0)).attr('y2', y(0)).style('stroke', FG);
      const pts = (cv) => cv.filter((c) => c.n >= 200 && Number.isFinite(c.pp));
      s.append('path').datum(pts(was)).attr('d', d3.line().x((c) => x(c.from + 12.5)).y((c) => y(c.pp)))
        .style('fill', 'none').style('stroke', MUTED).attr('stroke-width', 2).attr('stroke-linejoin', 'round');
      s.append('path').datum(pts(now)).attr('d', d3.line().x((c) => x(c.from + 12.5)).y((c) => y(c.pp)))
        .style('fill', 'none').style('stroke', color).attr('stroke-width', 2).attr('stroke-linejoin', 'round');
      s.append('g').selectAll('circle').data(pts(now)).join('circle').attr('cx', (c) => x(c.from + 12.5)).attr('cy', (c) => y(c.pp)).attr('r', 2.5).style('fill', color);
      s.append('rect').attr('x', ml).attr('width', w - 8 - ml).attr('height', h).style('fill', 'transparent')
        .on('pointermove pointerdown', (ev) => {
          const b = Math.max(0, Math.min(20, Math.floor(x.invert(d3.pointer(ev)[0]) / 25)));
          tip.show(ev, b === 20 ? tr('sim.view.size.tip_last') : tr('sim.view.size.tip', { a: 25 * b, b: 25 * b + 24 }), [
            { label: tr('sim.chart.with_fraud'), value: Number.isFinite(now[b].pp) ? tr('sim.unit.pp', { v: dec(now[b].pp, 2) }) : '—', color },
            { label: tr('sim.chart.real'), value: Number.isFinite(was[b].pp) ? tr('sim.unit.pp', { v: dec(was[b].pp, 2) }) : '—', color: MUTED, line: true },
            { label: tr('sim.view.size.sections'), value: int(now[b].n) }]);
        }).on('pointerleave', tip.leave);
      vf.legend(box, [{ label: tr('sim.chart.with_fraud'), color }, { label: tr('sim.legend.real'), color: MUTED, line: true }]);
    }
  }

  // one short summary for screen readers, once the controls stop moving
  let said = 0;
  function announce(text) {
    clearTimeout(said);
    said = setTimeout(() => { ui.status.textContent = text; }, 900);
  }

  // The integrity test draws its machines state by state. The national total is split evenly among
  // the 27 states (20 each, the lowest number reported), and none are drawn abroad.
  const perUf = () => D.meta.integrity_test_machines / D.meta.ufs.filter((u) => u !== 'ZZ').length;
  // chance that at least one tampered machine is drawn: one minus the chance of missing them in
  // every state (hypergeometric within each state)
  // Also for the biometric part of the test alone (a share of each state's machines, at least one): the
  // only part a program that recognised the test could not tell from an election.
  const bioPerUf = () => Math.max(1, Math.round(perUf() * D.meta.integrity_biometric_share));
  function integrity(f) {
    const M = new Array(D.byUf.length).fill(0);
    if (f.list) for (const i of f.list) M[D.uf[i]]++;
    const hit = (a) => {
      let pMiss = 1;
      D.byUf.forEach((idx, s) => {
        if (D.meta.ufs[s] === 'ZZ') return;
        const N = idx.length, m = f.list ? M[s] : N; // no list: the software is in every machine
        for (let j = 0; j < a && pMiss > 1e-300; j++) pMiss *= Math.max(0, (N - m - j) / (N - j));
      });
      return f.machines ? 1 - pMiss : 0;
    };
    const say = (p) => (p > 0.999999 ? tr('sim.chance.certain') : p === 0 ? '0%' : p < 0.0001 ? tr('sim.chance.tiny') : pct(p, p > 0.99 ? 2 : 1));
    const pHit = hit(perUf()), pBio = hit(bioPerUf());
    return { pHit, chance: say(pHit), pBio, chanceBio: say(pBio) };
  }
  // what a tampered machine does to the known votes typed in during the integrity test
  const swapped = () => tr('sim.swapped', {
    rate: Number.isInteger(state.intensity) ? state.intensity : dec(state.intensity),
    victim: NAME[state.ben === 'lula' ? 'flavio' : 'lula'], name: NAME[state.ben],
  });

  function renderOutside(f, { pHit, chance, chanceBio }) {
    const N = D.n, a = D.meta.integrity_test_machines, per = perUf();
    const M = f.machines;
    const sw = SOFTWARE(state.type);
    const detail = M === N ? tr('sim.outside.integrity_all', { swapped: swapped() })
      : tr('sim.outside.integrity_some', { m: int(M), n: int(N), chance, swapped: swapped() });
    let html;
    if (!M) html = `<p>${tr('sim.outside.none')}</p>`;
    else if (sw) html = `<p class="vf-sim-verdict"><span class="vf-chip ${pHit > 0.99 ? 'vf-bad' : 'vf-warn'}">${M === N ? tr('sim.outside.chip_all') : tr('sim.outside.chip_chance', { chance })}</span></p>
      <p>${tr('sim.outside.integrity', { a: int(a), detail })} ${tr('sim.outside.integrity_bio', { bio: int(bioPerUf()), chance: chanceBio })}</p>
      <p class="vf-sim-actions"><button type="button" class="vf-btn" id="sim-draw">${tr('sim.outside.draw_btn', { per: int(per) })}</button> <span id="sim-draw-out" aria-live="polite"></span></p>
      <p class="vf-sim-note">${tr('sim.outside.note', { per: int(per) })}</p>`;
    else if (state.type === 'stuff') html = `<p>${tr('sim.outside.stuff', { moved: int(f.moved), m: int(M) })}</p>`;
    else html = `<p>${tr('sim.outside.invent')}</p>`;
    ui.outside.innerHTML = html;
    const btn = document.getElementById('sim-draw');
    if (btn) btn.addEventListener('click', () => {
      const r = mulberry32((Date.now() & 0xffffffff) ^ state.seed);
      const hit = f.list ? new Set(f.list) : null; // null: the software is in every machine
      let found = 0, drawn = 0;
      D.byUf.forEach((idx, s) => {
        if (D.meta.ufs[s] === 'ZZ') return;
        const seen = new Set();
        while (seen.size < Math.min(per, idx.length)) { const i = idx[Math.floor(r() * idx.length)]; if (!seen.has(i)) { seen.add(i); if (!hit || hit.has(i)) found++; } }
        drawn += seen.size;
      });
      document.getElementById('sim-draw-out').innerHTML = found
        ? `<span class="vf-chip vf-bad">${tr('sim.draw.found')}</span> ${found === drawn ? tr('sim.draw.all', { drawn: int(drawn) })
          : found === 1 ? tr('sim.draw.some_one', { found: int(found), drawn: int(drawn) })
            : tr('sim.draw.some_many', { found: int(found), drawn: int(drawn) })}`
        : `<span class="vf-chip vf-ok">${tr('sim.draw.passed')}</span> ${tr('sim.draw.none', { drawn: int(drawn) })}`;
    });
  }

  function bind() {
    ui.app = $('sim-app');
    ui.ben = $('sim-ben'); ui.where = $('sim-where'); ui.modelSel = $('sim-model'); ui.ufSel = $('sim-uf');
    ui.machinesRow = $('sim-machines-row'); ui.whereRow = $('sim-where-row');
    ui.machRange = $('sim-machines'); ui.machNum = $('sim-machines-n'); ui.machOf = $('sim-machines-of');
    ui.intRange = $('sim-intensity'); ui.intOut = $('sim-intensity-out'); ui.intLabel = $('sim-intensity-lbl');
    ui.result = $('sim-result'); ui.score = $('sim-score'); ui.tbody = page.querySelector('#sim-tests tbody'); ui.outside = $('sim-outside');
    ui.minNote = $('sim-min-note'); ui.status = $('sim-status'); ui.minBtn = $('sim-min'); ui.charts = $('sim-charts');
    vf.segmented($('sim-fp-mode'), (v) => { fpMode = v; if (lastT) drawCharts(lastT); });
    vf.segmented($('sim-chart-view'), (v) => { showView(v); if (lastT) drawCharts(lastT); });
    ui.both = $('sim-both'); ui.bothRow = $('sim-both-row'); ui.roundNote = $('sim-round-note');
    ui.round = $('sim-round'); ui.roundRow = $('sim-round-row');
    ui.view = $('sim-chart-view'); ui.fpMode = $('sim-fp-mode'); ui.viewNote = $('sim-view-note'); ui.viewNotePair = $('sim-view-note-pair');
    page.querySelector('.vf-sim-controls').addEventListener('submit', (ev) => ev.preventDefault());
    ui.modelSel.innerHTML = D.meta.models.map((m, i) => `<option value="${i}">${m}</option>`).join('');
    ui.ufSel.innerHTML = D.meta.ufs.map((u, i) => `<option value="${i}">${u === 'ZZ' ? tr('sim.uf.abroad') : u}</option>`).join('');
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
    ui.round.addEventListener('change', () => { state.round = ui.round.checked; changed(); });
    $('sim-reseed').addEventListener('click', () => { state.seed += 1; D.order = Object.fromEntries(Object.entries(D.order).filter(([k]) => !/random|model|uf/.test(k))); changed(); });
    $('sim-reset').addEventListener('click', () => { Object.assign(state, START); ui.minNote.textContent = ''; changed(); });
    $('sim-min').addEventListener('click', () => {
      const m = minimumToFlip();
      const who = NAME[state.ben], victim = NAME[state.ben === 'lula' ? 'flavio' : 'lula'];
      const over = ` ${tr('sim.min.over')}`;
      if (m.impossible) ui.minNote.textContent = m.fabricate
        ? tr('sim.min.impossible_fabricate', { n: int(m.available), name: who })
        : tr('sim.min.impossible', { n: int(m.available) });
      else if (m.rate !== undefined) {
        if (m.rate > INTENSITY.software.max) { ui.minNote.textContent = tr('sim.min.rate_too_high', { rate: dec(m.rate), victim }); return; }
        state.intensity = m.rate;
        ui.minNote.textContent = m.fabricate
          ? `${tr('sim.min.rate_fabricate', { name: who, rate: dec(m.rate), victim })}${over}`
          : tr('sim.min.rate', { rate: dec(m.rate), victim });
      } else {
        state.machines = m.machines;
        ui.minNote.textContent = m.fabricate
          ? `${tr('sim.min.machines_fabricate', { name: who, n: int(m.machines) })}${over}`
          : tr('sim.min.machines', { n: int(m.machines) });
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
      box.innerHTML = tr('sim.error.load', { message: e.message ?? '' });
      started = false;
    }
  }
  new MutationObserver(start).observe(page, { attributes: true, attributeFilter: ['hidden'] });
  start();
  window.vfSim = { state, tests: () => D && D.base, get data() { return D; } };
})();
