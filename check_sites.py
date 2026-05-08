"""
Cyprus Lake — Aggressive endpoint discovery for resource name mapping
"""

import os
import sys
import json
import requests
from datetime import datetime

START_DATE = "2026-05-22"
END_DATE   = "2026-05-24"
NIGHTS     = 2
BASE_URL   = "https://reservation.pc.gc.ca"

CYPRUS_LAKE_RLID  = -2147483636
POPLARS_MAP_ID    = -2147483581
SAMPLE_RID        = -2147481250

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Referer": BASE_URL + "/",
    "Content-Type": "application/json",
}


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL, timeout=15)
    return s


def show(label, r):
    print(f"\n[{label}]  {r.request.method} {r.url}")
    print(f"  status: {r.status_code}")
    snippet = r.text[:600].replace("\n", " ")
    print(f"  body:   {snippet}")


def test(session, method, path, params=None, body=None, label=None):
    url = BASE_URL + path
    try:
        if method == "GET":
            r = session.get(url, params=params, timeout=15)
        else:
            r = session.post(url, params=params, json=body, timeout=15)
        show(label or path, r)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return r.text
    except Exception as e:
        print(f"\n[{label or path}] ERROR: {e}")
    return None


def main():
    print(f"[{datetime.now().isoformat()}]")
    print("=" * 70)
    s = get_session()

    # 1. List ALL resourceCategories to see if there's site-level data
    print("\n### 1. All resourceCategories (full dump)")
    cats = test(s, "GET", "/api/resourceCategory",
                params={"resourceLocationId": CYPRUS_LAKE_RLID},
                label="resourceCategory")
    if isinstance(cats, list):
        print(f"\n  {len(cats)} categories:")
        for c in cats:
            name = next((lv["name"] for lv in c.get("localizedValues",[])
                         if lv.get("cultureName")=="en-CA"), "")
            print(f"    id={c.get('resourceCategoryId')}  name='{name}'  type={c.get('resourceType')}")

    # 2. Try POST availability/resourceLocation
    print("\n### 2. POST /api/availability/resourceLocation")
    test(s, "POST", "/api/availability/resourceLocation",
         body={
             "resourceLocationId":   CYPRUS_LAKE_RLID,
             "mapIds":               [POPLARS_MAP_ID],
             "startDate":            START_DATE,
             "endDate":              END_DATE,
             "nights":               NIGHTS,
             "bookingCategoryId":    0,
             "isReservationResult":  True,
             "partySize":            1,
         },
         label="POST availability/resourceLocation")

    # 3. GET availability/resourceLocation with all params
    print("\n### 3. GET /api/availability/resourceLocation (full params)")
    test(s, "GET", "/api/availability/resourceLocation",
         params={
             "resourceLocationId":   CYPRUS_LAKE_RLID,
             "mapId":                POPLARS_MAP_ID,
             "startDate":            START_DATE,
             "endDate":              END_DATE,
             "nights":               NIGHTS,
             "bookingCategoryId":    0,
             "isReservationResult":  "true",
             "partySize":            1,
         },
         label="GET availability/resourceLocation+params")

    # 4. Calendar-style availability
    print("\n### 4. /api/availability/resourceCategory")
    test(s, "GET", "/api/availability/resourceCategory",
         params={"resourceLocationId": CYPRUS_LAKE_RLID,
                 "startDate": START_DATE, "endDate": END_DATE},
         label="availability/resourceCategory")

    # 5. Try fetching individual resource availability
    print("\n### 5. Per-resource endpoints")
    test(s, "GET", f"/api/availability/resource/{SAMPLE_RID}", label="availability/resource/{id}")
    test(s, "GET", "/api/availability/resource",
         params={"resourceId": SAMPLE_RID, "startDate": START_DATE, "endDate": END_DATE},
         label="availability/resource?resourceId=")
    test(s, "GET", f"/api/resource/details/{SAMPLE_RID}", label="resource/details/{id}")
    test(s, "GET", "/api/resource/details", params={"resourceId": SAMPLE_RID}, label="resource/details?id")

    # 6. Calendar
    print("\n### 6. Calendar endpoints")
    test(s, "GET", "/api/calendar/availability",
         params={"resourceLocationId": CYPRUS_LAKE_RLID, "mapId": POPLARS_MAP_ID,
                 "startDate": START_DATE, "endDate": END_DATE},
         label="calendar/availability")

    # 7. Booking flow / search
    print("\n### 7. Booking / search")
    test(s, "GET", "/api/booking/resource",
         params={"resourceId": SAMPLE_RID, "startDate": START_DATE, "endDate": END_DATE},
         label="booking/resource")

    # 8. Try fetching the actual booking results page HTML and search for site names
    print("\n### 8. Fetching booking results page HTML")
    booking_url = (f"{BASE_URL}/create-booking/results"
                   f"?mapId={POPLARS_MAP_ID}"
                   f"&resourceLocationId={CYPRUS_LAKE_RLID}"
                   f"&startDate={START_DATE}&endDate={END_DATE}"
                   f"&nights={NIGHTS}&bookingCategoryId=0")
    print(f"  URL: {booking_url}")
    try:
        r = s.get(booking_url, timeout=20)
        print(f"  status: {r.status_code}")
        print(f"  length: {len(r.text)}")
        # Look for embedded JSON or site names
        import re
        nums = re.findall(r'"name"\s*:\s*"(\d+)"', r.text)
        if nums:
            print(f"  Found {len(nums)} numeric names embedded: {nums[:30]}")
        sites = re.findall(r'(?:Site|site)[\s_-]?(\d+)', r.text)
        if sites:
            print(f"  Found 'Site N' references: {set(sites[:30])}")
        # Look for resourceId references
        rids = re.findall(r'"resourceId"\s*:\s*(-?\d+)', r.text)
        if rids:
            print(f"  Found {len(rids)} resourceIds embedded")
        # Look for script tags with embedded data
        scripts = re.findall(r'window\.__\w+__\s*=\s*({.+?})\s*[;<]', r.text, re.DOTALL)
        for script in scripts[:2]:
            print(f"  Embedded data: {script[:300]}")
    except Exception as e:
        print(f"  error: {e}")


if __name__ == "__main__":
    main()
