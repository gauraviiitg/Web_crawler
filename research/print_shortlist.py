import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
s = json.load(open("research/shortlist.json", encoding="utf-8"))
for i, r in enumerate(s):
    v = "NA" if r["value"] is None else f"{r['value'] / 1e5:.1f}L"
    j = "J" if r["jaipur"] else " "
    x = "x" if r["emd_exempt"] else " "
    print(f"{i:3} {j} {r['id']:24} {r['cat'][:4]} v={v:>7} emd={r['emd'] or 0:>7.0f}{x} fee={r['fee']:>5.0f} "
          f"d={r['days']:4.0f} {r['loc'][:14]:14} | {r['org'][:22]:22} | {(r['title'] or '')[:90]} | {r['product'][:24]}")
