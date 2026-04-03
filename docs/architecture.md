# Corvin — Architecture

## High-Level Overview

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                         CORVIN PLATFORM                              │
 │                                                                      │
 │  ┌───────────────┐     HTTPS      ┌──────────────────────────────┐  │
 │  │  React 18 +   │ ─────────────► │   FastAPI (Python 3.12)      │  │
 │  │  Vite +       │ ◄───────────── │   Uvicorn ASGI  /api/v1/*    │  │
 │  │  Tailwind CSS │    JSON / PDF  │                              │  │
 │  └───────────────┘                └──────────┬───────────────────┘  │
 │                                              │                      │
 │                               ┌─────────────┼─────────────┐        │
 │                               ▼             ▼             ▼        │
 │                     ┌──────────────┐ ┌──────────┐ ┌────────────┐   │
 │                     │ PostgreSQL 16│ │ Redis 7  │ │  Celery    │   │
 │                     │ (async ORM)  │ │ (broker) │ │  Workers   │   │
 │                     │ Multi-tenant │ │          │ │  + Beat    │   │
 │                     └──────────────┘ └──────────┘ └─────┬──────┘   │
 │                                                          │          │
 │                                   ┌──────────────────────┤          │
 │                                   ▼                      ▼          │
 │                            ┌────────────┐         ┌───────────┐    │
 │                            │ External   │         │  Upload   │    │
 │                            │ APIs:      │         │  Storage  │    │
 │                            │ HIBP, VT,  │         │ /uploads  │    │
 │                            │ DNS, SMTP  │         └───────────┘    │
 │                            └────────────┘                          │
 └──────────────────────────────────────────────────────────────────────┘
```

## Docker Compose Services

| Service | Image | Role |
|---------|-------|------|
| `corvin-db` | `postgres:16` | Primary datastore |
| `corvin-redis` | `redis:7` | Celery broker + result backend |
| `corvin-api` | Custom FastAPI | REST API, JWT auth, all endpoints |
| `corvin-worker` | Custom Celery | Async task execution |
| `corvin-beat` | Custom Celery Beat | Periodic task scheduler |
| `corvin-frontend` | Custom Vite/Nginx | React SPA on port 3000 |

---

## Multi-Tenant Architecture

Every table has an `organization_id` FK. Isolation is enforced at two layers:

1. `TenantIsolationMiddleware`: extracts `org_id` from JWT → `request.state.organization_id`
2. All ORM queries: `.where(Model.organization_id == current_org.id)`

Cross-tenant access returns `404` (not `403`) to prevent existence disclosure.

---

## Authentication Flow

```
POST /auth/login  →  access_token (JWT, 15 min) + refresh_token (7 days)
GET /protected    →  TenantMiddleware → get_current_user → RBAC check
POST /auth/refresh →  new access_token + rotated refresh_token
```

The frontend intercepts 401 responses, refreshes automatically, and retries.

---

## Security Layers

| Layer | Implementation |
|-------|----------------|
| Passwords | bcrypt cost 12 via passlib |
| JWT | HS256, 15 min access tokens |
| MFA | TOTP RFC 6238, QR provisioning |
| Rate limiting | slowapi + Redis, 5/min on login |
| IMAP passwords | Fernet-encrypted at rest |
| Webhook secrets | Fernet + HMAC-SHA256 per payload |
| HIBP | k-anonymity: 5-char SHA1 prefix, SHA-256 stored |
| File upload | UUID filenames, MIME allowlist, 10 MB limit |
| Web scanner | Passive only: 20 req max, 300 ms throttle |
| Audit log | Append-only `audit_logs`, all mutations |

---

## Celery Queues & Beat Schedule

| Queue | Tasks |
|-------|-------|
| `breach` | `daily_breach_check_all_orgs` |
| `domain` | `daily_domain_scan_all` |
| `scanner` | `run_web_scan_task`, `scheduled_web_scans` (hourly) |
| `email` | `scan_email_account_task`, `daily_email_scan_all_orgs` |
| `sandbox` | `analyze_file_task` |
| `notifications` | `dispatch_notification_task` |
