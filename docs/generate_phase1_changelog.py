"""
Generator PDF dokumentacije za Phase 1 refactor (april 2026).

Združi se s prvotno dokumentacijo (event-scraper-dokumentacija.pdf) in obravnava
samo spremembe + arhitekturne odločitve v tej fazi.
"""

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "event-scraper-phase1-changelog.pdf")


styles = getSampleStyleSheet()
TITLE = ParagraphStyle("Title", parent=styles["Title"], fontSize=24, leading=30,
                        spaceAfter=20, textColor=colors.HexColor("#1a73e8"))
SUBTITLE = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=13, leading=18,
                           textColor=colors.HexColor("#555"), spaceAfter=20)
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, leading=24,
                     spaceBefore=18, spaceAfter=10, textColor=colors.HexColor("#1a73e8"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=18,
                     spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#202124"))
BODY = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14,
                       alignment=TA_JUSTIFY, spaceAfter=6)
LIST = ParagraphStyle("List", parent=BODY, leftIndent=15, spaceAfter=2)
NOTE = ParagraphStyle("Note", parent=BODY, backColor=colors.HexColor("#fff3cd"),
                       borderColor=colors.HexColor("#ffeaa7"), borderWidth=0.5,
                       borderPadding=8, spaceAfter=8)
DANGER = ParagraphStyle("Danger", parent=BODY, backColor=colors.HexColor("#f8d7da"),
                         borderColor=colors.HexColor("#f5c2c7"), borderWidth=0.5,
                         borderPadding=8, spaceAfter=8)


def page_decorator(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#999"))
    canvas_obj.drawString(2 * cm, 1.5 * cm, "Event Scraper — Phase 1 Refactor")
    canvas_obj.drawRightString(A4[0] - 2 * cm, 1.5 * cm, f"str. {doc.page}")
    if doc.page > 1:
        canvas_obj.setStrokeColor(colors.HexColor("#1a73e8"))
        canvas_obj.setLineWidth(2)
        canvas_obj.line(2 * cm, A4[1] - 1.8 * cm, A4[0] - 2 * cm, A4[1] - 1.8 * cm)
    canvas_obj.restoreState()


def _table(data, col_widths, header_color="#1a73e8"):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
    ]))
    return t


def build_story():
    story = []

    # ============ NASLOVNICA ============
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Phase 1 Refactor", TITLE))
    story.append(Paragraph(
        "Persistent storage, PostgreSQL, multi-user, robust engine<br/>"
        "april 2026 — verzija 2.0",
        SUBTITLE))

    info = [
        ["Cilj", "Prehod iz \"wipe-and-rebuild\" v persistent storage"],
        ["Trajanje", "1 razvojna seja (april 2026)"],
        ["Spremembe baze", "5 novih tabel, 7 novih stolpcev na events"],
        ["Backwards compat", "Stari API endpointi delujejo (z dodatnimi polji)"],
        ["Out of scope", "Drupal integracija (Phase 2)"],
    ]
    story.append(_table([["Tema", "Opis"]] + info,
                        [4 * cm, 11 * cm], header_color="#5f6368"))
    story.append(PageBreak())

    # ============ MOTIVACIJA ============
    story.append(Paragraph("1. Motivacija", H1))
    story.append(Paragraph(
        "Pred Phase 1 je vsak scrape <b>brisal celotno bazo dogodkov</b> "
        "in jih ponovno vstavljal. Posledice:",
        BODY))
    motivations = [
        "<b>Izguba uredniškega dela:</b> statusi 'approved' in 'skipped' so se izgubili pri vsakem osveževanju.",
        "<b>Brez audit trail-a:</b> ni bilo mogoče videti, kdo je kdaj kaj uredil.",
        "<b>Neuporabno za več urednikov:</b> sistem je predpostavljal enega uporabnika.",
        "<b>Brez delta metrike:</b> nismo videli, koliko dogodkov je bilo dejansko novih, posodobljenih ali odpovedanih.",
        "<b>SQLite limitacije:</b> ni bil pripravljen za produkcijski deploy.",
    ]
    for m in motivations:
        story.append(Paragraph("• " + m, LIST))

    story.append(Paragraph(
        "<b>Zaključek:</b> sistem je delal kot <i>razvojni POC</i>, ne kot orodje za ekipo urednikov.",
        DANGER))

    # ============ KLJUČNE SPREMEMBE ============
    story.append(Paragraph("2. Ključne spremembe", H1))

    story.append(Paragraph("2.1 Persistent storage (jedro)", H2))
    story.append(Paragraph(
        "Engine zdaj uporablja <b>UPSERT</b> namesto INSERT-only:",
        BODY))
    upsert_steps = [
        "1. Najprej preveri po <code>(source_id, source_event_id)</code> ali dogodek že obstaja.",
        "2. Če da → posodobi spremenjena polja, povečaj <code>version</code>, beleži v <code>event_edits</code>.",
        "3. Če ne → fuzzy dedup proti vsem dogodkom istega datuma.",
        "4. Če novi → INSERT.",
        "5. Po koncu vira → <code>mark_stale_events()</code> dogodkom, ki jih nismo videli, postavi <code>is_active=False</code>.",
    ]
    for s in upsert_steps:
        story.append(Paragraph(s, LIST))

    story.append(Paragraph(
        "<b>Zaščita uredniških polj:</b> če je urednik ročno spremenil <code>description</code> ali "
        "<code>image_url</code> (<code>description_source='manual'</code>), scraper jih NE prepisuje.",
        NOTE))

    story.append(Paragraph("2.2 Audit trail", H2))
    audit_tables = [
        ["event_edits", "Vsaka sprememba polja: kdo, kdaj, vir spremembe (scraper/manual/ai-generated/auto-enrichment)"],
        ["dedup_decisions", "Vsaka odločitev deduplikacije: razlog (exact_normalized_title / fuzzy_same_time_t63 / …) + score + threshold"],
        ["users", "Persistentna identiteta uporabnika za attribution (sinhronizirano iz auth.yaml)"],
    ]
    story.append(_table([["Tabela", "Namen"]] + audit_tables,
                        [4 * cm, 11.5 * cm]))

    story.append(Paragraph("2.3 Multi-user", H2))
    multi = [
        "<b>last_edited_by_user_id</b> na Event — kdo je nazadnje uredil",
        "<b>approved_by_user_id, skipped_by_user_id</b> v event_media — kdo je odločil za ta status na tem mediju",
        "<b>version</b> stolpec na Event — optimistic locking; PUT vrne 409 če medtem nekdo posodobi",
        "<b>last_login_at</b> v users tabeli — sledenje aktivnim",
    ]
    for m in multi:
        story.append(Paragraph("• " + m, LIST))

    story.append(Paragraph("2.4 Refaktor scraping engine", H2))
    refactor = [
        "<b>retry_with_backoff</b> helper — eksponentni backoff, jitter, max_attempts",
        "<b>per-source isolation</b> — napaka enega vira NE pade celega scrape-a",
        "<b>SourceHealth</b> razširjen z <code>consecutive_successes</code>, <code>avg_duration_ms</code>, <code>last_retry_count</code>",
        "<b>cancel_event</b> threading.Event — gumb '⏹ Ustavi' v UI prekine med viri",
        "<b>persistence.py</b> ločen modul z <code>upsert_event()</code> in <code>mark_stale_events()</code>",
    ]
    for r in refactor:
        story.append(Paragraph("• " + r, LIST))
    story.append(PageBreak())

    # ============ PODATKOVNI MODEL ============
    story.append(Paragraph("3. Spremembe podatkovnega modela", H1))

    story.append(Paragraph("3.1 Novi stolpci na <code>events</code>", H2))
    new_cols = [
        ["is_active", "BOOLEAN, default TRUE", "Vidljivost v dashboardu"],
        ["first_seen_at", "DATETIME", "Kdaj prvič scrapan"],
        ["last_seen_at", "DATETIME", "Kdaj zadnjič potrjen v viru"],
        ["last_scraped_at", "DATETIME", "Zadnji scrape klic"],
        ["last_edited_by_user_id", "INTEGER FK", "Multi-user attribution"],
        ["last_edited_at", "DATETIME", "Zadnja ročna sprememba"],
        ["version", "INTEGER, default 1", "Optimistic locking"],
    ]
    story.append(_table([["Stolpec", "Tip", "Opis"]] + new_cols,
                        [4 * cm, 4 * cm, 7.5 * cm]))

    story.append(Paragraph("3.2 Novi stolpci na <code>event_media</code>", H2))
    em_cols = [
        ["approved_by_user_id", "INTEGER FK", "Kdo je 'approve-al'"],
        ["skipped_by_user_id", "INTEGER FK", "Kdo je 'preskočil'"],
    ]
    story.append(_table([["Stolpec", "Tip", "Opis"]] + em_cols,
                        [4 * cm, 4 * cm, 7.5 * cm]))

    story.append(Paragraph("3.3 Novi stolpci na <code>scrape_logs</code>", H2))
    sl_cols = [
        ["events_updated", "INTEGER", "Posodobljeni dogodki (UPSERT-update)"],
        ["events_marked_stale", "INTEGER", "Dogodki označeni kot neaktivni"],
        ["retry_count", "INTEGER", "Število retry-jev za uspešen scrape"],
    ]
    story.append(_table([["Stolpec", "Tip", "Opis"]] + sl_cols,
                        [4 * cm, 4 * cm, 7.5 * cm]))

    story.append(Paragraph("3.4 Nove tabele", H2))
    new_tables = [
        ["users", "id, email, name, is_active, created_at, last_login_at"],
        ["event_edits", "id, event_id, field_name, old_value, new_value, source, user_id, created_at"],
        ["dedup_decisions", "id, incoming_*, matched_event_id, decision, reason, score, threshold, created_at"],
    ]
    story.append(_table([["Tabela", "Stolpci"]] + new_tables,
                        [4 * cm, 11.5 * cm]))
    story.append(PageBreak())

    # ============ DEDUP ============
    story.append(Paragraph("4. Dedup refactor", H1))
    story.append(Paragraph(
        "Pred: <code>is_duplicate_fuzzy()</code> vrne bool — brez vidnosti zakaj. "
        "Po: <code>check_dedup()</code> vrne <code>DedupResult</code>:",
        BODY))

    code = """@dataclass
class DedupResult:
    decision: str    # "new" | "duplicate" | "stale-update"
    reason: str      # "exact_normalized_title" | "fuzzy_same_time_t63" | ...
    score: Optional[float]
    threshold: Optional[int]
    matched_event_id: Optional[int]
    matched_title: Optional[str]"""
    story.append(Paragraph("<font name='Courier' size='8'>" +
                           code.replace("\n", "<br/>").replace(" ", "&nbsp;") + "</font>",
                           BODY))

    story.append(Paragraph("Konfigurabilni thresholdi (<code>DedupConfig</code>):", H2))
    th = [
        ["threshold_same_time", "60", "Ko se ujema datum + čas (najbolj prizanesljivo)"],
        ["threshold_same_loc", "70", "Ko se ujema lokacija a ne čas"],
        ["threshold_title_only", "80", "Ko nimamo časa niti lokacije"],
        ["location_match_threshold", "70", "partial_ratio za ujemanje lokacij"],
    ]
    story.append(_table([["Parameter", "Default", "Razlaga"]] + th,
                        [5 * cm, 2 * cm, 8.5 * cm]))

    story.append(Paragraph(
        "Vsaka odločitev (razen 'new') se zabeleži v <code>dedup_decisions</code> "
        "tabelo — diagnostika false-positive/negative je preprosta.",
        NOTE))
    story.append(PageBreak())

    # ============ DASHBOARD ============
    story.append(Paragraph("5. Dashboard izboljšave", H1))
    items = [
        ("Brez page reload", "Po koncu scrape-a se kliče <code>/api/dashboard/snapshot</code> namesto <code>location.reload()</code>. Filtri ostanejo, layout ne miga."),
        ("⏹ Ustavi gumb", "Med scrape-om se desno od progress bara pokaže rdeč 'Ustavi'. Klik signalizira <code>cancel_event</code>; engine konča trenutni vir in se zaključi."),
        ("CSRF zaščita", "Vsi POST/PUT/DELETE zahtevajo <code>X-CSRF-Token</code>. Frontend doda header avtomatsko (patch-an <code>fetch</code>)."),
        ("Optimistic locking UI", "Inline edit pošlje <code>expected_version</code>; če je zastarelo, server vrne 409 s sporočilom 'drug uporabnik je medtem uredil dogodek'."),
        ("Persistent storage badge", "Neaktivni dogodki dobijo oznako 'NEAKTIVEN' poleg source ID-ja (vidno samo z <code>?show_inactive=1</code>)."),
        ("Card display", "Zdaj prikazujemo le datum/uro/prizorišče/tip. Organizator in vstopnina sta izpuščena (uredniška preferenca)."),
    ]
    for label, desc in items:
        story.append(Paragraph(f"<b>{label}</b> — {desc}", LIST))
    story.append(PageBreak())

    # ============ NEW MODULES ============
    story.append(Paragraph("6. Novi moduli", H1))
    new_modules = [
        ["scraper/persistence.py", "upsert_event(), mark_stale_events() — jedro persistent storage"],
        ["scraper/retry.py", "retry_with_backoff() helper z exponential backoff in jitter"],
        ["scraper/scheduler.py", "APScheduler integracija (opcijsko, env-driven)"],
        ["scraper/observability.py", "Strukturirano logiranje (JSON/human) + collect_system_metrics()"],
        ["scraper/bootstrap.py", "Sinhronizacija media.yaml → MediaOutlet tabela ob startupu"],
        ["scraper/config_schema.py", "Pydantic validacija YAML konfiguracij (88 virov + 8 medijev)"],
        ["scraper/disabled_sources.py", "Helper za 'disabled: true' flag v vir YAML-ih"],
        ["alembic/", "Migracije baze (initial_schema.py)"],
    ]
    story.append(_table([["Modul", "Namen"]] + new_modules,
                        [5 * cm, 10.5 * cm]))
    story.append(PageBreak())

    # ============ CONFIGURATION ============
    story.append(Paragraph("7. Konfiguracija (env)", H1))
    envs = [
        ["EVENT_SCRAPER_DATABASE_URL", "sqlite:///data/events.db", "PostgreSQL: postgresql://..."],
        ["EVENT_SCRAPER_SCHEDULER", "0", "1 = vključi periodični scrape"],
        ["EVENT_SCRAPER_SCHEDULE_INTERVAL", "60", "minute"],
        ["EVENT_SCRAPER_SCHEDULE_DAYS", "30", "look-ahead"],
        ["EVENT_SCRAPER_VALIDATE", "1", "0 = preskoči YAML validacijo"],
        ["DEDUP_TH_SAME_TIME", "60", "Threshold % za isti čas"],
        ["DEDUP_TH_SAME_LOC", "70", "Threshold % za isto lokacijo"],
        ["DEDUP_TH_TITLE_ONLY", "80", "Threshold % brez časa+lokacije"],
        ["LOG_JSON", "0", "1 = strukturirano JSON"],
        ["LOG_LEVEL", "INFO", "DEBUG/INFO/WARNING/ERROR"],
        ["SESSION_SECURE", "0", "1 = HTTPS only cookies"],
        ["GEMINI_API_KEY", "", "AI generiranje opisov"],
    ]
    story.append(_table([["Env", "Default", "Opis"]] + envs,
                        [6 * cm, 3 * cm, 6.5 * cm]))
    story.append(PageBreak())

    # ============ TESTING ============
    story.append(Paragraph("8. Testna pokritost", H1))
    story.append(Paragraph(
        "Phase 1 dodaja <b>23 novih testov</b> za jedrno logiko:", BODY))
    tests = [
        ["tests/test_persistence.py (9)",
         "test_upsert_new_event, test_upsert_skips_past_events, test_upsert_skips_event_without_key_fields, "
         "test_upsert_skips_long_exhibition, test_upsert_keeps_exhibition_opening, "
         "test_upsert_updates_existing_event_by_source_event_id, "
         "test_upsert_does_not_overwrite_manual_description, "
         "test_upsert_detects_fuzzy_duplicate, test_mark_stale_events"],
        ["tests/test_dedup.py (14)",
         "Normalizacija, hash determinizem, exact match, same-time različno besedilo, "
         "ČS Rožnik vs Posavje (kompromis), backward compat wrapperji, configurable thresholds, "
         "DedupResult vsebina"],
    ]
    story.append(_table([["Modul", "Pokriva"]] + tests, [5 * cm, 10.5 * cm]))

    story.append(Paragraph(
        "<b>Skupaj v projektu:</b> 62 testov, 61 prešlo, 1 preskočen (Drupal — out of scope).",
        NOTE))

    # ============ ZNANE OMEJITVE ============
    story.append(Paragraph("9. Znane omejitve in kompromisi", H1))
    limits = [
        "<b>Migracija iz starega sistema:</b> stari editorial statusi se izgubijo pri prvem zagonu Phase 1 (baza je bila resetirana). Od Phase 1 naprej se ohranijo.",
        "<b>Dedup ČS Rožnik vs Posavje:</b> isti datum+čas+podoben naslov = duplikat tudi pri različni lokaciji. Kompromis za ujetje 'Ed Rush' tipa duplikatov. False positive uredi z 'Preskoči'.",
        "<b>Bootstrap medijev:</b> ob vsakem startupu sinhronizira MediaOutlet iz media.yaml (idempotenten, a piše v DB).",
        "<b>Cancel scrape:</b> deluje med viri, NE prekine trenutnega vira sredi.",
        "<b>Optimistic locking:</b> implementirano za inline edit, ne pa za status spremembe (te ne kličejo expected_version).",
    ]
    for l in limits:
        story.append(Paragraph("• " + l, LIST))

    # ============ NEXT STEPS ============
    story.append(Paragraph("10. Predlog naslednjih korakov (Phase 2+)", H1))
    next_steps = [
        "<b>Drupal integracija end-to-end</b>: REST client za WordPress/Drupal portale + queued/pushed/published flow",
        "<b>Posebni view za 'Neaktivne'</b>: dashboard tab kjer urednik vidi izginule dogodke in jih lahko ohrani ali arhivira",
        "<b>Source health UI</b>: poseben pregled <code>/api/health</code> z grafom uspešnosti virov",
        "<b>Email notifikacije</b>: dnevno/tedensko poročilo (X novih, Y odpovedanih, Z brokenov)",
        "<b>Bulk operations</b>: izberi več dogodkov + obdelano/preskoči/dodeli mediju",
        "<b>Per-medij featured</b>: označi izpostavljene dogodke za posamezen portal",
        "<b>Multi-user roles</b>: admin (prek vseh medijev) vs urednik (samo svoj portal)",
        "<b>Webhook za nove dogodke</b>: POST v Slack/Email ko pride nov dogodek za moj medij",
    ]
    for n in next_steps:
        story.append(Paragraph("• " + n, LIST))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        f"<b>Konec dokumentacije Phase 1.</b> Generirano {datetime.now().strftime('%d. %m. %Y %H:%M')}.",
        NOTE))

    return story


def main():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        title="Event Scraper Phase 1 Refactor",
        author="Uros Maucec",
    )
    doc.build(build_story(), onFirstPage=page_decorator, onLaterPages=page_decorator)
    size = os.path.getsize(OUTPUT) / 1024
    print(f"PDF: {OUTPUT} ({size:.1f} KB)")


if __name__ == "__main__":
    main()
