/* Fathom — analyst review desk for Track 2 watchlist hits. */
(() => {
  "use strict";

  const COST = {
    DIFFERENT_ENTITY: { DIFFERENT_ENTITY: 0, SAME_ENTITY: 3, REVIEW: 3 },
    SAME_ENTITY: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 0, REVIEW: 2 },
    REVIEW: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 2, REVIEW: 0 },
  };

  const DECISION_LABEL = {
    DIFFERENT_ENTITY: "Cleared",
    SAME_ENTITY: "True match",
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
  };
  const svg = (k, cls = "ico") => {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", cls); s.setAttribute("aria-hidden", "true");
    s.innerHTML = ICON[k] || ""; return s;
  };
  const nf = new Intl.NumberFormat("en-GB");


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
      n.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
    }
    return n;
  }

  function text(v) {
    if (v == null || v === "" || (Array.isArray(v) && v.length === 0)) return null;
    return v;
  }

  function asList(v) {
    if (v == null || v === "") return [];
    return Array.isArray(v) ? v.filter((x) => x != null && x !== "") : [v];
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
      kpi("k-same", "True match", nf.format(c.SAME_ENTITY), "Sent to compliance", share(c.SAME_ENTITY)),
      kpi("k-review", "Needs review", nf.format(c.REVIEW), "Routed to an analyst", share(c.REVIEW)),
      kpi("k-diff", "Cleared", nf.format(c.DIFFERENT_ENTITY), "False positives closed", share(c.DIFFERENT_ENTITY)),
      el("div", { class: "kpi k-score", title: scoreTitle },
        el("div", { class: "score-main" },
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
        ["SAME_ENTITY", "True match", "same", s.counts.SAME_ENTITY],
        ["REVIEW", "Needs review", "review", s.counts.REVIEW],
        ["DIFFERENT_ENTITY", "Cleared", "diff", s.counts.DIFFERENT_ENTITY],
        ...(s.counts.pending ? [["PENDING", "Pending", "pending", s.counts.pending]] : []),
      ]],
      ["Practice set", [
        ["LABELED", "Labeled only", "labeled", labs.length],
        ["DISAGREE", "Disagreements", "disagree", disagreeN],
      ]],
    ];
    const box = $("filters");
    box.replaceChildren();
    for (const [title, items] of groups) {
      box.appendChild(el("div", { class: "nav-title" }, title));
      for (const [key, label, icon, count] of items) {
        const toggle = key === "LABELED" || key === "DISAGREE";
        const on = key === "LABELED" ? f.labeled : key === "DISAGREE" ? f.disagree : f.decision === key;
        const btn = el("button", {
          type: "button",
          class: "nav-item" + (on ? " on" : "") + " n-" + icon,
          "aria-pressed": on ? "true" : "false",
          onclick: () => {
            if (key === "LABELED") f.labeled = !f.labeled;
            else if (key === "DISAGREE") f.disagree = !f.disagree;
            else f.decision = key;
            render();
          },
        }, svg(icon), el("span", null, label),
          toggle ? el("span", { class: "toggle" + (on ? " on" : "") }, el("i")) : el("span", { class: "count" }, nf.format(count || 0)));
        if (toggle) btn.appendChild(el("span", { class: "count sub" }, String(count || 0)));
        box.appendChild(btn);
      }
    }
  }

  function renderQueue(rows) {
    const f = state.filter;
    const scope = f.decision === "ALL" ? "hits" : (DECISION_LABEL[f.decision] || "pending").toLowerCase();
    $("queue-meta").replaceChildren(
      el("span", null, `${nf.format(rows.length)} ${f.decision === "ALL" ? "hits" : scope}`),
      el("span", { class: "qm-sort" }, "Disagreements first, then by score")
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
        el("div", { class: "q-main" },
          el("div", { class: "q-name" }, row.hit.name || "Unnamed"),
          el("div", { class: "q-cust" }, "Customer ", el("b", null, row.alert.customer_name || "unknown")),
          el("div", { class: "q-sub" },
            el("span", { class: "mono" }, row.hit.hit_id),
            el("span", null, row.cat),
            row.lab ? el("span", { class: "flag" + (row.disagree ? " bad" : "") }, row.disagree ? "Label differs" : "Labeled") : null
          )
        ),
        el("div", { class: "q-right" },
          el("span", { class: "dec " + cls }, row.decision === "PENDING" ? "Pending" : DECISION_LABEL[row.decision] || row.decision),
          row.hit.match_score != null ? el("span", { class: "q-score mono", title: "Screening match score" }, String(row.hit.match_score)) : null
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
    const head = el("div", { class: "case-head" },
      el("div", { class: "case-meta" },
        meta("Hit", hit.hit_id, true),
        meta("Alert", hit.alert_id, true),
        meta("Screened", fmtLong(alert.screened_at)),
        meta("Match score", hit.match_score != null ? String(hit.match_score) : null, true)
      ),
      el("h2", { class: "case-title" }, hit.name || "Unnamed list entry"),
      el("div", { class: "case-sub" },
        el("span", null, "Screened customer ", el("b", null, alert.customer_name || "unknown")),
        ...asList(hit.categories).map((c) => el("span", { class: "tag" }, c)),
        hit.entity_type ? el("span", { class: "tag" }, hit.entity_type) : null,
        hit.gender ? el("span", { class: "tag" }, hit.gender) : null
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
        el("div", { class: "path" }, lab.path)
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

  function render() {
    const bundle = state.bundle;
    if (!bundle) return;
    renderStats(bundle);
    renderFilters();
    const rows = buildQueue(bundle);
    if (state.selectedId && !rows.some((r) => r.hit.hit_id === state.selectedId)) {
      // keep selection even if filtered out? Better to show it anyway in the stage, queue just won't highlight.
    }
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

  async function loadBundle() {
    $("boot-msg").textContent = "Loading case files…";
    const res = await fetch("data/bundle.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load data/bundle.json (${res.status}). Run python3 prepare.py and serve from /workspace/track2_ui.`);
    state.bundle = await res.json();
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
      const inField = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA");
      if (e.key === "Escape") {
        if (!$("help").hidden) { $("help").hidden = true; return; }
        if (inField) { e.target.blur(); return; }
        if (state.filter.q) { state.filter.q = ""; $("q").value = ""; render(); }
        return;
      }
      if (inField) return;
      if (e.key === "?" || (e.key === "/" && e.shiftKey)) { e.preventDefault(); toggleHelp(); return; }
      if (e.key === "/") { e.preventDefault(); $("q").focus(); $("q").select(); return; }
      if (e.key === "j" || e.key === "J") { move(1); return; }
      if (e.key === "k" || e.key === "K") { move(-1); return; }
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
