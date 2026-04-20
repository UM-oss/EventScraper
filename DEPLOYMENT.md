# Deployment na Render.com

## 📋 Predpogoji

- ✅ GitHub repo z Event Scraper kodo (push najprej)
- ✅ Render.com račun (https://render.com — registracija s GitHub OAuth)
- 💳 Za daily scrape cron: Starter plan ($7/mes); brez tega cron ne dela na free tier-u

---

## 🚀 Hitri deploy (5 min)

### 1. Pojdi na Render Dashboard

https://dashboard.render.com → **New** → **Blueprint**

### 2. Poveži GitHub repo

- Klikni **Connect a repository** → izberi `event-scraper`
- Render avtomatsko najde `render.yaml` in pokaže predogled treh storitev:
  - **event-scraper-db** (PostgreSQL)
  - **event-scraper-web** (Flask web)
  - **event-scraper-daily** (Cron job)

### 3. Vpiši okoljske spremenljivke

Render bo zahteval ročno vpisovanje za te (so označene `sync: false`):

| Spremenljivka | Pomen | Primer |
|---|---|---|
| `ADMIN_EMAIL` | tvoj email za prvi login | `ukistar@gmail.com` |
| `ADMIN_PASSWORD` | začetno geslo (spremeni v UI po prvem loginu!) | `MocnoZacasno2026!` |
| `ADMIN_NAME` | tvoje ime | `Uroš Maučec` |
| `GEMINI_API_KEY` | (opcijsko) za AI generiranje opisov | `AIzaSy...` |

### 4. Klikni **Apply**

Render zgradi tri storitve. **Trajanje: 5-10 min za prvi deploy.**

Spremlaj logs v Render dashboardu:
- DB → status `Available`
- Web → `Live` z URL-jem `https://event-scraper-web-xyz.onrender.com`
- Cron → `Scheduled` (prvi run čaka na 6:00 CET naslednji dan)

### 5. Odpri URL v brskalniku

```
https://event-scraper-web-xyz.onrender.com
```

Prijavi se z `ADMIN_EMAIL` + `ADMIN_PASSWORD` (kot si vpisal).

### 6. Sproži prvi scrape

V dashboardu klikni **30 dni** (vsi viri) — sproženo je takoj. Trajalo 5-10 min za 88 virov.

---

## 💰 Stroški

| Komponenta | Free tier | Plačljiv |
|---|---|---|
| Web service | ✅ 750h/mes (sleeps po 15 min idle) | $7/mes (vedno-on) |
| PostgreSQL | ✅ prvih 90 dni, 1GB | $7/mes naprej |
| Cron job (daily scrape) | ❌ ni free | $7/mes (Starter) |

**Min. setup za prvih 90 dni: $7/mes** (samo cron)
**Po 90 dneh, full produkcija: $14-21/mes**

### Brezplačna alternativa za scheduler

Če noćeš plačati Render Starter za cron, lahko uporabiš **GitHub Actions**:

```yaml
# .github/workflows/daily-scrape.yml
name: Daily Scrape
on:
  schedule:
    - cron: "0 5 * * *"   # 06:00 CEST
  workflow_dispatch:       # tudi ročno

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python scripts/daily_scrape.py
        env:
          EVENT_SCRAPER_DATABASE_URL: ${{ secrets.DATABASE_URL }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

(Free 2000 min/mes, daily scrape rabi ~10 min → 300 min/mes uporabe.)

---

## 🔄 Posodobitve (continuous deployment)

Vsak `git push origin main` avtomatsko sproži:
1. Build na Render-u (`pip install -r requirements.txt`)
2. Migracije (`alembic upgrade head`)
3. Restart web service-a brez downtime-a (rolling deploy)
4. Cron job uporablja zadnji deploy ob naslednjem run-u

---

## 🔧 Po deployu

### A. Spremeni svoje začetno geslo

Topbar → **👥 Uporabniki** → tvoj user → **Uredi** → vpiši novo geslo

### B. Dodaj urednike

Topbar → **👥 Uporabniki** → **+ Dodaj uporabnika**:
- Email + geslo
- Vloga: **Urednik**
- Označi medije do katerih ima dostop

### C. Webhook notifikacije (opcijsko)

V Render → Web service → Environment → dodaj:
- `EVENT_SCRAPER_WEBHOOK_URL` = Slack/Discord URL
- `EVENT_SCRAPER_WEBHOOK_TYPE` = `slack` ali `discord`

Dnevni scrape bo poslal sporočilo: *"Event scrape končan: 47 novih, 12 posodobljenih, 86 virov v 247s."*

---

## 🛠 Troubleshooting

### Web service "Sleeping" (free tier)

Po 15 min brez prometa Render free tier zaspi. Prvi obisk traja ~30s da se zbudi.
- **Rešitev**: nadgradi na Starter plan ($7/mes) ali pošlji ping vsakih 10 min iz UptimeRobot/Better Uptime.

### Migracija ni stekla

V Render → Web service → Logs poglej napake. Ročno sproži preko Shell:
```bash
alembic upgrade head
```

### Pozabljen admin geslo

V Render → Web service → Shell:
```bash
python manage_users.py reset -e tvoj@email.si -p NovoGeslo123
```

### Postgres dosegel 1GB limit (free)

Po 90 dneh free tier preneha. Možnosti:
- Nadgradi na Render Postgres Starter ($7/mes)
- Migriraj na **Neon** (free 0.5GB, generous quota) ali **Supabase**

### Cron job ne dela

- Preveri da imaš Starter plan (cron ni v free)
- Cron schedule je v UTC: `0 5 * * *` = 06:00 CEST (ker je +1h za UTC)
- Logs v Render → Cron job → History

---

## 📊 Monitoring

### Render dashboard
- Web service → **Metrics** → CPU, RAM, response time
- Cron → **History** → uspeh/napaka vsak dnevni run
- Postgres → **Metrics** → connections, storage

### V app
- `/health` — source health pregled (admin only)
- `/api/metrics` — sistemske metrike
- `/api/health` — JSON za zunanje monitoring orodje

---

## 🔐 Varnost v produkciji

✅ Že nastavljeno:
- HTTPS (Render avtomatsko)
- HttpOnly + SameSite=Lax piškotki
- `SESSION_SECURE=1` (samo HTTPS)
- CSRF tokeni za POST/PUT/DELETE
- bcrypt geslo hashes
- Rate limiting (login: 5/IP/15min, AI: 8/min/200/dan)

🔄 Priporočam dodatno:
- Daily backup Postgres-a (Render → DB → Backups, free tier ima 7 dnevne)
- Cloudflare proxy pred Render web service-om za DDoS zaščito
- Audit log review enkrat tedensko (`event_edits` tabela)

---

## 🆘 Pomoč

Render docs: https://render.com/docs
Render community: https://community.render.com

Za vprašanja o aplikaciji: glej `README.md` ali `docs/event-scraper-phase1-changelog.pdf`.
