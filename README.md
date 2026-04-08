# Corvin

![CI](https://github.com/Sewaaa/corvus/actions/workflows/ci.yml/badge.svg)

> **Guardiano silenzioso del tuo perimetro digitale.**

Corvin è una piattaforma SaaS di cybersecurity per PMI che centralizza il monitoraggio di minacce email, data breach, reputazione domini, vulnerabilità web e file sospetti — tutto da un'unica dashboard.

Progetto portfolio full-stack costruito come dimostrazione di competenze in sicurezza informatica, architettura SaaS multi-tenant e sviluppo web moderno.

*Named after corvus (Latin: raven) — a symbol of intelligence and foreknowledge.*

---

## Moduli

| Modulo | Descrizione |
|--------|-------------|
| **Breach Monitor** | Integrazione Have I Been Pwned con k-anonymity — verifica se le email aziendali sono apparse in data breach pubblici |
| **Domain Reputation** | Analisi DNS, controllo blacklist DNSBL, scadenza SSL, WHOIS, score di reputazione aggregato |
| **Web Scanner** | Scanner passivo di sicurezza web — header HTTP, file esposti, CMS outdated, redirect HTTPS |
| **Email Protection** | Connessione IMAP, rilevamento phishing, validazione SPF/DKIM/DMARC, quarantena email |
| **File Sandbox** | Analisi statica: regole YARA, hash lookup VirusTotal, entropia Shannon, parsing PE |
| **Notifiche** | Alert in-app con severity routing + webhook con firma HMAC-SHA256 per integrazioni esterne |
| **Report** | Panoramica aggregata di tutti i moduli con export PDF |

---

## Stack Tecnologico

| Layer | Tecnologia |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic |
| **Task queue** | Celery 5, Redis 7 (broker + backend), Celery Beat (schedulazione) |
| **Database** | PostgreSQL 16, isolamento multi-tenant a livello middleware |
| **Frontend** | React 18, Vite, Tailwind CSS, React Router v6 |
| **Sicurezza** | bcrypt, JWT (access + refresh), TOTP MFA, cifratura Fernet, HMAC-SHA256 |
| **Analisi** | Regole YARA, VirusTotal API v3, entropia Shannon, distanza di Levenshtein |
| **i18n** | Sistema multi-lingua IT/EN con 315 chiavi, tema chiaro/scuro |
| **CI/CD** | GitHub Actions — Bandit SAST, pip-audit, pytest (soglia 60% coverage) |
| **Deploy** | Render.com (backend Docker, frontend statico, PostgreSQL managed) |

---

## Architettura

Multi-tenant SaaS — ogni organizzazione vede solo i propri dati, isolamento applicato a livello middleware su ogni request.

```
[React SPA] ──HTTPS──► [FastAPI API]
                              │
                    ┌─────────┼─────────┐
                    │         │         │
               [PostgreSQL] [Redis] [Celery Workers]
                              │         │
                         [Celery Beat]  └──► [HIBP / VirusTotal /
                          (scheduled)         Google Safe Browsing]
```

**Flusso autenticazione:** JWT access token (15 min) + refresh token (7 giorni). MFA opzionale via TOTP (RFC 6238). Ogni token porta `organization_id` nel payload — il `TenantIsolationMiddleware` lo estrae e lo inietta in `request.state` prima che arrivi al router.

---

## Setup locale (Docker)

### Prerequisiti
- Docker ≥ 24 e Docker Compose v2
- Git

### 1. Clona il repository

```bash
git clone https://github.com/Sewaaa/corvus.git
cd corvus
```

### 2. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` e compila almeno queste variabili:

```env
# Genera con: openssl rand -hex 32
SECRET_KEY=la-tua-chiave-segreta-lunga-almeno-32-caratteri

# Have I Been Pwned — obbligatorio per il Breach Monitor
# Registrazione gratuita su: https://haveibeenpwned.com/API/Key
HIBP_API_KEY=la-tua-api-key-hibp

# VirusTotal — opzionale, per hash lookup nel File Sandbox
# Registrazione gratuita su: https://www.virustotal.com
VIRUSTOTAL_API_KEY=la-tua-api-key-vt
```

Le altre variabili (`DATABASE_URL`, `REDIS_URL`, ecc.) hanno già i valori corretti per Docker Compose.

### 3. Avvia tutti i servizi

```bash
docker-compose up -d
```

Questo avvia in ordine:
1. **PostgreSQL** (porta 5432)
2. **Redis** (porta 6379)
3. **API FastAPI** (porta 8000)
4. **Celery Worker** (gestisce task asincroni)
5. **Celery Beat** (schedulazione task periodici)
6. **Frontend React** (porta 3000)

### 4. Applica le migrazioni del database

```bash
docker-compose exec corvin-api alembic upgrade head
```

### 5. Accedi all'applicazione

| Servizio | URL |
|----------|-----|
| **Frontend** | http://localhost:3000 |
| **API docs (Swagger)** | http://localhost:8000/docs |
| **API docs (ReDoc)** | http://localhost:8000/redoc |

### 6. Crea il primo account

Vai su http://localhost:3000, clicca **Registrati** e crea il tuo account. Il primo utente registrato è automaticamente `ADMIN` dell'organizzazione.

---

## Setup senza Docker (sviluppo)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Esporta le variabili d'ambiente
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/corvin"
export SECRET_KEY="dev-secret-key"
export ENVIRONMENT="development"

# Avvia l'API
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

> Per collegare il frontend al backend locale, crea `frontend/.env.local`:
> ```
> VITE_API_BASE_URL=http://localhost:8000/api/v1
> ```

---

## Comandi Make utili

```bash
make dev              # Avvia tutti i container
make dev-build        # Rebuild immagini + avvia
make stop             # Ferma tutti i container
make logs             # Tail dei log api + worker
make migrate          # Applica migrazioni Alembic
make makemigrations MSG="descrizione"  # Genera nuova migrazione
make shell-db         # Entra nella shell PostgreSQL
make test             # Esegui test suite completa
```

---

## Variabili d'ambiente

| Variabile | Descrizione | Obbligatoria |
|-----------|-------------|-------------|
| `DATABASE_URL` | Stringa di connessione PostgreSQL (`postgresql+asyncpg://...`) | Sì |
| `REDIS_URL` | Stringa di connessione Redis (`redis://...`) | Sì |
| `SECRET_KEY` | Chiave JWT — genera con `openssl rand -hex 32` | Sì |
| `HIBP_API_KEY` | API key Have I Been Pwned | Sì (Breach Monitor) |
| `VIRUSTOTAL_API_KEY` | API key VirusTotal v3 | No (hash lookup) |
| `GOOGLE_SAFE_BROWSING_API_KEY` | API key Google Safe Browsing | No |
| `SENDGRID_API_KEY` | API key SendGrid per email | No |
| `SMTP_HOST` | Server SMTP fallback | No |
| `ENVIRONMENT` | `development` disabilita TrustedHost e abilita `/docs` | No |
| `VITE_API_BASE_URL` | URL base API per il frontend (build-time) | Solo in prod |

Vedi [`.env.example`](.env.example) per il file completo con valori di default.

---

## Come ottenere le API key

### Have I Been Pwned (obbligatoria)
1. Vai su https://haveibeenpwned.com/API/Key
2. Acquista una subscription (a partire da ~$3.50/mese) oppure usa il tier gratuito con rate limiting
3. Incolla la key in `HIBP_API_KEY`

> Le query usano **k-anonymity**: viene inviato solo il prefisso SHA-1 (5 caratteri), mai l'hash completo né l'email.

### VirusTotal (opzionale)
1. Registrazione gratuita su https://www.virustotal.com
2. Vai su *Profile → API Key*
3. Il tier gratuito ha 500 request/giorno — sufficiente per demo

### Google Safe Browsing (opzionale)
1. Vai su https://console.cloud.google.com
2. Abilita l'API "Safe Browsing"
3. Crea una API key nelle credenziali

---

## Deploy su Render.com

Il file `render.yaml` configura automaticamente il deploy. Per fare il deploy:

### 1. Fork/push su GitHub

Assicurati che il codice sia su GitHub.

### 2. Crea un account su Render

Vai su https://render.com e registrati (tier gratuito disponibile).

### 3. Crea un nuovo "Blueprint"

- Dashboard Render → **New** → **Blueprint**
- Collega il tuo repository GitHub
- Render legge `render.yaml` e crea automaticamente:
  - Servizio web **corvin-api** (Docker)
  - Sito statico **corvin-frontend**
  - Database **PostgreSQL managed**

### 4. Configura le variabili d'ambiente

Nel dashboard Render, per il servizio `corvin-api` aggiungi:

| Variabile | Valore |
|-----------|--------|
| `HIBP_API_KEY` | La tua API key HIBP |
| `VIRUSTOTAL_API_KEY` | La tua API key VT (opzionale) |
| `ALLOWED_ORIGINS` | `["https://tuo-frontend.onrender.com"]` |
| `REDIS_URL` | URL di un Redis esterno (es. Upstash free tier) |

Per `REDIS_URL` gratuito: registrati su https://upstash.com e crea un database Redis.

### 5. Configura il frontend

Per il servizio `corvin-frontend` aggiungi:

| Variabile | Valore |
|-----------|--------|
| `VITE_API_BASE_URL` | `https://corvin-api.onrender.com/api/v1` |

### 6. Applica le migrazioni

Dopo il primo deploy, nella shell del servizio API su Render:
```bash
alembic upgrade head
```

> **Nota free tier:** I servizi Render gratuiti si "addormentano" dopo 15 minuti di inattività. La prima request dopo lo sleep richiede ~30-60 secondi. Il frontend mostra un banner rosso se l'API non risponde.

---

## Testing

```bash
# Suite completa
make test

# Con output dettagliato
docker-compose exec corvin-api pytest tests/ -v --tb=short

# Solo autenticazione
docker-compose exec corvin-api pytest tests/test_auth.py -v

# Solo isolamento multi-tenant
docker-compose exec corvin-api pytest tests/test_tenant_isolation.py -v

# Solo sandbox
docker-compose exec corvin-api pytest tests/test_sandbox.py -v

# Con coverage report
docker-compose exec corvin-api pytest tests/ --cov=app --cov-report=term-missing
```

I test usano **SQLite in-memory** — nessun PostgreSQL necessario. Il CI blocca la merge se coverage < 60%.

---

## Sicurezza

- **Nessun segreto hardcoded** — tutto via variabili d'ambiente
- **bcrypt** per le password con fattore di costo configurabile
- **JWT** con access token (15 min) + refresh token rotation (7 giorni)
- **TOTP MFA** — RFC 6238, opzionale per ogni utente
- **Isolamento tenant** — applicato a livello middleware su ogni request
- **Rate limiting** — tutti gli endpoint via Redis (slowapi)
- **Solo scansione passiva** — il web scanner non invia mai payload offensivi
- **k-anonymity** — le query HIBP non espongono mai hash completi
- **Cifratura Fernet** — le password IMAP sono cifrate a riposo
- **HMAC-SHA256** — firma dei webhook per verifica autenticità

---

## Struttura del progetto

```
corvin/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # Router HTTP
│   │   ├── core/                # Config, DB, middleware, security
│   │   ├── models/              # ORM SQLAlchemy
│   │   ├── modules/             # Business logic per modulo
│   │   │   ├── breach_monitor/
│   │   │   ├── domain_reputation/
│   │   │   ├── web_scanner/
│   │   │   ├── email_protection/
│   │   │   ├── file_sandbox/
│   │   │   └── notifications/
│   │   ├── schemas/             # Schema Pydantic
│   │   └── tasks/               # Celery app config
│   ├── alembic/                 # Migrazioni database
│   ├── tests/                   # Test suite
│   ├── yara_rules/              # Regole YARA per analisi file
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # Client API per ogni modulo
│   │   ├── components/          # Componenti condivisi
│   │   ├── context/             # Auth + Settings (i18n/tema)
│   │   ├── hooks/               # useApi hook
│   │   ├── i18n/                # Traduzioni IT/EN
│   │   └── pages/               # Una pagina per route
│   ├── tailwind.config.js
│   └── vite.config.js
├── docker-compose.yml
├── render.yaml                  # Configurazione deploy Render
├── Makefile
└── .env.example
```

---

## Licenza

MIT — vedi file LICENSE.
