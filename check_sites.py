"""
Cyprus Lake Campsite Availability Checker
Bruce Peninsula National Park — May 22–24, 2026

Strategy:
  1. Fetch the Parks Canada Cyprus Lake page and find the booking link
     which contains mapId and resourceLocationId in the URL
  2. Fetch resource list for that location to map resourceId → site name
  3. Check availability and notify via ntfy
"""

import os
import sys
import re
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs

TARGET_SITE_NAMES = {
    "101","102","103","104","105","106","107","108",
    "109","110","111","112","113","114","115","116","117","118",
    "223","226","227","228","232","233","238","240","242",
}

START_DATE  = "2026-05-22"
END_DATE    = "2026-05-24"
NIGHTS      = 2
NTFY_TOPIC  = os.environ.get("NTFY_TOPIC", "")
BASE_URL    = "https://reservation.pc.gc.ca"
BOOKING_URL = BASE_URL + "/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Referer": BASE_URL + "/",
}


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL, timeout=15)
    return s


def find_ids_from_parks_canada_page(session):
    """
    Fetch the Parks Canada Cyprus Lake camping page and look for
    reservation links containing mapId and resourceLocationId.
    """
    urls_to_check = [
        "https://parks.canada.ca/pn-np/on/bruce/activ/camping/cyprus",
        "https://parks.canada.ca/pn-np/on/bruce/activ/camping",
        "https://parks.canada.ca/pn-np/on/bruce/activ/reserve-reservation",
    ]

    for page_url in urls_to_check:
        print(f"\nFetching: {page_url}")
        try:
            r = session.get(page_url, timeout=15)
            print(f"  status: {r.status_code}")
            html = r.text

            # Look for reservation.pc.gc.ca links with mapId
            links = re.findall(
                r'https?://reservation\.pc\.gc\.ca[^\s\'"<>]*mapId[^\s\'"<>]*',
                html
            )
            if links:
                print(f"  Found {len(links)} booking link(s):")
                for link in links:
                    print(f"    {link}")
                    parsed = urlparse(link)
                    qs = parse_qs(parsed.query)
                    map_id = qs.get("mapId", [None])[0]
                    loc_id = qs.get("resourceLocationId", [None])[0]
                    if map_id:
                        print(f"  ✅ mapId={map_id} resourceLocationId={loc_id}")
                        return int(map_id), int(loc_id) if loc_id else None

            # Also search for just the IDs as numbers near reservation context
            reservation_mentions = re.findall(
                r'reservation\.pc\.gc\.ca[^\s\'"<>]{0,200}',
                html
            )
            if reservation_mentions:
                print(f"  reservation.pc.gc.ca mentions:")
                for m in reservation_mentions[:5]:
                    print(f"    {m}")

        except Exception as e:
            print(f"  error: {e}")

    return None, None


def find_ids_from_reservation_site(session):
    """
    Try fetching the reservation site's API to browse parks.
    """
    attempts = [
        # Try root map that contained the Tunnel Mountain parent
        (f"{BASE_URL}/api/maps", {"mapId": -2147483630}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483643}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483642}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483641}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483640}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483639}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483638}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483637}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483636}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483635}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483634}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483633}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483632}),
        (f"{BASE_URL}/api/maps", {"resourceLocationId": -2147483631}),
    ]

    for url, params in attempts:
        try:
            r = session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                maps = data if isinstance(data, list) else [data]
                for m in maps:
                    for lv in m.get("localizedValues", []):
                        if lv.get("cultureName") == "en-CA":
                            title = lv.get("title","") + " " + lv.get("description","")
                            if any(kw in title.lower() for kw in ["cyprus","bruce","peninsula"]):
                                loc_id = m.get("resourceLocationId")
                                map_id = m.get("mapId")
                                print(f"  ✅ FOUND: '{title}' mapId={map_id} resourceLocationId={loc_id}")
                                return map_id, loc_id
                            elif r.status_code == 200:
                                title_short = title[:60].strip()
                                print(f"  resourceLocationId={params.get('resourceLocationId','?')} → '{title_short}'")
        except Exception as e:
            print(f"  error {params}: {e}")

    return None, None


def build_resource_name_map(session, resource_location_id):
    """Get resourceId → site name mapping."""
    endpoints = [
        f"{BASE_URL}/api/resourcelocation/{resource_location_id}/resources",
        f"{BASE_URL}/api/resource?resourceLocationId={resource_location_id}",
    ]
    for url in endpoints:
        try:
            r = session.get(url, timeout=15)
            print(f"  {url} → {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                resources = data if isinstance(data, list) else data.get("resources", [])
                mapping = {}
                for res in resources:
                    rid = str(res.get("resourceId") or res.get("id",""))
                    name = (
                        res.get("name","")
                        or next(
                            (lv.get("name","") for lv in res.get("localizedValues",[])
                             if lv.get("cultureName","") == "en-CA"),
                            ""
                        )
                    )
                    if rid:
                        mapping[rid] = name
                print(f"  → {len(mapping)} resources")
                return mapping
        except Exception as e:
            print(f"  error: {e}")
    return {}


def check_availability(session, map_id, resource_name_map):
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
    r = session.get(url, params=params, timeout=20)
    print(f"  availability status: {r.status_code}")
    if r.status_code != 200:
        return []

    data = r.json()
    resource_avails = data.get("resourceAvailabilities", {})
    available = []
    for resource_id, avail_list in resource_avails.items():
        site_name = resource_name_map.get(str(resource_id), "").strip()
        if not site_name:
            continue
        # GoingToCamp: availability=0 means open
        is_available = any(a.get("availability") == 0 for a in avail_list)
        if site_name in TARGET_SITE_NAMES:
            print(f"  Site {site_name}: {'✅ AVAILABLE' if is_available else '❌ taken'}")
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

    # Phase 1: try to get IDs from Parks Canada website links
    print("\n--- Phase 1: Scrape Parks Canada booking links ---")
    map_id, loc_id = find_ids_from_parks_canada_page(session)

    # Phase 2: if not found, scan nearby resource location IDs
    if not map_id:
        print("\n--- Phase 2: Scan resource location IDs ---")
        map_id, loc_id = find_ids_from_reservation_site(session)

    if not map_id:
        print("\n❌ Could not find Cyprus Lake IDs.")
        sys.exit(1)

    print(f"\n✅ map_id={map_id}  resourceLocationId={loc_id}")

    print("\n--- Building resource name map ---")
    resource_name_map = {}
    if loc_id:
        resource_name_map = build_resource_name_map(session, loc_id)

    print("\n--- Checking availability ---")
    available = check_availability(session, map_id, resource_name_map)

    print("=" * 60)
    if available:
        print(f"🚨 AVAILABLE: {available}")
        send_notification(available)
    else:
        print("No target sites available.")
