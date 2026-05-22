# Market Events Calendar

Automatically scrapes high-importance (3-star) US economic events from TradingEconomics, converts times to Europe/Bucharest, and publishes a live-subscribable ICS calendar to Google Cloud Storage.

Updated every Friday at 07:10 UTC via GitHub Actions.

---

## Subscribe

**ICS URL:**
```
https://storage.googleapis.com/market-calendar-bucket-497119/Market.ics
```

### Option 1 — Direct download

Click the URL above or paste it into your browser. The `Market.ics` file will download automatically.

### Option 2 — Calendar subscription (auto-updates)

1. Copy the ICS URL above.
2. Open Google Calendar, Apple Calendar, Outlook, or any ICS-compatible app.
3. Find **Add calendar by URL** or **Subscribe**.
4. Paste the URL and confirm.

Your calendar will sync automatically each time the file is updated.

---

## How it works

- `calendar_sync.py` scrapes TradingEconomics for 3-star US events and an optional second source via `EVENT_URL`.
- Events are filtered by `data-country="united states"` and `calendar-date-3` (3-star importance class).
- Times are converted from UTC to Europe/Bucharest using `pytz`.
- Cross-scraper deduplication prevents duplicate entries when both sources overlap.
- `Market.ics` is saved locally, then uploaded to the GCS bucket by the GitHub Actions workflow.
