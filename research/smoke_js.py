"""Run web/app.js in V8 with a stub DOM against site/data.json (English, then Hindi)."""
import json
import sys
from pathlib import Path

from py_mini_racer import MiniRacer

ROOT = Path(__file__).resolve().parents[1]
data = (ROOT / "site/data.json").read_text(encoding="utf-8")
app = (ROOT / "web/app.js").read_text(encoding="utf-8")

STUB = r"""
var els = {}, store = {}, handlers = {};
function el(id) {
  if (!els[id]) els[id] = { id, innerHTML: "", textContent: "", hidden: false, value: "", dataset: {}, open: false,
    placeholder: "", href: "", classList: { toggle() {} },
    addEventListener(ev, fn) { const k = id + ":" + ev, prev = handlers[k]; handlers[k] = prev ? (e) => { prev(e); fn(e); } : fn; },
    insertAdjacentHTML(_, h) { this.innerHTML += h; }, showModal() { this.open = true; }, close() { this.open = false; } };
  return els[id];
}
var tabs = ["picks","new","worth","personal","closing","updated","all","closed"].map((t) => ({ dataset: { tab: t, i18n: "tab_" + t }, innerHTML: "", classList: { toggle() {} } }));
var document = { documentElement: {}, title: "", getElementById: el, addEventListener(ev, fn) { handlers["document:" + ev] = fn; },
  querySelectorAll(sel) { return sel === "#tabs button" ? tabs : []; } };
var localStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } };
var location = { search: "?id=2026_DLB_604082_1", origin: "https://x", pathname: "/" };
var navigator = { clipboard: { writeText() {} } };
class URLSearchParams { constructor(s) { this.m = Object.fromEntries(s.replace(/^\?/, "").split("&").map((p) => p.split("="))); } get(k) { return this.m[k] ?? null; } }
var fetch = () => Promise.resolve({ json: () => Promise.resolve(DATA) });
"""


def main() -> int:
    ctx = MiniRacer()
    ctx.eval("var DATA = " + data + ";" + STUB)
    ctx.eval(app)
    ctx.eval("1")  # let promises settle
    picks = lambda: ctx.eval("(els.briefing.innerHTML.match(/class=\"pick\"/g) || []).length")
    all_picks = picks()
    ctx.eval("els['f-district'].value = 'Jaipur'; handlers['f-district:input']()")
    jaipur_picks, saved = picks(), ctx.eval("store.district")
    ctx.eval("els['f-district'].value = ''; handlers['f-district:input']()")
    print(f"picks: all={all_picks} jaipur={jaipur_picks} saved={saved!r}")
    print("district options:", ctx.eval("els['f-district'].innerHTML.replace(/<[^>]+>/g, '|').slice(0, 200)"))
    out = {}
    for lang in ("en", "hi"):
        if lang == "hi":
            ctx.eval("handlers['lang:click']()")
            ctx.eval("handlers['briefing:click']({ target: { closest: (s) => s.startsWith('button') ? { dataset: { section: 'photocopy' } } : null } })")
        out[lang] = json.loads(ctx.eval("""JSON.stringify({
          briefing: els.briefing.innerHTML.length, hidden: els.briefing.hidden,
          list: els.list.innerHTML.length, count: els.count.textContent, stats: els.stats.innerHTML.slice(0, 120),
          dialog: els['dlg-body'].innerHTML.length, dlgOpen: els.dlg.open, tab0: tabs[0].innerHTML,
          personalTab: tabs[3].innerHTML, sections: els.sections.innerHTML, sectionsHidden: els.sections.hidden,
          portalLinks: (els.list.innerHTML.match(/class="portal/g) || []).length + (els.briefing.innerHTML.match(/class="portal/g) || []).length,
          howOpen: els['dlg-body'].innerHTML.includes('class="box how"'),
          firstCard: els.list.innerHTML.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').slice(0, 200),
          head: els.briefing.innerHTML.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').slice(0, 260)})"""))
    ctx.eval("els['f-source'].value = 'gem'; tabs[0].dataset.tab; handlers['tabs:click']({ target: { closest: () => ({ dataset: { tab: 'all' } }) } }); handlers['f-source:input']()")
    gem = json.loads(ctx.eval("""JSON.stringify({ count: els.count.textContent,
      pdfLinks: (els.list.innerHTML.match(/class="portal pdf/g) || []).length,
      eprocCards: (els.list.innerHTML.match(/Open tender on portal|पोर्टल पर टेंडर खोलें/g) || []).length,
      sources: els['f-source'].innerHTML.replace(/<[^>]+>/g, '|') })"""))
    print("gem filter:", gem)
    print(json.dumps(out, ensure_ascii=True, indent=1))
    en, hi = out["en"], out["hi"]
    ok = (all_picks > 0 and saved == "Jaipur" and en["briefing"] > 500 and not en["hidden"] and en["list"] == 0
          and hi["hidden"] and hi["list"] > 500 and all(v["dialog"] > 500 for v in out.values())
          and (gem["pdfLinks"] > 0 and gem["eprocCards"] == 0 if "GeM" in gem["sources"] and "(0)" not in gem["sources"] else True))
    print("SMOKE OK" if ok else "SMOKE FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
