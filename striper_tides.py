#!/usr/bin/env python3
"""
striper_tides.py — Striper Tide Calendar Generator

Generates calendar events for prime striper fishing tides:
  - HIGH tides at Hereford Inlet, NJ  (West Wildwood / Grassy Sound station)
  - LOW tides at Cape May ferry terminal, NJ (Delaware Bay station)

Event quality:
  "REALLY GOOD" = big tidal swing + tide falls during dawn / dusk / nighttime
  "Good"        = big tidal swing + tide falls during daytime

CLI Usage:
    python3 striper_tides.py              # next 90 days, saves .ics to Desktop
    python3 striper_tides.py --days 180

Web Usage:
    python3 app.py                        # launches browser UI at localhost:5001
"""

import argparse
import bisect
import math
import subprocess
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone as _tz
from pathlib import Path
from zoneinfo import ZoneInfo

import ephem
import requests
from astral import LocationInfo
from astral.sun import sun
from icalendar import Calendar, Event

# ── Station IDs ───────────────────────────────────────────────────────────────
HEREFORD_STATION = "8535726"   # West Wildwood, Grassy Sound  (Hereford Inlet)
CAPE_MAY_STATION = "8536110"   # Cape May, NJ                 (ferry terminal)

# All five fishing spots → nearest NOAA tide prediction station + display metadata.
# Inlets  → High tide: center of the prime incoming/turning window.
#            Big tidal swings push more bait through the cut; fish stack
#            on the last 2–3 hrs incoming and first 2–3 hrs outgoing.
# Ferry   → Low tide:  Delaware Bay draining creates the famous Cape May
#            Rips; eels and bait funnel through, triggering the bite.
SPOT_CONFIG: dict[str, dict] = {
    # ── Ocean / Inlet spots ──────────────────────────────────────────────────
    "Corsons Inlet": {
        "station_id":    "8535221",
        "station_name":  "Ludlam Bay",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Corsons Inlet — Ocean City / Sea Isle City, NJ",
    },
    "Townsends Inlet": {
        "station_id":    "8535309",
        "station_name":  "Townsend Sound",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Townsends Inlet — Avalon / Sea Isle City, NJ",
    },
    "Hereford Inlet": {
        "station_id":    HEREFORD_STATION,
        "station_name":  "West Wildwood, Grassy Sound",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Hereford Inlet — Wildwood / Stone Harbor, NJ",
    },
    "Cape May Inlet": {
        "station_id":    "8535901",
        "station_name":  "Cape May Harbor",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Cape May Inlet — Cold Spring / Cape May Point, NJ",
    },
    "Cape May Point": {
        "station_id":    CAPE_MAY_STATION,
        "station_name":  "Cape May ferry terminal",
        "tide_type":     "L",
        "zone":          "ocean",
        "location_long": "Cape May Point — Delaware Bay Rips",
    },
    # ── Back Bay spots ───────────────────────────────────────────────────────
    "Grassy Sound": {
        "station_id":    "8535661",
        "station_name":  "Nummy Island, Grassy Sound Channel",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Grassy Sound — Nummy Island / Wildwood, NJ",
    },
    "Stone Harbor": {
        "station_id":    "8535581",
        "station_name":  "Stone Harbor, Great Channel",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Stone Harbor — Great Channel / Hereford Inlet, NJ",
    },
    "Avalon Back Bay": {
        "station_id":    "8535805",
        "station_name":  "Swain Channel, Taylor Sound",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Avalon Back Bay — Swain Channel / Taylor Sound, NJ",
    },
    "Sea Isle Back Bay": {
        "station_id":    "8535357",
        "station_name":  "Stites Sound",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Sea Isle Back Bay — Stites Sound, NJ",
    },
    "Townsends Back Bay": {
        "station_id":    "8535451",
        "station_name":  "Long Reach, Ingram Thorofare",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Townsends Back Bay — Ingram Thorofare, NJ",
    },
    "Cape May Back Bay": {
        "station_id":    "8535901",
        "station_name":  "Cape May Harbor",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Cape May Back Bay — Cape May Harbor, NJ",
    },
    "The Thorofare": {
        "station_id":    "8535695",
        "station_name":  "Old Turtle Thorofare, RR. bridge",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "The Thorofare — Old Turtle Thorofare / Wildwood, NJ",
    },
    # ── Atlantic County ──────────────────────────────────────────────────────
    "Atlantic City Back Bay": {
        "station_id":    "8534720",
        "station_name":  "Atlantic City",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Atlantic City Back Bay — Absecon Bay / AC Harbor, NJ",
    },
    "Somers Point Back Bay": {
        "station_id":    "8534691",
        "station_name":  "Great Egg Harbor River",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Somers Point — Great Egg Harbor Bay, NJ",
    },
    "Absecon Inlet": {
        "station_id":    "8534720",
        "station_name":  "Atlantic City",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Absecon Inlet — Atlantic City / Longport, NJ",
    },
    "Great Egg Harbor Inlet": {
        "station_id":    "8534691",
        "station_name":  "Great Egg Harbor River",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Great Egg Harbor Inlet — Ocean City / Longport, NJ",
    },
    # ── Ocean County ─────────────────────────────────────────────────────────
    "LBI Back Bay": {
        "station_id":    "8533631",
        "station_name":  "High Bar, Barnegat Bay",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "LBI Back Bay — High Bar Harbor / Barnegat Bay, NJ",
    },
    "Barnegat Inlet": {
        "station_id":    "8533615",
        "station_name":  "Barnegat Inlet (Inside)",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Barnegat Inlet — Barnegat Light, NJ",
    },
    "Island Beach SP": {
        "station_id":    "8533615",
        "station_name":  "Barnegat Inlet (Inside)",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Island Beach State Park — Seaside Park, NJ",
    },
    # ── Raritan Bay ──────────────────────────────────────────────────────────
    "Perth Amboy": {
        "station_id":    "8531232",
        "station_name":  "South Amboy, Raritan River",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Perth Amboy — Raritan River mouth / Raritan Bay, NJ",
    },
    "Keyport": {
        "station_id":    "8531545",
        "station_name":  "Keyport, Raritan Bay",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Keyport — Raritan Bay, NJ",
    },
    "Keansburg": {
        "station_id":    "8531545",
        "station_name":  "Keyport, Raritan Bay",
        "tide_type":     "H",
        "zone":          "back_bay",
        "location_long": "Keansburg — Raritan Bay, NJ",
    },
    # ── Monmouth County ──────────────────────────────────────────────────────
    "Manasquan Inlet": {
        "station_id":    "8532591",
        "station_name":  "Manasquan Inlet",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Manasquan Inlet — Point Pleasant / Manasquan, NJ",
    },
    "Shark River Inlet": {
        "station_id":    "8532322",
        "station_name":  "Shark River Hills",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Shark River Inlet — Belmar / Neptune, NJ",
    },
    "Sandy Hook": {
        "station_id":    "8531680",
        "station_name":  "Sandy Hook",
        "tide_type":     "H",
        "zone":          "ocean",
        "location_long": "Sandy Hook — Gateway NRA / Raritan Bay, NJ",
    },
}

# Legacy alias — app.py references this
SPOT_STATIONS = SPOT_CONFIG

# ── Location for solar calculations (Wildwood / Cape May area) ────────────────
TIMEZONE = "America/New_York"
LOCAL_TZ = ZoneInfo(TIMEZONE)

LOCATION = LocationInfo(
    name="Cape May, NJ",
    region="USA",
    timezone=TIMEZONE,
    latitude=38.93,
    longitude=-74.86,
)

# ── Thresholds ────────────────────────────────────────────────────────────────
BIG_SWING_PERCENTILE = 50   # show top 50% of days by tidal range; scoring handles quality
DAWN_WINDOW = timedelta(minutes=75)
DUSK_WINDOW = timedelta(minutes=75)

# ── NOAA CO-OPS API ───────────────────────────────────────────────────────────
NOAA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def fetch_tides(station_id: str, begin: date, end: date) -> list[dict]:
    """Return high/low tide prediction dicts from NOAA for a date range."""
    params = {
        "station":     station_id,
        "product":     "predictions",
        "datum":       "MLLW",
        "time_zone":   "lst_ldt",
        "interval":    "hilo",
        "units":       "english",
        "application": "striper_tide_cal",
        "format":      "json",
        "begin_date":  begin.strftime("%Y%m%d"),
        "end_date":    end.strftime("%Y%m%d"),
    }
    resp = requests.get(NOAA_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(
            f"NOAA API error for station {station_id}: {data['error']['message']}"
        )
    return data["predictions"]


def fetch_tides_hourly(station_id: str, d: date) -> list[dict]:
    """
    Return hourly tide predictions for a single day.
    For primary stations NOAA supplies hourly predictions directly.
    For subordinate stations (e.g. Hereford Inlet) that only have hilo data,
    we fetch hilo for a 3-day window and cosine-interpolate a smooth hourly curve.
    """
    params = {
        "station":     station_id,
        "product":     "predictions",
        "datum":       "MLLW",
        "time_zone":   "lst_ldt",
        "interval":    "h",
        "units":       "english",
        "application": "striper_tide_cal",
        "format":      "json",
        "begin_date":  d.strftime("%Y%m%d"),
        "end_date":    d.strftime("%Y%m%d"),
    }
    resp = requests.get(NOAA_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "error" not in data:
        return data["predictions"]

    # Station doesn't support hourly — fall back to cosine interpolation from hilo
    return _interpolate_from_hilo(station_id, d)


def _interpolate_from_hilo(station_id: str, d: date) -> list[dict]:
    """
    Fetch hilo data for d-1 → d+1 and cosine-interpolate an hourly curve
    for day d. Tides are well-approximated by cosine curves between extrema.
    """
    begin = d - timedelta(days=1)
    end   = d + timedelta(days=1)
    raw   = fetch_tides(station_id, begin, end)

    # Build list of (absolute_hour_offset_from_midnight_of_d, height)
    d_str = d.isoformat()
    extrema: list[tuple[float, float]] = []
    for t in raw:
        dt_point = datetime.strptime(t["t"], "%Y-%m-%d %H:%M")
        # Hours relative to midnight of target date
        delta = dt_point - datetime(d.year, d.month, d.day)
        rel_h = delta.total_seconds() / 3600.0
        extrema.append((rel_h, float(t["v"])))

    extrema.sort(key=lambda x: x[0])

    # Cosine interpolation for each hour 0–23
    result = []
    for hour in range(24):
        t_h = hour  # target decimal hour

        # Find the surrounding pair of extrema
        before = None
        after  = None
        for h, v in extrema:
            if h <= t_h:
                before = (h, v)
            elif after is None:
                after = (h, v)

        if before is None:
            height = after[1] if after else 0.0
        elif after is None:
            height = before[1]
        else:
            t0, v0 = before
            t1, v1 = after
            mu     = (t_h - t0) / (t1 - t0)
            mu2    = (1 - math.cos(mu * math.pi)) / 2
            height = v0 * (1 - mu2) + v1 * mu2

        result.append({
            "t": f"{d_str} {str(hour).zfill(2)}:00",
            "v": f"{height:.3f}",
        })

    return result


# ── Solar helpers ─────────────────────────────────────────────────────────────

def get_solar(d: date) -> dict:
    """Return sun dict (dawn, sunrise, noon, sunset, dusk) for a date."""
    return sun(LOCATION.observer, date=d, tzinfo=LOCAL_TZ)


def time_of_day(dt: datetime, solar: dict) -> str:
    """Classify a datetime as 'dawn', 'dusk', 'night', or 'day'."""
    dawn_window_start = solar["dawn"]   - DAWN_WINDOW
    dawn_window_end   = solar["sunrise"] + DAWN_WINDOW
    dusk_window_start = solar["sunset"]  - DUSK_WINDOW
    dusk_window_end   = solar["dusk"]   + DUSK_WINDOW

    if dawn_window_start <= dt <= dawn_window_end:
        return "dawn"
    if dusk_window_start <= dt <= dusk_window_end:
        return "dusk"
    if dt < solar["dawn"] or dt > solar["dusk"]:
        return "night"
    return "day"


# ── Moon phase ────────────────────────────────────────────────────────────────

def moon_phase_label(d: date) -> tuple[str, int]:
    """Return (readable phase name, illumination pct 0–100)."""
    m_today    = ephem.Moon()
    m_tomorrow = ephem.Moon()
    m_today.compute(d.strftime("%Y/%m/%d"))
    m_tomorrow.compute((d + timedelta(days=1)).strftime("%Y/%m/%d"))

    pct    = m_today.phase
    waxing = m_tomorrow.phase > pct

    if pct <= 6:
        label = "New Moon"
    elif pct <= 44:
        label = "Waxing Crescent" if waxing else "Waning Crescent"
    elif pct <= 56:
        label = "First Quarter"   if waxing else "Last Quarter"
    elif pct <= 94:
        label = "Waxing Gibbous"  if waxing else "Waning Gibbous"
    else:
        label = "Full Moon"

    return label, round(pct)


# ── Solunar windows ───────────────────────────────────────────────────────────

def get_solunar(d: date) -> list[dict]:
    """
    Calculate solunar feeding windows for a date at the Cape May / Wildwood location.
    Major periods (±1 hr): moon overhead (transit) + moon underfoot (antitransit)
    Minor periods (±30 min): moonrise + moonset
    Returns list of window dicts sorted by hour.
    """
    observer = ephem.Observer()
    observer.lat       = str(LOCATION.latitude)
    observer.lon       = str(LOCATION.longitude)
    observer.elevation = 0
    observer.pressure  = 0   # disable atmospheric refraction
    observer.horizon   = "0"

    start_local = datetime(d.year, d.month, d.day, 0, 0, tzinfo=LOCAL_TZ)
    start_utc   = start_local.astimezone(_tz.utc)
    moon        = ephem.Moon()

    def to_local(ephem_date) -> datetime:
        return ephem.Date(ephem_date).datetime().replace(tzinfo=_tz.utc).astimezone(LOCAL_TZ)

    def on_day(dt: datetime) -> bool:
        return dt.date() == d

    def fmt(dt: datetime) -> dict:
        return {
            "hour":    round(dt.hour + dt.minute / 60, 3),
            "time_12": dt.strftime("%-I:%M %p"),
        }

    windows: list[dict] = []

    # Major — transit (moon overhead)
    obs_date = ephem.Date(start_utc.strftime("%Y/%m/%d %H:%M:%S"))
    for _ in range(3):
        try:
            observer.date = obs_date
            t  = observer.next_transit(moon)
            dt = to_local(t)
            if on_day(dt):
                windows.append({"type": "major", "label": "Moon Overhead", "icon": "🌕", **fmt(dt), "duration": 2.0})
            obs_date = t + 0.35
        except Exception:
            break

    # Major — antitransit (moon underfoot)
    obs_date = ephem.Date(start_utc.strftime("%Y/%m/%d %H:%M:%S"))
    for _ in range(3):
        try:
            observer.date = obs_date
            t  = observer.next_antitransit(moon)
            dt = to_local(t)
            if on_day(dt):
                windows.append({"type": "major", "label": "Moon Underfoot", "icon": "🌑", **fmt(dt), "duration": 2.0})
            obs_date = t + 0.35
        except Exception:
            break

    # Minor — moonrise
    obs_date = ephem.Date(start_utc.strftime("%Y/%m/%d %H:%M:%S"))
    for _ in range(2):
        try:
            observer.date = obs_date
            t  = observer.next_rising(moon)
            dt = to_local(t)
            if on_day(dt):
                windows.append({"type": "minor", "label": "Moonrise", "icon": "🌒", **fmt(dt), "duration": 1.0})
            obs_date = t + 0.5
        except Exception:
            break

    # Minor — moonset
    obs_date = ephem.Date(start_utc.strftime("%Y/%m/%d %H:%M:%S"))
    for _ in range(2):
        try:
            observer.date = obs_date
            t  = observer.next_setting(moon)
            dt = to_local(t)
            if on_day(dt):
                windows.append({"type": "minor", "label": "Moonset", "icon": "🌘", **fmt(dt), "duration": 1.0})
            obs_date = t + 0.5
        except Exception:
            break

    windows.sort(key=lambda w: w["hour"])
    return windows


# ── Marine conditions (NOAA NWS + CO-OPS) ────────────────────────────────────
# Wind: KWWD ASOS observations for past hours + NWS PHI forecast for future
# Water temp: NOAA CO-OPS observed data from Cape May station (8536110)

_NWS_HEADERS       = {"User-Agent": "StriperTidesApp/1.0 (contact: stripertides@local)"}
_NWS_FORECAST      = "https://api.weather.gov/gridpoints/PHI/63,33/forecast/hourly"
_NWS_FORECAST_DAILY = "https://api.weather.gov/gridpoints/PHI/63,33/forecast"
_NWS_OBS_URL       = "https://api.weather.gov/stations/KWWD/observations"  # Cape May County Airport ASOS

_WIND_DIR_DEG = {
    "N": 0, "NNE": 22, "NE": 45, "ENE": 67,
    "E": 90, "ESE": 112, "SE": 135, "SSE": 157,
    "S": 180, "SSW": 202, "SW": 225, "WSW": 247,
    "W": 270, "WNW": 292, "NW": 315, "NNW": 337,
}

_KMH_TO_MPH = 0.621371


def fetch_marine_conditions(d: date) -> dict:
    """
    Wind: KWWD ASOS observations for past/current hours, NWS PHI forecast for future.
    Water temp: NOAA CO-OPS observed readings at Cape May station.
    Falls back gracefully if either source is unavailable.
    """
    hourly: list[dict] = [{
        "hour": h, "wind_mph": None, "wind_deg": None,
        "gust_mph": None, "water_temp": None,
    } for h in range(24)]

    local_tz = ZoneInfo(TIMEZONE)

    # ── Wind pass 1: KWWD ASOS observations (real data for past hours) ────
    try:
        # Determine proper UTC offset for the target date (handles EST/EDT)
        _ref_dt  = datetime(d.year, d.month, d.day, 12, tzinfo=local_tz)
        _off     = _ref_dt.strftime("%z")                       # e.g. "-0400" or "-0500"
        _off_str = f"{_off[:3]}:{_off[3:]}"                     # → "-04:00" or "-05:00"
        from_str = f"{d.isoformat()}T00:00:00{_off_str}"
        to_str   = f"{d.isoformat()}T23:59:59{_off_str}"
        resp_obs = requests.get(
            _NWS_OBS_URL,
            params={"start": from_str, "end": to_str},
            headers=_NWS_HEADERS,
            timeout=15,
        )
        resp_obs.raise_for_status()
        features = resp_obs.json().get("features", [])

        # Bucket readings by local hour, then average
        hour_speeds: dict = defaultdict(list)
        hour_dirs:   dict = defaultdict(list)
        hour_gusts:  dict = defaultdict(list)
        pressure_readings: list[tuple[datetime, float]] = []  # (dt, mb) for trend calc

        for feat in features:
            props = feat.get("properties", {})
            ts    = props.get("timestamp", "")
            if not ts:
                continue
            dt_local = datetime.fromisoformat(ts).astimezone(local_tz)
            if dt_local.date() != d:
                continue
            h = dt_local.hour

            ws = props.get("windSpeed",     {}) or {}
            wd = props.get("windDirection", {}) or {}
            wg = props.get("windGust",      {}) or {}
            bp = props.get("barometricPressure", {}) or {}

            if ws.get("value") is not None:
                hour_speeds[h].append(ws["value"] * _KMH_TO_MPH)
            if wd.get("value") is not None:
                hour_dirs[h].append(wd["value"])
            if wg.get("value") is not None:
                hour_gusts[h].append(wg["value"] * _KMH_TO_MPH)
            if bp.get("value") is not None:
                pressure_readings.append((dt_local, bp["value"] / 100.0))  # Pa → mb

        for h in range(24):
            if hour_speeds[h]:
                hourly[h]["wind_mph"] = round(sum(hour_speeds[h]) / len(hour_speeds[h]), 1)
            if hour_dirs[h]:
                hourly[h]["wind_deg"] = round(sum(hour_dirs[h]) / len(hour_dirs[h]))
            if hour_gusts[h]:
                hourly[h]["gust_mph"] = round(sum(hour_gusts[h]) / len(hour_gusts[h]), 1)
    except Exception:
        pass

    # ── Wind pass 2: NWS forecast (fills future hours, overrides where better) ──
    try:
        resp = requests.get(_NWS_FORECAST, headers=_NWS_HEADERS, timeout=15)
        resp.raise_for_status()
        periods  = resp.json()["properties"]["periods"]
        date_str = d.isoformat()

        for p in periods:
            # startTime like "2026-03-23T06:00:00-04:00"
            if not p["startTime"].startswith(date_str):
                continue
            hour = int(p["startTime"][11:13])
            speed_raw = p.get("windSpeed", "")
            speeds    = [int(x) for x in speed_raw.replace(" mph", "").split(" to ") if x.isdigit()]
            mph       = max(speeds) if speeds else None
            deg       = _WIND_DIR_DEG.get(p.get("windDirection", ""))
            if 0 <= hour < 24 and mph is not None:
                # Only override if no observed data exists for this hour
                if hourly[hour]["wind_mph"] is None:
                    hourly[hour]["wind_mph"] = mph
                    hourly[hour]["wind_deg"] = deg
    except Exception:
        pass

    # ── Water temp: CO-OPS observed ───────────────────────────────────────
    water_temp_f = None
    try:
        resp2 = requests.get(
            NOAA_URL,
            params={
                "station":    CAPE_MAY_STATION,
                "product":    "water_temperature",
                "time_zone":  "lst_ldt",
                "units":      "english",
                "format":     "json",
                "begin_date": d.strftime("%Y%m%d"),
                "end_date":   d.strftime("%Y%m%d"),
            },
            timeout=15,
        )
        data = resp2.json()
        if "data" in data and data["data"]:
            readings = [float(x["v"]) for x in data["data"] if x.get("v") not in (None, "")]
            if readings:
                water_temp_f = round(sum(readings) / len(readings), 1)
                # Also fill per-hour slots (readings are every 6 min)
                for rec in data["data"]:
                    try:
                        hour = int(rec["t"][11:13])
                        val  = float(rec["v"])
                        if hourly[hour]["water_temp"] is None:
                            hourly[hour]["water_temp"] = round(val, 1)
                    except Exception:
                        pass
    except Exception:
        pass

    # ── Pressure trend: 6-hour window ────────────────────────────────────
    # Positive drop_mb means pressure is falling (good for fishing)
    pressure_trend_mb = None
    if pressure_readings:
        pressure_readings.sort(key=lambda x: x[0])
        latest_dt, latest_mb = pressure_readings[-1]
        # Find reading closest to 6 hours before the latest
        target_dt = latest_dt - timedelta(hours=6)
        earlier = [(dt, mb) for dt, mb in pressure_readings if dt <= target_dt]
        if earlier:
            _, earlier_mb = earlier[-1]
            pressure_trend_mb = round(earlier_mb - latest_mb, 1)  # positive = falling

    return {
        "hourly": hourly,
        "water_temp_f": water_temp_f,
        "pressure_trend_mb": pressure_trend_mb,
    }


def fetch_7day_weather() -> dict:
    """
    Fetch NWS 7-day daily forecast for calendar display.
    Returns dict keyed by date string → {high_f, low_f, wind_dir, wind_speed, short_forecast, icon}.
    """
    try:
        resp = requests.get(_NWS_FORECAST_DAILY, headers=_NWS_HEADERS, timeout=15)
        resp.raise_for_status()
        periods = resp.json()["properties"]["periods"]
        by_day: dict[str, dict] = {}
        for p in periods:
            dt_start = datetime.fromisoformat(p["startTime"])
            day_str  = dt_start.date().isoformat()
            is_day   = p.get("isDaytime", True)
            short    = p.get("shortForecast", "")

            # Map NWS shortForecast to a simple icon
            sl = short.lower()
            if "snow" in sl:
                icon = "🌨️"
            elif "thunder" in sl or "storm" in sl:
                icon = "⛈️"
            elif "rain" in sl or "shower" in sl:
                icon = "🌧️"
            elif "cloud" in sl or "overcast" in sl:
                icon = "☁️"
            elif "partly" in sl:
                icon = "⛅"
            elif "fog" in sl:
                icon = "🌫️"
            elif "wind" in sl:
                icon = "💨"
            else:
                icon = "☀️"

            if day_str not in by_day:
                by_day[day_str] = {}

            if is_day:
                by_day[day_str]["high_f"] = p.get("temperature")
                by_day[day_str]["wind_dir"] = p.get("windDirection", "")
                ws = p.get("windSpeed", "")
                speeds = [int(x) for x in ws.replace(" mph", "").split(" to ") if x.isdigit()]
                by_day[day_str]["wind_speed"] = max(speeds) if speeds else None
                by_day[day_str]["short_forecast"] = short
                by_day[day_str]["icon"] = icon
            else:
                by_day[day_str]["low_f"] = p.get("temperature")
                # If no daytime period yet (tonight), still set icon
                if "icon" not in by_day[day_str]:
                    by_day[day_str]["icon"] = icon
                    by_day[day_str]["short_forecast"] = short

        return by_day
    except Exception:
        return {}


def fetch_water_temp_trend(lookback_days: int = 3) -> dict:
    """
    Fetch water temp from NOAA CO-OPS for the past N days and calculate trend.
    Returns {"current_f": float, "prev_f": float, "change_f": float} or empty dict.
    """
    try:
        end_d   = date.today()
        start_d = end_d - timedelta(days=lookback_days)
        resp = requests.get(
            NOAA_URL,
            params={
                "station":    CAPE_MAY_STATION,
                "product":    "water_temperature",
                "time_zone":  "lst_ldt",
                "units":      "english",
                "format":     "json",
                "begin_date": start_d.strftime("%Y%m%d"),
                "end_date":   end_d.strftime("%Y%m%d"),
            },
            timeout=15,
        )
        data = resp.json()
        if "data" not in data or not data["data"]:
            return {}
        # Group readings by date, average each day
        from collections import defaultdict as _dd
        by_day: dict[str, list[float]] = _dd(list)
        for rec in data["data"]:
            if rec.get("v") in (None, ""):
                continue
            day_key = rec["t"][:10]
            by_day[day_key].append(float(rec["v"]))
        if len(by_day) < 2:
            return {}
        sorted_days = sorted(by_day.keys())
        current_avg = sum(by_day[sorted_days[-1]]) / len(by_day[sorted_days[-1]])
        oldest_avg  = sum(by_day[sorted_days[0]])  / len(by_day[sorted_days[0]])
        change = round(current_avg - oldest_avg, 1)
        return {
            "current_f": round(current_avg, 1),
            "prev_f":    round(oldest_avg, 1),
            "change_f":  change,
        }
    except Exception:
        return {}


# ── Core data logic ───────────────────────────────────────────────────────────

def _score_event(range_pct: float, tod: str, moon_phase: str, month: int,
                  wind_mph: float = None, wind_deg: float = None,
                  pressure_trend_mb: float = None,
                  temp_change_f: float = None) -> int:
    """
    Score a tide event 0–135 (normalized to 0–100) across seven factors.

    Base factors (unchanged):
      Tidal range rank  (0–35): bigger daily swings push more bait through inlets.
      Time of day       (0–30): low-light windows (dawn/dusk) are peak ambush time.
      Moon phase        (0–15): new & full moons = spring tides + aggressive feeding.
      Season            (0–20): May + Oct-Nov peak, Jan/Jul dead.

    Boost-only factors (new — only add points, never subtract):
      Wind              (0–15): NE/E calm = 15, NW/N calm = 12, calm any = 8, else 0.
      Pressure trend    (0–10): Falling fast >3mb/6h = 10, slow 1-3mb = 6, else 0.
      Temp trend        (0–10): Rising 3°F+/3d in transition months = 10, 1-2°F = 6, else 0.
    """
    range_pts = round(range_pct * 35)

    tod_pts = {"dawn": 30, "dusk": 28, "night": 18, "day": 5}.get(tod, 0)

    moon_pts = {
        "New Moon": 15,  "Full Moon": 15,
        "Waxing Gibbous": 10, "Waning Gibbous": 10,
        "First Quarter": 8,   "Last Quarter": 8,
        "Waxing Crescent": 5, "Waning Crescent": 5,
    }.get(moon_phase, 5)

    season_pts = {
        5: 20, 4: 18,   # spring: May peak, April building
        10: 20, 11: 20, # fall peak (both critical months South Jersey)
        9: 15, 6: 12,   # early fall / late spring shoulder
        3: 12, 12: 8,   # cold-water spring start / late fall tail
        8: 3,  2: 0,    # possible late-summer blitzes / deep winter
        1: 0,  7: 0,    # January and July: fish are gone
    }.get(month, 0)

    # ── Wind boost (0-15) — boost only, no penalty ────────────────────────
    wind_pts = 0
    if wind_mph is not None and wind_deg is not None:
        card = ["N","NE","E","SE","S","SW","W","NW"][round(wind_deg / 45) % 8]
        if card in ("NE", "E") and wind_mph <= 20:
            wind_pts = 15
        elif card in ("NW", "N") and wind_mph <= 18:
            wind_pts = 12
        elif wind_mph < 8:
            wind_pts = 8

    # ── Pressure trend boost (0-10) — falling = fish feeding ──────────────
    pressure_pts = 0
    if pressure_trend_mb is not None and pressure_trend_mb > 0:
        if pressure_trend_mb > 3:
            pressure_pts = 10
        elif pressure_trend_mb >= 1:
            pressure_pts = 6

    # ── Temp trend boost (0-10) — rising temp in transition months ────────
    temp_pts = 0
    _TRANSITION_MONTHS = {3, 4, 5, 9, 10, 11, 12}
    if temp_change_f is not None and temp_change_f > 0 and month in _TRANSITION_MONTHS:
        if temp_change_f >= 3:
            temp_pts = 10
        elif temp_change_f >= 1:
            temp_pts = 6

    raw = range_pts + tod_pts + moon_pts + season_pts + wind_pts + pressure_pts + temp_pts
    # Normalize from 0-135 scale to 0-100
    return min(round(raw * 100 / 135), 100)






def fetch_all_spots_hilo(d: date) -> dict:
    """
    Fetch high/low tide predictions for all 5 spots for a single day.
    Returns a dict mapping spot name → {tide_type, events: [{type, time_12, hour, height, is_target}]}
    """
    result = {}
    for spot, cfg in SPOT_CONFIG.items():
        try:
            hilo = fetch_tides(cfg["station_id"], d, d)
            events = []
            for t in hilo:
                dt = datetime.strptime(t["t"], "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
                events.append({
                    "type":      "High" if t["type"] == "H" else "Low",
                    "time_12":   dt.strftime("%-I:%M %p"),
                    "hour":      round(dt.hour + dt.minute / 60, 2),
                    "height":    round(float(t["v"]), 1),
                    "is_target": t["type"] == cfg["tide_type"],
                })
            result[spot] = {
                "tide_type": "High" if cfg["tide_type"] == "H" else "Low",
                "events":    events,
            }
        except Exception:
            result[spot] = {"tide_type": "High" if cfg["tide_type"] == "H" else "Low", "events": []}
    return result


def get_day_fishing_outlook(d: date, water_temp_f=None, wind_mph=None, wind_deg=None, temp_change_f=None) -> dict:
    """
    Return a fishing outlook assessment for any day.
    Combines season, moon phase, and water temp into a go/no-go rating
    and human-readable context for the day detail panel.

    Research-backed NJ striper intel (see fetch_all_spots_hilo for spot data):
      Spring: May is true peak (bunker + migratory fish from Chesapeake arrive together)
      Fall:   October-November South Jersey peak (biggest fish of year; Nov top surf month)
      Water:  44-50F = schoolies active; 50-68F = full feed; >68F = offshore
      Wind:   NE/NW = pin bait, activate bite; S/SW = "stay home" (kills the bite)
      Tide:   Moving water is #1. Last 3 hrs outgoing + first 3 hrs incoming = prime.
    """
    month      = d.month
    moon_phase, moon_pct = moon_phase_label(d)

    # Season context (NJ-specific)  ───────────────────────────────────────────
    _SEASON: dict = {
        1:  ("Winter",       "very_slow",  "Fish have migrated south. Inshore is barren. Use this time to scout spots for spring."),
        2:  ("Winter",       "very_slow",  "Deep winter. Water in the 30s-40s°F — fish are far offshore. Almost nothing inshore."),
        3:  ("Early Spring", "building",   "Holdover schoolies in back bays, lethargic. Mid-month: if water hits 44°F+ try slow soft plastics on big tide days."),
        4:  ("Spring Run",   "excellent",  "Migratory fish arriving from Chesapeake. Moving tides push bait through inlets. Be there at the moving water windows."),
        5:  ("Spring Peak",  "excellent",  "TRUE PEAK. Bunker schools are in, inlets are firing, beaches and bay are fully invaded. Go find fish now."),
        6:  ("Late Spring",  "good",       "Spring run tapering. Larger fish still around. Night fishing picks up — fish moving shallower in dark."),
        7:  ("Summer",       "slow",       "Inshore water >68°F — fish have pushed offshore or north. Target night tides and deep structure. Mostly a waiting game."),
        8:  ("Late Summer",  "fair",       "Adult bunker schools return. Dawn/dusk blitzes possible near inlets when bait schools up. Worth checking early AM."),
        9:  ("Early Fall",   "building",   "Fall migration beginning. Peanut bunker pods forming north, pushing south. Fish fattening up — action picks up late month."),
        10: ("Fall Peak",    "excellent",  "GO. Biggest fish of the year moving through South Jersey. Bunker + mullet drive explosive feeding. Every good tide is worth the trip."),
        11: ("Fall Run",     "excellent",  "TOP MONTH for South Jersey surf. Migrating fish + bait = full-send conditions. NE winds push bait to the beach. Be out there."),
        12: ("Late Fall",    "fair",       "Last of the fall run. Cold fronts accelerate the migration south. Good days still happen but getting fewer. Watch water temps."),
    }
    season_name, season_rating, season_text = _SEASON.get(month, ("Unknown", "unknown", ""))

    # Moon context (spring tide vs. neap)  ────────────────────────────────────
    if moon_pct < 8 or moon_pct > 92:
        moon_rating = "new_full"
        phase_label = "New Moon 🌑" if moon_pct < 8 else "Full Moon 🌕"
        mood        = "New moon = darkest nights, fish hunt shallow. Excellent." if moon_pct < 8 else "Full moon = bright lights + big tides. Work plugs or soft plastics in moving current around dock lights — or fish pitch black moving water away from the crowds."
        moon_text   = f"{phase_label} ({moon_pct}%) — spring tides, biggest swings of the month. {mood}"
    elif 40 <= moon_pct <= 60:
        moon_rating = "quarter"
        moon_text   = f"{moon_phase} ({moon_pct}%) — neap tide week. Tidal swings at minimum. Slower fishing; pick your moving-water windows carefully."
    else:
        moon_rating = "gibbous_crescent"
        moon_text   = f"{moon_phase} ({moon_pct}%) — moderate tidal energy. Good conditions for moving-water windows."

    # Water temp context  ─────────────────────────────────────────────────────
    temp_rating = "unknown"
    temp_text   = ""
    if water_temp_f is not None:
        if water_temp_f < 44:
            temp_rating = "too_cold"
            temp_text   = f"{water_temp_f}°F — very cold. Stripers lethargic; minimal inshore activity."
        elif water_temp_f < 50:
            temp_rating = "cold"
            temp_text   = f"{water_temp_f}°F — cold but building. Schoolies active on big tidal swings. Slow soft plastics."
        elif water_temp_f < 58:
            temp_rating = "warming"
            temp_text   = f"{water_temp_f}°F — warming into the zone. Fish actively moving inshore. Go."
        elif water_temp_f < 68:
            temp_rating = "prime"
            temp_text   = f"{water_temp_f}°F — prime striper temp. Peak feeding activity across all spots."
        elif water_temp_f < 72:
            temp_rating = "warm"
            temp_text   = f"{water_temp_f}°F — warming up. Fish retreating deeper. Target dawn/dusk and night."
        else:
            temp_rating = "too_warm"
            temp_text   = f"{water_temp_f}°F — too warm. Fish have gone offshore. Night-only or don't bother."

    # Wind context  ───────────────────────────────────────────────────────────
    wind_rating = "unknown"
    wind_text   = ""
    if wind_mph is not None and wind_deg is not None:
        card = ["N","NE","E","SE","S","SW","W","NW"][round(wind_deg / 45) % 8]
        spd  = round(wind_mph)
        if card in ("NE", "E") and wind_mph <= 20:
            wind_rating = "great"
            wind_text   = f"{card} {spd} mph — NE wind is prime for NJ inlets. Pins bait to jetties and the beach. Go fish."
        elif card in ("NE", "E"):
            wind_rating = "great"
            wind_text   = f"{card} {spd} mph — strong NE pushing hard. Fish pinned tight to structure; incoming tide windows extremely fast. Stay on the jetties."
        elif card in ("NW", "N") and wind_mph <= 18:
            wind_rating = "good"
            wind_text   = f"{card} {spd} mph — cleans up the surf, activates the bite after storms. Solid conditions."
        elif card in ("W",):
            if wind_mph <= 12:
                wind_rating = "great"
                wind_text   = f"W {spd} mph — glassy conditions. Calm surf, good visibility, comfortable all around."
            elif wind_mph <= 20:
                wind_rating = "good"
                wind_text   = f"W {spd} mph — good conditions. Surf clean and manageable, fish active on moving water."
            elif month in (9, 10, 11):
                wind_rating = "good"
                wind_text   = f"W {spd} mph — west wind pushing bunker schools to the beach. Worth a look."
            else:
                wind_rating = "neutral"
                wind_text   = f"W {spd} mph — clean surf conditions but rough in the back bay. Ocean side fishable, bay spots a grind."
        elif card in ("S", "SW", "SSW", "SSE", "SE"):
            if wind_mph <= 12:
                wind_rating = "neutral"
                wind_text   = f"{card} {spd} mph — light southerly. Not ideal but still fishable; back bay and protected spots hold up fine."
            elif wind_mph <= 20:
                wind_rating = "caution"
                wind_text   = f"{card} {spd} mph — moderate S/SW. Open beaches get choppy and murky; back bay and lee-side jetties still worth fishing."
            else:
                wind_rating = "bad"
                wind_text   = f"{card} {spd} mph — blown out conditions. Dirty water pushed inshore, surf messy. Tough day out there."
        elif wind_mph > 22:
            wind_rating = "rough"
            wind_text   = f"{card} {spd} mph — too windy for comfortable fishing. Jetties dangerous; surf messy."
        else:
            wind_rating = "neutral"
            wind_text   = f"{card} {spd} mph — neutral conditions. Not helping, not hurting."

    # Species conditions  ─────────────────────────────────────────────────────
    species = []

    # Flounder: active April-July in NJ, active range 56-72°F, sweet spot 62-66°F.
    # Drops hurt far more than rises — cold fronts dull bite substantially even within range.
    if month in (4, 5, 6, 7):
        if water_temp_f is not None:
            if water_temp_f < 52:
                fl_status = "slow"
                fl_text   = f"Water at {water_temp_f}°F — too cold inshore. But early season is monster flounder time — the biggest fish of the year come through now. Find the warm water: sun-baked back bay flats and dark-bottom shallows can run 4-5°F warmer than the main channel. Focus there on sunny days."
            elif water_temp_f < 56:
                fl_status = "fair" if month in (4, 5) else "slow"
                fl_text   = f"Water at {water_temp_f}°F — prime early season flounder window. This is when the slabs show up. Main channels are still cold but sun-warmed back bay flats are holding fish. Dark bottom, protected from the wind, sunny afternoon — that combo can produce a doormat."
            elif water_temp_f <= 72:
                # Direction matters: drops are worse than rises
                if temp_change_f is not None and temp_change_f <= -4:
                    fl_status = "slow"
                    fl_text   = f"Water at {water_temp_f}°F but dropping hard ({temp_change_f:+.1f}°F over 3 days). Cold front has dulled the bite — flounder retreat to deeper, stable water. Back bay flats that were warm are now cold. Tough day."
                elif temp_change_f is not None and temp_change_f <= -2:
                    fl_status = "fair"
                    fl_text   = f"Water at {water_temp_f}°F with a noticeable drop ({temp_change_f:+.1f}°F trend). Bite may be suppressed. Fish slower and deeper, stick to wind-protected back bay pockets."
                elif temp_change_f is not None and temp_change_f >= 2:
                    fl_status = "good" if month in (5, 6) else "fair"
                    size_note = " Early season — big fish are in the mix." if month in (4, 5) else ""
                    fl_text   = f"Water at {water_temp_f}°F and rising ({temp_change_f:+.1f}°F over 3 days) — flounder moving onto warm back bay flats and feeding.{size_note} Good window."
                else:
                    fl_status = "good" if month in (5, 6) else "fair"
                    size_note = " Early season means a shot at a real doormat." if month in (4, 5) else ""
                    stable_note = "Sweet spot." if 62 <= water_temp_f <= 66 else "Good range."
                    fl_text   = f"Water at {water_temp_f}°F — stable. {stable_note} Work warm back bay flats and sandy bottom near structure with slow presentations.{size_note}"
            else:
                fl_status = "slow"
                fl_text   = f"Water at {water_temp_f}°F — too warm. Flounder have pushed to deeper structure."
        else:
            fl_status = "fair"
            fl_text   = "Flounder season is open. Early season is the best shot at a true doormat — biggest fish of the year come through now. Key is finding warm water: sun-baked back bay flats run several degrees above the main channel. Once temps stabilize in the 62-66°F range they're everywhere."
        species.append({"name": "Flounder", "icon": "🎣", "status": fl_status, "text": fl_text})

    # Weakfish: active May-October, water 60-72°F, love big moon strong tides
    if month in (5, 6, 7, 8, 9, 10):
        wk_parts = []
        wk_status = "fair"
        if water_temp_f is not None:
            if water_temp_f < 58:
                wk_status = "slow"
                wk_parts.append(f"water at {water_temp_f}°F is still a touch cold for them")
            elif water_temp_f <= 72:
                wk_status = "good"
                wk_parts.append(f"water at {water_temp_f}°F is right in their wheelhouse")
            else:
                wk_status = "fair"
                wk_parts.append(f"water at {water_temp_f}°F is warm — still around but pushed deeper")
        if moon_pct < 15 or moon_pct > 85:
            wk_parts.append("big moon pushing strong tides — prime time for weakfish in the back bay on moving water")
            if wk_status != "slow":
                wk_status = "great"
        elif 40 <= moon_pct <= 60:
            wk_parts.append("neap tide week means slower current — pick your moving water windows carefully")
            if wk_status == "good":
                wk_status = "fair"
        else:
            wk_parts.append("moderate tidal push — back bay structure and inlet mouths worth working")
        wk_text = "Weakfish: " + "; ".join(wk_parts) + "."
        species.append({"name": "Weakfish", "icon": "🎣", "status": wk_status, "text": wk_text})

    # Overall rating (0 = skip → 4 = GO)  ────────────────────────────────────
    base = {"excellent": 4, "good": 3, "building": 2, "fair": 2, "slow": 1, "very_slow": 0}.get(season_rating, 1)
    temp_adj = {
        "prime": 0, "warming": 0, "warm": -1, "too_warm": -2,
        "cold": -1, "too_cold": -2, "unknown": 0,
    }.get(temp_rating, 0)
    wind_adj = {"great": 1, "good": 0, "neutral": 0, "caution": 0, "bad": -1, "rough": -1, "unknown": 0}.get(wind_rating, 0)
    overall  = max(0, min(4, base + temp_adj + wind_adj))

    _LABELS = ["Skip It",  "Slow Day", "Worth a Shot", "Good Day", "GO NOW 🎣"]
    _COLORS = ["#475569",  "#64748b",  "#14b8a6",      "#f59e0b",  "#ef4444"  ]
    _ICONS  = ["💤",       "🐌",       "🎣",           "⭐",       "🔥"       ]

    return {
        "season_name":   season_name,
        "season_rating": season_rating,
        "season_text":   season_text,
        "moon_phase":    moon_phase,
        "moon_pct":      moon_pct,
        "moon_rating":   moon_rating,
        "moon_text":     moon_text,
        "temp_rating":   temp_rating,
        "temp_text":     temp_text,
        "wind_rating":   wind_rating,
        "wind_text":     wind_text,
        "overall":       overall,
        "overall_label": _LABELS[overall],
        "overall_color": _COLORS[overall],
        "overall_icon":  _ICONS[overall],
        "species":       species,
    }


def get_events(days: int = 90) -> dict:
    """
    Fetch tide predictions for all 5 South Jersey striper spots and score each
    tidal event using a multi-factor model.

    Returns:
        {
          "events":    list of event dicts sorted by date/time,
          "threshold": tidal-range cut-off in feet,
          "generated": ISO date string,
          "days":      number of days fetched,
        }
    """
    today    = date.today()
    end_date = today + timedelta(days=days)

    # ── Fetch hilo predictions for all spots (parallel) ───────────────────────
    spot_tides: dict[str, list[dict]] = {}
    def _fetch_spot_tides(spot, cfg):
        try:
            return spot, fetch_tides(cfg["station_id"], today, end_date)
        except Exception:
            return spot, []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_fetch_spot_tides, s, c) for s, c in SPOT_CONFIG.items()]
        for f in as_completed(futs):
            spot, tides = f.result()
            spot_tides[spot] = tides

    # ── Daily tidal range from Cape May reference station ────────────────────
    # Cape May has the most complete data and is a good regional proxy for
    # tidal energy — a big swing here means strong currents at all 5 spots.
    daily: dict[str, dict[str, list[float]]] = {}
    for t in spot_tides.get("Cape May Point", []):
        day = t["t"][:10]
        v   = float(t["v"])
        if day not in daily:
            daily[day] = {"H": [], "L": []}
        daily[day][t["type"]].append(v)

    ranges: dict[str, float] = {
        day: max(hl["H"]) - min(hl["L"])
        for day, hl in daily.items()
        if hl["H"] and hl["L"]
    }

    sorted_ranges = sorted(ranges.values())
    n             = len(sorted_ranges)
    threshold     = sorted_ranges[int(n * BIG_SWING_PERCENTILE / 100)] if n else 4.0

    # ── Fetch boost data (wind, pressure, temp trend) for near-term scoring ──
    # Wind + pressure: available for ~7 days (NWS forecast) / today (observations)
    # Temp trend: 3-day lookback, same value applies to all near-term events
    boost_wind: dict[str, dict] = {}   # day_str → {hour → {mph, deg}}
    boost_pressure_mb: float = None
    boost_temp_change: float = None

    # Fetch conditions for today + next 7 days (wind per hour) — parallel
    forecast_end = min(today + timedelta(days=7), end_date)
    def _fetch_boost(d_fc, day_off):
        try:
            cond = fetch_marine_conditions(d_fc)
            return d_fc, day_off, cond
        except Exception:
            return d_fc, day_off, None

    with ThreadPoolExecutor(max_workers=4) as pool:
        boost_futs = [pool.submit(_fetch_boost, today + timedelta(days=i), i)
                      for i in range((forecast_end - today).days + 1)]
        # Also fetch temp trend in parallel
        temp_fut = pool.submit(lambda: fetch_water_temp_trend(3))
        for f in as_completed(boost_futs):
            d_fc, day_off, cond = f.result()
            if cond is None:
                continue
            hourly_fc = cond.get("hourly", [])
            wind_data = {}
            for h in hourly_fc:
                if h["wind_mph"] is not None and h["wind_deg"] is not None:
                    wind_data[h["hour"]] = {"mph": h["wind_mph"], "deg": h["wind_deg"]}
            if wind_data:
                boost_wind[d_fc.isoformat()] = wind_data
            if day_off == 0 and cond.get("pressure_trend_mb") is not None:
                boost_pressure_mb = cond["pressure_trend_mb"]
        try:
            temp_trend = temp_fut.result()
            boost_temp_change = temp_trend.get("change_f")
        except Exception:
            pass

    # ── Score and collect events ─────────────────────────────────────────────
    events: list[dict] = []

    for spot, tides in spot_tides.items():
        cfg       = SPOT_CONFIG[spot]
        want_type = cfg["tide_type"]
        tide_word = "High" if want_type == "H" else "Low"
        loc_long  = cfg["location_long"]

        for t in tides:
            if t["type"] != want_type:
                continue
            day_str = t["t"][:10]
            swing   = ranges.get(day_str, 0.0)
            if swing < threshold:
                continue  # below minimum tidal energy for this spot

            d      = date.fromisoformat(day_str)
            dt     = datetime.strptime(t["t"], "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
            height = float(t["v"])
            solar  = get_solar(d)
            tod    = time_of_day(dt, solar)
            moon_label, moon_pct = moon_phase_label(d)

            # Percentile rank of today's tidal range within the loaded window
            rng_pct = bisect.bisect_left(sorted_ranges, swing) / len(sorted_ranges)

            # Get boost data for this event's day/hour (if available)
            ev_wind_mph, ev_wind_deg = None, None
            day_wind = boost_wind.get(day_str)
            if day_wind:
                # Use wind at the event's hour
                hw = day_wind.get(dt.hour)
                if hw:
                    ev_wind_mph, ev_wind_deg = hw["mph"], hw["deg"]

            # Pressure trend only applies to today
            ev_pressure = boost_pressure_mb if day_str == today.isoformat() else None

            score = _score_event(
                rng_pct, tod, moon_label, d.month,
                wind_mph=ev_wind_mph, wind_deg=ev_wind_deg,
                pressure_trend_mb=ev_pressure,
                temp_change_f=boost_temp_change,
            )

            if score < 35:
                continue  # not compelling enough to surface on the calendar

            events.append({
                "date":          day_str,
                "location":      spot,
                "location_long": loc_long,
                "tide_type":     tide_word,
                "time":          dt.strftime("%H:%M"),
                "time_12h":      dt.strftime("%-I:%M %p"),
                "height":        round(height, 1),
                "daily_range":   round(swing, 2),
                "score":         score,
                "quality":       "really_good" if score >= 65 else "good",
                "time_of_day":   tod,
                "moon":          moon_label,
                "moon_pct":      moon_pct,
                "solar": {
                    "dawn":       solar["dawn"].strftime("%H:%M"),
                    "sunrise":    solar["sunrise"].strftime("%H:%M"),
                    "sunset":     solar["sunset"].strftime("%H:%M"),
                    "dusk":       solar["dusk"].strftime("%H:%M"),
                    "dawn_12":    solar["dawn"].strftime("%-I:%M %p"),
                    "sunrise_12": solar["sunrise"].strftime("%-I:%M %p"),
                    "sunset_12":  solar["sunset"].strftime("%-I:%M %p"),
                    "dusk_12":    solar["dusk"].strftime("%-I:%M %p"),
                },
            })

    events.sort(key=lambda e: (e["date"], e["time"]))

    return {
        "events":    events,
        "threshold": round(threshold, 2),
        "generated": today.isoformat(),
        "days":      days,
    }


# ── Calendar builder ──────────────────────────────────────────────────────────

def build_ics(events: list[dict]) -> bytes:
    """Build and return .ics calendar bytes from a list of event dicts."""
    cal = Calendar()
    cal.add("prodid",        "-//Striper Tide Calendar//EN")
    cal.add("version",       "2.0")
    cal.add("x-wr-calname",  "Striper Tides")
    cal.add("x-wr-timezone", TIMEZONE)

    for e in events:
        dt = datetime.strptime(
            f"{e['date']} {e['time']}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=LOCAL_TZ)

        score  = e.get("score", "")
        prefix = "★★★ PRIME" if e["quality"] == "really_good" else "★★ Good"
        title  = (
            f"{prefix} — {e['location']} {e['tide_type']} "
            f"[{e['time_of_day'].capitalize()}]"
            + (f" [{score}/100]" if score else "")
        )
        description = (
            f"Spot: {e['location_long']}\n"
            f"Tide: {e['tide_type']} at {e['time_12h']}  ({e['height']:.1f} ft)\n"
            f"Daily Range: {e['daily_range']:.2f} ft\n"
            f"Score: {score}/100\n"
            f"Moon: {e['moon']}  ({e['moon_pct']}%)\n"
            f"Time: {e['time_of_day'].capitalize()}\n"
            f"---\n"
            f"Dawn   : {e['solar']['dawn_12']}\n"
            f"Sunrise: {e['solar']['sunrise_12']}\n"
            f"Sunset : {e['solar']['sunset_12']}\n"
            f"Dusk   : {e['solar']['dusk_12']}"
        )

        ev = Event()
        ev.add("summary",     title)
        ev.add("dtstart",     dt)
        ev.add("dtend",       dt + timedelta(hours=2))
        ev.add("description", description)
        ev.add("uid",         str(uuid.uuid4()) + "@stripercal")
        cal.add_component(ev)

    return cal.to_ical()


# ── Water Clarity Forecaster ──────────────────────────────────────────────────
# Single Cape May County regional forecast.
# Model: turbidity score (0-100) driven by waves, wind, rain, tidal energy.
# Decays over time with a half-life that varies by conditions.
# User "live reports" stored in DB for calibration and ground truth.

_NDBC_URLS = {
    "44009": "https://www.ndbc.noaa.gov/data/realtime2/44009.txt",  # Cape May / Delaware Bay
    "44025": "https://www.ndbc.noaa.gov/data/realtime2/44025.txt",  # Long Island South (LBI)
}
_NDBC_URL = _NDBC_URLS["44009"]   # legacy alias for clarity model
_M_TO_FT  = 3.28084

# ── Surf spots — beach orientation, offshore wind, buoy assignment ────────────
SURF_SPOTS = {
    "LBI": {
        "label":       "Long Beach Island",
        "buoy":        "44025",
        "lat":         39.63,
        "lon":         -74.10,
        "beach_deg":   110,     # faces ESE
        "offshore_deg": 315,    # NW is offshore
        "offshore_label": "NW",
    },
    "Ocean City": {
        "label":       "Ocean City, NJ",
        "buoy":        "44009",
        "lat":         39.28,
        "lon":         -74.55,
        "beach_deg":   110,     # faces ESE
        "offshore_deg": 315,    # NW is offshore
        "offshore_label": "NW",
    },
    "Avalon": {
        "label":       "Avalon, NJ",
        "buoy":        "44009",
        "lat":         39.10,
        "lon":         -74.72,
        "beach_deg":   115,     # faces ESE
        "offshore_deg": 292,    # WNW is offshore
        "offshore_label": "WNW",
    },
    "Cape May": {
        "label":       "Cape May, NJ",
        "buoy":        "44009",
        "lat":         38.93,
        "lon":         -74.86,
        "beach_deg":   160,     # faces SSE — sheltered from E, open to S
        "offshore_deg": 0,      # N is offshore
        "offshore_label": "N",
    },
}

# Open-Meteo marine model IDs
_MARINE_MODELS = {
    "gfs":  "ncep_gfswave025",
    "euro": "ecmwf_wam025",
}

_OPEN_METEO_MARINE = "https://marine-api.open-meteo.com/v1/marine"

CLARITY_LEVELS = [
    {"max": 15, "label": "Crystal",   "color": "#06b6d4"},
    {"max": 30, "label": "Clean",     "color": "#22c55e"},
    {"max": 50, "label": "Stained",   "color": "#eab308"},
    {"max": 75, "label": "Muddy",     "color": "#f97316"},
    {"max": 999,"label": "Blown Out", "color": "#ef4444"},
]


def _score_to_clarity(score: float) -> dict:
    """Map a turbidity score (0–100) to a clarity level dict."""
    for lvl in CLARITY_LEVELS:
        if score <= lvl["max"]:
            return {**lvl}
    return {**CLARITY_LEVELS[-1]}


def _fetch_ndbc_waves(station_id: str = "44009") -> list[dict]:
    """Fetch last ~48h of wave observations from an NDBC buoy."""
    url = _NDBC_URLS.get(station_id, _NDBC_URLS["44009"])
    try:
        resp = requests.get(url, timeout=20,
                            headers={"User-Agent": "StriperTidesApp/1.0"})
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        results = []
        for line in lines[2:]:          # skip 2 header lines
            parts = line.split()
            if len(parts) < 12:
                continue
            try:
                yr, mo, dy, hr, mn = (int(parts[i]) for i in range(5))
                wvht = float(parts[8])   # significant wave height (m)
                dpd  = float(parts[9])   # dominant period (s)
                mwd  = float(parts[11])  # mean wave direction (deg)
                if wvht > 90 or dpd > 90:   # 99.0 = missing
                    continue
                mwd_clean = None if mwd > 360 else round(mwd)
                dt_utc = datetime(yr, mo, dy, hr, mn, tzinfo=_tz.utc)
                results.append({
                    "dt":          dt_utc.astimezone(LOCAL_TZ),
                    "wave_ht_ft":  round(wvht * _M_TO_FT, 1),
                    "period_s":    round(dpd, 1),
                    "swell_deg":   mwd_clean,
                })
            except (ValueError, IndexError):
                continue
        results.sort(key=lambda x: x["dt"], reverse=True)
        cutoff = datetime.now(LOCAL_TZ) - timedelta(hours=48)
        return [r for r in results if r["dt"] >= cutoff]
    except Exception:
        return []


def _wind_turbidity(mph, deg) -> float:
    """Hourly turbidity contribution from wind."""
    if mph is None or deg is None:
        return 0.0
    card = ["N","NE","E","SE","S","SW","W","NW"][round(deg / 45) % 8]
    if card in ("NE", "E", "ENE", "ESE") and mph > 12:
        return (mph - 12) * 0.5          # onshore churn
    if card in ("S", "SW", "SSW", "SE") and mph > 12:
        return (mph - 12) * 0.3          # dirty Delaware Bay water pushed in
    return 0.0


def _wave_turbidity(wave_ht_ft: float, period_s: float) -> float:
    """Hourly turbidity contribution from waves."""
    if period_s <= 0:
        return 0.0
    # Short-period chop churns bottom much more than long ground swell
    energy = wave_ht_ft * (8.0 / max(period_s, 4.0))
    return max(0.0, energy * 1.5 - 3.0)   # threshold at ~2 ft equiv


def _decay_factor(mph, deg) -> float:
    """Hourly turbidity decay multiplier (lower = clears faster)."""
    base_half_life = 18.0   # hours in calm conditions
    if mph is not None and deg is not None:
        card = ["N","NE","E","SE","S","SW","W","NW"][round(deg / 45) % 8]
        if card in ("NW", "W", "N") and mph > 8:
            base_half_life = 12.0   # offshore wind cleans up fast
        elif card in ("NE", "E") and mph > 15:
            base_half_life = 28.0   # strong onshore prevents settling
    return 0.5 ** (1.0 / base_half_life)


def get_clarity_forecast() -> dict:
    """
    Compute a 72-hour water clarity forecast for Cape May County.

    Returns:
        {
            "updated":    ISO timestamp,
            "current":    {label, color, score},
            "hourly":     [{offset, score, label, color}, ...],   72 entries
            "clears_by":  ISO timestamp or null,
            "drivers":    {wave, wind, rain, tide summary strings},
        }
    """
    now       = datetime.now(LOCAL_TZ)
    today     = now.date()

    # ── 1. Wave data from NDBC buoy ────────────────────────────────────────
    waves = _fetch_ndbc_waves()
    if waves:
        recent     = waves[:6]   # last ~6 hours
        avg_wave   = sum(w["wave_ht_ft"] for w in recent) / len(recent)
        avg_period = sum(w["period_s"]   for w in recent) / len(recent)
    else:
        avg_wave, avg_period = 1.5, 8.0   # calm default

    # ── 2. Wind timeline: past (ASOS) + future (NWS) ──────────────────────
    # Fetch today + next 3 days of conditions (reuses cached data)
    wind_by_hour: dict[int, dict] = {}   # offset → {mph, deg}
    for day_off in range(4):
        d = today + timedelta(days=day_off)
        try:
            cond = fetch_marine_conditions(d)
        except Exception:
            continue
        for h in cond.get("hourly", []):
            abs_hour  = day_off * 24 + h["hour"]
            offset    = abs_hour - now.hour
            if -48 <= offset < 72 and h["wind_mph"] is not None:
                wind_by_hour[offset] = {
                    "mph": h["wind_mph"],
                    "deg": h["wind_deg"],
                }

    # ── 3. Precipitation from NWS forecast ─────────────────────────────────
    precip_by_hour: dict[int, float] = {}
    try:
        resp = requests.get(_NWS_FORECAST, headers=_NWS_HEADERS, timeout=15)
        resp.raise_for_status()
        for p in resp.json()["properties"]["periods"]:
            dt_p = datetime.fromisoformat(p["startTime"]).astimezone(LOCAL_TZ)
            off  = int((dt_p - now).total_seconds() / 3600)
            if off < 0 or off >= 72:
                continue
            # Check quantitativePrecipitation (mm) or estimate from shortForecast
            qp = p.get("quantitativePrecipitation") or {}
            if isinstance(qp, dict) and qp.get("value") is not None:
                precip_by_hour[off] = round(qp["value"] / 25.4, 2)
            else:
                short = (p.get("shortForecast") or "").lower()
                if any(w in short for w in ("rain", "shower", "storm", "drizzle")):
                    prob = (p.get("probabilityOfPrecipitation") or {}).get("value") or 0
                    precip_by_hour[off] = round(prob / 100 * 0.08, 3)
    except Exception:
        pass

    # ── 4. Tidal range today (proxy for sediment energy) ───────────────────
    try:
        hilo = fetch_tides(CAPE_MAY_STATION, today, today)
        highs = [float(t["v"]) for t in hilo if t["type"] == "H"]
        lows  = [float(t["v"]) for t in hilo if t["type"] == "L"]
        tide_range = max(highs) - min(lows) if highs and lows else 4.5
    except Exception:
        tide_range = 4.5
    tide_turb = max(0, (tide_range - 4.5) * 1.0)   # bonus above 4.5 ft

    # ── 5. Seed initial turbidity from recent wave/wind history ────────────
    turbidity = 5.0    # baseline (not perfectly clear)
    for off in range(-48, 0):
        w = wind_by_hour.get(off, {})
        mph, deg = w.get("mph"), w.get("deg")
        added  = _wind_turbidity(mph, deg) + _wave_turbidity(avg_wave, avg_period) + tide_turb
        decay  = _decay_factor(mph, deg)
        turbidity = turbidity * decay + added
    turbidity = max(0, min(100, turbidity))

    # ── 6. Project forward 72 hours ────────────────────────────────────────
    hourly: list[dict] = []
    # Track predicted wave: simple model — onshore wind builds waves, offshore calms them
    pred_wave   = avg_wave
    pred_period = avg_period
    clears_by   = None

    for off in range(72):
        w   = wind_by_hour.get(off, {})
        mph = w.get("mph")
        deg = w.get("deg")

        # Evolve predicted wave height from wind
        if mph is not None and deg is not None:
            card = ["N","NE","E","SE","S","SW","W","NW"][round(deg / 45) % 8]
            if card in ("NE", "E") and mph > 10:
                equil = (mph ** 1.4) / 40.0   # rough equilibrium wave height
                pred_wave += (equil - pred_wave) * 0.12
                pred_period = max(4, pred_period - 0.1)   # period shortens
            else:
                pred_wave *= 0.93    # decay toward calm
                pred_period = min(12, pred_period + 0.05)
        else:
            pred_wave *= 0.95
        pred_wave = max(0.3, pred_wave)

        rain_in  = precip_by_hour.get(off, 0.0)
        added    = (_wind_turbidity(mph, deg)
                    + _wave_turbidity(pred_wave, pred_period)
                    + rain_in * 20
                    + tide_turb * (0.3 if off > 24 else 1.0))   # tide effect fades for future days
        decay    = _decay_factor(mph, deg)
        turbidity = max(0, min(100, turbidity * decay + added))

        lvl = _score_to_clarity(turbidity)
        hourly.append({
            "offset": off,
            "score":  round(turbidity, 1),
            "label":  lvl["label"],
            "color":  lvl["color"],
        })

        # Track when it clears to "Clean" or better
        if clears_by is None and turbidity <= 30 and off > 0:
            clears_by = (now + timedelta(hours=off)).isoformat()

    current = _score_to_clarity(hourly[0]["score"] if hourly else 10)
    current["score"] = hourly[0]["score"] if hourly else 10

    # ── 7. Build driver summaries ──────────────────────────────────────────
    wave_desc = f"{avg_wave:.1f} ft @ {avg_period:.0f}s period"
    if avg_period < 7:
        wave_desc += " — short-period chop, churning bottom"
    elif avg_wave > 4:
        wave_desc += " — heavy swell stirring things up"
    elif avg_wave < 1.5:
        wave_desc += " — calm seas, minimal churn"
    else:
        wave_desc += " — moderate, settling"

    # Current wind summary
    cw = wind_by_hour.get(0, {})
    if cw.get("mph") is not None:
        card = ["N","NE","E","SE","S","SW","W","NW"][round(cw["deg"] / 45) % 8]
        wind_desc = f"{card} {round(cw['mph'])} mph"
        if card in ("NE", "E") and cw["mph"] > 12:
            wind_desc += " — onshore, stirring sediment"
        elif card in ("NW", "W") and cw["mph"] > 8:
            wind_desc += " — offshore, helping clear"
        elif card in ("S", "SW") and cw["mph"] > 10:
            wind_desc += " — pushing bay water in"
    else:
        wind_desc = "No current wind data"

    total_rain = sum(precip_by_hour.values())
    rain_desc  = f"{total_rain:.1f}\" expected next 72h" if total_rain > 0.05 else "No rain in forecast"
    if total_rain > 0.5:
        rain_desc += " — runoff will muddy the inlets"

    tide_desc = f"{tide_range:.1f} ft range"
    if tide_range > 5.2:
        tide_desc += " — spring tides, extra sediment movement"
    elif tide_range < 3.5:
        tide_desc += " — neap tides, less churn"

    return {
        "updated":   now.isoformat(),
        "current":   current,
        "hourly":    hourly,
        "clears_by": clears_by,
        "drivers": {
            "wave": wave_desc,
            "wind": wind_desc,
            "rain": rain_desc,
            "tide": tide_desc,
        },
    }


# ── Surf Forecast ────────────────────────────────────────────────────────────

def _fetch_marine_model(lat: float, lon: float, model_key: str) -> list:
    """
    Fetch hourly wave forecast from Open-Meteo marine API (GFS-Wave or ECMWF WAM).
    Returns list of {dt, wave_ht_ft, period_s, swell_ht_ft, swell_period_s,
                      swell_deg, wind_wave_ht_ft, wind_wave_period_s} dicts.
    """
    model_id = _MARINE_MODELS.get(model_key)
    if not model_id:
        return []
    try:
        resp = requests.get(_OPEN_METEO_MARINE, params={
            "latitude":      lat,
            "longitude":     lon,
            "hourly":        ",".join([
                "wave_height", "wave_period", "wave_direction",
                "swell_wave_height", "swell_wave_period", "swell_wave_direction",
                "wind_wave_height", "wind_wave_period", "wind_wave_direction",
            ]),
            "forecast_days": 7,
            "past_days":     2,
            "models":        model_id,
            "timezone":      TIMEZONE,
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        if not times:
            return []

        results = []
        for i, t_str in enumerate(times):
            wh = hourly.get("wave_height", [])[i] if i < len(hourly.get("wave_height", [])) else None
            wp = hourly.get("wave_period", [])[i] if i < len(hourly.get("wave_period", [])) else None
            wd = hourly.get("wave_direction", [])[i] if i < len(hourly.get("wave_direction", [])) else None
            sh = hourly.get("swell_wave_height", [])[i] if i < len(hourly.get("swell_wave_height", [])) else None
            sp = hourly.get("swell_wave_period", [])[i] if i < len(hourly.get("swell_wave_period", [])) else None
            sd = hourly.get("swell_wave_direction", [])[i] if i < len(hourly.get("swell_wave_direction", [])) else None
            wwh = hourly.get("wind_wave_height", [])[i] if i < len(hourly.get("wind_wave_height", [])) else None
            wwp = hourly.get("wind_wave_period", [])[i] if i < len(hourly.get("wind_wave_period", [])) else None

            if wh is None:
                continue

            dt_local = datetime.strptime(t_str, "%Y-%m-%dT%H:%M").replace(tzinfo=LOCAL_TZ)
            results.append({
                "dt":               dt_local,
                "wave_ht_ft":       round(wh * _M_TO_FT, 1),
                "period_s":         round(wp, 1) if wp else None,
                "wave_deg":         round(wd) if wd else None,
                "swell_ht_ft":      round(sh * _M_TO_FT, 1) if sh else None,
                "swell_period_s":   round(sp, 1) if sp else None,
                "swell_deg":        round(sd) if sd else (round(wd) if wd else None),
                "wind_wave_ht_ft":  round(wwh * _M_TO_FT, 1) if wwh else None,
                "wind_wave_period_s": round(wwp, 1) if wwp else None,
            })
        return results
    except Exception:
        return []


def _wind_quality_tag(wind_mph, wind_deg, spot_cfg: dict) -> dict:
    """
    Classify wind quality for surfing at a given spot.
    Returns {tag, color, short} based on wind direction relative to beach.
    """
    if wind_mph is None or wind_deg is None:
        return {"tag": "No Wind Data", "color": "#527898", "short": "?"}

    beach_deg  = spot_cfg["beach_deg"]
    # Angle between wind direction (where FROM) and beach-facing direction
    # If wind blows FROM the same direction the beach faces → onshore
    # If wind blows FROM opposite → offshore
    diff = abs((wind_deg - beach_deg + 180) % 360 - 180)

    if wind_mph < 3:
        return {"tag": "Glass", "color": "#06b6d4", "short": "Glass"}
    if wind_mph < 7:
        if diff > 120:
            return {"tag": "Light Offshore", "color": "#22c55e", "short": "Lt Off"}
        if diff < 60:
            return {"tag": "Light Onshore", "color": "#eab308", "short": "Lt On"}
        return {"tag": "Light & Variable", "color": "#22c55e", "short": "Light"}

    # Stronger winds (7+ mph)
    if diff > 140:
        return {"tag": "Clean & Offshore", "color": "#22c55e", "short": "Off"}
    if diff > 100:
        return {"tag": "Side-offshore", "color": "#60a5fa", "short": "Side-off"}
    if diff > 70:
        return {"tag": "Cross-shore", "color": "#f59e0b", "short": "Cross"}
    if diff > 40:
        return {"tag": "Side-onshore", "color": "#f97316", "short": "Side-on"}

    # Direct onshore
    if wind_mph > 20:
        return {"tag": "Blown Out", "color": "#ef4444", "short": "Blown"}
    return {"tag": "Onshore Chop", "color": "#f97316", "short": "On"}


def get_surf_forecast(spot_key: str, model: str = "gfs") -> dict:
    """
    Surf forecast for a given spot using GFS, Euro, or our proprietary wind model.

    model: 'gfs' | 'euro' | 'striper'
    """
    if spot_key not in SURF_SPOTS:
        raise ValueError(f"Unknown surf spot: {spot_key}")

    cfg = SURF_SPOTS[spot_key]
    now = datetime.now(LOCAL_TZ)
    today = now.date()
    card_dirs = ["N","NE","E","SE","S","SW","W","NW"]

    # ── 1. Collect wind data (needed for quality tags + striper model) ───
    wind_all = {}
    for day_off in range(-2, 4):
        d = today + timedelta(days=day_off)
        try:
            cond = fetch_marine_conditions(d)
        except Exception:
            continue
        for h in cond.get("hourly", []):
            abs_hour = day_off * 24 + h["hour"]
            offset = abs_hour - now.hour
            if -48 <= offset < 168 and h["wind_mph"] is not None:
                wind_all[offset] = {"mph": h["wind_mph"], "deg": h["wind_deg"]}

    # ── 2. Get wave data based on selected model ─────────────────────────
    history  = []
    forecast = []
    model_label = model

    if model in ("gfs", "euro"):
        # Use Open-Meteo marine API for real model data
        raw = _fetch_marine_model(cfg["lat"], cfg["lon"], model)
        for pt in raw:
            offset_h = round((pt["dt"] - now).total_seconds() / 3600, 1)
            swell_card = card_dirs[round(pt["swell_deg"] / 45) % 8] if pt.get("swell_deg") is not None else None
            # Wind quality for this hour
            closest_wind_off = round(offset_h)
            w = wind_all.get(closest_wind_off, {})
            wq = _wind_quality_tag(w.get("mph"), w.get("deg"), cfg)

            entry = {
                "offset":          offset_h,
                "dt_label":        pt["dt"].strftime("%-I %p %a"),
                "wave_ht_ft":      pt["wave_ht_ft"],
                "period_s":        pt["period_s"],
                "swell_ht_ft":     pt.get("swell_ht_ft"),
                "swell_period_s":  pt.get("swell_period_s"),
                "swell_deg":       pt.get("swell_deg"),
                "swell_card":      swell_card,
                "wind_wave_ht_ft": pt.get("wind_wave_ht_ft"),
                "wind_mph":        round(w["mph"]) if w.get("mph") else None,
                "wind_card":       card_dirs[round(w["deg"] / 45) % 8] if w.get("deg") is not None else None,
                "wind_quality":    wq,
            }
            if offset_h <= 0:
                history.append(entry)
            else:
                forecast.append(entry)
    else:
        # "striper" — proprietary wind-driven model
        model_label = "striper"
        # Try NDBC buoy for history
        waves = _fetch_ndbc_waves(cfg["buoy"])
        buoy_ok = len(waves) > 0

        if buoy_ok:
            waves_chrono = sorted(waves, key=lambda w: w["dt"])
            for w in waves_chrono:
                offset_h = (w["dt"] - now).total_seconds() / 3600
                swell_card = card_dirs[round(w["swell_deg"] / 45) % 8] if w["swell_deg"] is not None else None
                cw = wind_all.get(round(offset_h), {})
                history.append({
                    "offset":      round(offset_h, 1),
                    "dt_label":    w["dt"].strftime("%-I %p %a"),
                    "wave_ht_ft":  w["wave_ht_ft"],
                    "period_s":    w["period_s"],
                    "swell_deg":   w["swell_deg"],
                    "swell_card":  swell_card,
                    "wind_mph":    round(cw["mph"]) if cw.get("mph") else None,
                    "wind_card":   card_dirs[round(cw["deg"] / 45) % 8] if cw.get("deg") is not None else None,
                    "wind_quality": _wind_quality_tag(cw.get("mph"), cw.get("deg"), cfg),
                })
        else:
            est_wave, est_period = 1.0, 8.0
            for off in range(-48, 1):
                w = wind_all.get(off, {})
                mph, deg = w.get("mph"), w.get("deg")
                if mph is not None and deg is not None:
                    beach_diff = abs((deg - cfg["beach_deg"] + 180) % 360 - 180)
                    if beach_diff < 60 and mph > 8:
                        equil = min(mph / 5.0, 8.0)
                        est_wave += (equil - est_wave) * 0.08
                        est_period = max(4, est_period - 0.08)
                    elif beach_diff > 120 and mph > 8:
                        est_wave *= 0.96
                        est_period = min(14, est_period + 0.03)
                    else:
                        est_wave *= 0.97
                        est_period = min(12, est_period + 0.02)
                else:
                    est_wave *= 0.98
                est_wave = max(0.3, est_wave)
                fwd_dt = now + timedelta(hours=off)
                history.append({
                    "offset":      off,
                    "dt_label":    fwd_dt.strftime("%-I %p %a"),
                    "wave_ht_ft":  round(est_wave, 1),
                    "period_s":    round(est_period, 1),
                    "swell_deg":   None,
                    "swell_card":  None,
                    "estimated":   True,
                    "wind_mph":    round(mph) if mph else None,
                    "wind_card":   card_dirs[round(deg / 45) % 8] if deg is not None else None,
                    "wind_quality": _wind_quality_tag(mph, deg, cfg),
                })

        # Forward projection
        pred_wave   = history[-1]["wave_ht_ft"] if history else 1.5
        pred_period = history[-1]["period_s"] if history else 8.0
        for off in range(72):
            w = wind_all.get(off, {})
            mph, deg = w.get("mph"), w.get("deg")
            if mph is not None and deg is not None:
                beach_diff = abs((deg - cfg["beach_deg"] + 180) % 360 - 180)
                if beach_diff < 60 and mph > 8:
                    equil = min(mph / 5.0, 8.0)
                    pred_wave += (equil - pred_wave) * 0.08
                    pred_period = max(4, pred_period - 0.08)
                elif beach_diff > 120 and mph > 8:
                    pred_wave *= 0.96
                    pred_period = min(14, pred_period + 0.03)
                else:
                    pred_wave *= 0.97
                    pred_period = min(12, pred_period + 0.02)
            else:
                pred_wave *= 0.98
            pred_wave = max(0.3, pred_wave)
            fwd_dt = now + timedelta(hours=off)
            forecast.append({
                "offset":       off,
                "dt_label":     fwd_dt.strftime("%-I %p %a"),
                "wave_ht_ft":   round(pred_wave, 1),
                "period_s":     round(pred_period, 1),
                "wind_mph":     round(mph) if mph else None,
                "wind_card":    card_dirs[round(deg / 45) % 8] if deg is not None else None,
                "wind_quality": _wind_quality_tag(mph, deg, cfg),
            })

    # ── 3. Current conditions (from first forecast point or last history) ─
    ref = forecast[0] if forecast else (history[-1] if history else {})
    cw = wind_all.get(0, {})
    cur_wind_mph = cw.get("mph")
    cur_wind_deg = cw.get("deg")
    cur_swell = ref.get("swell_deg")

    current = {
        "wave_ht_ft":  ref.get("wave_ht_ft"),
        "period_s":    ref.get("period_s"),
        "swell_ht_ft": ref.get("swell_ht_ft"),
        "swell_deg":   cur_swell,
        "swell_card":  card_dirs[round(cur_swell / 45) % 8] if cur_swell is not None else None,
        "wind_mph":    cur_wind_mph,
        "wind_deg":    cur_wind_deg,
        "wind_card":   card_dirs[round(cur_wind_deg / 45) % 8] if cur_wind_deg is not None else None,
        "quality":     _wind_quality_tag(cur_wind_mph, cur_wind_deg, cfg),
        "estimated":   model == "striper" and not any(True for h in history if not h.get("estimated")),
    }

    return {
        "spot":      {**cfg, "key": spot_key},
        "model":     model_label,
        "updated":   now.isoformat(),
        "current":   current,
        "history":   history,
        "forecast":  forecast,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate striper fishing tide calendar (.ics) for Apple Calendar."
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="How many days ahead to generate events (default: 90)"
    )
    args = parser.parse_args()

    today    = date.today()
    end_date = today + timedelta(days=args.days)
    print(f"Fetching tide predictions  {today}  →  {end_date}")

    data   = get_events(args.days)
    events = data["events"]

    really_good = sum(1 for e in events if e["quality"] == "really_good")
    good        = sum(1 for e in events if e["quality"] == "good")
    print(f"  Big-swing cut  : {data['threshold']:.2f} ft  (top 33% of days)")
    print(f"\nGenerated {len(events)} events  ({really_good} Really Good,  {good} Good)")

    out = Path.home() / "Desktop" / "striper_tides.ics"
    out.write_bytes(build_ics(events))
    print(f"Saved to : {out}")
    print("Opening Apple Calendar ...")
    subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
