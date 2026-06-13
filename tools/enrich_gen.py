"""Generate the 4 index.html enrichment blocks (ORDER/COLORS/COORDS/TAGS) for
new courses, so adding a batch is copy-paste. Edit SPEC below and run:
    py tools/enrich_gen.py
Each SPEC row: (exact_course_name, [nominatim_queries_best_first], [landschap], hoogte)
- name MUST exactly match the `course`/`course_name` the scraper emits.
- geocode tries each query in order (named-golf query usually fails -> town centroid is fine for distance buckets).
- colors are auto-spread on the HSL wheel; tweak HUE_OFFSET if they clash with existing.
Tagging rule: default polder/plat. glooiend/heuvelachtig ONLY for real high ground
(Veluwe, Utrechtse Heuvelrug, Nijmegen/Groesbeek & Zuid-Limburg hills, Sallandse
Heuvelrug, Twente, 't Gooi). landschap: parkland->polder, tree-lined/estate->bos,
coastal->duinen, heath->heide. See memory tee-times-tag-validation for AHN method.
"""
import time, colorsys, httpx

HUE_OFFSET = 18
SPEC = [
    # ("Example", ["Golfclub Example, Town", "Town"], ["polder"], "plat"),
]

c = httpx.Client(timeout=20, headers={"User-Agent": "tee-times-nl/1.0 (luit94@hotmail.com)"})
def hexc(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360, l, s); return "#%02x%02x%02x" % (int(r*255), int(g*255), int(b*255))
def w(n): return f'"{n}":'.ljust(28)

coords = {}
for name, qs, _, _ in SPEC:
    for q in qs:
        j = c.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1, "countrycodes": "nl"}).json()
        time.sleep(1.1)
        if j:
            coords[name] = (float(j[0]["lat"]), float(j[0]["lon"]), q); break
    else:
        print(f"# !! NO GEOCODE: {name}")

print("=== ORDER ==="); print("    " + ", ".join(f'"{s[0]}"' for s in SPEC) + ",")
print("=== COLORS ===")
for i, s in enumerate(SPEC):
    h = (i * 360 / max(1, len(SPEC)) + HUE_OFFSET) % 360
    print(f'    {w(s[0])} {{ main: "{hexc(h,0.6,0.28)}", sub: "{hexc(h,0.55,0.42)}" }},')
print("=== COORDS ===")
for s in SPEC:
    if s[0] in coords:
        la, lo, q = coords[s[0]]; print(f'    {w(s[0])} {{ lat: {la:.5f}, lon: {lo:.5f} }},   # {q}')
print("=== TAGS ===")
for s in SPEC:
    ls = ", ".join(f'"{x}"' for x in s[2])
    print(f'    {w(s[0])} {{ landschap: [{ls}],{"":<{max(0,18-len(ls))}} hoogte: "{s[3]}" }},')
