"""GitHub API check and live-link checker.

Anything that fails is returned as "not assessed" so it is excluded from
scoring instead of being counted as zero.
"""
import ipaddress
import re
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

TIMEOUT = 6
UA = {"User-Agent": "IndustryReadinessApp/1.0"}


def normalize_url(url):
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _is_public_host(url):
    """Block localhost / private ranges so the checker can't be abused (SSRF)."""
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def check_link(url):
    url = normalize_url(url)
    result = {"url": url, "ok": False, "status": None, "note": ""}
    if not url:
        return result
    if not _is_public_host(url):
        result["note"] = "Could not resolve or not a public address"
        return result
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True, stream=True)
        result["status"] = r.status_code
        result["ok"] = r.status_code < 400
        r.close()
    except requests.RequestException as exc:
        result["note"] = type(exc).__name__
    return result


def github_username(value):
    value = (value or "").strip()
    if not value:
        return None
    m = re.search(r"github\.com/([\w\-]+)", value, re.I)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w\-]{1,39}", value):
        return value
    return None


def check_github(value):
    user = github_username(value)
    if not user:
        return {"assessed": False, "note": "No GitHub profile provided - not assessed"}
    try:
        r = requests.get(
            f"https://api.github.com/users/{user}/repos?per_page=100&sort=pushed",
            headers={**UA, "Accept": "application/vnd.github+json"},
            timeout=TIMEOUT,
        )
        if r.status_code == 404:
            return {"assessed": False, "username": user, "note": f"GitHub user '{user}' not found - not assessed"}
        if r.status_code != 200:
            return {"assessed": False, "username": user, "note": "GitHub API unavailable or rate-limited - not assessed"}
        repos = [x for x in r.json() if not x.get("fork")]
        cutoff = datetime.now(timezone.utc) - timedelta(days=120)
        recent = False
        for x in repos:
            pushed = x.get("pushed_at")
            if pushed and datetime.fromisoformat(pushed.replace("Z", "+00:00")) > cutoff:
                recent = True
                break
        return {
            "assessed": True,
            "username": user,
            "public_repos": len(repos),
            "repos_with_description": sum(1 for x in repos if x.get("description")),
            "languages": sorted({x["language"] for x in repos if x.get("language")}),
            "recent_activity": recent,
        }
    except requests.RequestException:
        return {"assessed": False, "username": user, "note": "GitHub could not be reached - not assessed"}


def gather(profile, cv):
    """Run GitHub + live-link checks. Never raises."""
    out = {"github": None, "live": [], "portfolio_site": None}
    gh_value = profile.get("github") or (cv.get("github_user") or "")
    out["github"] = check_github(gh_value)
    live_urls = [u for u in re.split(r"[\s,;]+", profile.get("live_urls", "") or "") if u][:5]
    out["live"] = [check_link(u) for u in live_urls]
    if profile.get("portfolio"):
        out["portfolio_site"] = check_link(profile["portfolio"])
    return out
