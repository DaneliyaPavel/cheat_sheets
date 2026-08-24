#!/usr/bin/env python3
import json
import socket
import time
import urllib.request
from pathlib import Path

UPSTREAM = "https://raw.githubusercontent.com/GrimbirdUsers/ru-routing-dat/main/INCY/DEFAULT.JSON"
OUTPUT = Path(__file__).with_name("incy-routing-v3.json")
PROFILE_NAME = "PAVL — РФ напрямую"
CONTROL_DOMAIN = "2ip.ru"


def load_upstream():
    req = urllib.request.Request(UPSTREAM, headers={"User-Agent": "PAVL-INCY-Routing-Updater/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def resolve_ipv4(domain):
    result = []
    for info in socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM):
        ip = info[4][0]
        if ip not in result:
            result.append(ip)
    return result


def unique(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def build(upstream, previous=None):
    control_ips = resolve_ipv4(CONTROL_DOMAIN)

    direct_sites = [x for x in upstream.get("DirectSites", []) if x != "geosite:category-ban-ru"]
    direct_sites.append(f"domain:{CONTROL_DOMAIN}")

    proxy_sites = list(upstream.get("ProxySites", []))
    proxy_sites.append("geosite:category-ban-ru")

    direct_ip = list(upstream.get("DirectIp", [])) + control_ips

    dns_hosts = dict(upstream.get("DnsHosts", {}))
    if control_ips:
        dns_hosts[CONTROL_DOMAIN] = control_ips[0]

    profile = {
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
        "Geoipurl": upstream["Geoipurl"],
        "Geositeurl": upstream["Geositeurl"],
        "DnsHosts": dns_hosts,
        "RouteOrder": "block-proxy-direct",
        "DirectSites": unique(direct_sites),
        "DirectIp": unique(direct_ip),
        "ProxySites": unique(proxy_sites),
        "ProxyIp": list(upstream.get("ProxyIp", [])),
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
        "useChunkFiles": False,
    }

    previous_last_updated = 0
    if previous:
        try:
            previous_last_updated = int(previous.get("LastUpdated", 0))
        except (TypeError, ValueError):
            pass

    try:
        upstream_last_updated = int(upstream.get("LastUpdated", 0))
    except (TypeError, ValueError):
        upstream_last_updated = 0

    # Compare everything except freshness marker. If routing content changed
    # (including 2ip DNS), force a fresh timestamp. Otherwise inherit a newer
    # upstream timestamp only when the upstream geo/profile actually advanced.
    comparable_previous = dict(previous or {})
    comparable_previous.pop("LastUpdated", None)
    comparable_new = dict(profile)

    if comparable_previous != comparable_new:
        last_updated = int(time.time())
    else:
        last_updated = max(previous_last_updated, upstream_last_updated)

    profile["LastUpdated"] = str(last_updated)
    return profile


def main():
    previous = None
    if OUTPUT.exists():
        with OUTPUT.open("r", encoding="utf-8") as fh:
            previous = json.load(fh)

    upstream = load_upstream()
    profile = build(upstream, previous)

    if previous == profile:
        print("No routing changes")
        return

    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("Updated", OUTPUT)


if __name__ == "__main__":
    main()
