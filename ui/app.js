/* Fathom — analyst review desk for Track 2 watchlist hits. */
(() => {
  "use strict";

  const COST = {
    DIFFERENT_ENTITY: { DIFFERENT_ENTITY: 0, SAME_ENTITY: 3, REVIEW: 3 },
    SAME_ENTITY: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 0, REVIEW: 2 },
    REVIEW: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 2, REVIEW: 0 },
  };

  const DECISION_LABEL = {
    DIFFERENT_ENTITY: "Different entity",
    SAME_ENTITY: "Same entity",
    REVIEW: "Review",
  };
  const DECISION_CLASS = {
    DIFFERENT_ENTITY: "diff",
    SAME_ENTITY: "same",
    REVIEW: "review",
  };

  const state = {
    bundle: null,
    importedPreds: null,
    filter: { decision: "ALL", q: "", labeled: false, disagree: false, category: "ALL" },
    selectedId: null,
    selectedCustomer: null,
    pollTimer: null,
    view: "queue",
    screen: null,
  };

  const $ = (id) => document.getElementById(id);

  const ICON = {
    all: '<path d="M4 6h16M4 12h16M4 18h10"/>',
    same: '<path d="M12 3 4 6v6c0 4.4 3.4 8 8 9 4.6-1 8-4.6 8-9V6z"/><path d="M12 8v4M12 15.5h.01"/>',
    review: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.5 3.6-5.5 7-5.5s6.2 2 7 5.5"/>',
    diff: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    pending: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    labeled: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h4"/>',
    disagree: '<path d="M7 7h10M7 7l3-3M7 7l3 3M17 17H7M17 17l-3-3M17 17l-3 3"/>',
    scan: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.8-4.8M8 10.5h5M10.5 8v5"/>',
    note: '<path d="M5 4h10l4 4v12H5z"/><path d="M9 12h6M9 16h4"/>',
    map: '<circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="5" r="2.5"/><circle cx="19" cy="19" r="2.5"/><path d="M7.5 12h4l5-6.5M11.5 12l5 6.5"/>',
    alert: '<path d="M12 4 3 19h18z"/><path d="M12 10v4M12 17h.01"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    person: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.5 3.6-5.5 7-5.5s6.2 2 7 5.5"/>',
    idcard: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.6-1.5 1.7-2 3-2s2.4.5 3 2M14 10h4M14 13h3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z"/>',
    list: '<path d="M12 3 4 6v6c0 4.4 3.4 8 8 9 4.6-1 8-4.6 8-9V6z"/><path d="M9 12h6"/>',
  };
  const svg = (k, cls = "ico") => {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", cls); s.setAttribute("aria-hidden", "true");
    s.innerHTML = ICON[k] || ""; return s;
  };
  const nf = new Intl.NumberFormat("en-GB");
  const NOTES_KEY = "fathom.analystNotes.v1";
  function loadNotes() {
    try { return JSON.parse(localStorage.getItem(NOTES_KEY) || "{}") || {}; } catch (_) { return {}; }
  }
  function saveNotes(n) {
    try { localStorage.setItem(NOTES_KEY, JSON.stringify(n)); return true; } catch (_) { return false; }
  }
  function noteCount() {
    return Object.values(loadNotes()).reduce((a, l) => a + l.length, 0);
  }
  const PAGE = {
    queue: ["Review queue", "Every watchlist hit with the system’s decision and the records behind it"],
    screen: ["Screen a person", "Check one name against every watchlist entry before or after onboarding"],
    notes: ["Analyst notes", "Information you’ve added to cases, kept in this browser"],
    map: ["Link map", "How one alert’s records connect, from the screened customer to the decision"],
  };


  function el(tag, attrs, ...children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === "class") n.className = v;
        else if (k === "dataset") Object.assign(n.dataset, v);
        else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
        else if (k === "html") n.innerHTML = v;
        else n.setAttribute(k, v === true ? "" : String(v));
      }
    }
    for (const c of children) {
      if (c == null || c === false) continue;
      n.appendChild(c instanceof Node ? c : document.createTextNode(asText(c)));
    }
    return n;
  }

  function text(v) {
    if (v == null || v === "" || (Array.isArray(v) && v.length === 0)) return null;
    return v;
  }

  // Official data can carry lists and objects where the workbook had plain text
  // (e.g. hits.details is {"pep": "..."}, practice_labels.path is a list).
  function asText(v) {
    if (v == null) return "";
    if (Array.isArray(v)) return v.map(asText).filter(Boolean).join(", ");
    if (typeof v === "object") {
      return Object.entries(v).map(([k, x]) => { const s = asText(x); return s ? `${String(k).replace(/_/g, " ")}: ${s}` : ""; }).filter(Boolean).join("; ");
    }
    return String(v);
  }
  function asList(v) {
    if (v == null || v === "") return [];
    const arr = Array.isArray(v) ? v : [v];
    return arr.filter((x) => x != null && x !== "").map((x) => (typeof x === "object" ? asText(x) : x)).filter((x) => x !== "");
  }

  function fold(s) {
    return String(s || "")
      .normalize("NFKD")
      .replace(/\p{M}/gu, "")
      .toLowerCase()
      .trim();
  }

  function nameParts(s) {
    const cleaned = fold(s)
      .replace(/\([^)]*\)/g, " ")
      .replace(/[^\p{L}\p{N}\s]/gu, " ");
    const stop = new Set(["aka", "n", "a", "the", "of", "and"]);
    return cleaned.split(/\s+/).filter((t) => t && !stop.has(t) && !/^\d+$/.test(t));
  }

  function lev(a, b) {
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    const m = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 0; j <= b.length; j++) m[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + cost);
      }
    }
    return m[a.length][b.length];
  }

  function partMatch(a, b, variants) {
    if (a === b) return true;
    if (variants && variants[a] && variants[a] === variants[b]) return true;
    const shorter = a.length <= b.length ? a : b;
    const d = lev(a, b);
    if (shorter.length < 4) return false;
    if (shorter.length <= 6) return d <= 1;
    return d <= 2;
  }

  function namesAgree(aNames, bNames, variants) {
    const A = aNames.flatMap(nameParts);
    const B = bNames.flatMap(nameParts);
    if (!A.length || !B.length) return { status: "unknown", matched: 0 };
    const used = new Set();
    let matched = 0;
    for (const pa of A) {
      let found = -1;
      for (let i = 0; i < B.length; i++) {
        if (used.has(i)) continue;
        if (partMatch(pa, B[i], variants)) {
          found = i;
          break;
        }
      }
      if (found >= 0) {
        used.add(found);
        matched++;
      }
    }
    const shorter = Math.min(A.length, B.length);
    const agree = matched >= 2 || (shorter > 0 && matched >= shorter);
    return { status: agree ? "agree" : "conflict", matched, a: A, b: B };
  }

  const MONTHS = {
    january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
    july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
    jan: 1, feb: 2, mar: 3, apr: 4, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12,
  };

  function parseDate(value) {
    if (value == null || value === "") return null;
    const s = String(value).trim();
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return { y: +m[1], m: +m[2], d: +m[3], raw: s };
    m = s.match(/^(\d{4})-(\d{2})(?!\d)/);
    if (m) return { y: +m[1], m: +m[2], d: null, raw: s };
    m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m) return { y: +m[3], m: +m[2], d: +m[1], raw: s };
    m = s.match(/^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})/);
    if (m && MONTHS[m[2].toLowerCase()]) return { y: +m[3], m: MONTHS[m[2].toLowerCase()], d: +m[1], raw: s };
    m = s.match(/^([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})/);
    if (m && MONTHS[m[1].toLowerCase()]) return { y: +m[3], m: MONTHS[m[1].toLowerCase()], d: +m[2], raw: s };
    m = s.match(/^(\d{4})(?!\d)/);
    if (m) return { y: +m[1], m: null, d: null, raw: s };
    return { y: null, m: null, d: null, raw: s };
  }

  function extractRecordDates(text) {
    if (!text) return [];
    const out = [];
    const re = /(?:born|dob|d\.o\.b\.?|date of birth|birth date|verified dob)[:\s,]*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{4})/gi;
    let m;
    while ((m = re.exec(String(text)))) {
      const p = parseDate(m[1]);
      if (p && p.y) out.push(p);
    }
    return out;
  }

  function fmtDate(p) {
    if (!p) return null;
    if (p.y && p.m && p.d) return `${String(p.y).padStart(4, "0")}-${String(p.m).padStart(2, "0")}-${String(p.d).padStart(2, "0")}`;
    if (p.y && p.m) return `${String(p.y).padStart(4, "0")}-${String(p.m).padStart(2, "0")}`;
    if (p.y) return String(p.y);
    return p.raw;
  }

  function datesAgree(c, h) {
    if (!c || !h || c.y == null || h.y == null) return null;
    if (c.y !== h.y) return false;
    if (c.m && h.m && c.m !== h.m) return false;
    if (c.d && h.d && c.d !== h.d) return false;
    return true;
  }

  function datesConflict(c, h) {
    if (!c || !h || c.y == null || h.y == null) return false;
    if (Math.abs(c.y - h.y) > 1) return true;
    if (c.y === h.y && c.m && h.m && c.m !== h.m) return true;
    if (c.y === h.y && c.m && h.m && c.m === h.m && c.d && h.d && c.d !== h.d) return true;
    return false;
  }

  function extractNoteDobs(notes) {
    if (!notes) return [];
    const first = String(notes).split(/\n\s*\n/)[0];
    const found = [];
    const age = first.match(/\b(\d{1,3})-year-old\b|\baged\s+(\d{1,3})\b/i);
    const years = [...first.matchAll(/\b(19|20)\d{2}\b/g)].map((m) => +m[0]);
    if (age && years.length) {
      const n = +(age[1] || age[2]);
      if (n >= 10 && n <= 110) {
        const y = years[0];
        found.push({ y: y - n, m: null, d: null, raw: `${y - n} (from age ${n} in ${y})` });
        found.push({ y: y - n - 1, m: null, d: null, raw: `${y - n - 1} (from age ${n} in ${y})` });
      }
    }
    const born = [...first.matchAll(/\bborn\b[^.]{0,40}?((?:19|20)\d{2}(?:-\d{2}(?:-\d{2})?)?|\d{1,2}[\/]\d{1,2}[\/](?:19|20)\d{2})/gi)];
    for (const m of born) {
      const p = parseDate(m[1]);
      if (p && p.y) found.push(p);
    }
    return found;
  }

  function dobStatus(custDates, hitDates) {
    const C = custDates.map(parseDate).filter(Boolean);
    const H = hitDates.map(parseDate).filter(Boolean);
    if (!C.length || !H.length) return "unknown";
    if (C.some((c) => H.some((h) => datesAgree(c, h)))) return "agree";
    if (H.every((h) => C.every((c) => datesConflict(c, h)))) return "conflict";
    return "unknown";
  }

  function countryCanon(value, lookup, notCountries, loose) {
    if (value == null) return null;
    let s = String(value).replace(/\[[^\]]*\]/g, "").trim();
    if (!s) return null;
    const tryLookup = (raw) => {
      const k = fold(raw);
      if (!k) return null;
      if (notCountries && notCountries.has(k)) return null;
      if (lookup && lookup[k]) return lookup[k];
      return null;
    };
    let hit = tryLookup(s);
    if (hit) return hit;
    if (s.includes(",")) {
      hit = tryLookup(s.split(",").pop().trim());
      if (hit) return hit;
    }
    if (loose) {
      const k = fold(s);
      if (notCountries && notCountries.has(k)) return null;
      return s;
    }
    return null;
  }

  function countrySet(values, lookup, notCountries, loose) {
    const out = new Set();
    for (const v of asList(values)) {
      const c = countryCanon(v, lookup, notCountries, loose);
      if (c) out.add(c);
    }
    return out;
  }

  function countriesFromText(text, lookup, notCountries) {
    const out = new Set();
    if (!text || !lookup) return out;
    const words = String(text).split(/[^\p{L}]+/u).filter(Boolean);
    for (let i = 0; i < words.length; i++) {
      const grams = [words[i]];
      if (i + 1 < words.length) grams.push(words[i] + " " + words[i + 1]);
      if (i + 2 < words.length) grams.push(words[i] + " " + words[i + 1] + " " + words[i + 2]);
      for (const g of grams) {
        if (g.length <= 2) continue; // skip ISO-style tokens in free text
        const k = fold(g);
        if (notCountries && notCountries.has(k)) continue;
        if (lookup[k]) out.add(lookup[k]);
      }
    }
    return out;
  }

  function setStatus(a, b) {
    if (!a.size || !b.size) return "unknown";
    for (const x of a) if (b.has(x)) return "agree";
    return "conflict";
  }

  function entityNorm(t) {
    const s = fold(t);
    if (!s) return null;
    if (s.includes("indiv") || s.includes("person")) return "Individual";
    if (s.includes("comp") || s.includes("org") || s.includes("entity") || s.includes("corp")) return "Company";
    return t;
  }

  function latestApprovedKyc(ids, bundle) {
    let best = null;
    for (const id of ids || []) {
      const k = bundle.kyc_checks[id];
      if (!k) continue;
      if (String(k.result || "").toLowerCase() !== "approved") continue;
      if (!best || String(k.checked_at || "") > String(best.checked_at || "")) best = k;
    }
    return best;
  }

  function predictions(bundle) {
    return bundle.predictions || {};
  }

  function isSample(bundle, pred) {
    if (pred && (pred._sample || pred.sample)) return true;
    return !!(bundle && bundle.meta && bundle.meta.sample_predictions);
  }

  function computeStats(bundle) {
    const preds = Object.values(predictions(bundle));
    const labels = bundle.labels || {};
    const counts = { DIFFERENT_ENTITY: 0, SAME_ENTITY: 0, REVIEW: 0, pending: 0, total: Object.keys(bundle.hits).length };
    const seen = new Set();
    for (const p of preds) {
      if (p && p.decision && counts[p.decision] != null) {
        counts[p.decision]++;
        seen.add(p.hit_id);
      }
    }
    counts.pending = counts.total - seen.size;

    let cost = 0, baseline = 0, labeled = 0, unsafe = 0;
    let tpDiff = 0, goldDiff = 0, predDiff = 0, tpSame = 0, goldSame = 0;
    const confusion = {};
    const predMap = predictions(bundle);
    for (const lab of Object.values(labels)) {
      if (!lab || !lab.hit_id) continue;
      const p = predMap[lab.hit_id];
      if (!p || !p.decision) continue;
      const g = lab.decision;
      const d = p.decision;
      if (!COST[g] || COST[g][d] == null) continue;
      labeled++;
      cost += COST[g][d];
      baseline += COST[g].REVIEW;
      confusion[g + ">" + d] = (confusion[g + ">" + d] || 0) + 1;
      if (d === "DIFFERENT_ENTITY" && (g === "SAME_ENTITY" || g === "REVIEW")) unsafe++;
      if (g === "DIFFERENT_ENTITY") {
        goldDiff++;
        if (d === "DIFFERENT_ENTITY") tpDiff++;
      }
      if (d === "DIFFERENT_ENTITY") predDiff++;
      if (g === "SAME_ENTITY") {
        goldSame++;
        if (d === "SAME_ENTITY") tpSame++;
      }
    }
    let decisionScore = baseline > 0 ? Math.max(0, 1 - cost / baseline) : null;
    const metaScore = bundle.meta && bundle.meta.practice_score;
    if (labeled === 0 && metaScore && metaScore.labeled) {
      labeled = metaScore.labeled;
      cost = metaScore.cost;
      baseline = metaScore.baseline_review_cost;
      decisionScore = metaScore.decision_score;
      unsafe = metaScore.unsafe_clearances;
    }
    return {
      counts,
      labeled,
      cost,
      baseline,
      decisionScore,
      unsafe,
      confusion,
      fpClearedShare: goldDiff ? tpDiff / goldDiff : null,
      clearancePrecision: predDiff ? tpDiff / predDiff : null,
      sameRecall: goldSame ? tpSame / goldSame : null,
      reviewRate: counts.total ? counts.REVIEW / counts.total : 0,
      sample: isSample(bundle),
    };
  }

  function variantMap(bundle) {
    const idx = {};
    for (const group of (bundle.name_variants && bundle.name_variants.given_names) || []) {
      if (!group || !group.length) continue;
      const canon = fold(group[0]);
      for (const n of group) idx[fold(n)] = canon;
    }
    return idx;
  }

  function lookupMaps(bundle) {
    const raw = (bundle.countries && bundle.countries.lookup) || {};
    const lookup = {};
    for (const [k, v] of Object.entries(raw)) lookup[fold(k)] = v;
    const notCountries = new Set(((bundle.countries && bundle.countries.not_countries) || []).map(fold));
    return { lookup, notCountries };
  }

  function categoryOf(hit) {
    return hit.primary_category || (hit.categories && hit.categories[0]) || "Unspecified";
  }

  function buildQueue(bundle) {
    const { filter } = state;
    const q = fold(filter.q);
    const variants = variantMap(bundle);
    const rows = [];
    for (const hit of Object.values(bundle.hits)) {
      const pred = predictions(bundle)[hit.hit_id] || null;
      const lab = bundle.labels[hit.hit_id] || null;
      const alert = bundle.alerts[hit.alert_id] || {};
      const decision = pred && pred.decision ? pred.decision : "PENDING";
      if (filter.decision === "PENDING" && decision !== "PENDING") continue;
      if (filter.decision !== "ALL" && filter.decision !== "PENDING" && decision !== filter.decision) continue;
      if (filter.labeled && !lab) continue;
      if (filter.disagree) {
        if (!lab || !pred || lab.decision === pred.decision) continue;
      }
      if (filter.category !== "ALL" && categoryOf(hit) !== filter.category) continue;
      if (q) {
        const hay = [
          hit.hit_id, hit.alert_id, hit.name, ...(hit.aliases || []),
          alert.customer_name, pred && pred.customer_record_id, pred && pred.reason_code,
          pred && pred.reason, categoryOf(hit),
        ]
          .filter(Boolean)
          .map(fold)
          .join(" | ");
        if (!hay.includes(q)) continue;
      }
      const disagree = !!(lab && pred && lab.decision !== pred.decision);
      rows.push({ hit, pred, lab, alert, decision, disagree, cat: categoryOf(hit) });
    }
    const rank = { SAME_ENTITY: 0, REVIEW: 1, DIFFERENT_ENTITY: 2, PENDING: 3 };
    rows.sort((a, b) => {
      if (a.disagree !== b.disagree) return a.disagree ? -1 : 1;
      if (!!a.lab !== !!b.lab) return a.lab ? -1 : 1;
      const ra = rank[a.decision] ?? 9, rb = rank[b.decision] ?? 9;
      if (ra !== rb) return ra - rb;
      return (b.hit.match_score || 0) - (a.hit.match_score || 0);
    });
    return rows;
  }

  function fmtPct(x) {
    if (x == null || Number.isNaN(x)) return "—";
    return `${(x * 100).toFixed(1)}%`;
  }

  function renderStats(bundle) {
    const s = computeStats(bundle);
    const c = s.counts;
    const total = c.total || 1;
    const share = (n) => `${Math.round((n / total) * 100)}%`;
    const kpi = (cls, label, value, note, badge) =>
      el("div", { class: "kpi " + cls },
        el("div", { class: "kpi-top" }, el("span", { class: "kpi-label" }, label), badge ? el("span", { class: "kpi-badge" }, badge) : null),
        el("div", { class: "kpi-value" }, value),
        el("div", { class: "kpi-note" }, note)
      );
    const labs = Object.values(bundle.labels || {});
    const predMap = predictions(bundle);
    const dots = el("div", { class: "lab-dots", "aria-hidden": "true" },
      ...labs.map((l) => {
        const p = predMap[l.hit_id];
        const st = !p || !p.decision ? "none" : p.decision === l.decision ? "ok" : (p.decision === "DIFFERENT_ENTITY" ? "unsafe" : "off");
        return el("i", { class: st, title: `${l.hit_id}: label ${DECISION_LABEL[l.decision] || l.decision}${p && p.decision ? ", system " + (DECISION_LABEL[p.decision] || p.decision) : ""}` });
      })
    );
    const agree = labs.filter((l) => predMap[l.hit_id] && predMap[l.hit_id].decision === l.decision).length;
    const scoreTitle = s.sample
      ? "Sample predictions copy the practice labels, so this reads 100% until real output is loaded"
      : "Share of the review-everything cost saved on the practice labels (an unsafe clear costs 60)";
    $("stats").replaceChildren(
      kpi("k-total", "Hits reviewed", nf.format(c.total - c.pending), c.pending ? `${c.pending} still pending` : `Across ${nf.format(Object.keys(bundle.alerts || {}).length)} alerts`),
      kpi("k-same", "Same entity", nf.format(c.SAME_ENTITY), "Sent to compliance", share(c.SAME_ENTITY)),
      kpi("k-review", "Review", nf.format(c.REVIEW), "Routed to an analyst", share(c.REVIEW)),
      kpi("k-diff", "Different entity", nf.format(c.DIFFERENT_ENTITY), "False positives closed", share(c.DIFFERENT_ENTITY)),
      el("div", { class: "kpi k-score", title: scoreTitle },
        el("div", null,
          el("div", { class: "kpi-top" }, el("span", { class: "kpi-label" }, "Practice check")),
          el("div", { class: "kpi-value" }, s.decisionScore == null ? "—" : fmtPct(s.decisionScore)),
          el("div", { class: "kpi-note" }, s.labeled ? `${agree} of ${s.labeled} match the labels` : "No practice labels loaded")
        ),
        el("div", { class: "score-side" },
          dots,
          el("div", { class: "unsafe" + (s.unsafe ? " bad" : "") },
            el("span", { class: "u-n" }, s.labeled ? String(s.unsafe) : "—"),
            el("span", null, s.unsafe === 1 ? "unsafe clear" : "unsafe clears")
          )
        )
      ),
    );
    const live = !s.sample && Object.keys(predictions(bundle)).length;
    const pill = $("mode-pill");
    pill.textContent = live ? "Live output" : "Sample data";
    pill.className = "pill " + (live ? "pill-live" : "pill-sample");
    const src = $("source-sub");
    if (src) {
      const n = Object.keys(predictions(bundle)).length;
      const from = (bundle.meta && bundle.meta.prediction_source) || "output/dev.jsonl";
      src.textContent = live ? `${nf.format(n)} decisions from ${String(from).replace(/^\/track2\//, "")}` : "Practice-label answers, not the system";
      const chg = $("btn-change-data");
      if (chg) chg.hidden = state.dataSource !== "browser";
    }
    const banner = $("sample-banner");
    const showBanner = !live;
    banner.hidden = !showBanner;
    document.body.classList.toggle("has-banner", showBanner);
  }

  function renderFilters() {
    const f = state.filter;
    const bundle = state.bundle;
    const s = computeStats(bundle);
    const predMap = predictions(bundle);
    const labs = Object.values(bundle.labels || {});
    const disagreeN = labs.filter((l) => predMap[l.hit_id] && predMap[l.hit_id].decision && predMap[l.hit_id].decision !== l.decision).length;
    const groups = [
      ["Decisions", [
        ["ALL", "All hits", "all", s.counts.total],
        ["SAME_ENTITY", "Same entity", "same", s.counts.SAME_ENTITY],
        ["REVIEW", "Review", "review", s.counts.REVIEW],
        ["DIFFERENT_ENTITY", "Different entity", "diff", s.counts.DIFFERENT_ENTITY],
        ...(s.counts.pending ? [["PENDING", "Pending", "pending", s.counts.pending]] : []),
      ]],
      ["Practice set", [
        ["LABELED", "Labeled only", "labeled", labs.length],
        ["DISAGREE", "Disagreements", "disagree", disagreeN],
      ]],
      ["Tools", [
        ["VIEW:screen", "Screen a person", "scan", null],
        ["VIEW:map", "Link map", "map", null],
        ["VIEW:notes", "Analyst notes", "note", noteCount()],
      ]],
    ];
    const box = $("filters");
    box.replaceChildren();
    for (const [title, items] of groups) {
      box.appendChild(el("div", { class: "nav-title" }, title));
      for (const [key, label, icon, count] of items) {
        const isView = key.startsWith("VIEW:");
        const toggle = key === "LABELED" || key === "DISAGREE";
        const on = isView ? state.view === key.slice(5)
          : key === "LABELED" ? f.labeled && state.view === "queue"
          : key === "DISAGREE" ? f.disagree && state.view === "queue"
          : f.decision === key && state.view === "queue";
        const btn = el("button", {
          type: "button",
          class: "nav-item" + (on ? " on" : "") + " n-" + icon,
          "aria-pressed": on ? "true" : "false",
          onclick: () => {
            if (isView) { state.view = key.slice(5); render(); return; }
            state.view = "queue";
            if (key === "LABELED") f.labeled = !f.labeled;
            else if (key === "DISAGREE") f.disagree = !f.disagree;
            else f.decision = key;
            render();
          },
        }, svg(icon), el("span", null, label),
          toggle ? el("span", { class: "toggle" + (on ? " on" : "") }, el("i"))
            : count == null ? null : el("span", { class: "count" }, nf.format(count || 0)));
        if (toggle) btn.appendChild(el("span", { class: "count sub" }, String(count || 0)));
        box.appendChild(btn);
      }
    }
  }

  function renderQueue(rows) {
    const f = state.filter;
    $("queue-meta").replaceChildren(
      el("span", null, f.decision === "ALL" && !f.labeled && !f.disagree && !f.q ? `${nf.format(rows.length)} hits` : `${nf.format(rows.length)} of ${nf.format(Object.keys(state.bundle.hits).length)} hits`),
    );
    const box = $("queue");
    box.replaceChildren();
    if (!rows.length) {
      box.appendChild(el("div", { class: "queue-empty" }, "No hits match. Clear the search or pick another filter."));
      return;
    }
    for (const row of rows) {
      const cls = DECISION_CLASS[row.decision] || "pending";
      const on = row.hit.hit_id === state.selectedId;
      const item = el(
        "div",
        {
          class: "queue-item" + (on ? " on" : ""),
          role: "option",
          tabindex: "-1",
          "aria-selected": on ? "true" : "false",
          onclick: () => selectHit(row.hit.hit_id),
        },
        el("div", null,
          el("div", { class: "q-name" }, row.hit.name || "Unnamed"),
          el("div", { class: "q-cust" }, "Customer ", el("b", null, row.alert.customer_name || "unknown")),
          el("div", { class: "q-sub" },
            el("span", { class: "mono" }, row.hit.hit_id),
            el("span", null, row.cat),
            row.lab ? el("span", { class: "flag" + (row.disagree ? " bad" : "") }, row.disagree ? "Label differs" : "Labeled") : null,
            (state._notes && state._notes[row.hit.hit_id] && state._notes[row.hit.hit_id].length) ? el("span", { class: "flag note" }, "Note") : null
          )
        ),
        el("div", { class: "q-right" },
          el("span", { class: "dec " + cls }, row.decision === "PENDING" ? "Pending" : DECISION_LABEL[row.decision] || row.decision)
        )
      );
      box.appendChild(item);
    }
    const sel = box.querySelector(".queue-item.on");
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }

  function selectHit(id, customerId) {
    state.selectedId = id;
    state.selectedCustomer = customerId || null;
    if (id && location.hash !== "#" + id) {
      history.replaceState(null, "", "#" + id);
    }
    render();
  }

  function customerCountries(cust, kyc, lookup, notCountries) {
    const vals = [];
    if (cust) {
      // Nationality and ISO residence may be used loosely; city/address only if the gazetteer recognises them.
      for (const v of countrySet([cust.nationality, cust.residence_country], lookup, notCountries, true)) vals.push(v);
      for (const v of countrySet([cust.city, cust.address], lookup, notCountries, false)) vals.push(v);
    }
    if (kyc) {
      for (const v of countrySet([kyc.document_country], lookup, notCountries, true)) vals.push(v);
    }
    return countrySet(vals, lookup, notCountries, true);
  }

  function hitCountries(hit, lookup, notCountries) {
    const vals = [
      ...asList(hit.countries),
      ...asList(hit.nationality),
      ...asList(hit.citizenship),
      ...asList(hit.addresses),
      ...asList(hit.place_of_birth),
    ];
    return countrySet(vals, lookup, notCountries);
  }

  function displayList(items, empty = "—") {
    const arr = asList(items);
    if (!arr.length) return el("span", { class: "missing" }, empty);
    if (arr.length === 1) return document.createTextNode(String(arr[0]));
    return el("ul", { class: "val-list" }, ...arr.map((x) => el("li", null, String(x))));
  }

  function compareRows(cust, hit, kyc, alert, bundle, noteIds) {
    bundle._activeNoteIds = noteIds || [];
    const variants = variantMap(bundle);
    const { lookup, notCountries } = lookupMaps(bundle);

    const custNames = [];
    if (kyc && kyc.verified_name) custNames.push(kyc.verified_name);
    if (cust) custNames.push(cust.full_name, cust.preferred_name, cust.login_name);
    if (alert) custNames.push(alert.customer_name);
    const hitNames = [hit.name, ...asList(hit.aliases)];
    const nameCmp = namesAgree(custNames.filter(Boolean), hitNames.filter(Boolean), variants);

    const noteDates = [];
    const noteDateSources = [];
    for (const nid of asList(bundle._activeNoteIds)) {
      const n = bundle.notes[nid];
      if (!n) continue;
      for (const p of extractRecordDates(n.text)) {
        noteDates.push(fmtDate(p) || p.raw);
        noteDateSources.push(nid);
      }
    }
    const custDobsPrimary = [];
    if (kyc && kyc.verified_dob) custDobsPrimary.push(kyc.verified_dob + " (verified " + kyc.check_id + ")");
    for (let i = 0; i < noteDates.length; i++) {
      custDobsPrimary.push(noteDates[i] + " (from " + noteDateSources[i] + ")");
    }
    const custDobsDeclared = [];
    if (cust && cust.dob) custDobsDeclared.push(cust.dob + (custDobsPrimary.length ? " (declared)" : ""));
    if (alert && alert.dob && (!cust || cust.dob !== alert.dob)) custDobsDeclared.push(alert.dob + " (screened)");
    const custDobs = custDobsPrimary.length ? custDobsPrimary.concat(custDobsDeclared) : custDobsDeclared;
    const custDobsForStatus = (kyc && kyc.verified_dob)
      ? [kyc.verified_dob]
      : (noteDates.length ? noteDates : custDobsDeclared);
    const hitDobs = asList(hit.dobs);
    const noteDobs = (!hitDobs.length) ? extractNoteDobs(hit.profile_notes) : [];
    const dobSt = dobStatus(custDobsForStatus, hitDobs.length ? hitDobs : noteDobs.map((p) => String(p.y)));

    const cCountries = customerCountries(cust, kyc, lookup, notCountries);
    for (const nid of asList(bundle._activeNoteIds)) {
      const n = bundle.notes[nid];
      if (!n) continue;
      for (const c of countriesFromText(n.text, lookup, notCountries)) cCountries.add(c);
    }
    const hCountries = hitCountries(hit, lookup, notCountries);
    const locSt = setStatus(cCountries, hCountries);

    const cType = entityNorm((cust && cust.entity_type) || (alert && alert.entity_type));
    const hType = entityNorm(hit.entity_type);
    const typeSt = !cType || !hType ? "unknown" : cType === hType ? "agree" : "conflict";

    const cNat = countrySet([cust && cust.nationality, kyc && kyc.document_country], lookup, notCountries);
    const hNat = countrySet([...asList(hit.nationality), ...asList(hit.citizenship)], lookup, notCountries);
    const natSt = setStatus(cNat, hNat);

    function showDates(arr) {
      const parsed = arr.map(parseDate).filter(Boolean);
      if (!parsed.length) return el("span", { class: "missing" }, "Not given");
      const uniq = [...new Set(parsed.map(fmtDate))];
      return displayList(uniq);
    }

    const rows = [
      {
        label: "Entity type",
        left: cType || el("span", { class: "missing" }, "Not given"),
        right: hType || el("span", { class: "missing" }, "Not given"),
        status: typeSt,
      },
      {
        label: "Name",
        left: displayList(
          [
            kyc && kyc.verified_name ? `${kyc.verified_name} (verified)` : null,
            cust && cust.full_name,
            cust && cust.preferred_name ? `${cust.preferred_name} (preferred)` : null,
            !cust && alert ? alert.customer_name : null,
          ].filter(Boolean)
        ),
        right: displayList([hit.name, ...asList(hit.aliases)]),
        status: nameCmp.status,
      },
      {
        label: "Date of birth",
        left: custDobs.length ? displayList(custDobs) : el("span", { class: "missing" }, "Not given"),
        right: hitDobs.length
          ? showDates(hitDobs)
          : (noteDobs.length
            ? displayList(noteDobs.map((p) => p.raw))
            : el("span", { class: "missing" }, "Not given")),
        status: dobSt,
      },
      {
        label: "Nationality",
        left: cNat.size ? displayList([...cNat]) : el("span", { class: "missing" }, "Not given"),
        right: hNat.size ? displayList([...hNat]) : el("span", { class: "missing" }, "Not given"),
        status: natSt,
      },
      {
        label: "Countries",
        left: cCountries.size ? displayList([...cCountries]) : el("span", { class: "missing" }, "Not given"),
        right: hCountries.size ? displayList([...hCountries]) : el("span", { class: "missing" }, "Not given"),
        status: locSt,
      },
      {
        label: "City / address",
        left: displayList([cust && cust.city, cust && cust.address, alert && alert.city].filter(Boolean), "Not given"),
        right: displayList(hit.addresses, "Not given"),
        status: "unknown",
      },
      {
        label: "Identifiers",
        left: displayList([cust && cust.registration_number, kyc && kyc.document_type && kyc.document_number ? `${kyc.document_type} ${kyc.document_number}` : null].filter(Boolean), "Not given"),
        right: displayList(hit.identifiers, "Not given"),
        status: "unknown",
      },
      {
        label: "Occupation",
        left: displayList([cust && cust.occupation, cust && cust.employer].filter(Boolean), "Not given"),
        right: displayList([hit.position_or_allegation].filter(Boolean), "Not given"),
        status: "unknown",
      },
      {
        label: "Life status",
        left: el("span", { class: "missing" }, "—"),
        right: displayList([hit.life_status, hit.deceased_date && `Deceased ${hit.deceased_date}`].filter(Boolean), "Not given"),
        status: hit.deceased_date ? "conflict" : "unknown",
      },
      {
        label: "Gender",
        left: el("span", { class: "missing" }, "—"),
        right: hit.gender || el("span", { class: "missing" }, "Not given"),
        status: "unknown",
      },
    ];
    return rows;
  }

  function highlightReason(text, evidence) {
    const raw = String(text || "").trim() || "No reason text.";
    const ids = (evidence || []).slice().sort((a, b) => b.length - a.length);
    const wrap = el("div", { class: "reason-text" });
    if (!ids.length) {
      wrap.textContent = raw;
      return wrap;
    }
    const re = new RegExp("(" + ids.map((i) => i.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")");
    for (const part of raw.split(re)) {
      if (ids.includes(part)) wrap.appendChild(el("button", { type: "button", class: "idchip", title: "Show this record", onclick: () => {
        const card = document.querySelector(`.ev-card[data-ev="${part}"]`);
        if (card) { card.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash"); }
      } }, part));
      else wrap.appendChild(document.createTextNode(part));
    }
    return wrap;
  }

  function findRecord(id, bundle) {
    if (!id) return null;
    const tables = [
      ["Customer", "customers"],
      ["Account", "accounts"],
      ["KYC check", "kyc_checks"],
      ["Note", "notes"],
      ["Search result", "search_results"],
      ["Hit", "hits"],
      ["Alert", "alerts"],
    ];
    for (const [kind, key] of tables) {
      if (bundle[key] && bundle[key][id]) return { kind, rec: bundle[key][id] };
    }
    if (id.startsWith("APP-")) {
      const rows = (bundle.onboarding || []).filter((o) => o.kyc_applicant_id === id);
      if (rows.length) return { kind: "Applicant / onboarding", rec: rows[0] };
    }
    return null;
  }

  function evRows(pairs) {
    const body = el("div", { class: "ev-body" });
    for (const [k, v] of pairs) {
      if (v == null || v === "" || (Array.isArray(v) && !v.length)) continue;
      body.appendChild(el("div", { class: "row" }, el("div", { class: "k" }, k), el("div", null, Array.isArray(v) ? v.join(", ") : String(v))));
    }
    return body;
  }

  function evidenceCard(id, bundle, cited) {
    const found = findRecord(id, bundle);
    const card = el("div", { class: "ev-card" + (cited ? " cited" : ""), "data-ev": id });
    if (!found) {
      card.append(
        el("div", { class: "ev-top" }, el("div", { class: "ev-id" }, id), el("div", { class: "ev-kind" }, "Not in bundle"))
      );
      return card;
    }
    const { kind, rec } = found;
    card.append(el("div", { class: "ev-top" }, el("div", { class: "ev-id mono" }, id), el("div", { class: "ev-kind" }, kind), cited ? el("span", { class: "ev-cited" }, "Cited") : null));
    if (kind === "Customer") {
      card.append(evRows([
        ["Name", rec.full_name], ["Preferred", rec.preferred_name], ["DOB", rec.dob],
        ["Type", rec.entity_type], ["Nationality", rec.nationality],
        ["Residence", rec.residence_country], ["City", rec.city], ["Address", rec.address],
        ["Email", rec.email], ["Phone", rec.phone], ["Occupation", rec.occupation],
        ["Employer", rec.employer], ["Reg. no.", rec.registration_number],
        ["Onboarded", rec.onboarded_at], ["Status", rec.status],
      ]));
    } else if (kind === "KYC check") {
      card.append(evRows([
        ["Result", rec.result], ["Verified name", rec.verified_name], ["Verified DOB", rec.verified_dob],
        ["Document", [rec.document_type, rec.document_number].filter(Boolean).join(" ")],
        ["Country", rec.document_country], ["Provider", rec.provider], ["Checked", rec.checked_at],
        ["Applicant", rec.applicant_id],
      ]));
    } else if (kind === "Note") {
      card.append(evRows([
        ["When", rec.created_at], ["Channel", rec.channel], ["Email", rec.requester_email],
      ]));
      if (rec.text) card.appendChild(el("div", { class: "ev-text" }, rec.text));
    } else if (kind === "Search result") {
      card.append(evRows([["Query", rec.query], ["Title", rec.title], ["Source", rec.source]]));
      if (rec.snippet) card.appendChild(el("div", { class: "ev-text" }, rec.snippet));
    } else if (kind === "Account") {
      card.append(evRows([
        ["Customer", rec.customer_id], ["Login", rec.login_handle], ["Phone", rec.phone],
        ["Opened", rec.opened_at], ["Status", rec.status],
      ]));
    } else if (kind === "Hit") {
      card.append(evRows([["Name", rec.name], ["Type", rec.entity_type], ["DOBs", rec.dobs], ["Countries", rec.countries]]));
    } else if (kind === "Alert") {
      card.append(evRows([
        ["Screened", rec.customer_name], ["DOB", rec.dob], ["Account", rec.account_ref],
        ["Login", rec.login_handle], ["Email", rec.email],
      ]));
    } else {
      card.append(evRows(Object.entries(rec)));
    }
    return card;
  }

  function renderCase(bundle) {
    const stage = $("stage");
    const hit = bundle.hits[state.selectedId];
    if (!hit) {
      stage.replaceChildren(
        el("div", { class: "empty", id: "empty" },
          el("div", { class: "empty-title" }, "Select a hit"),
          el("div", { class: "empty-sub" }, "Use the queue, or press J / K to move.")
        )
      );
      return;
    }
    const pred = predictions(bundle)[hit.hit_id] || null;
    const lab = bundle.labels[hit.hit_id] || null;
    const alert = bundle.alerts[hit.alert_id] || {};
    const cse = bundle.cases[hit.alert_id] || { candidate_customer_ids: [], kyc_ids: [], note_ids: [], account_ids: [], search_ids: [], person_groups: [] };
    const decision = pred && pred.decision ? pred.decision : "PENDING";
    const dcls = DECISION_CLASS[decision] || "pending";
    const reasonCode = (pred && pred.reason_code) || "";
    const codeMeta = (bundle.reason_codes || {})[reasonCode];

    let resolvedIds = [];
    if (pred && pred.customer_record_id && pred.customer_record_id !== "AMBIGUOUS" && pred.customer_record_id !== "null") {
      resolvedIds = [pred.customer_record_id];
    } else if (pred && pred.customer_record_id === "AMBIGUOUS") {
      const fromEv = asList(pred.evidence).filter((id) => String(id).startsWith("CUS-"));
      resolvedIds = fromEv.length ? fromEv : (cse.candidate_customer_ids || []);
    } else if (lab && lab.customer_record_ids && lab.customer_record_ids.length) {
      resolvedIds = lab.customer_record_ids;
    } else {
      resolvedIds = cse.candidate_customer_ids || [];
    }

    const uniqueCust = [...new Set(resolvedIds.filter((id) => bundle.customers[id]))];
    if (!state.selectedCustomer || !uniqueCust.includes(state.selectedCustomer)) {
      state.selectedCustomer = uniqueCust[0] || null;
    }
    const cust = state.selectedCustomer ? bundle.customers[state.selectedCustomer] : null;

    // KYC for this person (group if possible)
    let personIds = [state.selectedCustomer].filter(Boolean);
    for (const g of cse.person_groups || []) {
      if (state.selectedCustomer && g.includes(state.selectedCustomer)) personIds = g;
    }
    const personKyc = (cse.kyc_ids || []).filter((id) => {
      const k = bundle.kyc_checks[id];
      if (!k) return false;
      return (bundle.onboarding || []).some(
        (o) => o.kyc_applicant_id === k.applicant_id && personIds.includes(o.customer_id)
      );
    });
    const kyc = latestApprovedKyc(personKyc.length ? personKyc : cse.kyc_ids, bundle);

    const fmtLong = (d) => {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(d || ""));
      if (!m) return d;
      return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
    };
    const meta = (k, v, mono) => v == null || v === "" ? null : el("span", { class: "meta" }, el("span", { class: "meta-k" }, k), el("span", { class: mono ? "mono" : "" }, v));
    const head = el("div", null,
      el("div", { class: "case-meta" },
        meta("Hit", hit.hit_id, true),
        meta("Alert", hit.alert_id, true),
        meta("Screened", fmtLong(alert.screened_at)),
        meta("Match score", hit.match_score != null ? String(hit.match_score) : null, true),
        el("button", { type: "button", class: "map-open", onclick: () => { state.mapHit = hit.hit_id; state.mapMode = "case"; state.mapPos = null; state.view = "map"; render(); } }, svg("map"), "Link map")
      ),
      el("h2", { class: "case-title" }, hit.name || "Unnamed list entry"),
      el("div", { class: "case-sub" },
        el("span", null, "Screened customer ", el("b", null, alert.customer_name || "unknown")),
        ...asList(hit.categories).map((c) => el("span", { class: "tag" }, c))
      )
    );
    const decisionCard = el("section", { class: "decision " + dcls },
      el("div", { class: "d-top" },
        el("div", null,
          el("div", { class: "d-label" }, "Decision"),
          el("div", { class: "d-value" }, decision === "PENDING" ? "Pending" : DECISION_LABEL[decision] || decision),
          el("div", { class: "d-what" }, {
            SAME_ENTITY: "This hit is the customer. Escalate to compliance.",
            DIFFERENT_ENTITY: "A fact contradicts the hit, so it was cleared as a false positive.",
            REVIEW: "The records can’t settle it, so an analyst should look.",
            PENDING: "No decision has been produced for this hit yet.",
          }[decision] || "")
        ),
        el("div", { class: "d-code" },
          el("span", { class: "mono" }, reasonCode || "No reason code"),
          pred && pred.customer_record_id ? el("span", { class: "d-cust" }, "Customer record ", el("span", { class: "mono" }, String(pred.customer_record_id))) : null
        )
      ),
      highlightReason(pred && pred.reason, pred && pred.evidence),
      codeMeta && codeMeta.when ? el("div", { class: "d-rule" }, el("span", null, "Rule"), codeMeta.when) : null
    );
    const parts = [head, decisionCard];

    if (pred && isSample(bundle, pred) && pred._sample_source === "practice_labels") {
      parts.push(el("div", { class: "label-row" }, el("span", { class: "lab-k" }, "Source"), el("span", null, "Sample copied from the practice labels")));
    }

    if (lab) {
      const disagree = pred && pred.decision && pred.decision !== lab.decision;
      parts.push(el("div", { class: "label-row " + (pred && pred.decision ? (disagree ? "disagree" : "agree") : "") },
        el("span", { class: "lab-icon" }, svg(disagree ? "disagree" : "labeled")),
        el("span", { class: "lab-k" }, disagree ? "Disagrees with the practice label" : pred && pred.decision ? "Matches the practice label" : "Practice label"),
        el("span", null, `${DECISION_LABEL[lab.decision] || lab.decision}`, el("span", { class: "mono lab-code" }, (lab.reason_codes || []).join(", ")))
      ));
    }

    parts.push(notesPanel(hit.hit_id));

    if (uniqueCust.length > 1) {
      parts.push(el("div", { class: "person-switch" },
        el("span", { class: "ps-k" }, `${uniqueCust.length} customer records fit this alert`),
        el("div", { class: "seg" }, ...uniqueCust.map((id) => {
          const c = bundle.customers[id];
          return el("button", {
            type: "button",
            class: id === state.selectedCustomer ? "on" : "",
            onclick: () => { state.selectedCustomer = id; render(); },
          }, el("span", { class: "mono" }, id), c && c.full_name ? " " + c.full_name : "");
        }))
      ));
    }

    // Comparison table (paper)
    const noteIdsForCompare = [];
    const custEmail = fold(cust && cust.email);
    for (const nid of asList(cse.note_ids)) {
      const n = bundle.notes[nid];
      if (n && custEmail && fold(n.requester_email) === custEmail) noteIdsForCompare.push(nid);
    }
    for (const id of asList(pred && pred.evidence)) {
      if (String(id).startsWith("NOTE-") && !noteIdsForCompare.includes(id)) noteIdsForCompare.push(id);
    }
    const rows = compareRows(cust, hit, kyc, alert, bundle, noteIdsForCompare);
    const screenedBits = [
      ["Name", alert.customer_name], ["Date of birth", alert.dob], ["Country", alert.country], ["City", alert.city],
      ["Account", alert.account_ref, true], ["Login", alert.login_handle, true], ["Email", alert.email, true],
    ].filter((b) => b[1]);
    const statusWord = { agree: "Agrees", conflict: "Conflict", unknown: "Not compared" };
    const table = el("section", { class: "compare" },
      el("div", { class: "sec-head" },
        el("h3", null, "Customer and list entry, side by side"),
        el("div", { class: "screened" }, el("span", { class: "meta-k" }, "As screened"),
          ...(screenedBits.length ? screenedBits.map(([k, v, mono]) => el("span", { class: "sc" }, `${k} `, el("span", { class: mono ? "mono" : "" }, v))) : [el("span", null, "No screened identity fields")]))
      ),
      el("div", { class: "field-grid fg-head" },
        el("div", null, "Field"),
        el("div", null, "Customer ", cust ? el("span", { class: "mono" }, cust.record_id) : el("span", { class: "missing" }, "unresolved")),
        el("div", null, "List entry ", el("span", { class: "mono" }, hit.hit_id)),
        el("div", { class: "status" }, "Check")
      ),
      ...rows.map((r) => el("div", { class: "field-grid row-" + r.status },
        el("div", { class: "fcell lab" }, r.label),
        el("div", { class: "fcell val" }, r.left),
        el("div", { class: "fcell val" }, r.right),
        el("div", { class: "fcell status" }, el("span", { class: "status-pill " + r.status }, statusWord[r.status] || r.status))
      )),
      kyc
        ? el("div", { class: "compare-foot" }, "Verified identity from approved check ", el("span", { class: "mono" }, kyc.check_id), ` on ${fmtLong(kyc.checked_at) || "an unknown date"}: ${kyc.verified_name || "no name"}, born ${kyc.verified_dob || "unknown"}, ${kyc.document_country || "no"} document`)
        : (!cust ? el("div", { class: "compare-foot" }, "No customer record is resolved for this alert, so the customer column uses the screened details only") : null)
    );
    parts.push(table);

    // Evidence
    const cited = [...asList(pred && pred.evidence)];
    if (lab) {
      for (const id of asList(lab.evidence)) if (!cited.includes(id)) { /* keep cited as prediction's; we'll still show label evidence */ }
    }
    const evIds = [];
    const addEv = (id, force) => {
      if (!id || evIds.includes(id)) return;
      evIds.push(id);
    };
    cited.forEach((id) => addEv(id));
    asList(lab && lab.evidence).forEach((id) => addEv(id));
    asList(cse.kyc_ids).forEach((id) => addEv(id));
    asList(cse.note_ids).forEach((id) => addEv(id));
    if (cust) addEv(cust.record_id);
    asList(cse.search_ids).slice(0, 6).forEach((id) => addEv(id));

    const evPanel = el("section", { class: "panel", id: "evidence-panel" },
      el("div", { class: "sec-head" }, el("h3", null, "Evidence records"),
        el("div", { class: "sec-note" }, "Records cited in the decision are marked. Click a highlighted ID in the reasoning to jump here")));
    if (!evIds.length) {
      evPanel.appendChild(el("div", { class: "muted" }, "No evidence records are attached to this hit yet"));
    } else {
      const gridE = el("div", { class: "evidence-grid" });
      const citedSet = new Set(cited.length ? cited : asList(lab && lab.evidence));
      const ordered = [...evIds].sort((a, b) => (citedSet.has(b) ? 1 : 0) - (citedSet.has(a) ? 1 : 0));
      for (const id of ordered) gridE.appendChild(evidenceCard(id, bundle, citedSet.has(id)));
      evPanel.appendChild(gridE);
    }
    parts.push(evPanel);

    if (lab && lab.reference_reason) {
      parts.push(el("div", { class: "panel" },
        el("h3", null, "Practice reference reason"),
        highlightReason(lab.reference_reason, lab.evidence)
      ));
    }
    if (lab && lab.path) {
      parts.push(el("div", { class: "panel" },
        el("h3", null, "Path through the files"),
        el("div", { class: "path" }, Array.isArray(lab.path) ? lab.path.map(asText).join("  →  ") : asText(lab.path))
      ));
    }

    if (hit.profile_notes || hit.details || (hit.relationships && hit.relationships.length) || (hit.sources && hit.sources.length) || (hit.source_urls && hit.source_urls.length)) {
      const prof = el("div", { class: "panel" }, el("h3", null, "List-entry profile"));
      if (hit.position_or_allegation) prof.appendChild(el("div", { class: "prof-pos" }, hit.position_or_allegation));
      if (hit.details) prof.appendChild(el("div", { class: "prof-det" }, hit.details));
      if (hit.profile_notes) prof.appendChild(el("div", { class: "notes-block" }, hit.profile_notes));
      if (hit.relationships && hit.relationships.length) {
        prof.appendChild(el("h4", null, "Relationships"));
        prof.appendChild(el("ul", { class: "rel-list" }, ...hit.relationships.map((r) => el("li", null, String(r)))));
      }
      const urls = asList(hit.source_urls);
      const srcs = asList(hit.sources);
      if (urls.length || srcs.length) {
        prof.appendChild(el("h4", null, "Sources"));
        const box = el("div", { class: "sources" });
        for (const s of srcs) box.appendChild(el("div", null, String(s)));
        for (const u of urls) box.appendChild(el("div", null, el("a", { href: u, target: "_blank", rel: "noreferrer" }, u)));
        prof.appendChild(box);
      }
      parts.push(prof);
    }

    const caseEl = el("div", { class: "case" }, ...parts);
    stage.replaceChildren(caseEl);
    const scrollTo = new URLSearchParams(location.search).get("scroll");
    if (scrollTo === "evidence") {
      const ev = caseEl.querySelector("#evidence-panel");
      if (ev) ev.scrollIntoView({ block: "start" });
    } else {
      stage.scrollTop = 0;
    }
  }

  // ---------- Tools: analyst notes ----------
  function fmtWhen(iso) {
    try { return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch (_) { return iso; }
  }
  function notesPanel(hitId) {
    const list = (state._notes || {})[hitId] || [];
    const box = el("section", { class: "notes-panel" },
      el("div", { class: "sec-head" }, el("h3", null, "Analyst notes"), el("div", { class: "sec-note" }, list.length ? `${list.length} on this case` : "Add what you’ve learned that the records don’t show")));
    for (const [i, n] of list.entries()) {
      box.appendChild(el("div", { class: "note-item" },
        el("div", { class: "note-text" }, n.text),
        el("div", { class: "note-meta" }, el("span", null, fmtWhen(n.at)),
          el("button", { type: "button", class: "link-btn", onclick: () => { const all = loadNotes(); all[hitId].splice(i, 1); if (!all[hitId].length) delete all[hitId]; saveNotes(all); render(); } }, "Delete"))
      ));
    }
    const ta = el("textarea", { class: "note-input", rows: "2", placeholder: "e.g. Customer sent a passport copy, DOB is 1979, not 1977", "aria-label": "New analyst note" });
    const add = () => {
      const v = ta.value.trim(); if (!v) { ta.focus(); return; }
      const all = loadNotes(); (all[hitId] = all[hitId] || []).push({ text: v, at: new Date().toISOString() });
      if (!saveNotes(all)) { ta.setCustomValidity("This browser blocked saving notes"); ta.reportValidity(); return; }
      render();
    };
    ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); add(); } });
    box.appendChild(el("div", { class: "note-add" }, ta,
      el("div", { class: "note-actions" }, el("span", { class: "muted small" }, "⌘ Enter to save"), el("button", { type: "button", class: "btn primary sm-fixed", onclick: add }, "Add note"))));
    return box;
  }

  function openCase(id) {
    state.view = "queue";
    state.selectedId = id;
    state.selectedCustomer = null;
    history.replaceState(null, "", "#" + id);
    render();
  }

  function renderNotes(bundle) {
    const all = loadNotes();
    const ids = Object.keys(all).filter((id) => all[id].length).sort((a, b) => {
      const la = all[a][all[a].length - 1].at, lb = all[b][all[b].length - 1].at; return lb.localeCompare(la);
    });
    const preds = predictions(bundle);
    const exportBtn = el("button", { type: "button", class: "btn", onclick: () => {
      const rows = ids.flatMap((id) => all[id].map((n) => ({ hit_id: id, alert_id: bundle.hits[id] && bundle.hits[id].alert_id, note: n.text, added_at: n.at })));
      const blob = new Blob([rows.map((r) => JSON.stringify(r)).join("\n") + "\n"], { type: "application/jsonl" });
      const a = el("a", { href: URL.createObjectURL(blob), download: "analyst-notes.jsonl" }); document.body.appendChild(a); a.click(); a.remove();
    } }, "Export notes");
    if (!ids.length) exportBtn.disabled = true;
    const wrap = el("div", { class: "tool" },
      el("div", { class: "tool-head" },
        el("div", null, el("h2", { class: "tool-title" }, ids.length ? `${noteCount()} ${noteCount() === 1 ? "note" : "notes"} on ${ids.length} ${ids.length === 1 ? "case" : "cases"}` : "No notes yet"),
          el("p", { class: "tool-sub" }, "Notes are saved in this browser only. Export them to share with the team.")),
        exportBtn));
    if (!ids.length) {
      wrap.appendChild(el("div", { class: "tool-empty" }, "Open any case and use Analyst notes under the decision to record something the records don’t show."));
    }
    for (const id of ids) {
      const hit = bundle.hits[id] || {}; const p = preds[id];
      const cls = p ? DECISION_CLASS[p.decision] || "pending" : "pending";
      const card = el("div", { class: "note-case" },
        el("div", { class: "nc-head" },
          el("button", { type: "button", class: "nc-title", onclick: () => openCase(id) }, hit.name || id),
          el("span", { class: "mono muted" }, id),
          p ? el("span", { class: "dec " + cls }, DECISION_LABEL[p.decision] || p.decision) : null),
        ...all[id].map((n) => el("div", { class: "note-item" }, el("div", { class: "note-text" }, n.text), el("div", { class: "note-meta" }, el("span", null, fmtWhen(n.at)))))
      );
      wrap.appendChild(card);
    }
    $("stage").replaceChildren(wrap);
  }


  // ---------- Tools: link map ----------
  function buildGraph(bundle, hitId) {
    const hit = bundle.hits[hitId]; if (!hit) return null;
    const alert = bundle.alerts[hit.alert_id] || {};
    const cse = bundle.cases[hit.alert_id] || {};
    const preds = predictions(bundle);
    const hitIds = asList(alert.hit_ids).length ? asList(alert.hit_ids) : [hitId];
    const cited = new Set(hitIds.flatMap((h) => asList(preds[h] && preds[h].evidence)));
    const resolved = new Set(hitIds.map((h) => preds[h] && preds[h].customer_record_id).filter((x) => x && bundle.customers[x]));
    const nodes = new Map(), edges = [];
    const add = (id, col, kind, icon, title, sub, extra = {}) => { if (!nodes.has(id)) nodes.set(id, { id, col, kind, icon, title, sub, ...extra }); return id; };
    const link = (a, b, label, strong) => { if (nodes.has(a) && nodes.has(b) && !edges.some((e) => e.a === a && e.b === b)) edges.push({ a, b, label, strong: !!strong }); };

    const A = add("alert:" + hit.alert_id, 0, "Alert", "alert", alert.customer_name || "Screened customer", hit.alert_id, { rec: hit.alert_id, meta: [alert.dob && "born " + alert.dob, alert.country].filter(Boolean).join(", ") });

    // how the alert reaches the bank's records
    const accIds = [...new Set([alert.account_ref, ...asList(cse.account_ids)].filter(Boolean))];
    const linkNodes = [];
    for (const acc of accIds) linkNodes.push(add(acc, 1, "Account", "link", bundle.accounts[acc] && bundle.accounts[acc].login_handle ? bundle.accounts[acc].login_handle : "Account", acc, { rec: acc }));
    if (alert.login_handle && !accIds.length) linkNodes.push(add("login:" + alert.login_handle, 1, "Login", "link", alert.login_handle, "login handle"));
    if (alert.email) linkNodes.push(add("email:" + alert.email, 1, "Email", "link", alert.email, "email on file"));
    if (!linkNodes.length) linkNodes.push(add("search:" + hit.alert_id, 1, "Name search", "scan", "No link on the alert", "matched by name, birth date, country"));
    linkNodes.forEach((n) => link(A, n, null, true));

    // customers
    const custIds = [...new Set([...asList(cse.candidate_customer_ids), ...resolved, ...[...cited].filter((x) => String(x).startsWith("CUS-"))])].filter((c) => bundle.customers[c]);
    const groups = asList(cse.person_groups);
    for (const cid of custIds) {
      const c = bundle.customers[cid];
      add(cid, 2, "Customer", "person", c.full_name || cid, cid, { rec: cid, resolved: resolved.has(cid), meta: [c.dob && "born " + c.dob, c.nationality || c.residence_country].filter(Boolean).join(", ") });
      let linked = false;
      for (const ln of linkNodes) {
        const lnode = nodes.get(ln);
        if (lnode.kind === "Account") {
          const accRec = bundle.accounts[lnode.rec];
          const joint = (bundle.onboarding || []).some((o) => o.account_id === lnode.rec && o.customer_id === cid);
          if ((accRec && accRec.customer_id === cid) || joint) { link(ln, cid, joint && accRec && accRec.customer_id !== cid ? "joint holder" : null, resolved.has(cid)); linked = true; }
        } else if (lnode.kind === "Email" && fold(c.email) === fold(alert.email)) { link(ln, cid, null, resolved.has(cid)); linked = true; }
        else if (lnode.kind === "Name search" || lnode.kind === "Login") { link(ln, cid, null, resolved.has(cid)); linked = true; }
      }
      if (!linked) link(linkNodes[0], cid, "same person", resolved.has(cid));
    }
    // same-person groups (records merged into one person)
    for (const g of groups) for (let i = 1; i < g.length; i++) if (nodes.has(g[0]) && nodes.has(g[i])) link(g[0], g[i], "same person", resolved.has(g[0]) || resolved.has(g[i]));

    // evidence: KYC, notes, web results
    const kycIds = [...new Set([...asList(cse.kyc_ids), ...[...cited].filter((x) => String(x).startsWith("KYC-"))])].filter((k) => bundle.kyc_checks[k]);
    for (const k of kycIds) {
      const r = bundle.kyc_checks[k];
      add(k, 3, "KYC check", "idcard", r.verified_name || "Identity check", k, { rec: k, cited: cited.has(k), meta: [r.result, r.document_country].filter(Boolean).join(", ") });
      const owners = (bundle.onboarding || []).filter((o) => o.kyc_applicant_id === r.applicant_id).map((o) => o.customer_id);
      const own = owners.find((o) => nodes.has(o));
      if (own) link(own, k, null, cited.has(k));
    }
    const noteIds = [...new Set([...asList(cse.note_ids), ...[...cited].filter((x) => String(x).startsWith("NOTE-"))])].filter((n) => bundle.notes[n]);
    for (const n of noteIds) {
      const r = bundle.notes[n];
      add(n, 3, "Note", "note", (r.text || "").slice(0, 48) + ((r.text || "").length > 48 ? "…" : ""), n, { rec: n, cited: cited.has(n), meta: [r.channel, r.created_at].filter(Boolean).join(", ") });
      const own = custIds.find((cid) => fold(bundle.customers[cid].email) === fold(r.requester_email));
      if (own) link(own, n, null, cited.has(n));
    }
    // watchlist hits + decisions
    for (const h of hitIds) {
      const H = bundle.hits[h]; if (!H) continue;
      add("hit:" + h, 4, "Watchlist hit", "list", H.name || h, h, { rec: h, focus: h === hitId, meta: categoryOf(H) });
      const p = preds[h];
      const dec = p && p.decision ? p.decision : "PENDING";
      add("dec:" + h, 5, "Decision", "map", DECISION_LABEL[dec] || "Pending", p && p.reason_code ? p.reason_code : "no decision", { decision: dec, focus: h === hitId, hit: h });
      link("hit:" + h, "dec:" + h, null, true);
      if (p && p.customer_record_id && nodes.has(p.customer_record_id)) link(p.customer_record_id, "dec:" + h, "resolved", true);
    }
    const srIds = [...new Set([...asList(cse.search_ids), ...[...cited].filter((x) => String(x).startsWith("SR-"))])].filter((s) => bundle.search_results[s]);
    for (const s of srIds) {
      const r = bundle.search_results[s];
      add(s, 3, "Web result", "globe", r.title || s, s, { rec: s, cited: cited.has(s), meta: r.source });
      link(s, "hit:" + hitId, cited.has(s) ? "about this hit" : null, cited.has(s));
    }
    // hits with no other way in hang off the alert
    for (const h of hitIds) if (nodes.has("hit:" + h) && !edges.some((e) => e.b === "hit:" + h)) link(A, "hit:" + h, "screened against", false);
    // cited evidence feeds the decision
    for (const id of cited) if (nodes.has(id) && nodes.get(id).col === 3) {
      const owner = hitIds.find((h) => asList(preds[h] && preds[h].evidence).includes(id));
      link(id, "dec:" + owner, "cited", true);
    }
    // cap busy columns
    const CAP = 9;
    const byCol = {};
    for (const n of nodes.values()) (byCol[n.col] = byCol[n.col] || []).push(n);
    for (const [col, list] of Object.entries(byCol)) {
      list.sort((a, b) => (b.cited || b.resolved || b.focus ? 1 : 0) - (a.cited || a.resolved || a.focus ? 1 : 0));
      if (list.length > CAP) {
        const drop = list.slice(CAP - 1);
        for (const d of drop) nodes.delete(d.id);
        const more = "more:" + col;
        nodes.set(more, { id: more, col: +col, kind: "More", icon: "all", title: `${drop.length} more`, sub: "not shown to keep the map readable" });
      }
    }
    const kept = edges.filter((e) => nodes.has(e.a) && nodes.has(e.b));
    return { nodes: [...nodes.values()], edges: kept, hit, alert };
  }


  // ---------- link map search ----------
  function mapSearch(bundle, q) {
    const f = fold(q).trim();
    if (f.length < 2) return [];
    const preds = predictions(bundle);
    const out = [];
    for (const hit of Object.values(bundle.hits)) {
      const alert = bundle.alerts[hit.alert_id] || {};
      const p = preds[hit.hit_id];
      const cust = p && p.customer_record_id && bundle.customers[p.customer_record_id];
      const fields = [hit.name, ...asList(hit.aliases), alert.customer_name, cust && cust.full_name];
      const ids = [hit.hit_id, hit.alert_id, p && p.customer_record_id, ...asList(p && p.evidence), ...asList((bundle.cases[hit.alert_id] || {}).candidate_customer_ids)];
      const idHit = ids.some((x) => x && fold(x) === f);
      const nameHit = fields.some((x) => x && fold(x).includes(f));
      if (!idHit && !nameHit) continue;
      out.push({ hit, alert, pred: p, score: idHit ? 0 : fields.findIndex((x) => x && fold(x).startsWith(f)) === -1 ? 2 : 1 });
    }
    const rank = { SAME_ENTITY: 0, REVIEW: 1, DIFFERENT_ENTITY: 2 };
    out.sort((a, b) => a.score - b.score || (rank[a.pred && a.pred.decision] ?? 3) - (rank[b.pred && b.pred.decision] ?? 3));
    return out;
  }

  function buildSearchGraph(bundle, q, results) {
    const MAX = 14;
    const shown = results.slice(0, MAX);
    const nodes = new Map(), edges = [];
    const add = (id, col, kind, icon, title, sub, extra = {}) => { if (!nodes.has(id)) nodes.set(id, { id, col, kind, icon, title, sub, ...extra }); return id; };
    const link = (a, b, label, strong) => { if (nodes.has(a) && nodes.has(b) && !edges.some((e) => e.a === a && e.b === b)) edges.push({ a, b, label, strong: !!strong }); };
    const Q = add("query", 0, "Search", "scan", `“${q}”`, `${results.length} matching ${results.length === 1 ? "hit" : "hits"}`, { meta: results.length > MAX ? `Showing the first ${MAX}` : "" });
    for (const r of shown) {
      const { hit, alert, pred } = r;
      const A = add("alert:" + hit.alert_id, 1, "Alert", "alert", alert.customer_name || "Screened customer", hit.alert_id, { rec: hit.alert_id });
      link(Q, A, null, false);
      const cse = bundle.cases[hit.alert_id] || {};
      const resolvedId = pred && pred.customer_record_id && bundle.customers[pred.customer_record_id] ? pred.customer_record_id : null;
      const cands = [...new Set([resolvedId, ...asList(cse.candidate_customer_ids)].filter((c) => c && bundle.customers[c]))].slice(0, resolvedId ? 1 : 2);
      for (const cid of cands) {
        const c = bundle.customers[cid];
        add(cid, 2, "Customer", "person", c.full_name || cid, cid, { rec: cid, resolved: cid === resolvedId, meta: [c.dob && "born " + c.dob, c.nationality || c.residence_country].filter(Boolean).join(", ") });
        link(A, cid, null, cid === resolvedId);
      }
      const H = add("hit:" + hit.hit_id, 3, "Watchlist hit", "list", hit.name || hit.hit_id, hit.hit_id, { rec: hit.hit_id, meta: categoryOf(hit) });
      const dec = pred && pred.decision ? pred.decision : "PENDING";
      const D = add("dec:" + hit.hit_id, 4, "Decision", "map", DECISION_LABEL[dec] || "Pending", pred && pred.reason_code ? pred.reason_code : "no decision", { decision: dec, hit: hit.hit_id });
      link(H, D, null, true);
      if (resolvedId) link(resolvedId, D, "resolved", true);
      link(A, H, resolvedId ? null : "screened against", false);
    }
    // the same customer behind several alerts is the interesting part
    for (const n of nodes.values()) if (n.kind === "Customer") {
      const inbound = edges.filter((e) => e.b === n.id && e.a.startsWith("alert:")).length;
      if (inbound > 1) { n.shared = true; n.meta = `On ${inbound} alerts` + (n.meta ? ", " + n.meta : ""); }
    }
    if (results.length > MAX) nodes.set("more:search", { id: "more:search", col: 1, kind: "More", icon: "all", title: `${results.length - MAX} more`, sub: "narrow the search to see them" });
    return { nodes: [...nodes.values()], edges, search: true, q, total: results.length, totalAlerts: new Set(results.map((r) => r.hit.alert_id)).size, shownHits: shown.length };
  }

  function mapSearchBox(bundle) {
    const wrap = el("div", { class: "map-search" });
    const input = el("input", { type: "search", value: state.mapQuery || "", placeholder: "Search a person, hit, alert or customer ID", "aria-label": "Search for a person or case to map", autocomplete: "off", role: "combobox", "aria-expanded": "false", "aria-controls": "map-results" });
    const list = el("div", { class: "map-results", id: "map-results", role: "listbox", hidden: "" });
    wrap.append(el("span", { class: "ms-icon" }, svg("scan")), input, list);
    let items = [], active = -1, timer = null;
    const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
    const pick = (i) => {
      const it = items[i]; if (!it || it.none) return;
      if (it.all) { state.mapQuery = input.value.trim(); state.mapMode = "search"; }
      else { state.mapMode = "case"; state.mapHit = it.hitId; state.mapQuery = input.value.trim(); }
      state.mapPos = null; close(); renderMap(bundle);
    };
    const paint = () => {
      list.replaceChildren(...items.map((it, i) => {
        const o = el("div", { class: "mr-item" + (i === active ? " active" : "") + (it.all ? " all" : "") + (it.none ? " none" : ""), role: "option", "aria-selected": i === active ? "true" : "false" }, ...it.content);
        o.addEventListener("mousedown", (e) => { e.preventDefault(); pick(i); });
        return o;
      }));
    };
    const update = () => {
      const q = input.value.trim();
      if (q.length < 2) { close(); return; }
      const res = mapSearch(bundle, q);
      items = [];
      if (res.length > 1) items.push({ all: true, content: [svg("map"), el("span", { class: "mr-main" }, `Map all ${res.length} results together`), el("span", { class: "mr-sub" }, "Shared people linked")] });
      for (const r of res.slice(0, 8)) {
        const dec = r.pred && r.pred.decision ? r.pred.decision : "PENDING";
        items.push({ hitId: r.hit.hit_id, content: [
          el("span", { class: "mr-dot " + (DECISION_CLASS[dec] || "pending") }),
          el("span", { class: "mr-main" }, r.hit.name || r.hit.hit_id, el("span", { class: "mr-cust" }, " · customer " + (r.alert.customer_name || "unknown"))),
          el("span", { class: "mr-sub mono" }, r.hit.hit_id) ] });
      }
      if (!res.length) items.push({ none: true, content: [el("span", { class: "mr-sub" }, `Nothing matches “${q}”`)] });
      if (res.length > 8) items.push({ none: true, content: [el("span", { class: "mr-sub" }, `${res.length - 8} more. Use “Map all” or keep typing`)] });
      active = items.findIndex((x) => !x.none);
      list.hidden = false; input.setAttribute("aria-expanded", "true"); paint();
    };
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(update, 120); });
    input.addEventListener("focus", () => { if (input.value.trim().length >= 2) update(); });
    input.addEventListener("blur", () => setTimeout(close, 100));
    input.addEventListener("keydown", (e) => {
      if (list.hidden && e.key === "Enter") { e.preventDefault(); update(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); if (!items.some((x) => !x.none)) return;
        let i = active;
        do { i = (i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length; } while (items[i].none);
        active = i; paint();
      } else if (e.key === "Enter") { e.preventDefault(); if (active >= 0) pick(active); }
      else if (e.key === "Escape") { close(); }
    });
    return wrap;
  }

  const NODE_W = 196, NODE_H = 64, LEVEL_GAP = 64, SIB_GAP = 20;
  function layoutGraph(g) {
    // top-down tree: one level per record type, children centred under their parents
    const levels = {};
    for (const n of g.nodes) (levels[n.col] = levels[n.col] || []).push(n);
    const order = Object.keys(levels).map(Number).sort((a, b) => a - b);
    const parentsOf = (id) => g.edges.filter((e) => e.b === id).map((e) => e.a);
    const widest = Math.max(...order.map((l) => levels[l].length));
    const fullW = widest * (NODE_W + SIB_GAP);
    const pos = {};
    order.forEach((lvl, li) => {
      const list = levels[lvl];
      // keep children near their parents: sort by mean parent x
      list.sort((a, b) => {
        const mx = (n) => { const ps = parentsOf(n.id).filter((p) => pos[p]); return ps.length ? ps.reduce((s, p) => s + pos[p].x, 0) / ps.length : fullW / 2; };
        return mx(a) - mx(b);
      });
      const w = list.length * (NODE_W + SIB_GAP) - SIB_GAP;
      list.forEach((n, i) => { pos[n.id] = { x: 48 + (fullW - w) / 2 + i * (NODE_W + SIB_GAP), y: 40 + li * (NODE_H + LEVEL_GAP) }; });
    });
    return pos;
  }

  function renderMap(bundle) {
    if (!state.mapHit || !bundle.hits[state.mapHit]) state.mapHit = state.selectedId || Object.keys(bundle.hits)[0];
    const searching = state.mapMode === "search" && state.mapQuery;
    const sres = searching ? mapSearch(bundle, state.mapQuery) : null;
    const g = searching && sres.length ? buildSearchGraph(bundle, state.mapQuery, sres) : buildGraph(bundle, state.mapHit);
    const mapKey = searching && sres.length ? "q:" + state.mapQuery : state.mapHit;
    const stage = $("stage");
    if (!g) { stage.replaceChildren(el("div", { class: "tool" }, el("div", { class: "tool-empty" }, "Pick a hit in the queue first."))); return; }
    if (!state.mapPos || state.mapPos._hit !== mapKey) { state.mapPos = layoutGraph(g); state.mapPos._hit = mapKey; state.mapView = null; }
    const pos = state.mapPos;
    const view = state.mapView || (state.mapView = { x: 0, y: 0, k: 1 });
    const preds = predictions(bundle);
    const p = preds[state.mapHit];
    const dec = p && p.decision ? p.decision : "PENDING";

    const layer = el("div", { class: "map-layer" });
    const svgNS = "http://www.w3.org/2000/svg";
    const edgeSvg = document.createElementNS(svgNS, "svg");
    edgeSvg.setAttribute("class", "map-edges");
    const defs = document.createElementNS(svgNS, "defs");
    defs.innerHTML = '<marker id="mArrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1 7 4 1 7" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></marker>';
    edgeSvg.appendChild(defs);
    layer.appendChild(edgeSvg);
    const edgeEls = g.edges.map((e) => {
      const path = document.createElementNS(svgNS, "path");
      path.setAttribute("class", "map-edge" + (e.strong ? " strong" : ""));
      path.setAttribute("marker-end", "url(#mArrow)");
      edgeSvg.appendChild(path);
      let lab = null;
      if (e.label) { lab = el("span", { class: "edge-label" + (e.strong ? " strong" : "") }, e.label); layer.appendChild(lab); }
      return { e, path, lab };
    });
    const nodeEls = {};
    for (const n of g.nodes) {
      const cls = ["map-node", "k-" + n.kind.toLowerCase().replace(/\s+/g, "-")];
      if (n.cited) cls.push("cited"); if (n.resolved) cls.push("resolved"); if (n.focus) cls.push("focus"); if (n.shared) cls.push("shared");
      if (n.decision) cls.push("dec-" + (DECISION_CLASS[n.decision] || "pending"));
      const node = el("div", { class: cls.join(" "), tabindex: "0", role: "button", "aria-label": `${n.kind}: ${n.title}` },
        el("span", { class: "mn-icon" }, svg(n.icon)),
        el("div", { class: "mn-body" },
          el("div", { class: "mn-kind" }, n.kind, n.cited ? el("span", { class: "mn-tag" }, "Cited") : null, n.resolved ? el("span", { class: "mn-tag" }, "Resolved") : null, n.shared ? el("span", { class: "mn-tag" }, "Shared") : null),
          el("div", { class: "mn-title" }, n.title),
          el("div", { class: "mn-sub mono" }, n.sub))
      );
      node.style.transform = `translate(${pos[n.id].x}px, ${pos[n.id].y}px)`;
      nodeEls[n.id] = node; layer.appendChild(node);
    }
    function drawEdges() {
      let maxX = 0, maxY = 0;
      for (const id in nodeEls) { maxX = Math.max(maxX, pos[id].x + NODE_W); maxY = Math.max(maxY, pos[id].y + NODE_H); }
      edgeSvg.setAttribute("width", maxX + 200); edgeSvg.setAttribute("height", maxY + 200);
      for (const { e, path, lab } of edgeEls) {
        const a = pos[e.a], b = pos[e.b];
        let x1, y1, x2, y2, d, lx, ly;
        if (Math.abs(a.y - b.y) < 8) { // same level: arc underneath
          const left = a.x < b.x ? a : b, right = a.x < b.x ? b : a;
          x1 = a.x + NODE_W / 2; y1 = a.y + NODE_H; x2 = b.x + NODE_W / 2; y2 = b.y + NODE_H + 4;
          const dip = 28 + Math.min(40, Math.abs(x2 - x1) * 0.08);
          d = `M${x1},${y1} C${x1},${y1 + dip} ${x2},${y2 + dip} ${x2},${y2}`;
          lx = (left.x + right.x + NODE_W) / 2; ly = y1 + dip * 0.75;
        } else {
          const down = b.y > a.y;
          x1 = a.x + NODE_W / 2; y1 = down ? a.y + NODE_H : a.y; x2 = b.x + NODE_W / 2; y2 = down ? b.y - 4 : b.y + NODE_H + 4;
          const dy = Math.max(28, Math.abs(y2 - y1) * 0.5) * (down ? 1 : -1);
          d = `M${x1},${y1} C${x1},${y1 + dy} ${x2},${y2 - dy} ${x2},${y2}`;
          lx = (x1 + x2) / 2; ly = (y1 + y2) / 2;
        }
        path.setAttribute("d", d);
        if (lab) lab.style.transform = `translate(${lx - lab.offsetWidth / 2}px, ${ly - 9}px)`;
      }
    }
    const canvas = el("div", { class: "map-canvas", tabindex: "-1" }, layer);
    const applyView = () => { layer.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.k})`; canvas.style.backgroundPosition = `${view.x}px ${view.y}px`; canvas.style.backgroundSize = `${20 * view.k}px ${20 * view.k}px`; zoomLabel.textContent = Math.round(view.k * 100) + "%"; };

    // details panel
    const panel = el("aside", { class: "map-panel" });
    function showDetail(n) {
      for (const id in nodeEls) nodeEls[id].classList.toggle("selected", id === n.id);
      const kids = [el("div", { class: "mp-kind" }, n.kind), el("div", { class: "mp-title" }, n.title)];
      if (n.meta) kids.push(el("div", { class: "mp-meta" }, n.meta));
      if (n.decision) {
        const pr = preds[n.hit];
        kids.push(el("span", { class: "dec " + (DECISION_CLASS[n.decision] || "pending") }, DECISION_LABEL[n.decision] || "Pending"));
        if (pr && pr.reason) kids.push(el("p", { class: "mp-reason" }, pr.reason));
        kids.push(el("button", { type: "button", class: "btn sm-fixed", onclick: () => openCase(n.hit) }, "Open case"));
      } else if (n.rec && findRecord(n.rec, bundle)) {
        kids.push(evidenceCard(n.rec, bundle, !!n.cited));
        if (n.kind === "Watchlist hit") kids.push(el("button", { type: "button", class: "btn sm-fixed", onclick: () => openCase(n.rec) }, "Open case"));
      } else if (n.sub) kids.push(el("div", { class: "mp-meta" }, n.sub));
      const linkedTo = g.edges.filter((e) => e.a === n.id || e.b === n.id).map((e) => g.nodes.find((x) => x.id === (e.a === n.id ? e.b : e.a))).filter(Boolean);
      if (linkedTo.length) kids.push(el("div", { class: "mp-links" }, el("div", { class: "mp-kind" }, `Linked to ${linkedTo.length}`),
        ...linkedTo.map((x) => el("button", { type: "button", class: "mp-link", onclick: () => showDetail(x) }, el("span", null, x.kind), el("span", { class: "mono" }, x.sub)))));
      panel.replaceChildren(...kids);
      for (const { e, path } of edgeEls) path.classList.toggle("hot", e.a === n.id || e.b === n.id);
    }

    // drag nodes, pan canvas
    let drag = null;
    canvas.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      const nodeEl = ev.target.closest(".map-node");
      const id = nodeEl ? Object.keys(nodeEls).find((k) => nodeEls[k] === nodeEl) : null;
      drag = { id, sx: ev.clientX, sy: ev.clientY, ox: id ? pos[id].x : view.x, oy: id ? pos[id].y : view.y, moved: false };
      canvas.setPointerCapture(ev.pointerId);
      canvas.classList.add(id ? "dragging-node" : "panning");
      if (nodeEl) nodeEl.classList.add("lift");
    });
    canvas.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      const dx = ev.clientX - drag.sx, dy = ev.clientY - drag.sy;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      if (drag.id) {
        pos[drag.id].x = drag.ox + dx / view.k; pos[drag.id].y = drag.oy + dy / view.k;
        nodeEls[drag.id].style.transform = `translate(${pos[drag.id].x}px, ${pos[drag.id].y}px)`;
        drawEdges();
      } else { view.x = drag.ox + dx; view.y = drag.oy + dy; applyView(); }
    });
    const end = () => {
      if (!drag) return;
      if (drag.id) { nodeEls[drag.id].classList.remove("lift"); if (!drag.moved) showDetail(g.nodes.find((n) => n.id === drag.id)); }
      canvas.classList.remove("dragging-node", "panning");
      drag = null;
    };
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    canvas.addEventListener("keydown", (ev) => {
      const nodeEl = ev.target.closest && ev.target.closest(".map-node");
      if (nodeEl && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); showDetail(g.nodes.find((n) => nodeEls[n.id] === nodeEl)); }
    });
    const zoomTo = (k, cx, cy) => {
      const r = canvas.getBoundingClientRect();
      cx = cx == null ? r.width / 2 : cx; cy = cy == null ? r.height / 2 : cy;
      const nk = Math.min(1.8, Math.max(0.35, k));
      view.x = cx - ((cx - view.x) * nk) / view.k; view.y = cy - ((cy - view.y) * nk) / view.k; view.k = nk; applyView();
    };
    canvas.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      if (ev.ctrlKey || ev.metaKey) { const r = canvas.getBoundingClientRect(); zoomTo(view.k * (ev.deltaY < 0 ? 1.1 : 0.9), ev.clientX - r.left, ev.clientY - r.top); }
      else { view.x -= ev.deltaX; view.y -= ev.deltaY; applyView(); }
    }, { passive: false });
    const fit = () => {
      const r = canvas.getBoundingClientRect();
      let minX = Infinity, minY = Infinity, maxX = 0, maxY = 0;
      for (const id in nodeEls) { minX = Math.min(minX, pos[id].x); minY = Math.min(minY, pos[id].y); maxX = Math.max(maxX, pos[id].x + NODE_W); maxY = Math.max(maxY, pos[id].y + NODE_H); }
      const k = Math.min(1, Math.max(0.7, Math.min((r.width - 48) / (maxX - minX + 48), (r.height - 130) / (maxY - minY + 40))));
      const w = (maxX - minX) * k, h = (maxY - minY) * k;
      view.k = k;
      // wide trees open centred on the top of the tree; pan to see the sides
      view.x = r.width / 2 - ((minX + maxX) / 2) * k;
      view.y = h + 130 <= r.height ? 44 + (r.height - 130 - h) / 2 - minY * k : 44 - minY * k;
      applyView();
    };
    const zoomLabel = el("span", { class: "zoom-label mono" }, "100%");
    const hitsInAlert = g.search ? [] : asList(g.alert.hit_ids);
    const toolbar = el("div", { class: "map-toolbar" },
      el("button", { type: "button", class: "tb-btn", title: "Zoom out", "aria-label": "Zoom out", onclick: () => zoomTo(view.k / 1.2) }, "−"),
      zoomLabel,
      el("button", { type: "button", class: "tb-btn", title: "Zoom in", "aria-label": "Zoom in", onclick: () => zoomTo(view.k * 1.2) }, "+"),
      el("span", { class: "tb-sep" }),
      el("button", { type: "button", class: "tb-btn wide", onclick: fit }, "Fit"),
      el("button", { type: "button", class: "tb-btn wide", onclick: () => { state.mapPos = null; renderMap(bundle); } }, "Reset layout")
    );
    const legend = el("div", { class: "map-legend" },
      el("span", null, el("i", { class: "lg-line strong" }), g.search ? "Resolved customer and decision" : "Path the decision used"),
      el("span", null, el("i", { class: "lg-line" }), "Other link"),
      el("span", null, "Drag nodes to rearrange, drag the background to pan, ⌘ scroll to zoom"));

    const head = g.search
      ? el("div", { class: "map-head" },
          el("div", null,
            el("div", { class: "case-meta" }, el("span", { class: "meta" }, el("span", { class: "meta-k" }, "Combined map"), el("span", null, `${g.total} ${g.total === 1 ? "hit" : "hits"} across ${g.totalAlerts} ${g.totalAlerts === 1 ? "alert" : "alerts"}` + (g.shownHits < g.total ? `, first ${g.shownHits} mapped` : "")))),
            el("h2", { class: "map-title" }, `Results for “${g.q}”`)),
          el("div", { class: "map-actions" }, mapSearchBox(bundle),
            el("button", { type: "button", class: "btn", onclick: () => { state.mapMode = "case"; state.mapQuery = ""; state.mapPos = null; renderMap(bundle); } }, "Back to case")))
      : el("div", { class: "map-head" },
          el("div", null,
            el("div", { class: "case-meta" },
              el("span", { class: "meta" }, el("span", { class: "meta-k" }, "Alert"), el("span", { class: "mono" }, g.hit.alert_id)),
              el("span", { class: "meta" }, el("span", { class: "meta-k" }, "Screened customer"), el("span", null, g.alert.customer_name || "unknown")),
              hitsInAlert.length > 1 ? el("span", { class: "meta" }, el("span", { class: "meta-k" }, "Hits on this alert"), el("span", { class: "mono" }, String(hitsInAlert.length))) : null),
            el("h2", { class: "map-title" }, g.hit.name || state.mapHit, el("span", { class: "dec " + (DECISION_CLASS[dec] || "pending") }, DECISION_LABEL[dec] || "Pending"))),
          el("div", { class: "map-actions" }, mapSearchBox(bundle),
            el("button", { type: "button", class: "btn", onclick: () => openCase(state.mapHit) }, "Open case")));
    if (searching && !sres.length) head.appendChild(el("div", { class: "map-note" }, `Nothing matches “${state.mapQuery}”, so this is still the current case`));
    const wrap = el("div", { class: "map-wrap" }, head, el("div", { class: "map-body" }, el("div", { class: "map-stage" }, canvas, toolbar, legend), panel));
    stage.replaceChildren(wrap);
    drawEdges();
    requestAnimationFrame(() => { drawEdges(); if (!state.mapViewSet) fit(); state.mapViewSet = false; applyView(); });
    showDetail(g.search ? (g.nodes.find((n) => n.shared) || g.nodes[0]) : (g.nodes.find((n) => n.focus && n.decision) || g.nodes[0]));
  }

  // ---------- Tools: screen a person ----------
  const LISTING_PHRASE = { sanctions: "a sanctioned individual", pep: "a politically exposed person", enforcement: "the subject of enforcement action", "adverse media": "named in adverse media", soe: "a state-owned enterprise official" };
  function hitBirthYears(bundle, hit, lookup, notCountries) {
    const listed = asList(hit.dobs);
    if (listed.length) return { dobs: listed, src: "listed" };
    const fromNotes = extractNoteDobs(hit.profile_notes).map((p) => String(p.y));
    if (fromNotes.length) return { dobs: fromNotes, src: "profile notes" };
    // web results about this hit: same kind of listing, in a country tied to the hit
    const cse = (bundle.cases || {})[hit.alert_id];
    if (!cse || !cse.search_ids) return { dobs: [], src: null };
    const phrase = LISTING_PHRASE[fold(categoryOf(hit))] || "named on a watchlist";
    const hc = hitCountries(hit, lookup, notCountries);
    const years = new Set();
    for (const id of cse.search_ids) {
      const r = bundle.search_results[id]; if (!r || !r.snippet) continue;
      if (!fold(r.snippet).includes(phrase)) continue;
      const sc = countriesFromText(r.snippet, lookup, notCountries);
      if (![...sc].some((c) => hc.has(c))) continue;
      const age = /(\d{1,3})-year-old|age of (\d{1,3})|aged? (\d{1,3})|, (\d{1,3})[,.]|\((\d{1,3})\)|\bat (\d{1,3})\b|then (\d{1,3})|being (\d{1,3})/.exec(r.snippet);
      const yr = /\b(19\d{2}|20\d{2})\b/.exec(r.snippet);
      if (!age || !yr) continue;
      const a = +age.slice(1).find(Boolean), y = +yr[1];
      if (a > 0 && a < 120) { years.add(String(y - a - 1)); years.add(String(y - a)); }
    }
    return { dobs: [...years], src: years.size ? "web results" : null };
  }

  function screenOne(bundle, q) {
    const variants = variantMap(bundle);
    const { lookup, notCountries } = lookupMaps(bundle);
    const qType = entityNorm(q.type);
    const qC = countrySet([q.country], lookup, notCountries);
    const out = [];
    for (const hit of Object.values(bundle.hits)) {
      const nm = q.name ? namesAgree([q.name], [hit.name, ...asList(hit.aliases)].filter(Boolean), variants) : { status: "unknown", matched: 0 };
      if (q.name && !nm.matched) continue;
      const hType = entityNorm(hit.entity_type);
      const typeSt = !qType || !hType ? "unknown" : qType === hType ? "agree" : "conflict";
      const hb = hitBirthYears(bundle, hit, lookup, notCountries);
      const hDobs = hb.dobs;
      const dobSt = q.dob ? dobStatus([q.dob], hDobs) : "unknown";
      const locSt = setStatus(qC, hitCountries(hit, lookup, notCountries));
      const nameSt = nm.status;
      if (!q.name) {
        // limited data: keep entries the given fields support and nothing contradicts
        const given = [q.dob ? dobSt : null, q.country ? locSt : null, q.type && !q.typeDefault ? typeSt : null].filter(Boolean);
        if (!given.includes("agree") || given.includes("conflict")) continue;
      }
      let verdict = "REVIEW", why = "Not enough agreement to confirm and nothing contradicts it";
      if (typeSt === "conflict") { verdict = "DIFFERENT_ENTITY"; why = "One is a person and the other a company"; }
      else if (dobSt === "conflict") { verdict = "DIFFERENT_ENTITY"; why = "Every birth date on the hit contradicts the one entered"; }
      else if (nameSt === "agree" && dobSt === "agree") { verdict = locSt === "conflict" ? "REVIEW" : "SAME_ENTITY"; why = locSt === "conflict" ? "Name and birth date agree but the countries differ" : "Name and birth date agree and nothing contradicts them"; }
      else if (locSt === "conflict") { verdict = "DIFFERENT_ENTITY"; why = "Every country differs"; }
      else if (qType === "Company" && nameSt === "agree" && locSt === "agree") { verdict = "SAME_ENTITY"; why = "Company name and country agree"; }
      else if (!q.name) { verdict = "REVIEW"; why = "Matches what you entered, but no name to compare"; }
      else if (nameSt !== "agree") { verdict = "REVIEW"; why = "Only part of the name matches"; }
      const score = (nameSt === "agree" ? 4 : nm.matched) + (dobSt === "agree" ? 3 : dobSt === "conflict" ? -3 : 0) + (locSt === "agree" ? 2 : locSt === "conflict" ? -2 : 0) + (typeSt === "conflict" ? -4 : 0);
      out.push({ hit, nameSt, dobSt, locSt, typeSt, verdict, why, score, hDobs, dobSrc: hb.src });
    }
    const rank = { SAME_ENTITY: 0, REVIEW: 1, DIFFERENT_ENTITY: 2 };
    out.sort((a, b) => rank[a.verdict] - rank[b.verdict] || b.score - a.score);
    return out;
  }

  function renderScreen(bundle) {
    const q = state.screen || { name: "", dob: "", country: "", type: "", typeDefault: true };
    const field = (label, name, ph, extra = {}) => el("label", null, label, el("input", { name, value: q[name] || "", placeholder: ph, autocomplete: "off", ...extra }));
    const form = el("form", { class: "screen-form" },
      field("Name", "name", "Full name, or just part of it"),
      field("Date of birth", "dob", "YYYY-MM-DD or year"),
      field("Country", "country", "e.g. France"),
      el("label", null, "Type", el("select", { name: "type" },
        ...[["", "Any"], ["Individual", "Individual"], ["Company", "Company"]].map(([v, l]) => el("option", v === (q.type || "") ? { value: v, selected: "" } : { value: v }, l)))),
      el("button", { type: "submit", class: "btn primary" }, "Scan watchlist")
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const typeVal = String(fd.get("type") || "");
      state.screen = { name: String(fd.get("name") || "").trim(), dob: String(fd.get("dob") || "").trim(), country: String(fd.get("country") || "").trim(), type: typeVal || "", typeDefault: !typeVal };
      if (!state.screen.name && !state.screen.dob && !state.screen.country) {
        const inp = form.querySelector("input[name=name]");
        inp.setCustomValidity("Enter at least a name, a date of birth or a country");
        inp.reportValidity(); inp.addEventListener("input", () => inp.setCustomValidity(""), { once: true });
        return;
      }
      renderScreen(bundle);
      const r = $("stage").querySelector(".screen-results"); if (r) r.scrollIntoView({ block: "start" });
    });
    const wrap = el("div", { class: "tool" },
      el("div", { class: "tool-head" }, el("div", null,
        el("h2", { class: "tool-title" }, "Check a name against all " + nf.format(Object.keys(bundle.hits).length) + " watchlist entries"),
        el("p", { class: "tool-sub" }, "Fill in as much or as little as you have. Any one field is enough, and every match is listed. Results use the case view’s matching rules and are indicative, not the decision system’s verdict."))),
      form);
    const ran = q.name || q.dob || q.country;
    const what = [q.name && `“${q.name}”`, q.dob && `born ${q.dob}`, q.country && `linked to ${q.country}`].filter(Boolean).join(", ");
    if (ran) {
      const res = screenOne(bundle, q);
      const counts = { SAME_ENTITY: 0, REVIEW: 0, DIFFERENT_ENTITY: 0 };
      res.forEach((r) => counts[r.verdict]++);
      const word = { agree: "Agrees", conflict: "Conflict", unknown: "—" };
      const cell = (st) => el("span", { class: "status-pill " + st }, word[st]);
      const box = el("section", { class: "screen-results" },
        el("div", { class: "sec-head" },
          el("h3", null, res.length ? `${nf.format(res.length)} watchlist ${res.length === 1 ? "entry matches" : "entries match"} ${what}` : `No watchlist entry matches ${what}`),
          res.length ? el("div", { class: "sec-note" }, `${counts.SAME_ENTITY} likely same, ${counts.REVIEW} to review, ${counts.DIFFERENT_ENTITY} ruled out`) : null));
      if (res.length) {
        const shown = res;
        box.appendChild(el("table", { class: "screen-table" },
          el("thead", null, el("tr", null, ...["Watchlist entry", "List", "Name", "Born", "Country", "Indicative result"].map((h) => el("th", null, h)))),
          el("tbody", null, ...shown.map((r) => el("tr", { class: "row", onclick: () => openCase(r.hit.hit_id), title: "Open this hit’s case" },
            el("td", null, el("div", { class: "st-name" }, r.hit.name), el("div", { class: "mono muted" }, r.hit.hit_id)),
            el("td", { class: "muted" }, categoryOf(r.hit)),
            el("td", null, cell(r.nameSt)),
            el("td", null, cell(r.dobSt), r.hDobs.length ? el("div", { class: "muted small" }, r.hDobs.slice(0, 3).join(" or ") + (r.dobSrc && r.dobSrc !== "listed" ? `, from ${r.dobSrc}` : "")) : null),
            el("td", null, cell(r.locSt)),
            el("td", null, el("span", { class: "dec " + DECISION_CLASS[r.verdict] }, DECISION_LABEL[r.verdict]), el("div", { class: "muted small" }, r.why))
          )))));
        if (res.length > 25) box.appendChild(el("p", { class: "muted small" }, "Add a birth date or country to narrow these down."));
      }
      wrap.appendChild(box);
    }
    $("stage").replaceChildren(wrap);
    if (!ran) form.querySelector("input").focus();
  }

  function render() {
    const bundle = state.bundle;
    if (!bundle) return;
    state._notes = loadNotes();
    renderStats(bundle);
    renderFilters();
    const [title, sub] = PAGE[state.view] || PAGE.queue;
    $("page-title").textContent = title;
    $("page-sub").textContent = sub;
    document.body.classList.toggle("tool-view", state.view !== "queue");
    document.body.classList.toggle("map-mode", state.view === "map");
    if (state.view === "screen") { renderScreen(bundle); return; }
    if (state.view === "notes") { renderNotes(bundle); return; }
    if (state.view === "map") { renderMap(bundle); return; }
    const rows = buildQueue(bundle);
    if (state.selectedId && !rows.some((r) => r.hit.hit_id === state.selectedId)) {
      // keep selection even if filtered out? Better to show it anyway in the stage, queue just won't highlight.
    }
    const fkey = JSON.stringify([state.filter.decision, state.filter.labeled, state.filter.disagree, state.filter.category, state.filter.q]);
    if (state._fkey !== undefined && state._fkey !== fkey && rows.length && !rows.some((r) => r.hit.hit_id === state.selectedId)) {
      state.selectedId = rows[0].hit.hit_id;
      state.selectedCustomer = null;
    }
    state._fkey = fkey;
    if (!state.selectedId && rows.length) state.selectedId = rows[0].hit.hit_id;
    renderQueue(rows);
    renderCase(bundle);
  }

  function move(delta) {
    const rows = buildQueue(state.bundle);
    if (!rows.length) return;
    const idx = rows.findIndex((r) => r.hit.hit_id === state.selectedId);
    const next = rows[Math.max(0, Math.min(rows.length - 1, (idx < 0 ? 0 : idx) + delta))];
    selectHit(next.hit.hit_id);
  }

  function parseJsonl(text) {
    const rows = [];
    for (const line of text.split(/\r?\n/)) {
      const s = line.trim();
      if (!s) continue;
      rows.push(JSON.parse(s));
    }
    return rows;
  }

  function applyPredictions(rows, source) {
    const map = {};
    for (const r of rows) {
      if (r && r.hit_id) map[r.hit_id] = r;
    }
    state.bundle.predictions = map;
    state.bundle.meta = state.bundle.meta || {};
    state.bundle.meta.sample_predictions = false;
    state.bundle.meta.prediction_source = source || "imported";
    state.bundle.meta.n_predictions = Object.keys(map).length;
    render();
  }

  function askForData(message) {
    // Static hosting (GitHub Pages): the analyst supplies the dataset; it never leaves the browser.
    return new Promise((resolve) => {
      const drop = $("data-drop"), input = $("data-file"), status = $("drop-status"), zone = $("drop-zone");
      $("boot-load").hidden = true;
      drop.hidden = false;
      status.textContent = message || "";
      status.classList.toggle("err", !!message);
      let busy = false;
      const go = async (files) => {
        if (busy || !files || !files.length) return;
        busy = true; zone.classList.add("working"); status.classList.remove("err");
        try {
          const bundle = await window.FathomLoader.fromFiles(files, (m) => { status.textContent = m + "…"; });
          drop.hidden = true; $("boot-load").hidden = false;
          resolve(bundle);
        } catch (err) {
          status.textContent = err.message || String(err); status.classList.add("err");
        } finally { busy = false; zone.classList.remove("working"); }
      };
      input.onchange = () => go(input.files);
      $("data-folder").onchange = (e) => go(e.target.files);
      zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("over"); };
      zone.ondragleave = () => zone.classList.remove("over");
      zone.ondrop = (e) => { e.preventDefault(); zone.classList.remove("over"); go(e.dataTransfer.files); };
    });
  }

  async function loadBundle() {
    $("boot-msg").textContent = "Loading case files…";
    let res = null;
    // The hosted site (Vercel) never ships a bundle (participant data stays off the web), so don't ask for one.
    const staticSite = /\.(vercel\.app|github\.io)$/i.test(location.hostname) || new URLSearchParams(location.search).has("static");
    if (!staticSite) {
      try { res = await fetch("data/bundle.json", { cache: "no-store" }); } catch (_) { res = null; }
    }
    if (res && res.ok) {
      state.bundle = await res.json();
      state.dataSource = "server";
    } else {
      if (!window.FathomLoader) throw new Error("No data/bundle.json and no in-browser loader. Run python3 ui/serve.py.");
      const cached = await window.FathomLoader.getCached();
      state.bundle = cached || await askForData();
      state.dataSource = "browser";
      render();
      return;
    }
    // If a live output file is being served, prefer it over sample predictions.
    try {
      const live = await fetch("/track2/output/dev.jsonl", { cache: "no-store" });
      if (live.ok) {
        const txt = await live.text();
        if (txt.trim()) {
          applyPredictions(parseJsonl(txt), "/track2/output/dev.jsonl");
          return;
        }
      }
    } catch (_) { /* static server without the proxy is fine */ }
    render();
  }

  async function pollMeta() {
    if (state.dataSource === "browser") return; // hosted site: nothing on the server to watch
    try {
      const res = await fetch("data/meta.json", { cache: "no-store" });
      if (!res.ok) return;
      const meta = await res.json();
      const cur = state.bundle && state.bundle.meta;
      if (!cur) return;
      if (meta.generated_at !== cur.generated_at || meta.output_mtime !== cur.output_mtime || meta.sample_predictions !== cur.sample_predictions || meta.n_predictions !== cur.n_predictions) {
        await loadBundle();
      }
    } catch (_) { /* ignore */ }
  }

  function bind() {
    $("q").addEventListener("input", (e) => {
      state.filter.q = e.target.value;
      render();
    });
    $("btn-change-data").addEventListener("click", async () => {
      await window.FathomLoader.clearCached();
      $("boot").classList.remove("done");
      state.bundle = await askForData();
      state.selectedId = null; state.mapPos = null;
      $("boot").classList.add("done");
      render();
    });
    $("btn-reload").addEventListener("click", () => {
      $("boot").classList.remove("done");
      loadBundle().finally(() => $("boot").classList.add("done"));
    });
    $("file-preds").addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      e.target.value = "";
      if (!file) return;
      const txt = await file.text();
      applyPredictions(parseJsonl(txt), file.name);
    });
    const toggleHelp = () => {
      $("help").hidden = !$("help").hidden;
    };
    $("btn-help").addEventListener("click", toggleHelp);
    $("help-close").addEventListener("click", () => { $("help").hidden = true; });
    $("help").addEventListener("click", (e) => { if (e.target.id === "help") $("help").hidden = true; });

    document.addEventListener("keydown", (e) => {
      const inField = e.target && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
      if (e.key === "Escape") {
        if (!$("help").hidden) { $("help").hidden = true; return; }
        if (inField) { e.target.blur(); return; }
        if (state.filter.q) { state.filter.q = ""; $("q").value = ""; render(); }
        return;
      }
      if (inField) return;
      if (e.key === "?" || (e.key === "/" && e.shiftKey)) { e.preventDefault(); toggleHelp(); return; }
      if (e.key === "/") { e.preventDefault(); $("q").focus(); $("q").select(); return; }
      if ((e.key === "j" || e.key === "J") && state.view === "queue") { move(1); return; }
      if ((e.key === "k" || e.key === "K") && state.view === "queue") { move(-1); return; }
      if (["1", "2", "3", "4", "l", "L", "d", "D"].includes(e.key)) state.view = "queue";
      if (e.key === "1") { state.filter.decision = "ALL"; render(); }
      if (e.key === "2") { state.filter.decision = "DIFFERENT_ENTITY"; render(); }
      if (e.key === "3") { state.filter.decision = "SAME_ENTITY"; render(); }
      if (e.key === "4") { state.filter.decision = "REVIEW"; render(); }
      if (e.key === "l" || e.key === "L") { state.filter.labeled = !state.filter.labeled; render(); }
      if (e.key === "d" || e.key === "D") { state.filter.disagree = !state.filter.disagree; render(); }
    });
  }

  async function main() {
    bind();
    window.addEventListener("hashchange", () => {
      const id = (location.hash || "").replace(/^#/, "");
      if (id && state.bundle && state.bundle.hits[id] && id !== state.selectedId) {
        state.selectedId = id;
        state.selectedCustomer = null;
        state.view = "queue";
        render();
      }
    });
    try {
      await loadBundle();
    } catch (err) {
      $("boot-msg").textContent = err.message || String(err);
      return;
    }
    $("boot").classList.add("done");
    // Default to labeled queue in sample mode so the desk is populated with decisions.
    const fromHash = (location.hash || "").replace(/^#/, "");
    if (fromHash && state.bundle && state.bundle.hits[fromHash]) {
      state.selectedId = fromHash;
    }
    if (state.bundle && state.bundle.meta && state.bundle.meta.sample_predictions) {
      state.filter.labeled = true;
      if (!state.selectedId) {
        const first = Object.keys(state.bundle.labels || {})[0];
        if (first) state.selectedId = first;
      }
    }
    render();
    state.pollTimer = setInterval(pollMeta, 15000);
  }

  main();
})();
