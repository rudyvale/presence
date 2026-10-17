import json
import os
import socket
import ssl
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DOMAIN = "presence.news"
REPOSITORY = "rudyvale/presence"


def report(title: str, message: str, error: bool = False) -> None:
    print(f"{title}: {message}", flush=True)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{'error' if error else 'notice'} title={title}::{escaped}", flush=True)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a") as output:
            output.write(f"**{title}:** {message}\n\n")


def dns_records(kind: str) -> list[str]:
    result = subprocess.run(["dig", "+short", "+time=5", "+tries=1", DOMAIN, kind], capture_output=True, text=True, check=True, timeout=10)
    return result.stdout.strip().splitlines()[:20]


def pages_settings() -> None:
    token = os.environ.get("GH_TOKEN")
    if not token:
        report("Pages settings", "No runtime token available; HTTPS and DNS checks will still run")
        return
    request = Request(f"https://api.github.com/repos/{REPOSITORY}/pages", headers={"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
    except HTTPError as error:
        report("Pages settings", f"Read-only API returned HTTP {error.code}")
        return
    fields = {key: data.get(key) for key in ("status", "cname", "https_enforced")}
    fields["certificate"] = {key: (data.get("https_certificate") or {}).get(key) for key in ("state", "description", "expires_at")}
    report("Pages settings", json.dumps(fields))


def main() -> None:
    failures = []
    pages_settings()
    for kind in ("A", "AAAA", "CNAME", "NS"):
        try:
            report("Public DNS", f"{DOMAIN} {kind}: {', '.join(dns_records(kind)) or '(none)'}")
        except (OSError, subprocess.SubprocessError) as error:
            failures.append(f"DNS {kind}: {error}")
    try:
        with socket.create_connection((DOMAIN, 443), timeout=15) as connection:
            with ssl.create_default_context().wrap_socket(connection, server_hostname=DOMAIN) as secure:
                certificate = secure.getpeercert()
                report("TLS certificate", json.dumps({"subjectAltName": certificate.get("subjectAltName"), "notAfter": certificate.get("notAfter"), "protocol": secure.version()}))
    except (OSError, ssl.SSLError) as error:
        failures.append(f"TLS validation: {error}")
    for route, expected in (("/", b"PRESENCE"), ("/news/", b"Latest news")):
        try:
            with urlopen(Request(f"https://{DOMAIN}{route}", headers={"User-Agent": "PresenceHostingCheck/1.0"}), timeout=20) as response:
                document = response.read(2 * 1024 * 1024)
                if response.status != 200 or expected.lower() not in document.lower():
                    raise ValueError("Expected Presence page is missing")
                if response.url.split("/")[2] != DOMAIN:
                    raise ValueError("The domain redirects away from Presence")
                report("HTTPS page", f"{route}: HTTP 200; expected Presence content verified")
        except (URLError, OSError, ValueError) as error:
            failures.append(f"{route}: {error}")
    for failure in failures:
        report("Hosting failure", failure, error=True)
    if failures:
        raise SystemExit(1)
    report("Hosting health", "Public DNS resolved; trusted certificate matches presence.news; homepage and news are accessible over HTTPS")


if __name__ == "__main__":
    main()
