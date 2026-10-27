const PAGE = 40;
const state = { data: null, tab: "new", shown: PAGE, latestDay: "" };
const $ = (id) => document.getElementById(id);

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
const DECISION_TEXT = { worth_reading: "Worth reading", maybe: "Maybe", skip: "Skip" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function inr(n) {
  if (n == null) return "Not disclosed";
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
    case "new": return t.status === "active" && isNew(t);
    case "worth": return t.status === "active" && t.analysis?.decision === "worth_reading";
    case "closing": return t.status === "active" && dl != null && dl >= 0 && dl <= 3;
    case "updated": return t.status === "active" && t.changes?.length > 0;
    case "closed": return t.status !== "active";
    default: return t.status === "active";
  }
}

function matchesFilters(t) {
  const q = $("q").value.trim().toLowerCase();
  if (q) {
    const hay = [t.id, t.title, t.org_chain, t.location, t.analysis?.summary, t.analysis?.sector, ...(t.analysis?.tags || [])].join(" ").toLowerCase();
    if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
  }
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
  if (a.decision) badges.push(`<span class="badge ${a.decision}">${DECISION_TEXT[a.decision] || a.decision}${a.relevance != null ? " · " + a.relevance : ""}</span>`);
  if (isNew(t)) badges.push(`<span class="badge new">NEW</span>`);
  if (isUpdated(t)) badges.push(`<span class="badge upd">UPDATED</span>`);
  if (t.status === "active" && dl != null && dl <= 3) badges.push(`<span class="badge urgent">${dl < 1 ? "Closes today" : "Closes in " + Math.ceil(dl) + " days"}</span>`);
  if (t.status !== "active") badges.push(`<span class="badge">${esc(t.status)}</span>`);
  if (a.sector) badges.push(`<span class="badge">${esc(a.sector)}</span>`);
  if (a.work_type) badges.push(`<span class="badge">${esc(a.work_type)}</span>`);
  (a.risk_flags || []).slice(0, 3).forEach((f) => badges.push(`<span class="badge flag">${esc(f)}</span>`));
  if (a.source === "rules") badges.push(`<span class="badge rules" title="AI analysis pending; keyword rules used">rule-based</span>`);
  return `<article class="card" data-id="${esc(t.id)}">
    <div class="badges">${badges.join("")}</div>
    <h3>${esc(t.title)}</h3>
    <div class="meta">
      <span>${esc(t.org)}</span><span>${esc(t.id)}</span>
      ${hasDetail(t) ? `<span>Value: <span class="money">${inr(t.value)}</span></span><span>EMD: ${inr(t.emd)}</span>` : `<span>Value/EMD: details pending</span>`}
      <span>Closes: <b>${fmtDate(t.closing)}</b></span>
      ${t.location ? `<span>📍 ${esc(t.location)}</span>` : ""}
    </div>
    ${a.summary && a.source === "llm" ? `<p class="summary">${esc(a.summary)}</p>` : ""}
  </article>`;
}

function render() {
  const all = state.data.tenders;
  document.querySelectorAll("#tabs button").forEach((b) => {
    const n = all.filter((t) => inTab(t, b.dataset.tab)).length;
    b.innerHTML = b.textContent.replace(/\s*\d+$/, "") + ` <span class="n">${n}</span>`;
    b.classList.toggle("active", b.dataset.tab === state.tab);
  });
  const list = sorted(all.filter((t) => inTab(t, state.tab) && matchesFilters(t)));
  $("count").textContent = `${list.length} tender${list.length === 1 ? "" : "s"}`;
  $("list").innerHTML = list.length
    ? list.slice(0, state.shown).map(card).join("")
    : `<div class="empty">No tenders here${state.tab === "new" ? " today — nothing new was published since the last run" : ""}.</div>`;
  $("more").hidden = list.length <= state.shown;
}

function showDetail(id) {
  const t = state.data.tenders.find((x) => x.id === id);
  if (!t) return;
  const a = t.analysis || {};
  const rows = Object.entries(t.detail || {}).map(([k, v]) => {
    let val = Array.isArray(v) ? v.join(", ") : MONEY.has(k) ? inr(v) : DATES.has(k) ? fmtDate(v) : v;
    return `<tr><td>${esc(LABELS[k] || k)}</td><td>${esc(val)}</td></tr>`;
  }).join("");
  const list = (items) => (items?.length ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "");
  const changes = (t.changes || []).map((c) => `<li>${fmtDate(c.date)}: ${esc(c.fields.join(", ") || "details changed")}</li>`).join("");
  $("dlg-body").innerHTML = `
    <button class="close" onclick="document.getElementById('dlg').close()">Close</button>
    <div class="badges">${a.decision ? `<span class="badge ${a.decision}">${DECISION_TEXT[a.decision]} · relevance ${a.relevance ?? "-"}</span>` : ""}
      ${a.sector ? `<span class="badge">${esc(a.sector)}</span>` : ""}${a.work_type ? `<span class="badge">${esc(a.work_type)}</span>` : ""}</div>
    <h2>${esc(t.title)}</h2>
    <div class="meta"><span>${esc(t.org_chain)}</span></div>
    <div class="actions">
      <a href="${esc(state.data.portal.url)}" target="_blank" rel="noopener">Open portal</a>
      <button class="secondary" onclick="navigator.clipboard.writeText('${esc(t.id)}');this.textContent='Copied ${esc(t.id)}'">Copy Tender ID</button>
    </div>
    <div class="box">
      <h4>${a.source === "llm" ? "AI analysis" : "Rule-based analysis (AI analysis pending)"}</h4>
      ${a.summary ? `<p>${esc(a.summary)}</p>` : ""}
      ${a.reason ? `<p><b>Why:</b> ${esc(a.reason)}</p>` : ""}
      ${a.upfront_cost_inr != null ? `<p><b>Cash to bid (startup/MSE, excl. stock):</b> ₹${Number(a.upfront_cost_inr).toLocaleString("en-IN")}</p>` : ""}
      ${a.blockers?.length ? `<b>Blockers</b>${list(a.blockers)}` : ""}
      ${a.key_requirements?.length ? `<b>Key requirements</b>${list(a.key_requirements)}` : ""}
      ${a.risk_flags?.length ? `<b>Risk flags</b>${list(a.risk_flags)}` : ""}
      ${a.model ? `<p class="meta">Model: ${esc(a.model)} · ${fmtDate(a.analysed_at)}${a.basis === "listing" ? " · based on listing only" : ""}</p>` : ""}
    </div>
    ${hasDetail(t) ? "" : `<p class="warn">Full tender details (value, EMD, eligibility) could not be fetched yet; the crawler retries on the next run.</p>`}
    <table class="kv">
      <tr><td>Tender ID</td><td>${esc(t.id)}</td></tr>
      ${t.ref_no ? `<tr><td>Reference no.</td><td>${esc(t.ref_no)}</td></tr>` : ""}
      <tr><td>Bid submission closes</td><td><b>${fmtDate(t.closing)}</b></td></tr>
      <tr><td>Bid opening</td><td>${fmtDate(t.opening)}</td></tr>
      <tr><td>First seen by crawler</td><td>${fmtDate(t.first_seen)}</td></tr>
      ${t.related?.length ? `<tr><td>Other lots under the same tender number</td><td>${esc(t.related.join(", "))}</td></tr>` : ""}
      ${rows}
    </table>
    ${changes ? `<div class="box"><h4>Changes detected (corrigendum)</h4><ul>${changes}</ul></div>` : ""}
    <p class="meta">To open this tender: Open portal → Search → paste the Tender ID. Documents (PDF/BOQ) are downloaded on the portal.</p>`;
  $("dlg").showModal();
}

function fillSelect(id, values) {
  const sel = $(id);
  [...new Set(values.filter(Boolean))].sort().forEach((v) => sel.insertAdjacentHTML("beforeend", `<option>${esc(v)}</option>`));
}

async function init() {
  const res = await fetch("data.json", { cache: "no-store" });
  state.data = await res.json();
  const d = state.data;
  state.latestDay = (d.generated_at || "").slice(0, 10);
  document.title = d.title;
  $("title").textContent = d.title;
  $("updated").textContent = fmtDate(d.generated_at) + " IST";
  $("portal").textContent = d.portal.name;
  $("portal").href = d.portal.url;
  const run = d.run || {};
  const an = run.analysis || {};
  $("runinfo").textContent = an.llm_pending ? `AI analysis pending for ${an.llm_pending} tenders (free-tier limit; continues next run)` : "";

  const active = d.tenders.filter((t) => t.status === "active");
  const stat = (n, label) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`;
  $("stats").innerHTML = [
    stat(active.length, "Active tenders"),
    stat(active.filter(isNew).length, "New today"),
    stat(active.filter((t) => t.analysis?.decision === "worth_reading").length, "Worth reading"),
    stat(active.filter((t) => { const x = daysLeft(t); return x != null && x >= 0 && x <= 3; }).length, "Closing in 3 days"),
    stat(inr(active.reduce((s, t) => s + (t.value || 0), 0)), "Total disclosed value"),
  ].join("") + (run.status && run.status !== "ok" ? `<div class="warn">Last run problem: ${esc(run.error || run.status)} — showing previous data.</div>` : "");

  fillSelect("f-org", d.tenders.map((t) => t.org));
  fillSelect("f-sector", d.tenders.map((t) => t.analysis?.sector));
  if (!active.some(isNew)) state.tab = "worth";

  $("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state.tab = b.dataset.tab; state.shown = PAGE; render();
  });
  ["q", "f-org", "f-sector", "f-decision", "f-value", "sort"].forEach((id) =>
    $(id).addEventListener("input", () => { state.shown = PAGE; render(); }));
  $("more").addEventListener("click", () => { state.shown += PAGE; render(); });
  $("list").addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) showDetail(c.dataset.id); });
  render();
}

init().catch((err) => { $("list").innerHTML = `<div class="empty">Could not load data: ${esc(err.message)}</div>`; });
