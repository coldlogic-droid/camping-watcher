# Cyprus Lake Campsite Watcher

Monitors Parks Canada for cancellations at Bruce Peninsula National Park (Cyprus Lake),
and pushes an iOS notification the moment a target site opens up.

**Target sites:** Poplars 101–118 | Tamaracks 223, 226, 227, 228, 232, 233, 238, 240, 242  
**Dates:** May 22–24, 2026

---

## Setup (do this once, in order)

### 1. Create the GitHub repo
- Go to github.com → New repository
- Name it `camping-watcher`
- Set it to **Public** (free unlimited Actions minutes)
- Push this folder to it

### 2. Set up ntfy on your iPhone
1. Install the **ntfy** app from the App Store
2. Open the app → tap **+** to add a subscription
3. Enter a unique topic name — something like `jass-camping-2026` (don't use something obvious)
4. Tap Subscribe

### 3. Add your ntfy topic as a GitHub Secret
1. In your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `NTFY_TOPIC`
4. Value: your topic name (e.g. `jass-camping-2026`)
5. Click Add secret

### 4. Run the Discovery workflow to get your campground and site IDs
1. Go to your repo → **Actions** tab
2. Click **🔍 Discover Site IDs (Run Once)**
3. Click **Run workflow** → Run
4. Once it finishes, click the run → read the output logs
5. From the output, find:
   - The **Recreation Area ID** for Bruce Peninsula National Park
   - The **Campground ID** for Cyprus Lake
6. Add these as GitHub **Variables** (not secrets — they're not sensitive):
   - Settings → Secrets and variables → Actions → **Variables** tab
   - `REC_AREA_ID` = the rec area ID
   - `CAMPGROUND_ID` = the campground ID
7. Run the discovery workflow again — this time Step 3 will list all sites
8. In the **list-campsites output**, find the internal IDs for your target sites:
   - Look for: Poplars 101–118 and Tamaracks 223, 226, 227, 228, 232, 233, 238, 240, 242
   - Note down the `campsite_id` column value for each

### 5. Fill in check_sites.py
Open `check_sites.py` and update:
```python
CAMPGROUND_ID = "FILL_IN"   # the campground ID from step 4

TARGET_SITES = {
    "101": "FILL_IN_INTERNAL_ID",
    "102": "FILL_IN_INTERNAL_ID",
    # ... all your target sites
    "223": "FILL_IN_INTERNAL_ID",
    "226": "FILL_IN_INTERNAL_ID",
    # etc.
}
```
Commit and push.

### 6. Test the monitor
1. Actions → **⛺ Campsite Monitor** → **Run workflow**
2. Check the logs — you should see camply running and "No target sites available" (or a notification if you got lucky)
3. Check your ntfy app — if a site was found, you'll have a notification

### 7. You're done
The monitor now runs automatically every 10 minutes.
When a target site opens, you get an urgent push notification with a direct link to book.

---

## How to stop it
Go to Actions → **⛺ Campsite Monitor** → click the **...** menu → **Disable workflow**

## Troubleshooting
- **No notification received:** Go to Actions and check the last run's logs for errors
- **camply error about IDs:** Re-run the discover workflow and double-check the IDs in check_sites.py
- **ntfy not receiving:** Make sure the NTFY_TOPIC secret exactly matches what you subscribed to in the app
