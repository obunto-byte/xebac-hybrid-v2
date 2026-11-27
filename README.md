# XEBAC Auth Hardening Auditor

> **Status: Defensive release.** Audits *your own* login endpoints for missing
> protections. Read-only probing, allowlist-gated, no credential attempts.

`auth_audit.py` checks whether a login page has the defenses that attackers
look for — CSRF tokens, secure cookie flags, security headers, TLS version,
rate limiting. It does **not** attempt login, spray credentials, or send
injection payloads.

![XEBAC banner](assets/xebac-hybrid-v2-banner.svg)

## What it checks

| Check                       | Why it matters                                   |
|-----------------------------|--------------------------------------------------|
| CSRF token in form          | Missing token enables cross-site POST forgery    |
| HSTS header                 | Prevents TLS downgrade / cookie theft in transit |
| X-Frame-Options / CSP       | Blocks clickjacking on the login page            |
| X-Content-Type-Options      | Stops MIME sniffing XSS                          |
| Referrer-Policy / CSP       | Reduces token leakage via Referer                |
| Cookie Secure / HttpOnly / SameSite | Blocks session hijack via XSS or network |
| Rate limit / lockout        | Stops credential stuffing & brute runs           |
| TLS version ≥ 1.2           | Blocks BEAST/POODLE-class attacks                |
| Certificate validity        | Sanity for handshake                             |

## Requirements

- Python 3.9+
- `aiohttp`

```bash
pip install aiohttp
