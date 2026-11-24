#!/usr/bin/env python3
"""Export the approved signals from the BASIN database to data/signals.json.

Why this exists
---------------
The website must never hold a database key, because everything on a public
page can be read by anyone. So the page reads a plain file instead, and this
script refreshes that file from the database on a schedule.

What it exports
---------------
Only signals whose RoutingStatus is "Approved": the ones a person has checked.
For each: title, our summary, link, dates, lenses, kind, horizon, regions,
geographic scope, sectors, trends, and the source's name, website, voice and tier.
The name and description of each trend are exported too.

Every signal should have a place: one or more regions, or a wider scope (Whole of
Basin, Australia, Asia-Pacific or Global). The export warns about any that has neither. Nothing else leaves the database.

Running it
----------
    NOCODB_TOKEN=... python3 scripts/export_signals.py

The token is read from the environment and is never printed or saved.
If no token is set the script says so and changes nothing.
If the approved signals are the same as last time, the file is left alone.
Standard library only. Python 3.8 or later.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

NOCODB_URL = os.environ.get("NOCODB_URL", "https://tables.safuturesagency.com.au")
TABLES = {"signals": "mfvzyv1coptbops", "regions": "mnai6n0qtjk00xh", "sectors": "m55zoinuwpq5dey",
          "sources": "mp7faeuytgv3h5k", "trends": "mkmk2swxur1wdrh"}
# The field on Regions and on Sectors that links back to Signals.
BACKLINK = {"regions": "cl1kdbjznk1eq2l", "sectors": "ccazbdnbpvxkb3k", "trends": "cq804jq0rl30eel"}
OUT = Path(__file__).resolve().parent.parent / "data" / "signals.json"


def call(path: str, token: str):
    request = urllib.request.Request(NOCODB_URL + path, headers={"xc-token": token})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def rows(path: str, token: str, **params) -> list[dict]:
    """Read every row behind an endpoint, a page at a time."""
    found, offset = [], 0
    while True:
        query = urllib.parse.urlencode({**params, "limit": 100, "offset": offset})
        page = call(f"{path}?{query}", token).get("list", [])
        found.extend(page)
        if len(page) < 100:
            return found
        offset += 100


def names_by_signal(kind: str, token: str) -> dict[int, list[str]]:
    """For regions or sectors: which names is each signal linked to?"""
    linked: dict[int, list[str]] = {}
    for item in rows(f"/api/v2/tables/{TABLES[kind]}/records", token, fields="Id,Name"):
        path = f"/api/v2/tables/{TABLES[kind]}/links/{BACKLINK[kind]}/records/{item['Id']}"
        for signal in rows(path, token, fields="Id"):
            linked.setdefault(signal["Id"], []).append(item["Name"])
    return linked


def source_for(url: str, sources: list[dict]) -> dict:
    """Match a link to its row in the source register. The longest match wins."""
    parts = urllib.parse.urlsplit(url or "")
    host = parts.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    address = (host + parts.path).rstrip("/")
    best: dict = {}
    for source in sources:
        domain = source.get("Domain") or ""
        hit = address == domain or address.startswith(domain + "/") or (
            "/" not in domain and host.endswith("." + domain))
        if domain and hit and len(domain) > len(best.get("Domain", "")):
            best = source
    return best


def published() -> dict | None:
    """The signals and trends in the file as it stands, or None if it cannot be read.

    The export compares against this and leaves the file alone when nothing has
    changed, so the site's history shows a change only when the signals change.
    """
    try:
        found = json.loads(OUT.read_text(encoding="utf-8"))
        return {"signals": found.get("signals"), "trends": found.get("trends")}
    except (OSError, ValueError, AttributeError):
        return None


def as_list(value) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def main() -> int:
    token = os.environ.get("NOCODB_TOKEN", "")
    if not token:
        print("NOCODB_TOKEN is not set, so nothing was exported. See the README.")
        return 0
    signals = rows(f"/api/v2/tables/{TABLES['signals']}/records", token,
                   where="(RoutingStatus,eq,Approved)",
                   fields="Id,Title,Summary,URL,PublishedDate,HarvestedDate,Valence,Horizon,SteepTags,BasinRelevance,GeographicScope")
    sources = rows(f"/api/v2/tables/{TABLES['sources']}/records", token, fields="Domain,Name,Tier,Voice")
    regions, sectors = names_by_signal("regions", token), names_by_signal("sectors", token)
    trends = names_by_signal("trends", token)
    trend_notes = [{"name": row.get("Name") or "", "description": row.get("Description") or ""}
                   for row in rows(f"/api/v2/tables/{TABLES['trends']}/records", token, fields="Name,Description")]
    out = []
    for signal in signals:
        source = source_for(signal.get("URL"), sources)
        out.append({
            "id": signal["Id"], "title": signal.get("Title") or "", "summary": signal.get("Summary") or "",
            "url": signal.get("URL") or "", "published": signal.get("PublishedDate"),
            "harvested": signal.get("HarvestedDate"), "valence": signal.get("Valence") or "",
            "horizon": as_list(signal.get("Horizon")), "steep": as_list(signal.get("SteepTags")),
            "relevance": signal.get("BasinRelevance") or "",
            "regions": sorted(regions.get(signal["Id"], [])), "scope": signal.get("GeographicScope") or "",
            "sectors": sorted(sectors.get(signal["Id"], [])), "trends": sorted(trends.get(signal["Id"], [])),
            "source": source.get("Name") or "", "source_domain": source.get("Domain") or "",
            "voice": source.get("Voice") or "", "tier": source.get("Tier"),
        })
    no_place = [item["id"] for item in out if not item["regions"] and item["scope"] in ("", "Basin region")]
    if no_place:
        print(f"WARNING: {len(no_place)} approved signals have no place. Their ids: {no_place}. "
              "Set GeographicScope or a region for each one in the Signals table.")
    if published() == {"signals": out, "trends": trend_notes}:
        print(f"No change: the same {len(out)} approved signals are already on the site.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                               "count": len(out), "trends": trend_notes, "signals": out},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Exported {len(out)} approved signals to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
