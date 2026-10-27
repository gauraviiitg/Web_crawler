const PAGE = 40;
const state = { data: null, tab: "new", section: "", shown: PAGE, latestDay: "", lang: localStorage.getItem("lang") === "hi" ? "hi" : "en" };
const $ = (id) => document.getElementById(id);

const I18N = {
  en: {
    updated: "Updated", source: "Source", tab_new: "New today", tab_worth: "Worth reading",
    tab_picks: "Today's picks", all_districts: "All districts",
    b_filtered: "No picks match these filters. Try the \"Worth reading\" or \"Personalised\" tab with the same filters.",
    tab_closing: "Closing in 3 days", tab_updated: "Updated", tab_all: "All active", tab_closed: "Recently closed",
    search: "Search title, tender ID, organisation, location...", all_orgs: "All organisations",
    all_sectors: "All sectors", any_decision: "Any decision", worth_reading: "Worth reading", maybe: "Maybe",
    skip: "Skip", any_value: "Any value", v1: "Below ₹10 lakh", v2: "₹10 lakh – ₹1 crore", v3: "₹1 – ₹10 crore",
    v4: "Above ₹10 crore", v5: "Value not disclosed", sort_relevance: "Sort: relevance",
    sort_closing: "Sort: closing soonest", sort_newest: "Sort: newest", sort_value: "Sort: highest value",
    more: "Show more",
    footer: "Tender data is read from public pages of the Rajasthan eProcurement portal. Classification and \"worth reading\" decisions are AI-generated and can be wrong — always verify on the official portal before bidding. To open a tender: go to the portal → Search → enter the Tender ID.",
    lang_toggle: "हिंदी", st_active: "Active tenders", st_new: "New today", st_worth: "Worth reading",
    st_closing: "Closing in 3 days", st_value: "Total disclosed value", not_disclosed: "Not disclosed",
    badge_new: "NEW", badge_upd: "UPDATED", closes_today: "Closes today", closes_in: "Closes in {n} days",
    rule_based: "rule-based", rule_based_tip: "AI analysis pending; keyword rules used", value: "Value", emd: "EMD",
    closes: "Closes", details_pending: "Value/EMD: details pending", tenders: "{n} tenders", tender: "1 tender",
    empty: "No tenders here", empty_new: " today — nothing new was published since the last run",
    close: "Close", open_portal: "Open portal", copy_id: "Copy Tender ID", copied: "Copied", copy_link: "Copy link",
    link_copied: "Link copied", ai_analysis: "AI analysis", rule_analysis: "Rule-based analysis (AI analysis pending)",
    why: "Why", cash_to_bid: "Cash to bid (startup/MSE, excl. stock)", blockers: "Blockers",
    key_req: "Key requirements", risk_flags: "Risk flags", model: "Model", listing_only: "based on listing only",
    no_detail: "Full tender details (value, EMD, eligibility) could not be fetched yet; the crawler retries on the next run.",
    tender_id: "Tender ID", ref_no: "Reference no.", bid_closes: "Bid submission closes", bid_opening: "Bid opening",
    first_seen: "First seen by crawler", other_lots: "Other lots under the same tender number",
    changes: "Changes detected (corrigendum)", details_changed: "details changed",
    howto: "To open this tender: Open portal → Search → paste the Tender ID. Documents (PDF/BOQ) are downloaded on the portal.",
    translate_title: "Translate title (Google)", llm_pending: "AI analysis pending for {n} tenders (free-tier limit; continues next run)",
    last_run_problem: "Last run problem: {e} — showing previous data.", load_error: "Could not load data: {e}",
    b_title: "Today's top picks for us", b_why: "Why", b_risks: "Risks", b_next: "Next step",
    b_cash: "Cash to bid", b_deadline: "Deadline", b_days: "{n} days left", b_open: "Open details",
    b_tips: "Tips for this week", b_by_ai: "Written by AI ({m})", b_template: "Template briefing — add a free AI key for written advice",
    b_none: "No suitable tenders open right now.", b_of: "{n} feasible tenders considered",
    tab_personal: "Personalised", b_personal: "Your personalised sections", b_open_new: "{o} open · {n} new today",
    see_all: "See all", no_sections: "No personalised sections configured (config/settings.yaml → personalised).",
    open_tender: "Open tender on portal", portal_tip: "Copies {id} and opens the portal list; click \"{org}\", then Ctrl+F and paste",
    how_open: "How to open this tender and its PDFs", step1: "Click \"Open tender on portal\" (the Tender ID is copied for you).",
    step2: "On the portal page, click the organisation {org}.", step3: "Press Ctrl+F, paste {id} and click the tender title.",
    step4: "On the tender page, click a document (NIT PDF, BOQ) and type the captcha to download it.",
    docs: "Documents on the portal", docs_note: "The portal requires a captcha for each download, so the files can't be linked directly.",
  },
  hi: {
    updated: "अपडेट", source: "स्रोत", tab_new: "आज नए",
    tab_picks: "आज की पसंद", all_districts: "सभी जिले",
    b_filtered: "इन फ़िल्टर से कोई पसंद मेल नहीं खाती। इन्हीं फ़िल्टर के साथ \"पढ़ने योग्य\" या \"व्यक्तिगत\" टैब देखें।", tab_worth: "पढ़ने योग्य", tab_closing: "3 दिन में बंद",
    tab_updated: "संशोधित", tab_all: "सभी सक्रिय", tab_closed: "हाल में बंद",
    search: "शीर्षक, टेंडर आईडी, विभाग, स्थान खोजें...", all_orgs: "सभी विभाग", all_sectors: "सभी क्षेत्र",
    any_decision: "कोई भी निर्णय", worth_reading: "पढ़ने योग्य", maybe: "शायद", skip: "छोड़ें", any_value: "कोई भी मूल्य",
    v1: "₹10 लाख से कम", v2: "₹10 लाख – ₹1 करोड़", v3: "₹1 – ₹10 करोड़", v4: "₹10 करोड़ से अधिक", v5: "मूल्य घोषित नहीं",
    sort_relevance: "क्रम: प्रासंगिकता", sort_closing: "क्रम: जल्द बंद होने वाले", sort_newest: "क्रम: नवीनतम",
    sort_value: "क्रम: अधिकतम मूल्य", more: "और दिखाएँ",
    footer: "टेंडर डेटा राजस्थान ई-प्रोक्योरमेंट पोर्टल के सार्वजनिक पृष्ठों से लिया गया है। वर्गीकरण और \"पढ़ने योग्य\" निर्णय एआई द्वारा बनाए गए हैं और गलत हो सकते हैं — बोली लगाने से पहले आधिकारिक पोर्टल पर अवश्य जाँचें। टेंडर खोलने के लिए: पोर्टल → Search → टेंडर आईडी डालें।",
    lang_toggle: "English", st_active: "सक्रिय टेंडर", st_new: "आज नए", st_worth: "पढ़ने योग्य", st_closing: "3 दिन में बंद",
    st_value: "कुल घोषित मूल्य", not_disclosed: "घोषित नहीं", badge_new: "नया", badge_upd: "संशोधित",
    closes_today: "आज बंद", closes_in: "{n} दिन में बंद", rule_based: "नियम-आधारित",
    rule_based_tip: "एआई विश्लेषण लंबित; कीवर्ड नियम प्रयुक्त", value: "मूल्य", emd: "ईएमडी", closes: "अंतिम तिथि",
    details_pending: "मूल्य/ईएमडी: विवरण लंबित", tenders: "{n} टेंडर", tender: "1 टेंडर", empty: "यहाँ कोई टेंडर नहीं",
    empty_new: " — पिछले रन के बाद कोई नया टेंडर प्रकाशित नहीं हुआ", close: "बंद करें", open_portal: "पोर्टल खोलें",
    copy_id: "टेंडर आईडी कॉपी करें", copied: "कॉपी हुआ", copy_link: "लिंक कॉपी करें", link_copied: "लिंक कॉपी हुआ",
    ai_analysis: "एआई विश्लेषण", rule_analysis: "नियम-आधारित विश्लेषण (एआई विश्लेषण लंबित)", why: "क्यों",
    cash_to_bid: "बोली हेतु नकद (स्टार्टअप/एमएसई, माल छोड़कर)", blockers: "बाधाएँ", key_req: "मुख्य आवश्यकताएँ",
    risk_flags: "जोखिम", model: "मॉडल", listing_only: "केवल सूची के आधार पर",
    no_detail: "पूरा विवरण (मूल्य, ईएमडी, पात्रता) अभी प्राप्त नहीं हुआ; क्रॉलर अगले रन में फिर प्रयास करेगा।",
    tender_id: "टेंडर आईडी", ref_no: "संदर्भ संख्या", bid_closes: "बोली जमा करने की अंतिम तिथि", bid_opening: "बोली खुलने की तिथि",
    first_seen: "क्रॉलर ने पहली बार देखा", other_lots: "इसी टेंडर संख्या के अन्य लॉट", changes: "बदलाव (शुद्धिपत्र)",
    details_changed: "विवरण बदला",
    howto: "टेंडर खोलने के लिए: पोर्टल खोलें → Search → टेंडर आईडी डालें। दस्तावेज़ (PDF/BOQ) पोर्टल से डाउनलोड करें।",
    translate_title: "शीर्षक का हिंदी अनुवाद (Google)", llm_pending: "{n} टेंडरों का एआई विश्लेषण लंबित (मुफ़्त सीमा; अगले रन में जारी)",
    last_run_problem: "पिछले रन में समस्या: {e} — पिछला डेटा दिखाया जा रहा है।", load_error: "डेटा लोड नहीं हो सका: {e}",
    b_title: "आज हमारे लिए सर्वश्रेष्ठ टेंडर", b_why: "क्यों", b_risks: "जोखिम", b_next: "अगला कदम", b_cash: "बोली हेतु नकद",
    b_deadline: "अंतिम तिथि", b_days: "{n} दिन शेष", b_open: "विवरण देखें", b_tips: "इस सप्ताह के सुझाव",
    b_by_ai: "एआई द्वारा लिखित ({m})", b_template: "टेम्पलेट सलाह — लिखित सलाह के लिए मुफ़्त एआई कुंजी जोड़ें",
    b_none: "अभी कोई उपयुक्त टेंडर खुला नहीं है।", b_of: "{n} संभव टेंडरों पर विचार किया गया",
    tab_personal: "व्यक्तिगत", b_personal: "आपके व्यक्तिगत अनुभाग", b_open_new: "{o} खुले · आज {n} नए",
    see_all: "सभी देखें", no_sections: "कोई व्यक्तिगत अनुभाग सेट नहीं है (config/settings.yaml → personalised)।",
    open_tender: "पोर्टल पर टेंडर खोलें", portal_tip: "{id} कॉपी होगा और पोर्टल सूची खुलेगी; \"{org}\" पर क्लिक करें, फिर Ctrl+F से पेस्ट करें",
    how_open: "यह टेंडर और इसकी PDF कैसे खोलें", step1: "\"पोर्टल पर टेंडर खोलें\" पर क्लिक करें (टेंडर आईडी अपने-आप कॉपी हो जाएगी)।",
    step2: "पोर्टल पेज पर विभाग {org} पर क्लिक करें।", step3: "Ctrl+F दबाएँ, {id} पेस्ट करें और टेंडर के शीर्षक पर क्लिक करें।",
    step4: "टेंडर पेज पर दस्तावेज़ (NIT PDF, BOQ) पर क्लिक करें और कैप्चा भरकर डाउनलोड करें।",
    docs: "पोर्टल पर दस्तावेज़", docs_note: "पोर्टल हर डाउनलोड पर कैप्चा माँगता है, इसलिए फ़ाइलों का सीधा लिंक नहीं दिया जा सकता।",
  },
};
function T(key, vars = {}) {
  const s = I18N[state.lang][key] ?? I18N.en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}
const pickLang = (en, hi) => (state.lang === "hi" && hi ? hi : en);

const LABELS_HI = {
  ref_no: "संदर्भ संख्या", tender_type: "टेंडर प्रकार", form_of_contract: "अनुबंध का स्वरूप", tender_category: "श्रेणी",
  product_category: "उत्पाद श्रेणी", sub_category: "उप श्रेणी", contract_type: "अनुबंध प्रकार", covers: "कवर की संख्या",
  payment_mode: "भुगतान का तरीका", tender_value: "टेंडर मूल्य", emd: "ईएमडी", emd_percentage: "ईएमडी %",
  emd_exemption: "ईएमडी छूट", tender_fee: "टेंडर शुल्क", processing_fee: "प्रोसेसिंग शुल्क", fee_exemption: "शुल्क छूट",
  description: "कार्य विवरण", pre_qualification: "पूर्व-योग्यता", remarks: "टिप्पणी", location: "स्थान", pincode: "पिनकोड",
  period_of_work_days: "कार्य अवधि (दिन)", bid_validity_days: "बोली वैधता (दिन)", tenderer_class: "बोलीदाता श्रेणी",
  published: "प्रकाशित", doc_start: "दस्तावेज़ डाउनलोड आरंभ", doc_end: "दस्तावेज़ डाउनलोड समाप्त",
  clarification_end: "स्पष्टीकरण समाप्त", prebid_date: "प्री-बिड बैठक", prebid_place: "प्री-बिड स्थान",
  bid_start: "बोली जमा आरंभ", bid_end: "बोली जमा समाप्त", bid_opening: "बोली खुलना", bid_opening_place: "बोली खुलने का स्थान",
  nit_documents: "एनआईटी दस्तावेज़", work_documents: "टेंडर दस्तावेज़", authority_name: "टेंडर आमंत्रित करने वाला अधिकारी",
  authority_address: "अधिकारी का पता",
};

const LABELS = {
  ref_no: "Reference no.", tender_type: "Tender type", form_of_contract: "Form of contract",
  tender_category: "Category", product_category: "Product category", sub_category: "Sub category",
  contract_type: "Contract type", covers: "No. of covers", payment_mode: "Payment mode",
  tender_value: "Tender value", emd: "EMD", emd_percentage: "EMD %", emd_exemption: "EMD exemption",
  tender_fee: "Tender fee", processing_fee: "Processing fee", fee_exemption: "Fee exemption",
  description: "Work description", pre_qualification: "Pre-qualification", remarks: "Remarks",
  location: "Location", pincode: "Pincode", period_of_work_days: "Period of work (days)",
  bid_validity_days: "Bid validity (days)", tenderer_class: "Tenderer class", published: "Published",
  doc_start: "Document download start", doc_end: "Document download end",
  clarification_end: "Clarification end", prebid_date: "Pre-bid meeting", prebid_place: "Pre-bid place",
  bid_start: "Bid submission start", bid_end: "Bid submission end", bid_opening: "Bid opening",
  bid_opening_place: "Bid opening place", nit_documents: "NIT documents",
  work_documents: "Tender documents", authority_name: "Tender inviting authority",
  authority_address: "Authority address",
};
const MONEY = new Set(["tender_value", "emd", "tender_fee", "processing_fee"]);
const DATES = new Set(["published", "doc_start", "doc_end", "clarification_end", "prebid_date", "bid_start", "bid_end", "bid_opening"]);
const decisionText = (d) => (d ? T(d) : "");

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function inr(n) {
  if (n == null) return T("not_disclosed");
  if (n >= 1e7) return "₹" + (n / 1e7).toFixed(2).replace(/\.00$/, "") + " Cr";
  if (n >= 1e5) return "₹" + (n / 1e5).toFixed(2).replace(/\.00$/, "") + " L";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}
function parseIst(s) { return s ? new Date(s + ":00+05:30") : null; }
function fmtDate(s) {
  const d = parseIst(s);
  if (!d || isNaN(d)) return s || "-";
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
}
function daysLeft(t) {
  const d = parseIst(t.closing);
  return d ? (d - Date.now()) / 864e5 : null;
}
function hasDetail(t) { return Object.keys(t.detail || {}).length > 0; }
function isNew(t) { return (t.first_seen || "").slice(0, 10) === state.latestDay; }
function isUpdated(t) { return t.changes?.length && (t.last_changed || "").slice(0, 10) === state.latestDay; }

function inTab(t, tab) {
  const dl = daysLeft(t);
  switch (tab) {
    case "picks": return pickIds().has(t.id);
    case "new": return t.status === "active" && isNew(t);
    case "worth": return t.status === "active" && t.analysis?.decision === "worth_reading";
    case "personal": return t.status === "active" && (state.section ? (t.personal || []).includes(state.section) : t.personal?.length > 0);
    case "closing": return t.status === "active" && dl != null && dl >= 0 && dl <= 3;
    case "updated": return t.status === "active" && t.changes?.length > 0;
    case "closed": return t.status !== "active";
    default: return t.status === "active";
  }
}

function pickIds() {
  const b = state.data.briefing || {};
  return state.data._pickIds ||= new Set([...(b.picks || []), ...(b.personal || []).flatMap((s) => s.top || [])].map((p) => p.tender_id));
}

function pickVisible(id) {
  const t = state.data.tenders.find((x) => x.id === id);
  return !t || matchesFilters(t);
}

function districtName(id) {
  const d = (state.data.districts || []).find((x) => x.id === id);
  return d ? pickLang(d.name_en, d.name_hi) : id;
}

function renderDistricts() {
  const sel = $("f-district");
  const current = sel.value || localStorage.getItem("district") || "";
  const counts = {};
  state.data.tenders.forEach((t) => { if (t.status === "active") (t.districts || []).forEach((d) => { counts[d] = (counts[d] || 0) + 1; }); });
  const opts = (state.data.districts || []).filter((d) => counts[d.id])
    .map((d) => ({ id: d.id, name: pickLang(d.name_en, d.name_hi), n: counts[d.id] }))
    .sort((a, b) => (a.id === "Statewide") - (b.id === "Statewide") || a.name.localeCompare(b.name, state.lang));
  sel.innerHTML = `<option value="">${T("all_districts")}</option>` +
    opts.map((d) => `<option value="${esc(d.id)}">${esc(d.name)} (${d.n})</option>`).join("");
  sel.value = opts.some((d) => d.id === current) ? current : "";
}

function matchesFilters(t) {
  const q = $("q").value.trim().toLowerCase();
  if (q) {
    const hay = [t.id, t.title, t.org_chain, t.location, t.analysis?.summary, t.analysis?.sector, ...(t.analysis?.tags || [])].join(" ").toLowerCase();
    if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
  }
  if ($("f-district").value && !(t.districts || []).includes($("f-district").value)) return false;
  if ($("f-org").value && t.org !== $("f-org").value) return false;
  if ($("f-sector").value && t.analysis?.sector !== $("f-sector").value) return false;
  if ($("f-decision").value && t.analysis?.decision !== $("f-decision").value) return false;
  const v = $("f-value").value;
  if (v === "none") return t.value == null;
  if (v) {
    const [lo, hi] = v.split("-").map((x) => (x === "" ? Infinity : Number(x)));
    if (t.value == null || t.value < lo || t.value >= hi) return false;
  }
  return true;
}

function sorted(list) {
  const by = $("sort").value;
  const rank = { worth_reading: 0, maybe: 1, skip: 2 };
  const cmp = {
    relevance: (a, b) => (rank[a.analysis?.decision] ?? 3) - (rank[b.analysis?.decision] ?? 3) || (b.analysis?.relevance ?? 0) - (a.analysis?.relevance ?? 0),
    closing: (a, b) => (a.closing || "9").localeCompare(b.closing || "9"),
    newest: (a, b) => (b.published || "").localeCompare(a.published || ""),
    value: (a, b) => (b.value ?? -1) - (a.value ?? -1),
  }[by];
  return list.slice().sort(cmp);
}

function card(t) {
  const a = t.analysis || {};
  const dl = daysLeft(t);
  const badges = [];
  if (a.decision) badges.push(`<span class="badge ${a.decision}">${decisionText(a.decision)}${a.relevance != null ? " · " + a.relevance : ""}</span>`);
  if (isNew(t)) badges.push(`<span class="badge new">${T("badge_new")}</span>`);
  if (isUpdated(t)) badges.push(`<span class="badge upd">${T("badge_upd")}</span>`);
  if (t.status === "active" && dl != null && dl <= 3) badges.push(`<span class="badge urgent">${dl < 1 ? T("closes_today") : T("closes_in", { n: Math.ceil(dl) })}</span>`);
  if (t.status !== "active") badges.push(`<span class="badge">${esc(t.status)}</span>`);
  (t.personal || []).forEach((id) => badges.push(`<span class="badge personal">★ ${esc(sectionName(id))}</span>`));
  if (a.sector) badges.push(`<span class="badge">${esc(a.sector)}</span>`);
  if (a.work_type) badges.push(`<span class="badge">${esc(a.work_type)}</span>`);
  (a.risk_flags || []).slice(0, 3).forEach((f) => badges.push(`<span class="badge flag">${esc(f)}</span>`));
  if (a.source === "rules") badges.push(`<span class="badge rules" title="${T("rule_based_tip")}">${T("rule_based")}</span>`);
  return `<article class="card" data-id="${esc(t.id)}">
    <div class="badges">${badges.join("")}</div>
    <h3>${esc(t.title)}</h3>
    <div class="meta">
      <span>${esc(t.org)}</span><span>${esc(t.id)}</span>
      ${hasDetail(t) ? `<span>${T("value")}: <span class="money">${inr(t.value)}</span></span><span>${T("emd")}: ${inr(t.emd)}</span>` : `<span>${T("details_pending")}</span>`}
      <span>${T("closes")}: <b>${fmtDate(t.closing)}</b></span>
      ${t.location ? `<span>📍 ${esc(t.location)}</span>` : ""}
      ${t.districts?.length ? `<span class="district">🗺 ${esc(t.districts.map(districtName).join(", "))}</span>` : ""}
      ${t.status === "active" ? portalButton(t, "small") : ""}
    </div>
    ${a.summary && a.source === "llm" ? `<p class="summary">${esc(pickLang(a.summary, a.summary_hi))}</p>` : ""}
  </article>`;
}

const ORG_URL = "https://eproc.rajasthan.gov.in/nicgep/app?page=FrontEndTendersByOrganisation&service=page";

function portalButton(t, cls = "") {
  const url = state.data.portal.org_url || ORG_URL;
  return `<a class="portal ${cls}" href="${esc(url)}" target="_blank" rel="noopener" data-copy="${esc(t.id)}"
    title="${esc(T("portal_tip", { org: t.org || "", id: t.id }))}">${T("open_tender")} ↗</a>`;
}

function tenderRef(id) {
  const t = state.data.tenders.find((x) => x.id === id);
  return { id, org: t?.org || "" };
}

function portalSteps(t) {
  return `<ol class="steps">
    <li>${T("step1")}</li>
    <li>${T("step2", { org: `<b>${esc(t.org || "")}</b>` })}</li>
    <li>${T("step3", { id: `<b>${esc(t.id)}</b>` })}</li>
    <li>${T("step4")}</li></ol>`;
}

function sectionName(id) {
  const s = (state.data.personalised || []).find((x) => x.id === id);
  return s ? pickLang(s.name_en, s.name_hi) : id;
}

function renderSections() {
  const box = $("sections");
  const sections = state.data.personalised || [];
  box.hidden = state.tab !== "personal";
  if (box.hidden) return;
  if (!sections.length) { box.innerHTML = `<p class="meta">${T("no_sections")}</p>`; return; }
  if (!sections.some((s) => s.id === state.section)) state.section = sections[0].id;
  box.innerHTML = sections.map((s) => {
    const n = state.data.tenders.filter((t) => t.status === "active" && (t.personal || []).includes(s.id)).length;
    return `<button data-section="${esc(s.id)}" class="${s.id === state.section ? "active" : ""}">★ ${esc(pickLang(s.name_en, s.name_hi))} <span class="n">${n}</span></button>`;
  }).join("");
}

function openSection(id) {
  state.tab = "personal"; state.section = id; state.shown = PAGE;
  render();
  $("tabs").scrollIntoView?.({ behavior: "smooth" });
}

function renderBriefing() {
  const b = state.data.briefing;
  const box = $("briefing");
  if (!b || state.tab !== "picks") { box.hidden = true; return; }
  const L = (o, key) => pickLang(o[key + "_en"], o[key + "_hi"]);
  const filtered = $("q").value.trim() || ["f-district", "f-org", "f-sector", "f-decision", "f-value"].some((id) => $(id).value);
  const list = (items) => (items?.length ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "");
  const picks = (b.picks || []).filter((p) => pickVisible(p.tender_id)).map((p) => `
    <article class="pick">
      <div class="rank">${p.rank}</div>
      <div class="pick-body">
        <h3><a href="?id=${encodeURIComponent(p.tender_id)}" data-id="${esc(p.tender_id)}">${esc(p.title)}</a>
          ${p.is_new ? `<span class="badge new">${T("badge_new")}</span>` : ""}</h3>
        <div class="meta">
          <span>${esc(p.authority || "")}</span><span>${esc(p.tender_id)}</span>
          ${p.location ? `<span>📍 ${esc(p.location)}</span>` : ""}
          <span>${T("value")}: <b>${inr(p.value)}</b></span>
          <span>${T("b_cash")}: <b>${p.cash_to_bid != null ? "₹" + Number(p.cash_to_bid).toLocaleString("en-IN") : "-"}</b></span>
          <span>${T("b_deadline")}: <b>${fmtDate(p.closing)}</b>${p.days_left != null ? ` (${T("b_days", { n: Math.floor(p.days_left) })})` : ""}</span>
        </div>
        ${L(p, "why") ? `<p><b>${T("b_why")}:</b> ${esc(L(p, "why"))}</p>` : ""}
        ${(state.lang === "hi" && p.risks_hi?.length ? p.risks_hi : p.risks_en)?.length ? `<b>${T("b_risks")}</b>${list(state.lang === "hi" && p.risks_hi?.length ? p.risks_hi : p.risks_en)}` : ""}
        ${L(p, "next_step") ? `<p class="next"><b>${T("b_next")}:</b> ${esc(L(p, "next_step"))}</p>` : ""}
        <div class="actions">${portalButton(tenderRef(p.tender_id))}
          <a class="secondary" href="?id=${encodeURIComponent(p.tender_id)}" data-id="${esc(p.tender_id)}">${T("b_open")}</a></div>
      </div>
    </article>`).join("");
  const advice = state.lang === "hi" && b.advice_hi?.length ? b.advice_hi : b.advice_en;
  const personal = (b.personal || []).map((s) => ({ ...s, top: (s.top || []).filter((p) => pickVisible(p.tender_id)) }))
    .filter((s) => s.top.length || !filtered).map((s) => `
    <div class="psec">
      <h4>★ ${esc(pickLang(s.name_en, s.name_hi))} <span class="meta">${T("b_open_new", { o: s.open, n: s.new })}</span>
        <button class="link" data-section="${esc(s.id)}">${T("see_all")} →</button></h4>
      <ul>${s.top.map((p) => {
        const bl = state.lang === "hi" && p.blockers_hi?.length ? p.blockers_hi : p.blockers;
        return `<li><a href="?id=${encodeURIComponent(p.tender_id)}" data-id="${esc(p.tender_id)}">${esc(p.title)}</a>
          <span class="meta">${esc(p.location || "")} · ${inr(p.value)} · ${T("b_deadline")}: ${fmtDate(p.closing)}${p.cash_to_bid != null ? ` · ${T("b_cash")}: ₹${Number(p.cash_to_bid).toLocaleString("en-IN")}` : ""}</span>
          ${bl?.length ? `<span class="blk">⚠ ${esc(bl.join("; "))}</span>` : ""}
          ${portalButton(tenderRef(p.tender_id), "small")}</li>`;
      }).join("")}</ul>
    </div>`).join("");
  box.innerHTML = `
    <h2>${T("b_title")}</h2>
    ${L(b, "headline") ? `<p class="headline">${esc(L(b, "headline"))}</p>` : ""}
    ${picks || `<p>${filtered && b.picks?.length ? T("b_filtered") : T("b_none")}</p>`}
    ${personal ? `<div class="box"><h4>${T("b_personal")}</h4>${personal}</div>` : ""}
    ${advice?.length ? `<div class="box"><h4>${T("b_tips")}</h4>${list(advice)}</div>` : ""}
    <p class="meta">${b.source === "llm" ? T("b_by_ai", { m: esc(b.model || "") }) : T("b_template")} · ${T("b_of", { n: b.candidates ?? 0 })} · ${fmtDate(b.generated_at)}</p>`;
  box.hidden = false;
}

function applyLang() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = T(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = T(el.dataset.i18nPh); });
  $("lang").textContent = "🌐 " + T("lang_toggle");
}

function render() {
  const all = state.data.tenders;
  renderSections();
  document.querySelectorAll("#tabs button").forEach((b) => {
    const n = b.dataset.tab === "personal"
      ? all.filter((t) => t.status === "active" && t.personal?.length).length
      : all.filter((t) => inTab(t, b.dataset.tab)).length;
    b.innerHTML = esc(T(b.dataset.i18n)) + ` <span class="n">${n}</span>`;
    b.classList.toggle("active", b.dataset.tab === state.tab);
  });
  renderBriefing();
  if (state.tab === "picks") {
    $("count").textContent = "";
    $("list").innerHTML = "";
    $("more").hidden = true;
    return;
  }
  const list = sorted(all.filter((t) => inTab(t, state.tab) && matchesFilters(t)));
  $("count").textContent = list.length === 1 ? T("tender") : T("tenders", { n: list.length });
  $("list").innerHTML = list.length
    ? list.slice(0, state.shown).map(card).join("")
    : `<div class="empty">${T("empty")}${state.tab === "new" ? T("empty_new") : ""}.</div>`;
  $("more").hidden = list.length <= state.shown;
}

function showDetail(id) {
  const t = state.data.tenders.find((x) => x.id === id);
  if (!t) return;
  const a = t.analysis || {};
  const rows = Object.entries(t.detail || {}).map(([k, v]) => {
    let val = Array.isArray(v) ? v.join(", ") : MONEY.has(k) ? inr(v) : DATES.has(k) ? fmtDate(v) : v;
    const label = (state.lang === "hi" && LABELS_HI[k]) || LABELS[k] || k;
    return `<tr><td>${esc(label)}</td><td>${esc(val)}</td></tr>`;
  }).join("");
  const list = (items) => (items?.length ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "");
  const changes = (t.changes || []).map((c) => `<li>${fmtDate(c.date)}: ${esc(c.fields.join(", ") || T("details_changed"))}</li>`).join("");
  const blockers = state.lang === "hi" && a.blockers_hi?.length ? a.blockers_hi : a.blockers;
  const translate = `https://translate.google.com/?sl=en&tl=hi&op=translate&text=${encodeURIComponent(t.title || "")}`;
  $("dlg-body").dataset.id = id;
  const docs = [...(t.detail?.nit_documents || []), ...(t.detail?.work_documents || [])];
  $("dlg-body").innerHTML = `
    <button class="close" onclick="document.getElementById('dlg').close()">${T("close")}</button>
    <div class="badges">${a.decision ? `<span class="badge ${a.decision}">${decisionText(a.decision)} · ${a.relevance ?? "-"}</span>` : ""}
      ${a.sector ? `<span class="badge">${esc(a.sector)}</span>` : ""}${a.work_type ? `<span class="badge">${esc(a.work_type)}</span>` : ""}</div>
    <h2>${esc(t.title)}</h2>
    ${state.lang === "hi" ? `<p class="meta"><a href="${translate}" target="_blank" rel="noopener">${T("translate_title")}</a></p>` : ""}
    <div class="meta"><span>${esc(t.org_chain)}</span></div>
    <div class="actions">
      ${portalButton(t)}
      <button class="secondary" onclick="navigator.clipboard.writeText('${esc(t.id)}');this.textContent='${T("copied")} ${esc(t.id)}'">${T("copy_id")}</button>
      <button class="secondary" onclick="navigator.clipboard.writeText(location.origin+location.pathname+'?id=${esc(t.id)}');this.textContent='${T("link_copied")}'">${T("copy_link")}</button>
    </div>
    <div class="box how">
      <h4>${T("how_open")}</h4>
      ${portalSteps(t)}
      ${docs.length ? `<b>${T("docs")}</b><ul>${docs.map((f) => `<li>📄 ${esc(f)}</li>`).join("")}</ul><p class="meta">${T("docs_note")}</p>` : ""}
    </div>
    <div class="box">
      <h4>${a.source === "llm" ? T("ai_analysis") : T("rule_analysis")}</h4>
      ${a.summary ? `<p>${esc(pickLang(a.summary, a.summary_hi))}</p>` : ""}
      ${a.reason ? `<p><b>${T("why")}:</b> ${esc(pickLang(a.reason, a.reason_hi))}</p>` : ""}
      ${a.upfront_cost_inr != null ? `<p><b>${T("cash_to_bid")}:</b> ₹${Number(a.upfront_cost_inr).toLocaleString("en-IN")}</p>` : ""}
      ${blockers?.length ? `<b>${T("blockers")}</b>${list(blockers)}` : ""}
      ${a.key_requirements?.length ? `<b>${T("key_req")}</b>${list(a.key_requirements)}` : ""}
      ${a.risk_flags?.length ? `<b>${T("risk_flags")}</b>${list(a.risk_flags)}` : ""}
      ${a.model ? `<p class="meta">${T("model")}: ${esc(a.model)} · ${fmtDate(a.analysed_at)}${a.basis === "listing" ? " · " + T("listing_only") : ""}</p>` : ""}
    </div>
    ${hasDetail(t) ? "" : `<p class="warn">${T("no_detail")}</p>`}
    <table class="kv">
      <tr><td>${T("tender_id")}</td><td>${esc(t.id)}</td></tr>
      ${t.ref_no ? `<tr><td>${T("ref_no")}</td><td>${esc(t.ref_no)}</td></tr>` : ""}
      <tr><td>${T("bid_closes")}</td><td><b>${fmtDate(t.closing)}</b></td></tr>
      <tr><td>${T("bid_opening")}</td><td>${fmtDate(t.opening)}</td></tr>
      <tr><td>${T("first_seen")}</td><td>${fmtDate(t.first_seen)}</td></tr>
      ${t.related?.length ? `<tr><td>${T("other_lots")}</td><td>${esc(t.related.join(", "))}</td></tr>` : ""}
      ${rows}
    </table>
    ${changes ? `<div class="box"><h4>${T("changes")}</h4><ul>${changes}</ul></div>` : ""}
`;
  if (!$("dlg").open) $("dlg").showModal();
}

function fillSelect(id, values) {
  const sel = $(id);
  [...new Set(values.filter(Boolean))].sort().forEach((v) => sel.insertAdjacentHTML("beforeend", `<option>${esc(v)}</option>`));
}

function renderHeader() {
  const d = state.data;
  const run = d.run || {};
  const an = run.analysis || {};
  $("runinfo").textContent = an.llm_pending ? T("llm_pending", { n: an.llm_pending }) : "";
  const active = d.tenders.filter((t) => t.status === "active");
  const stat = (n, label) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`;
  $("stats").innerHTML = [
    stat(active.length, T("st_active")),
    stat(active.filter(isNew).length, T("st_new")),
    stat(active.filter((t) => t.analysis?.decision === "worth_reading").length, T("st_worth")),
    stat(active.filter((t) => { const x = daysLeft(t); return x != null && x >= 0 && x <= 3; }).length, T("st_closing")),
    stat(inr(active.reduce((s, t) => s + (t.value || 0), 0)), T("st_value")),
  ].join("") + (run.status && run.status !== "ok" ? `<div class="warn">${T("last_run_problem", { e: esc(run.error || run.status) })}</div>` : "");
}

function renderAll() {
  applyLang();
  renderHeader();
  renderDistricts();
  render();
  const open = $("dlg").open && $("dlg-body").dataset.id;
  if (open) showDetail(open);
}

async function init() {
  applyLang();
  const res = await fetch("data.json", { cache: "no-store" });
  state.data = await res.json();
  const d = state.data;
  state.latestDay = (d.generated_at || "").slice(0, 10);
  document.title = d.title;
  $("title").textContent = d.title;
  $("updated").textContent = fmtDate(d.generated_at) + " IST";
  $("portal").textContent = d.portal.name;
  $("portal").href = d.portal.url;
  const active = d.tenders.filter((t) => t.status === "active");

  fillSelect("f-org", d.tenders.map((t) => t.org));
  fillSelect("f-sector", d.tenders.map((t) => t.analysis?.sector));
  if (d.briefing?.picks?.length) state.tab = "picks";
  else if (!active.some(isNew)) state.tab = "worth";
  $("lang").addEventListener("click", () => {
    state.lang = state.lang === "hi" ? "en" : "hi";
    localStorage.setItem("lang", state.lang);
    renderAll();
  });
  $("briefing").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-id]");
    if (a) { e.preventDefault(); showDetail(a.dataset.id); return; }
    const s = e.target.closest("button[data-section]");
    if (s) openSection(s.dataset.section);
  });
  $("sections").addEventListener("click", (e) => {
    const s = e.target.closest("button[data-section]");
    if (s) { state.section = s.dataset.section; state.shown = PAGE; render(); }
  });
  const params = new URLSearchParams(location.search);
  if (params.get("section")) { state.tab = "personal"; state.section = params.get("section"); }

  $("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state.tab = b.dataset.tab; state.shown = PAGE; render();
  });
  ["q", "f-district", "f-org", "f-sector", "f-decision", "f-value", "sort"].forEach((id) =>
    $(id).addEventListener("input", () => { state.shown = PAGE; render(); }));
  $("f-district").addEventListener("input", () => localStorage.setItem("district", $("f-district").value));
  $("more").addEventListener("click", () => { state.shown += PAGE; render(); });
  $("list").addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    const c = e.target.closest(".card");
    if (c) showDetail(c.dataset.id);
  });
  document.addEventListener("click", (e) => {
    const a = e.target.closest?.("a.portal");
    if (a) navigator.clipboard?.writeText(a.dataset.copy).catch(() => {});
  });
  renderAll();
  const linked = new URLSearchParams(location.search).get("id");
  if (linked) showDetail(linked);
}

init().catch((err) => { $("list").innerHTML = `<div class="empty">${T("load_error", { e: esc(err.message) })}</div>`; });
