# Corvin — Threat Model (STRIDE)

This document models threats **to the Corvin platform itself**, not the threats it detects.

## Assets

| Asset | Sensitivity | Notes |
|-------|-------------|-------|
| User credentials (passwords) | Critical | bcrypt-hashed; never stored plaintext |
| TOTP MFA secrets | Critical | Stored encrypted at rest (TODO: KMS) |
| JWT signing key | Critical | Env var only; rotation policy needed |
| Organization data | High | Isolated per tenant |
| API keys (HIBP, VT) | High | Env vars only |
| Scan results / breach records | High | Contains sensitive findings |
| Audit log | High | Immutable; tamper-evident |
| File uploads (sandbox) | Medium | Stored isolated; never executed |

---

## STRIDE Analysis

### Spoofing

| Threat | Likelihood | Mitigation |
|--------|-----------|------------|
| JWT token forgery | Low | HS256 with 256-bit secret; short expiry (15min) |
| Session fixation | Low | Refresh token rotation on every use |
| Password brute-force | Medium | bcrypt (slow hash) + rate limiting on `/auth/login` |
| Credential stuffing | Medium | Rate limiting, account lockout (TODO) |
| MFA bypass | Low | TOTP verified server-side with 1-window tolerance |

### Tampering

| Threat | Likelihood | Mitigation |
|--------|-----------|------------|
| SQL injection | Low | SQLAlchemy ORM only; no raw queries |
| Input manipulation | Low | Pydantic strict validation on all inputs |
| Audit log modification | Low | Append-only table; no UPDATE/DELETE in ORM |
| File upload abuse | Medium | Magic byte detection; size limit (10MB); no execution |

### Repudiation

| Threat | Likelihood | Mitigation |
|--------|-----------|------------|
| Denying actions | Low | Immutable audit log with user_id, IP, timestamp |
| Log tampering | Low | Append-only audit_logs table; structured JSON logs |

### Information Disclosure

| Threat | Likelihood | Mitigation |
|--------|-----------|------------|
| Cross-tenant data leak | Low | org_id scoping + TenantIsolationMiddleware; integration test enforces this |
| Sensitive data in logs | Low | Email/token masking in LoggingMiddleware |
| API key exposure | Low | Env vars only; never in code or DB |
| HIBP email exposure | Low | k-anonymity: only SHA-1 prefix sent; suffix compared locally |
| Error message leakage | Medium | Generic 4xx/5xx in production; stack traces suppressed |

### Denial of Service

| Threat | Likelihood | Mitigation |
|--------|-----------|------------|
| API flooding | Medium | slowapi rate limiting on all public endpoints |
| Scanner DoS on targets | Low | Passive scan only; rate-limited requests to target |
| Large file upload DoS | Medium | 10MB hard limit; async processing via Celery |
| Redis exhaustion | Low | Celery task queue size limits (TODO) |

### Elevation of Privilege

| Threat | Likelihood | Mitigation |
|--------|-----------|------------|
| Role escalation | Low | RBAC enforced in dependencies; `require_admin` checks role |
| JWT claim manipulation | Low | Server-side signing; claims not trusted from client |
| IDOR (insecure direct object reference) | Low | All resource queries scoped by org_id |

---

## Out of Scope (Accepted Risks for Portfolio)

- Hardware security module (HSM) for key storage
- Formal penetration test
- SIEM integration
- mTLS between internal services
