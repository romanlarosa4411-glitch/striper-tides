# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Start the web server (requires venv)
.venv/bin/python3 app.py
# → http://localhost:5001

# Install dependencies
.venv/bin/pip install -r requirements.txt

# Initialize database (also runs on app startup)
.venv/bin/python3 db.py
```

The dev server is configured in `.claude/launch.json` for `preview_start` on port 5001. The venv is at `.venv/` using system Python 3. In production (Render), the app reads `PORT` from the environment variable.

## Deployment

Hosted on Render.com, auto-deploys from `main` branch on GitHub (`romanlarosa4411-glitch/striper-tides`). Build command: `pip install -r requirements.txt`. Start command: `python app.py`. Push to `main` triggers a redeploy.

**Render filesystem is ephemeral** — uploaded photos in `static/uploads/` are wiped on every redeploy. Photo upload UI exists but persistent storage (Cloudinary/S3) has not been wired up yet.

## Architecture

**Flask app** with four Python modules, one monolithic SPA template, and server-rendered SEO pages:

- **`striper_tides.py`** — Core engine (~1960 lines). All data fetching (NOAA tides, NWS weather, NDBC buoys, Open-Meteo marine models), astronomical calculations (solar via Astral, lunar via ephem), scoring algorithms, forecast logic, and species-specific fishing conditions.
- **`app.py`** — Flask routes and API layer. Thin wrapper that calls into `striper_tides.py`, manages an in-memory daily cache (`_cache` dict keyed by date), and serves JSON endpoints. Handles journal/clarity/comments CRUD against SQLite. Also serves `/robots.txt`, `/sitemap.xml`, and the per-spot SEO pages.
- **`spots_content.py`** — Single source of truth for the 25 spot writeups (slug, display title, blurb) plus `REGION_LABELS`/`REGION_ORDER`. Used by the spot pages, the About tab, and the sitemap. Edit spot copy here, nowhere else.
- **`db.py`** — SQLite setup. Three tables: `journal_entries` (fishing logs with auto-filled NOAA conditions), `clarity_reports` (crowd-sourced water clarity), and `comments` (Bite Talk community thread). WAL mode, Row factory.
- **`templates/index.html`** — Full SPA with embedded CSS + vanilla JS (~2780 lines). Five tabs: Tide Calendar (with weekly report), Water Clarity, Local Reports (journal + Bite Talk), About. Chart.js for visualizations. About tab spot cards render from `about_groups` (Jinja loop over `spots_content.py` data).
- **`templates/spot.html`** + **`templates/spots_index.html`** — Server-rendered SEO pages: `/spots` hub and `/spots/<slug>` for each of the 25 spots (7-day NOAA tide table, writeup, same-region links). All in the sitemap. Built so each spot can rank for "[spot] tides" / "[spot] fishing" queries.

## Key External APIs

| API | Purpose | Key Constants |
|-----|---------|---------------|
| NOAA CO-OPS | Tide predictions (hilo + hourly) + water temp | 12 station IDs in `SPOT_CONFIG`, Cape May station `8536110` for temp |
| NWS api.weather.gov | Wind observations (KWWD) + hourly forecast (PHI/63,33) | Grid point covers Cape May County |
| NDBC Buoys | Real-time wave data | 44009 (Cape May), 44025 (LBI) |
| Open-Meteo Marine | GFS/ECMWF wave model forecasts | `ncep_gfswave025`, `ecmwf_wam025` |

## Data Flow

1. `get_events(days)` is the master function — scores every tidal event across a date range using `_score_event()` with 7 factors (raw max 135, normalized 0–100): tidal range 0-35, time of day 0-30, season 0-20, moon 0-15, plus three **boost-only** factors (wind 0-15, pressure trend 0-10, temp trend 0-10) that only add points, never subtract.
2. `/api/forecast/<date>` assembles a full day view: hourly tides for all 12 spots, solunar windows, marine conditions, solar/moon data, and a fishing outlook via `get_day_fishing_outlook()`.
3. `get_day_fishing_outlook(d, water_temp_f, wind_mph, wind_deg, temp_change_f)` returns season/moon/temp/wind context plus a `species` list with flounder and weakfish conditions (active months only). The `temp_change_f` is a 3-day delta from `fetch_water_temp_trend()` and is the key input for flounder suppression logic.
4. `/api/surf?spot=X&model=Y` returns wave history + 7-day forecast from Open-Meteo (or wind-estimated fallback via "striper" model).
5. Clarity model in `get_clarity_forecast()` estimates turbidity from wave energy, wind, tidal range, and rain.

## Important Patterns

- **Caching**: `_cache` dict in app.py keys by `prefix:today:params`. Refreshes daily. The forecast cache is invalidated by day, not by content — restart the server to bust it during development.
- **Graceful degradation**: All external API calls wrapped in try/except. Missing data returns partial results rather than errors.
- **Spot selector**: Users pick spots via "My Spots" on the Tides tab, grouped by region (county). Selection persists in `localStorage('selectedSpots')`. Spots have `zone` (`"ocean"` or `"back_bay"`) and `region` fields. All 25 spots in `SPOT_CONFIG` (striper_tides.py) have NOAA tide station IDs; the same names appear in `db.py`'s `SPOTS` list used for journal entry logging.
- **Regions**: `REGION_CONFIG` (striper_tides.py) maps each region key (`cape_may`, `atlantic`, `ocean`, `raritan`, `monmouth`) to its NWS obs station, lat/lon for grid forecast lookup, NOAA water-temp station, and a `season_offset` in months (positive shifts the scoring month forward, so April at Sandy Hook scores like May at Cape May). Boost data (wind/pressure/temp trend) is fetched per region in `get_events()`.
- **Subordinate stations**: Most back bay spots don't have direct NOAA hourly data. `fetch_tides_hourly()` fetches from Cape May (8536110) and applies time/height offsets via cosine interpolation.
- **Boost-only scoring**: Wind, pressure trend, and temp trend factors only add points (never penalize). Wind boost uses NWS forecast (7-day range), pressure uses KWWD observations (today only), temp trend uses NDBC 3-day lookback (transition months only: Mar-May, Sep-Dec).
- **Species conditions**: Flounder (April-July) and weakfish (May-October) rows appear in the daily outlook card. Flounder logic is temp-drop-sensitive — a drop of 2°F+ over 3 days suppresses the bite; early season (April-May) copy highlights warm back bay flats as the key location and flags doormat season. Weakfish logic keys off moon phase for tidal strength.
- **Photo uploads**: Two-step flow — POST journal entry → get back ID → POST image to `/api/journal/<id>/image`. Stored under `static/uploads/journal/` (full + thumbs). Non-persistent on Render.
- **Bite Talk**: Lightweight community thread on the Reports tab. `GET/POST /api/comments`. Name comes from `anglerName` in localStorage (shared with journal). 280-char limit.
- **Swell tab**: Currently archived/hidden. Code remains in template but tab button is commented out.
- **Weekly report**: Manually updated HTML block in `templates/index.html` around line 730, inside the Tide Calendar pane (`pane-calendar`). Update the "Week of X" date, the title, and the body paragraph each week. No em dashes or hyphens in paragraph copy.
- **About tab**: `pane-about` div at the bottom of `templates/index.html` (~line 1098). Spot cards render via Jinja from `spots_content.py` — edit writeups there, not in the template. Species/seasons and how-it-works sections are still static HTML in the template.

## Mobile Responsive

Full mobile layout at `@media max-width: 600px`. Tab labels shorten via `.tab-full`/`.tab-short`. Day pills group by 1 day on mobile vs 3 on desktop (`_getWindowDays()`). Spot tides default to one spot with "Show all spots" toggle. Stats bar replaced with ranked "Top 5 Days" list.

## Geography

The forecast engine covers 25 fishing spots along the NJ Shore from Sandy Hook to Cape May via `SPOT_CONFIG` in `striper_tides.py`, spanning five regions: Cape May County, Atlantic County, Ocean County, Raritan Bay, and Monmouth County. Solar/lunar calculations and the water clarity model are anchored at Cape May (38.93°N, 74.86°W). Timezone is `America/New_York`.
