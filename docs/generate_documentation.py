"""
Generator celovite PDF dokumentacije Event Scraper projekta.
Zagon: venv/bin/python3 docs/generate_documentation.py
Izhod: docs/event-scraper-dokumentacija.pdf
"""

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, Image
)
from reportlab.pdfgen import canvas


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "event-scraper-dokumentacija.pdf")


# =====================================================================
# STILI
# =====================================================================

styles = getSampleStyleSheet()

TITLE = ParagraphStyle(
    "Title", parent=styles["Title"], fontSize=28, leading=34, spaceAfter=20,
    textColor=colors.HexColor("#1a73e8"),
)
SUBTITLE = ParagraphStyle(
    "Subtitle", parent=styles["Normal"], fontSize=14, leading=20,
    textColor=colors.HexColor("#555"), spaceAfter=20,
)
H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontSize=20, leading=26, spaceBefore=20,
    spaceAfter=12, textColor=colors.HexColor("#1a73e8"),
    borderPadding=(0, 0, 6, 0),
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontSize=15, leading=20, spaceBefore=12,
    spaceAfter=8, textColor=colors.HexColor("#202124"),
)
H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontSize=12, leading=16, spaceBefore=8,
    spaceAfter=4, textColor=colors.HexColor("#5f6368"),
)
BODY = ParagraphStyle(
    "Body", parent=styles["Normal"], fontSize=10, leading=14,
    alignment=TA_JUSTIFY, spaceAfter=6,
)
LIST = ParagraphStyle(
    "List", parent=BODY, leftIndent=15, bulletIndent=5, spaceAfter=2,
)
CODE = ParagraphStyle(
    "Code", parent=styles["Code"], fontSize=8, leading=11,
    backColor=colors.HexColor("#f5f5f5"), borderColor=colors.HexColor("#ddd"),
    borderWidth=0.5, borderPadding=6, spaceAfter=8, leftIndent=0, rightIndent=0,
)
NOTE = ParagraphStyle(
    "Note", parent=BODY, backColor=colors.HexColor("#fff3cd"),
    borderColor=colors.HexColor("#ffeaa7"), borderWidth=0.5, borderPadding=8,
    spaceAfter=8,
)


# =====================================================================
# HEADER / FOOTER
# =====================================================================

def page_decorator(canvas_obj, doc):
    canvas_obj.saveState()
    # Footer
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#999"))
    canvas_obj.drawString(2 * cm, 1.5 * cm,
                          "Event Scraper — Dokumentacija sistema")
    canvas_obj.drawRightString(A4[0] - 2 * cm, 1.5 * cm, f"str. {doc.page}")
    # Header line
    if doc.page > 1:
        canvas_obj.setStrokeColor(colors.HexColor("#1a73e8"))
        canvas_obj.setLineWidth(2)
        canvas_obj.line(2 * cm, A4[1] - 1.8 * cm,
                        A4[0] - 2 * cm, A4[1] - 1.8 * cm)
    canvas_obj.restoreState()


# =====================================================================
# VSEBINA
# =====================================================================

def build_story():
    story = []

    # ============ NASLOVNICA ============
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Event Scraper", TITLE))
    story.append(Paragraph(
        "Sistem za centralizirano agregacijo dogodkov<br/>"
        "iz slovenskih kulturnih in turističnih virov", SUBTITLE))
    story.append(Spacer(1, 1 * cm))

    info_data = [
        ["Verzija", "2.0"],
        ["Datum dokumentacije", datetime.now().strftime("%d. %m. %Y")],
        ["Število virov", "88"],
        ["Število medijskih portalov", "8"],
        ["Tehnologija", "Python 3.9 + Flask + SQLAlchemy"],
        ["Avtor", "Uroš Maučec"],
    ]
    info_tbl = Table(info_data, colWidths=[5 * cm, 9 * cm])
    info_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#5f6368")),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eee")),
    ]))
    story.append(info_tbl)
    story.append(PageBreak())

    # ============ KAZALO (statično) ============
    story.append(Paragraph("Kazalo vsebine", H1))
    toc = [
        ("1.", "Pregled in namen sistema"),
        ("2.", "Arhitektura"),
        ("3.", "Tehnološki sklad"),
        ("4.", "Konfiguracija virov in medijev"),
        ("5.", "Scraping engine"),
        ("6.", "Parserji (12 tipov)"),
        ("7.", "Deduplikacija dogodkov"),
        ("8.", "Slike — fallback in proxy"),
        ("9.", "Opisi — extraction in AI generiranje"),
        ("10.", "Web dashboard"),
        ("11.", "REST API endpointi"),
        ("12.", "Podatkovni model"),
        ("13.", "Delovni potek (workflow)"),
        ("14.", "Varnost in avtentikacija"),
        ("15.", "Namestitev in zagon"),
        ("16.", "Operativni postopki"),
        ("17.", "Znane omejitve in prihodnji razvoj"),
    ]
    toc_data = [[num, title] for num, title in toc]
    toc_tbl = Table(toc_data, colWidths=[1.5 * cm, 14 * cm])
    toc_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a73e8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ]))
    story.append(toc_tbl)
    story.append(PageBreak())

    # ============ 1. PREGLED ============
    story.append(Paragraph("1. Pregled in namen sistema", H1))
    story.append(Paragraph(
        "<b>Event Scraper</b> je namenjen lastniku osmih regionalnih medijskih portalov "
        "(SobotaInfo, Pomurec.com, MariborInfo, PtujInfo, LjubljanaInfo, GorenjskaInfo, "
        "DolenjskaInfo in nacionalna kategorija Slovenija). Namen sistema je <b>centralizirano "
        "zbiranje dogodkov</b> iz 88 javno dostopnih virov (RSS feedi, iCal, HTML strani) ter "
        "njihovo <b>pametno razvrščanje</b> na ustrezne portale glede na regionalno relevantnost.",
        BODY))
    story.append(Paragraph(
        "Cilj: ena nadzorna plošča, kjer urednik pregleda nove dogodke, jih po potrebi "
        "dopolni (manjkajoč organizator, prizorišče ali tip), označi kot obdelane in "
        "kopira podatke v Drupal CMS portala.",
        BODY))

    story.append(Paragraph("Ključne lastnosti", H2))
    bullets = [
        "<b>Centralizirano scrapanje</b> z ročnim sproženjem (7/14/30/60/90 dni)",
        "<b>Per-medij scraping</b> — osveži samo vire za izbrani medij",
        "<b>Avtomatska deduplikacija</b> z dinamičnim fuzzy thresholdom",
        "<b>Region aliasi</b> — pomurje/pomurska, mol/osrednjeslovenska, jugovzhodna/dolenjska",
        "<b>Image fallback</b> z og:image, JSON-LD, Facebook crawler proxy in Unsplash kategorijami",
        "<b>AI generiranje opisov</b> z Gemini Flash (ROČNO, brezplačni tier)",
        "<b>Live progress bar</b> z indikatorjem virov in faz",
        "<b>Per-event inline urejanje</b> manjkajočih polj",
    ]
    for b in bullets:
        story.append(Paragraph("• " + b, LIST))

    story.append(Paragraph("Statistika ob času dokumentacije", H2))
    stats_data = [
        ["Virov vir.", "88 (60 avtomatskih, 28 ročnih)"],
        ["Regije", "12 unikatnih (po aliasingu)"],
        ["Mediji", "8 portalov (7 regionalnih + 1 nacionalni)"],
        ["Tipi parserjev", "12 (rss, ical, kulturnik-rss, kulturnik, mgml, kinodvor, kinosiska, mojaobcina, cankarjevdom, visitskofjaloka, html, manual)"],
        ["Avg. dogodkov/mesec", "~800-1200 (po deduplikaciji)"],
    ]
    stats_tbl = Table(stats_data, colWidths=[5 * cm, 11 * cm])
    stats_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(stats_tbl)
    story.append(PageBreak())

    # ============ 2. ARHITEKTURA ============
    story.append(Paragraph("2. Arhitektura", H1))
    story.append(Paragraph(
        "Sistem je sestavljen iz štirih plasti, ki tečejo na enem strežniku:",
        BODY))

    arch_data = [
        ["Plast", "Komponente", "Tehnologija"],
        ["Konfiguracija", "config/sources/*.yaml (88 datotek), config/media.yaml, config/auth.yaml",
         "YAML"],
        ["Scraping plast", "scraper/engine.py, scraper/parsers/, scraper/dedup.py, scraper/categorizer.py, scraper/image_fallback.py, scraper/ai_description.py",
         "Python, requests, BeautifulSoup, feedparser, icalendar"],
        ["Podatkovna plast", "database/models.py — Event, MediaOutlet, ScrapeLog, DrupalPushLog, SourceHealth, UnprocessedUrl, event_media",
         "SQLAlchemy + SQLite (data/events.db)"],
        ["Web plast", "web/app.py (Flask), web/templates/index.html (dashboard), login.html",
         "Flask, bcrypt, vanilla JavaScript"],
    ]
    arch_tbl = Table(arch_data, colWidths=[3.5 * cm, 7.5 * cm, 5 * cm])
    arch_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fafafa")),
    ]))
    story.append(arch_tbl)

    story.append(Paragraph("Tok podatkov", H2))
    story.append(Paragraph(
        "1. Uporabnik klikne <b>Osveži (X dni)</b> v dashboardu (z izbrano regijo/medijem ali brez).<br/>"
        "2. Flask endpoint <code>/api/scrape/refresh</code> sproži <b>thread</b> z ScraperEngine.run_all().<br/>"
        "3. Engine najprej <b>počisti staro bazo</b> (samo za izbrane vire če je media_id podan).<br/>"
        "4. Za vsak vir izbere ustrezen <b>parser</b> iz registra (preko @ParserRegistry.register).<br/>"
        "5. Parser pridobi seznam dogodkov; HTML parserji dodatno scrape-ajo detail strani.<br/>"
        "6. Vsak dogodek gre skozi <b>deduplication</b> (hash + fuzzy z dinamičnim thresholdom).<br/>"
        "7. Po scrape-u <b>auto-enrichment</b>: opisi (og:description, JSON-LD, article body) in slike (og:image, FB lookaside).<br/>"
        "8. <b>assign_events_to_media()</b> dodeli dogodke portalom glede na regijo (z aliasi).<br/>"
        "9. <b>_mark_published_events()</b> označi tiste, ki so že na portalih (preverjeno preko Drupal API).<br/>"
        "10. Dashboard <b>poll-a</b> /api/tasks/status vsake 2s za progress in po koncu naredi <code>location.reload()</code>.",
        BODY))
    story.append(PageBreak())

    # ============ 3. TEHNOLOŠKI SKLAD ============
    story.append(Paragraph("3. Tehnološki sklad", H1))

    tech_data = [
        ["Komponenta", "Verzija", "Namen"],
        ["Python", "3.9", "Glavni jezik"],
        ["Flask", "3.x", "Web dashboard"],
        ["SQLAlchemy", "2.x", "ORM (SQLite)"],
        ["bcrypt", "—", "Hashiranje gesel uporabnikov"],
        ["requests", "—", "HTTP klici (scrape, AI, proxy)"],
        ["cloudscraper", "—", "Premostitev Cloudflare zaščite"],
        ["BeautifulSoup4", "—", "HTML parser"],
        ["feedparser", "6.x", "RSS/Atom parser"],
        ["icalendar", "6.x", "iCal (.ics) parser"],
        ["rapidfuzz", "—", "Fuzzy string matching za deduplikacijo"],
        ["PyYAML", "—", "Branje YAML konfiguracij"],
        ["zoneinfo", "stdlib", "UTC → Europe/Ljubljana pretvorba"],
        ["Gemini 2.5 Flash", "API", "AI generiranje opisov (REST)"],
    ]
    tech_tbl = Table(tech_data, colWidths=[4 * cm, 2.5 * cm, 9.5 * cm])
    tech_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eee")),
    ]))
    story.append(tech_tbl)

    story.append(Paragraph("Strukturna shema", H2))
    structure = """event-scraper/
├── config/
│   ├── auth.yaml          (uporabniki, secret_key, gemini_api_key)
│   ├── media.yaml         (8 medijskih portalov)
│   └── sources/           (88 vir YAML datotek)
├── data/
│   └── events.db          (SQLite baza)
├── database/
│   └── models.py          (SQLAlchemy modeli)
├── scraper/
│   ├── engine.py          (orchestrator)
│   ├── dedup.py           (fuzzy deduplikacija)
│   ├── categorizer.py     (event_type, organizer normalizacija)
│   ├── image_fallback.py  (og:image, FB, kategorije)
│   ├── ai_description.py  (Gemini Flash)
│   ├── published_checker.py
│   └── parsers/
│       ├── registry.py    (@ParserRegistry decorator)
│       ├── base.py        (BaseParser)
│       ├── html_parser.py
│       ├── feed_parsers.py    (rss, kulturnik-rss, ical, manual)
│       └── special_parsers.py (kulturnik, mgml, kinodvor, kinosiska, mojaobcina, cankarjevdom, visitskofjaloka)
├── web/
│   ├── app.py             (Flask)
│   └── templates/
│       ├── index.html
│       └── login.html
├── tests/
├── docs/
├── run_scraper.py         (CLI scrape)
├── run_dashboard.py       (Flask zagon)
└── manage_users.py        (dodajanje uporabnikov)"""
    story.append(Paragraph("<font name='Courier' size='8'>" +
                           structure.replace("\n", "<br/>").replace(" ", "&nbsp;") + "</font>", BODY))
    story.append(PageBreak())

    # ============ 4. KONFIGURACIJA ============
    story.append(Paragraph("4. Konfiguracija virov in medijev", H1))

    story.append(Paragraph("Mediji (8 portalov)", H2))
    media_data = [
        ["ID", "Ime", "Primarne regije", "Sek."],
        ["sobotainfo", "SobotaInfo", "pomurska, pomurje, murska-sobota, lendava", "—"],
        ["pomurec", "Pomurec.com", "pomurska, pomurje, prlekija", "podravska"],
        ["mariborinfo", "MariborInfo", "maribor, podravska", "—"],
        ["ptujinfo", "PtujInfo", "ptuj, ormoz", "podravska"],
        ["ljubljanainfo", "LjubljanaInfo", "ljubljana, osrednjeslovenska, mol", "—"],
        ["gorenjskainfo", "GorenjskaInfo", "gorenjska", "—"],
        ["dolenjskainfo", "DolenjskaInfo", "dolenjska, jugovzhodna, posavje", "—"],
        ["slovenija", "Slovenija", "slovenija, savinjska, zasavska, primorska, goriska, koroska, notranjska", "—"],
    ]
    media_tbl = Table(media_data, colWidths=[2.5 * cm, 2.7 * cm, 8 * cm, 2.5 * cm])
    media_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(media_tbl)

    story.append(Paragraph("Vzorec konfiguracije vira", H2))
    sample_yaml = """source:
  id: "kulturnik-rss-maribor"
  name: "Kulturnik RSS - Maribor"
  base_url: "https://www.kulturnik.si"
  feed_url: "https://www.kulturnik.si/rss/maribor"
  region: "maribor"
  parser_type: "kulturnik-rss"
  list_selectors: {}
  detail_selectors: {}
  settings:
    delay_between_requests: 1
    timeout: 30
    encoding: "utf-8"
    user_agent: "EventScraper/1.0"
"""
    story.append(Paragraph("<font name='Courier' size='8'>" +
                           sample_yaml.replace("\n", "<br/>").replace(" ", "&nbsp;") + "</font>", BODY))

    story.append(Paragraph("Region aliasi (engine.py)", H2))
    story.append(Paragraph(
        "Engine pred ujemanjem regij normalizira nazive, da preprečimo neusklajenosti "
        "med YAML viri:",
        BODY))
    alias_data = [
        ["Iz", "V"],
        ["pomurje, murska-sobota, lendava, prlekija", "pomurska"],
        ["mol", "osrednjeslovenska"],
        ["jugovzhodna, jugovzhodna-slovenija", "dolenjska"],
        ["(ljubljana ostane kot občinski naziv za fine-grain matching)", "ljubljana"],
    ]
    alias_tbl = Table(alias_data, colWidths=[10 * cm, 5.5 * cm])
    alias_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5f6368")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(alias_tbl)
    story.append(PageBreak())

    # ============ 5. SCRAPING ENGINE ============
    story.append(Paragraph("5. Scraping engine", H1))
    story.append(Paragraph(
        "Glavna metoda <code>ScraperEngine.run_all(progress, media_id)</code> izvede "
        "scraping v 4 fazah z žic posodobljenim <code>progress</code> dict-om za live UI.",
        BODY))

    phases_data = [
        ["Faza", "% bar", "Opis"],
        ["clearing", "0", "Pobriše obstoječe dogodke (vse ali samo za media_id) + povezane event_media in DrupalPushLog. Obdrži zadnjih 50 ScrapeLog zapisov."],
        ["checking_published", "2", "Preveri portale za že objavljene dogodke (PublishedChecker)."],
        ["scraping", "2-75", "Iteracija po virih. Za vsak vir: parser.parse() → detail pages → dedup → save. Posodablja current_index/total_sources."],
        ["enrichment", "75-95", "Samo za <b>nove</b> dogodke (event_ids list). Najprej opisi (75-87%), nato slike (87-95%). Časovna meja 90s na fazo."],
        ["assigning", "96", "assign_events_to_media() + _mark_published_events()."],
        ["done", "100", "Konec, JS naredi location.reload()."],
    ]
    phases_tbl = Table(phases_data, colWidths=[3 * cm, 1.5 * cm, 11 * cm])
    phases_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(phases_tbl)

    story.append(Paragraph("Filtri pri shranjevanju dogodka", H2))
    story.append(Paragraph(
        "Vsak dogodek pred shranjevanjem v scrape_source mora preživeti naslednje filtre:",
        BODY))
    filters = [
        "<b>Datum:</b> dogodek mora imeti date_start ≥ today (preteklost se preskoči)",
        "<b>Hash dedup:</b> SHA-256 normaliziranega naslova + datuma — natančno ujemanje",
        "<b>Fuzzy dedup:</b> dinamičen threshold 60-80% glede na ujemanje časa in lokacije",
        "<b>Razstave:</b> če event_type='razstava' in trajanje > 2 dni in naslov ne vsebuje 'odprtje'/'otvoritev'/'vernisaž' → preskoči",
        "<b>Ključna polja:</b> mora imeti vsaj eno od (location/address, organizer, event_type) — drugače skoraj prazen",
    ]
    for f in filters:
        story.append(Paragraph("• " + f, LIST))
    story.append(PageBreak())

    # ============ 6. PARSERJI ============
    story.append(Paragraph("6. Parserji (12 tipov)", H1))
    story.append(Paragraph(
        "Vsak parser je registriran z dekoratorjem <code>@ParserRegistry.register('ime')</code>. "
        "Engine izbere parser glede na <code>parser_type</code> v vir YAML datoteki.",
        BODY))

    parsers_data = [
        ["parser_type", "Modul", "Namen"],
        ["html", "html_parser.py", "Generičen HTML parser preko CSS selectorjev iz YAML."],
        ["rss", "feed_parsers.py", "Univerzalni RSS/Atom parser z razširitvami za občinske feede."],
        ["kulturnik-rss", "feed_parsers.py", "Kulturnik z iCal extenzijami v RSS (DC:source/publisher)."],
        ["ical", "feed_parsers.py", "VEVENT iz .ics datotek."],
        ["manual", "feed_parsers.py", "No-op — vir je registriran a se preskoči (čaka na parser)."],
        ["kulturnik", "special_parsers.py", "Kulturnik JSON API."],
        ["mgml", "special_parsers.py", "Mestne galerije Ljubljana."],
        ["kinodvor", "special_parsers.py", "Kinodvor (Wordpress)."],
        ["kinosiska", "special_parsers.py", "Kino Šiška."],
        ["mojaobcina", "special_parsers.py", "MojaObčina.si feed."],
        ["cankarjevdom", "special_parsers.py", "Cankarjev dom."],
        ["visitskofjaloka", "special_parsers.py", "Visit Škofja Loka."],
    ]
    parsers_tbl = Table(parsers_data, colWidths=[3.5 * cm, 4 * cm, 8 * cm])
    parsers_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(parsers_tbl)

    story.append(Paragraph("BaseParser API", H2))
    story.append(Paragraph(
        "Vsak parser podeduje od <code>BaseParser</code> in implementira <code>parse(config, html=None)</code>. "
        "Razpoložljive pomožne metode:",
        BODY))
    helpers = [
        "<code>extract_text(soup, selector)</code> — varno extracta besedilo iz CSS selectorja",
        "<code>extract_attr(soup, selector, attr)</code> — extracta atribut",
        "<code>parse_date(text)</code> — slovenski formati datumov (15. apr 2026, 15.04.2026, ...)",
        "<code>parse_time(text)</code> — 'ob 19.30', '19:30', '7.30 PM' itd.",
        "<code>resolve_url(url, base)</code> — relativni → absolutni URL",
        "Properties: <code>needs_html</code> (engine pridobi HTML), <code>skip_details</code> (preskoči detail pages).",
    ]
    for h in helpers:
        story.append(Paragraph("• " + h, LIST))
    story.append(PageBreak())

    # ============ 7. DEDUPLIKACIJA ============
    story.append(Paragraph("7. Deduplikacija dogodkov", H1))
    story.append(Paragraph(
        "Sistem uporablja <b>dvostopenjsko deduplikacijo</b>:",
        BODY))

    story.append(Paragraph("1. Hash ujemanje (compute_dedup_hash)", H2))
    story.append(Paragraph(
        "<code>SHA-256(normalize_text(title) + '|' + date_start.isoformat())</code><br/>"
        "Normalizacija: male črke, odstranjeni šumniki (NFD), odstranjena ločila, "
        "presledki strnjeni. Hash se shrani v <code>events.dedup_hash</code> z indexom.",
        BODY))

    story.append(Paragraph("2. Fuzzy ujemanje (is_duplicate_fuzzy)", H2))
    story.append(Paragraph(
        "Hierarhična logika z dinamičnim thresholdom:",
        BODY))
    fuzzy_data = [
        ["Pogoj", "Threshold", "Razlaga"],
        ["Identičen normaliziran naslov + isti datum", "—", "Vedno duplikat"],
        ["Isti datum + ISTI ČAS", "60% (token_set)", "Različni viri pišejo lokacijo različno (eno venue, drugo organizator) — čas je trden indikator"],
        ["Isti datum + drug/manjka čas + ujemanje lokacije", "80%", "Strožji pogoj"],
        ["Isti datum + drug/manjka čas + RAZLIČNA lokacija", "—", "NIKOLI duplikat (npr. ČS Rožnik vs ČS Posavje)"],
    ]
    fuzzy_tbl = Table(fuzzy_data, colWidths=[5 * cm, 3 * cm, 7.5 * cm])
    fuzzy_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(fuzzy_tbl)

    story.append(Paragraph(
        "<b>Uporabljene metrike:</b> rapidfuzz <code>ratio</code>, <code>partial_ratio</code>, "
        "<code>token_sort_ratio</code>, <code>token_set_ratio</code>. Vzame se MAKSIMUM teh.",
        NOTE))

    story.append(Paragraph("Praktični primeri", H2))
    examples = [
        ["'Bass Fighters pres. Ed Rush' vs 'Ed Rush (UK) v Mariboru – Drum & Bass večer'",
         "ISTI datum + ISTI čas (21:00) → token_set 63% > 60% → DUPLIKAT"],
        ["'Čistilna akcija v ČS Rožnik' vs 'Čistilna akcija v ČS Posavje'",
         "ISTI datum + ISTI čas (09:00) ALI različni lokaciji → različni dogodki"],
        ["'Wigmorski solisti' vs '5. koncert Komornega cikla: Wigmorski solisti'",
         "Isti datum + token_set 100% → DUPLIKAT"],
    ]
    ex_tbl = Table(examples, colWidths=[8 * cm, 7.5 * cm])
    ex_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eee")),
    ]))
    story.append(ex_tbl)
    story.append(PageBreak())

    # ============ 8. SLIKE ============
    story.append(Paragraph("8. Slike — fallback in proxy", H1))
    story.append(Paragraph(
        "Modul <code>scraper/image_fallback.py</code> implementira hierarhično iskanje slik:",
        BODY))
    img_steps = [
        "<b>1. og:image / twitter:image</b> iz source_url ali detail_url",
        "<b>2. JSON-LD schema.org Event.image</b>",
        "<b>3. link rel='image_src'</b>",
        "<b>4. Facebook posts</b> — z <code>facebookexternalhit/1.1</code> User-Agent (drugače dobimo HTML redirect)",
        "<b>5. Največja vsebinska slika</b> v &lt;article&gt;/&lt;main&gt; (filtri: brez logo/icon, > 100×100px)",
        "<b>6. Slika prizorišča</b> iz VENUE_IMAGE_MAP (po source_id)",
        "<b>7. Kategorijska Unsplash slika</b> iz CATEGORY_IMAGE_MAP (koncert/gledalisce/film/...)",
        "<b>8. DEFAULT_IMAGE</b> (univerzalni placeholder)",
    ]
    for s in img_steps:
        story.append(Paragraph("• " + s, LIST))

    story.append(Paragraph("Image proxy (/api/image-proxy)", H2))
    story.append(Paragraph(
        "Facebook lookaside crawler URL-i blokirajo direktni hotlinking iz drugih domen "
        "(vrnejo HTML z JS redirect). Image proxy:",
        BODY))
    proxy_steps = [
        "Detektira FB lookaside / fbcdn.net domene",
        "Uporabi <code>facebookexternalhit/1.1</code> User-Agent (drugi vrne HTML)",
        "Sledi do 3 JavaScript redirektom (<code>location.href = '...'</code>)",
        "Postreže sliko z <code>Cache-Control: max-age=3600</code>",
    ]
    for s in proxy_steps:
        story.append(Paragraph("• " + s, LIST))

    story.append(Paragraph(
        "<b>Junk-filter:</b> <code>_is_valid_image_url()</code> izloči tracking pixle, blank-e, "
        "transparent gif-e (po keywords v URL-ju).",
        NOTE))

    story.append(Paragraph("Ročni kontrolniki", H2))
    story.append(Paragraph(
        "<b>Per-event:</b> kartica brez slike pokaže gumb <i>'Poišči sliko'</i> "
        "(POST /api/event/&lt;id&gt;/fetch-image) ki izvede force_fetch.",
        BODY))
    story.append(PageBreak())

    # ============ 9. OPISI ============
    story.append(Paragraph("9. Opisi — extraction in AI generiranje", H1))

    story.append(Paragraph("Avtomatsko extraction (extract_description)", H2))
    desc_steps = [
        "<b>1. og:description</b> meta tag",
        "<b>2. JSON-LD schema.org Event.description</b>",
        "<b>3. twitter:description</b>",
        "<b>4. meta name='description'</b>",
        "<b>5. Glavni vsebinski element</b> — prvih 10 odstavkov v &lt;article&gt;/&lt;main&gt;, max 500 znakov",
    ]
    for s in desc_steps:
        story.append(Paragraph("• " + s, LIST))

    story.append(Paragraph(
        "<b>Junk-filter:</b> <code>_is_junk_description()</code> izloči besedila krajša od 50 znakov, "
        "FB statistike (\"X people interested\"), navigacijo. Filter zazna ≥2 ključnih besed iz "
        "blacklist seznama.",
        NOTE))

    story.append(Paragraph("AI generiranje z Gemini Flash", H2))
    story.append(Paragraph(
        "Modul <code>scraper/ai_description.py</code> kliče Gemini 2.5 Flash REST API. "
        "Sproženo <b>SAMO ročno</b> z gumbom <i>'🤖 Generiraj z AI'</i>.",
        BODY))

    story.append(Paragraph("Varovalke za brezplačni tier", H3))
    quotas_data = [
        ["Limit", "Sistem", "Uradni"],
        ["Zahteve/min", "8", "10"],
        ["Zahteve/dan", "200", "250"],
        ["Beleženje", "Samo USPEŠNI klici", "—"],
        ["Reset", "00:00 UTC", "Ob 9:00 lokalno"],
    ]
    quotas_tbl = Table(quotas_data, colWidths=[5 * cm, 4 * cm, 4 * cm])
    quotas_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5f6368")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(quotas_tbl)

    story.append(Paragraph("Prompt", H3))
    prompt_text = """Napiši kratko, 2-3 stavčno promocijsko najavo dogodka v slovenščini.
Uporabi SAMO podatke ki so spodaj — NE izmišljaj programa, gostov, podrobnosti,
umetnikov ali zgodovine, ki jih ni v podatkih.
Ton naj bo vabljiv, a stvaren. Ne uporabljaj klišejev.
Ne začni s 'Pridružite se', 'Vabljeni' ali podobnimi frazami.
Vrni samo besedilo opisa, brez dodatnih navedb.

PODATKI:
Naslov: ...
Tip dogodka: ...
Datum: ...
Prizorišče: ...
Organizator: ..."""
    story.append(Paragraph("<font name='Courier' size='8'>" +
                           prompt_text.replace("\n", "<br/>").replace(" ", "&nbsp;") + "</font>", BODY))

    story.append(Paragraph(
        "<b>Označevanje:</b> AI opisi imajo <code>description_source = 'ai-generated'</code>. "
        "V dashboardu prikaže rumeno značko <i>'🤖 AI najava — preveri'</i>. "
        "Strošek pri ~50 dogodkih/dan: ~$0.15/mesec, znotraj brezplačnega tier-ja.",
        NOTE))
    story.append(PageBreak())

    # ============ 10. WEB DASHBOARD ============
    story.append(Paragraph("10. Web dashboard", H1))
    story.append(Paragraph(
        "Flask dashboard (<code>web/app.py</code>, ~900 vrstic) z enim šablonom "
        "<code>templates/index.html</code> (vanilla JS, brez framework-ov).",
        BODY))

    story.append(Paragraph("Glavne komponente UI", H2))
    ui_data = [
        ["Element", "Funkcija"],
        ["Header (modri pas)", "Naslov, števec novih, skupaj aktivnih, zadnji scraping (lokalni čas + trajanje)"],
        ["Akcijski pas (rumen)", "5× scrape gumb (7/14/30/60/90 dni), progress bar, status indikator"],
        ["Filtri", "Medij, datumski razpon (Od/Do), status (Novi/Obdelani/Preskočeni/Vsi), iskanje"],
        ["Event card", "Slika (200×150), naslov + 📋, datum + 📋, prizorišče + 📋✏️, organizator + 📋✏️, tip + ✏️, opis (vedno polni), 6 akcijskih gumbov"],
        ["Event akcije", "Kopiraj vse / Kopiraj opis / Prenesi sliko / Odpri vir / Obdelano (status='approved') / Preskoči (status='skipped')"],
        ["Per-event AI/fetch", "Pri praznem opisu: 'Najdi opis' (zeleno), '🤖 Generiraj z AI' (vijolično). Pri prazni sliki: 'Poišči sliko'."],
    ]
    ui_tbl = Table(ui_data, colWidths=[4 * cm, 11.5 * cm])
    ui_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(ui_tbl)

    story.append(Paragraph("Live progress polling", H2))
    story.append(Paragraph(
        "JavaScript polling preko <code>/api/tasks/status</code> vsake 2s. Polling se "
        "<b>zažene SAMO če task dejansko teče</b> (ne v idle stanju). DOM se posodobi "
        "samo ob spremembi vrednosti (<code>_setIfChanged</code>) — preprečuje utripanje. "
        "Po koncu scrape-a se izvede <code>location.reload()</code> da se posodobita "
        "header in seznam dogodkov.",
        BODY))
    story.append(PageBreak())

    # ============ 11. API ENDPOINTI ============
    story.append(Paragraph("11. REST API endpointi", H1))

    api_data = [
        ["Method", "Pot", "Opis"],
        ["GET", "/", "Glavni dashboard (Jinja2)"],
        ["GET/POST", "/login", "Prijava (email + bcrypt geslo)"],
        ["GET", "/logout", "Odjava"],
        ["GET", "/auth/status", "Stanje seje"],
        ["—", "", "EVENT MANAGEMENT"],
        ["POST", "/api/event/&lt;id&gt;/status", "Posodobi status dogodka (validacija)"],
        ["POST", "/api/event/&lt;id&gt;/approve", "Obdelaj dogodek za en/več medijev"],
        ["POST", "/api/event/batch-approve", "Bulk approve"],
        ["POST", "/api/event/&lt;id&gt;/update-field", "Inline edit polja (location/organizer/event_type)"],
        ["POST", "/api/event/&lt;id&gt;/fetch-image", "Najdi sliko za dogodek (force_fetch)"],
        ["POST", "/api/event/&lt;id&gt;/fetch-description", "Pridobi opis iz source_url"],
        ["POST", "/api/event/&lt;id&gt;/ai-description", "Generiraj opis z Gemini Flash"],
        ["GET", "/api/event/&lt;id&gt;", "Vrne dogodek (JSON)"],
        ["GET", "/api/event/&lt;id&gt;/copy-text", "Plain-text za kopiranje"],
        ["GET", "/api/event/&lt;id&gt;/drupal-json", "Drupal struktura"],
        ["—", "", "SCRAPING / AI"],
        ["POST", "/api/scrape/refresh", "Sproži scrape (?days=N&media=ID)"],
        ["GET", "/api/tasks/status", "Stanje scrape opravila + progress"],
        ["GET", "/api/ai/usage", "AI quota: per_min/per_day"],
        ["GET", "/api/image-proxy", "Proxy za FB hotlinking-blokirane slike"],
        ["—", "", "DRUPAL INTEGRACIJA"],
        ["GET", "/api/drupal/&lt;media&gt;/queue", "Vrste za objavo"],
        ["POST", "/api/drupal/&lt;media&gt;/push", "Push v Drupal"],
        ["POST", "/api/drupal/&lt;media&gt;/confirm", "Potrdi objavo"],
        ["GET", "/api/drupal/&lt;media&gt;/export", "Export JSON za ročno objavo"],
        ["—", "", "ZDRAVJE"],
        ["GET", "/api/stats", "Statistika"],
        ["GET", "/api/health", "SourceHealth + UnprocessedUrl"],
    ]
    api_tbl = Table(api_data, colWidths=[1.5 * cm, 6 * cm, 8 * cm])
    api_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eee")),
        ("FONTNAME", (0, 1), (1, -1), "Courier"),
    ]))
    # Označi separator vrstice
    sep_rows = [i for i, r in enumerate(api_data) if r[0] == "—"]
    for r in sep_rows:
        api_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#5f6368")),
            ("TEXTCOLOR", (0, r), (-1, r), colors.white),
            ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
            ("ALIGN", (0, r), (-1, r), "CENTER"),
        ]))
    story.append(api_tbl)
    story.append(PageBreak())

    # ============ 12. PODATKOVNI MODEL ============
    story.append(Paragraph("12. Podatkovni model", H1))

    story.append(Paragraph("Tabela: events", H2))
    events_cols = [
        ["Stolpec", "Tip", "Opis"],
        ["id", "INTEGER PK", "Avto"],
        ["title", "VARCHAR(500)", "Naslov dogodka"],
        ["description", "TEXT", "Opis"],
        ["description_source", "VARCHAR(20)", "scraped / ai-generated / manual"],
        ["date_start, date_end", "DATE", "Datumski razpon"],
        ["time_start, time_end", "VARCHAR(5)", "HH:MM"],
        ["location", "VARCHAR(500)", "Prizorišče"],
        ["address", "VARCHAR(500)", "Naslov ulice"],
        ["price", "VARCHAR(200)", "Vstopnina"],
        ["organizer", "VARCHAR(300)", "Organizator"],
        ["categories", "VARCHAR(500)", "CSV kategorij"],
        ["event_type", "VARCHAR(50)", "koncert/gledalisce/film/razstava/..."],
        ["target_audience", "VARCHAR(200)", "Otroci/Odrasli/Vsi"],
        ["district", "VARCHAR(100)", "Območje znotraj mesta"],
        ["image_url", "VARCHAR(1000)", "URL slike"],
        ["image_source", "VARCHAR(20)", "original / fallback"],
        ["source_url, detail_url, ticket_url", "VARCHAR(1000)", "URL-i"],
        ["source_id", "VARCHAR(50)", "ID vira (YAML)"],
        ["source_event_id", "VARCHAR(200)", "ID pri viru"],
        ["region", "VARCHAR(100)", "Regija vira (pred normalizacijo)"],
        ["dedup_hash", "VARCHAR(64) IDX", "SHA-256 dedup hash"],
        ["quality_score, completeness", "INTEGER", "Kakovost"],
        ["scraped_at, updated_at", "DATETIME", "Časovni žigi"],
    ]
    events_tbl = Table(events_cols, colWidths=[5 * cm, 3.5 * cm, 7 * cm])
    events_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eee")),
        ("FONTNAME", (0, 1), (0, -1), "Courier"),
    ]))
    story.append(events_tbl)

    story.append(Paragraph("Druge tabele", H2))
    other_data = [
        ["Tabela", "Namen"],
        ["media_outlets", "8 medijskih portalov (id, name, regions JSON)"],
        ["event_media (M:N)", "Many-to-many povezava event ↔ media + status (new/approved/skipped/queued/pushed/published)"],
        ["scrape_log", "Eden zapis na vir-zagon: started_at, finished_at, status, events_found/new/duplicates"],
        ["drupal_push_log", "Sledenje push-ov v Drupal portale"],
        ["source_health", "Zdravje virov (consecutive_errors, last_check)"],
        ["unprocessed_urls", "URL-i ki niso bili obdelani (za diagnostiko)"],
    ]
    other_tbl = Table(other_data, colWidths=[4 * cm, 11.5 * cm])
    other_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5f6368")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(other_tbl)

    story.append(Paragraph(
        "<b>Session management:</b> SQLAlchemy <code>scoped_session</code> + <code>get_db()</code> "
        "context manager (auto-commit ob uspehu, auto-rollback ob napaki, vedno close). "
        "Vsak Flask endpoint uporablja <code>with get_db() as db:</code>.",
        NOTE))
    story.append(PageBreak())

    # ============ 13. WORKFLOW ============
    story.append(Paragraph("13. Delovni potek (workflow)", H1))

    story.append(Paragraph("Statusi dogodka", H2))
    status_data = [
        ["Status", "Pomen", "Prehod (kdo lahko →)"],
        ["new", "Novi (privzeti)", "approved, skipped"],
        ["approved", "Obdelano (urednik kliknil 'Obdelano')", "queued, skipped"],
        ["queued", "V čakalnici za push v Drupal", "pushed, approved"],
        ["pushed", "Poslano v Drupal API", "published, queued"],
        ["published", "Objavljeno na portalu", "archived"],
        ["skipped", "Preskočeno (irelevanten)", "new"],
        ["archived", "Arhivirano (zgodovina)", "(končno)"],
    ]
    status_tbl = Table(status_data, colWidths=[3 * cm, 6 * cm, 6.5 * cm])
    status_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
        ("FONTNAME", (0, 1), (0, -1), "Courier"),
    ]))
    story.append(status_tbl)

    story.append(Paragraph("Tipičen dnevni delovni potek urednika", H2))
    flow_steps = [
        "<b>1.</b> Urednik odpre dashboard, izbere medij iz dropdown (npr. 'MariborInfo')",
        "<b>2.</b> Klikne <i>Osveži (30 dni)</i> — sproži scrape samo za 13 mariborskih virov, počisti staro bazo zanje",
        "<b>3.</b> Sledi progress bar (5-10 min): scrape → enrichment → razvrščanje",
        "<b>4.</b> Po končanem reload-u vidi seznam novih dogodkov v statusu 'Novi'",
        "<b>5.</b> Za vsak dogodek pregleda vsebino, po potrebi dopolni manjkajoče (✏️ inline edit) ali generira AI opis",
        "<b>6.</b> Klikne <i>Kopiraj vse</i> ali posamezna polja → prilepi v Drupal CMS",
        "<b>7.</b> V dashboardu klikne <i>Obdelano</i> (status → approved) ali <i>Preskoči</i> (skipped)",
        "<b>8.</b> Naslednji dan ali tedensko ponovi celoten cikel",
    ]
    for s in flow_steps:
        story.append(Paragraph(s, BODY))
    story.append(PageBreak())

    # ============ 14. VARNOST ============
    story.append(Paragraph("14. Varnost in avtentikacija", H1))

    sec_items = [
        ["Avto-generirani secret_key", "Če v auth.yaml manjka ali je placeholder, sistem generira 256-bit naključen ključ in ga shrani"],
        ["bcrypt geslo hashes", "Vsi uporabniki imajo bcrypt hash z gensalt() (default cost=12)"],
        ["Sejni piškotki", "HttpOnly + SameSite=Lax + 7-dnevno trajanje"],
        ["Brez avtentikacije = 503", "Če ni definiranih uporabnikov, sistem ne dovoli dostopa (prej je bil odprt)"],
        ["Rate limiting", "Login: 5 poskusov/IP/15min; AI: 8/min in 200/dan (free-tier zaščita)"],
        ["Input validacija", "VALID_STATUSES enum, get_json_or_400() validira JSON body, dovoljena polja za update_field"],
        ["FLASK_DEBUG=0 default", "Debug mode samo če eksplicitno nastavljen v okolici"],
        ["Error handlers", "400, 404, 500 vrnejo JSON z varnim sporočilom (brez tracebacks za uporabnika)"],
    ]
    for label, desc in sec_items:
        story.append(Paragraph(f"<b>{label}</b> — {desc}", LIST))

    story.append(Paragraph("Občutljivi podatki — kje so", H2))
    secrets_data = [
        ["Datoteka", "Vsebina", "V git?"],
        ["config/auth.yaml", "secret_key, bcrypt password hashes, gemini_api_key", "NE (mora biti v .gitignore)"],
        ["data/events.db", "Vsi dogodki, scrape logi", "NE"],
        ["logs/", "Scrape log datoteke (lahko vsebujejo URL-je)", "NE"],
    ]
    secrets_tbl = Table(secrets_data, colWidths=[5 * cm, 7 * cm, 3.5 * cm])
    secrets_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dc3545")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    story.append(secrets_tbl)
    story.append(PageBreak())

    # ============ 15. NAMESTITEV ============
    story.append(Paragraph("15. Namestitev in zagon", H1))

    story.append(Paragraph("Sistem zahteve", H2))
    story.append(Paragraph(
        "• Python 3.9+ (testirano na 3.9)<br/>"
        "• ~500 MB prostora (venv + baza)<br/>"
        "• Internet dostop (scraping)<br/>"
        "• Po želji: Gemini API ključ za AI opise",
        BODY))

    story.append(Paragraph("Prva namestitev", H2))
    install = """cd /Users/urosmaucec/Claude/event-scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 manage_users.py add  # Dodaj prvega uporabnika"""
    story.append(Paragraph("<font name='Courier' size='9'>" +
                           install.replace("\n", "<br/>") + "</font>", BODY))

    story.append(Paragraph("Zagon dashboard-a", H2))
    run = """venv/bin/python3 run_dashboard.py
# Privzeto na portu 5000 (lokalno: 8080 preko launch.json)
# Brskalnik: http://localhost:8080"""
    story.append(Paragraph("<font name='Courier' size='9'>" +
                           run.replace("\n", "<br/>") + "</font>", BODY))

    story.append(Paragraph("CLI scraping (brez dashboard-a)", H2))
    cli = """venv/bin/python3 run_scraper.py          # Vsi viri
venv/bin/python3 run_scraper.py --test   # Samo prvi vir
# Logi: logs/scrape_YYYYMMDD_HHMM.log"""
    story.append(Paragraph("<font name='Courier' size='9'>" +
                           cli.replace("\n", "<br/>") + "</font>", BODY))

    story.append(Paragraph("Konfiguracija Gemini API", H2))
    story.append(Paragraph(
        "1. Pridobi ključ na <b>https://aistudio.google.com/apikey</b><br/>"
        "2. V <code>config/auth.yaml</code> spremeni <code>gemini_api_key: null</code> v "
        "<code>gemini_api_key: AIzaSy...</code><br/>"
        "3. Restartiraj strežnik<br/>"
        "4. V dashboardu klikni <i>'🤖 Generiraj z AI'</i> pri dogodku brez opisa",
        BODY))
    story.append(PageBreak())

    # ============ 16. OPERATIVNI POSTOPKI ============
    story.append(Paragraph("16. Operativni postopki", H1))

    story.append(Paragraph("Dodajanje novega uporabnika", H2))
    story.append(Paragraph(
        "<code>venv/bin/python3 manage_users.py add</code><br/>"
        "Skript zahteva email, ime in geslo. Generira bcrypt hash in doda v auth.yaml.",
        BODY))

    story.append(Paragraph("Dodajanje novega vira", H2))
    story.append(Paragraph(
        "1. Ustvari <code>config/sources/&lt;ime&gt;.yaml</code> po vzorcu obstoječega<br/>"
        "2. Določi <code>parser_type</code> (rss/html/manual/special)<br/>"
        "3. Določi <code>region</code> (uporabi že obstoječe nazive)<br/>"
        "4. Po želji dodaj v <code>config/media.yaml</code> pod <code>all_sources</code><br/>"
        "5. Po naslednjem scrape-u se dogodki avtomatsko razvrstijo na ustrezne portale",
        BODY))

    story.append(Paragraph("Onemogočanje vira", H2))
    story.append(Paragraph(
        "Najlažje: spremeni <code>parser_type: \"rss\"</code> v <code>parser_type: \"manual\"</code> "
        "in dodaj <code>disabled: true</code>. Engine ga bo preskočil. "
        "Primer: Občina Ormož je onemogočena ker opisi niso ustrezni.",
        BODY))

    story.append(Paragraph("Backup baze", H2))
    story.append(Paragraph(
        "<code>cp data/events.db data/events.db.backup-$(date +%Y%m%d)</code><br/>"
        "Priporočljivo pred velikimi spremembami (clear-and-rescrape).",
        BODY))

    story.append(Paragraph("Diagnostika napak", H2))
    diag = [
        "<b>Scraper se zatakne pri viru:</b> preveri logs/scrape_*.log za stack trace; viri imajo timeout 30s.",
        "<b>Slika ni vidna pri FB dogodkih:</b> preveri ali image proxy uporablja facebookexternalhit User-Agent (app.py: image_proxy()).",
        "<b>AI ne dela:</b> /api/ai/usage pokaže porabo; če per_day == 200, počakaj na reset (UTC midnight).",
        "<b>Header 'Zadnji scraping' kaže star čas:</b> osveži stran (location.reload je avtomatski po scrape-u).",
        "<b>Veliko duplikatov:</b> preveri dedup.py thresholde; dvigni če imaš false negative-e.",
    ]
    for d in diag:
        story.append(Paragraph("• " + d, LIST))
    story.append(PageBreak())

    # ============ 17. ZNANE OMEJITVE ============
    story.append(Paragraph("17. Znane omejitve in prihodnji razvoj", H1))

    story.append(Paragraph("Trenutne omejitve", H2))
    limits = [
        "<b>Statusi se izgubijo ob clear-and-rescrape</b> — če uporabnik označi dogodek kot 'approved', nato sproži nov scrape, status se izgubi (ker se baza počisti).",
        "<b>28 ročnih virov</b> (parser_type='manual') — ti viri trenutno nimajo avtomatskega scraping-a (večinoma JS-težke strani).",
        "<b>Drupal push še ni implementiran end-to-end</b> — endpointi obstajajo, a Drupal API integracija je placeholderska.",
        "<b>Brez schedulerja</b> — vse je ročno (po uporabnikovi zahtevi). Ni cron job-a.",
        "<b>Single-user assumption</b> — če dva uporabnika hkrati klikneta scrape, drugi dobi 409 (running).",
    ]
    for l in limits:
        story.append(Paragraph("• " + l, LIST))

    story.append(Paragraph("Možne izboljšave", H2))
    future = [
        "<b>Persistent statusi</b>: ločena 'event_history' tabela z naslov+datum hash-em za 'skipped' dogodke da se ne pojavijo več kot 'novi'",
        "<b>Drupal API client</b>: implementacija push-a v WordPress/Drupal preko REST",
        "<b>Per-medij 'Featured' označevanje</b>: za izpostavljene dogodke",
        "<b>Email diges</b>: dnevno/tedensko poročilo o novostih",
        "<b>Histogram po regijah</b>: vizualizacija dogodkov po regiji v dashboardu",
        "<b>Avtomatsko parserizacija ročnih virov</b>: dodatni parser-ji za posamezne strani",
        "<b>Multi-user collaboration</b>: ločeni statusi po urednikih",
    ]
    for f in future:
        story.append(Paragraph("• " + f, LIST))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        "<b>Konec dokumentacije.</b> Za vprašanja in dopolnitve se obrnite na avtorja.",
        NOTE))

    return story


def main():
    os.makedirs(HERE, exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        title="Event Scraper - Dokumentacija",
        author="Uros Maucec",
    )
    story = build_story()
    doc.build(story, onFirstPage=page_decorator, onLaterPages=page_decorator)
    print(f"PDF zgrajen: {OUTPUT}")
    print(f"Velikost: {os.path.getsize(OUTPUT) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
