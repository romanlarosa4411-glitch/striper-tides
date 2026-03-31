# Striper Tides — Product Requirements Document

## Overview

Striper Tides is a single-page fishing forecast app built for a small crew of Cape May County, NJ anglers. It predicts prime striper fishing windows by scoring tidal events across 7 weighted factors, displays a calendar with color-coded day quality, and provides detailed daily forecasts with tide charts, wind data, solunar periods, and spot-specific tide times.

The app runs as a Flask server with vanilla JS frontend. No frameworks, no auth, no database beyond a local SQLite for journal/clarity entries.

---

## Scoring Algorithm (v2)

### Philosophy
The score answers one question: **"How good is this tidal event for striper fishing?"** It accumulates reasons to go (0–100). The three newest factors (wind, pressure, temp trend) are **boost-only** — they reward favorable conditions but never penalize. A calm SW day doesn't lose points; a NE 12mph day earns a bonus.

### Seven Factors

| Factor | Max Raw Pts | Effective Weight (of 100) | Source |
|--------|------------|--------------------------|--------|
| Tidal range | 35 | ~26% | NOAA CO-OPS hilo predictions |
| Time of day | 30 | ~22% | Astral solar calculations |
| Season | 20 | ~15% | Month of year |
| Wind | 15 | ~11% | NWS KWWD obs (today) / PHI forecast (future) |
| Moon phase | 15 | ~11% | ephem library |
| Pressure trend | 10 | ~7% | NWS KWWD observations, 6hr window |
| Temp trend | 10 | ~7% | NDBC buoy 44009, 3-day lookback |

**Raw max = 135, normalized to 0–100.**

### Factor Details

#### Tidal Range (0–35)
- Measures daily high-low swing as a percentile across the date range
- Bigger swings push more bait through inlets = better fishing
- `BIG_SWING_PERCENTILE = 50` filters calendar to top half of days

#### Time of Day (0–30)
- Dawn = 30, Dusk = 28, Night = 18, Day = 5
- Dawn/dusk windows defined by ±75 min around sunrise/sunset
- Stripers are ambush predators; low light = peak feeding

#### Season (0–20)
- May = 20, Oct = 20, Nov = 20 (spring + fall peaks)
- Apr = 18, Sep = 15, Jun = 12, Mar = 12, Dec = 8
- Jan/Feb/Jul/Aug = 0–3 (fish not around in Cape May)

#### Moon Phase (0–15)
- New Moon = 15, Full Moon = 15 (spring tides + feeding)
- Quarter moons = 8, crescents = 5
- Strong tides from new/full moons amplify tidal range effect

#### Wind — BOOST ONLY (0–15)
- NE/E at ≤20 mph = 15 (pushes bait against beaches/jetties)
- NW/N at ≤18 mph = 12 (offshore, cleans up water)
- Calm <8 mph any direction = 8 (generally better bite)
- Everything else = 0 (no penalty)
- Data: NWS observations for today, NWS hourly forecast for future days (7-day range)

#### Barometric Pressure Trend — BOOST ONLY (0–10)
- 6-hour observation window from NWS KWWD station
- Falling fast (>3 mb drop) = 10 ("fish before the storm")
- Falling slow (1–3 mb drop) = 6
- Steady or rising = 0 (no penalty)
- Only available for today (requires real observation data, not forecasts)

#### Water Temp Trend — BOOST ONLY (0–10)
- 3-day lookback from NDBC buoy 44009 (Cape May)
- Rising ≥3°F in transition months (Mar–May, Sep–Dec) = 10
- Rising 1–2°F in transition months = 6
- Flat, dropping, or non-transition month = 0
- Matters most at season edges: initial spring warmup, fall cooldown

### Quality Tiers
Scores map to display tiers:
- **Really Good** (≥70): Green highlight, worth planning your day around
- **Good** (≥50): Blue highlight, solid window
- **OK** (≥30): Faint highlight, fishable but nothing special
- **Skip** (<30): No highlight

---

## Calendar Weather Overlay

### What
Each calendar day cell shows a non-scored weather summary for the next 7 days:
- Weather condition icon (☀️ ⛅ 🌧️ etc.)
- High temperature
- Wind direction shorthand (NE, SW, etc.)

### Why
One-stop-shop: anglers see fishing score + weather at a glance without checking another app. The weather info is context, not scored — it's for comfort/planning, not bite prediction.

### Data Source
- NWS 7-day daily forecast (`/gridpoints/PHI/63,33/forecast`)
- Days 8+ show tide/moon score only (no weather data available)
- Graceful degradation: if NWS is down, calendar renders normally without weather badges

### Display
- `.day-weather` div below the score in each calendar cell
- Compact: icon + temp + wind direction, single line
- Scales down on mobile (smaller font, same info)

---

## Data Sources

| Source | Endpoint | What We Use | Refresh |
|--------|----------|-------------|---------|
| NOAA CO-OPS | `/api/datagetter` | Tide predictions (hilo + hourly) for 5 stations | Per-request, cached daily |
| NWS Observations | `/stations/KWWD/observations` | Current wind speed/dir, barometric pressure | Per-request, cached daily |
| NWS Hourly Forecast | `/gridpoints/PHI/63,33/forecast/hourly` | Future wind speed/dir (7 days) | Per-request, cached daily |
| NWS Daily Forecast | `/gridpoints/PHI/63,33/forecast` | Weather icons, high temp, wind summary | Per-request, cached daily |
| NDBC Buoy 44009 | Station page / realtime data | Water temp (current + 3-day history) | Per-request, cached daily |
| Open-Meteo Marine | `/v1/marine` | Wave height/period/direction forecasts | Per-request, cached daily |
| Astral library | Local calc | Sunrise, sunset, dawn, dusk | Computed per date |
| ephem library | Local calc | Moon phase, moonrise, moonset | Computed per date |

All external API calls are wrapped in try/except. Missing data returns partial results, never errors.

---

## App Tabs

### 1. Tide Calendar (Primary)
- Monthly calendar with color-coded fishing quality per day
- Weather overlay on next 7 days (icon + temp + wind)
- "Next Best Day" card (mobile replaces stat chips)
- Day detail view: tide chart (Chart.js), hourly winds, fishing outlook, solunar windows, spot-specific tides

### 2. Swell Report (Archived)
- Currently hidden from tab bar
- Quality-colored wave height fill chart with period overlay and direction arrows
- Day pill navigation (1-day mobile, 3-day desktop)
- Hover/tap banner with swell details
- Will be re-enabled when ready for further development

### 3. Water Clarity
- Primarily for diving, not striper fishing
- Turbidity model based on wave energy, wind, tidal range, rain
- Crowd-sourced clarity reports stored in SQLite

### 4. Fish Journal
- CRUD fishing log entries
- Auto-populates NOAA conditions at time of entry
- SQLite storage

---

## Mobile Design

All tabs are mobile-responsive (`@media max-width: 600px`):

- **Tab labels**: `.tab-full` (desktop) / `.tab-short` (mobile) CSS pattern
- **Tide Calendar**: Compact cells, smaller weather text, "Next Best Day" card replaces stat chips
- **Spot Tides**: Default one spot (Cape May Inlet), "Show all spots" toggle reveals rest
- **Swell** (archived): 1-day windows instead of 3, every-3h table sampling (8 cols)
- **No horizontal scroll**: All containers use `overflow-x: hidden` or flexible layouts

---

## Deployment

- **Host**: Render.com (free tier)
- **Auto-deploy**: Push to `main` on GitHub → Render rebuilds
- **Build**: `pip install -r requirements.txt`
- **Start**: `python app.py` (reads `PORT` from env, defaults to 5001)
- **Database**: SQLite file on Render disk (ephemeral on free tier — journal/clarity data resets on redeploy)
- **Domain**: Currently `*.onrender.com`, custom domain possible later

---

## What's NOT In Scope

- **Bait presence**: No reliable API; already proxied by season + water temp
- **Current speed**: Already captured by tidal range factor
- **Clarity in scoring**: Stripers aren't sight feeders; clarity matters for diving tab only
- **User accounts / auth**: Small crew, no need
- **Push notifications**: Not yet — would need PWA service worker
- **Historical accuracy tracking**: Not tracking predicted vs actual catches yet
