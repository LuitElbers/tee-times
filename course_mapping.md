# Tee Times — Phase 1 Course→Backend Mapping (working doc)

Status as of 2026-06-10. Goal: add as many NL public courses as possible (18-hole + notable 9-hole, publicly viewable tee times only).

## Regions DONE
Noord-Holland, Zuid-Holland, Zeeland, Utrecht, Flevoland, Noord-Brabant. Plus Phase-0 sample courses in other regions.

## Regions REMAINING to map
Gelderland, Overijssel, Limburg, Groningen, Friesland, Drenthe (each has partial coverage from the Phase-0 sample, listed at bottom).

## Province facility counts (completeness tracker; all-facility count, in-scope ≈ half)
NH 37 ✓ · ZH 42 ✓ · Zeeland 8 ✓ · Utrecht 22 ✓ · Flevoland 11 ✓ · Brabant 49 ✓ · Gelderland 35 ☐ · Overijssel 19 ☐ · Limburg 24 ☐ · Groningen 7 ☐ · Friesland 11 ☐ · Drenthe 14 ☐. Total ≈279 (NGF); ~195 publicly playable.

---

## ADD-COURSE STATUS & ROADMAP (updated 2026-06-11, session 2)

### DONE & deployed
- **intogolf +13, teecontrol +16** added, enriched (coords/colors/order/tags), per-backend 8s timeout in main.py, committed + pushed. See [[project-tee-times]]. Tags are geography-guesses pending validation — see [[tee-times-tag-validation]].
- **(session 3, 2026-06-11) hollandschegolfclub +12** (Westerpark + the whole BurgGolf/HGC cluster) added via `location_id` — see the BIG WIN note below. App now 54 courses. Info tab removed; "Gemaakt door Luit Elbers" credit added (main page + Banen modal).
- **(2026-06-13) Phase 1 — all mapped courses on existing scrapers DONE, +36 → 90 courses, pushed (HEAD 1021187).** Done via 3 parallel background subagents (one scraper each, no index.html edits; main enriched centrally). Per backend:
  - **teecontrol +3:** Tespelduyn=`golfbaantespelduyn`, Edese=`egcp`, De Compagnie=`gcdecompagnie` (the previously-401'd subdomains — found from booking pages). **Havelte left teecontrol → nexxchange.**
  - **hetrijk +3:** Nijmegen=RvN(SiteId 2), Sybrook=RvS(4), Margraten=RvM(3). Scraper generalized to a SITES list.
  - **egolf4u +20:** scraper generalized to full `host` + `noverify`; correct host form is `<sub>.teetime.e-golf4u.nl`. DROPPED Capelle (=Asparagi crsNr=71), Amelisweerd/Welschap (no grid), Eindhovensche (private).
  - **nexxchange +10:** reworked request — DROP `sortIndex`, add `hx-request` header + session-cookie GET, resolve `facetId` by hole-label per date, Semaphore(3). DROPPED Almeerderhout/Kleiburg/Tongelreep (no public sheet), Ookmeer/Old Course Loenen (gated).
  - All 36 tags are geography-guesses → [[tee-times-tag-validation]]. PERF: watch fan-out at 90+ (8s per-backend timeout caps response).

### BIG WIN — hollandschegolfclub.nl portal serves the ENTIRE BurgGolf/HGC cluster (cheapest adds available)
The existing `scrapers/hollandschegolfclub.py` hits one WordPress AJAX endpoint (`itg_get_teetimes`) keyed by `location_id`. That ONE portal exposes the whole BurgGolf/Hollandsche Golfclub group. Adding a course = **ONE line** `{"id": <location_id>, "name": "..."}` in `LOCATIONS` + standard enrichment. No new scraper, no per-club host hunting.
- **Enumerate location_ids** (do this once to find any remaining ones):
  `curl -s https://www.hollandschegolfclub.nl/boek-een-starttijd/ | tr '\n' ' '` then grep the `<select id="itg-location">` block for `value="NN" ... >Name`.
- Added s3: Westerpark(154), De Haverleij(151), Gendersteyn(157), Almkreek(107), De Kurenpolder(148), Reymerswael(159), De Berendonck(155), De Breuninkhof(104), Land van Thorn(158), Sint Nyk(156), Rotterdam→"BurgGolf Rotterdam"(152), Shortgolf Utrecht(149, par-3 only).
- **International Golf Maastricht(161) NOT added** — in the dropdown but `itg_get_teetimes` returns an empty course list on every date/holes/period (no public greenfee teetimes). Always-probe-before-add; drop always-empty courses.
- This **supersedes the old "intogolf BurgGolf cluster" row** below — that cluster is hollandschegolfclub, not intogolf.

### REMAINING — addable NOW with existing scrapers (~47 courses)
| Scraper | #  | What's needed | Cost (vs 1 session-to-cap) |
|---|---|---|---|
| egolf4u | ~24 | add host + **enumerate baan-ids per club** (fetch booking page, parse baan dropdown for id/holes/par3). White-label hosts (Texelse, Vught, Dommel, Riel) = TLS/host quirks | HIGH ~0.7–1 |
| nexxchange | ~12 | probe `facet_id` + `courseId` per course (scriptable). Excl. Ookmeer (login), Old Course Loenen (member-gated) | MED ~0.4 |
| hetrijk | 3 | extend scraper by SITECODE: Het Rijk van Nijmegen, Sybrook, Margraten | LOW ~0.15 |
| teecontrol | 4 | find correct subdomains (these 401'd): Tespelduyn, Edese, Havelte, De Compagnie | LOW ~0.1 |
| ~~intogolf BurgGolf cluster~~ | — | **RESOLVED & DONE in s3** — it's hollandschegolfclub `location_id`, not intogolf. See BIG WIN note above. | — |

### REMAINING — new scrapers needed (~6 courses)
| Scraper | # | Notes | Cost |
|---|---|---|---|
| **Asparagi / ikgagolfen** | many | **HIGH-VALUE** new scraper — parse the public `teetimes.asp?exclusiveCrsNr=NNN` HTML grid. Confirmed: Ockenburgh(908), Delfland. Shared NGF portal → enumerate crsNr to unlock a big batch. User deferred s3 but flagged worth building. | MED ~0.4–0.6 |
| chronogolf (Lightspeed) | 4 | new scraper; Weesp, Hoogland Amersfoort, Dongen, Roosendaal | MED–HIGH ~0.5–0.7 |
| Bernardus (custom wp-json) | 1 | bespoke scraper, high-end course | LOW–MED ~0.2 |
| cps (eu.cps.golf) | 1 | Dorhout Mees — poor ROI, **defer/skip** | MED ~0.3 |
| birdy | 2 | app-only; check for public endpoint, **likely exclude** | LOW ~0.1 |

### REMAINING — 6 regions NOT yet mapped (~55 in-scope courses)
Gelderland, Overijssel, Limburg, Groningen, Friesland, Drenthe. Enumerate + detect backend first (method in this doc); most then add via existing scrapers. Cost HIGH ~1+ (its own session).

### SUGGESTED ORDER (best courses-per-budget first)
1. teecontrol 4 + hetrijk 3 (~0.25, +7, low-risk) ← recommended next (intogolf BurgGolf 4 now DONE as hollandschegolfclub). Also cheap: any remaining hollandschegolfclub location_ids if the dropdown grows.
2. nexxchange ~12 (~0.4)
3. egolf4u ~24 (own session)
4. chronogolf + Bernardus (+5)
5. map the 6 regions, then bulk-add

### "ADD A COURSE" CHECKLIST (today's steps — keep mechanical)
1. Add config entry to the scraper: **hollandschegolfclub = `{"id": <location_id>, "name": "..."}` in LOCATIONS (BurgGolf/HGC cluster — cheapest, see BIG WIN note)**; teecontrol = `{origin,course_name,booking_url}`; intogolf = `{api_url=<sub>.baan.intogolf.nl/api/igg, course_name, booking_url}`; egolf4u = `{subdomain, name, baans:[{baan,sub,holes,is_par3}]}`; nexxchange = `{slug,name,is_par3,booking_url,facets:[{facet_id,holes}]}`; hetrijk = SITECODE.
2. Enrich in `public/index.html`: COURSE_COORDS, COURSE_COLORS, COURSE_ORDER, COURSE_TAGS. **GOTCHA: the key string in all 4 maps must EXACTLY equal the `name`/`course_name` the scraper emits (case + spacing).** Caught a "ShortGolf" vs "Shortgolf" mismatch this way. Coords: Nominatim **named-golf queries usually fail (return empty) → use the TOWN name** (centroid is fine for distance buckets); rate-limit ~1.2s between calls, set a User-Agent. Colors: any distinct HSL pair. Tags: geography rule (default plat/polder).
3. **FUTURE (after user-settings/course-select UI ships): also register the course in whatever new course-list/settings structure that task introduces — check how it stores the canonical course list so adds stay one place.** (Banen-select UI already exists, auto-includes new courses via the `excludedCourses` localStorage exclusion model — no migration needed.)
4. Validate (these exact commands worked s3):
   - Map consistency + JS parse: `node -e` — extract the largest `<script>`, `new Function(it)`, then assert COURSE_ORDER/COLORS(`{ main:`)/COORDS(`{ lat:`)/TAGS(`{ landschap:`) key sets are identical. Catches missing/orphan keys.
   - Scraper end-to-end: `py -c` importing the scraper's `fetch_tee_times`, run for a near date, `Counter(t.course ...)`, print slots/course. A new course with 0 slots → check it isn't par-3-only (those show 0 unless `include_par3=True`) or always-empty (drop it).
   - Test 2-3 clubs at a time — do NOT re-run full fan-outs (teecontrol rate-limit + cost).
   - UI: serve `public/` with `py -m http.server <port> --directory public` and Playwright to `http://localhost:<port>/index.html` (file:// is BLOCKED). API 404s on the static server — that's fine, layout/Banen/credits still render. Close the auto-opened loc-overlay before clicking other buttons.
5. Commit specific files; **push from the Claude session works** (auth has not prompted recently) — try it directly. Beware `git add -A` sweeping in untracked working docs (it added course_mapping.md once).

### EFFICIENCY NOTES for next add-courses session
- Probe candidate backends in ONE batched script (see how session 2 did intogolf/teecontrol) — cheap, fast, returns confirm/deny per host.
- teecontrol API rate-limits any concurrency; don't re-test the full 20-club fetch. Unit-test logic in isolation.
- A single canonical list of all courses+metadata may be worth introducing during the user-settings task (one source of truth for both the select-UI and the scrapers/enrichment) — would make future adds a single-file edit.

## Mapping METHOD (use this to finish the 6 remaining regions — don't re-derive)
- Scope: public 18-hole + notable standalone 9-hole; tee times viewable WITHOUT login. Exclude driving ranges / par-3-only / pitch&putt / footgolf and members-only / phone-only courses.
- Enumerate per province via: golfmeesters.nl, golfinderegio.nl, anwbgolf.nl/golfbanen, playgolfinholland.nl. AVOID leadingcourses.com and nl.wikipedia.org (403/blocked) and golf.nl banenzoeker (JS-rendered → empty to WebFetch).
- Detect backend with WebFetch on the club's "boek starttijd / reserveren" page (read the booking link host). Avoid the Playwright browser for this — it is unstable here (tabs bleed across sites).
- ALWAYS probe the public backend grid before marking a course unavailable (the Haenen lesson: club site can login-gate while the backend grid URL is public).
- Subagents are one-shot and a usage-cap mid-run returns NOTHING. Front-load each agent with its course list if possible, keep batches small (~20-25 courses), and tell each to ALWAYS return a partial table. See [[feedback-subagents-not-resumable]].

## Backend DETECTION SIGNATURES (+ how to add)
- **teecontrol** → booking host `<sub>.teecontrol.com`; grid `/book` is public. (`golfdashboard.com` = member front-end of teecontrol.) Add: origin `<sub>.teecontrol.com`.
- **egolf4u** → `*.e-golf4u.nl` OR a white-label host; PUBLIC grid `https://<host>/app/booking/teetime?baan=1&datum=DD-MM-YYYY&holes=18&view=grid` — probe this even if the club site login-gates. (`ikgagolfen.nl` = front-end.) White-label hosts often throw TLS cert errors to WebFetch but load in a browser. Add: host + enumerate `baan` ids.
- **intogolf** → `*.intogolf.nl`; our scraper uses the PUBLIC `https://<sub>.baan.intogolf.nl/api/igg?date=YYYY-MM-DD`. The `golfer.*` SPA grid is login-gated — IGNORE it, use the baan API. A club WordPress page with `itgTeetimeConfig`/`itg_get_teetimes` is also intogolf. Add: subdomain.
  - **ProWare quirk:** ProWare and IntoGolf share the `/api/igg` endpoint, BUT proware hosts (`<club>.prowaregolf.nl/api/igg`) are AUTH-GATED ("Invalid authorization") while `*.baan.intogolf.nl` are open. Don't waste time on proware `/api/igg`. ProWare clubs route through the **hollandschegolfclub.nl portal** (use location_id) or **Asparagi/ikgagolfen** (see below) instead.
- **hollandschegolfclub (BurgGolf/HGC group)** → WordPress AJAX `itg_get_teetimes` on hollandschegolfclub.nl, keyed by `location_id`. The whole BurgGolf cluster lives here. Detection: booking goes to an HGC web-app / `<club>.prowaregolf.nl/mobile`, or the club is BurgGolf-branded. Add: ONE LOCATIONS line (enumerate ids — see BIG WIN note). CHEAPEST adds available.
- **Asparagi / ikgagolfen (NEW — no scraper yet)** → booking iframe `www.ikgagolfen.nl/asparagi/ikgagolfen/site2/teetimes/teetimes.asp?exclusiveCrsNr=<NNN>` (redirects to `www2.ikgagolfen.nl`). The tee-time GRID is publicly readable (times in the HTML, no login to VIEW availability; login only to book). A shared NGF portal hosting MANY public courses → one Asparagi scraper unlocks a big batch. Confirmed: Ockenburgh (`crsNr=908`), Delfland. **NOTE: `ikgagolfen.nl` is ALSO the front for egolf4u/intogolf — the egolf4u-host guess for a ikgagolfen course CAN be wrong** (Delfland's `delfland.e-golf4u.nl` 302s→404). Verify by reading the actual iframe src.
- **golfmanager** → `eu.golfmanager.com/<slug>` (JSON availability). Add: slug + `area` id.
- **nexxchange** → `nexxchange.com/search/teetimes/<slug>` (grid public). Add: slug + facet ids.
- **hetrijk** → `reserveren.hetrijkgolfbanen.nl/OnlineRes/<SITECODE>`. Add: extend rijkvannunspeet scraper with SITECODE.
- **NEW (no scraper yet)** → chronogolf/Lightspeed (`chronogolf.com|.co.nl/club/<slug>`, public), cps (`eu.cps.golf/<club>`), birdy (app-only → likely exclude), custom per-club API (e.g. Bernardus `bernardusgolf.com/wp-json/...`).
- NOTE: agents are unreliable on already-in-app courses (they guessed wrong backends for Amsteldijk/Heemskerk/Waterland). Trust the "Already in app" section above, not agent guesses, for those.

## Backends supported today (scraper exists)
teecontrol, egolf4u, intogolf (`*.baan.intogolf.nl/api/igg`), golfmanager, nexxchange, hetrijk (rijkvannunspeet — extend by SITECODE), hollandschegolfclub (ITG/Proware plugin on hollandschegolfclub.nl — keyed by `location_id`, serves the whole BurgGolf/HGC cluster).

## Already in app (13) — real backends
Hoge Dijk=teecontrol · Spaarnwoude=teecontrol · Liemeer=teecontrol · Bergvliet=teecontrol · Waterland=golfmanager · Wilnis=intogolf · Zaanse=intogolf · Amsteldijk=nexxchange · De Purmer=hollandschegolfclub(ITG) · De Loonsche Duynen=hollandschegolfclub(ITG)/loonscheduynen.prowaregolf.nl · Heemskerk=egolf4u · Haenen=egolf4u · Rijk van Nunspeet=hetrijk(RvNu)

---

## NEW courses by backend (host/slug | grid public? | city)

### teecontrol  (add: origin `<sub>.teecontrol.com`, booking `/book`)
- Dirkshorn — dirkshorn.teecontrol.com — yes — Dirkshorn (NH)
- Haarlemmermeersche — haarlemmermeersche.teecontrol.com — yes — Cruquius (NH)
- Spandersbosch — golfpark-spandersbosch.teecontrol.com — yes — Hilversum (NH)
- Kralingen — kralingen.teecontrol.com — yes — Rotterdam (ZH)
- Bentwoud — bentwoud.teecontrol.com — yes — Benthuizen (ZH)
- Zeegersloot — zeegersloot.teecontrol.com — yes — Alphen a/d Rijn (ZH)
- Tespelduyn — tespelduyn.teecontrol.com — yes — Noordwijkerhout (ZH)
- De Hooge Rotterdamsche — dehoogerotterdamsche.teecontrol.com — yes — Bergschenhoek (ZH)
- Hitland — hitland.teecontrol.com — yes — Nieuwerkerk a/d IJssel (ZH)
- Zeewolde — zeewolde.teecontrol.com — yes — Zeewolde (FL)
- Harderwold — harderwold.teecontrol.com — yes — Zeewolde (FL)
- Emmeloord — emmeloord.teecontrol.com — yes — Emmeloord (FL)
- De Gulbergen — gulbergen.teecontrol.com — yes — Mierlo (NB)
- Landgoed Nieuwkerk — nieuwkerk.teecontrol.com — yes — Goirle (NB)
- Prise d'Eau — (teecontrol; confirm subdomain) — yes — Tilburg (NB)
- Heelsum — heelsum.teecontrol.com — yes — Heelsum (GLD) [Phase0]
- Edese — (teecontrol; confirm subdomain) — yes — Ede (GLD) [Phase0]
- Welderen — welderen.teecontrol.com — yes — Elst (GLD) [Phase0]
- Havelte — (teecontrol; confirm subdomain) — yes — Havelte (DR) [Phase0]
- De Compagnie — (teecontrol; confirm subdomain) — yes — Veendam (GR) [Phase0]

### egolf4u  (add: host; PUBLIC grid `https://<host>/app/booking/teetime?baan=1&datum=DD-MM-YYYY&holes=18&view=grid` — PROBE THIS even if club site looks login-gated; enumerate baan ids)
- De Texelse — teetime.texelse.nl (white-label; TLS cert issue via fetch) — De Cocksdorp (NH)
- Regthuys — regthuys.teetime.e-golf4u.nl — Winkel (NH)
- Amsterdam Old Course — aoc.e-golf4u.nl — Amsterdam (NH)
- Broekpolder — broekpolder.e-golf4u.nl — Vlaardingen (ZH)
- Capelle — capelle.e-golf4u.nl (ikgagolfen front; possible intogolf — VERIFY) — Capelle a/d IJssel (ZH)
- Delfland — via ikgagolfen → e-golf4u — Schipluiden (ZH)
- De Woeste Kop — woestekop.e-golf4u.nl — Axel (ZE)
- Amelisweerd — eg4u.nl / m.eg4u.nl — Bunnik (UT)
- Kromme Rijn — krommerijn.teetime.e-golf4u.nl — yes — Bunnik (UT)
- Schaerweijde — schaerweijde.e-golf4u.nl — Zeist (UT)
- Wouwse Plantage — wouwse.teetime.e-golf4u.nl — yes(14d) — Bergen op Zoom (NB)
- Eindhovensche — eindhovensche.teetime.e-golf4u.nl — (private) — Valkenswaard (NB)
- Haviksoord — haviksoord.teetime.e-golf4u.nl — Leende (NB)
- Princenbosch — princenbosch.teetime.e-golf4u.nl — Molenschot (NB)
- Parc de Pettelaar — boisleduc.teetime.e-golf4u.nl — yes — Den Bosch (NB)
- De Swinkelsche — swinkelsche.teetime.e-golf4u.nl — yes — Someren (NB)
- Vught — teetime.golfclubvught.nl — Vught (NB)
- De Dommel — e-golf4u.gcdedommel.nl — Sint-Michielsgestel (NB)
- Overbrug — overbrug.e-golf4u.nl — Helmond (NB)
- Riel — gcriel.nl — Geldrop (NB)
- Welschap — (e-golf4u; find host) — Eindhoven (NB)
- De Oosterhoutse — (e-golf4u; oosterhoutse) — yes — Oosterhout (NB)
- Stippelberg — teetime.golfbaan-stippelberg.com — yes — Gemert (NB)
- De Golfhorst — (e-golf4u) — America (LB) [Phase0]
- Westfriese/Westwoud — westwoud.teetime.e-golf4u.nl — yes — Westwoud (NH) [not yet in app]

### intogolf  (our scraper uses `<sub>.baan.intogolf.nl/api/igg` — PUBLIC. The `golfer.*` grid the agents saw is login-gated, but the baan API is likely open. PROBE `https://<sub>.baan.intogolf.nl/api/igg?date=YYYY-MM-DD`)
- De Vlietlanden — vlietlanden — Wervershoof (NH)
- Sluispolder — sluispolder — Alkmaar (NH)
- Ooghduyne — ooghduyne — Den Helder (NH)
- Rijswijkse — rijswijkse — Rijswijk (ZH)
- Crayestein — crayestein — Dordrecht (ZH)
- Duinzicht — duinzicht — Wassenaar (ZH)
- Leeuwenbergh — leeuwenbergh — Leidschendam (ZH)
- Cromstrijen — cromstrijen — Numansdorp (ZH)
- De Goese Golf — goese — Goes (ZE)
- Grevelingenhout — grevelingenhout — Bruinisse (ZE)
- De Zeeuwsche — zeeuwsche — Middelburg (ZE)
- De Kroonprins — kroonprins — Vianen (UT)
- Golf Residentie Dronten — dronten — Dronten (FL)
- BurgGolf De Haverleij — hollandschegolfclub.prowaregolf.nl — Den Bosch (NB) [BurgGolf cluster]
- BurgGolf Gendersteyn — hollandschegolfclub.prowaregolf.nl — Veldhoven (NB)
- Almkreek — hollandschegolfclub.prowaregolf.nl — Almkerk (NB)
- De Kurenpolder — hollandschegolfclub.prowaregolf.nl — Hank (NB, 9-hole)

### nexxchange  (add slug; `nexxchange.com/search/teetimes/<slug>`)
- Ookmeer — golfclubookmeer (→ nexxchange login) — Amsterdam (NH)
- Heiloo G&CC — golf-countryclub-heiloo — yes — Heiloo (NH) [changed from egolf4u]
- Kavel II Beemster — kavel-2-beemster — yes — Middenbeemster (NH)
- Kleiburg — golfclub-kleiburg — yes — Brielle (ZH)
- Domburgsche — domburgsche-golfclub — yes — Domburg (ZE)
- Anderstein — (known) — yes — Maarsbergen (UT)
- Soestduinen — (known) — yes — Soest (UT)
- Old Course Loenen — old-course-loenen — (member-gated greenfee) — Loenen a/d Vecht (UT)
- Golfclub Flevoland/Batavia — (known) — yes — Lelystad (FL)
- Almeerderhout — (known) — yes — Almere (FL)
- Openbare GC Dronten — openbare-golfclub-dronten — yes — Dronten (FL)
- De Tongelreep — golf-countryclub-de-tongelreep — yes — Eindhoven (NB)
- De Bonte Bij — golfpark-de-bonte-bij — yes — Uden (NB)
- Putten — golfclub-putten — Putten (GLD) [Phase0]

### hetrijk  (extend rijkvannunspeet scraper by SITECODE at reserveren.hetrijkgolfbanen.nl/OnlineRes/<CODE>)
- Het Rijk van Nijmegen — Groesbeek (GLD) [Phase0]
- Het Rijk van Sybrook — Enschede (OV) [Phase0]
- Het Rijk van Margraten — RvM — Limburg [Phase0]

---

## NEW backends found (NOT yet supported) — candidate integrations
- **chronogolf** (Lightspeed Golf, `chronogolf.com`/`.co.nl`): Weesp, Hoogland Amersfoort, Golfcentrum Dongen, Golfcentrum Roosendaal = **4+** → worth a scraper.
- **cps** (`eu.cps.golf`): Dorhout Mees (Biddinghuizen) = 1.
- **birdy** (Birdy Golf App): Spierdijk, Open Golf Zandvoort = 2 — app-only, may have no public web grid → likely EXCLUDE unless a public endpoint exists.
- **custom-wordpress**: Bernardus Golf (`bernardusgolf.com/wp-json/.../booking-start`) = 1, own API.

## Excluded (no public tee times — members-only/phone/app)
The International, Mariënweide, Kennemer, Amsterdamse GC, Naarderbos(closed), Sloten(GolfGo only) [NH]; Koninklijke Haagsche, Noordwijkse, Rozenstein, Groendael [ZH]; De Pan, De Hoge Kleij, Goyer, De Haar [UT]; Brunssummerheide, Lauswolt [Phase0].

## UNKNOWN / to resolve
- De Lage Vuursche (Den Dolder, UT) — golfdashboard frontend; backend not exposed (login). golfdashboard usually = teecontrol → likely teecontrol, verify.
- Golfclub Midden-Brabant (Esbeek, NB) — site 403'd; member login-gated; likely egolf4u or teecontrol.
- **BurgGolf / Hollandsche Golfclub cluster conflict:** ZH agent labeled BurgGolf Gouda & Reymerswael as egolf4u via ikgagolfen; NB agent found BurgGolf (Haverleij/Gendersteyn/Almkreek/Kurenpolder + Loonsche Duynen) on `*.prowaregolf.nl` routed via hollandschegolfclub.nl (our existing ITG/Proware scraper). Resolve whether the whole BurgGolf group goes through one hollandschegolfclub.nl integration (likely) vs per-club egolf4u. Proware vs IntoGolf are conflated by the agents — verify which API actually serves these.

## Implementation notes
- egolf4u "login" entries: most are recoverable via the public `view=grid` URL (the Haenen lesson) — probe before excluding; then enumerate baan ids per club.
- intogolf "no (login)" entries: the login was the `golfer.*` SPA; our scraper uses the public `baan.intogolf.nl/api/igg` JSON — probe that host instead.
- Performance: at ~120 courses a single /api/tee-times fan-out will be huge (egolf4u = 1 request per baan per club). Need concurrency caps + short-TTL response cache before shipping.
- Enrichment still TODO for all new courses: geocode (Nominatim), landschap+hoogte tags (descriptions + AHN), auto colors, default order.
