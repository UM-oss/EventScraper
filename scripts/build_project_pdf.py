#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generira PDF pregled projekta Event Scraper za zunanje ocenjevanje."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, ListFlowable, ListItem
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Pisave s podporo za šumnike ---
pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold",
                              italic="Arial", boldItalic="Arial-Bold")

# --- Barvna paleta ---
NAVY = colors.HexColor("#1a2238")
ACCENT = colors.HexColor("#2d6cdf")
LIGHT = colors.HexColor("#eef3fb")
GREY = colors.HexColor("#5a6473")
LINE = colors.HexColor("#d4dbe6")
GREEN = colors.HexColor("#1f9d57")

OUT = "/Users/urosmaucec/Claude/EventScraper_Pregled_Projekta.pdf"

styles = getSampleStyleSheet()

def S(name, **kw):
    base = kw.pop("parent", styles["Normal"])
    kw.setdefault("fontName", "Arial")
    return ParagraphStyle(name, parent=base, **kw)

st_title = S("t", fontName="Arial-Bold", fontSize=26, textColor=NAVY, leading=30, spaceAfter=6)
st_sub = S("s", fontSize=13, textColor=GREY, leading=18, spaceAfter=4)
st_h1 = S("h1", fontName="Arial-Bold", fontSize=15, textColor=NAVY, leading=19,
          spaceBefore=16, spaceAfter=7)
st_h2 = S("h2", fontName="Arial-Bold", fontSize=11.5, textColor=ACCENT, leading=15,
          spaceBefore=10, spaceAfter=4)
st_body = S("b", fontSize=10, textColor=colors.HexColor("#222831"), leading=15,
            alignment=TA_JUSTIFY, spaceAfter=6)
st_small = S("sm", fontSize=8.5, textColor=GREY, leading=12)
st_bullet = S("bul", fontSize=10, textColor=colors.HexColor("#222831"), leading=14)
st_cell = S("cell", fontSize=9, textColor=colors.HexColor("#222831"), leading=12.5)
st_cellb = S("cellb", fontName="Arial-Bold", fontSize=9, textColor=NAVY, leading=12.5)
st_cellw = S("cellw", fontName="Arial-Bold", fontSize=9, textColor=colors.white, leading=12.5)

story = []

def h1(t): story.append(Paragraph(t, st_h1))
def h2(t): story.append(Paragraph(t, st_h2))
def p(t): story.append(Paragraph(t, st_body))
def sp(h=6): story.append(Spacer(1, h))
def rule(): story.append(HRFlowable(width="100%", thickness=0.6, color=LINE,
                                    spaceBefore=4, spaceAfter=8))

def bullets(items):
    flow = [ListItem(Paragraph(x, st_bullet), leftIndent=6, value="•") for x in items]
    story.append(ListFlowable(flow, bulletType="bullet", start="•",
                              leftIndent=12, bulletColor=ACCENT, bulletFontSize=8))
    sp(4)

def table(data, col_widths, header=True, zebra=True):
    rows = []
    for r in data:
        rows.append([Paragraph(c, st_cellw if (header and i==0 and False) else st_cell)
                     if not isinstance(c, Paragraph) else c for i, c in enumerate(r)])
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEBELOW", (0,0), (-1,-1), 0.4, LINE),
    ]
    if header:
        cmds += [("BACKGROUND", (0,0), (-1,0), NAVY),
                 ("LINEBELOW", (0,0), (-1,0), 0.4, NAVY)]
    if zebra:
        for i in range(1, len(data)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0,i), (-1,i), LIGHT))
    t.setStyle(TableStyle(cmds))
    story.append(t)
    sp(8)

def hcell(t): return Paragraph(t, st_cellw)
def cb(t): return Paragraph(t, st_cellb)
def cc(t): return Paragraph(t, st_cell)

# ======================= NASLOVNICA =======================
sp(40)
story.append(HRFlowable(width="100%", thickness=3, color=ACCENT, spaceAfter=18))
story.append(Paragraph("Event Scraper", st_title))
story.append(Paragraph("Avtomatiziran sistem za zajem, urejanje in objavo dogodkov<br/>"
                       "za regionalne medijske portale", st_sub))
sp(10)
story.append(HRFlowable(width="38%", thickness=2, color=NAVY, spaceAfter=20))
sp(6)
story.append(Paragraph("Tehnični pregled projekta in arhitektura rešitve",
             S("x", fontName="Arial-Bold", fontSize=12.5, textColor=NAVY, leading=16)))
story.append(Paragraph("Dokument za potrebe zunanjega ocenjevanja", st_small))
sp(26)

meta = [
    [cb("Naziv projekta"), cc("Event Scraper — agregator dogodkov")],
    [cb("Tip rešitve"), cc("Spletna aplikacija (Python / Flask) z avtomatiziranim zajemom podatkov")],
    [cb("Področje uporabe"), cc("Regionalni medijski portali (uredniški delovni tok)")],
    [cb("Število virov"), cc("94 konfiguriranih virov dogodkov")],
    [cb("Produkcijska postavitev"), cc("Coolify (lasten strežnik) + Cloudflare Tunnel")],
    [cb("Status"), cc("V produkciji — javno dostopno")],
    [cb("Datum dokumenta"), cc("junij 2026")],
]
table(meta, [45*mm, 110*mm], header=False, zebra=False)

sp(10)
story.append(Paragraph(
    "Dokument opisuje namen, arhitekturo in tehnične rešitve sistema Event Scraper: "
    "od avtomatiziranega zajema dogodkov iz 94 virov, prek inteligentne deduplikacije in "
    "kategorizacije, do uredniškega vmesnika ter produkcijske postavitve na lastni "
    "infrastrukturi.", st_body))

story.append(PageBreak())

# ======================= 1. POVZETEK =======================
h1("1. Povzetek projekta")
p("Event Scraper je avtomatiziran sistem, ki vsak dan zbere dogodke iz 94 spletnih virov "
  "(spletne strani prizoriščev, RSS/iCal viri, Facebook dogodki, koledarji občin in kulturnih "
  "ustanov), jih očisti, poveže morebitne podvojene zapise, kategorizira po vsebini in pripravi "
  "v enotnem uredniškem vmesniku. Uredniki in novinarji prek spletnega nadzornega vmesnika "
  "dogodke pregledajo, dopolnijo in potrdijo za objavo na regionalnih portalih.")
p("Sistem nadomešča zamudno ročno spremljanje desetin virov in zmanjšuje tveganje za podvajanje "
  "ali spregledane dogodke. Ključne lastnosti so robusten zajem (z odpornostjo na različne "
  "tehnologije spletnih strani), inteligentna deduplikacija med viri ter optimizacija hitrosti, "
  "ki je čas celotnega zajema skrajšala za približno 2–4-krat.")

h2("Ključni dosežki")
bullets([
    "<b>Avtomatizacija:</b> dnevni zajem 94 virov brez ročnega posredovanja.",
    "<b>Kakovost podatkov:</b> deduplikacija med viri, kategorizacija in obogatitev (opisi, slike).",
    "<b>Zmogljivost:</b> ~2–4× hitrejši zajem zaradi paralelizacije in optimizacij.",
    "<b>Neodvisnost:</b> selitev na lastno infrastrukturo (Coolify), brez vezave na zunanjega ponudnika.",
    "<b>Dostopnost:</b> varen oddaljen dostop za uredništvo prek Cloudflare Tunnela.",
])

# ======================= 2. PROBLEM IN CILJI =======================
h1("2. Izhodišče, problem in cilji")
h2("Problem")
p("Regionalni mediji morajo redno objavljati napovednike dogodkov. Informacije so razpršene po "
  "desetinah spletnih strani, vsaka v svoji obliki (HTML, RSS, iCal, družbena omrežja). Ročno "
  "spremljanje je zamudno, nedosledno in podvrženo napakam — isti dogodek se pogosto pojavi pri "
  "več virih, kar vodi v podvajanje.")
h2("Cilji")
bullets([
    "Centralizirati zajem dogodkov iz vseh relevantnih virov v enoten sistem.",
    "Samodejno prepoznati in združiti podvojene zapise iste prireditve iz različnih virov.",
    "Vsebinsko kategorizirati dogodke in jih obogatiti z opisi in slikami.",
    "Uredništvu ponuditi pregleden vmesnik za potrditev in objavo.",
    "Zagotoviti hiter, zanesljiv in stroškovno učinkovit sistem na lastni infrastrukturi.",
])

# ======================= 3. ARHITEKTURA =======================
h1("3. Arhitektura sistema")
p("Sistem je zasnovan modularno in ga sestavljajo štiri glavne plasti: (1) plast zajema, "
  "(2) plast obdelave podatkov, (3) podatkovna plast in (4) predstavitvena/uredniška plast. "
  "Zajem in obdelava sta ločena, kar omogoča vzporedno mrežno pridobivanje ob hkratni "
  "doslednosti pri shranjevanju.")

h2("Pregled plasti")
arch = [
    [hcell("Plast"), hcell("Komponente"), hcell("Vloga")],
    [cb("Zajem"), cc("engine, parsers (HTML / RSS / iCal / posebni)"),
     cc("Pridobivanje surovih podatkov iz 94 virov")],
    [cb("Obdelava"), cc("dedup, categorizer, persistence, ai_description, image_fallback"),
     cc("Čiščenje, deduplikacija, kategorizacija, obogatitev")],
    [cb("Podatki"), cc("SQLAlchemy modeli, PostgreSQL, Alembic migracije"),
     cc("Trajno shranjevanje in zgodovina sprememb")],
    [cb("Uredniška"), cc("Flask aplikacija, spletni dashboard"),
     cc("Pregled, urejanje in potrditev dogodkov")],
]
table(arch, [24*mm, 66*mm, 65*mm])

h2("Podatkovni tok")
p("1) <b>Zajem</b> — vzporedno se pridobi seznam dogodkov iz vsakega vira. &nbsp; "
  "2) <b>Razčlenitev</b> — ustrezen razčlenjevalnik (parser) glede na tip vira pretvori vsebino "
  "v enotno strukturo. &nbsp; 3) <b>Obogatitev</b> — vzporedno se pridobijo podrobnosti "
  "(opis, slika) s podstrani. &nbsp; 4) <b>Deduplikacija in shranjevanje</b> — zaporedno (zaradi "
  "doslednosti) se preveri morebitno podvajanje in zapis se vstavi ali posodobi. &nbsp; "
  "5) <b>Objava</b> — urednik dogodek potrdi v dashboardu.")

story.append(PageBreak())

# ======================= 4. TEHNIČNE REŠITVE =======================
h1("4. Tehnične rešitve")

h2("4.1 Zajem podatkov (94 virov)")
p("Sistem podpira raznolike tipe virov prek namenskih razčlenjevalnikov: standardne HTML strani, "
  "RSS in Atom vire, iCal koledarje ter posebne razčlenjevalnike za specifične strani in Facebook "
  "dogodke. Mrežni sloj uporablja HTTP/2 s souporabo povezav (connection pooling), v primeru "
  "blokad (HTTP 403) pa samodejno preklopi na nadomestni način pridobivanja (cloudscraper). "
  "Skupno število hkratnih zahtevkov je omejeno (semafor), da se viri ne preobremenijo.")

h2("4.2 Deduplikacija")
p("Isti dogodek se pogosto pojavi pri več virih z drugačnim naslovom ali zapisom lokacije. "
  "Sistem najprej preveri neposredno ujemanje po identifikatorju vira, nato pa uporabi mehko "
  "(fuzzy) primerjavo naslovov (knjižnica rapidfuzz) v kombinaciji z datumom in časom. Vsaka "
  "odločitev o deduplikaciji se beleži, kar omogoča pregled in nastavljanje pragov.")

h2("4.3 Kategorizacija")
p("Novi dogodki se samodejno razvrstijo v 8 fiksnih kategorij: glasba, kultura, literatura, "
  "predstava, šport, sejmi, za otroke in ostalo. Kategorizacija se izvaja sproti ob zajemu in "
  "samo za nove dogodke, da se ohranijo morebitne uredniške prilagoditve obstoječih zapisov.")

h2("4.4 Obogatitev (opisi in slike)")
p("Kjer vir ne ponuja zadostnih podatkov, sistem obogati zapis: pridobi opis in sliko s podstrani "
  "dogodka, po potrebi pa uporabi rezervne mehanizme za slike. Uredniško urejena polja (ročni "
  "opis, ročno izbrana slika) so zaščitena in jih samodejni zajem ne prepiše.")

h2("4.5 Uredniški vmesnik")
p("Spletni nadzorni vmesnik (Flask) uredništvu omogoča pregled zajetih dogodkov, urejanje polj, "
  "filtriranje, potrjevanje za objavo in vpogled v zgodovino sprememb. Dostop je zaščiten z "
  "uporabniškimi računi in vlogami (bcrypt zgoščevanje gesel). Sistem hrani revizijsko sled "
  "sprememb (kdo/kdaj/kaj).")

h2("4.6 Uvoz iz e-pošte (v pripravi)")
p("Predvidena je tudi možnost, da organizatorji dogodek pošljejo na namenski e-naslov; sistem "
  "z branjem nabiralnika (IMAP) in jezikovnim modelom (Gemini) izlušči podatke o dogodku in ga "
  "doda v sistem. Funkcija se dokončno vključuje v produkcijsko okolje.")

# ======================= 5. OPTIMIZACIJA =======================
h1("5. Optimizacija zmogljivosti")
p("Začetni zajem je bil zaporeden in zato počasen. Izvedena je bila optimizacija v treh sklopih, "
  "ki je skupni čas zajema skrajšala za približno 2–4-krat (npr. posamezen večji vir s ~48 s na "
  "~21 s; ocenjen celotni zajem s ~15 min na ~3–4 min).")

opt = [
    [hcell("Sklop"), hcell("Ukrep"), hcell("Učinek")],
    [cb("Paralelizacija"), cc("Vzporeden zajem virov in podstrani (ThreadPool), zaporedno shranjevanje"),
     cc("Bistveno krajši skupni čas")],
    [cb("Pametno preskakovanje"), cc("Preskok ponovnega zajema za sveže in popolne dogodke"),
     cc("Manj odvečnih zahtevkov")],
    [cb("Mrežni sloj"), cc("HTTP/2, souporaba povezav, omejevanje hkratnosti"),
     cc("Hitrejši in stabilnejši prenos")],
    [cb("Baza"), cc("Indeksi in množični vnosi, predpomnjenje objavljenih dogodkov"),
     cc("Hitrejše poizvedbe in shranjevanje")],
]
table(opt, [34*mm, 76*mm, 45*mm])

# ======================= 6. PODATKOVNI MODEL =======================
h1("6. Podatkovni model")
p("Podatki so v relacijski bazi PostgreSQL, dostop poteka prek SQLAlchemy, sheme pa se "
  "nadzorovano spreminjajo z migracijami (Alembic). Namesto brisanja in ponovnega vnosa sistem "
  "uporablja vzorec UPSERT (posodobi obstoječe ali vstavi novo), dogodki, ki jih vir ne ponuja "
  "več, pa se označijo kot neaktivni — tako se ohranijo uredniški statusi in zgodovina.")
dm = [
    [hcell("Entiteta"), hcell("Namen")],
    [cb("events"), cc("Osrednji zapisi dogodkov (z metapodatki, kategorijo, stanjem)")],
    [cb("event_edits"), cc("Revizijska sled sprememb posameznih polj")],
    [cb("dedup_decisions"), cc("Beležka odločitev o deduplikaciji (za pregled in nastavljanje)")],
    [cb("media_outlets"), cc("Konfiguracija medijev / portalov")],
    [cb("users"), cc("Uporabniški računi in vloge (zgoščena gesla)")],
    [cb("scrape_logs / source_health"), cc("Dnevniki zajema in zdravje virov")],
]
table(dm, [50*mm, 105*mm])

story.append(PageBreak())

# ======================= 7. INFRASTRUKTURA =======================
h1("7. Produkcijska postavitev in infrastruktura")
p("Sistem teče na lastni infrastrukturi prek platforme Coolify (samostojno gostovan PaaS), "
  "kar zagotavlja neodvisnost od zunanjih ponudnikov in nadzor nad stroški. Aplikacija je "
  "zapakirana v Docker vsebnik (gunicorn), podatkovna baza PostgreSQL teče kot ločen vir. "
  "Ob vsaki namestitvi se samodejno izvedejo migracije baze in inicializacija.")
p("Strežnik nima javnega naslova (je za omrežnim prevajanjem), zato je javni dostop zagotovljen "
  "prek Cloudflare Tunnela — varne odhodne povezave brez odpiranja vrat. Aplikacija je dostopna "
  "na javni domeni, dostop je šifriran (HTTPS), uredniki in novinarji jo uporabljajo na daljavo.")

infra = [
    [hcell("Sklop"), hcell("Tehnologija / rešitev")],
    [cb("Gostovanje"), cc("Coolify (samostojno gostovan PaaS) na lastnem strežniku")],
    [cb("Izvajalno okolje"), cc("Docker vsebnik, gunicorn (Python 3.11)")],
    [cb("Baza"), cc("PostgreSQL (ločen vir), migracije Alembic")],
    [cb("Javni dostop"), cc("Cloudflare Tunnel + javna domena (HTTPS)")],
    [cb("Načrtovana opravila"), cc("Vgrajen razporejevalnik (APScheduler) + Coolify načrtovane naloge")],
    [cb("Različice / dostava"), cc("Git (GitHub), samodejna ponovna namestitev ob spremembi")],
]
table(infra, [42*mm, 113*mm])

h2("Avtomatizirana opravila")
bullets([
    "<b>Dnevni zajem</b> — vgrajen razporejevalnik v aplikaciji (vsak dan zjutraj).",
    "<b>Sinhronizacija objavljenih</b> — dnevno označevanje že objavljenih dogodkov (Coolify naloga).",
    "<b>Uvoz iz e-pošte</b> — periodično branje nabiralnika (v vključevanju).",
])

# ======================= 8. TEHNOLOŠKI SKLAD =======================
h1("8. Tehnološki sklad")
tech = [
    [hcell("Področje"), hcell("Tehnologije")],
    [cb("Jezik / okolje"), cc("Python 3.11")],
    [cb("Spletni okvir"), cc("Flask, gunicorn")],
    [cb("Baza / ORM"), cc("PostgreSQL, SQLAlchemy 2.0, Alembic")],
    [cb("Zajem / mreža"), cc("httpx (HTTP/2), requests, cloudscraper, BeautifulSoup, lxml, feedparser, icalendar")],
    [cb("Obdelava"), cc("rapidfuzz (deduplikacija), pydantic (validacija), APScheduler (razporejanje)")],
    [cb("Varnost"), cc("bcrypt (gesla), HTTPS prek Cloudflare")],
    [cb("Kakovost"), cc("pytest (64 testov), nadzorovane migracije sheme")],
    [cb("Infrastruktura"), cc("Docker, Coolify, Cloudflare Tunnel, Git / GitHub")],
]
table(tech, [38*mm, 117*mm])

# ======================= 9. VARNOST IN ZANESLJIVOST =======================
h1("9. Varnost, zanesljivost in kakovost")
bullets([
    "<b>Avtentikacija in vloge:</b> uporabniški računi z zgoščenimi gesli (bcrypt), ločene pravice.",
    "<b>Šifriran dostop:</b> ves promet prek HTTPS (Cloudflare), brez odprtih vrat na strežniku.",
    "<b>Ohranjanje podatkov:</b> UPSERT in označevanje neaktivnih namesto brisanja; zgodovina sprememb.",
    "<b>Odpornost zajema:</b> samodejni nadomestni mehanizmi (cloudscraper), beleženje zdravja virov.",
    "<b>Testiranje:</b> samodejni testi (pytest) ključne logike (deduplikacija, shranjevanje, kategorizacija).",
    "<b>Nadzorovane spremembe:</b> migracije baze in različice kode v Git.",
])

# ======================= 10. ZAKLJUČEK =======================
h1("10. Zaključek in nadaljnji razvoj")
p("Event Scraper je delujoča produkcijska rešitev, ki avtomatizira zamuden uredniški proces "
  "zbiranja dogodkov. Sistem je zasnovan modularno, optimiziran za hitrost in postavljen na "
  "lastni infrastrukturi, kar zagotavlja neodvisnost, nadzor nad stroški in dolgoročno "
  "vzdržnost. Arhitekturne odločitve (ločitev zajema in shranjevanja, deduplikacija, nadzorovane "
  "migracije, revizijska sled) sistem delajo razširljiv in vzdržen.")
h2("Smeri nadaljnjega razvoja")
bullets([
    "Dokončna vključitev uvoza dogodkov iz e-pošte (IMAP + jezikovni model).",
    "Razširitev nabora virov in samodejno spremljanje njihovega zdravja.",
    "Dodatne uredniške funkcije in upravljanje uporabnikov za širše uredništvo.",
    "Nadaljnja avtomatizacija objave na ciljne portale.",
])

sp(14)
story.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=6))
story.append(Paragraph(
    "Dokument je pripravljen za potrebe zunanjega ocenjevanja in povzema stanje sistema "
    "Event Scraper ob junij 2026.", st_small))


# --- glava / noga ---
def decorate(canvas, doc):
    canvas.saveState()
    w, h = A4
    # noga
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(20*mm, 14*mm, w-20*mm, 14*mm)
    canvas.setFont("Arial", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(20*mm, 9*mm, "Event Scraper — Tehnični pregled projekta")
    canvas.drawRightString(w-20*mm, 9*mm, "Stran %d" % doc.page)
    canvas.restoreState()

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm,
    title="Event Scraper — Tehnični pregled projekta",
    author="Event Scraper",
)
doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
print("PDF ustvarjen:", OUT)
