"""
Avtomatska kategorizacija dogodkov.
Standardizira event_type in target_audience iz surovih podatkov
(categories, title, description, location).
"""

import re

# Standardizirano: 8 fiksnih kategorij za vse dogodke (uporabnikova zahteva)
ALLOWED_TYPES = ("glasba", "kultura", "literatura", "predstava",
                 "sport", "sejmi", "za otroke", "ostalo")

# Mapiranje surovih kategorij → ciljna kategorija
# Vrstni red ni naključen — bolj specifični vzorci morajo biti prvi.
EVENT_TYPE_MAP = {
    # === ZA OTROKE (najprej, ker druge kategorije lahko prevladajo) ===
    "otroš": "za otroke",
    "za otroke": "za otroke",
    "za mlade": "za otroke",
    "mladinsk": "za otroke",
    "družin": "za otroke",
    "pravljic": "za otroke",
    "lutkov": "za otroke",
    "družinsk": "za otroke",

    # === LITERATURA ===
    "literatur": "literatura",
    "knjig": "literatura",
    "branj": "literatura",
    "pisateljev": "literatura",
    "poezij": "literatura",
    "pesnik": "literatura",
    "roman": "literatura",
    "predstavitev knjige": "literatura",
    "predstavitev zbirke": "literatura",
    "literarni večer": "literatura",
    "literarno srečanje": "literatura",
    "knjižni večer": "literatura",
    "novinarska konferenca": "literatura",

    # === GLASBA ===
    "glasba": "glasba",
    "koncert": "glasba",
    "music": "glasba",
    "jazz": "glasba",
    "rock": "glasba",
    "pop": "glasba",
    "klasik": "glasba",
    "simfon": "glasba",
    "orkest": "glasba",
    "festival glasb": "glasba",
    "klubski večer": "glasba",
    "dj ": "glasba",
    "techno": "glasba",
    "elektronska glasba": "glasba",
    "zborovsk": "glasba",

    # === PREDSTAVA (gledališče, ples, opera, komedija, film, stand-up) ===
    "gledališč": "predstava",
    "predstav": "predstava",
    "ples ": "predstava",
    "plesn": "predstava",
    "theater": "predstava",
    "balet": "predstava",
    "opera": "predstava",
    "komedij": "predstava",
    "monodram": "predstava",
    "stand-up": "predstava",
    "stand up": "predstava",
    "improvizacij": "predstava",
    "kabaret": "predstava",
    "musical": "predstava",
    "film": "predstava",
    "kino": "predstava",
    "cinema": "predstava",
    "filmsk": "predstava",

    # === SPORT ===
    "šport": "sport",
    "tek ": "sport",
    "pohod": "sport",
    "kolesarj": "sport",
    "maraton": "sport",
    "turnir": "sport",
    "tekmovanj": "sport",
    "joga": "sport",
    "fitnes": "sport",
    "tenis": "sport",
    "nogomet": "sport",
    "košarka": "sport",
    "rolerji": "sport",
    "smučanj": "sport",
    "plavanj": "sport",

    # === SEJMI ===
    "sejem": "sejmi",
    "sejmi": "sejmi",
    "tržnic": "sejmi",
    "bolšjak": "sejmi",
    "kramars": "sejmi",
    "izmenjevalnic": "sejmi",
    "razprodaja": "sejmi",

    # === KULTURA (razstave, predavanja, delavnice, kulinarika, vodeni ogledi, etno) ===
    "razstav": "kultura",
    "vizualna umetnost": "kultura",
    "exhibition": "kultura",
    "vernisaž": "kultura",
    "predavanj": "kultura",
    "okrogla miza": "kultura",
    "pogovor": "kultura",
    "lecture": "kultura",
    "delavnic": "kultura",
    "workshop": "kultura",
    "ustvarjaln": "kultura",
    "kulinar": "kultura",
    "degustacij": "kultura",
    "vino": "kultura",
    "čokolad": "kultura",
    "voden ogled": "kultura",
    "vodenje": "kultura",
    "voden sprehod": "kultura",
    "kulturna prireditev": "kultura",
    "kulturni dogodek": "kultura",
    "kultura": "kultura",
    "dan odprtih vrat": "kultura",
    "odprtje": "kultura",
    "prireditev na prostem": "kultura",
    "festival": "kultura",
    "etnografsk": "kultura",
    "muzej": "kultura",
    "galerij": "kultura",
}

# Mapiranje za target_audience
AUDIENCE_PATTERNS = {
    "otroci": ["otrok", "otroš", "pravljic", "lutkov"],
    "mladina": ["mlad", "za mlade", "mladinsk"],
    "druzine": ["družin", "family"],
    "odrasli": ["odrasl", "18+"],
    "seniorji": ["senior", "upokojenc"],
    "strokovnjaki": ["strokovn", "seminar", "konferenc"],
}


def categorize_event_type(categories=None, title=None, description=None):
    """
    Določi standardizirani event_type iz surovih podatkov.
    Vedno vrne eno od 8 dovoljenih kategorij; "ostalo" če ni ujemanja.

    Priority: 'za otroke' > 'literatura' > 'glasba' > 'predstava' > 'sport' > 'sejmi' > 'kultura' > 'ostalo'.
    Zaradi tega so vzorci v EVENT_TYPE_MAP urejeni v tem vrstnem redu.
    """
    texts = []
    if categories:
        texts.append(categories.lower())
    if title:
        texts.append(title.lower())
    if description:
        texts.append(description[:300].lower())

    search_text = " ".join(texts)

    for pattern, event_type in EVENT_TYPE_MAP.items():
        if pattern in search_text:
            return event_type

    return "ostalo"


def normalize_event_type(value):
    """Preslikaj poljuben event_type v eno od 8 dovoljenih kategorij.
    Uporablja se pri migraciji obstoječih dogodkov."""
    if not value:
        return "ostalo"
    v = value.lower().strip()
    if v in ALLOWED_TYPES:
        return v
    # Mapiranje legacy vrednosti
    legacy_map = {
        "koncert": "glasba",
        "gledalisce": "predstava",
        "gledališče": "predstava",
        "film": "predstava",
        "razstava": "kultura",
        "predavanje": "kultura",
        "delavnica": "kultura",
        "festival": "kultura",
        "kulinarika": "kultura",
        "vodeni-ogled": "kultura",
        "zabava": "predstava",
        "otroski": "za otroke",
        "otroški": "za otroke",
        "sejem": "sejmi",
    }
    return legacy_map.get(v, "ostalo")


def categorize_target_audience(categories=None, title=None, description=None):
    """Določi ciljno publiko iz surovih podatkov."""
    texts = []
    if categories:
        texts.append(categories.lower())
    if title:
        texts.append(title.lower())
    if description:
        texts.append(description[:300].lower())

    search_text = " ".join(texts)

    for audience, patterns in AUDIENCE_PATTERNS.items():
        for pattern in patterns:
            if pattern in search_text:
                return audience

    return "vsi"


# Mapiranje surovih organizatorjev → človeško berljiva imena
# POZOR: Ne dodajaj dc_source ID-jev (SIGICRSS, MKCD, itd.) —
# ti so sistemski identifikatorji, ne dejanski organizatorji!
ORGANIZER_MAP = {
    "cdcc": "Cankarjev dom",
    "cd-cc": "Cankarjev dom",
    "MestoLiterature": "Mesto Literature",
    "kinosiska": "Kino Šiška",
    "kinodvor": "Kinodvor",
    "mgml": "Mestna galerija Ljubljana",
    "MGML": "Mestna galerija Ljubljana",
    "spanskiborci": "Španski borci",
    "stuk": "ŠtUK",
    "zkts-ms": "ZKTS Murska Sobota",
    "hisaotrokinumetnosti": "Hiša otrok in umetnosti",
    "lgmb": "Lutkovno gledališče Maribor",
}

# Mapiranje source_id → privzeti organizator (če ni iz vira)
SOURCE_DEFAULT_ORGANIZER = {
    "cd-cc": "Cankarjev dom",
    "kinodvor": "Kinodvor",
    "kinosiska": "Kino Šiška",
    "mgml": "Mestna galerija Ljubljana",
    "spanskiborci": "Španski borci",
    "visitljubljana": "Visit Ljubljana",
    "visitmaribor": "Visit Maribor",
    "visitskofjaloka": "Visit Škofja Loka",
    "visitptuj": "Visit Ptuj",
    "visitkranj": "Visit Kranj",
    "visitdolenjska": "Visit Dolenjska",
    "visitkrsko": "Visit Krško",
    "visitnovomesto": "Visit Novo mesto",
    "visitradgona": "Visit Radgona",
    "stuk": "Študentski kulturni center",
    "zkts-ms": "ZKTS Murska Sobota",
}


def normalize_organizer(organizer, source_id=None):
    """
    Normaliziraj ime organizatorja:
    - Popravi source_id-je ki se mešajo z imeni
    - CamelCase razbij z razmaki
    - Uporabi SOURCE_DEFAULT_ORGANIZER če ni organizatorja
    """
    if organizer:
        # Preveri v mapi popravkov
        if organizer in ORGANIZER_MAP:
            return ORGANIZER_MAP[organizer]

        # CamelCase razbij: "MestoLiterature" → "Mesto Literature"
        # Ampak ne razbij če je že normalno (npr. "MGML")
        if not organizer.isupper() and any(c.isupper() for c in organizer[1:]):
            import re
            fixed = re.sub(r'([a-zšžč])([A-ZŠŽČ])', r'\1 \2', organizer)
            if fixed != organizer:
                return fixed

        return organizer

    # Če ni organizatorja, uporabi privzetega glede na source_id
    if source_id and source_id in SOURCE_DEFAULT_ORGANIZER:
        return SOURCE_DEFAULT_ORGANIZER[source_id]

    return organizer


def categorize_event(event):
    """
    Kategoriziraj posamezen Event objekt.
    Nastavi event_type, target_audience in normalizira organizatorja.
    Vrne True če je bilo kaj spremenjenega.
    """
    changed = False

    if not event.event_type:
        et = categorize_event_type(event.categories, event.title, event.description)
        if et:
            event.event_type = et
            changed = True
    else:
        # Normaliziraj v eno od 8 dovoljenih kategorij (legacy → nova)
        normalized = normalize_event_type(event.event_type)
        if normalized != event.event_type:
            event.event_type = normalized
            changed = True

    if not event.target_audience:
        ta = categorize_target_audience(event.categories, event.title, event.description)
        if ta:
            event.target_audience = ta
            changed = True

    # Normaliziraj organizatorja
    new_org = normalize_organizer(event.organizer, event.source_id)
    if new_org != event.organizer:
        event.organizer = new_org
        changed = True

    return changed


def categorize_all():
    """Kategoriziraj vse dogodke v bazi ki še nimajo event_type."""
    from database.models import Session, Event
    db = Session()

    events = db.query(Event).filter(
        (Event.event_type == None) | (Event.event_type == "")
    ).all()

    categorized = 0
    for event in events:
        if categorize_event(event):
            categorized += 1

    db.commit()
    db.close()
    return categorized, len(events)
