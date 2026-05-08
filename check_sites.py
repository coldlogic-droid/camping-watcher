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

# No Accept-Encoding — let requests decompress automatically
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": BASE_URL + "/",
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    print("Fetching homepage...")
    try:
        r = s.get(BASE_URL, timeout=15)
        print(f"  Homepage status: {r.status_code}")
        print(f"  Cookies: {dict(s.cookies)}")
    except Exception as e:
        print(f"  Homepage failed: {e}")
    return s


def find_map_id(session: requests.Session) -> int | None:
    """
    /api/maps?resourceLocationId=-2147483644 returned 200 last run.
    Parse it to get the mapId for the availability query.
    """
    url = f"{BASE_URL}/api/maps"
    params = {"resourceLocationId": -2147483644}
    print(f"\nGET {url} params={params}")
    try:
        r = session.get(url, params=params, timeout=15)
        print(f"  status: {r.status_code}")
        print(f"  content-type: {r.headers.get('content-type','')}")
        print(f"  raw text (first 800 chars): {r.text[:800]}")

        if r.status_code != 200:
            return None

        data = r.json()
        print(f"\nParsed JSON type: {type(data)}")

        # Could be a list of maps or a single map object
        if isinstance(data, list):
            print(f"  {len(data)} map(s) returned:")
            for m in data:
                print(f"    {m}")
            if data:
                mid = data[0].get("id") or data[0].get("mapId")
                print(f"  Using first map id={mid}")
                return mid

        elif isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
            print(f"  Full: {data}")
            mid = data.get("id") or data.get("mapId")
            if mid:
                print(f"  map id={mid}")
                return mid

    except Exception as e:
        print(f"  Error: {e}")

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
    print(f"\nGET {url}")
    print(f"  params: {params}")
    try:
        r = session.get(url, params=params, timeout=20)
        print(f"  status: {r.status_code}")
        print(f"  body (first 800): {r.text[:800]}")
        if r.status_code != 200:
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
            print(f"  Sample site: {sites[0]}")
        return sites
    except Exception as e:
        print(f"  Error: {e}")
        return []


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
        print("\nCould not determine map ID.")
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
