# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development (Docker-based)
```bash
make dev            # Start all services (postgres, redis, api, worker, beat, frontend)
make dev-build      # Rebuild images then start
make stop           # Stop all containers
make logs           # Tail logs for api + worker
```

### Database
```bash
make migrate                           # Apply pending Alembic migrations
make makemigrations MSG="description"  # Auto-generate a new migration
make shell-db                          # psql into the running postgres container
```

### Testing
```bash
make test                                                            # Run full test suite (inside container)
docker-compose exec corvin-api pytest tests/ -v --tb=short          # Same, verbose
docker-compose exec corvin-api pytest tests/test_auth.py -v         # Single file
docker-compose exec corvin-api pytest tests/test_auth.py::test_register -v  # Single test
```

Tests use **SQLite in-memory** (no running postgres needed). To run locally without Docker:
```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

### Linting
```bash
docker-compose exec corvin-api ruff check app/
docker-compose exec corvin-api ruff check app/ --fix
```

### Frontend
```bash
cd frontend && npm install
cd frontend && npm run dev      # Dev server on :3000
cd frontend && npm run build    # Production build
```

---

## Architecture

### Backend (`backend/`)

**FastAPI** app with async SQLAlchemy 2.0 + PostgreSQL. Background jobs via **Celery** + Redis.

```
app/
├── main.py              # App factory: middleware stack, lifespan, router registration
├── api/v1/endpoints/    # HTTP handlers (thin layer — delegate to modules/)
├── core/
│   ├── config.py        # Settings loaded from env via pydantic-settings
│   ├── database.py      # Async engine, get_db() dependency, Base
│   ├── dependencies.py  # get_current_user, get_current_active_user, require_admin, get_current_org
│   ├── middleware.py     # LoggingMiddleware, TenantIsolationMiddleware
│   └── security.py      # JWT encode/decode, bcrypt, TOTP
├── models/              # SQLAlchemy ORM models (all inherit Base)
├── schemas/             # Pydantic request/response schemas
├── modules/             # Business logic, one subpackage per feature
│   └── <feature>/
│       ├── router.py    # FastAPI router (mounted at /api/v1/<feature>)
│       ├── service.py   # Core logic, DB queries — all strings in Italian
│       └── tasks.py     # Celery tasks for async work
└── tasks/celery_app.py  # Celery app config + task autodiscovery
```

**Multi-tenancy:** Every authenticated request carries `organization_id` in the JWT. `TenantIsolationMiddleware` extracts it into `request.state.organization_id`. All DB queries must filter by `organization_id` — never trust a user-supplied org ID. The `test_tenant_isolation.py` suite enforces this.

**Auth flow:** JWT access + refresh tokens. MFA via TOTP (optional per user). Dependency chain: `get_db` → `get_current_user` → `get_current_active_user` → `require_admin` / `get_current_org`.

**Celery queues:** `breach`, `domain`, `scanner`, `sandbox`, `email`, `notifications` — one queue per module, all consumed by `corvin-worker`. `corvin-beat` runs scheduled tasks.

### Frontend (`frontend/`)

**React 18 + Vite + Tailwind CSS**. No external UI component library — all components are hand-built.

```
src/
├── api/          # One module per backend feature (breach.js, domain.js, etc.)
│                 # All import api/client.js which wraps fetch with auth headers
├── context/
│   ├── AuthContext.jsx     # User state, login/logout, token refresh
│   └── SettingsContext.jsx # Language (IT/EN) + theme (light/dark), t() function
├── hooks/        # useApi(fn, deps) — generic data-fetching hook with loading/error/refetch
├── i18n/
│   ├── it.js     # Italian translations (315 keys)
│   ├── en.js     # English translations (315 keys)
│   └── index.js  # getTranslations(lang) helper
├── components/   # Shared: Layout, Sidebar, StatCard, SeverityBadge, InfoModal, EmptyState
└── pages/        # One component per route
```

**Routing** is in `App.jsx`. Protected routes render `<Layout>` (sidebar + outlet); the login page is standalone.

**i18n:** All UI strings go through `t(key, params?)` from `useSettings()`. Keys live in `src/i18n/it.js` and `src/i18n/en.js`. Language and theme are persisted in `localStorage` (`corvin_lang`, `corvin_theme`). Add new keys to both files when adding new UI strings.

**Theme:** `[data-theme="dark"]` CSS attribute on `<html>`. Dark mode overrides are in `index.css`. The `SettingsContext` applies the attribute when theme changes.

**Tailwind theme** (`tailwind.config.js`): custom `corvin.*` color tokens. Key ones: `corvin-nav` (sidebar), `corvin-accent` (primary blue), `corvin-50/100/200` (light backgrounds/borders). Utility classes `btn-primary`, `btn-secondary`, `form-input`, `form-select`, `card` are defined in `index.css` via `@layer components`.

### Environment

All secrets live in `.env` (see `.env.example`). Key variables:
- `DATABASE_URL` — asyncpg connection string
- `REDIS_URL` — Celery broker + rate limiter backend
- `SECRET_KEY` — JWT signing key (generate with `openssl rand -hex 32`)
- `HIBP_API_KEY` — Have I Been Pwned API key (required for breach checks)
- `VIRUSTOTAL_API_KEY` — VirusTotal API v3 key (optional, hash lookups)
- `ENVIRONMENT` — `development` disables TrustedHost middleware and exposes `/docs`

### Migrations

Alembic is configured in `alembic/` with async engine support. Always run `make migrate` after pulling changes that add models. When adding a new SQLAlchemy model, import it in `alembic/env.py` so autogenerate picks it up.

### i18n — Adding new strings

1. Add the key to `frontend/src/i18n/it.js` (Italian value)
2. Add the same key to `frontend/src/i18n/en.js` (English value)
3. Use `const { t } = useSettings()` in the component, then `t('your.key')`
4. For parameterized strings: `t('key', { count: 5 })` with `{count}` placeholder in the value

### Notification strings

All user-facing notification titles, messages, and finding descriptions in the backend are in **Italian**. When adding new findings in `modules/*/service.py`, write strings in Italian.

### Deployment (Render.com)

See `render.yaml`. Free tier limitations:
- Celery worker/beat are disabled (require paid plan)
- Backend sleeps after 15 min of inactivity — first request after sleep is slow
- Frontend is a static site; set `VITE_API_BASE_URL` to the backend URL in Render env vars
