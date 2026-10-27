import html
import re
import sys

s = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
t = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
t = re.sub(r"<[^>]+>", "|", t)
t = html.unescape(re.sub(r"\s+", " ", t))
t = re.sub(r"(\|\s*)+", "|", t)
print(t[: int(sys.argv[2]) if len(sys.argv) > 2 else 6000])
print("\nLINKS:")
for m in sorted(set(re.findall(r'href="([^"]+)"', s)))[:120]:
    print(html.unescape(m))
print("\nFORMS:")
for m in re.findall(r"<form[^>]*>", s):
    print(m)
for m in re.findall(r"<input[^>]*>", s)[:40]:
    print(m)
