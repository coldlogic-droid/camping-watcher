"""
Cyprus Lake Campsite Availability Checker
Bruce Peninsula National Park — May 22–24, 2026

Target sites:
  Poplars:   101–118
  Tamaracks: 223, 226, 227, 228, 232, 233, 238, 240, 242

SETUP REQUIRED:
  After running the discover workflow, fill in the values below:
    CAMPGROUND_ID  — from camply campgrounds output
    TARGET_SITE_IDS — the internal IDs matching your target site numbers
                      (match them by name in the list-campsites output)
"""

import os
import sys
import subprocess
import requests
import json

# ─────────────────────────────────────────────────────────────────
# FILL THESE IN after running the discover workflow
# ─────────────────────────────────────────────────────────────────
CAMPGROUND_ID = "FILL_IN_AFTER_DISCOVERY"   # e.g. "232" or whatever Parks Canada uses

# Map of site number (as shown on Parks Canada site) → internal camply ID
# Run discover workflow, find your target sites in the list-campsites output,
# then paste their internal IDs here.
TARGET_SITES = {
    # "site_number": "internal_id",
    # Examples (replace with real values from discover output):
    # "101": "12345",
    # "223": "12399",
}
# ─────────────────────────────────────────────────────────────────

START_DATE = "2026-05-22"
END_DATE   = "2026-05-24"
NIGHTS     = 2
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
BOOKING_URL = "https://reservation.pc.gc.ca/"


def send_notification(site_numbers: list[str]):
    """Send an ntfy push notification to iOS."""
    if not NTFY_TOPIC:
        print("WARNING: NTFY_TOPIC not set — skipping notification")
        return

    site_list = ", ".join(site_numbers)
    message = (
        f"🏕️ CAMPSITE AVAILABLE!\n"
        f"Sites: {site_list}\n"
        f"Dates: {START_DATE} → {END_DATE}\n"
        f"Book NOW → {BOOKING_URL}"
    )

    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Campsite Alert — Bruce Peninsula",
                "Priority": "urgent",
                "Tags": "tent,rotating_light",
                "Click": BOOKING_URL,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"✅ Notification sent for sites: {site_list}")
        else:
            print(f"⚠️ ntfy returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Failed to send notification: {e}")


def check_availability() -> list[str]:
    """
    Use camply to check for available sites and return a list
    of available site numbers from our target list.
    """
    if CAMPGROUND_ID == "FILL_IN_AFTER_DISCOVERY" or not TARGET_SITES:
        print("ERROR: You must fill in CAMPGROUND_ID and TARGET_SITES.")
        print("Run the discover workflow first, then update check_sites.py.")
        sys.exit(1)

    internal_ids = list(TARGET_SITES.values())
    id_to_number = {v: k for k, v in TARGET_SITES.items()}

    # Build camply command — use silent mode (no looping, just check once)
    cmd = [
        "camply", "campsites",
        "--provider", "CanadaParks",
        "--campground", CAMPGROUND_ID,
        "--start-date", START_DATE,
        "--end-date", END_DATE,
        "--nights", str(NIGHTS),
        "--notifications", "silent",  # don't loop — we handle notification ourselves
    ]
    for site_id in internal_ids:
        cmd += ["--campsite-id", site_id]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        print("camply output:\n", output)

        # Parse which internal IDs appear as available in the output
        available_numbers = []
        for internal_id, site_number in id_to_number.items():
            if internal_id in output and (
                "Available" in output or "available" in output or "AVAILABLE" in output
            ):
                available_numbers.append(site_number)

        return available_numbers

    except subprocess.TimeoutExpired:
        print("camply timed out")
        return []
    except Exception as e:
        print(f"camply error: {e}")
        return []


if __name__ == "__main__":
    print(f"Checking availability for May 22–24 | Campground: {CAMPGROUND_ID}")
    print(f"Target sites: {list(TARGET_SITES.keys())}")
    print("─" * 50)

    available = check_availability()

    if available:
        print(f"\n🚨 AVAILABLE SITES FOUND: {available}")
        send_notification(available)
        sys.exit(0)
    else:
        print("\nNo target sites available right now. Will check again in 10 minutes.")
        sys.exit(0)
