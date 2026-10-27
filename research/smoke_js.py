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
    addEventListener(ev, fn) { handlers[id + ":" + ev] = fn; },
    insertAdjacentHTML(_, h) { this.innerHTML += h; }, showModal() { this.open = true; }, close() { this.open = false; } };
  return els[id];
}
var tabs = ["new","worth","personal","closing","updated","all","closed"].map((t) => ({ dataset: { tab: t, i18n: "tab_" + t }, innerHTML: "", classList: { toggle() {} } }));
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
    out = {}
    for lang in ("en", "hi"):
        if lang == "hi":
            ctx.eval("handlers['lang:click']()")
            ctx.eval("handlers['briefing:click']({ target: { closest: (s) => s.startsWith('button') ? { dataset: { section: 'photocopy' } } : null } })")
        out[lang] = json.loads(ctx.eval("""JSON.stringify({
          briefing: els.briefing.innerHTML.length, hidden: els.briefing.hidden,
          list: els.list.innerHTML.length, count: els.count.textContent, stats: els.stats.innerHTML.slice(0, 120),
          dialog: els['dlg-body'].innerHTML.length, dlgOpen: els.dlg.open, tab0: tabs[0].innerHTML,
          personalTab: tabs[2].innerHTML, sections: els.sections.innerHTML, sectionsHidden: els.sections.hidden,
          portalLinks: (els.list.innerHTML.match(/class="portal/g) || []).length + (els.briefing.innerHTML.match(/class="portal/g) || []).length,
          howOpen: els['dlg-body'].innerHTML.includes('class="box how"'),
          firstCard: els.list.innerHTML.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').slice(0, 200),
          head: els.briefing.innerHTML.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').slice(0, 260)})"""))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    ok = all(v["briefing"] > 500 and not v["hidden"] and v["list"] > 500 and v["dialog"] > 500 for v in out.values())
    print("SMOKE OK" if ok else "SMOKE FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
