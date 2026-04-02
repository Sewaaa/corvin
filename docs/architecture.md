# Corvin — Architecture

## Overview

Corvin is a multi-tenant SaaS platform. All data is isolated at the database level using `organization_id` scoping on every table, enforced by:

1. A SQLAlchemy convention: every query includes `.where(Model.organization_id == current_org_id)`
2. `TenantIsolationMiddleware` in the API layer that extracts `org_id` from the JWT and attaches it to `request.state`

No raw SQL is used anywhere. Tenant cross-contamination is structurally prevented.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Network (corvin-net)          │
│                                                             │
│  ┌──────────────┐   /api/*   ┌──────────────────────────┐  │
│  │   Frontend   │ ─────────▶ │       corvin-api          │  │
│  │  React/Vite  │            │       FastAPI             │  │
│  │  :3000       │            │       :8000               │  │
│  └──────────────┘            └────────────┬─────────────┘  │
│                                           │                 │
│                              ┌────────────▼─────────────┐  │
│                              │       PostgreSQL 16       │  │
│                              │       corvin-db :5432     │  │
│                              └──────────────────────────┘  │
│                                           │                 │
│                              ┌────────────▼─────────────┐  │
│                              │       Redis 7             │  │
│                              │       corvin-redis :6379  │  │
│                              └────────────┬─────────────┘  │
│                                           │                 │
│                  ┌────────────────────────┤                 │
│                  ▼                        ▼                 │
│  ┌───────────────────────┐  ┌───────────────────────────┐  │
│  │    corvin-worker      │  │    corvin-beat            │  │
│  │    Celery Worker      │  │    Celery Beat Scheduler  │  │
│  └───────────────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Services

| Service | Image | Purpose |
|---------|-------|---------|
| `corvin-api` | `./backend` | FastAPI REST API, handles auth + all module endpoints |
| `corvin-worker` | `./backend` | Celery worker, processes async scan/check tasks |
| `corvin-beat` | `./backend` | Celery Beat, schedules recurring tasks (daily breach checks, etc.) |
| `corvin-db` | `postgres:16-alpine` | Primary datastore, multi-tenant via org_id scoping |
| `corvin-redis` | `redis:7-alpine` | Celery broker + backend, rate-limit counters, session cache |
| `corvin-frontend` | `./frontend` | React SPA, proxies `/api` to corvin-api |

## Data Flow — Breach Check Example

```
User → POST /api/v1/breach/check
  → TenantIsolationMiddleware extracts org_id from JWT
  → BreachRouter validates payload (Pydantic)
  → Enqueues Celery task: check_breaches.delay(org_id, email_hashes)
  → Returns 202 Accepted

Celery Worker:
  → Receives task
  → For each email hash prefix: GET https://haveibeenpwned.com/range/{prefix}
  → Parses response, compares suffix (k-anonymity — full hash never sent)
  → Inserts BreachRecord rows (scoped by org_id)
  → Triggers NotificationTask if new breach found
  → Updates MonitoredEmail.last_checked
```

## Tenant Isolation Model

Every database table that holds customer data has an `organization_id` column (FK → `organizations.id`). The ORM layer is the primary enforcement point:

```python
# All queries must follow this pattern:
result = await db.execute(
    select(MonitoredEmail)
    .where(MonitoredEmail.organization_id == current_org.id)
)
```

The `TenantIsolationMiddleware` provides defence-in-depth by parsing the JWT and populating `request.state.organization_id`, which endpoints use as the authoritative org identifier — never user-supplied query parameters.

## Auth Flow

```
POST /auth/register → bcrypt(password) → User row created, unverified
POST /auth/login    → verify password → check MFA if enabled
                    → access_token (15min JWT) + refresh_token (7d JWT)
POST /auth/refresh  → validate refresh_token → rotate both tokens
POST /auth/mfa/setup   → generate TOTP secret → return QR URI
POST /auth/mfa/verify  → verify TOTP code → enable MFA on user
```

Access tokens carry: `sub` (user_id), `org_id`, `role`, `type: "access"`.

## Module Architecture

Each module under `backend/app/modules/` follows the same pattern:

```
modules/breach_monitor/
├── __init__.py
├── router.py      # FastAPI router, endpoints, request/response schemas
├── service.py     # Business logic, DB operations
└── tasks.py       # Celery tasks (async background jobs)
```

This keeps concerns separated and makes each module independently testable.
