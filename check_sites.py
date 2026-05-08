"""
Cyprus Lake Campsite Availability Checker
Bruce Peninsula National Park — May 22–24, 2026
Hits the Parks Canada / GoingToCamp API directly.
"""

import os
import sys
import requests
from datetime import datetime

# ─────────────────────────────────────────────────────────────────
# Target sites
# ─────────────────────────────────────────────────────────────────
TARGET_SITE_NAMES = {
    # Poplars
    "101", "102", "103", "104", "105", "106", "107", "108",
    "109", "110", "111", "112", "113", "114", "115", "116",
    "117", "118",
    # Tamaracks
    "223", "226", "227", "228", "232", "233", "238", "240", "242",
}

START_DATE  = "2026-05-22"
END_DATE    = "2026-05-24"
NIGHTS      = 2
NTFY_TOPIC  = os.environ.get("NTFY_TOPIC", "")
BOOKING_URL = "https://reservation.pc.gc.ca/"

# Parks Canada GoingToCamp API
BASE_URL       = "https://reservation.pc.gc.ca"
REC_AREA_ID    = 14          # Parks Canada on GoingToCamp
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; campsite-checker/1.0)",
    "Accept": "application/json",
    "Referer": BASE_URL,
}

# ─────────────────────────────────────────────────────────────────

def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    # Hit the homepage first to pick up any session cookies
    try:
        s.get(BASE_URL, timeout=15)
    except Exception:
        pass
    return s


def find_cyprus_lake_map_id(session: requests.Session) -> int | None:
    """
    Get all facilities/campgrounds for Parks Canada (rec area 14)
    and find Cyprus Lake's mapId.
    """
    url = f"{BASE_URL}/api/resourcelocation/list/{REC_AREA_ID}"
    try:
        resp = session.get(url, timeout=15)
        print(f"Resource location list status: {resp.status_code}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        # Look for Cyprus Lake / Bruce Peninsula
        for item in data:
            name = str(item.get("name", "") or item.get("localizedName", "")).lower()
            if "cyprus" in name or "bruce peninsula" in name:
                map_id = item.get("mapId") or item.get("id")
                print(f"Found: {item.get('name')} → mapId={map_id}")
                return map_id
        # If not found, print all options to help debug
        print("Cyprus Lake not found. Available facilities:")
        for item in data:
            print(f"  {item.get('name')} id={item.get('id')} mapId={item.get('mapId')}")
    except Exception as e:
        print(f"Error fetching facilities: {e}")
    return None


def get_availability(session: requests.Session, map_id: int) -> list[dict]:
    """
    Query the availability endpoint for the campground map.
    Returns list of available site objects.
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
    try:
        resp = session.get(url, params=params, timeout=20)
        print(f"Availability status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Response body: {resp.text[:500]}")
            return []
        data = resp.json()
        # Response is typically a dict with a "availability" or "mapLinkAvailabilities" key
        sites = (
            data.get("availability")
            or data.get("mapLinkAvailabilities")
            or data.get("sites")
            or (data if isinstance(data, list) else [])
        )
        print(f"Total sites returned: {len(sites)}")
        return sites
    except Exception as e:
        print(f"Error fetching availability: {e}")
        return []


def check_target_sites(sites: list[dict]) -> list[str]:
    """
    Filter available sites down to our target list.
    Returns list of available target site names/numbers.
    """
    available = []
    for site in sites:
        # GoingToCamp uses various field names
        name = (
            str(site.get("name", ""))
            or str(site.get("siteName", ""))
            or str(site.get("mapLinkName", ""))
        ).strip()
        is_available = (
            site.get("availability") == "Available"
            or site.get("isAvailable") is True
            or str(site.get("availability", "")).lower() == "available"
            or site.get("availableCount", 0) > 0
        )
        if is_available and name in TARGET_SITE_NAMES:
            available.append(name)
            print(f"  ✅ Site {name} is AVAILABLE")
    return available


def send_notification(site_numbers: list[str]):
    if not NTFY_TOPIC:
        print("WARNING: NTFY_TOPIC not set — skipping notification")
        return
    site_list = ", ".join(sorted(site_numbers))
    message = (
        f"🏕️ CAMPSITE AVAILABLE!\n"
        f"Sites: {site_list}\n"
        f"Dates: {START_DATE} to {END_DATE}\n"
        f"Book NOW: {BOOKING_URL}"
    )
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":    "Campsite Alert — Bruce Peninsula",
                "Priority": "urgent",
                "Tags":     "tent,rotating_light",
                "Click":    BOOKING_URL,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"✅ Notification sent for sites: {site_list}")
        else:
            print(f"⚠️  ntfy returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Failed to send notification: {e}")


if __name__ == "__main__":
    print(f"[{datetime.utcnow().isoformat()}] Checking availability {START_DATE} → {END_DATE}")
    print(f"Target sites: {sorted(TARGET_SITE_NAMES)}")
    print("─" * 60)

    session = get_session()

    map_id = find_cyprus_lake_map_id(session)
    if not map_id:
        print("Could not find Cyprus Lake map ID — dumping raw response for debugging")
        sys.exit(1)

    print(f"Cyprus Lake map ID: {map_id}")
    print("─" * 60)

    sites = get_availability(session, map_id)
    if not sites:
        print("No site data returned — may need to adjust API params")
        sys.exit(0)

    available = check_target_sites(sites)

    print("─" * 60)
    if available:
        print(f"🚨 AVAILABLE: {available}")
        send_notification(available)
    else:
        print("No target sites available right now.")
