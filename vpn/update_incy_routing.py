#!/usr/bin/env python3
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

UPSTREAM_PROFILE = "https://raw.githubusercontent.com/GrimbirdUsers/ru-routing-dat/main/INCY/DEFAULT.JSON"
UPSTREAM_TREE = "https://api.github.com/repos/GrimbirdUsers/ru-routing-dat/git/trees/main?recursive=1"
UPSTREAM_COMMIT = "https://api.github.com/repos/GrimbirdUsers/ru-routing-dat/commits/main"
OUTPUT = Path(__file__).with_name("incy-routing-v4.json")
PROFILE_NAME = "🇷🇺 РФ напрямую · 🇫🇷 остальное v4"

DIRECT_GEOSITES = [
    "private",
    "category-ru-whitelist",
    "swift",
    "apple",
    "apple-dev",
    "apple-pki",
    "apple-update",
    "icloud",
    "icloudprivaterelay",
    "itunes",
    "beats",
]

PROXY_GEOSITES = [
    "category-ban-ru",
    "youtube",
    "google",
    "google-play",
    "telegram",
]

DIRECT_GEOIPS = ["private", "ru"]
PROXY_GEOIPS = []

DIRECT_DOMAINS = [
    "gosuslugi.ru",
    "esia.gosuslugi.ru",
    "gu-st.ru",
    "gazprombank.ru",
    "gpb.ru",
    "2ip.ru",
    "2ip.io",
    "api.2ip.io",
]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "PAVL-INCY-Routing-Updater/4.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def available_tags(tree):
    geosite = set()
    geoip = set()
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        if entry.get("type") != "blob":
            continue
        if path.startswith("data-geosite/"):
            name = path[len("data-geosite/"):]
            if "/" not in name:
                geosite.add(name)
        elif path.startswith("data-geoip/") and path.endswith(".txt"):
            name = path[len("data-geoip/"):-4]
            if "/" not in name:
                geoip.add(name)
    return geosite, geoip


def validate_tags(geosite, geoip):
    missing_geosite = sorted(set(DIRECT_GEOSITES + PROXY_GEOSITES) - geosite)
    missing_geoip = sorted(set(DIRECT_GEOIPS + PROXY_GEOIPS) - geoip)
    if missing_geosite or missing_geoip:
        parts = []
        if missing_geosite:
            parts.append("missing geosite tags: " + ", ".join(missing_geosite))
        if missing_geoip:
            parts.append("missing geoip tags: " + ", ".join(missing_geoip))
        raise RuntimeError("Routing validation failed: " + "; ".join(parts))


def upstream_timestamp(commit, upstream_profile):
    values = []
    try:
        values.append(int(upstream_profile.get("LastUpdated", 0)))
    except (TypeError, ValueError):
        pass
    try:
        iso = commit["commit"]["committer"]["date"]
        values.append(int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()))
    except (KeyError, TypeError, ValueError):
        pass
    return max(values or [0])


def versioned_geo_url(commit_sha, filename):
    return f"https://cdn.jsdelivr.net/gh/GrimbirdUsers/ru-routing-dat@{commit_sha}/{filename}"


def build_without_freshness(upstream, commit_sha):
    return {
        "Name": PROFILE_NAME,
        "GlobalProxy": "true",
        "RemoteDns": upstream.get("RemoteDns", "8.8.8.8"),
        "DomesticDns": upstream.get("DomesticDns", "77.88.8.8"),
        "RemoteDNSType": upstream.get("RemoteDNSType", "DoH"),
        "RemoteDNSDomain": upstream.get("RemoteDNSDomain", "https://8.8.8.8/dns-query"),
        "RemoteDNSIP": upstream.get("RemoteDNSIP", "8.8.8.8"),
        "DomesticDNSType": upstream.get("DomesticDNSType", "DoH"),
        "DomesticDNSDomain": upstream.get("DomesticDNSDomain", "https://common.dot.dns.yandex.net/dns-query"),
        "DomesticDNSIP": upstream.get("DomesticDNSIP", "77.88.8.8"),
        "Geoipurl": versioned_geo_url(commit_sha, "geoip.dat"),
        "Geositeurl": versioned_geo_url(commit_sha, "geosite.dat"),
        "DnsHosts": dict(upstream.get("DnsHosts", {})),
        "RouteOrder": "block-proxy-direct",
        "DirectSites": [f"geosite:{x}" for x in DIRECT_GEOSITES] + [f"domain:{x}" for x in DIRECT_DOMAINS],
        "DirectIp": [f"geoip:{x}" for x in DIRECT_GEOIPS],
        "ProxySites": [f"geosite:{x}" for x in PROXY_GEOSITES],
        "ProxyIp": [f"geoip:{x}" for x in PROXY_GEOIPS],
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
        "useChunkFiles": False,
    }


def parse_timestamp(profile):
    if not profile:
        return 0
    try:
        return int(profile.get("LastUpdated", 0))
    except (TypeError, ValueError):
        return 0


def main():
    previous = None
    if OUTPUT.exists():
        with OUTPUT.open("r", encoding="utf-8") as fh:
            previous = json.load(fh)

    upstream = get_json(UPSTREAM_PROFILE)
    tree = get_json(UPSTREAM_TREE)
    commit = get_json(UPSTREAM_COMMIT)

    geosite, geoip = available_tags(tree)
    validate_tags(geosite, geoip)

    commit_sha = commit.get("sha")
    if not commit_sha:
        raise RuntimeError("Upstream commit SHA is missing")

    profile = build_without_freshness(upstream, commit_sha)

    previous_comparable = dict(previous or {})
    previous_comparable.pop("LastUpdated", None)

    previous_ts = parse_timestamp(previous)
    upstream_ts = upstream_timestamp(commit, upstream)

    # LastUpdated must never move backwards. INCY uses it as the profile
    # freshness marker. If any effective routing/DNS/geodata content changes,
    # advance it to at least the current wall-clock time. If nothing changes,
    # keep the exact existing timestamp so the workflow produces no noisy commit.
    if previous and previous_comparable == profile:
        profile["LastUpdated"] = str(previous_ts)
    else:
        profile["LastUpdated"] = str(max(int(time.time()), previous_ts + 1, upstream_ts))

    if previous == profile:
        print("No routing changes")
        return

    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print("Validated and updated", OUTPUT, "from", commit_sha)


if __name__ == "__main__":
    main()
