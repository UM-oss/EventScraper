#!/usr/bin/env python3
"""
Generira PDF: Event Scraper — Staff-Level Architecture Review & Renovation Plan
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, HRFlowable, ListFlowable, ListItem
)

OUTPUT = "/Users/urosmaucec/Claude/event-scraper/docs/architecture-review.pdf"

PRIMARY = HexColor("#1a1a2e")
ACCENT = HexColor("#4285F4")
LIGHT_BG = HexColor("#f8f9fa")
BORDER = HexColor("#dee2e6")
GREEN = HexColor("#28a745")
ORANGE = HexColor("#fd7e14")
RED = HexColor("#dc3545")
YELLOW_BG = HexColor("#fff3cd")
RED_BG = HexColor("#f8d7da")
GREEN_BG = HexColor("#d4edda")

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], fontSize=26, leading=32, textColor=PRIMARY, spaceAfter=4, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="DocSubtitle", parent=styles["Normal"], fontSize=13, leading=17, textColor=HexColor("#666"), spaceAfter=24, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], fontSize=18, leading=24, textColor=PRIMARY, spaceBefore=20, spaceAfter=10))
styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], fontSize=14, leading=19, textColor=HexColor("#333"), spaceBefore=14, spaceAfter=7))
styles.add(ParagraphStyle(name="H3", parent=styles["Heading3"], fontSize=11, leading=15, textColor=HexColor("#555"), spaceBefore=10, spaceAfter=5))
styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY, spaceAfter=6))
styles.add(ParagraphStyle(name="BodyBold", parent=styles["Normal"], fontSize=9.5, leading=13.5, fontName="Helvetica-Bold", spaceAfter=6))
styles.add(ParagraphStyle(name="CB", parent=styles["Code"], fontSize=8, leading=11, backColor=LIGHT_BG, borderWidth=0.5, borderColor=BORDER, borderPadding=5, spaceAfter=6, spaceBefore=3, fontName="Courier"))
styles.add(ParagraphStyle(name="BL", parent=styles["Normal"], fontSize=9.5, leading=13.5, leftIndent=18, bulletIndent=6, spaceAfter=3))
styles.add(ParagraphStyle(name="BL2", parent=styles["Normal"], fontSize=9, leading=12.5, leftIndent=36, bulletIndent=24, spaceAfter=2))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=7.5, leading=10, textColor=HexColor("#999")))
styles.add(ParagraphStyle(name="Warning", parent=styles["Normal"], fontSize=9, leading=12, backColor=YELLOW_BG, borderPadding=6, spaceAfter=8))
styles.add(ParagraphStyle(name="Critical", parent=styles["Normal"], fontSize=9, leading=12, backColor=RED_BG, borderPadding=6, spaceAfter=8))
styles.add(ParagraphStyle(name="Good", parent=styles["Normal"], fontSize=9, leading=12, backColor=GREEN_BG, borderPadding=6, spaceAfter=8))


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=10, spaceBefore=10)

def mt(headers, rows, cw=None):
    data = [headers] + rows
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8),
        ("FONTSIZE", (0,1), (-1,-1), 8),
        ("LEADING", (0,0), (-1,-1), 11),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("TOPPADDING", (0,0), (-1,0), 6),
        ("BOTTOMPADDING", (0,1), (-1,-1), 4),
        ("TOPPADDING", (0,1), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("GRID", (0,0), (-1,-1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, LIGHT_BG]),
    ]))
    return t

def b(text):
    return Paragraph(f"&bull; {text}", styles["BL"])

def b2(text):
    return Paragraph(f"- {text}", styles["BL2"])

def build():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=1.8*cm, bottomMargin=1.8*cm,
        title="Event Scraper — Architecture Review", author="Staff Architect")
    s = []
    W = A4[0] - 3.6*cm

    # === TITLE ===
    s.append(Spacer(1, 40))
    s.append(Paragraph("Event Scraper", styles["DocTitle"]))
    s.append(Paragraph("Staff-Level Architecture Review &amp; Renovation Plan", styles["DocSubtitle"]))
    s.append(hr())
    s.append(Paragraph("Pripravil: Principal Software Engineer / Staff Architect<br/>Datum: 16. april 2026<br/>Verzija dokumenta: 1.0", styles["Body"]))
    s.append(PageBreak())

    # ================================================================
    # 1. EXECUTIVE SUMMARY
    # ================================================================
    s.append(Paragraph("1. Executive Summary", styles["H1"]))
    s.append(Paragraph(
        "Event Scraper je funkcionalen MVP ki uspesno pobira ~800 prihodnjih dogodkov iz 39 avtomatiziranih virov "
        "in jih razvrsca na 7 medijskih portalov. Sistem ima delujoce parserje za RSS, iCal in vec vrst HTML strani, "
        "osnovno deduplikacijo, kategorizacijo in Drupal-kompatibilen JSON izhod. "
        "Za enega razvijalca je to soliden proof-of-concept.", styles["Body"]))
    s.append(Paragraph(
        "Vendar ima sistem <b>kriticne varnostne ranljivosti</b> (ponarejen secret_key, privzeto geslo, CSRF, debug mode), "
        "<b>arhitekturne omejitve</b> (1.500-vrsticni god object, SQLite v produkciji, ni testov, ni deployment modela) "
        "in <b>operativne vrzeli</b> (ni retry logike, ni audit traila, ni observability) ki preprecujejo produkcijsko rast. "
        "49 rocnih virov je korekten pristop — to je namenski backlog, ne napaka.", styles["Body"]))
    s.append(Paragraph(
        "Ta dokument predlaga <b>postopno prenovo brez big-bang migracije</b>: 30-dnevni plan popravlja kriticne varnostne "
        "luknje in refaktorira engine.py, 90-dnevni plan uvede PostgreSQL in background jobs, "
        "6-mesecni plan prinese polno Drupal integracijo, RBAC in observability.", styles["Body"]))

    s.append(PageBreak())

    # ================================================================
    # 2. KAJ JE DOVOLJ DOBRO ZA MVP
    # ================================================================
    s.append(Paragraph("2. Kaj je v tej zasnovi dovolj dobro za MVP", styles["H1"]))
    good_items = [
        "YAML-driven source konfiguracija — fleksibilen, razumljiv, razsirljiv model",
        "Centralizirano zbiranje + distribucija po portalih — pravilna arhitekturna odlocitev",
        "RSS/iCal parserji — zanesljivi, strukturirani viri imajo prednost pred HTML scrapingom",
        "3-nivojska deduplikacija — pravilen pristop (hash + fuzzy + portal check)",
        "Drupal JSON format — to_drupal() metoda pravilno mapira na CMS polja",
        "Kulturnik.si kot primarni vir — en agregator za ~1300 dogodkov po vseh regijah",
        "Health check modul — registracija vseh virov z monitoringom dostopnosti",
        "49 rocnih virov kot evidentirani backlog — to NI napaka, je namenski pristop",
        "Completeness score — osnovna metrika kvalitete podatkov",
        "event_media workflow statusi — pravilna zasnova za polavtomatsko objavo",
    ]
    for item in good_items:
        s.append(Paragraph(f"<font color='#28a745'>&#10003;</font> {item}", styles["BL"]))

    s.append(PageBreak())

    # ================================================================
    # 3. KLJUCNE PRODUKCIJSKE SLABOSTI
    # ================================================================
    s.append(Paragraph("3. Kljucne produkcijske slabosti", styles["H1"]))

    s.append(Paragraph("P0 — Kriticno (popraviti pred kakrsnokoli produkcijsko uporabo):", styles["Critical"]))
    p0 = [
        ["#", "Problem", "Tveganje", "Datoteka"],
        ["1", "Flask secret_key je placeholder string", "Vsakdo lahko ponaredi session cookie in se prijavi", "auth.yaml"],
        ["2", "Privzeto geslo zamenjaj-me-123 verjetno se aktivno", "Nepooblascen dostop do dashboarda", "auth.yaml"],
        ["3", "debug=True hardcoded v app.py", "Interaktivni debugger z RCE v produkciji", "app.py"],
        ["4", "Auth bypass ko je AUTH_USERS prazen", "Prazna konfiguracija = brez avtentikacije", "app.py"],
        ["5", "SQLite brez check_same_thread=False", "Threading napake pod Flask concurrent requests", "models.py"],
        ["6", "to_drupal() odpre svojo DB sejo brez finally", "Session leak, SQLite deadlock", "models.py"],
    ]
    s.append(mt(p0[0], p0[1:], [0.7*cm, 5*cm, 5.5*cm, 2.5*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("P1 — Visoka prioriteta (popraviti pred prvimi uporabniki):", styles["Warning"]))
    p1 = [
        ["#", "Problem", "Tveganje"],
        ["7", "Ni CSRF zasicte na POST endpointih", "Cross-site request forgery napadi"],
        ["8", "status parameter ni validiran proti enum", "Poljuben string v workflow statusu"],
        ["9", "request.get_json() ni null-checkan", "AttributeError na malformed requestih"],
        ["10", "engine.py je 1.519-vrsticni god object z 26 metodami", "Nemogoce testirati, vzdrzevati ali razsiriti"],
        ["11", "Ni testov — nobenih", "Vsaka sprememba je tvegana"],
        ["12", "Portal ID-ji v published_checker.py ne ujemajo z media.yaml", "Published check tiho ne dela nicesar"],
        ["13", "Ni rate limitinga na /login", "Brute-force napad na gesla"],
    ]
    s.append(mt(p1[0], p1[1:], [0.7*cm, 6*cm, 7*cm]))

    s.append(PageBreak())

    # ================================================================
    # 4. CILJNA ARHITEKTURA
    # ================================================================
    s.append(Paragraph("4. Ciljna arhitektura sistema", styles["H1"]))
    s.append(Paragraph(
        "Ciljna arhitektura loci sistem v jasne plasti: <b>ingestion</b> (pobiranje), <b>processing</b> (obdelava), "
        "<b>storage</b> (hramba), <b>distribution</b> (razvrscanje) in <b>presentation</b> (API/UI). "
        "Vsaka plast je neodvisno testabilna in zamenljiva.", styles["Body"]))

    arch = [
        ["Plast", "Odgovornost", "Moduli"],
        ["Ingestion", "HTTP fetch, feed parsing, HTML extraction", "parsers/, fetcher.py"],
        ["Normalization", "Cisticenje, standardizacija, geocoding", "normalizer.py"],
        ["Enrichment", "Kategorizacija, quality scoring", "categorizer.py, scorer.py"],
        ["Deduplication", "Hash, fuzzy, cross-source", "dedup.py"],
        ["Storage", "PostgreSQL, migracije, ORM", "db/models.py, db/migrations/"],
        ["Distribution", "Dodelitev portalom, workflow", "distributor.py"],
        ["Publishing", "Drupal push, status tracking", "publisher.py"],
        ["API", "REST endpoints, auth, validation", "api/"],
        ["Jobs", "Background tasks, scheduler, retries", "jobs/"],
        ["Admin UI", "Dashboard, uredniski vmesnik", "web/"],
    ]
    s.append(mt(arch[0], arch[1:], [2.5*cm, 5.5*cm, 5.5*cm]))

    s.append(PageBreak())

    # ================================================================
    # 5. NOVA STRUKTURA MAP
    # ================================================================
    s.append(Paragraph("5. Predlog nove strukture map in modulov", styles["H1"]))

    tree = """event-scraper/
  config/
    settings.yaml          # Globalne nastavitve (ne secrets!)
    sources/               # 88 YAML konfiguracij virov
  secrets/                 # .gitignore'd — nikoli v VCS
    .env                   # DB_URL, SECRET_KEY, DRUPAL_API_KEYS
  src/
    core/
      config.py            # Branje YAML + env vars
      exceptions.py        # Custom exception hierarhija
      logging.py           # Structured logging setup
    ingestion/
      fetcher.py           # HTTP client z retry, timeout, rate limit
      parsers/
        __init__.py         # Parser registry (avtomatski discovery)
        base.py             # BaseParser abstraktni razred
        rss_parser.py       # RSS/Atom parser
        ical_parser.py      # iCal parser
        kulturnik.py        # Kulturnik JSON + RSS
        mojaobcina.py       # MojaObcina HTML
        kinodvor.py         # Kinodvor HTML
        kinosiska.py        # Kino Siska HTML
        cankarjevdom.py     # CD HTML
        visitskofjaloka.py  # Visit Skofja Loka HTML
        generic_html.py     # Genericni HTML (iz list_selectors)
    processing/
      normalizer.py         # Text cleaning, date normalization
      categorizer.py        # Event type + audience classification
      scorer.py             # Quality + completeness scoring
      dedup.py              # Multi-layer deduplication
    distribution/
      assigner.py           # Portal assignment logic
      published_checker.py  # Ze objavljeni na portalih
    publishing/
      drupal_client.py      # Drupal REST API client
      publisher.py          # Workflow state machine
    db/
      models.py             # SQLAlchemy modeli
      migrations/           # Alembic migracije
      session.py            # Session factory, connection pool
    api/
      app.py                # FastAPI/Flask app factory
      auth.py               # Auth middleware, RBAC
      routes/
        events.py           # Event CRUD endpoints
        editorial.py        # Approve, reject, feature
        drupal.py           # Drupal integration endpoints
        monitoring.py       # Health, stats endpoints
      schemas.py            # Pydantic/Marshmallow validation
    jobs/
      scheduler.py          # APScheduler ali Celery beat
      scrape_job.py         # Periodic scraping
      health_job.py         # Periodic health check
      archive_job.py        # Cleanup preteklih dogodkov
    web/
      templates/            # Jinja2 templates
      static/               # CSS, JS
  tests/
    unit/
    integration/
    fixtures/               # HTML snapshots za parser teste
    conftest.py
  alembic.ini
  pyproject.toml
  Dockerfile
  docker-compose.yml"""
    s.append(Paragraph(tree.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CB"]))

    s.append(Paragraph(
        "<b>Kljucna sprememba:</b> Parserji so posamezni moduli z skupnim vmesnikom (BaseParser). "
        "engine.py se razgradi v vec modulov. Vsak parser je neodvisno testabilen s HTML fixture datotekami. "
        "Registry pattern omogoca dodajanje novih parserjev brez spreminjanja dispatch kode.", styles["Body"]))

    s.append(PageBreak())

    # ================================================================
    # 6. POSTGRESQL SHEMA
    # ================================================================
    s.append(Paragraph("6. Predlog podatkovnega modela — PostgreSQL", styles["H1"]))
    s.append(Paragraph(
        "<b>Zakaj PostgreSQL namesto SQLite:</b> (1) Concurrent write access — SQLite ima en writer naenkrat, "
        "Flask/Gunicorn imata vec workerjev. (2) Full-text search za iskanje dogodkov. (3) JSONB za fleksibilna polja. "
        "(4) ENUM tipi za workflow statuse. (5) Alembic migracije. (6) Connection pooling. "
        "(7) Row-level locking za concurrent editorial workflow.", styles["Body"]))

    tables = [
        ["Tabela", "Namen", "Kljucna polja", "Indeksi"],
        ["events", "Centralni model dogodka",
         "id SERIAL PK, title, description TEXT, date_start DATE NOT NULL, date_end, time_start, time_end, "
         "location, address, lat FLOAT, lng FLOAT, price, organizer, image_url, source_url, detail_url, ticket_url, "
         "event_type VARCHAR(50), target_audience VARCHAR(50), categories JSONB, "
         "region VARCHAR(50), source_id FK, dedup_hash VARCHAR(64) UNIQUE, "
         "completeness FLOAT, quality_score FLOAT, raw_data JSONB, "
         "created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ",
         "idx_date_start, idx_dedup_hash (UNIQUE), idx_source_id, idx_region, idx_event_type, "
         "idx_fulltext (GIN on title||description)"],

        ["event_versions", "Verzioniranje sprememb dogodka",
         "id SERIAL PK, event_id FK, version INT, changed_fields JSONB, "
         "changed_by VARCHAR(100), changed_at TIMESTAMPTZ, change_type ENUM(scraped,edited,merged)",
         "idx_event_versions_event_id"],

        ["event_media", "Povezava dogodek-portal z workflowom",
         "event_id FK + media_id FK = COMPOSITE PK, status ENUM(new,approved,queued,pushed,published,skipped,archived), "
         "priority SMALLINT DEFAULT 0, featured BOOLEAN DEFAULT false, editor_notes TEXT, "
         "drupal_nid INT, drupal_status VARCHAR(20), "
         "assigned_at, approved_at, approved_by, pushed_at, published_at TIMESTAMPTZ",
         "idx_em_status, idx_em_media_status (media_id, status)"],

        ["media_outlets", "7 medijskih portalov",
         "id VARCHAR(50) PK, name, url, primary_regions JSONB, secondary_regions JSONB, "
         "drupal_api_url, active BOOLEAN DEFAULT true",
         ""],

        ["sources", "88 registriranih virov",
         "id VARCHAR(50) PK, name, base_url, list_url, feed_url, region, parser_type, "
         "config JSONB, active BOOLEAN, priority SMALLINT, notes TEXT, created_at, updated_at",
         "idx_sources_parser_type, idx_sources_active"],

        ["source_runs", "Dnevnik vsakega scrape runa",
         "id SERIAL PK, source_id FK, started_at, finished_at TIMESTAMPTZ, "
         "status ENUM(running,success,error,skipped), events_found INT, events_new INT, events_dup INT, "
         "error_message TEXT, duration_ms INT",
         "idx_source_runs_source_id, idx_source_runs_started_at"],

        ["source_health", "Tekoci zdravstveni status vira",
         "source_id FK PK, status ENUM(healthy,degraded,broken,manual,unknown), "
         "last_check, last_success, last_error TIMESTAMPTZ, last_error_msg TEXT, "
         "consecutive_errors INT, avg_events_7d FLOAT, total_events_30d INT, "
         "reliability_score FLOAT",
         "idx_health_status"],

        ["users", "Uporabniki sistema",
         "id SERIAL PK, email VARCHAR(255) UNIQUE NOT NULL, name, password_hash, "
         "role ENUM(admin,editor,viewer), active BOOLEAN, last_login TIMESTAMPTZ, "
         "created_at, updated_at",
         "idx_users_email (UNIQUE)"],

        ["audit_log", "Revizijska sled vseh akcij",
         "id BIGSERIAL PK, user_id FK, action VARCHAR(50), entity_type VARCHAR(50), entity_id INT, "
         "old_values JSONB, new_values JSONB, ip_address INET, user_agent TEXT, created_at TIMESTAMPTZ",
         "idx_audit_entity (entity_type, entity_id), idx_audit_user, idx_audit_created_at"],

        ["publication_attempts", "Dnevnik Drupal push poskusov",
         "id SERIAL PK, event_id FK, media_id FK, attempt_num INT, "
         "action ENUM(create,update,unpublish), status ENUM(success,error,timeout), "
         "drupal_nid INT, response_code INT, response_body TEXT, attempted_at TIMESTAMPTZ",
         "idx_pub_event_media"],

        ["parser_backlog", "Backlog virov brez parserja",
         "id SERIAL PK, source_id FK, url, reason VARCHAR(50), content_type VARCHAR(50), "
         "page_title, response_code INT, complexity_estimate SMALLINT, "
         "priority SMALLINT, assigned_to VARCHAR(100), "
         "status ENUM(pending,in_progress,resolved,wont_fix), resolution TEXT, "
         "discovered_at, resolved_at TIMESTAMPTZ",
         "idx_backlog_status, idx_backlog_priority"],
    ]
    s.append(mt(tables[0], tables[1:], [2.2*cm, 3.5*cm, 6*cm, 4*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("<b>Migracija SQLite → PostgreSQL:</b>", styles["BodyBold"]))
    s.append(b("Uporabi Alembic za schema migracije od zacetka"))
    s.append(b("Zapisi migracijski skript ki prebere SQLite in vstavi v PostgreSQL"))
    s.append(b("Vzdrzuj dual-write obdobje: 1 teden pisanja v obe bazi, nato prerez"))
    s.append(b("raw_data JSONB polje hrani celoten surovi odgovor parserja za debugging"))

    s.append(PageBreak())

    # ================================================================
    # 7. WORKFLOW STATE MACHINE
    # ================================================================
    s.append(Paragraph("7. Predlog workflow state machine", styles["H1"]))

    s.append(Paragraph("7.1 Event-Media workflow (event_media.status):", styles["H2"]))
    wf = [
        ["Iz stanja", "V stanje", "Kdo", "Pogoj", "Audit"],
        ["new", "approved", "editor, admin", "Urednik pregleda in odobri", "Da"],
        ["new", "skipped", "editor, admin", "Ni relevantno za portal", "Da"],
        ["approved", "queued", "system", "Drupal client pobere iz queue", "Da"],
        ["approved", "new", "editor, admin", "Urednik prekliče odobritev", "Da"],
        ["queued", "pushed", "system", "Drupal vrne 2xx + nid", "Da"],
        ["queued", "approved", "system", "Drupal vrne napako, retry later", "Da"],
        ["pushed", "published", "system/drupal", "Drupal potrdi objavo", "Da"],
        ["pushed", "queued", "admin", "Ponoven push potreben", "Da"],
        ["published", "archived", "system", "Dogodek je minil", "Ne"],
        ["*", "archived", "system", "date_end < today - 7 dni", "Ne"],
    ]
    s.append(mt(wf[0], wf[1:], [2*cm, 2*cm, 2.5*cm, 5*cm, 1.2*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("7.2 Neveljavni prehodi (PREPOVEDANO):", styles["H2"]))
    invalid = [
        ["Prehod", "Razlog"],
        ["new -> pushed", "Preskoci odobritev — urednik MORA pregledati"],
        ["new -> published", "Preskoci celoten workflow"],
        ["skipped -> approved", "Preskozen dogodek potrebuje review, ne re-approve"],
        ["published -> new", "Objavljeni dogodek se ne more vrniti na zacetek"],
        ["archived -> *", "Arhivirani dogodki so zakljuceni"],
        ["* -> approved (brez editor-ja)", "Samo clovek lahko odobri"],
    ]
    s.append(mt(invalid[0], invalid[1:], [3.5*cm, 10.5*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph(
        "<b>Implementacija:</b> StateMachine razred z dovoljenimi prehodi kot dict. Vsak prehod klice validate_transition() "
        "ki preveri: (1) ali je prehod dovoljen, (2) ali ima uporabnik pravico, (3) zapise audit log. "
        "Ni vec golega db.execute(update().values(status=X)) brez validacije.", styles["Body"]))

    s.append(PageBreak())

    # ================================================================
    # 8. API REDESIGN
    # ================================================================
    s.append(Paragraph("8. Predlog API redesigna", styles["H1"]))
    s.append(Paragraph(
        "Trenutni API ima nekonsistentne odgovore, manjka validacija, CSRF in auth na nekaterih endpointih. "
        "Predlagam prehod na verzioniran REST API z jasno locenim public/internal/admin delom.", styles["Body"]))

    api_design = [
        ["Metoda", "Endpoint", "Namen", "Auth", "Idempotent"],
        ["GET", "/api/v1/events", "Seznam dogodkov s filtri in paginacijo", "editor+", "Da"],
        ["GET", "/api/v1/events/{id}", "Podrobni podatki dogodka", "editor+", "Da"],
        ["PATCH", "/api/v1/events/{id}", "Ureditev polj dogodka", "editor+", "Da (If-Match)"],
        ["POST", "/api/v1/events/{id}/approve", "Odobritev za portale", "editor+", "Da (idempotent key)"],
        ["POST", "/api/v1/events/{id}/skip", "Preskok dogodka", "editor+", "Da"],
        ["POST", "/api/v1/events/batch", "Batch operacija (approve/skip)", "editor+", "Ne"],
        ["GET", "/api/v1/portals", "Seznam portalov s statistiko", "viewer+", "Da"],
        ["GET", "/api/v1/portals/{id}/queue", "Odobreni za push", "service", "Da"],
        ["POST", "/api/v1/portals/{id}/ack", "Potrditev uspesne objave", "service", "Da (nid)"],
        ["GET", "/api/v1/portals/{id}/export", "CSV/JSON export", "editor+", "Da"],
        ["GET", "/api/v1/sources", "Seznam virov z zdravjem", "viewer+", "Da"],
        ["GET", "/api/v1/stats", "Statistika sistema", "viewer+", "Da"],
        ["GET", "/api/v1/audit", "Audit log z filtri", "admin", "Da"],
        ["POST", "/api/v1/auth/login", "Prijava", "none", "Ne"],
        ["POST", "/api/v1/auth/logout", "Odjava", "any", "Da"],
    ]
    s.append(mt(api_design[0], api_design[1:], [1.5*cm, 4*cm, 4*cm, 2*cm, 2.5*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("Primer request/response za POST /api/v1/events/{id}/approve:", styles["H3"]))
    approve_ex = """Request:
  POST /api/v1/events/123/approve
  Authorization: Bearer {token}
  Content-Type: application/json
  X-Idempotency-Key: uuid-here
  {
    "portal_ids": ["sobotainfo", "pomurec"],
    "featured": true,
    "priority": 2,
    "editor_notes": "Festival - izpostaviti"
  }

Response 200:
  {
    "event_id": 123,
    "transitions": [
      {"portal": "sobotainfo", "from": "new", "to": "approved"},
      {"portal": "pomurec", "from": "new", "to": "approved"}
    ]
  }

Response 409 (conflict):
  {
    "error": "invalid_transition",
    "message": "Event 123 is already approved for sobotainfo",
    "current_status": "approved"
  }"""
    s.append(Paragraph(approve_ex.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CB"]))

    s.append(PageBreak())

    # ================================================================
    # 9. DEDUPLIKACIJA
    # ================================================================
    s.append(Paragraph("9. Predlog izboljsane deduplikacije", styles["H1"]))
    s.append(Paragraph(
        "<b>Trenutni problem:</b> Fuzzy matching z 'ce katerakoli metrika preseze 85%' je pregrobo. "
        "partial_ratio('Festival Ljubljana', 'Festival Ljubljana presents: Nocturne') = 100%, "
        "kar bo oznacilo dva razlicna dogodka kot duplikat.", styles["Body"]))

    s.append(Paragraph("9.1 Predlagani vec-slojni pipeline:", styles["H2"]))
    dedup_layers = [
        ["Sloj", "Metoda", "Prag", "Rezultat"],
        ["1. Canonical hash", "SHA256(canonical_title + date)", "100%", "Auto-merge"],
        ["2. Title similarity", "Weighted: 0.4*ratio + 0.3*token_sort + 0.3*partial", ">=92%", "Auto-merge"],
        ["3. Title similarity", "Isti weighted score", "80-92%", "Manual review"],
        ["4. Organizer match", "Ce isti organizator + isti datum + location overlap", ">=75% title", "Auto-merge"],
        ["5. Cross-source", "Ce razlicen vir + isti datum + >=88% title", "N/A", "Auto-merge"],
        ["6. Low confidence", "Score pod 80%", "N/A", "Keep separate"],
    ]
    s.append(mt(dedup_layers[0], dedup_layers[1:], [2.5*cm, 5.5*cm, 2*cm, 3*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("9.2 Canonicalization:", styles["H2"]))
    s.append(b("Lowercase + strip diakritike (c->c, s->s, z->z)"))
    s.append(b("Odstrani locila in odvecne presledke"))
    s.append(b("Odstrani stop words: 'v', 'na', 'za', 'in', 'z', 'ob', 'pri', 'do'"))
    s.append(b("Normaliziraj organizatorje: 'SNG Drama Lj.' -> 'sng drama ljubljana'"))
    s.append(b("Normaliziraj lokacije: 'CD, Gallusova dvorana' -> 'cankarjev dom gallusova dvorana'"))

    s.append(Spacer(1, 8))
    s.append(Paragraph("9.3 Duplicate confidence score:", styles["H2"]))
    s.append(Paragraph(
        "Vsak potencialni duplikat dobi <b>confidence score 0.0-1.0</b> izracunan kot:<br/>"
        "score = 0.40 * title_sim + 0.25 * date_match + 0.20 * location_sim + 0.15 * organizer_sim<br/>"
        "Kjer je date_match: 1.0 ce isti datum, 0.5 ce +/-1 dan, 0.0 sicer.<br/>"
        "Auto-merge: score >= 0.92 | Manual review: 0.75-0.92 | Keep separate: &lt; 0.75", styles["Body"]))

    s.append(PageBreak())

    # ================================================================
    # 10. KATEGORIZACIJA
    # ================================================================
    s.append(Paragraph("10. Predlog izboljsane kategorizacije", styles["H1"]))
    s.append(Paragraph(
        "<b>Trenutni problem:</b> Golo keyword matching z 'if pattern in search_text' proizvaja false positive-e. "
        "'pop' ujame 'popularen', 'trg' ujame 'treking'. Default 'vsi' za target_audience je semanticno napacen — "
        "pomeni 'ne vemo', ne 'za vse'.", styles["Body"]))

    s.append(Paragraph("10.1 Izboljsan sistem:", styles["H2"]))
    s.append(b("<b>Word boundary matching:</b> Uporabi regex \\bpattern\\b namesto substring in"))
    s.append(b("<b>Weighted patterns:</b> Vsak vzorec ima utez (0.0-1.0), koncni score je sestevek"))
    s.append(b("<b>Multi-label:</b> Dogodek ima lahko vec tipov: ['koncert', 'festival']"))
    s.append(b("<b>Confidence score:</b> 0.0-1.0 za vsako kategorijo, ne samo da/ne"))
    s.append(b("<b>Unknown namesto 'vsi':</b> Ce ni ujemanja, nastavi 'unknown' — urednik dopolni"))
    s.append(b("<b>Synonym dictionary:</b> 'jazz' -> koncert (0.9), 'jazz festival' -> festival (0.95)"))
    s.append(b("<b>Editor feedback loop:</b> Ko urednik popravi kategorijo, belezi kot training data"))
    s.append(b("<b>Lemmatizacija:</b> classla ali lemmagen za slovenscino (dolgorocno)"))

    s.append(Spacer(1, 8))
    s.append(Paragraph("10.2 Primer confidence score:", styles["H2"]))
    cat_ex = """Naslov: "Jazz festival Maribor 2026"
Kategorije iz vira: "Glasba, Festivali"

Matched patterns:
  "jazz"     -> koncert  (weight=0.7, boundary=True)
  "festival" -> festival (weight=0.9, boundary=True)
  "glasba"   -> koncert  (weight=0.8, boundary=True, from categories)

Result:
  event_type: ["festival", "koncert"]
  confidence: {"festival": 0.90, "koncert": 0.75}
  primary_type: "festival"  (highest confidence)"""
    s.append(Paragraph(cat_ex.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CB"]))

    s.append(PageBreak())

    # ================================================================
    # 11. QUALITY SCORING
    # ================================================================
    s.append(Paragraph("11. Predlog quality scoring modela", styles["H1"]))
    s.append(Paragraph(
        "Trenutni completeness score steje izpolnjena polja. Potrebujemo vec-dimenzionalen quality score "
        "ki uposteva vsebino, vir, in konsistentnost.", styles["Body"]))

    s.append(Paragraph("11.1 Formula:", styles["H2"]))
    scoring = """quality_score = (
    0.15 * has_title +              # 1.0 ce obstaja, 0.0 sicer
    0.20 * description_quality +    # min(len(desc)/200, 1.0) — daljsi opis = boljsi
    0.15 * has_date_and_time +      # 1.0 ce oba, 0.5 ce samo datum, 0.0 sicer
    0.10 * has_location +           # 1.0 ce obstaja, 0.0 sicer
    0.10 * has_image +              # 1.0 ce obstaja IN je dosegljiva, 0.0 sicer
    0.05 * has_organizer +          # 1.0 ce obstaja, 0.0 sicer
    0.05 * has_price_info +         # 1.0 ce obstaja (tudi "vstop prost"), 0.0 sicer
    0.05 * has_category +           # 1.0 ce event_type != null/unknown, 0.0 sicer
    0.10 * source_reliability +     # source_health.reliability_score (0.0-1.0)
    0.05 * freshness               # 1.0 ce scraped < 24h, 0.5 < 7d, 0.0 sicer
)

Penalizacije:
  -0.10 ce dedup_confidence med 0.75-0.92 (potencialni duplikat)
  -0.20 ce image_url vrne 404
  -0.05 ce date_start < today (pretekel dogodek ki je se v bazi)"""
    s.append(Paragraph(scoring.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CB"]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("11.2 Source reliability score:", styles["H2"]))
    src_score = [
        ["Metrika", "Utez", "Izracun"],
        ["Uspesnost scrapanja", "0.30", "success_runs / total_runs (30 dni)"],
        ["Povprecno stevilo dogodkov", "0.20", "min(avg_events / 20, 1.0)"],
        ["Konsistentnost", "0.20", "1.0 - (stddev_events / avg_events)"],
        ["Casovna stabilnost", "0.15", "dni_od_zadnjega_outage / 30"],
        ["Podatkovni coverage", "0.15", "avg_completeness vseh dogodkov iz vira"],
    ]
    s.append(mt(src_score[0], src_score[1:], [3.5*cm, 1.5*cm, 9*cm]))

    s.append(PageBreak())

    # ================================================================
    # 12. VARNOSTNI MODEL
    # ================================================================
    s.append(Paragraph("12. Predlog varnostnega modela", styles["H1"]))

    sec_items = [
        ["Podrocje", "Trenutno stanje", "Predlog"],
        ["Uporabniki", "YAML datoteka, en nivo", "PostgreSQL users tabela z RBAC (admin/editor/viewer)"],
        ["Secret key", "Placeholder v YAML", "Env var FLASK_SECRET_KEY, generiran z secrets.token_hex(32)"],
        ["Gesla", "bcrypt v YAML", "bcrypt v bazi, password reset flow z email tokenji"],
        ["CSRF", "Ni zaiscite", "Flask-WTF CSRF tokeni na vseh POST formah"],
        ["Session mgmt", "Flask session, ni expiry", "Session expiry 8h, secure + httponly cookie flags"],
        ["Service auth", "Ni — Drupal endpointi so odprti", "API key ali JWT za Drupal service-to-service"],
        ["Secrets storage", "V YAML datotekah", ".env datoteka (gitignored), env vars v produkciji"],
        ["Rate limiting", "Ni", "Flask-Limiter: 5 /login/min, 100 req/min/user"],
        ["Audit", "Ni", "audit_log tabela z vsako status spremembo, prijavo, odobritvijo"],
        ["debug mode", "Hardcoded True", "Env var FLASK_DEBUG=0, nikoli True v produkciji"],
    ]
    s.append(mt(sec_items[0], sec_items[1:], [2.5*cm, 4.5*cm, 7.5*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("12.1 RBAC model:", styles["H2"]))
    rbac = [
        ["Vloga", "Pravice"],
        ["viewer", "Bere dogodke, statistiko, health — NE more odobravati ali urejati"],
        ["editor", "Vse viewer + approve, skip, feature, edit, batch operations"],
        ["admin", "Vse editor + user management, source config, audit log, force status changes"],
        ["service", "Samo Drupal queue/ack endpointi — API key auth, brez session"],
    ]
    s.append(mt(rbac[0], rbac[1:], [2*cm, 12*cm]))

    s.append(PageBreak())

    # ================================================================
    # 13. AUDIT TRAIL
    # ================================================================
    s.append(Paragraph("13. Predlog audit traila", styles["H1"]))
    s.append(Paragraph(
        "Vsaka uredniška in sistemska akcija mora biti zabelezena v audit_log tabeli. "
        "To omogoca: (1) forenzicno analizo, (2) undo operacij, (3) compliance, (4) debugging workflowa.", styles["Body"]))

    audit_events = [
        ["Akcija", "Entity", "Podatki"],
        ["user.login", "user", "email, ip, user_agent, success/fail"],
        ["user.logout", "user", "email"],
        ["user.created", "user", "email, role, created_by"],
        ["event.approved", "event_media", "event_id, media_id, approved_by, featured, priority"],
        ["event.skipped", "event_media", "event_id, media_id, skipped_by, reason"],
        ["event.status_changed", "event_media", "event_id, media_id, from_status, to_status, changed_by"],
        ["event.edited", "event", "event_id, changed_fields (old + new values)"],
        ["event.featured", "event_media", "event_id, media_id, featured_by"],
        ["drupal.pushed", "publication_attempts", "event_id, media_id, drupal_nid, response_code"],
        ["drupal.push_failed", "publication_attempts", "event_id, media_id, error_message"],
        ["source.config_changed", "sources", "source_id, changed_fields"],
        ["scrape.completed", "source_runs", "source_id, events_found, events_new, duration"],
        ["system.dedup_merge", "events", "kept_event_id, merged_event_id, confidence_score"],
    ]
    s.append(mt(audit_events[0], audit_events[1:], [3*cm, 3*cm, 8.5*cm]))

    s.append(PageBreak())

    # ================================================================
    # 14. OBSERVABILITY IN DEPLOYMENT
    # ================================================================
    s.append(Paragraph("14. Predlog observability in deployment modela", styles["H1"]))

    s.append(Paragraph("14.1 Containerizacija:", styles["H2"]))
    docker = """# docker-compose.yml
services:
  web:                    # Flask/FastAPI app (Gunicorn, 2 workers)
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db, redis]

  worker:                 # Background job worker (scraping, health checks)
    build: .
    command: python -m jobs.worker
    env_file: .env
    depends_on: [db, redis]

  scheduler:              # Cron scheduler (APScheduler)
    build: .
    command: python -m jobs.scheduler
    env_file: .env

  db:                     # PostgreSQL 16
    image: postgres:16-alpine
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:                  # Job queue + cache
    image: redis:7-alpine"""
    s.append(Paragraph(docker.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CB"]))

    s.append(Paragraph("14.2 Background jobs:", styles["H2"]))
    jobs = [
        ["Job", "Interval", "Trenutno", "Predlog"],
        ["Scrape all sources", "6h", "Sinhroni CLI (python -m scraper.engine)", "RQ/Celery job z retry"],
        ["Health check", "1h", "Sinhroni CLI", "Background job"],
        ["Categorize uncategorized", "Po vsakem scrape runu", "Inline v scrape", "Post-scrape hook"],
        ["Archive past events", "1x/dan", "Ni implementirano", "Nightly job"],
        ["Quality score recalc", "1x/dan", "Inline ob scrapanju", "Nightly batch job"],
        ["Published check", "Pred vsakim scrapom", "Inline", "Locen pre-scrape job"],
        ["Image URL validation", "1x/teden", "Ni implementirano", "Weekly job"],
        ["Drupal push queue", "5min", "Ni implementirano", "Periodic job"],
    ]
    s.append(mt(jobs[0], jobs[1:], [3.5*cm, 2*cm, 4*cm, 4.5*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("14.3 Structured logging + Metrics:", styles["H2"]))
    s.append(b("structlog za JSON loge z correlation ID-ji"))
    s.append(b("Sentry za error tracking (brezplacen za open source)"))
    s.append(b("Prometheus metrics: scrape_duration, events_per_source, dedup_matches, api_latency"))
    s.append(b("Healthcheck endpoint /health za load balancer"))
    s.append(b("Alert: ce source_health.consecutive_errors >= 3 (email ali Slack webhook)"))

    s.append(Spacer(1, 8))
    s.append(Paragraph("14.4 Backup:", styles["H2"]))
    s.append(b("PostgreSQL: pg_dump daily (7 dni retencije)"))
    s.append(b("Source YAML configs: git versioned"))
    s.append(b("Secrets: nikoli v gitu — env vars ali secrets manager"))

    s.append(PageBreak())

    # ================================================================
    # 15. TESTNA STRATEGIJA
    # ================================================================
    s.append(Paragraph("15. Predlog testne strategije", styles["H1"]))

    test_pyramid = [
        ["Nivo", "St. testov", "Kaj testiramo", "Orodja"],
        ["Unit", "~80", "Canonicalization, date parsing, categorizer, scorer, dedup logic, state machine", "pytest"],
        ["Parser fixtures", "~20", "Vsak parser z shranjenim HTML/RSS/iCal snapshotom", "pytest + fixtures/"],
        ["Snapshot", "~10", "HTML extraction ne producira regresij", "pytest-snapshot"],
        ["Contract", "~5", "Drupal JSON payload shape ostane stabilen", "pytest + jsonschema"],
        ["Integration", "~15", "API endpoints, DB operations, auth flow", "pytest + TestClient"],
        ["E2E workflow", "~5", "Celoten flow: scrape -> categorize -> assign -> approve -> export", "pytest"],
        ["Migration", "~3", "Alembic up + down migracije so reversibilne", "pytest + alembic"],
        ["Performance", "~3", "Dedup z 10k eventi, categorizer z 5k eventi", "pytest-benchmark"],
    ]
    s.append(mt(test_pyramid[0], test_pyramid[1:], [2.5*cm, 2*cm, 6*cm, 3.5*cm]))

    s.append(Spacer(1, 8))
    s.append(Paragraph("Primer parser fixture testa:", styles["H3"]))
    test_ex = """# tests/fixtures/kinodvor_2026_04.html — shranjen HTML snapshot
# tests/unit/test_kinodvor_parser.py

def test_kinodvor_extracts_events():
    html = Path("tests/fixtures/kinodvor_2026_04.html").read_text()
    parser = KinodvorParser()
    events = parser.parse(html, config)

    assert len(events) >= 10
    assert events[0]["title"] is not None
    assert events[0]["date_start"] is not None
    assert events[0]["image_url"].startswith("http")"""
    s.append(Paragraph(test_ex.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), styles["CB"]))

    s.append(PageBreak())

    # ================================================================
    # 16-18. 30/90/180 DNEVNI PLAN
    # ================================================================
    s.append(Paragraph("16. 30-dnevni plan", styles["H1"]))
    d30 = [
        ["Teden", "Naloga", "Rezultat"],
        ["1", "P0 varnostne popravke: secret_key, geslo, debug, auth bypass, check_same_thread", "Sistem varen za prvo uporabo"],
        ["1", "Fix to_drupal() session leak — prenesi featured kot parameter", "Ni vec session leakov"],
        ["1", "Fix published_checker portal ID-ji — sinhroniziraj z media.yaml", "Published check dejansko dela"],
        ["2", "Razbij engine.py: izvleci parserje v locene module (parsers/)", "Vsak parser je svoja datoteka"],
        ["2", "Parser registry pattern: config.parser_type -> avtomatski lookup", "Dodajanje parserja brez spreminjanja dispatch"],
        ["2", "Dodaj CSRF zaiscito (Flask-WTF)", "POST endpointi zasciteni"],
        ["3", "Osnovna testna infrastruktura: pytest setup, 5 parser fixture testov", "CI-ready test suite"],
        ["3", "Input validacija na vseh API endpointih", "Ni vec AttributeError na malformed requestih"],
        ["3", "Status enum validacija v workflow", "Nemogoc neveljaven status"],
        ["4", "Dockerfile + docker-compose za lokalni dev", "Reproducibilno okolje"],
        ["4", "Alembic setup za migracije (se vedno SQLite)", "Schema migracije od zdaj naprej"],
        ["4", "Structured logging z structlog", "JSON logi z correlation ID"],
    ]
    s.append(mt(d30[0], d30[1:], [1.5*cm, 8*cm, 4.5*cm]))

    s.append(Spacer(1, 12))
    s.append(Paragraph("17. 90-dnevni plan", styles["H1"]))
    d90 = [
        ["Mesec", "Naloga", "Rezultat"],
        ["2", "PostgreSQL migracija z dual-write obdobjem", "Robustna baza za concurrent access"],
        ["2", "RBAC: users tabela, admin/editor/viewer vloge", "Granularen dostop"],
        ["2", "Audit log tabela + middleware", "Revizijska sled vseh akcij"],
        ["2", "Background jobs z RQ ali Celery (scraping, health check)", "Asinhrono scraping"],
        ["3", "Izboljsana deduplikacija: canonicalization + weighted scoring + confidence", "Manj false positive/negative"],
        ["3", "Izboljsana kategorizacija: word boundary + multi-label + confidence", "Bolj natancna klasifikacija"],
        ["3", "Quality scoring model", "Prioritizacija po kakovosti"],
        ["3", "Source backlog management: prioritizacija, complexity estimate", "Sistematicno resevanje rocnih virov"],
        ["3", "Sentry integracija za error tracking", "Proaktivno odkrivanje napak"],
        ["3", "Staging okolje na VPS", "Testiranje pred produkcijo"],
    ]
    s.append(mt(d90[0], d90[1:], [1.5*cm, 8*cm, 4.5*cm]))

    s.append(Spacer(1, 12))
    s.append(Paragraph("18. 6-mesecni plan", styles["H1"]))
    d180 = [
        ["Mesec", "Naloga", "Rezultat"],
        ["4", "Drupal push integracija (dejanski REST API calls)", "Polavtomatska objava"],
        ["4", "Image proxy/cache (namesto hotlinkanja)", "Ni vec pravnih/operativnih tveganj s slikami"],
        ["4", "Event versioning (event_versions tabela)", "Zgodovina sprememb"],
        ["5", "FastAPI migracija (postopna, route-by-route)", "Async, boljsa validacija, OpenAPI docs"],
        ["5", "Prometheus metrics + Grafana dashboard", "Operativna vidljivost"],
        ["5", "Avtomatizacija 10-15 rocnih virov (WordPress /feed/, iCal discovery)", "Vec avtomatiziranih virov"],
        ["6", "Geocoding lokacij (Nominatim)", "Lokacijska preciznost"],
        ["6", "ML kategorizacija (classla za slovenscino)", "Natancna klasifikacija brez keyword matchinga"],
        ["6", "Multi-tenant: priprava za nove medije/portale", "Skalabilnost"],
    ]
    s.append(mt(d180[0], d180[1:], [1.5*cm, 8*cm, 4.5*cm]))

    s.append(PageBreak())

    # ================================================================
    # 19. TOP 15 PRIORITET
    # ================================================================
    s.append(Paragraph("19. Top 15 prioritet po vplivu in nujnosti", styles["H1"]))
    priorities = [
        ["#", "Prioriteta", "Vpliv", "Nujnost", "Cas"],
        ["1", "Popravki P0 varnostnih ranljivosti (secret_key, debug, auth)", "Kriticen", "Takoj", "2h"],
        ["2", "Fix to_drupal() session leak", "Visok", "Takoj", "1h"],
        ["3", "Fix published_checker portal ID mismatch", "Visok", "Takoj", "1h"],
        ["4", "Razbij engine.py v locene parserje", "Visok", "Teden 2", "2-3 dni"],
        ["5", "Dodaj CSRF zaiscito", "Visok", "Teden 2", "2h"],
        ["6", "Input validacija na API endpointih", "Srednji", "Teden 3", "4h"],
        ["7", "Status enum validacija v workflow", "Srednji", "Teden 3", "2h"],
        ["8", "Osnovna test suite (parser fixtures)", "Visok", "Teden 3", "2 dni"],
        ["9", "Docker setup za lokalni dev", "Srednji", "Teden 4", "1 dan"],
        ["10", "Alembic migracije", "Srednji", "Teden 4", "4h"],
        ["11", "PostgreSQL migracija", "Visok", "Mesec 2", "3-5 dni"],
        ["12", "RBAC + users v bazi", "Srednji", "Mesec 2", "2 dni"],
        ["13", "Audit log", "Srednji", "Mesec 2", "2 dni"],
        ["14", "Izboljsana deduplikacija", "Visok", "Mesec 3", "3-4 dni"],
        ["15", "Background jobs za scraping", "Visok", "Mesec 2", "3 dni"],
    ]
    s.append(mt(priorities[0], priorities[1:], [0.7*cm, 6*cm, 2*cm, 2*cm, 2*cm]))

    s.append(PageBreak())

    # ================================================================
    # 20. MIGRACIJSKA TVEGANJA
    # ================================================================
    s.append(Paragraph("20. Glavna migracijska tveganja in kako jih obvladati", styles["H1"]))
    risks = [
        ["Tveganje", "Verjetnost", "Vpliv", "Mitigacija"],
        ["Izguba podatkov pri SQLite->PG migraciji", "Srednja", "Kriticen",
         "Dual-write 7 dni, verificiraj stevila pred prerezom, ohrani SQLite backup 30 dni"],
        ["Parser regresije po refaktorju engine.py", "Visoka", "Visok",
         "Najprej napisi fixture teste za vsak parser, sele nato refaktoriraj"],
        ["Downtime med migracijami", "Nizka", "Srednji",
         "Blue-green deploy, migracije v off-peak urah"],
        ["Deduplikacija pobrise prave dogodke", "Srednja", "Visok",
         "Soft-delete (archived status), ne hard delete. Manual review za 75-92% confidence"],
        ["Auth spremembe zaklenejo uporabnike", "Nizka", "Visok",
         "Ohrani YAML fallback 2 tedna po migraciji v bazo"],
        ["Drupal API integracija ne dela", "Srednja", "Srednji",
         "Ohrani CSV export kot fallback za rocni uvoz"],
        ["Background jobs ne procesirajo", "Nizka", "Visok",
         "Dead letter queue + alert ce job ne konca v 30min"],
    ]
    s.append(mt(risks[0], risks[1:], [3.5*cm, 2*cm, 2*cm, 7*cm]))

    s.append(PageBreak())

    # ================================================================
    # 10 TOCK KOMENTARJEV
    # ================================================================
    s.append(Paragraph("Dodatek: Konkretni komentarji na 10 identificiranih tock", styles["H1"]))

    # 1
    s.append(Paragraph("1. Parserji zmesani v engine.py", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> 10 site-specific parserjev, 1.519 vrstic, 26 metod v enem razredu. "
        "ScraperEngine je god object ki dela fetch, parse, dedup, DB, media assignment in orchestracijo.", styles["Body"]))
    s.append(Paragraph("<b>Zakaj je tveganje:</b> Nemogoce testirati posamezen parser brez celotnega engine-a. "
        "Dodajanje novega parserja zahteva urejanje dispatch if/elif verige. Dva parserja (mgml, kinosiska) "
        "se dispatchata po config.id namesto parser_type — nekonsistentno.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Izvleci vsak parser v svojo datoteko z BaseParser vmesnikom: "
        "parse(html, config) -> list[dict]. Registry dict mapira parser_type na razred. Dispatch postane "
        "parser_cls = REGISTRY[config.parser_type]; events = parser_cls().parse(html, config).", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> Autodiscovery parserjev iz parsers/ direktorija. "
        "Vsak parser registrira sam sebe z dekoratorjem @register_parser('kulturnik-rss').", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Teden 2. Brez tega ni mogoce pisati testov za parserje.", styles["Body"]))

    # 2
    s.append(Paragraph("2. SQLite ni dobra baza za produkcijski workflow", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> SQLite ima en writer naenkrat. Flask z Gunicorn/multiple workers "
        "bo produciral locking napake. Ni full-text searcha, ni JSONB, ni ENUM tipov.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Dodaj check_same_thread=False na engine in WAL mode. "
        "To resi threading problem za kratkorocno.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> PostgreSQL z Alembic migracijami. "
        "Docker compose z PG containerjem za lokalni dev.", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> check_same_thread takoj (1h). PostgreSQL v mesecu 2.", styles["Body"]))

    # 3
    s.append(Paragraph("3. Uporabniki v auth.yaml", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> Gesla (hash) in secret_key v datoteki ki bo verjetno v git repo. "
        "Ni vlog, ni password reseta, ni audit logiranja prijav.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Takoj zamenjaj secret_key z naključnim. "
        "Premakni v .env datoteko ki je v .gitignore.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> Users tabela v bazi z RBAC, password reset flow, "
        "audit log prijav.", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Secret key popravek TAKOJ. Users v bazo v mesecu 2.", styles["Body"]))

    # 4
    s.append(Paragraph("4. API statusi in workflow semantika", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> Status se nastavi z golim db.execute(update().values(status=X)) "
        "brez validacije. Klient lahko poslje status='banana' in se zapise v bazo. "
        "Ni prehodni matrike — vsak status lahko preide v vsakega.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Enum validacija: ALLOWED_STATUSES = {...}. "
        "V vsakem endpointu preveri da je new_status v ALLOWED.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> StateMachine razred z validate_transition(from, to, role). "
        "PostgreSQL ENUM tip za status stolpec.", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Enum validacija teden 3. State machine mesec 2.", styles["Body"]))

    # 5
    s.append(Paragraph("5. Deduplikacija pregrobo", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> 'Ce katerakoli fuzzy metrika preseze 85%' producira false positive. "
        "partial_ratio je posebej problematicen — kratki naslovi so podmnozica dolgih. "
        "is_duplicate() ima mrtev fuzzy_threshold parameter ki nikoli ni uporabljen.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Dvigni prag na 90%. Uporabi weighted average namesto max(). "
        "Odstrani mrtev parameter.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> Confidence score z canonicalizacijo (poglavje 9).", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Quick fix teden 3. Polna prenova mesec 3.", styles["Body"]))

    # 6
    s.append(Paragraph("6. 'vsi' kot default target audience", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> 'vsi' semanticno pomeni 'ta dogodek je namenjen vsem'. "
        "V resnici pomeni 'ne vemo komu je namenjen'. To onemogoča filtriranje.", styles["Body"]))
    s.append(Paragraph("<b>Resitev:</b> Zamenjaj default z 'unknown'. Ko urednik pregleda, nastavi pravo vrednost. "
        "Dogodki z 'unknown' so vizualno oznaceni v dashboardu.", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Teden 3 (enostavna sprememba).", styles["Body"]))

    # 7
    s.append(Paragraph("7. Image hotlinkanje", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> image_url kaze na tuji streznik. Ce lastnik spremeni URL, slika izgine. "
        "Nekateri strezniki blokirajo hotlinking (403). Pravno gledano je to potencialna krsitev avtorskih pravic.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Preveri dostopnost slik enkrat tedensko (image validation job). "
        "Oznaci nedosegljive slike.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> Image proxy ki shrani lokalno kopijo, servira iz lastnega CDN. "
        "S3-compatible storage (MinIO za self-hosted).", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Validacija teden 4. Proxy mesec 4.", styles["Body"]))

    # 8
    s.append(Paragraph("8. Manjka audit trail", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> Nobena uredniška odlocitev ni zabelezena. Ce urednik po pomoti "
        "odobri 500 dogodkov, ni nacina ugotoviti kdo, kdaj, zakaj.", styles["Body"]))
    s.append(Paragraph("<b>Resitev:</b> audit_log tabela + AuditMiddleware ki avtomatsko zapise vsak POST/PATCH/DELETE. "
        "Primer v poglavju 13.", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Mesec 2 (skupaj z RBAC in PostgreSQL).", styles["Body"]))

    # 9
    s.append(Paragraph("9. Manjka testna strategija", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> 0 testov. Vsaka sprememba v parserju je tvegana — ni nacina vedeti "
        "ali je refaktor pokvaril ekstrakcijo za obstojece vire.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> pytest setup + 5 parser fixture testov (en HTML snapshot za "
        "vsak parser tip). To traja 1 dan in takoj prinese varnostno mrezo.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> Polna testna piramida iz poglavja 15.", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Teden 3. PRED kakrsnimkoli vecjim refaktorjem.", styles["Body"]))

    # 10
    s.append(Paragraph("10. Manjka deployment in observability", styles["H2"]))
    s.append(Paragraph("<b>Kaj je narobe:</b> Sistem se zaganja z python3 web/app.py. Ni Docker-ja, ni process managerja, "
        "ni log agregacije, ni alertov. Ce scraper crkne ob 3h zjutraj, nihce ne ve.", styles["Body"]))
    s.append(Paragraph("<b>Najhitrejsa resitev:</b> Dockerfile + docker-compose (teden 4). "
        "systemd unit za scraper cron job na VPS.", styles["Body"]))
    s.append(Paragraph("<b>Dolgorocna resitev:</b> docker-compose z web + worker + scheduler + db + redis (poglavje 14).", styles["Body"]))
    s.append(Paragraph("<b>Nujnost:</b> Docker teden 4. Polna observability mesec 3.", styles["Body"]))

    s.append(PageBreak())

    # ================================================================
    # PRAKTICNI SEZNAMI
    # ================================================================
    s.append(Paragraph("Kaj bi popravil v prvem tednu", styles["H1"]))
    w1 = [
        "Zamenjaj secret_key v auth.yaml z naključnim 64-char hex stringom",
        "Zamenjaj privzeto geslo zamenjaj-me-123",
        "Spremeni debug=True v os.environ.get('FLASK_DEBUG', '0') == '1'",
        "Dodaj check_same_thread=False na SQLite engine",
        "Popravi to_drupal() — featured naj bo parameter, ne odpira svoje session",
        "Sinhroniziraj portal ID-je v published_checker.py z media.yaml",
        "Dodaj .gitignore vnose za auth.yaml, .env, data/events.db",
        "Dodaj explicit auth guard na auth_required: ce AUTH_USERS prazen, zahtevaj env var ALLOW_DEV_MODE=1",
    ]
    for item in w1:
        s.append(Paragraph(f"<font color='#dc3545'>&#9679;</font> {item}", styles["BL"]))

    s.append(hr())
    s.append(Paragraph("Kaj bi prepovedal pred produkcijsko rastjo", styles["H1"]))
    forbid = [
        "Deploy brez CSRF zaiscite na POST endpointih",
        "Dodajanje novih parserjev v engine.py (najprej razbij)",
        "Shranjevanje secretov v YAML datotekah ki gredo v git",
        "Kakrsenkoli write endpoint brez input validacije",
        "Workflow status sprememba brez enum preverjanja",
        "Produkcijski deploy brez vsaj 20 osnovnih testov",
        "Flask dev server v produkciji (mora biti Gunicorn ali uWSGI)",
        "SQLite z vec kot 2 concurrent workerji",
    ]
    for item in forbid:
        s.append(Paragraph(f"<font color='#dc3545'>&#9679;</font> {item}", styles["BL"]))

    s.append(hr())
    s.append(Paragraph("Kaj bi pustil pri miru v tej fazi", styles["H1"]))
    leave = [
        "YAML konfiguracija virov — deluje, je pregledna, jo razumejo ne-razvijalci",
        "49 rocnih virov — so korektno evidentirani backlog, ne tehnicni dolg",
        "Kulturnik RSS kot primarni vir — je zanesljiv, strukturiran, pokrije vso Slovenijo",
        "SQLite za lokalni development (PostgreSQL samo za staging/production)",
        "Flask (ne FastAPI) — migracija je smiselna sele v mesecu 5 ko je vec API endpointov",
        "Keyword matching za kategorizacijo — ML pristop je smiselen sele z 5000+ labeliranimi eventi",
        "Geocoding lokacij — lepo imeti, ni kriticno za MVP",
        "Email notifikacije — Slack webhook ali email alert ko source_health degradira, ampak ne takoj",
        "Image proxy — hotlinkanje je sprejemljivo za MVP, dolgorocno ne",
        "Multi-tenant podpora — 7 portalov je dovolj za trenutno arhitekturo",
    ]
    for item in leave:
        s.append(Paragraph(f"<font color='#28a745'>&#10003;</font> {item}", styles["BL"]))

    s.append(Spacer(1, 30))
    s.append(hr())
    s.append(Paragraph("Event Scraper — Architecture Review v1.0 — 16. 4. 2026", styles["Small"]))

    doc.build(s)
    print(f"PDF ustvarjen: {OUTPUT}")


if __name__ == "__main__":
    build()
