# XEBAC Hybrid v2

> **Status: Safe defensive release. The original active-testing source is not included; this repository includes a passive local Python source reviewer.**

XEBAC Hybrid v2 is a web-application security assessment project intended for learning and authorized security reviews. The supplied source was reviewed and contains active authentication-testing and probing routines. This repository currently publishes project documentation and safety requirements only—not the operational testing code.

![XEBAC Hybrid v2 banner](assets/xebac-hybrid-v2-banner.svg)

## Project purpose

The reviewed source contains code paths related to web technology reconnaissance, login-form inspection, authentication request variations, route/path discovery, user/object access-control checks, token-pattern detection, and JSON-style reporting. These are static source-review observations, not a guarantee that each check is reliable or production-ready.

## Publication note

The original executable source is intentionally not distributed. The reviewed version includes active credential/authentication tests, IDOR-style probing, sensitive-path requests, token collection, and potentially state-changing payloads. Instead, this repository includes `safe_local_review.py`, a limited read-only checker for a few common Python source misconfigurations. It performs no network requests, login tests, endpoint enumeration, or remote probing.

## Requirements and running

The passive reviewer uses only the Python standard library (Python 3.9+ recommended). From the repository directory, run:

```bash
python safe_local_review.py .
```

To review another local project directory, pass its path:

```bash
python safe_local_review.py "C:/path/to/your/project"
```

This is a small heuristic checker, not a vulnerability scanner or proof of security. It prints finding locations and recommendations but does not print matched source lines, to reduce the risk of exposing secrets.

## Authorized-use requirements

Only assess applications that you own or for which you have explicit, written authorization. Define the scope, use test accounts, agree on a time window and rate limits, and stop if testing affects availability, data integrity, or other users. Never collect or retain real users' credentials, session tokens, or private data.

See [TERMS.md](TERMS.md), [SECURITY.md](SECURITY.md), and [TECHNICAL-REVIEW.md](TECHNICAL-REVIEW.md).

## Limitations

- Static review is not a full security audit.
- Heuristic response checks can produce false positives and false negatives.
- No independent test suite or reproducible safe test environment is included.
- No production-readiness or compliance certification is claimed.

## Contributions

Documentation, safe test fixtures, defensive analysis, and non-invasive checks are welcome. Do not submit credential attacks, bypass payloads, destructive probes, secret harvesting, or changes intended to access systems without authorization.

## Disclaimer

This project is provided for educational and authorized defensive-security purposes. Users are responsible for obtaining permission and complying with applicable laws. See [TERMS.md](TERMS.md).
