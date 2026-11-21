/* Fathom — analyst review desk for Track 2 watchlist hits. */
(() => {
  "use strict";

  const COST = {
    DIFFERENT_ENTITY: { DIFFERENT_ENTITY: 0, SAME_ENTITY: 3, REVIEW: 3 },
    SAME_ENTITY: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 0, REVIEW: 2 },
    REVIEW: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 2, REVIEW: 0 },
  };

  // The system's vocabulary on every hit; the gloss is the analyst's word for it.
  const DECISION_LABEL = {
    DIFFERENT_ENTITY: "Different",
    SAME_ENTITY: "Same",
    REVIEW: "Review",
  };
  const DECISION_GLOSS = {
    DIFFERENT_ENTITY: "Different entity · cleared",
    SAME_ENTITY: "Same entity · true match",
    REVIEW: "Needs a human",
  };
  const DECISION_CLASS = {
    DIFFERENT_ENTITY: "diff",
    SAME_ENTITY: "same",
    REVIEW: "review",
  };

  // Fact states the system's reason code asserts. They win over the desk's own
  // heuristics so the strip never contradicts the decision it explains.
  const CODE_FACTS = {
    NAME_DOB_LOCATION_MATCH: { name: "agree", dob: "agree", countries: "agree" },
    NAME_DOB_MATCH: { name: "agree", dob: "agree" },
    NAME_LOCATION_MATCH: { name: "agree", countries: "agree" },
    DOB_MISMATCH: { dob: "conflict" },
    LOCATION_MISMATCH: { countries: "conflict" },
    NAME_MISMATCH_VERIFIED: { name: "conflict" },
  };

  const ID_RE = /\b(?:CUS|KYC|NOTE|SR|ACC|APP)-[0-9A-Z]{4,}\b/g;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";

  const state = {
    bundle: null,
    version: 0,
    importedPreds: null,
    filter: { decision: "ALL", q: "", labeled: false, disagree: false, category: "ALL" },
    selectedId: null,
    selectedCustomer: null,
    moreFields: false,
    animateNext: false,
    queueKey: null,
    caseKey: null,
    prevCounts: null,
    pollTimer: null,
  };

  const $ = (id) => document.getElementById(id);

  // Lucide-style icons (24px grid, round caps), drawn inline so the desk stays dependency-free.
  const ICONS = {
    check: ["M20 6 9 17l-5-5"],
    x: ["M18 6 6 18", "m6 6 12 12"],
    equal: ["M5 9h14", "M5 15h14"],
    notEqual: ["M5 9h14", "M5 15h14", "M19 5 5 19"],
    help: ["M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3", "M12 17h.01"],
    chevron: ["m9 18 6-6-6-6"],
    shield: ["M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z", "m9 12 2 2 4-4"],
    alert: ["m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3", "M12 9v4", "M12 17h.01"],
    searchX: ["m13.5 8.5-5 5", "m8.5 8.5 5 5", "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "m21 21-4.3-4.3"],
  };
  const SVG_NS = "http://www.w3.org/2000/svg";
  function icon(name, cls) {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "icon" + (cls ? " " + cls : ""));
    svg.setAttribute("aria-hidden", "true");
    for (const d of ICONS[name] || []) {
      const p = document.createElementNS(SVG_NS, "path");
      p.setAttribute("d", d);
      svg.appendChild(p);
    }
    return svg;
  }

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
      Object.assign(confusion, metaScore.confusion || {});
    }
    let correct = 0;
    for (const [k, n] of Object.entries(confusion)) {
      const [g, d] = k.split(">");
      if (g === d) correct += n;
    }
    return {
      correct,
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
    const rows = [];
    // Counts per decision honour search / labeled / disagree but not the decision filter,
    // so each chip says how many hits it would show.
    const counts = { ALL: 0, SAME_ENTITY: 0, DIFFERENT_ENTITY: 0, REVIEW: 0, PENDING: 0, LABELED: 0, DISAGREE: 0 };
    for (const hit of Object.values(bundle.hits)) {
      const pred = predictions(bundle)[hit.hit_id] || null;
      const lab = bundle.labels[hit.hit_id] || null;
      const alert = bundle.alerts[hit.alert_id] || {};
      const decision = pred && pred.decision ? pred.decision : "PENDING";
      if (lab) counts.LABELED++;
      if (lab && pred && lab.decision !== pred.decision) counts.DISAGREE++;
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
      counts.ALL++;
      counts[decision] = (counts[decision] || 0) + 1;
      if (filter.decision !== "ALL" && decision !== filter.decision) continue;
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
    rows.counts = counts;
    return rows;
  }

  function fmtPct(x) {
    if (x == null || Number.isNaN(x)) return "n/a";
    return `${(x * 100).toFixed(1)}%`;
  }

  // One beat on a number that just changed: it tells you the filter worked.
  function pulse(node) {
    if (!node || !node.animate) return;
    const frames = reduceMotion.matches
      ? [{ opacity: 0.35 }, { opacity: 1 }]
      : [{ transform: "scale(1.14)" }, { transform: "scale(1)" }];
    node.animate(frames, { duration: 240, easing: EASE_OUT });
    node.classList.remove("ticked");
    void node.offsetWidth;
    node.classList.add("ticked");
  }

  function renderStats(bundle) {
    const s = computeStats(bundle);
    const c = s.counts;
    const scoreTitle = s.sample
      ? "Practice labels answered correctly (sample predictions copy those labels)"
      : `Practice labels answered correctly. Decision score ${fmtPct(s.decisionScore)} of review-baseline cost saved.`;
    const stat = (cls, k, v, sub, title) =>
      el("div", { class: "stat " + cls, title },
        el("div", { class: "k" }, k),
        el("div", { class: "v" }, el("span", { class: "num" }, v), cls === "safe" ? icon("shield", "stat-icon") : null, sub ? el("em", null, sub) : null));
    $("stats").replaceChildren(
      stat("total", "Hits", String(c.total), c.pending ? `${c.pending} pending` : null),
      stat("cleared", "Cleared", String(c.DIFFERENT_ENTITY), null, "Decided DIFFERENT_ENTITY"),
      stat("match", "Matches", String(c.SAME_ENTITY), null, "Decided SAME_ENTITY"),
      stat("review", "Review", String(c.REVIEW), null, "Sent to a human"),
      stat("score", "Practice", s.labeled ? `${s.correct}/${s.labeled}` : "n/a", s.labeled ? "correct" : "no labels", scoreTitle),
      stat(s.labeled ? (s.unsafe ? "danger" : "safe") : "", "Unsafe clears", s.labeled ? String(s.unsafe) : "n/a", null,
        "Cleared (DIFFERENT_ENTITY) when the practice label is SAME_ENTITY or REVIEW. Costs 60 each."),
    );
    const live = !s.sample && Object.keys(predictions(bundle)).length;
    const pill = $("mode-pill");
    pill.textContent = live ? "Live output" : "Sample";
    pill.className = "pill " + (live ? "pill-live" : "pill-sample");
    const banner = $("sample-banner");
    const showBanner = !live;
    banner.hidden = !showBanner;
    document.body.classList.toggle("has-banner", showBanner);
  }

  const CHIPS = [
    ["ALL", "All", "", "1"],
    ["SAME_ENTITY", "Same", "match", "2"],
    ["DIFFERENT_ENTITY", "Different", "cleared", "3"],
    ["REVIEW", "Review", "review", "4"],
    ["PENDING", "Pending", "pending", ""],
    ["LABELED", "Labeled", "", "L"],
    ["DISAGREE", "Disagrees", "", "D"],
  ];

  function renderFilters(counts) {
    const f = state.filter;
    const prev = state.prevCounts;
    const box = $("filters");
    box.replaceChildren();
    const changed = [];
    for (const [key, label, cls, shortcut] of CHIPS) {
      if (key === "PENDING" && !counts.PENDING && f.decision !== "PENDING") continue;
      let on = false;
      if (key === "LABELED") on = f.labeled;
      else if (key === "DISAGREE") on = f.disagree;
      else on = f.decision === key;
      const n = counts[key];
      const num = n != null ? el("span", { class: "n" }, String(n)) : null;
      if (num && prev && prev[key] !== n) changed.push(num);
      box.appendChild(
        el("button", {
          type: "button",
          class: "chip" + (on ? " on" : "") + (cls ? " " + cls : ""),
          "aria-pressed": on ? "true" : "false",
          title: shortcut ? `Shortcut: ${shortcut}` : null,
          onclick: () => {
            if (key === "LABELED") f.labeled = !f.labeled;
            else if (key === "DISAGREE") f.disagree = !f.disagree;
            else f.decision = key;
            render();
          },
        }, label, num)
      );
    }
    state.prevCounts = { ...counts };
    if (prev) changed.forEach(pulse);
  }

  function queueItem(row) {
    const cls = DECISION_CLASS[row.decision] || "pending";
    const id = row.hit.hit_id;
    const code = row.pred && row.pred.reason_code;
    return el(
      "div",
      {
        class: "queue-item" + (id === state.selectedId ? " on" : ""),
        id: "q-" + id,
        role: "option",
        dataset: { id },
        "aria-selected": id === state.selectedId ? "true" : "false",
        onclick: () => selectHit(id, null, { animate: true }),
      },
      el("div", { class: "q-bar " + cls }),
      el("div", null,
        el("div", { class: "q-name" }, row.hit.name || "Unnamed"),
        el("div", { class: "q-sub" },
          el("span", null, id),
          el("span", { class: "code" }, code || row.cat)
        )
      ),
      el("div", { class: "q-right" },
        el("span", { class: "mini " + cls }, row.decision === "PENDING" ? "Pending" : DECISION_LABEL[row.decision] || row.decision),
        row.lab ? el("span", { class: "flag" + (row.disagree ? " bad" : "") }, row.disagree ? icon("alert") : null, row.disagree ? "Label differs" : "Labeled") : el("span", { class: "flag cat" }, row.cat)
      )
    );
  }

  function renderQueue(rows) {
    const meta = $("queue-meta");
    meta.replaceChildren(el("span", { class: "num" }, String(rows.length)), ` ${rows.length === 1 ? "hit" : "hits"} in queue`);
    if (state.queueLen != null && state.queueLen !== rows.length) pulse(meta.firstChild);
    state.queueLen = rows.length;
    const box = $("queue");
    box.replaceChildren();
    if (!rows.length) {
      const f = state.filter;
      box.appendChild(el("div", { class: "queue-empty" },
        icon("searchX", "qe-icon"),
        el("div", { class: "qe-title" }, "Nothing here"),
        el("div", { class: "qe-sub" }, f.q ? `No hits match “${f.q}” with these filters.` : "No hits match these filters."),
        el("button", {
          type: "button",
          class: "btn ghost",
          onclick: () => {
            Object.assign(state.filter, { decision: "ALL", q: "", labeled: false, disagree: false });
            $("q").value = "";
            render();
          },
        }, "Clear filters")
      ));
      return;
    }
    const frag = document.createDocumentFragment();
    for (const row of rows) frag.appendChild(queueItem(row));
    box.appendChild(frag);
    syncQueueSelection();
  }

  function syncQueueSelection() {
    const box = $("queue");
    const prev = box.querySelector(".queue-item.on");
    const next = state.selectedId ? document.getElementById("q-" + state.selectedId) : null;
    if (prev && prev !== next) {
      prev.classList.remove("on");
      prev.setAttribute("aria-selected", "false");
    }
    if (next) {
      next.classList.add("on");
      next.setAttribute("aria-selected", "true");
      box.setAttribute("aria-activedescendant", next.id);
      next.scrollIntoView({ block: "nearest" });
    } else {
      box.removeAttribute("aria-activedescendant");
    }
  }

  function selectHit(id, customerId, opts) {
    state.selectedId = id;
    state.selectedCustomer = customerId || null;
    // Motion is for pointer selection only: keyboard navigation (j/k) is a
    // hundreds-a-day action and must swap instantly.
    state.animateNext = !!(opts && opts.animate);
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

  function displayList(items, empty = "Not on file") {
    const arr = asList(items);
    if (!arr.length) return el("span", { class: "missing" }, empty);
    if (arr.length === 1) return linkText(String(arr[0]));
    return el("ul", { class: "val-list" }, ...arr.map((x) => el("li", null, linkText(String(x)))));
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

    const firstOf = (set) => (set.size ? [...set].join(", ") : null);
    const custName = (kyc && kyc.verified_name) || (cust && cust.full_name) || (alert && alert.customer_name) || null;
    const custDobBrief = custDobsForStatus.length ? (fmtDate(parseDate(custDobsForStatus[0])) || custDobsForStatus[0]) : null;
    const hitDobBrief = hitDobs.length
      ? [...new Set(hitDobs.map((d) => fmtDate(parseDate(d)) || d))].join(", ")
      : (noteDobs.length ? `≈${noteDobs[0].y} (from notes)` : null);

    function showDates(arr) {
      const parsed = arr.map(parseDate).filter(Boolean);
      if (!parsed.length) return el("span", { class: "missing" }, "Not on file");
      const uniq = [...new Set(parsed.map(fmtDate))];
      return displayList(uniq);
    }

    const rows = [
      {
        key: "type",
        label: "Entity type",
        left: cType || el("span", { class: "missing" }, "Not on file"),
        right: hType || el("span", { class: "missing" }, "Not on file"),
        status: typeSt,
      },
      {
        key: "name",
        brief: [custName, hit.name || null],
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
        key: "dob",
        brief: [custDobBrief, hitDobBrief],
        label: "Date of birth",
        left: custDobs.length ? displayList(custDobs) : el("span", { class: "missing" }, "Not on file"),
        right: hitDobs.length
          ? showDates(hitDobs)
          : (noteDobs.length
            ? displayList(noteDobs.map((p) => p.raw))
            : el("span", { class: "missing" }, "Not on file")),
        status: dobSt,
      },
      {
        key: "nationality",
        label: "Nationality",
        left: cNat.size ? displayList([...cNat]) : el("span", { class: "missing" }, "Not on file"),
        right: hNat.size ? displayList([...hNat]) : el("span", { class: "missing" }, "Not on file"),
        status: natSt,
      },
      {
        key: "countries",
        brief: [firstOf(cCountries), firstOf(hCountries)],
        label: "Countries",
        left: cCountries.size ? displayList([...cCountries]) : el("span", { class: "missing" }, "Not on file"),
        right: hCountries.size ? displayList([...hCountries]) : el("span", { class: "missing" }, "Not on file"),
        status: locSt,
      },
      {
        key: "address",
        weak: true,
        label: "City / address",
        left: displayList([cust && cust.city, cust && cust.address, alert && alert.city].filter(Boolean), "Not on file"),
        right: displayList(hit.addresses, "Not on file"),
        status: "unknown",
      },
      {
        key: "ids",
        weak: true,
        label: "Identifiers",
        left: displayList([cust && cust.registration_number, kyc && kyc.document_type && kyc.document_number ? `${kyc.document_type} ${kyc.document_number}` : null].filter(Boolean), "Not on file"),
        right: displayList(hit.identifiers, "Not on file"),
        status: "unknown",
      },
      {
        key: "occupation",
        weak: true,
        label: "Occupation",
        left: displayList([cust && cust.occupation, cust && cust.employer].filter(Boolean), "Not on file"),
        right: displayList([hit.position_or_allegation].filter(Boolean), "Not on file"),
        status: "unknown",
      },
      {
        key: "life",
        weak: true,
        label: "Life status",
        left: el("span", { class: "missing" }, "Not on file"),
        right: displayList([hit.life_status, hit.deceased_date && `Deceased ${hit.deceased_date}`].filter(Boolean), "Not on file"),
        status: hit.deceased_date ? "conflict" : "unknown",
      },
      {
        key: "gender",
        weak: true,
        label: "Gender",
        left: el("span", { class: "missing" }, "Not on file"),
        right: hit.gender || el("span", { class: "missing" }, "Not on file"),
        status: "unknown",
      },
    ];
    return rows;
  }

  // Turns every record ID in a string into a button that jumps to its evidence card.
  function linkText(str) {
    const raw = String(str);
    ID_RE.lastIndex = 0;
    if (!ID_RE.test(raw)) return document.createTextNode(raw);
    const frag = document.createDocumentFragment();
    let last = 0;
    ID_RE.lastIndex = 0;
    for (const m of raw.matchAll(ID_RE)) {
      if (m.index > last) frag.appendChild(document.createTextNode(raw.slice(last, m.index)));
      frag.appendChild(idButton(m[0]));
      last = m.index + m[0].length;
    }
    if (last < raw.length) frag.appendChild(document.createTextNode(raw.slice(last)));
    return frag;
  }

  function idButton(id) {
    return el("button", {
      type: "button",
      class: "idchip",
      title: `Show source record ${id}`,
      onclick: (e) => { e.stopPropagation(); focusEvidence(id); },
    }, id);
  }

  function focusEvidence(id) {
    const card = document.getElementById("ev-" + id);
    if (!card) return;
    card.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "center" });
    card.focus({ preventScroll: true });
    card.classList.remove("flash");
    void card.offsetWidth; // restart the one-shot ring
    card.classList.add("flash");
  }

  function highlightReason(text) {
    const raw = String(text || "").trim() || "No reason text.";
    const wrap = el("div", { class: "reason-text" });
    wrap.appendChild(linkText(raw));
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
    const card = el("div", { class: "ev-card" + (cited ? " cited" : ""), id: "ev-" + id, tabindex: "-1" });
    if (!found) {
      card.append(
        el("div", { class: "ev-top" }, el("div", { class: "ev-id" }, id), el("div", { class: "ev-kind" }, "Not in bundle"))
      );
      return card;
    }
    const { kind, rec } = found;
    card.append(el("div", { class: "ev-top" }, el("div", { class: "ev-id" }, id), el("div", { class: "ev-kind" }, kind)));
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

  const STATE_WORD = { agree: "Agrees", conflict: "Contradicts", unknown: "Unknown" };
  const STATE_ICON = { agree: "equal", conflict: "notEqual", unknown: "help" };
  const ROW_ORDER = ["name", "dob", "nationality", "countries", "type", "life", "address", "ids", "occupation", "gender"];

  function stateMark(status) {
    return el("span", { class: "state " + status },
      el("span", { class: "glyph", "aria-hidden": "true" }, icon(STATE_ICON[status] || "help")),
      el("span", { class: "w" }, STATE_WORD[status] || status));
  }

  function factTile(label, row, delay) {
    const st = row ? row.status : "unknown";
    const [c, l] = (row && row.brief) || [null, null];
    const side = (k, v) => el("div", { class: "ft-side" },
      el("span", { class: "ft-k" }, k),
      v ? el("span", { class: "ft-v", title: v }, v) : el("span", { class: "ft-v missing" }, "not on file"));
    return el("div", { class: "fact-tile stagger " + st, style: `--d:${delay}ms` },
      el("div", { class: "ft-top" }, el("span", { class: "ft-label" }, label), stateMark(st)),
      side("Customer", c),
      side("List", l));
  }

  function emptyStage(title, sub) {
    return el("div", { class: "empty", id: "empty" },
      el("div", { class: "empty-title" }, title),
      el("div", { class: "empty-sub" }, ...sub));
  }

  function renderCase(bundle) {
    const stage = $("stage");
    const hit = bundle.hits[state.selectedId];
    const animate = state.animateNext;
    state.animateNext = false;
    if (!hit) {
      stage.replaceChildren(emptyStage("Select a hit", ["Pick one from the queue, or press ", el("kbd", null, "J"), " / ", el("kbd", null, "K"), "."]));
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

    // Comparison rows, with the facts the reason code asserts taking precedence.
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
    const asserted = CODE_FACTS[reasonCode] || {};
    for (const r of rows) {
      const want = asserted[r.key];
      if (!want) continue;
      // A contradiction needs a value on both sides; otherwise the fact stays unknown.
      if (want === "conflict" && r.brief && !(r.brief[0] && r.brief[1])) continue;
      r.status = want;
    }
    rows.sort((a, b) => ROW_ORDER.indexOf(a.key) - ROW_ORDER.indexOf(b.key));
    const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));

    const head = el("div", { class: "case-head" },
      el("div", { class: "ids" },
        el("span", null, el("b", null, "HIT"), hit.hit_id),
        el("span", null, el("b", null, "ALERT"), hit.alert_id),
        alert.screened_at ? el("span", null, el("b", null, "SCREENED"), alert.screened_at) : null,
        hit.match_score != null ? el("span", null, el("b", null, "SCORE"), String(hit.match_score)) : null
      ),
      el("h1", { class: "case-title" }, hit.name || "Unnamed list entry"),
      el("div", { class: "case-sub" },
        el("span", null, "Screened customer ", el("b", null, alert.customer_name || "Unknown")),
        el("span", { class: "badges" },
          ...asList(hit.categories).map((c) => {
            const k = fold(c);
            const cls = k.includes("sanction") ? "sanctions" : k === "pep" ? "pep" : k.includes("enforce") ? "enforcement" : k.includes("adverse") ? "adverse" : "";
            return el("span", { class: "badge " + cls }, c);
          }),
          hit.entity_type ? el("span", { class: "badge" }, hit.entity_type) : null
        )
      )
    );

    const verdict = el("section", { class: "verdict", "aria-label": "Decision and grounds" },
      el("div", { class: "stamp " + dcls },
        el("div", { class: "s-k" }, "Decision"),
        el("div", { class: "s-v" }, decision === "PENDING" ? "Pending" : DECISION_LABEL[decision] || decision),
        el("div", { class: "s-g" }, DECISION_GLOSS[decision] || "No prediction yet"),
        el("div", { class: "s-c" }, reasonCode || "No reason code")
      ),
      el("div", { class: "facts" },
        factTile("Name", byKey.name, 40),
        factTile("DOB", byKey.dob, 75),
        factTile("Countries", byKey.countries, 105)
      )
    );

    const parts = [head, verdict];

    const reasonWrap = el("div", { class: "reason-block stagger", style: "--d:130ms" },
      el("h3", null, "Why", reasonCode ? el("span", { class: "code" }, reasonCode) : null),
      highlightReason(pred && pred.reason),
      codeMeta ? el("div", { class: "reason-rule" }, codeMeta.when) : null,
      pred && pred.customer_record_id
        ? el("div", { class: "reason-meta" }, "Resolved customer record ", linkText(String(pred.customer_record_id)))
        : null
    );
    parts.push(reasonWrap);

    if (pred && isSample(bundle, pred) && pred._sample_source === "practice_labels") {
      parts.push(el("div", { class: "label-row" },
        el("div", null, el("div", { class: "lab-k" }, "Source"), " Sample copied from practice labels")
      ));
    }

    if (lab) {
      const disagree = pred && pred.decision && pred.decision !== lab.decision;
      parts.push(el("div", { class: "label-row " + (pred && pred.decision ? (disagree ? "disagree" : "agree") : "") },
        pred && pred.decision ? el("span", { class: "lab-icon" }, icon(disagree ? "x" : "check")) : null,
        el("div", null, el("div", { class: "lab-k" }, "Practice label"), `${DECISION_LABEL[lab.decision] || lab.decision}  ·  ${(lab.reason_codes || []).join(", ")}`),
        pred && pred.decision
          ? el("div", null, el("div", { class: "lab-k" }, disagree ? "System disagrees" : "System agrees"), `${DECISION_LABEL[pred.decision]}  ·  ${pred.reason_code || ""}`)
          : el("div", null, el("div", { class: "lab-k" }, "System"), "No prediction yet")
      ));
    }

    if (uniqueCust.length > 1) {
      parts.push(el("div", { class: "person-switch" },
        el("span", { class: "ps-k" }, `${uniqueCust.length} customer records fit`),
        ...uniqueCust.map((id) => {
          const c = bundle.customers[id];
          return el("button", {
            type: "button",
            class: id === state.selectedCustomer ? "on" : "",
            "aria-pressed": id === state.selectedCustomer ? "true" : "false",
            onclick: () => { state.selectedCustomer = id; render(); },
          }, `${id} · ${c && c.full_name ? c.full_name : "record"}`);
        })
      ));
    }

    // Side-by-side comparison
    const table = el("div", { class: "compare" });
    const screenedBits = [
      alert.customer_name && `Name ${alert.customer_name}`,
      alert.dob && `DOB ${alert.dob}`,
      alert.country && `Country ${alert.country}`,
      alert.city && `City ${alert.city}`,
      alert.account_ref && `Account ${alert.account_ref}`,
      alert.login_handle && `Login ${alert.login_handle}`,
      alert.email && `Email ${alert.email}`,
    ].filter(Boolean);
    table.appendChild(el("div", { class: "screened" },
      el("b", null, "As screened  "),
      screenedBits.join("  ·  ") || "No screened identity fields."
    ));
    table.appendChild(el("div", { class: "field-grid head" },
      el("div", { class: "fh" }, "Field"),
      el("div", { class: "fh" }, "Customer  ·  ", cust ? linkText(cust.record_id) : "unresolved"),
      el("div", { class: "fh" }, "List entry  ·  " + hit.hit_id),
      el("div", { class: "fh status" }, "Compare")
    ));
    const line = (r, i) => el("div", { class: "field-grid row-" + r.status + (i != null ? " stagger" : ""), style: i != null ? `--d:${150 + Math.min(i, 5) * 22}ms` : null },
      el("div", { class: "fcell lab" }, r.label),
      el("div", { class: "fcell val" }, r.left),
      el("div", { class: "fcell val" }, r.right),
      el("div", { class: "fcell status" }, stateMark(r.status))
    );
    const strong = rows.filter((r) => !r.weak || r.status !== "unknown");
    const weak = rows.filter((r) => r.weak && r.status === "unknown");
    strong.forEach((r, i) => table.appendChild(line(r, i)));
    if (weak.length) {
      const more = el("details", { class: "more", open: state.moreFields || null },
        el("summary", null, icon("chevron", "more-chev"), `${weak.length} more fields`, el("span", { class: "more-hint" }, weak.map((r) => r.label.toLowerCase()).join(", "))),
        ...weak.map((r) => line(r)));
      more.addEventListener("toggle", () => { state.moreFields = more.open; });
      table.appendChild(more);
    }

    parts.push(el("div", { class: "section-k" },
      el("span", null, "Side by side"),
      el("span", { class: "legend" },
        stateMark("agree"), stateMark("conflict"), stateMark("unknown"),
        el("span", { class: "legend-note" }, "Unknown stays unknown: a missing fact is never scored as a mismatch.")
      )
    ), table);

    if (kyc) {
      parts.push(el("div", { class: "foot-note" },
        "Verified identity from approved check ", linkText(kyc.check_id), ` (${kyc.checked_at || "undated"}): ${kyc.verified_name || "no name"}, ${kyc.verified_dob || "no DOB"}, document country ${kyc.document_country || "not recorded"}.`
      ));
    } else if (!cust) {
      parts.push(el("div", { class: "foot-note" },
        "No customer record is resolved for this alert in the review bundle. The customer column uses screened details only."
      ));
    }

    // Evidence: cited first, then IDs the reason mentions, then the rest of the case file.
    const cited = [...asList(pred && pred.evidence)];
    const evIds = [];
    const addEv = (id) => {
      if (!id || evIds.includes(id)) return;
      evIds.push(id);
    };
    cited.forEach(addEv);
    for (const m of String((pred && pred.reason) || "").matchAll(ID_RE)) if (findRecord(m[0], bundle)) addEv(m[0]);
    asList(lab && lab.evidence).forEach(addEv);
    asList(cse.kyc_ids).forEach(addEv);
    asList(cse.note_ids).forEach(addEv);
    if (cust) addEv(cust.record_id);
    asList(cse.search_ids).slice(0, 6).forEach(addEv);

    const citedSet = new Set(cited.length ? cited : asList(lab && lab.evidence));
    const evPanel = el("div", { class: "panel", id: "evidence-panel" },
      el("h3", null, "Evidence records", el("span", { class: "code" }, `${citedSet.size} cited · ${evIds.length} shown`)));
    if (!evIds.length) {
      evPanel.appendChild(el("div", { class: "panel-empty" }, "No evidence records are attached to this hit."));
    } else {
      const gridE = el("div", { class: "evidence-grid" });
      for (const id of evIds) gridE.appendChild(evidenceCard(id, bundle, citedSet.has(id)));
      evPanel.appendChild(el("div", { class: "panel-note" },
        "Cards with a heavy border and a CITED tab are the records the decision cites. Click any ID above to jump to its card."
      ));
      evPanel.appendChild(gridE);
    }
    parts.push(evPanel);

    if (lab && lab.reference_reason) {
      parts.push(el("div", { class: "panel" },
        el("h3", null, "Practice reference reason"),
        highlightReason(lab.reference_reason)
      ));
    }
    if (lab && lab.path) {
      parts.push(el("div", { class: "panel" },
        el("h3", null, "Path through the files"),
        el("div", { class: "path" }, linkText(lab.path))
      ));
    }

    if (hit.profile_notes || hit.details || (hit.relationships && hit.relationships.length) || (hit.sources && hit.sources.length) || (hit.source_urls && hit.source_urls.length)) {
      const prof = el("div", { class: "panel" }, el("h3", null, "List-entry profile"));
      if (hit.position_or_allegation) prof.appendChild(el("div", { class: "prof-lead" }, hit.position_or_allegation));
      if (hit.details) prof.appendChild(el("div", { class: "prof-details" }, hit.details));
      if (hit.profile_notes) prof.appendChild(el("div", { class: "notes-block" }, hit.profile_notes));
      if (hit.relationships && hit.relationships.length) {
        prof.appendChild(el("h3", { class: "sub" }, "Relationships"));
        prof.appendChild(el("ul", { class: "rel-list" }, ...hit.relationships.map((r) => el("li", null, String(r)))));
      }
      const urls = asList(hit.source_urls);
      const srcs = asList(hit.sources);
      if (urls.length || srcs.length) {
        prof.appendChild(el("h3", { class: "sub" }, "Sources"));
        const box = el("div", { class: "sources" });
        for (const s of srcs) box.appendChild(el("div", null, String(s)));
        for (const u of urls) box.appendChild(el("div", null, el("a", { href: u, target: "_blank", rel: "noreferrer" }, u)));
        prof.appendChild(box);
      }
      parts.push(prof);
    }

    const caseEl = el("article", { class: "case" + (animate ? " enter" : "") }, ...parts);
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
    const rows = buildQueue(bundle);
    renderFilters(rows.counts);
    // A filter that hides the open hit moves you to the top of the new queue.
    if (rows.length && !rows.some((r) => r.hit.hit_id === state.selectedId)) {
      state.selectedId = rows[0].hit.hit_id;
      state.selectedCustomer = null;
      history.replaceState(null, "", "#" + state.selectedId);
    }
    // Rebuild the queue only when its contents change; selection alone just moves the highlight.
    const queueKey = state.version + "|" + JSON.stringify(state.filter);
    if (queueKey !== state.queueKey) {
      state.queueKey = queueKey;
      renderQueue(rows);
    } else {
      syncQueueSelection();
    }
    // Leave the detail pane (and its scroll position) alone unless the case itself changed.
    const caseKey = state.version + "|" + state.selectedId + "|" + state.selectedCustomer + "|" + state.moreFields;
    if (caseKey !== state.caseKey) {
      renderCase(bundle);
      state.caseKey = state.version + "|" + state.selectedId + "|" + state.selectedCustomer + "|" + state.moreFields;
    }
    state.animateNext = false;
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
    state.version++;
    render();
  }

  async function loadBundle() {
    $("boot-msg").textContent = "Loading case files…";
    const res = await fetch("data/bundle.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load data/bundle.json (${res.status}). Run python3 prepare.py and serve from /workspace/track2_ui.`);
    state.bundle = await res.json();
    state.version++;
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
      const help = $("help");
      help.hidden = !help.hidden;
      if (!help.hidden) $("help-close").focus();
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
      if (inField) {
        // Enter or arrow-down hands control back to the queue so j/k work straight away.
        if (e.target.id === "q" && (e.key === "Enter" || e.key === "ArrowDown")) { e.preventDefault(); e.target.blur(); }
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "?" || (e.key === "/" && e.shiftKey)) { e.preventDefault(); toggleHelp(); return; }
      if (!$("help").hidden) return;
      if (e.key === "/") { e.preventDefault(); $("q").focus(); $("q").select(); return; }
      // Arrows move the queue only while it has focus, so they still scroll the case pane otherwise.
      const inQueue = document.activeElement === $("queue");
      if (e.key === "j" || e.key === "J" || (inQueue && e.key === "ArrowDown")) { e.preventDefault(); move(1); return; }
      if (e.key === "k" || e.key === "K" || (inQueue && e.key === "ArrowUp")) { e.preventDefault(); move(-1); return; }
      const byKey = { 1: "ALL", 2: "SAME_ENTITY", 3: "DIFFERENT_ENTITY", 4: "REVIEW" };
      if (byKey[e.key]) { state.filter.decision = byKey[e.key]; render(); return; }
      if (e.key === "l" || e.key === "L") { state.filter.labeled = !state.filter.labeled; render(); }
      if (e.key === "d" || e.key === "D") { state.filter.disagree = !state.filter.disagree; render(); }
    });
  }

  async function main() {
    bind();
    // Read the deep link before the first render can rewrite the hash.
    const fromHash = (location.hash || "").replace(/^#/, "");
    if (fromHash) state.selectedId = fromHash;
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
    // The first case lands with the entrance motion: a once-per-session moment.
    state.caseKey = null;
    state.animateNext = true;
    render();
    state.pollTimer = setInterval(pollMeta, 15000);
  }

  main();
})();
