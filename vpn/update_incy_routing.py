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
    req = urllib.request.Request(url, headers={"User-Agent": "PAVL-INCY-Routing-Updater/2.0"})
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
    return max(values or [int(time.time())])


def build(upstream, last_updated):
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
        "Geoipurl": upstream.get("Geoipurl", "https://cdn.jsdelivr.net/gh/GrimbirdUsers/ru-routing-dat@main/geoip.dat"),
        "Geositeurl": upstream.get("Geositeurl", "https://cdn.jsdelivr.net/gh/GrimbirdUsers/ru-routing-dat@main/geosite.dat"),
        "LastUpdated": str(last_updated),
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


def main():
    upstream = get_json(UPSTREAM_PROFILE)
    tree = get_json(UPSTREAM_TREE)
    commit = get_json(UPSTREAM_COMMIT)

    geosite, geoip = available_tags(tree)
    validate_tags(geosite, geoip)

    profile = build(upstream, upstream_timestamp(commit, upstream))

    previous = None
    if OUTPUT.exists():
        with OUTPUT.open("r", encoding="utf-8") as fh:
            previous = json.load(fh)

    if previous == profile:
        print("No routing changes")
        return

    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print("Validated and updated", OUTPUT)


if __name__ == "__main__":
    main()
