"""
Avtomatska kategorizacija dogodkov.
Standardizira event_type in target_audience iz surovih podatkov
(categories, title, description, location).
"""

import re

# Mapiranje surovih kategorij → standardizirani event_type
# Ključi so lowercase vzorci, vrednosti so standardizirane kategorije
EVENT_TYPE_MAP = {
    # Razstave
    "razstav": "razstava",
    "vizualna umetnost": "razstava",
    "exhibition": "razstava",
    # Glasba
    "glasba": "koncert",
    "koncert": "koncert",
    "music": "koncert",
    "jazz": "koncert",
    "rock": "koncert",
    "pop": "koncert",
    # Gledališče
    "gledališč": "gledalisce",
    "predstav": "gledalisce",
    "ples": "gledalisce",
    "theater": "gledalisce",
    "balet": "gledalisce",
    "opera": "gledalisce",
    "komedij": "gledalisce",
    "lutkov": "gledalisce",
    # Film
    "film": "film",
    "kino": "film",
    "cinema": "film",
    # Predavanja / izobraževanje
    "predavanj": "predavanje",
    "okrogla miza": "predavanje",
    "pogovor": "predavanje",
    "lecture": "predavanje",
    # Delavnice
    "delavnic": "delavnica",
    "workshop": "delavnica",
    "ustvarjaln": "delavnica",
    # Festivali
    "festival": "festival",
    # Šport
    "šport": "sport",
    "tek ": "sport",
    "pohod": "sport",
    "kolesarj": "sport",
    "maraton": "sport",
    "turnir": "sport",
    "tekmovanj": "sport",
    # Sejmi / tržnice
    "sejem": "sejem",
    "tržnic": "sejem",
    "trg": "sejem",
    # Otroški
    "otroš": "otroski",
    "za otroke": "otroski",
    "za mlade": "otroski",
    "mladinsk": "otroski",
    "družin": "otroski",
    "pravljic": "otroski",
    # Kulinarika
    "kulinar": "kulinarika",
    "degustacij": "kulinarika",
    "vino": "kulinarika",
    "čokolad": "kulinarika",
    # Vodeni ogledi
    "voden ogled": "vodeni-ogled",
    "vodenje": "vodeni-ogled",
    "voden sprehod": "vodeni-ogled",
    # Zabava
    "zabav": "zabava",
    "party": "zabava",
    "stand-up": "zabava",
    "kviz": "zabava",
    "družabn": "zabava",
    # Kulturna prireditev (splošno)
    "kulturna prireditev": "kultura",
    "kulturni dogodek": "kultura",
    "kultura": "kultura",
    "dan odprtih vrat": "kultura",
    "odprtje": "kultura",
    "prireditev na prostem": "kultura",
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
    Preveri categories → title → description (po prioriteti).
    """
    # Združi vsa besedila za iskanje
    texts = []
    if categories:
        texts.append(categories.lower())
    if title:
        texts.append(title.lower())
    # Description samo kot zadnji fallback
    if description and not texts:
        texts.append(description[:200].lower())

    search_text = " ".join(texts)

    # Poišči ujemanje po prioriteti
    for pattern, event_type in EVENT_TYPE_MAP.items():
        if pattern in search_text:
            return event_type

    return None


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
