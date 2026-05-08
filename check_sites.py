"""
Cyprus Lake Campsite Availability Checker
Bruce Peninsula National Park — May 22–24, 2026
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

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    print("Fetching homepage to establish session...")
    try:
        r = s.get(BASE_URL, timeout=15)
        print(f"  Homepage status: {r.status_code}")
        print(f"  Cookies: {dict(s.cookies)}")
    except Exception as e:
        print(f"  Homepage fetch failed: {e}")
    return s


def try_endpoint(session, url, params=None, label=""):
    print(f"\n[{label}] GET {url}")
    if params:
        print(f"  params: {params}")
    try:
        r = session.get(url, params=params, timeout=15)
        print(f"  status: {r.status_code}")
        snippet = r.text[:400].replace("\n", " ")
        print(f"  body:   {snippet}")
        if r.status_code == 200:
            return r
    except Exception as e:
        print(f"  error: {e}")
    return None


def find_map_id(session: requests.Session) -> int | None:
    # Pattern 1: resource location list
    r = try_endpoint(session,
        f"{BASE_URL}/api/resourcelocation/list/14",
        label="resourcelocation/list")
    if r:
        data = r.json()
        items = data if isinstance(data, list) else data.get("resourceLocations", [])
        for item in items:
            name = str(item.get("name","") or "").lower()
            if "cyprus" in name or "bruce" in name:
                mid = item.get("mapId") or item.get("id")
                print(f"  Found: {item.get('name')} mapId={mid}")
                return mid
        print("  Not found. All entries:")
        for item in items:
            print(f"    {item}")

    # Pattern 2: maps by known GoingToCamp resource location ID
    r = try_endpoint(session,
        f"{BASE_URL}/api/maps",
        params={"resourceLocationId": -2147483644},
        label="maps?resourceLocationId=-2147483644")
    if r:
        data = r.json()
        mid = data.get("id") or data.get("mapId")
        if mid:
            return mid
        print(f"  Keys: {list(data.keys()) if isinstance(data,dict) else type(data)}")

    # Pattern 3: direct map list
    r = try_endpoint(session,
        f"{BASE_URL}/api/maps/list",
        params={"resourceLocationId": 14},
        label="maps/list")
    if r:
        print(f"  Response: {r.text[:500]}")

    # Pattern 4: facilities under rec area
    r = try_endpoint(session,
        f"{BASE_URL}/api/resourcelocation/14/facilities",
        label="resourcelocation/14/facilities")
    if r:
        print(f"  Response: {r.text[:500]}")

    return None


def get_availability(session: requests.Session, map_id: int) -> list[dict]:
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
    r = try_endpoint(session, url, params=params, label="availability")
    if not r:
        return []
    data = r.json()
    sites = (
        data.get("availability")
        or data.get("mapLinkAvailabilities")
        or data.get("sites")
        or (data if isinstance(data, list) else [])
    )
    print(f"  Total sites: {len(sites)}")
    if sites:
        print(f"  Sample keys: {list(sites[0].keys())}")
        print(f"  Sample: {sites[0]}")
    return sites


def check_target_sites(sites: list[dict]) -> list[str]:
    available = []
    for site in sites:
        name = (
            str(site.get("name",""))
            or str(site.get("siteName",""))
            or str(site.get("mapLinkName",""))
        ).strip()
        is_available = (
            site.get("availability") == "Available"
            or site.get("isAvailable") is True
            or str(site.get("availability","")).lower() == "available"
            or site.get("availableCount", 0) > 0
        )
        if name in TARGET_SITE_NAMES:
            print(f"  Site {name}: {'✅ AVAILABLE' if is_available else '❌ taken'}")
            if is_available:
                available.append(name)
    return available


def send_notification(site_numbers: list[str]):
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
    print(f"Targets: {sorted(TARGET_SITE_NAMES)}")
    print("=" * 60)

    session = get_session()
    map_id = find_map_id(session)

    if not map_id:
        print("\nCould not determine map ID. See output above.")
        sys.exit(1)

    print(f"\nUsing map_id={map_id}")
    sites = get_availability(session, map_id)

    if not sites:
        print("No site data returned.")
        sys.exit(0)

    available = check_target_sites(sites)
    print("=" * 60)
    if available:
        print(f"AVAILABLE: {available}")
        send_notification(available)
    else:
        print("No target sites available.")
