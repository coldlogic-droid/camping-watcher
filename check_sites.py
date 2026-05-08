"""
Cyprus Lake Campsite Availability Checker
Bruce Peninsula National Park — May 22–24, 2026

Step 1: Find Cyprus Lake's resourceLocationId
Step 2: Get its maps and resource-to-site-name mapping
Step 3: Check availability correctly
"""

import os
import sys
import requests
from datetime import datetime

TARGET_SITE_NAMES = {
    "101","102","103","104","105","106","107","108",
    "109","110","111","112","113","114","115","116","117","118",
    "223","226","227","228","232","233","238","240","242",
}

START_DATE  = "2026-05-22"
END_DATE    = "2026-05-24"
NIGHTS      = 2
NTFY_TOPIC  = os.environ.get("NTFY_TOPIC", "")
BOOKING_URL = "https://reservation.pc.gc.ca/"
BASE_URL    = "https://reservation.pc.gc.ca"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Referer": BASE_URL + "/",
}


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL, timeout=15)
    return s


def find_cyprus_lake_location_id(session):
    """
    Try several endpoints to list all Parks Canada resource locations
    and find the one for Cyprus Lake / Bruce Peninsula.
    """
    endpoints_to_try = [
        f"{BASE_URL}/api/resourcelocation/list",
        f"{BASE_URL}/api/resourcelocation/search?query=cyprus",
        f"{BASE_URL}/api/resourcelocation/search?query=bruce",
        f"{BASE_URL}/api/resourcelocation/search?query=bruce+peninsula",
    ]

    for url in endpoints_to_try:
        print(f"\nTrying: {url}")
        try:
            r = session.get(url, timeout=15)
            print(f"  status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("resourceLocations", [])
                print(f"  {len(items)} locations returned")
                for item in items:
                    name = str(
                        item.get("name","")
                        or item.get("localizedName","")
                        or item.get("localizedValues",{}).get("name","")
                    ).lower()
                    if "cyprus" in name or "bruce" in name:
                        print(f"  ✅ MATCH: {item}")
                        return item.get("resourceLocationId") or item.get("id")
                # Print all if no match
                for item in items[:10]:
                    print(f"    {item.get('name') or item.get('localizedName')} "
                          f"id={item.get('resourceLocationId') or item.get('id')}")
                if len(items) > 10:
                    print(f"    ... and {len(items)-10} more")
        except Exception as e:
            print(f"  error: {e}")

    return None


def get_maps_for_location(session, resource_location_id):
    url = f"{BASE_URL}/api/maps"
    params = {"resourceLocationId": resource_location_id}
    print(f"\nGET {url} resourceLocationId={resource_location_id}")
    r = session.get(url, params=params, timeout=15)
    print(f"  status: {r.status_code}")
    if r.status_code != 200:
        return []
    data = r.json()
    maps = data if isinstance(data, list) else [data]
    print(f"  {len(maps)} map(s):")
    for m in maps:
        title = next(
            (lv.get("title","") for lv in m.get("localizedValues",[])
             if lv.get("cultureName","") == "en-CA"),
            m.get("mapId","")
        )
        print(f"    mapId={m['mapId']} title='{title}' resources={len(m.get('mapResources',[]))}")
    return maps


def build_resource_name_map(session, resource_location_id):
    """
    Query the resource details endpoint to get site names/numbers
    for each resourceId.
    Returns dict: resourceId -> site_name_string
    """
    url = f"{BASE_URL}/api/resourcelocation/{resource_location_id}/resources"
    print(f"\nGET {url}")
    try:
        r = session.get(url, timeout=15)
        print(f"  status: {r.status_code}  body: {r.text[:300]}")
        if r.status_code == 200:
            data = r.json()
            resources = data if isinstance(data, list) else data.get("resources", [])
            mapping = {}
            for res in resources:
                rid = str(res.get("resourceId") or res.get("id",""))
                name = (
                    res.get("name","")
                    or res.get("localizedName","")
                    or next(
                        (lv.get("name","") for lv in res.get("localizedValues",[])
                         if lv.get("cultureName","") == "en-CA"),
                        ""
                    )
                )
                if rid:
                    mapping[rid] = name
            print(f"  {len(mapping)} resources mapped")
            return mapping
    except Exception as e:
        print(f"  error: {e}")
    return {}


def check_availability(session, map_id, resource_name_map):
    """
    Query availability. In GoingToCamp:
      availability=0 → Available
      availability=1 → Not available (booked/restricted)
    Returns list of available target site names.
    """
    url = f"{BASE_URL}/api/availability/map"
    params = {
        "mapId":               map_id,
        "bookingCategoryId":   0,
        "startDate":           START_DATE,
        "endDate":             END_DATE,
        "nights":              NIGHTS,
        "isReservationResult": "true",
        "partySize":           1,
    }
    print(f"\nGET availability mapId={map_id}")
    r = session.get(url, params=params, timeout=20)
    print(f"  status: {r.status_code}")
    if r.status_code != 200:
        print(f"  body: {r.text[:300]}")
        return []

    data = r.json()
    resource_avails = data.get("resourceAvailabilities", {})
    print(f"  {len(resource_avails)} resources in availability response")

    available = []
    for resource_id, avail_list in resource_avails.items():
        site_name = resource_name_map.get(str(resource_id), "").strip()
        if not site_name:
            continue
        # availability=0 means available in GoingToCamp
        is_available = any(
            a.get("availability") == 0 for a in avail_list
        )
        if site_name in TARGET_SITE_NAMES:
            status = "✅ AVAILABLE" if is_available else "❌ taken"
            print(f"  Site {site_name} (id={resource_id}): {status}")
            if is_available:
                available.append(site_name)

    return available


def send_notification(site_numbers):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set — skipping")
        return
    site_list = ", ".join(sorted(site_numbers))
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"Sites {site_list} available May 22-24! Book: {BOOKING_URL}".encode(),
            headers={
                "Title":    "Campsite Alert — Bruce Peninsula",
                "Priority": "urgent",
                "Tags":     "tent,rotating_light",
                "Click":    BOOKING_URL,
            },
            timeout=10,
        )
        print(f"ntfy: {resp.status_code}")
    except Exception as e:
        print(f"ntfy error: {e}")


if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Checking {START_DATE} → {END_DATE}")
    print("=" * 60)

    session = get_session()

    loc_id = find_cyprus_lake_location_id(session)
    if not loc_id:
        print("\nCould not find Cyprus Lake resource location ID.")
        sys.exit(1)

    print(f"\n✅ Cyprus Lake resourceLocationId = {loc_id}")

    maps = get_maps_for_location(session, loc_id)
    if not maps:
        print("No maps found.")
        sys.exit(1)

    resource_name_map = build_resource_name_map(session, loc_id)

    available_all = []
    for m in maps:
        avail = check_availability(session, m["mapId"], resource_name_map)
        available_all.extend(avail)

    available_all = sorted(set(available_all))
    print("=" * 60)
    if available_all:
        print(f"🚨 AVAILABLE: {available_all}")
        send_notification(available_all)
    else:
        print("No target sites available.")
