"""
Cyprus Lake Campsite Availability Checker — discovery + drill-down version

We know: Bruce Peninsula Overview Map = mapId -2147483584
Strategy:
  1. Fetch that overview map, list its mapLinks
  2. Follow links to find Cyprus Lake child map
  3. Drill into Cyprus Lake → list its mapLinks (Poplars, Tamaracks, Birches, ...)
  4. Print everything found so we can identify the target loops
"""

import os
import sys
import requests
from datetime import datetime

START_DATE = "2026-05-22"
END_DATE   = "2026-05-24"
BASE_URL   = "https://reservation.pc.gc.ca"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Referer": BASE_URL + "/",
}

BRUCE_OVERVIEW_MAP_ID = -2147483584


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL, timeout=15)
    return s


def map_title(m):
    for lv in m.get("localizedValues", []):
        if lv.get("cultureName") == "en-CA":
            t = lv.get("title","")
            d = lv.get("description","")
            return f"{t} — {d}".strip(" —")
    return str(m.get("mapId",""))


def fetch_map_by_id(session, map_id):
    """
    The /api/maps endpoint takes resourceLocationId. To get a single map by ID
    we need a different endpoint. Try a few.
    """
    candidates = [
        (f"{BASE_URL}/api/map", {"mapId": map_id}),
        (f"{BASE_URL}/api/maps", {"mapId": map_id}),
        (f"{BASE_URL}/api/map/{map_id}", None),
        (f"{BASE_URL}/api/maps/{map_id}", None),
    ]
    for url, params in candidates:
        try:
            r = session.get(url, params=params, timeout=10) if params else session.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and data.get("mapId"):
                    print(f"  ✅ {url} {params or ''} → mapId={data['mapId']}")
                    return data
                if isinstance(data, list) and data:
                    for m in data:
                        if m.get("mapId") == map_id:
                            print(f"  ✅ {url} {params or ''} → mapId={m['mapId']}")
                            return m
        except Exception as e:
            pass
    return None


def fetch_maps_for_location(session, resource_location_id):
    """Get all maps that share this resourceLocationId."""
    r = session.get(
        f"{BASE_URL}/api/maps",
        params={"resourceLocationId": resource_location_id},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    data = r.json()
    return data if isinstance(data, list) else [data]


def explore(session):
    print(f"Fetching Bruce Peninsula Overview Map (mapId={BRUCE_OVERVIEW_MAP_ID})...")
    overview = fetch_map_by_id(session, BRUCE_OVERVIEW_MAP_ID)
    if not overview:
        print("Could not fetch overview map — trying scan instead.")
        # Try scanning resourceLocationIds near Bruce Peninsula
        for rlid in range(-2147483600, -2147483500):
            maps = fetch_maps_for_location(session, rlid)
            for m in maps:
                t = map_title(m).lower()
                if "bruce" in t or "cyprus" in t or "tamarack" in t or "poplar" in t:
                    print(f"  rlid={rlid} mapId={m['mapId']} → '{map_title(m)}'")
        return

    print(f"\n  Title: {map_title(overview)}")
    print(f"  resourceLocationId: {overview.get('resourceLocationId')}")
    print(f"  parentMap: {overview.get('parentMap')}")

    map_links = overview.get("mapLinks", [])
    print(f"\n  {len(map_links)} mapLinks (children):")
    for link in map_links:
        loc_strs = [
            f"{lv.get('cultureName','')}={lv.get('title','')}"
            for lv in link.get("localizations", [])
        ]
        print(f"    childMapId={link.get('childMapId')} "
              f"resourceLocationId={link.get('resourceLocationId')} "
              f"titles=[{', '.join(loc_strs)}]")

    # For each child link, try to fetch and look for Cyprus Lake
    print("\n--- Drilling into each child ---")
    for link in map_links:
        child_id = link.get("childMapId")
        rlid = link.get("resourceLocationId")
        if not child_id:
            continue

        # Get title from the link itself
        title = ", ".join(
            lv.get("title","") for lv in link.get("localizations", [])
            if lv.get("cultureName") == "en-CA"
        )
        print(f"\n  childMapId={child_id} title='{title}' rlid={rlid}")

        if rlid:
            # Fetch all maps for this resourceLocationId
            maps = fetch_maps_for_location(session, rlid)
            print(f"    → {len(maps)} map(s) at this location:")
            for m in maps:
                t = map_title(m)
                print(f"      mapId={m['mapId']}  '{t}'  "
                      f"resources={len(m.get('mapResources',[]))} "
                      f"links={len(m.get('mapLinks',[]))}")

                # If this map has its own mapLinks, list those too
                for sublink in m.get("mapLinks", []):
                    sub_title = ", ".join(
                        lv.get("title","") for lv in sublink.get("localizations", [])
                        if lv.get("cultureName") == "en-CA"
                    )
                    print(f"        sublink → mapId={sublink.get('childMapId')} "
                          f"title='{sub_title}' rlid={sublink.get('resourceLocationId')}")


if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}]")
    print("=" * 60)
    session = get_session()
    explore(session)
