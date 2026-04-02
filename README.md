# Corvin

> **Silent guardian for your digital perimeter.**

Corvin is a SaaS cybersecurity platform that gives SMBs enterprise-grade protection without the enterprise complexity. It monitors email threats, data breaches, domain reputation, web vulnerabilities, and suspicious files — all from a single dashboard.

Named after *corvus* (Latin: raven) — a symbol of intelligence and foreknowledge. Corvin watches in the dark so you don't have to.

---

## Features

| Module | Description |
|--------|-------------|
| **Email Protection** | IMAP-based phishing detection, SPF/DKIM/DMARC validation, attachment scanning |
| **Breach Monitor** | Have I Been Pwned integration with k-anonymity — daily breach checks per email |
| **Domain Reputation** | DNS health, DNSBL checks, SSL expiry, VirusTotal reputation scoring |
| **Web Scanner** | Passive vulnerability scanner — security headers, exposed files, outdated CMS detection |
| **File Sandbox** | Static analysis with YARA rules, VirusTotal hash lookup, macro extraction |
| **Notifications** | Multi-channel alerting with severity-based routing and smart deduplication |

---

## Architecture

Multi-tenant SaaS with PostgreSQL row-level security. No tenant ever sees another tenant's data.

```
[React Frontend] → [FastAPI Backend] → [PostgreSQL + Redis]
                                    ↘ [Celery Workers] → [External APIs]
```

See [`docs/architecture.md`](docs/architecture.md) for the full component diagram and data flow.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### 1. Clone and configure

```bash
git clone https://github.com/Sewaaa/corvus.git
cd corvus
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start all services

```bash
docker-compose up -d
```

### 3. Run database migrations

```bash
docker-compose exec api alembic upgrade head
```

### 4. Access

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **API redoc**: http://localhost:8000/redoc

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `SECRET_KEY` | JWT signing key (generate with `openssl rand -hex 32`) | Yes |
| `HIBP_API_KEY` | Have I Been Pwned API key | Yes |
| `VIRUSTOTAL_API_KEY` | VirusTotal API v3 key | Optional |
| `SENDGRID_API_KEY` | SendGrid email API key | Optional |
| `SMTP_HOST` | SMTP server for notifications | Optional |

See [`.env.example`](.env.example) for the full list.

---

## Security

Corvin is built with security-first principles:

- **No hardcoded secrets** — all credentials via environment variables
- **Bcrypt** password hashing with configurable cost factor
- **TOTP MFA** — RFC 6238 compliant
- **Short-lived JWTs** — 15-minute access tokens + refresh token rotation
- **Tenant isolation** — enforced at middleware and ORM level
- **Rate limiting** — all endpoints via Redis (slowapi)
- **Passive scanning only** — web scanner never sends intrusive payloads
- **k-anonymity** — HIBP queries never expose full email hashes

See [`docs/threat-model.md`](docs/threat-model.md) for the full STRIDE analysis.

---

## Development

```bash
# Run tests
docker-compose exec api pytest

# Run SAST scan
docker-compose exec api bandit -r app/

# Check dependencies for vulnerabilities
docker-compose exec api pip-audit
```

---

## License

MIT — see LICENSE file.
