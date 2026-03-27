# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Start the web server (requires venv)
.venv/bin/python3 app.py
# → http://localhost:5001

# CLI mode: generate .ics calendar file
.venv/bin/python3 striper_tides.py

# Install dependencies
.venv/bin/pip install -r requirements.txt

# Initialize database (also runs on app startup)
.venv/bin/python3 db.py
```

The dev server is configured in `.claude/launch.json` for preview_start on port 5001. The venv is at `.venv/` using system Python 3.

## Architecture

**Single-page Flask app** with three Python modules and one monolithic HTML template:

- **`striper_tides.py`** — Core engine. All data fetching (NOAA tides, NWS weather, NDBC buoys, Open-Meteo marine models), astronomical calculations (solar via Astral, lunar via ephem), scoring algorithms, and forecast logic. This is the brains — ~1500 lines.
- **`app.py`** — Flask routes and API layer. Thin wrapper that calls into `striper_tides.py`, manages an in-memory daily cache (`_cache` dict keyed by date), and serves JSON endpoints. Also handles journal/clarity CRUD against SQLite.
- **`db.py`** — SQLite setup. Two tables: `journal_entries` (fishing logs with auto-filled NOAA conditions) and `clarity_reports` (crowd-sourced water clarity). WAL mode, Row factory.
- **`templates/index.html`** — Full SPA with embedded CSS + vanilla JS. Four tabs: Tide Calendar, Swell Report, Water Clarity, Fish Journal. Uses Chart.js for visualizations. ~2800+ lines.

## Key External APIs

| API | Purpose | Key Constants |
|-----|---------|---------------|
| NOAA CO-OPS | Tide predictions (hilo + hourly) | 5 station IDs in `SPOT_CONFIG` |
| NWS api.weather.gov | Wind observations (KWWD) + hourly forecast (PHI/63,33) | Grid point covers Cape May County |
| NDBC Buoys | Real-time wave data | 44009 (Cape May), 44025 (LBI) |
| Open-Meteo Marine | GFS/ECMWF wave model forecasts | `ncep_gfswave025`, `ecmwf_wam025` |

## Data Flow

1. `get_events(days)` is the master function — scores every tidal event across a date range using `_score_event()` (tidal range 0-35, time of day 0-30, moon 0-15, season 0-20)
2. `/api/forecast/<date>` assembles a full day view: hourly tides for all 5 spots, solunar windows, marine conditions, solar/moon data, fishing outlook
3. `/api/surf?spot=X&model=Y` returns wave history + 7-day forecast from Open-Meteo (or wind-estimated fallback via "striper" model)
4. Clarity model in `get_clarity_forecast()` estimates turbidity from wave energy, wind, tidal range, and rain

## Important Patterns

- **Caching**: `_cache` dict in app.py keys by `prefix:today:params`. Refreshes daily. No invalidation needed since forecasts change by day.
- **Graceful degradation**: All API calls wrapped in try/except. Missing data (buoys offline, API down) returns partial results rather than errors.
- **Subordinate stations**: Hereford, Corsons, Townsends don't have direct NOAA hourly data. `fetch_tides_hourly()` fetches from Cape May (8536110) and applies time/height offsets via cosine interpolation.
- **Surf models**: Three sources — GFS and ECMWF via Open-Meteo, plus proprietary "Striper Tides" wind-driven estimation as fallback when buoys are down.
- **Scoring thresholds**: `BIG_SWING_PERCENTILE = 50` (top half of tidal ranges). Water temp prime: 50-68°F. Spring peak: May. Fall peak: Oct-Nov.

## Geography

All 5 fishing spots are in Cape May County, NJ. Coordinates center around 38.93°N, 74.86°W. Timezone is `America/New_York`. Surf spots (LBI, Ocean City, Avalon, Cape May) have different beach orientations affecting offshore wind classification.
