"""Map a tender to Rajasthan districts from its location, title, organisation and pincode."""
from __future__ import annotations

import re

STATEWIDE = "Statewide"

# (English, Hindi, extra aliases incl. towns) for the 41 districts after the Dec-2024 reorganisation.
DISTRICTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Ajmer", "अजमेर", ("kishangarh", "pushkar", "nasirabad")),
    ("Alwar", "अलवर", ("rajgarh alwar",)),
    ("Balotra", "बालोतरा", ("pachpadra", "siwana")),
    ("Banswara", "बांसवाड़ा", ()),
    ("Baran", "बारां", ("chhabra", "atru")),
    ("Barmer", "बाड़मेर", ()),
    ("Beawar", "ब्यावर", ()),
    ("Bharatpur", "भरतपुर", ("bharathpur",)),
    ("Bhilwara", "भीलवाड़ा", ("asind", "shahpura bhilwara")),
    ("Bikaner", "बीकानेर", ("nokha", "kolayat", "lunkaransar")),
    ("Bundi", "बूंदी", ()),
    ("Chittorgarh", "चित्तौड़गढ़", ("chittaurgarh", "chittor", "chitorgarh", "nimbahera", "badi sadri")),
    ("Churu", "चूरू", ("sardarshahar", "ratangarh", "sujangarh")),
    ("Dausa", "दौसा", ()),
    ("Deeg", "डीग", ("kaman",)),
    ("Dholpur", "धौलपुर", ("dhaulpur", "rajakhera", "bari dholpur")),
    ("Didwana-Kuchaman", "डीडवाना-कुचामन", ("didwana", "kuchaman")),
    ("Dungarpur", "डूंगरपुर", ("sagwara",)),
    ("Hanumangarh", "हनुमानगढ़", ("nohar", "bhadra")),
    ("Jaipur", "जयपुर", ("jpr", "chomu", "naraina", "sanganer", "bassi", "phagi", "chaksu")),
    ("Jaisalmer", "जैसलमेर", ("pokaran", "pokhran")),
    ("Jalore", "जालोर", ("jalor", "bhinmal", "sanchore")),
    ("Jhalawar", "झालावाड़", ("jhalrapatan",)),
    ("Jhunjhunu", "झुंझुनूं", ("jhunjhunun", "khetri", "nawalgarh", "pilani")),
    ("Jodhpur", "जोधपुर", ("pipar", "bilara", "osian")),
    ("Karauli", "करौली", ("hindaun",)),
    ("Khairthal-Tijara", "खैरथल-तिजारा", ("khairthal", "tijara", "bhiwadi", "bida")),
    ("Kota", "कोटा", ("ramganjmandi",)),
    ("Kotputli-Behror", "कोटपूतली-बहरोड़", ("kotputli", "behror")),
    ("Nagaur", "नागौर", ("merta", "ladnun")),
    ("Pali", "पाली", ("falna", "sojat", "sumerpur", "bali pali")),
    ("Phalodi", "फलोदी", ()),
    ("Pratapgarh", "प्रतापगढ़", ()),
    ("Rajsamand", "राजसमंद", ("nathdwara", "kankroli")),
    ("Salumbar", "सलूम्बर", ("salumber",)),
    ("Sawai Madhopur", "सवाई माधोपुर", ("s. madhopur", "swm", "gangapur city")),
    ("Sikar", "सीकर", ("fatehpur sikar", "neem ka thana", "khandela")),
    ("Sirohi", "सिरोही", ("abu road", "aburoad", "mount abu", "pindwara")),
    ("Sri Ganganagar", "श्रीगंगानगर", ("ganganagar", "sriganganagar", "anupgarh", "suratgarh")),
    ("Tonk", "टोंक", ("niwai", "newai", "malpura", "deoli")),
    ("Udaipur", "उदयपुर", ("udr", "fatehnagar", "fathenagar")),
]

# First three pincode digits -> district, used only when the text names no district.
PIN_PREFIX = {
    "301": "Alwar", "302": "Jaipur", "303": "Jaipur", "305": "Ajmer", "306": "Pali", "307": "Sirohi",
    "311": "Bhilwara", "312": "Chittorgarh", "313": "Udaipur", "314": "Dungarpur", "321": "Bharatpur",
    "322": "Sawai Madhopur", "323": "Bundi", "324": "Kota", "325": "Baran", "326": "Jhalawar",
    "327": "Banswara", "328": "Dholpur", "331": "Churu", "332": "Sikar", "333": "Jhunjhunu",
    "334": "Bikaner", "335": "Sri Ganganagar", "341": "Nagaur", "342": "Jodhpur", "343": "Jalore",
    "344": "Barmer", "345": "Jaisalmer",
}

_STATEWIDE_RE = re.compile(r"\b(?:all|whole|entire)\s+(?:of\s+)?rajasthan\b|\bstate\s*wide\b", re.I)
_MATCHERS = [
    (en, re.compile(r"\b(?:" + "|".join(re.escape(n) for n in (en.lower(), *en.lower().split("-"), *al)) + r")\b", re.I))
    for en, _hi, al in DISTRICTS
]


def find_in_text(text: str) -> list[str]:
    if not text:
        return []
    return [en for en, rx in _MATCHERS if rx.search(text)]


def districts_for(record: dict) -> list[str]:
    detail = record.get("detail") or {}
    location = record.get("location") or detail.get("location") or ""
    found = find_in_text(location)
    if found:
        return found
    if _STATEWIDE_RE.search(location):
        return [STATEWIDE]
    found = find_in_text(record.get("title") or "")
    if found:
        return found
    for level in reversed((record.get("org_chain") or "").split("||")):
        found = find_in_text(level)
        if found:
            return found
    pin = str(detail.get("pincode") or "").strip()
    return [PIN_PREFIX[pin[:3]]] if pin[:3] in PIN_PREFIX else []


def district_names() -> list[dict]:
    return [{"id": en, "name_en": en, "name_hi": hi} for en, hi, _ in DISTRICTS] + [
        {"id": STATEWIDE, "name_en": "All Rajasthan (statewide)", "name_hi": "पूरा राजस्थान"}]
