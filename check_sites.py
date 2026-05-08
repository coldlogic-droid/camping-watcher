"""
Cyprus Lake — Find resourceId → site name mapping
Discovery only, no notification yet.
"""

import os
import sys
import requests
from datetime import datetime

START_DATE = "2026-05-22"
END_DATE   = "2026-05-24"
NIGHTS     = 2
BASE_URL   = "https://reservation.pc.gc.ca"

CYPRUS_LAKE_RLID  = -2147483636
POPLARS_MAP_ID    = -2147483581
BIRCHES_MAP_ID    = -2147483580
TAMARACKS_MAP_ID  = -2147483579

LOOPS = [
    ("Poplars",   POPLARS_MAP_ID),
    ("Birches",   BIRCHES_MAP_ID),
    ("Tamaracks", TAMARACKS_MAP_ID),
]

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


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL, timeout=15)
    return s


def try_endpoint(session, url, params=None, label=""):
    print(f"\n[{label}] GET {url}")
    if params: print(f"  params: {params}")
    try:
        r = session.get(url, params=params, timeout=15)
        print(f"  status: {r.status_code}")
        if r.status_code != 200:
            print(f"  body: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"  error: {e}")
        return None


def get_availability(session, map_id):
    """Get availability response — has resourceIds and their availability status."""
    data = try_endpoint(session,
        f"{BASE_URL}/api/availability/map",
        params={
            "mapId":               map_id,
            "bookingCategoryId":   0,
            "startDate":           START_DATE,
            "endDate":             END_DATE,
            "nights":              NIGHTS,
            "isReservationResult": "true",
            "partySize":           1,
        },
        label=f"availability mapId={map_id}",
    )
    if not data:
        return {}
    return data.get("resourceAvailabilities", {})


def try_get_resource_names(session, resource_location_id, sample_resource_id=None):
    """Try every endpoint pattern to find resource name → resourceId mapping."""
    print("\n" + "=" * 60)
    print("TRYING TO FIND RESOURCE NAMES")
    print("=" * 60)

    candidates = [
        f"{BASE_URL}/api/resource/list/{resource_location_id}",
        f"{BASE_URL}/api/resourceCategory/list/{resource_location_id}",
        f"{BASE_URL}/api/resourceCategory?resourceLocationId={resource_location_id}",
        f"{BASE_URL}/api/availability/resourceLocation",
        f"{BASE_URL}/api/availability/resourcelocation",
    ]
    for url in candidates:
        data = try_endpoint(session, url,
            params={"resourceLocationId": resource_location_id} if "?" not in url else None,
            label=url.split("/api/")[-1])
        if data:
            print(f"  Type: {type(data).__name__}")
            if isinstance(data, list) and data:
                print(f"  {len(data)} items, sample: {data[0]}")
            elif isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:20]}")
                # Find any items that look like resources
                for k, v in data.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        print(f"  {k}: {len(v)} items, sample: {v[0]}")
                        break

    if sample_resource_id:
        # Try fetching individual resource
        for url in [
            f"{BASE_URL}/api/resource/{sample_resource_id}",
            f"{BASE_URL}/api/resource?id={sample_resource_id}",
        ]:
            data = try_endpoint(session, url, label=f"single resource {sample_resource_id}")
            if data:
                print(f"  Got resource: {data}")


def main():
    print(f"[{datetime.now().isoformat()}]")
    session = get_session()

    print("\n" + "=" * 60)
    print("AVAILABILITY FOR EACH LOOP")
    print("=" * 60)

    sample_resource_id = None
    all_resources = {}  # resourceId -> {loop, availability}

    for loop_name, map_id in LOOPS:
        avails = get_availability(session, map_id)
        print(f"\n  {loop_name}: {len(avails)} resources returned")
        # Print first 3 entries as sample
        for i, (rid, alist) in enumerate(list(avails.items())[:5]):
            avail_codes = [a.get("availability") for a in alist]
            print(f"    resourceId={rid} availability={avail_codes}")
            if not sample_resource_id:
                sample_resource_id = rid
            all_resources[rid] = {"loop": loop_name, "availability": avail_codes}

        # Count by status
        counts = {}
        for rid, alist in avails.items():
            for a in alist:
                code = a.get("availability")
                counts[code] = counts.get(code, 0) + 1
        print(f"    Status code counts: {counts}")

    # Now try to find names
    try_get_resource_names(session, CYPRUS_LAKE_RLID, sample_resource_id)


if __name__ == "__main__":
    main()
