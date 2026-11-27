# Security Policy

## Scope

This policy covers `auth_audit.py`, its documentation, and any test fixtures
in this repository. The auditor is a read-only defensive checker: it fetches a
login page, inspects headers/cookies/form fields, and sends a bounded set of
failed login attempts to probe rate limiting. It performs no credential
spraying, injection testing, endpoint enumeration, or unauthorized access.

Explicitly **out of scope**: the previously reviewed active-testing source
(authentication bypass engine). That code is not distributed here and is not
covered by this policy.

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a vulnerability

Please report issues in the auditor itself — not in systems you ran it against.

- Use GitHub's **private vulnerability reporting** if enabled.
- Otherwise open a **minimal issue** with no exploit details, no target URLs,
  no credentials, and no session tokens.
- Request a private channel for the full report.

Include:

- Affected file / version / commit.
- Concise description and potential impact.
- Minimal reproduction steps in a **local test environment** (a fixture
  server you control, e.g. `python -m http.server` behind a stub login page).
- Suggested remediation if known.

## Responsible use expectations

The auditor is designed for use against login endpoints you own or have
**written authorization** to test.

- Keep `authorized_targets.json` to hosts you control.
- The rate-limit check sends 5 rapid failed logins — schedule it outside
  active user hours if your own lockout policy could affect real users.
- Do **not** point `-u` at third-party systems, even read-only checks.
- Do **not** collect, store, or share any response body, cookie, or token
  from a target you do not own.

Reports that describe unauthorized use of this tool will be closed.

## Secrets

Never commit:

- Passwords, API keys, bearer tokens, session cookies.
- Real `authorized_targets.json` entries for production hosts you don't own.
- Private keys, TLS material, or `.env` files.
- Response dumps that may contain other users' data.

If a secret is committed by accident:

1. **Revoke and rotate** it immediately.
2. Remove from git history (`git filter-repo` or BFG).
3. Force-push, notify collaborators.
4. Add a `.gitignore` rule + `git-secrets` / `detect-secrets` pre-commit hook
   so it can't recur.

## Disclosure timeline

- **Day 0** — report received via private channel.
- **Day 1–3** — acknowledgment and triage.
- **Day 7–30** — fix prepared and released, depending on severity.
- **Post-fix** — coordinated public disclosure with credit (on request).

If the issue is a **false-positive in a check** (e.g., a check incorrectly
reports FAIL on a correctly-hardened endpoint), that's still a valid bug —
report it as a correctness issue.

## Safe test environment

To reproduce issues without touching real systems:

```bash
# Minimal local login stub
python - <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<form method='post'><input name='username'><input type='password' name='password'></form>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        self.send_response(401)
        self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 8000), H).serve_forever()
PY

# authorized_targets.json
echo '{"targets":["http://127.0.0.1:8000"]}' > authorized_targets.json

python auth_audit.py -u http://127.0.0.1:8000/
