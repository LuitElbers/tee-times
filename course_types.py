"""Single source of truth for course type (championship vs short).

DEFINITION (hard requirement): a course may be classified "championship" ONLY if it
is a full-length REGULATION course — 18-hole regulation (par ~68-72) or a full 9-hole
regulation course (par ~34-36 per 9). Short / executive / par-3 / pitch&putt courses
are "short" and must only appear under the app's "Par 3/4" filter, never as Championship.

This is enforced by tests/test_course_types.py:
  - every course the app/scrapers can emit MUST appear in COURSE_TYPES (a new, unclassified
    course fails the test — default-deny: nothing is championship until verified here);
  - each backend's per-course championship-eligibility MUST match this registry.

"short" courses (verified par below regulation). Each cites why:
  Soestduinen            par 27/9, C-status par-3
  De Bonte Bij           par-3 9h (70-170m)
  Eyckenduyn             par ~29/9, C-status (7 par-3 + 2 par-4)
  Kavel II Beemster      par 64/18 (32/9), executive
  De Vlietlanden         par 60/18 (30/9), executive
  Duinzicht              par ~29/9 (7 par-3 + 2 par-4)
  Kapelkeshof            par-3/4 pitch&putt (PPBN)
  Riel                   par 31/9, executive (6 par-3)
  Ockenburgh             par ~31/9, executive (5 par-4 + 4 par-3)
  Concordia              par-3 (Delft)
  Weesp                  pure par-3 9h (90-160m)
  Tespelduyn             par 32/9, executive (1 par-5, 3 par-4, 5 par-3) [borderline]
  Golfcentrum Roosendaal par 33/9, 5 of 9 holes par-3 [borderline]
  Welderen               par-3/4 course
  Shortgolf Utrecht      par-3 / par-3-4 short course
  Schaerweijde           9 holes par 28/9 (8 par-3 + 1 par-4), played twice for "18"
  Parc de Pettelaar      par-3/4 9h (short narrow fairways)
  Vught                  par-3 course (longest hole 140m)
  Kralingen              par 32/9, executive
  Harderwold             par 31/9, executive (4 par-4 + 5 par-3)
  Maasduinen             par 29/9, executive (7 par-3 + 2 par-4)
  Putten                 par 64/18 (32/9), executive "compact qualifying"
  BurgGolf Rotterdam     Crimpenerhout par 33/9 (~2074m) [borderline]

Note: a booking system offering "18 holes" is often a 9-hole course played twice — so
classification is by actual length/par per course, NOT by the hole option shown.

Mixed clubs (a full regulation course AND a separate par-3/short course) are classified
"championship": they legitimately offer championship golf; their par-3 sub-course is split
off at the sub-course level by the scraper, not here.
"""

COURSE_TYPES = {
    "Hoge Dijk": "championship",
    "Waterland": "championship",
    "Spaarnwoude": "championship",
    "Wilnis": "championship",
    "De Purmer": "championship",
    "Zaanse": "championship",
    "Amsteldijk": "championship",
    "Liemeer": "championship",
    "Heemskerk": "championship",
    "Bergvliet": "championship",
    "Haenen": "championship",
    "De Loonsche Duynen": "championship",
    "Rijk van Nunspeet": "championship",
    "Dirkshorn": "championship",
    "Haarlemmermeersche": "championship",
    "Spandersbosch": "championship",
    "Kralingen": "short",
    "Bentwoud": "championship",
    "Zeegersloot": "championship",
    "De Hooge Rotterdamsche": "championship",
    "Hitland": "championship",
    "Zeewolde": "championship",
    "Harderwold": "short",
    "Emmeloord": "championship",
    "De Gulbergen": "championship",
    "Landgoed Nieuwkerk": "championship",
    "Heelsum": "championship",
    "Welderen": "short",
    "Prise d'Eau": "championship",
    "De Vlietlanden": "short",
    "Sluispolder": "championship",
    "Ooghduyne": "championship",
    "Rijswijkse": "championship",
    "Crayestein": "championship",
    "Duinzicht": "short",
    "Leeuwenbergh": "championship",
    "Cromstrijen": "championship",
    "De Goese Golf": "championship",
    "Grevelingenhout": "championship",
    "De Zeeuwsche": "championship",
    "De Kroonprins": "championship",
    "Golf Residentie Dronten": "championship",
    "Westerpark": "championship",
    "De Haverleij": "championship",
    "Gendersteyn": "championship",
    "Almkreek": "championship",
    "De Kurenpolder": "championship",
    "Reymerswael": "championship",
    "De Berendonck": "championship",
    "De Breuninkhof": "championship",
    "Land van Thorn": "championship",
    "Sint Nyk": "championship",
    "BurgGolf Rotterdam": "short",
    "Shortgolf Utrecht": "short",
    "Tespelduyn": "short",
    "Edese": "championship",
    "De Compagnie": "championship",
    "Rijk van Nijmegen": "championship",
    "Rijk van Sybrook": "championship",
    "Rijk van Margraten": "championship",
    "De Texelse": "championship",
    "Regthuys": "championship",
    "Westfriese": "championship",
    "Amsterdam Old Course": "championship",
    "Broekpolder": "championship",
    "De Woeste Kop": "championship",
    "Kromme Rijn": "championship",
    "Schaerweijde": "short",
    "Wouwse Plantage": "championship",
    "Princenbosch": "championship",
    "Parc de Pettelaar": "short",
    "De Swinkelsche": "championship",
    "Vught": "short",
    "De Dommel": "championship",
    "Overbrug": "championship",
    "Riel": "short",
    "De Oosterhoutse": "championship",
    "Stippelberg": "championship",
    "De Golfhorst": "championship",
    "Haviksoord": "championship",
    "Heiloo": "championship",
    "Kavel II Beemster": "short",
    "Domburgsche": "championship",
    "Openbare Golfclub Dronten": "championship",
    "Putten": "short",
    "Anderstein": "championship",
    "Flevoland": "championship",
    "Havelte": "championship",
    "Soestduinen": "short",
    "De Bonte Bij": "short",
    "Ockenburgh": "short",
    "Capelle": "championship",
    "Concordia": "short",
    "De Turfvaert": "championship",
    "Hoenshuis": "championship",
    "Twentse Golfpark": "championship",
    "Delfland": "championship",
    "De Hattemse": "championship",
    "Winterswijk": "championship",
    "De Scherpenbergh": "championship",
    "Engelenburg": "championship",
    "De Batouwe": "championship",
    "Keppelse": "championship",
    "Sallandsche": "championship",
    "The Links Valley": "championship",
    "Hooge Graven": "championship",
    "Zwolle": "championship",
    "De Koepel": "championship",
    "Rosendaelsche": "championship",
    "De Dorpswaard": "championship",
    "De Lage Mors": "championship",
    "Maasduinen": "short",
    "Brunssummerheide": "championship",
    "Heidemeer": "championship",
    "Martensplek": "championship",
    "De Semslanden": "championship",
    "De Peelse Golf": "championship",
    "Drentsche": "championship",
    "Ameland": "championship",
    "Kapelkeshof": "short",
    "Zuid-Drenthe": "championship",
    "De Herkenbosche": "championship",
    "Eyckenduyn": "short",
    "Gaasterland": "championship",
    "Holthuizen": "championship",
    "Sandur": "championship",
    "Exloo": "championship",
    "Weesp": "short",
    "Golfcentrum Dongen": "championship",
    "Golfcentrum Roosendaal": "short",
    "Bernardus": "championship",
    "Bleijenbeek": "championship",
    "Lochemse": "championship",
}


def is_championship(course_name: str) -> bool:
    """A course counts as championship ONLY if explicitly verified as such here.
    Unknown courses default to NOT championship (default-deny)."""
    return COURSE_TYPES.get(course_name) == "championship"
