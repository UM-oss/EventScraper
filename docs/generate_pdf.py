#!/usr/bin/env python3
"""Generira PDF dokumentacijo za Event Scraper projekt."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, HRFlowable
)

OUTPUT = "/Users/urosmaucec/Claude/event-scraper/docs/event-scraper-dokumentacija.pdf"

# Colors
PRIMARY = HexColor("#1a1a2e")
ACCENT = HexColor("#4285F4")
LIGHT_BG = HexColor("#f8f9fa")
BORDER = HexColor("#dee2e6")
GREEN = HexColor("#28a745")
ORANGE = HexColor("#fd7e14")
RED = HexColor("#dc3545")

styles = getSampleStyleSheet()

# Custom styles
styles.add(ParagraphStyle(
    name="DocTitle", parent=styles["Title"],
    fontSize=28, leading=34, textColor=PRIMARY,
    spaceAfter=6, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="DocSubtitle", parent=styles["Normal"],
    fontSize=14, leading=18, textColor=HexColor("#666"),
    spaceAfter=30, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="H1", parent=styles["Heading1"],
    fontSize=20, leading=26, textColor=PRIMARY,
    spaceBefore=24, spaceAfter=12,
    borderWidth=0, borderPadding=0,
))
styles.add(ParagraphStyle(
    name="H2", parent=styles["Heading2"],
    fontSize=15, leading=20, textColor=HexColor("#333"),
    spaceBefore=18, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="H3", parent=styles["Heading3"],
    fontSize=12, leading=16, textColor=HexColor("#555"),
    spaceBefore=12, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["Normal"],
    fontSize=10, leading=14, alignment=TA_JUSTIFY,
    spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="CodeBlock", parent=styles["Code"],
    fontSize=9, leading=13,
    backColor=LIGHT_BG,
    borderWidth=0.5, borderColor=BORDER,
    borderPadding=6,
    spaceAfter=8, spaceBefore=4,
    fontName="Courier",
))
styles.add(ParagraphStyle(
    name="BulletCustom", parent=styles["Normal"],
    fontSize=10, leading=14,
    leftIndent=20, bulletIndent=8,
    spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="Small", parent=styles["Normal"],
    fontSize=8, leading=11, textColor=HexColor("#999"),
))


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12, spaceBefore=12)


def make_table(headers, rows, col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_BG]),
    ]))
    return t


def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="Event Scraper - Dokumentacija",
        author="Event Scraper System",
    )

    story = []
    W = A4[0] - 4*cm  # usable width

    # ============================================================
    # NASLOVNA STRAN
    # ============================================================
    story.append(Spacer(1, 60))
    story.append(Paragraph("Event Scraper", styles["DocTitle"]))
    story.append(Paragraph("Sistem za avtomatizirano zbiranje, kategorizacijo<br/>in distribucijo dogodkov po Sloveniji", styles["DocSubtitle"]))
    story.append(hr())

    story.append(Spacer(1, 20))
    info_data = [
        ["Verzija", "1.0"],
        ["Datum", "16. april 2026"],
        ["Virov", "88 (39 avtomatiziranih, 49 rocnih)"],
        ["Portalov", "7 medijev"],
        ["Dogodkov v bazi", "1.023 (764 prihodnjih)"],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("LEADING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(info_table)

    story.append(PageBreak())

    # ============================================================
    # KAZALO
    # ============================================================
    story.append(Paragraph("Kazalo vsebine", styles["H1"]))
    toc_items = [
        "1. Pregled sistema",
        "2. Arhitektura",
        "3. Viri dogodkov (88 virov)",
        "4. Mediji / Portali (7 portalov)",
        "5. Baza podatkov",
        "6. Drupal JSON format",
        "7. API endpointi",
        "8. Avtomatska kategorizacija",
        "9. Deduplikacija",
        "10. Health monitoring",
        "11. Avtentikacija",
        "12. CLI ukazi",
        "13. Namestitev in zagon",
    ]
    for item in toc_items:
        story.append(Paragraph(item, styles["Body"]))
    story.append(PageBreak())

    # ============================================================
    # 1. PREGLED SISTEMA
    # ============================================================
    story.append(Paragraph("1. Pregled sistema", styles["H1"]))
    story.append(Paragraph(
        "Event Scraper je centraliziran sistem za avtomatizirano zbiranje dogodkov iz razlicnih virov "
        "po celotni Sloveniji. Dogodki se zbirajo iz RSS feedov, iCal koledarjev in HTML strani, nato pa "
        "se kategorizirajo, dedupplicirajo in razvrscajo na 7 medijskih portalov za objavo.",
        styles["Body"]
    ))
    story.append(Paragraph(
        "Sistem je zasnovan za polavtomatsko objavo v Drupal CMS — vsak dogodek se pretvori v "
        "Drupal-kompatibilen JSON format z vsemi potrebnimi polji (naslov, prizorisce, vrsta dogodka, "
        "termin, slika, vsebina). Urednik pregleda dogodke v dashboardu, odobri izbrane, sistem pa "
        "jih posreduje v Drupal.",
        styles["Body"]
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Kljucne zmogljivosti:", styles["H3"]))
    features = [
        "88 virov dogodkov po celotni Sloveniji (gledalisca, galerije, festivali, turisticni portali...)",
        "RSS, iCal in HTML parserji z avtomatskim prepoznavanjem formata",
        "3-nivojska deduplikacija (hash + fuzzy matching + portal check)",
        "Avtomatska kategorizacija po vrsti dogodka in ciljni publiki",
        "Centralizirano zbiranje + pametna distribucija na 7 portalov",
        "Drupal-ready JSON API za polavtomatizirano objavo",
        "Health monitoring vseh virov z opozorili ob napakah",
        "Email/geslo avtentikacija za dashboard",
    ]
    for f in features:
        story.append(Paragraph(f"&bull; {f}", styles["BulletCustom"]))

    story.append(PageBreak())

    # ============================================================
    # 2. ARHITEKTURA
    # ============================================================
    story.append(Paragraph("2. Arhitektura", styles["H1"]))
    story.append(Paragraph("Sistem je sestavljen iz naslednjih komponent:", styles["Body"]))

    arch_data = [
        ["Komponenta", "Opis", "Lokacija"],
        ["Scraper Engine", "Glavni motor za pobiranje podatkov", "scraper/engine.py"],
        ["Parserji", "RSS, iCal, HTML (kulturnik, mojaobcina...)", "scraper/engine.py"],
        ["Kategorizator", "Avtomatska kategorizacija dogodkov", "scraper/categorizer.py"],
        ["Deduplikator", "Hash + fuzzy + portal preverjanje", "scraper/dedup.py"],
        ["Health Check", "Monitoring zdravja virov", "scraper/health_check.py"],
        ["Published Checker", "Preverjanje ze objavljenih na portalih", "scraper/published_checker.py"],
        ["Baza podatkov", "SQLite z SQLAlchemy ORM", "database/models.py"],
        ["Web Dashboard", "Flask app z avtentikacijo", "web/app.py"],
        ["YAML konfiguracija", "Viri in mediji", "config/"],
    ]
    story.append(make_table(arch_data[0], arch_data[1:], [3.5*cm, 7*cm, 5.5*cm]))

    story.append(Spacer(1, 16))
    story.append(Paragraph("Workflow:", styles["H2"]))
    workflow_steps = [
        "1. Scraper pobere dogodke iz vseh avtomatiziranih virov (RSS, iCal, HTML)",
        "2. Vsak dogodek se kategorizira (event_type, target_audience)",
        "3. Deduplikacija odstrani podvojene dogodke (3 nivoji preverjanja)",
        "4. Dogodki se shranijo v SQLite bazo z vsemi metapodatki",
        "5. Centralizirano razvrscanje dodeli dogodke ustreznim portalom",
        "6. Preverjanje ze objavljenih dogodkov na portalih",
        "7. Urednik pregleda in odobri dogodke v dashboardu",
        "8. Odobreni dogodki so na voljo kot Drupal JSON za objavo",
    ]
    for s in workflow_steps:
        story.append(Paragraph(s, styles["BulletCustom"]))

    story.append(PageBreak())

    # ============================================================
    # 3. VIRI DOGODKOV
    # ============================================================
    story.append(Paragraph("3. Viri dogodkov", styles["H1"]))
    story.append(Paragraph(
        "Sistem ima 88 registriranih virov: 39 avtomatiziranih (RSS, iCal, HTML parserji) "
        "in 49 rocnih (URL shranjen, parser se naknadno razvije). "
        "Viri pokrivajo celotno Slovenijo.",
        styles["Body"]
    ))

    story.append(Paragraph("3.1 Avtomatizirani viri", styles["H2"]))

    auto_sources = [
        ["Tip", "Virov", "Primer"],
        ["kulturnik-rss", "7", "kulturnik-rss-ljubljana, -maribor, -pomurje..."],
        ["rss", "4", "ljubljana-si, tisina, ormoz, prlekija"],
        ["ical", "1", "kultura-maribor (kultura.maribor.si)"],
        ["kulturnik (JSON)", "2", "kulturnik-ljubljana, kulturnik-maribor"],
        ["mojaobcina", "4", "mojaobcina-osrednjeslovenska, -pomurska..."],
        ["visitskofjaloka", "1", "visitskofjaloka (207 dogodkov)"],
        ["kinodvor", "1", "kinodvor"],
        ["cankarjevdom", "1", "cd-cc (Cankarjev dom)"],
        ["html (genericni)", "18", "visitmaribor, stuk, visitptuj..."],
    ]
    story.append(make_table(auto_sources[0], auto_sources[1:], [3.5*cm, 2*cm, 10.5*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("3.2 Rocni viri po regijah", styles["H2"]))

    manual_regions = [
        ["Regija", "St. virov", "Primeri"],
        ["Ljubljana", "12", "Drama, Opera, MGL, Moderna galerija, Cukrarna, Bunker..."],
        ["Maribor", "7", "SNG MB, Narodni dom, UGM, Lutkovno gledalisce, GT22..."],
        ["Gorenjska", "7", "Visit Bled, Bohinj, Kranjska Gora, PGK Kranj, Radolca..."],
        ["Dolenjska/Posavje", "5", "Dolenjski muzej, KSTM Sevnica, Visit Brezice..."],
        ["Pomurje", "4", "Visit Pomurje, Visit MS, Pomurski muzej, TIC Lendava"],
        ["Ptuj/Ormoz", "3", "PMPO, Dominikanski samostan, Mestno gledalisce Ptuj"],
        ["Primorska", "7", "Visit Koper, Visit Piran, SNG Nova Gorica, GO!2025..."],
        ["Celje/Savinjska", "4", "Visit Celje, SLG Celje, Celjski dom, Pokrajinski muzej"],
    ]
    story.append(make_table(manual_regions[0], manual_regions[1:], [4*cm, 2*cm, 10*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("3.3 YAML konfiguracija vira", styles["H2"]))
    yaml_example = """source:
  id: "kulturnik-rss-ljubljana"
  name: "Kulturnik.si - Ljubljana"
  base_url: "https://dogodki.kulturnik.si"
  list_url: "https://dogodki.kulturnik.si/?where=Ljubljana"
  feed_url: "https://dogodki.kulturnik.si/?where=Ljubljana&amp;format=rss"
  region: "ljubljana"
  parser_type: "kulturnik-rss"   # ali: rss, ical, html, manual
  pagination:
    type: "query"
    max_pages: 1
  settings:
    delay_between_requests: 1
    timeout: 30"""
    story.append(Paragraph(yaml_example.replace("\n", "<br/>"), styles["CodeBlock"]))

    story.append(PageBreak())

    # ============================================================
    # 4. MEDIJI / PORTALI
    # ============================================================
    story.append(Paragraph("4. Mediji / Portali", styles["H1"]))
    story.append(Paragraph(
        "Dogodke se centralizirano zbira in nato razvrsti na 7 medijskih portalov. "
        "Vsak portal ima definirane primarne in sekundarne regije. Dogodek se lahko objavi "
        "na vec portalih hkrati.",
        styles["Body"]
    ))

    portals_data = [
        ["Portal", "URL", "Primarne regije", "Dogodkov"],
        ["Ljubljana Info", "ljubljanainfo.com", "ljubljana, osrednjeslovenska, mol", "369"],
        ["Gorenjska Info", "gorenjskainfo.com", "gorenjska", "326"],
        ["Maribor Info", "mariborinfo.com", "maribor, podravska", "132"],
        ["Dolenjska Info", "dolenjskainfo.com", "dolenjska, jugovzhodna, posavje", "47"],
        ["Sobota Info", "sobotainfo.com", "pomurska, pomurje, murska-sobota", "38"],
        ["Pomurec.com", "pomurec.com", "pomurska, pomurje, prlekija", "38"],
        ["Ptuj Info", "ptujinfo.com", "ptuj, ormoz", "38"],
    ]
    story.append(make_table(portals_data[0], portals_data[1:], [3*cm, 3.5*cm, 6*cm, 2*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Razvrscanje dogodkov:", styles["H3"]))
    story.append(Paragraph(
        "&bull; <b>Primarna regija</b>: dogodek se vedno dodeli portalu", styles["BulletCustom"]))
    story.append(Paragraph(
        "&bull; <b>Sekundarna regija</b>: samo nacionalni/vecji dogodki (kulturnik-rss-slovenija...)", styles["BulletCustom"]))
    story.append(Paragraph(
        "&bull; Dogodek se lahko pojavi na <b>vec portalih hkrati</b> (npr. pomurski na Sobotainfo IN Pomurec.com)", styles["BulletCustom"]))

    story.append(PageBreak())

    # ============================================================
    # 5. BAZA PODATKOV
    # ============================================================
    story.append(Paragraph("5. Baza podatkov", styles["H1"]))
    story.append(Paragraph("SQLite baza (data/events.db) z naslednjimi tabelami:", styles["Body"]))

    story.append(Paragraph("5.1 Tabela: events", styles["H2"]))
    events_fields = [
        ["Polje", "Tip", "Drupal mapiranje"],
        ["title", "VARCHAR(500)", "Naslov"],
        ["description", "TEXT", "Vsebina (body)"],
        ["date_start, date_end", "DATE", "Termin (zacetek/konec)"],
        ["time_start, time_end", "VARCHAR(20)", "Termin (ura)"],
        ["location", "VARCHAR(500)", "Prizorisce"],
        ["address", "VARCHAR(500)", "Naslov prizorisce"],
        ["price", "VARCHAR(200)", "Vstopnina"],
        ["organizer", "VARCHAR(300)", "Organizator"],
        ["categories", "VARCHAR(500)", "Surove kategorije iz vira"],
        ["event_type", "VARCHAR(100)", "Vrsta dogodka (standardizirana)"],
        ["target_audience", "VARCHAR(100)", "Ciljna publika"],
        ["image_url", "VARCHAR(1000)", "Slika URL"],
        ["source_url, detail_url", "VARCHAR(1000)", "Povezava do vira"],
        ["ticket_url", "VARCHAR(1000)", "Vstopnice URL"],
        ["source_id", "VARCHAR(50)", "ID vira (YAML)"],
        ["region", "VARCHAR(100)", "Regija"],
        ["dedup_hash", "VARCHAR(64)", "Hash za deduplikacijo"],
        ["completeness", "FLOAT", "Izpolnjenost (0.0-1.0)"],
        ["quality_score", "FLOAT", "Ocena kakovosti"],
    ]
    story.append(make_table(events_fields[0], events_fields[1:], [4.5*cm, 3*cm, 8.5*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("5.2 Tabela: event_media (workflow)", styles["H2"]))
    em_fields = [
        ["Polje", "Tip", "Opis"],
        ["event_id + media_id", "PK", "Povezava dogodek-portal"],
        ["status", "VARCHAR(20)", "new / approved / queued / pushed / published / skipped"],
        ["priority", "INTEGER", "0=normalen, 1=pomemben, 2=izpostavljen"],
        ["featured", "BOOLEAN", "Izpostavi na portalu (da/ne)"],
        ["editor_notes", "TEXT", "Opombe urednika"],
        ["drupal_nid", "INTEGER", "Node ID v Drupalu po objavi"],
        ["drupal_status", "VARCHAR(20)", "draft / published / unpublished"],
        ["assigned_at", "DATETIME", "Kdaj dodeljen portalu"],
        ["approved_at", "DATETIME", "Kdaj odobren"],
        ["pushed_at", "DATETIME", "Kdaj poslan v Drupal"],
        ["published_at", "DATETIME", "Kdaj objavljen"],
    ]
    story.append(make_table(em_fields[0], em_fields[1:], [4.5*cm, 3*cm, 8.5*cm]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Workflow statusi:", styles["H3"]))
    story.append(Paragraph(
        "new &rarr; approved &rarr; queued &rarr; pushed &rarr; published<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "&nbsp;&nbsp;&nbsp;&nbsp;&rarr; skipped / archived",
        styles["Body"]
    ))

    story.append(PageBreak())

    # ============================================================
    # 6. DRUPAL JSON FORMAT
    # ============================================================
    story.append(Paragraph("6. Drupal JSON format", styles["H1"]))
    story.append(Paragraph(
        "Vsak dogodek se pretvori v JSON ki mapira direktno na polja Drupal content type 'dogodek'. "
        "Metoda to_drupal() na Event modelu generira ta format.",
        styles["Body"]
    ))

    drupal_json = """{
  "type": "dogodek",
  "title": "Naša pesem &amp; Koncert 1",
  "body": {
    "value": "Nacionalno tekmovanje zborov...",
    "format": "full_html"
  },
  "field_portali": ["mariborinfo", "sobotainfo"],
  "field_prizorisce": "Unionska dvorana, Maribor",
  "field_naslov_prizorisce": "",
  "field_vrsta_dogodka": "koncert",
  "field_ciljna_publika": "vsi",
  "field_izpostavi": false,
  "field_termin": {
    "value": "2026-04-18T09:30:00",
    "end_value": "2026-04-18T11:00:00"
  },
  "field_slika": "https://..../image.jpg",
  "field_organizator": "JSKD",
  "field_cena": "Vstop prost",
  "field_vir_url": "https://kultura.maribor.si/...",
  "field_vstopnice_url": "",
  "_meta": {
    "scraper_id": 1015,
    "source_id": "kultura-maribor",
    "region": "maribor",
    "quality_score": null,
    "completeness": 0.67
  }
}"""
    story.append(Paragraph(drupal_json.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CodeBlock"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Mapiranje Drupal polj:", styles["H2"]))
    drupal_map = [
        ["Drupal polje", "JSON key", "Izvor"],
        ["Naslov", "title", "Event.title"],
        ["Vsebina (body)", "body.value", "Event.description"],
        ["Portali", "field_portali", "Event.media_outlets (seznam ID-jev)"],
        ["Prizorisce", "field_prizorisce", "Event.location"],
        ["Vrsta dogodka", "field_vrsta_dogodka", "Event.event_type ali .categories"],
        ["Ciljna publika", "field_ciljna_publika", "Event.target_audience"],
        ["Izpostavi", "field_izpostavi", "event_media.featured"],
        ["Termin", "field_termin.value/end_value", "date_start + time_start (ISO 8601)"],
        ["Slika", "field_slika", "Event.image_url"],
        ["Organizator", "field_organizator", "Event.organizer"],
        ["Cena", "field_cena", "Event.price"],
        ["Vir URL", "field_vir_url", "Event.source_url"],
        ["Vstopnice", "field_vstopnice_url", "Event.ticket_url"],
    ]
    story.append(make_table(drupal_map[0], drupal_map[1:], [3.5*cm, 5*cm, 7.5*cm]))

    story.append(PageBreak())

    # ============================================================
    # 7. API ENDPOINTI
    # ============================================================
    story.append(Paragraph("7. API endpointi", styles["H1"]))

    story.append(Paragraph("7.1 Dashboard API", styles["H2"]))
    dash_api = [
        ["Metoda", "Endpoint", "Opis"],
        ["GET", "/", "Glavni dashboard z dogodki"],
        ["GET", "/api/event/{id}", "Podrobni podatki dogodka + status po portalih"],
        ["GET", "/api/event/{id}/drupal-json", "Drupal JSON za dogodek"],
        ["GET", "/api/event/{id}/copy-text", "Formatirano besedilo za kopiranje"],
        ["POST", "/api/event/{id}/status", "Posodobi status (new/done/skipped)"],
        ["POST", "/api/event/{id}/approve", "Odobri za objavo na portalih"],
        ["POST", "/api/event/batch-approve", "Batch odobritev vec dogodkov"],
        ["GET", "/api/stats", "Statistika (dogodki, portali, viri)"],
        ["GET", "/api/stats/portals", "Podrobna statistika po portalih"],
        ["GET", "/api/health", "Zdravje vseh virov"],
    ]
    story.append(make_table(dash_api[0], dash_api[1:], [2*cm, 5.5*cm, 8.5*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("7.2 Drupal integracija API", styles["H2"]))
    drupal_api = [
        ["Metoda", "Endpoint", "Opis"],
        ["GET", "/api/drupal/{portal}/queue", "Odobreni dogodki za push v Drupal"],
        ["POST", "/api/drupal/{portal}/push", "Potrdi ustvaritev node-a (drupal_nid)"],
        ["POST", "/api/drupal/{portal}/confirm", "Potrdi objavo na portalu"],
        ["GET", "/api/drupal/{portal}/export", "Batch izvoz (JSON ali CSV)"],
    ]
    story.append(make_table(drupal_api[0], drupal_api[1:], [2*cm, 5.5*cm, 8.5*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("7.3 Primer: batch approve", styles["H2"]))
    approve_ex = """POST /api/event/batch-approve
Content-Type: application/json

{
  "event_ids": [101, 102, 103],
  "media_id": "sobotainfo",
  "featured": false,
  "priority": 1
}

Odgovor: {"ok": true, "approved": 3}"""
    story.append(Paragraph(approve_ex.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CodeBlock"]))

    story.append(PageBreak())

    # ============================================================
    # 8. AVTOMATSKA KATEGORIZACIJA
    # ============================================================
    story.append(Paragraph("8. Avtomatska kategorizacija", styles["H1"]))
    story.append(Paragraph(
        "Sistem avtomatsko kategorizira vsak nov dogodek glede na besedilo v naslovu, "
        "kategorijah in opisu. Kategorizacija se izvede ob scrapanju.",
        styles["Body"]
    ))

    story.append(Paragraph("8.1 Vrste dogodkov (event_type)", styles["H2"]))
    types_data = [
        ["Kategorija", "St.", "Vzorci za prepoznavanje"],
        ["razstava", "160", "razstav*, vizualna umetnost, exhibition"],
        ["koncert", "93", "glasba, koncert, jazz, rock, pop"],
        ["film", "83", "film, kino, cinema"],
        ["gledalisce", "40", "gledalisce, predstav*, ples, balet, opera"],
        ["delavnica", "28", "delavnic*, workshop, ustvarjaln*"],
        ["predavanje", "16", "predavanj*, okrogla miza, pogovor"],
        ["otroski", "15", "otrosk*, za otroke, pravljic*, druzin*"],
        ["festival", "14", "festival"],
        ["sport", "13", "sport, tek, pohod, maraton, turnir"],
        ["kultura", "11", "kulturna prireditev, dan odprtih vrat"],
        ["vodeni-ogled", "10", "voden ogled, vodenje"],
        ["sejem", "6", "sejem, trznic*"],
        ["zabava", "3", "zabav*, stand-up, kviz"],
        ["kulinarika", "-", "kulinar*, degustacij*, vino, cokolad*"],
        ["nekategorizirano", "272", "ni ujemanja — rocno kategorizirati"],
    ]
    story.append(make_table(types_data[0], types_data[1:], [3.5*cm, 1.5*cm, 11*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("8.2 Ciljna publika (target_audience)", styles["H2"]))
    audience_data = [
        ["Publika", "Vzorci"],
        ["otroci", "otrok*, otrosk*, pravljic*, lutkov*"],
        ["mladina", "mlad*, za mlade, mladinsk*"],
        ["druzine", "druzin*, family"],
        ["odrasli", "odrasl*, 18+"],
        ["seniorji", "senior*, upokojenc*"],
        ["strokovnjaki", "strokovn*, seminar, konferenc*"],
        ["vsi", "privzeto (ce ni ujemanja)"],
    ]
    story.append(make_table(audience_data[0], audience_data[1:], [3.5*cm, 12.5*cm]))

    story.append(PageBreak())

    # ============================================================
    # 9. DEDUPLIKACIJA
    # ============================================================
    story.append(Paragraph("9. Deduplikacija", styles["H1"]))
    story.append(Paragraph(
        "Sistem uporablja 3-nivojsko deduplikacijo za preprecevanje podvojenih dogodkov:",
        styles["Body"]
    ))

    dedup_data = [
        ["Nivo", "Metoda", "Prag", "Opis"],
        ["1", "SHA256 hash", "100%", "Eksaktno ujemanje (naslov + datum + lokacija)"],
        ["2", "Fuzzy matching", "85%", "rapidfuzz: ratio, partial_ratio, token_sort_ratio"],
        ["3", "Portal check", "80%", "Preverjanje ze objavljenih dogodkov na portalih"],
    ]
    story.append(make_table(dedup_data[0], dedup_data[1:], [1.5*cm, 3*cm, 2*cm, 9.5*cm]))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Fuzzy matching primerja naslove dogodkov na isti datum. Uporablja maksimum treh metrik "
        "(ratio, partial_ratio, token_sort_ratio) in oznaci kot duplikat ce katerakoli preseze 85%.",
        styles["Body"]
    ))

    story.append(PageBreak())

    # ============================================================
    # 10. HEALTH MONITORING
    # ============================================================
    story.append(Paragraph("10. Health monitoring", styles["H1"]))
    story.append(Paragraph(
        "Health check periodocno preverja dostopnost in delovanje vseh virov.",
        styles["Body"]
    ))

    health_statuses = [
        ["Status", "Opis", "Akcija"],
        ["healthy", "Vir deluje, vraca dogodke", "Ni potrebna"],
        ["degraded", "Dostopen, ampak 0 dogodkov ali obcasne napake", "Preveriti strukturo"],
        ["broken", "3+ zaporedne napake (HTTP 4xx/5xx, timeout)", "Popraviti parser/URL"],
        ["manual", "Ni parserja, URL shranjen v unprocessed_urls", "Razviti parser"],
        ["unknown", "Se ni bil preverjen", "Zagnati health check"],
    ]
    story.append(make_table(health_statuses[0], health_statuses[1:], [2.5*cm, 6*cm, 7.5*cm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Tabela unprocessed_urls:", styles["H2"]))
    story.append(Paragraph(
        "URL-ji ki jih scraper ne more obdelati se shranijo v bazo za prihodnje resevanje. "
        "Razlogi: no-parser, js-rendered, api-blocked, timeout, http-403, http-404.",
        styles["Body"]
    ))

    # ============================================================
    # 11. AVTENTIKACIJA
    # ============================================================
    story.append(Paragraph("11. Avtentikacija", styles["H1"]))
    story.append(Paragraph(
        "Dashboard uporablja preprosto email/geslo prijavo. Uporabniki so definirani v config/auth.yaml. "
        "Gesla so hashirana z bcrypt.",
        styles["Body"]
    ))

    story.append(Paragraph("Upravljanje uporabnikov:", styles["H2"]))
    user_cmds = """python3 manage_users.py add                  # interaktivno dodaj
python3 manage_users.py add -e email -p geslo  # z argumenti
python3 manage_users.py list                   # izpisi vse
python3 manage_users.py reset -e email         # ponastavi geslo
python3 manage_users.py remove -e email        # odstrani"""
    story.append(Paragraph(user_cmds.replace("\n", "<br/>"), styles["CodeBlock"]))

    # ============================================================
    # 12. CLI UKAZI
    # ============================================================
    story.append(Paragraph("12. CLI ukazi", styles["H1"]))

    cli_data = [
        ["Ukaz", "Opis"],
        ["python3 -m scraper.engine", "Pozeni scraping vseh virov"],
        ["python3 -m scraper.engine --source ID", "Scraping enega vira"],
        ["python3 -m scraper.health_check", "Preveri zdravje vseh virov"],
        ["python3 -m scraper.health_check --report", "Samo izpisi porocilo"],
        ["python3 -m scraper.health_check --json", "JSON porocilo"],
        ["python3 manage_users.py add/list/reset/remove", "Upravljanje uporabnikov"],
        ["python3 web/app.py", "Pozeni dashboard (port 5000)"],
    ]
    story.append(make_table(cli_data[0], cli_data[1:], [7*cm, 9*cm]))

    story.append(PageBreak())

    # ============================================================
    # 13. NAMESTITEV
    # ============================================================
    story.append(Paragraph("13. Namestitev in zagon", styles["H1"]))

    story.append(Paragraph("13.1 Sistemske zahteve", styles["H2"]))
    story.append(Paragraph("&bull; Python 3.9+", styles["BulletCustom"]))
    story.append(Paragraph("&bull; SQLite (vkljucen v Python)", styles["BulletCustom"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("13.2 Namestitev", styles["H2"]))
    install_cmd = """pip3 install -r requirements.txt

# Kljucni paketi:
# flask, sqlalchemy, requests, beautifulsoup4,
# feedparser, icalendar, rapidfuzz, bcrypt,
# cloudscraper, python-dateutil, pyyaml"""
    story.append(Paragraph(install_cmd.replace("\n", "<br/>"), styles["CodeBlock"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("13.3 Prvi zagon", styles["H2"]))
    first_run = """# 1. Inicializiraj bazo
python3 -c "from database.models import init_db; init_db()"

# 2. Dodaj uporabnika
python3 manage_users.py add

# 3. Pozeni scraping
python3 -m scraper.engine

# 4. Pozeni dashboard
python3 web/app.py

# 5. Odpri http://localhost:5000"""
    story.append(Paragraph(first_run.replace("\n", "<br/>"), styles["CodeBlock"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("13.4 Struktura projekta", styles["H2"]))
    structure = """event-scraper/
  config/
    auth.yaml              # Uporabniki in gesla
    media.yaml             # 7 portalov + seznam vseh virov
    sources/               # 88 YAML konfiguracij virov
  database/
    models.py              # SQLAlchemy modeli (Event, MediaOutlet...)
  scraper/
    engine.py              # Glavni scraping engine + parserji
    categorizer.py         # Avtomatska kategorizacija
    dedup.py               # 3-nivojska deduplikacija
    health_check.py        # Monitoring zdravja virov
    published_checker.py   # Preverjanje ze objavljenih
  web/
    app.py                 # Flask dashboard + Drupal API
    templates/             # HTML predloge
  data/
    events.db              # SQLite baza
  manage_users.py          # CLI za upravljanje uporabnikov
  requirements.txt         # Python odvisnosti"""
    story.append(Paragraph(structure.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CodeBlock"]))

    story.append(Spacer(1, 30))
    story.append(hr())
    story.append(Paragraph(
        "Event Scraper v1.0 — Dokumentacija generirana 16. 4. 2026",
        styles["Small"]
    ))

    # BUILD
    doc.build(story)
    print(f"PDF ustvarjen: {OUTPUT}")


if __name__ == "__main__":
    build()
