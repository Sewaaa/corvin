# Corvin — Threat Model (STRIDE)

## Scope

This document covers the threat model for the Corvin SaaS platform:
API server, Celery workers, PostgreSQL, Redis, file upload, external API integrations.

---

## STRIDE Analysis

### S — Spoofing

| Threat | Mitigation |
|--------|------------|
| Attacker impersonates a legitimate user | JWT signed with HS256 + bcrypt password hashing (cost 12) |
| Attacker steals a valid JWT | Short 15-minute expiry; refresh token rotation on every use |
| Attacker replays a webhook payload | HMAC-SHA256 signature on every webhook (X-Corvin-Signature) |
| Email sender spoofing in email protection | SPF/DKIM/DMARC header parsing detects spoofed senders |

### T — Tampering

| Threat | Mitigation |
|--------|------------|
| DB row modification by cross-tenant actor | `organization_id` enforced at middleware + ORM; cross-tenant returns 404 |
| Audit log deletion/modification | Audit table is append-only; no UPDATE/DELETE routes exposed |
| File upload replaced after hash computation | SHA-256 computed before persistence; UUID filename prevents prediction |
| Webhook payload modification in transit | HMAC-SHA256 allows receiver to detect any tampering |

### R — Repudiation

| Threat | Mitigation |
|--------|------------|
| User denies performing an action | Append-only `audit_logs` table: action, user_id, IP, timestamp, resource |
| Admin denies config change | All org/user mutations go through `audit()` helper |

### I — Information Disclosure

| Threat | Mitigation |
|--------|------------|
| Email address leaked via HIBP | k-anonymity: only 5-char SHA1 prefix sent to HIBP; SHA-256 stored, never plaintext |
| Cross-tenant data access | Double enforcement (middleware + ORM); 404 instead of 403 |
| Sensitive headers in logs | `LoggingMiddleware` masks `Authorization` tokens and email patterns |
| IMAP password in DB | Fernet symmetric encryption; key derived from `secret_key` via SHA-256 |
| File content exposed | Files stored with UUID names; only authorized org members can access |
| Server version in HTTP response | `Server` header disclosure detected by web scanner and flagged as finding |

### D — Denial of Service

| Threat | Mitigation |
|--------|------------|
| Login brute-force | slowapi: 5 req/min per IP on `/auth/login` |
| File upload flooding | Max 10 MB per file; MIME allowlist rejects unexpected types |
| Web scan abuse | Max 20 HTTP requests per scan; domain ownership verification required |
| IMAP credential stuffing | IMAP connection tested before saving; no retry loop |
| Celery task flooding | Tasks dispatched one per account/domain; Celery retry limits (max 2-3) |

### E — Elevation of Privilege

| Threat | Mitigation |
|--------|------------|
| Analyst modifies other users' roles | `require_admin` dependency blocks role changes for non-admins |
| Viewer accesses admin endpoints | RBAC enforced per endpoint via FastAPI dependencies |
| Path traversal via filename | File stored with UUID name; original filename only stored in DB |
| SSRF via webhook URL | Webhook URL validated as HTTPS; no internal IP ranges allowed in production |

---

## Trust Boundaries

```
[Internet] → [Nginx/Load Balancer] → [corvin-api] → [PostgreSQL]
                                                   → [Redis]
                                                   → [External APIs]
[Celery Workers] ← [Redis] ← [corvin-api]
[File System] ← [corvin-api] (write) / [corvin-worker] (read)
```

- **External APIs** (HIBP, VirusTotal, DNS): treated as untrusted; responses are validated before persisting
- **Redis**: internal only; not exposed to the internet
- **File system**: only the `UPLOAD_DIR` volume is writable; path traversal prevented by UUID filenames

---

## Out of Scope

- Physical security of hosting infrastructure
- Browser-side XSS (frontend uses React, which escapes by default)
- Supply chain attacks on npm/PyPI packages (mitigated by `pip-audit` in CI)
