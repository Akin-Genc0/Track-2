/* Fathom data loader for static hosting (GitHub Pages).
 *
 * When there is no server-built data/bundle.json, the analyst drops the organisers'
 * workbook ("Screening Dev Set - browse.xlsx") or a dev/ folder of JSON Lines files.
 * Everything runs in the browser: the file is never uploaded anywhere.
 *
 *   readWorkbook   mirrors tools/workbook.py      (xlsx -> tables, no libraries)
 *   toDevTables    mirrors tools/xlsx_to_dev.py   (list fields, numbers, name variants)
 *   buildBundle    mirrors ui/prepare.py build()  (same bundle the local server writes)
 *
 * The built bundle is cached in IndexedDB so the drop happens once per browser.
 */
(() => {
  "use strict";

  // ---------------------------------------------------------------- zip / xlsx
  async function inflate(bytes, method) {
    if (method === 0) return bytes;
    if (method !== 8) throw new Error("Unsupported compression in workbook (method " + method + ")");
    if (typeof DecompressionStream === "undefined") throw new Error("This browser can't unzip files. Use a current Chrome, Edge, Firefox or Safari.");
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  function zipEntries(buf) {
    const dv = new DataView(buf);
    let eocd = -1;
    for (let i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 70000); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("That file isn't a valid .xlsx workbook");
    const count = dv.getUint16(eocd + 10, true);
    let p = dv.getUint32(eocd + 16, true);
    const dec = new TextDecoder();
    const out = {};
    for (let i = 0; i < count; i++) {
      if (dv.getUint32(p, true) !== 0x02014b50) break;
      const method = dv.getUint16(p + 10, true);
      const csize = dv.getUint32(p + 20, true);
      const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true);
      const local = dv.getUint32(p + 42, true);
      const name = dec.decode(new Uint8Array(buf, p + 46, nlen));
      out[name] = { method, csize, local };
      p += 46 + nlen + xlen + clen;
    }
    return out;
  }

  async function zipText(buf, entries, name) {
    const e = entries[name];
    if (!e) return null;
    const dv = new DataView(buf);
    const nlen = dv.getUint16(e.local + 26, true), xlen = dv.getUint16(e.local + 28, true);
    const start = e.local + 30 + nlen + xlen;
    const raw = await inflate(new Uint8Array(buf, start, e.csize), e.method);
    return new TextDecoder().decode(raw);
  }

  const ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };
  function unxml(s) {
    if (s.indexOf("&") < 0) return s;
    return s.replace(/&(#x[0-9a-fA-F]+|#\d+|amp|lt|gt|quot|apos);/g, (_, e) =>
      e[0] === "#" ? String.fromCodePoint(e[1] === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)) : ENT[e]);
  }
  function attr(tag, name) {
    const m = new RegExp("\\s" + name + '="([^"]*)"').exec(tag);
    return m ? unxml(m[1]) : null;
  }
  function allText(xml) { // like ElementTree itertext() over <t> nodes
    let s = "";
    for (const m of xml.matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g)) s += m[1];
    return unxml(s);
  }

  async function readWorkbook(buf, progress) {
    const entries = zipEntries(buf);
    progress("Reading shared strings");
    const sst = await zipText(buf, entries, "xl/sharedStrings.xml");
    const strings = [];
    if (sst) for (const m of sst.matchAll(/<si>([\s\S]*?)<\/si>|<si\/>/g)) strings.push(m[1] ? allText(m[1]) : "");
    const rels = await zipText(buf, entries, "xl/_rels/workbook.xml.rels");
    const links = {};
    for (const m of rels.matchAll(/<Relationship\b[^>]*>/g)) {
      let target = attr(m[0], "Target") || "";
      target = target.startsWith("/") ? target.slice(1) : "xl/" + target;
      const parts = [];
      for (const seg of target.split("/")) { if (seg === "..") parts.pop(); else if (seg && seg !== ".") parts.push(seg); }
      links[attr(m[0], "Id")] = parts.join("/");
    }
    const wb = await zipText(buf, entries, "xl/workbook.xml");
    const sheets = [...wb.matchAll(/<sheet\b[^>]*>/g)].map((m) => ({ name: attr(m[0], "name"), rid: attr(m[0], "r:id") }));
    const tables = {};
    let policy = "";
    for (const sh of sheets) {
      const name = sh.name.toLowerCase().replace(/ /g, "_");
      if (name === "start_here") continue;
      progress("Reading " + sh.name);
      const xml = await zipText(buf, entries, links[sh.rid]);
      if (!xml) continue;
      const rows = [];
      let headers = null;
      for (const rm of xml.matchAll(/<row\b[^>]*?(?:\/>|>([\s\S]*?)<\/row>)/g)) {
        const body = rm[1] || "";
        const cells = {};
        for (const cm of body.matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
          const head = cm[1], inner = cm[2] || "";
          const col = (attr(head, "r") || "").replace(/[^A-Za-z]/g, "");
          const t = attr(head, "t");
          let value = null;
          const v = /<v>([\s\S]*?)<\/v>/.exec(inner);
          if (v) value = unxml(v[1]);
          if (t === "s" && value != null) value = strings[parseInt(value, 10)];
          else if (t === "inlineStr") { const is = /<is>([\s\S]*?)<\/is>/.exec(inner); value = is ? allText(is[1]) : ""; }
          cells[col] = value;
        }
        if (name === "policy") {
          policy += Object.values(cells).filter((x) => x != null).join("\n") + "\n";
        } else if (!headers) {
          headers = cells;
        } else if (Object.values(cells).some((x) => x != null)) {
          const row = {};
          for (const [col, key] of Object.entries(headers)) if (key) row[key] = cells[col] !== undefined ? cells[col] : null;
          rows.push(row);
        }
      }
      if (name !== "policy") tables[name] = rows;
      await new Promise((r) => setTimeout(r, 0));
    }
    return { tables, policy };
  }

  const LISTS = {
    alerts: ["hit_ids"],
    hits: ["aliases", "dobs", "place_of_birth", "nationality", "citizenship", "countries", "addresses",
      "identifiers", "categories", "relationships", "sources", "source_urls"],
    practice_labels: ["reason_codes", "customer_record_ids", "evidence"],
  };
  const TABLES = ["alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks", "notes", "search_results", "practice_labels"];

  function toDevTables(tables, policy) {
    const dev = {};
    for (const name of TABLES) {
      if (!tables[name]) throw new Error(`The workbook has no “${name.replace(/_/g, " ")}” sheet. Is this the organisers' Screening Dev Set?`);
      dev[name] = tables[name].map((d) => {
        for (const k of LISTS[name] || []) {
          const v = d[k];
          d[k] = typeof v === "string" ? v.split("; ").map((x) => x.trim()).filter(Boolean) : (v == null ? [] : v);
        }
        if (name === "alerts" && d.hit_count != null) d.hit_count = Math.trunc(parseFloat(d.hit_count));
        if (name === "hits" && d.match_score != null) d.match_score = parseFloat(d.match_score);
        return d;
      });
    }
    const txt = policy.split(/\r?\n/).map((l) => l.replace(/\s+$/, "")).join("\n");
    const at = txt.indexOf("\nname_variants.json");
    const nv = at >= 0 ? txt.slice(at + "\nname_variants.json".length) : "";
    const groups = [], forms = [];
    for (let l of nv.split("\n")) {
      l = l.trim();
      if (l.startsWith("Company legal forms:")) forms.push(...l.split(":").slice(1).join(":").split(",").map((x) => x.trim()).filter(Boolean));
      else if (l.includes(",") && !l.startsWith("Groups")) groups.push(l.split(",").map((x) => x.trim()).filter(Boolean));
    }
    dev.name_variants = { given_names: groups, company_legal_forms: forms };
    return dev;
  }

  // ---------------------------------------------------------------- prepare.py port
  const REASON_CODES = {
    TEMPORAL_IMPOSSIBILITY: { decision: "DIFFERENT_ENTITY", when: "The customer could not have done what the hit's profile reports: too young, or not yet incorporated, at the earliest dated report" },
    DOB_MISMATCH: { decision: "DIFFERENT_ENTITY", when: "The customer's date of birth (or a company's incorporation date) contradicts every birth date the hit gives" },
    LOCATION_MISMATCH: { decision: "DIFFERENT_ENTITY", when: "Every country tied to the customer differs from every country tied to the hit" },
    NAME_MISMATCH_VERIFIED: { decision: "DIFFERENT_ENTITY", when: "The customer's verified legal name does not agree with any of the hit's names" },
    ENTITY_TYPE_MISMATCH: { decision: "DIFFERENT_ENTITY", when: "One is a person and the other a company" },
    DECEASED: { decision: "DIFFERENT_ENTITY", when: "The hit's profile gives a date of death before the customer was screened" },
    NAME_DOB_LOCATION_MATCH: { decision: "SAME_ENTITY", when: "Name, date of birth and country all agree and nothing contradicts them" },
    NAME_DOB_MATCH: { decision: "SAME_ENTITY", when: "Name and date of birth agree and nothing contradicts them" },
    NAME_LOCATION_MATCH: { decision: "SAME_ENTITY", when: "Companies only: name and country agree and nothing contradicts them" },
    INSUFFICIENT_DATA: { decision: "REVIEW", when: "Nothing settles it: no contradiction, and not enough agreement to confirm" },
    AMBIGUOUS_CUSTOMER_RECORD: { decision: "REVIEW", when: "More than one person in the system of record fits the alert and they lead to different decisions" },
  };
  const COST = {
    DIFFERENT_ENTITY: { DIFFERENT_ENTITY: 0, SAME_ENTITY: 3, REVIEW: 3 },
    SAME_ENTITY: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 0, REVIEW: 2 },
    REVIEW: { DIFFERENT_ENTITY: 60, SAME_ENTITY: 2, REVIEW: 0 },
  };

  const fold = (s) => (s ? String(s).normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/ß/g, "ss").trim() : "");
  const STOP = new Set(["aka", "n", "a"]);
  function nameTokens(s) {
    let t = fold(s).replace(/\([^)]*\)/g, " ").replace(/[^\p{L}\p{N}_\s]/gu, " ");
    return t.split(/\s+/).filter((x) => x && !STOP.has(x));
  }
  function tokensOverlap(a, b, variants) {
    const ta = nameTokens(a), tb = nameTokens(b);
    if (!ta.length || !tb.length) return 0;
    const canon = (x) => (variants && variants[x]) || x;
    const sb = new Set(tb.map(canon));
    return ta.filter((x) => sb.has(canon(x))).length;
  }
  function parseDateParts(value) {
    if (value == null) return null;
    const s = String(value).trim();
    if (!s) return null;
    let m;
    if ((m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s))) return { y: +m[1], m: +m[2], d: +m[3], raw: s };
    if ((m = /^(\d{4})-(\d{2})$/.exec(s))) return { y: +m[1], m: +m[2], d: null, raw: s };
    if ((m = /^(\d{4})$/.exec(s))) return { y: +m[1], m: null, d: null, raw: s };
    if ((m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s))) return { y: +m[3], m: +m[2], d: +m[1], raw: s };
    return { y: null, m: null, d: null, raw: s };
  }
  function dobAgrees(c, h) {
    if (!c || !h || c.y == null || h.y == null) return false;
    if (c.y !== h.y) return false;
    if (c.m && h.m && c.m !== h.m) return false;
    if (c.d && h.d && c.d !== h.d) return false;
    return true;
  }
  const noSpace = (s) => String(s || "").replace(/\s+/g, "");
  const multimap = () => new Map();
  const push = (map, k, v) => { if (!map.has(k)) map.set(k, []); map.get(k).push(v); };
  const addSet = (map, k, v) => { if (!map.has(k)) map.set(k, new Set()); map.get(k).add(v); };
  const byKey = (rows, key) => { const o = new Map(); for (const r of rows) o.set(r[key], r); return o; };

  function scorePredictions(preds, labelsBy) {
    let scored = 0, cost = 0, baseline = 0, unsafe = 0;
    const conf = {};
    for (const p of preds) {
      const lab = labelsBy[p.hit_id];
      if (!lab) continue;
      const gold = lab.decision, pred = p.decision;
      if (!COST[pred] || !COST[gold]) continue;
      scored++; cost += COST[gold][pred]; baseline += COST[gold].REVIEW;
      conf[gold + ">" + pred] = (conf[gold + ">" + pred] || 0) + 1;
      if (pred === "DIFFERENT_ENTITY" && (gold === "SAME_ENTITY" || gold === "REVIEW")) unsafe++;
    }
    return { labeled: scored, cost, baseline_review_cost: baseline, decision_score: baseline > 0 ? Math.max(0, 1 - cost / baseline) : null, unsafe_clearances: unsafe, confusion: conf };
  }
  function sampleFromLabels(labels) {
    return labels.map((lab) => {
      const codes = lab.reason_codes || [], ids = lab.customer_record_ids || [];
      return {
        hit_id: lab.hit_id, alert_id: lab.alert_id, decision: lab.decision,
        reason_code: codes[0] || "INSUFFICIENT_DATA",
        customer_record_id: codes.includes("AMBIGUOUS_CUSTOMER_RECORD") ? "AMBIGUOUS" : (ids.length ? ids[0] : null),
        reason: lab.reference_reason || "", evidence: [...(lab.evidence || [])], _sample: true, _sample_source: "practice_labels",
      };
    });
  }

  async function buildBundle(dev, countries, predictionRows, predictionSource, progress) {
    const { hits, alerts, customers, accounts, onboarding, kyc_checks: kycChecks, notes, search_results: searchResults, practice_labels: labels } = dev;
    const nameVariants = dev.name_variants;
    const vidx = {};
    for (const g of nameVariants.given_names || []) { if (!g.length) continue; const c = fold(g[0]); for (const n of g) vidx[fold(n)] = c; }

    const hitsBy = byKey(hits, "hit_id"), alertsBy = byKey(alerts, "alert_id"), custBy = byKey(customers, "record_id"), acctBy = byKey(accounts, "account_id");
    const kycBy = byKey(kycChecks, "check_id"), notesBy = byKey(notes, "note_id"), searchBy = byKey(searchResults, "result_id"), labelsBy = byKey(labels, "hit_id");

    const accountsByLogin = multimap(), accountsByCustomer = multimap();
    for (const a of accounts) {
      if (a.login_handle) push(accountsByLogin, fold(a.login_handle), a.account_id);
      if (a.customer_id) push(accountsByCustomer, a.customer_id, a.account_id);
    }
    const custByEmail = multimap(), custByName = multimap();
    for (const c of customers) {
      if (c.email) push(custByEmail, fold(c.email), c.record_id);
      for (const f of ["full_name", "preferred_name", "login_name"]) {
        const key = nameTokens(c[f] || "").sort().join(" ");
        if (key) push(custByName, key, c.record_id);
      }
    }
    const onbByAccount = multimap(), onbByCustomer = multimap(), onbByApplicant = multimap();
    for (const o of onboarding) { push(onbByAccount, o.account_id, o); push(onbByCustomer, o.customer_id, o); push(onbByApplicant, o.kyc_applicant_id, o); }
    const notesByEmail = multimap();
    for (const n of notes) { const em = fold(n.requester_email || ""); if (em) push(notesByEmail, em, n.note_id); }
    const kycByApplicant = multimap(), approvedDocToApplicants = multimap();
    for (const k of kycChecks) {
      push(kycByApplicant, k.applicant_id, k);
      if ((k.result || "").toLowerCase() === "approved" && k.document_number) addSet(approvedDocToApplicants, fold(k.document_number), k.applicant_id);
    }
    progress("Linking records into people");
    const fullDobKey = (c) => { const p = parseDateParts(c.dob); return p && p.y && p.m && p.d ? `${String(p.y).padStart(4, "0")}-${String(p.m).padStart(2, "0")}-${String(p.d).padStart(2, "0")}` : null; };
    const phoneDobIndex = multimap();
    for (const a of accounts) {
      const c = custBy.get(a.customer_id); if (!c) continue;
      const dk = fullDobKey(c); const phone = noSpace(a.phone) || noSpace(c.phone);
      if (phone && dk) addSet(phoneDobIndex, phone + "|" + dk, a.customer_id);
    }
    for (const c of customers) { const dk = fullDobKey(c), phone = noSpace(c.phone); if (phone && dk) addSet(phoneDobIndex, phone + "|" + dk, c.record_id); }
    const applicantToCustomers = multimap();
    for (const o of onboarding) if (o.kyc_applicant_id && o.customer_id) addSet(applicantToCustomers, o.kyc_applicant_id, o.customer_id);

    function expandPerson(seed) {
      const group = new Set(seed);
      let changed = true;
      while (changed) {
        changed = false;
        const extra = new Set();
        for (const cid of group) {
          const c = custBy.get(cid); if (!c) continue;
          const dk = fullDobKey(c);
          const phones = new Set();
          if (c.phone) phones.add(noSpace(c.phone));
          for (const aid of accountsByCustomer.get(cid) || []) { const ph = acctBy.get(aid).phone; if (ph) phones.add(noSpace(ph)); }
          if (dk) for (const ph of phones) for (const x of phoneDobIndex.get(ph + "|" + dk) || []) extra.add(x);
          for (const o of onbByCustomer.get(cid) || []) for (const k of kycByApplicant.get(o.kyc_applicant_id) || []) {
            if ((k.result || "").toLowerCase() === "approved" && k.document_number) {
              for (const other of approvedDocToApplicants.get(fold(k.document_number)) || []) for (const x of applicantToCustomers.get(other) || []) extra.add(x);
            }
          }
        }
        for (const x of extra) if (!group.has(x)) { group.add(x); changed = true; }
      }
      return group;
    }
    function screenedFits(c, alert) {
      const names = [c.full_name, c.preferred_name, c.login_name];
      const overlap = Math.max(0, ...names.map((n) => tokensOverlap(alert.customer_name || "", n || "", vidx)));
      if (nameTokens(alert.customer_name || "").length >= 2 && overlap < 1) return false;
      if (alert.dob && c.dob) {
        const a = parseDateParts(alert.dob), b = parseDateParts(c.dob);
        if (a && b && a.y && b.y && !dobAgrees(b, a) && !dobAgrees(a, b)) {
          if (a.y !== b.y) return false;
          if (a.m && b.m && a.m !== b.m) return false;
          if (a.d && b.d && a.d !== b.d) return false;
        }
      }
      return true;
    }

    progress("Resolving candidate customers for each alert");
    const needCust = new Set(), needAcc = new Set(), needKyc = new Set(), needNotes = new Set(), needSearch = new Set();
    const needOnb = [], seenOnb = new Set();
    const onbKey = (o) => [o.account_id, o.customer_id, o.kyc_applicant_id].join("|");
    const addOnbFor = (cids, aids) => {
      for (const cid of cids) for (const o of onbByCustomer.get(cid) || []) {
        const k = onbKey(o); if (!seenOnb.has(k)) { seenOnb.add(k); needOnb.push(o); }
        if (o.account_id) aids.add(o.account_id);
      }
      for (const aid of [...aids]) for (const o of onbByAccount.get(aid) || []) { const k = onbKey(o); if (!seenOnb.has(k)) { seenOnb.add(k); needOnb.push(o); } }
    };
    const cases = {};
    let n = 0;
    for (const alert of alerts) {
      const seeds = new Set(), aids = new Set();
      if (alert.account_ref && acctBy.has(alert.account_ref)) { aids.add(alert.account_ref); const cid = acctBy.get(alert.account_ref).customer_id; if (cid) seeds.add(cid); }
      if (alert.login_handle) for (const aid of accountsByLogin.get(fold(alert.login_handle)) || []) { aids.add(aid); const cid = acctBy.get(aid).customer_id; if (cid) seeds.add(cid); }
      if (alert.email) for (const cid of custByEmail.get(fold(alert.email)) || []) seeds.add(cid);
      let unlinked = false;
      if (!seeds.size) {
        unlinked = true;
        const key = nameTokens(alert.customer_name || "").sort().join(" ");
        const cands = [...new Set(custByName.get(key) || [])];
        cands.filter((cid) => screenedFits(custBy.get(cid), alert)).slice(0, 12).forEach((cid) => seeds.add(cid));
      }
      const people = [];
      const remaining = new Set(seeds);
      while (remaining.size) {
        const cid = remaining.values().next().value;
        const group = expandPerson([cid]);
        people.push([...group].sort());
        for (const x of group) remaining.delete(x);
      }
      const candidateIds = [...new Set(people.flat())].sort();
      for (const cid of candidateIds) { needCust.add(cid); for (const aid of accountsByCustomer.get(cid) || []) aids.add(aid); }
      if (alert.account_ref) aids.add(alert.account_ref);
      for (const a of aids) needAcc.add(a);
      addOnbFor(candidateIds, aids);
      const candSet = new Set(candidateIds);
      const kycIds = new Set();
      for (const o of needOnb) if (candSet.has(o.customer_id) || aids.has(o.account_id)) for (const k of kycByApplicant.get(o.kyc_applicant_id) || []) { kycIds.add(k.check_id); needKyc.add(k.check_id); }
      const emails = new Set();
      if (alert.email) emails.add(fold(alert.email));
      for (const cid of candidateIds) { const em = (custBy.get(cid) || {}).email; if (em) emails.add(fold(em)); }
      const noteIds = new Set();
      for (const em of emails) for (const nid of notesByEmail.get(em) || []) { noteIds.add(nid); needNotes.add(nid); }
      cases[alert.alert_id] = {
        alert_id: alert.alert_id, candidate_customer_ids: candidateIds, person_groups: people, account_ids: [...aids].sort(),
        kyc_ids: [...kycIds].sort(), note_ids: [...noteIds].sort(), search_ids: [], unlinked_name_search: unlinked,
      };
      if (++n % 60 === 0) { progress(`Resolving customers: ${n} of ${alerts.length} alerts`); await new Promise((r) => setTimeout(r, 0)); }
    }

    const ingestCited = (ids) => {
      for (const i of ids || []) {
        if (!i) continue;
        if (custBy.has(i)) needCust.add(i); else if (acctBy.has(i)) needAcc.add(i); else if (kycBy.has(i)) needKyc.add(i);
        else if (notesBy.has(i)) needNotes.add(i); else if (searchBy.has(i)) needSearch.add(i);
      }
    };
    for (const lab of labels) {
      ingestCited(lab.evidence); ingestCited(lab.customer_record_ids);
      const cs = cases[lab.alert_id];
      if (cs) for (const cid of lab.customer_record_ids || []) if (custBy.has(cid) && !cs.candidate_customer_ids.includes(cid)) { cs.candidate_customer_ids.push(cid); needCust.add(cid); }
    }

    progress("Selecting web search results");
    const byQuery = multimap();
    for (const s of searchResults) push(byQuery, fold(s.query || ""), s.result_id);
    for (const h of hits) {
      const sids = [];
      for (const nm of [h.name || "", ...(h.aliases || [])]) {
        sids.push(...(byQuery.get(fold(nm)) || []));
        const parts = String(nm || "").replace(" (AKA)", "").split(",").map((x) => x.trim()).filter(Boolean);
        if (parts.length === 2) { sids.push(...(byQuery.get(fold(`${parts[1]} ${parts[0]}`)) || [])); sids.push(...(byQuery.get(fold(`${parts[0]} ${parts[1]}`)) || [])); }
      }
      const seen = [];
      for (const sid of sids) { if (!seen.includes(sid)) seen.push(sid); if (seen.length >= 6) break; }
      seen.forEach((s) => needSearch.add(s));
      const cs = cases[h.alert_id];
      if (cs) for (const sid of seen) if (!cs.search_ids.includes(sid)) cs.search_ids.push(sid);
    }

    let preds = predictionRows || [];
    const sample = !preds.length;
    let source = predictionSource;
    if (sample) { preds = sampleFromLabels(labels); source = "sample:practice_labels"; }
    else for (const p of preds) {
      ingestCited(Array.isArray(p.evidence) ? p.evidence : []);
      const cid = p.customer_record_id;
      if (cid && custBy.has(cid)) { needCust.add(cid); const cs = cases[p.alert_id]; if (cs && !cs.candidate_customer_ids.includes(cid)) cs.candidate_customer_ids.push(cid); }
    }
    for (const kid of [...needKyc]) {
      const k = kycBy.get(kid);
      for (const o of onbByApplicant.get(k.applicant_id) || []) {
        if (o.customer_id) needCust.add(o.customer_id);
        const key = onbKey(o); if (!seenOnb.has(key)) { seenOnb.add(key); needOnb.push(o); }
      }
    }
    const predsBy = {};
    for (const p of preds) if (p.hit_id) predsBy[p.hit_id] = p;
    const labelsObj = Object.fromEntries(labelsBy);
    const pick = (ids, map) => { const o = {}; for (const i of [...ids].sort()) if (map.has(i)) o[i] = map.get(i); return o; };
    const meta = {
      generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      sample_predictions: sample, prediction_source: source,
      n_hits: hits.length, n_alerts: alerts.length, n_practice_labels: labels.length, n_predictions: Object.keys(predsBy).length,
      n_customers_in_bundle: needCust.size, output_path: source, output_mtime: null,
      practice_score: scorePredictions(Object.values(predsBy), labelsObj), cost_matrix: COST,
      built_in_browser: true,
    };
    return {
      meta, reason_codes: REASON_CODES, name_variants: nameVariants, countries,
      hits: Object.fromEntries(hitsBy), alerts: Object.fromEntries(alertsBy),
      customers: pick(needCust, custBy), accounts: pick(needAcc, acctBy), kyc_checks: pick(needKyc, kycBy),
      notes: pick(needNotes, notesBy), search_results: pick(needSearch, searchBy), onboarding: needOnb,
      labels: labelsObj, predictions: predsBy, cases,
    };
  }

  // ---------------------------------------------------------------- cache
  const DB = "fathom", STORE = "kv", KEY = "bundle.v1";
  function idb(mode, fn) {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) return resolve(null);
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onerror = () => resolve(null);
      req.onsuccess = () => {
        const tx = req.result.transaction(STORE, mode);
        const r = fn(tx.objectStore(STORE));
        tx.oncomplete = () => resolve(r && "result" in r ? r.result : true);
        tx.onerror = () => reject(tx.error);
      };
    });
  }
  const getCached = () => idb("readonly", (s) => s.get(KEY)).catch(() => null);
  const setCached = (b) => idb("readwrite", (s) => s.put(b, KEY)).catch(() => false);
  const clearCached = () => idb("readwrite", (s) => s.delete(KEY)).catch(() => false);

  // ---------------------------------------------------------------- entry points
  async function fetchPredictions() {
    try {
      const r = await fetch("data/dev.jsonl", { cache: "no-store" });
      if (!r.ok) return null;
      const rows = (await r.text()).split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));
      return rows.length ? rows : null;
    } catch (_) { return null; }
  }
  async function fetchCountries() {
    const r = await fetch("countries.json", { cache: "force-cache" });
    if (!r.ok) throw new Error("countries.json is missing from the site");
    return r.json();
  }

  async function fromFiles(files, progress) {
    files = [...files];
    const xlsx = files.find((f) => /\.xlsx$/i.test(f.name));
    let dev;
    if (xlsx) {
      progress("Opening " + xlsx.name);
      const { tables, policy } = await readWorkbook(await xlsx.arrayBuffer(), progress);
      dev = toDevTables(tables, policy);
    } else {
      // a dev/ folder: alerts.jsonl, hits.jsonl, … plus name_variants.json
      const byName = Object.fromEntries(files.map((f) => [f.name.replace(/^.*\//, ""), f]));
      dev = {};
      for (const t of TABLES) {
        const f = byName[t + ".jsonl"];
        if (!f) throw new Error(`Missing ${t}.jsonl. Drop the whole dev/ folder, or the organisers' .xlsx workbook.`);
        progress("Reading " + f.name);
        dev[t] = (await f.text()).split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));
      }
      const nv = byName["name_variants.json"];
      dev.name_variants = nv ? JSON.parse(await nv.text()) : { given_names: [], company_legal_forms: [] };
    }
    progress("Loading decisions");
    const [countries, preds] = await Promise.all([fetchCountries(), fetchPredictions()]);
    const bundle = await buildBundle(dev, countries, preds, preds ? "data/dev.jsonl" : null, progress);
    progress("Saving in this browser");
    await setCached(bundle);
    return bundle;
  }

  window.FathomLoader = { fromFiles, getCached, setCached, clearCached, buildBundle, readWorkbook, toDevTables };
})();
