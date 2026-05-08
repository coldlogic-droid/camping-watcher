"""
Cyprus Lake Campsite Watcher — Production
Bruce Peninsula National Park
Dates: May 22-24, 2026 (2 nights)

Monitors three loops and fires an ntfy alert when any site opens up:
  - Poplars   (mapId -2147483581)  — user wants ANY site
  - Birches   (mapId -2147483580)  — user wants 101-118
  - Tamaracks (mapId -2147483579)  — user wants 223,226,227,228,232,233,238,240,242

Strategy:
  Since the API doesn't expose resourceId→site-number mapping, we notify on
  ANY status-0 (available) site in each loop. The notification includes a
  direct link to that loop so the user can verify the specific site and book.

GoingToCamp availability codes seen so far:
  0 = Available (the target — fire alert)
  1 = Reserved
  4 = Closed/Restricted
  7 = Other restriction (winter-only / first-come)
"""

import os
import sys
import requests
from datetime import datetime

# Trip parameters
START_DATE = "2026-05-22"
END_DATE   = "2026-05-24"
NIGHTS     = 2

# Cyprus Lake at Bruce Peninsula National Park
BASE_URL          = "https://reservation.pc.gc.ca"
CYPRUS_LAKE_RLID  = -2147483636

LOOPS = [
    {"name": "Poplars",   "map_id": -2147483581, "site_range": "1-63"},
    {"name": "Birches",   "map_id": -2147483580, "site_range": "100-198"},
    {"name": "Tamaracks", "map_id": -2147483579, "site_range": "201-281"},
]

# Codes that mean the site is bookable
AVAILABLE_CODES = {0}

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

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


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL, timeout=15)
    return s


def check_loop(session: requests.Session, loop: dict) -> int:
    """
    Returns count of available sites (status 0) in the given loop.
    """
    url = f"{BASE_URL}/api/availability/map"
    params = {
        "mapId":               loop["map_id"],
        "bookingCategoryId":   0,
        "startDate":           START_DATE,
        "endDate":             END_DATE,
        "nights":              NIGHTS,
        "isReservationResult": "true",
        "partySize":           1,
    }
    try:
        r = session.get(url, params=params, timeout=20)
        if r.status_code != 200:
            print(f"  {loop['name']}: HTTP {r.status_code}")
            return 0
        data = r.json()
        resource_avails = data.get("resourceAvailabilities", {})

        available_count = 0
        status_breakdown = {}
        for rid, alist in resource_avails.items():
            for a in alist:
                code = a.get("availability")
                status_breakdown[code] = status_breakdown.get(code, 0) + 1
                if code in AVAILABLE_CODES:
                    available_count += 1

        print(f"  {loop['name']:10s} ({loop['site_range']}): "
              f"{len(resource_avails)} sites, "
              f"available={available_count}, breakdown={status_breakdown}")
        return available_count
    except Exception as e:
        print(f"  {loop['name']}: ERROR {e}")
        return 0


def booking_url_for(loop: dict) -> str:
    return (
        f"{BASE_URL}/create-booking/results"
        f"?mapId={loop['map_id']}"
        f"&resourceLocationId={CYPRUS_LAKE_RLID}"
        f"&startDate={START_DATE}&endDate={END_DATE}"
        f"&nights={NIGHTS}&bookingCategoryId=0"
    )


def send_notification(alerts: list[dict]):
    if not NTFY_TOPIC:
        print("WARNING: NTFY_TOPIC not set — skipping notification")
        return

    lines = [f"🏕️  Cyprus Lake openings for {START_DATE} → {END_DATE}!"]
    for a in alerts:
        lines.append(f"• {a['name']} ({a['site_range']}): {a['count']} site(s)")
    lines.append("")
    lines.append("Tap to book — book FAST, cancellations get snapped up in minutes.")

    message = "\n".join(lines)
    primary_url = booking_url_for(alerts[0]["loop"])

    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":    "Campsite Alert — Bruce Peninsula",
                "Priority": "urgent",
                "Tags":     "tent,rotating_light",
                "Click":    primary_url,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"✅ Notification sent")
        else:
            print(f"⚠️  ntfy returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Notification failed: {e}")


def main():
    print(f"[{datetime.now().isoformat()}] Checking Cyprus Lake {START_DATE} → {END_DATE}")
    session = get_session()

    alerts = []
    for loop in LOOPS:
        count = check_loop(session, loop)
        if count > 0:
            alerts.append({
                "loop":       loop,
                "name":       loop["name"],
                "site_range": loop["site_range"],
                "count":      count,
            })

    if alerts:
        print(f"\n🚨 {len(alerts)} loop(s) have openings!")
        for a in alerts:
            print(f"   {a['name']}: {a['count']} sites")
            print(f"   {booking_url_for(a['loop'])}")
        send_notification(alerts)
    else:
        print("\nNo openings. Will check again in 10 minutes.")


if __name__ == "__main__":
    main()
