# Event Scraper

Sistem za centralizirano zbiranje dogodkov iz slovenskih kulturnih in turističnih virov ter njihovo razvrščanje na 8 regionalnih medijskih portalov.

**Verzija:** 2.0 (Phase 1 — april 2026)
**Tehnologija:** Python 3.11 + Flask + SQLAlchemy + PostgreSQL/SQLite + Alembic

---

## ✨ Kaj je novega v Phase 1

### Persistent storage (najpomembnejša sprememba)
- Sistem **več NE briše baze** ob vsakem scrape-u.
- Dogodki se **posodabljajo** (UPSERT) — uredniški statusi (`approved`/`skipped`) **ostanejo** med scrape-i.
- Dogodki, ki jih scraper več ne najde, dobijo `is_active=False` (ne pobrišejo se — zgodovina je ohranjena).
- Nova polja: `is_active`, `first_seen_at`, `last_seen_at`, `last_scraped_at`, `version`.

### Audit trail
- Nova tabela `event_edits`: vsaka sprememba polja se beleži (kdo, kdaj, kateri vir spremembe).
- Nova tabela `dedup_decisions`: zakaj je bil dogodek označen kot duplikat (z razlogom in score).
- Nova tabela `users`: persistentna identiteta uporabnika za attribution.

### Multi-user
- `last_edited_by_user_id`, `approved_by_user_id`, `skipped_by_user_id`.
- **Optimistic locking** preko `version` stolpca — drug uporabnik ne more prepisati tvojih sprememb.

### PostgreSQL podpora
- `EVENT_SCRAPER_DATABASE_URL` env var določi bazo (SQLite default, PostgreSQL produkcija).
- Alembic migracije za upgrade/downgrade sheme.
- Docker compose za hitri razvojni setup.

### Robust scraping engine
- **Retry z exponential backoff** za vsak vir (privzeto 2 dodatna poskusa).
- Napaka enega vira **ne ustavi** celotnega procesa.
- Razširjene `source_health` metrike: `consecutive_errors`, `consecutive_successes`, `avg_duration_ms`.

### Eksplicitna deduplikacija
- `DedupConfig` dataclass — thresholdi se nastavijo prek env spremenljivk.
- Vsaka odločitev se vrne kot `DedupResult` z razlogom (`exact_normalized_title`, `fuzzy_same_time_t63`, …).
- Beleženje v `dedup_decisions` tabelo za diagnostiko.

### Dashboard izboljšave
- **Brez `location.reload()`** — AJAX `/api/dashboard/snapshot` ohranja filtre.
- **Stop scrape** gumb (⏹) za prekinitev med scrape-om.
- **CSRF zaščita** za vse POST/PUT/DELETE zahteve.

### Observability
- Strukturirano logiranje (JSON v produkciji, human v razvoju).
- Nov endpoint `/api/metrics`: events_active, scrape_runs_24h, sources_broken, …
- APScheduler (opcijsko, `EVENT_SCRAPER_SCHEDULER=1`) za periodični scrape.

---

## 📦 Hitri zagon

### Razvojno okolje (SQLite, brez Dockerja)

```bash
# 1. Klon + venv
git clone <repo> event-scraper
cd event-scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Konfiguracija
cp .env.example .env
# (.env lahko pustiš z default SQLite za začetek)

# 3. Migracije
alembic upgrade head

# 4. Bootstrap medijev iz config/media.yaml
python -c "from scraper.bootstrap import bootstrap_media_outlets; bootstrap_media_outlets()"

# 5. Dodaj prvega uporabnika
python manage_users.py add

# 6. Zaženi
python run_dashboard.py
# → http://localhost:8080
```

### Razvojno okolje s PostgreSQL (Docker compose)

```bash
# Zaženi samo bazo
docker compose up -d postgres

# Nastavi env
echo 'EVENT_SCRAPER_DATABASE_URL=postgresql://event_scraper:event_scraper_pwd@localhost:5432/event_scraper' > .env

alembic upgrade head
python -c "from scraper.bootstrap import bootstrap_media_outlets; bootstrap_media_outlets()"
python manage_users.py add
python run_dashboard.py
```

### Produkcijsko okolje (Docker)

```bash
# Zgradi in zaženi celoten stack
docker compose --profile full up -d --build
# → http://localhost:8080
```

---

## 🗂️ Struktura projekta

```
event-scraper/
├── alembic/               # Migracije baze
│   └── versions/
├── config/
│   ├── auth.yaml          # Uporabniki + secret_key + gemini_api_key
│   ├── media.yaml         # 8 medijskih portalov
│   └── sources/           # 88 vir YAML datotek
├── data/
│   └── events.db          # SQLite (samo razvoj)
├── database/
│   └── models.py          # SQLAlchemy modeli
├── scraper/
│   ├── engine.py          # Glavni orchestrator
│   ├── persistence.py     # NEW: upsert + mark-stale
│   ├── dedup.py           # Refaktor: DedupConfig + DedupResult
│   ├── retry.py           # NEW: exponential backoff
│   ├── scheduler.py       # NEW: APScheduler integracija
│   ├── observability.py   # NEW: strukturirano logiranje
│   ├── bootstrap.py       # NEW: media.yaml → DB sinhronizacija
│   ├── config_schema.py   # NEW: Pydantic validacija YAML-ov
│   ├── disabled_sources.py
│   ├── categorizer.py
│   ├── image_fallback.py
│   ├── ai_description.py  # Gemini Flash AI generiranje
│   └── parsers/
├── web/
│   ├── app.py             # Flask + endpointi
│   └── templates/
├── tests/
│   ├── test_dedup.py      # NEW: 14 testov
│   ├── test_persistence.py # NEW: 9 testov upsert/mark-stale
│   └── …
├── docs/
├── docker-compose.yml     # NEW
├── Dockerfile             # NEW
├── alembic.ini            # NEW
├── .env.example           # NEW
└── requirements.txt
```

---

## 🔄 Delovni potek (workflow)

### Statusi dogodka (event_media tabela)
| Status | Pomen | Prehod → |
|---|---|---|
| `new` | Novi | `approved`, `skipped` |
| `approved` | Urednik potrdil | `queued`, `skipped` |
| `queued` | V čakalni vrsti | `pushed` |
| `pushed` | Poslano | `published` |
| `published` | Objavljeno | `archived` |
| `skipped` | Preskočeno | `new` |

### Tipičen dnevni cikel
1. Urednik odpre dashboard
2. Izbere medij (npr. **MariborInfo**) ali pusti "vsi"
3. Klikne **Osveži (X dni)** — sproži persistent scrape
   - Stari dogodki **ostanejo s svojim statusom**
   - Novi dogodki dobijo status `new`
   - Spremenjeni dogodki se posodobijo (verzija + 1)
   - Dogodki, ki jih ni več → `is_active=False`
4. Med scrape-om lahko klikne **⏹ Ustavi** za prekinitev
5. Pregleda dogodke, po potrebi inline ureja manjkajoča polja
6. Označi **Obdelano** ali **Preskoči**

---

## 🗄️ Migracije baze

```bash
# Trenutna verzija
alembic current

# Posodobi na zadnjo
alembic upgrade head

# Generiraj novo migracijo iz sprememb modelov
alembic revision --autogenerate -m "opis spremembe"

# Vrni na prejšnjo
alembic downgrade -1
```

### Migracija iz starega sistema (SQLite)

Stara baza je shranjena kot `data/events.db.backup-pre-phase1`. Za prenos podatkov:

```bash
# 1. Backup že obstaja
ls data/events.db.backup-*

# 2. Nova baza je prazna (po migraciji)
# Old data je zgolj referenca, ne uvažamo direktno
# Naslednji scrape bo zgradil svežo bazo z novimi polji
```

> **Opomba:** Glede na to, da baza vsebuje agregirane javne podatke iz virov, smatramo da poln re-scrape je sprejemljiv kompromis. Stari editorial statusi se izgubijo le pri prvi migraciji — od Phase 1 naprej se ohranijo.

---

## ⚙️ Konfiguracija (env spremenljivke)

| Spremenljivka | Default | Opis |
|---|---|---|
| `EVENT_SCRAPER_DATABASE_URL` | `sqlite:///data/events.db` | DB URL |
| `EVENT_SCRAPER_SCHEDULER` | `0` | `1` = vključi periodični scrape |
| `EVENT_SCRAPER_SCHEDULE_INTERVAL` | `60` | minute med scrape-i |
| `EVENT_SCRAPER_SCHEDULE_DAYS` | `30` | look-ahead dni |
| `EVENT_SCRAPER_VALIDATE` | `1` | `0` = preskoči YAML validacijo |
| `DEDUP_TH_SAME_TIME` | `60` | threshold % za isti čas |
| `DEDUP_TH_SAME_LOC` | `70` | threshold % za isto lokacijo |
| `DEDUP_TH_TITLE_ONLY` | `80` | threshold % brez časa |
| `LOG_JSON` | `0` | `1` = strukturirano JSON logiranje |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `FLASK_DEBUG` | `0` | `1` = debug mode |
| `SESSION_SECURE` | `0` | `1` = HTTPS only cookies |
| `GEMINI_API_KEY` | | API ključ za AI generiranje opisov |

---

## 🧪 Testi

```bash
pytest tests/                  # vsi testi
pytest tests/test_dedup.py     # samo dedup
pytest tests/test_persistence.py  # samo upsert/mark-stale
pytest -v                       # verbose
pytest --cov=scraper           # s coverage
```

Trenutno: **62 testov** (61 prešlo, 1 preskočen — Drupal je out-of-scope).

---

## 🔌 API endpointi

Vsi endpointi razen `/login` zahtevajo prijavo. Vsi POST/PUT/DELETE zahtevajo `X-CSRF-Token` header (frontend doda avtomatsko).

### Dashboard
- `GET /` — Dashboard
- `GET /api/dashboard/snapshot` — AJAX osvežitev brez reload-a
- `GET /api/tasks/status` — stanje aktivnega scrape-a
- `GET /api/metrics` — sistemske metrike
- `GET /api/health` — source health pregled

### Scraping
- `POST /api/scrape/refresh?days=N&media=ID` — sproži scrape
- `POST /api/scrape/cancel` — prekini aktivni scrape

### Dogodki
- `POST /api/event/<id>/status` — spremeni status (audit log)
- `POST /api/event/<id>/update-field` — inline edit (z optimistic locking)
- `POST /api/event/<id>/fetch-image` — najdi sliko
- `POST /api/event/<id>/fetch-description` — najdi opis
- `POST /api/event/<id>/ai-description` — Gemini Flash AI (rate-limited)
- `GET  /api/event/<id>/copy-text` — plain text za kopiranje
- `GET  /api/image-proxy?url=…` — Facebook hotlinking proxy

---

## 🛠️ Operativne naloge

### Onemogočanje vira
V `config/sources/<vir>.yaml` dodaj `disabled: true` in spremeni `parser_type: "manual"`.

### Dodajanje vira
1. Ustvari `config/sources/<id>.yaml` po vzorcu obstoječega
2. Restartiraj — Pydantic validacija zazna napake
3. Naslednji scrape ga bo vključil

### Backup baze (PostgreSQL)
```bash
docker exec event-scraper-db pg_dump -U event_scraper event_scraper > backup-$(date +%Y%m%d).sql
```

### Dodajanje uporabnika
```bash
python manage_users.py add
# Email + ime + geslo → bcrypt hash v config/auth.yaml
```

---

## 📜 Licenca

Notranji projekt; ni javno odprt.

## 👤 Avtor

Uroš Maučec
