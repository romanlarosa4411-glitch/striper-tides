#!/usr/bin/env python3
"""
app.py — Flask web interface for Striper Tides
Run: python3 app.py  →  http://localhost:5001
"""

import io
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request, send_file

import striper_tides as st
from db import SPOTS, get_conn, init_db

app    = Flask(__name__)
LOCAL_TZ = ZoneInfo(st.TIMEZONE)

# ── In-memory cache (keyed by today's date so it refreshes each day) ──────────
_cache: dict = {}

def _key(prefix: str, **kw) -> str:
    today = date.today().isoformat()
    parts = "&".join(f"{k}={v}" for k, v in sorted(kw.items()))
    return f"{prefix}:{today}:{parts}"


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", spots=SPOTS)


# ── Tide calendar API ──────────────────────────────────────────────────────────

@app.route("/api/events")
def api_events():
    days = int(request.args.get("days", 90))
    key  = _key("events", days=days)
    if key not in _cache:
        _cache[key] = st.get_events(days)
    return jsonify(_cache[key])


@app.route("/api/chart")
def api_chart():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "date required"}), 400
    key = _key("chart", date=date_str)
    if key not in _cache:
        try:
            d        = date.fromisoformat(date_str)
            hereford = st.fetch_tides_hourly(st.HEREFORD_STATION, d)
            cape_may = st.fetch_tides_hourly(st.CAPE_MAY_STATION,  d)
            _cache[key] = {"hereford": hereford, "cape_may": cape_may}
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify(_cache[key])


@app.route("/api/forecast/<date_str>")
def api_forecast(date_str):
    """Full day forecast: tides (hourly) + all-spot hilo + solunar + wind + water temp + solar + moon + outlook."""
    key = _key("forecast", date=date_str)
    if key not in _cache:
        try:
            d          = date.fromisoformat(date_str)
            # Hourly curves for all 5 spots
            hourly_curves = {}
            for spot_name, cfg in st.SPOT_CONFIG.items():
                try:
                    hourly_curves[spot_name] = st.fetch_tides_hourly(cfg["station_id"], d)
                except Exception:
                    hourly_curves[spot_name] = []
            # Legacy keys for backwards compat
            hereford   = hourly_curves.get("Hereford Inlet", [])
            cape_may   = hourly_curves.get("Cape May Ferry Terminal", [])
            all_spots  = st.fetch_all_spots_hilo(d)
            solunar    = st.get_solunar(d)
            conditions = st.fetch_marine_conditions(d)
            raw_solar  = st.get_solar(d)
            moon_phase, moon_pct = st.moon_phase_label(d)
            # Use midday wind (hour 12) as the representative wind for the outlook
            hourly     = conditions.get("hourly", [])
            noon_wind  = next((h for h in hourly if h["hour"] == 12), None)
            wind_mph   = noon_wind["wind_mph"] if noon_wind else None
            wind_deg   = noon_wind["wind_deg"] if noon_wind else None
            outlook    = st.get_day_fishing_outlook(d, conditions.get("water_temp_f"), wind_mph, wind_deg)
            _cache[key] = {
                "hereford":      hereford,
                "cape_may":      cape_may,
                "hourly_curves": hourly_curves,
                "all_spots":     all_spots,
                "solunar":    solunar,
                "conditions": conditions,
                "outlook":    outlook,
                "solar": {
                    "dawn":       raw_solar["dawn"].strftime("%H:%M"),
                    "sunrise":    raw_solar["sunrise"].strftime("%H:%M"),
                    "sunset":     raw_solar["sunset"].strftime("%H:%M"),
                    "dusk":       raw_solar["dusk"].strftime("%H:%M"),
                    "dawn_12":    raw_solar["dawn"].strftime("%-I:%M %p"),
                    "sunrise_12": raw_solar["sunrise"].strftime("%-I:%M %p"),
                    "sunset_12":  raw_solar["sunset"].strftime("%-I:%M %p"),
                    "dusk_12":    raw_solar["dusk"].strftime("%-I:%M %p"),
                },
                "moon": {"phase": moon_phase, "pct": moon_pct},
            }
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify(_cache[key])


@app.route("/api/journal/leaderboard")
def journal_leaderboard():
    """Top anglers this season by total fish caught."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT angler_name,
                   COUNT(*)        AS sessions,
                   SUM(fish_count) AS total_fish,
                   ROUND(AVG(bite_quality), 1) AS avg_bite,
                   MAX(fish_count) AS best_session
            FROM journal_entries
            GROUP BY angler_name
            ORDER BY total_fish DESC
            LIMIT 10
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/journal/stats")
def journal_stats():
    """Aggregate season stats."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COUNT(*)                   AS sessions,
                   COALESCE(SUM(fish_count),0) AS total_fish,
                   ROUND(AVG(bite_quality),1)  AS avg_bite,
                   MAX(fish_count)             AS best_haul,
                   COUNT(DISTINCT angler_name) AS anglers,
                   COUNT(DISTINCT spot)        AS spots_fished
            FROM journal_entries
        """).fetchone()
    return jsonify(dict(row))


@app.route("/api/export")
def api_export():
    days = int(request.args.get("days", 90))
    key  = _key("events", days=days)
    if key not in _cache:
        _cache[key] = st.get_events(days)
    ics_bytes = st.build_ics(_cache[key]["events"])
    return send_file(
        io.BytesIO(ics_bytes),
        mimetype="text/calendar",
        as_attachment=True,
        download_name="striper_tides.ics",
    )


# ── Journal API ────────────────────────────────────────────────────────────────

@app.route("/api/journal", methods=["GET"])
def journal_list():
    """Return recent journal entries, newest first."""
    limit  = int(request.args.get("limit", 30))
    spot   = request.args.get("spot")

    with get_conn() as conn:
        if spot:
            rows = conn.execute(
                "SELECT * FROM journal_entries WHERE spot=? ORDER BY session_date DESC, time_start DESC LIMIT ?",
                (spot, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM journal_entries ORDER BY session_date DESC, time_start DESC LIMIT ?",
                (limit,)
            ).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/api/journal", methods=["POST"])
def journal_post():
    """Save a new journal entry, auto-filling NOAA conditions."""
    data = request.get_json(force=True)

    required = ["angler_name", "spot", "session_date", "time_start",
                "time_end", "fish_count", "bite_quality"]
    for f in required:
        if f not in data or data[f] is None or str(data[f]).strip() == "":
            return jsonify({"error": f"Missing field: {f}"}), 400

    if data["spot"] not in SPOTS:
        return jsonify({"error": "Invalid spot"}), 400

    # ── Auto-fill NOAA conditions ──────────────────────────────────────────
    tide_type = tide_height = tidal_range = moon_phase = moon_pct_val = time_of_day_val = None
    try:
        d       = date.fromisoformat(data["session_date"])
        # Use the midpoint of the session for condition matching
        t_start = datetime.strptime(f"{data['session_date']} {data['time_start']}", "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
        t_end   = datetime.strptime(f"{data['session_date']} {data['time_end']}",   "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
        mid_dt  = t_start + (t_end - t_start) / 2

        # Get hilo data for this spot's station
        spot_info  = st.SPOT_STATIONS.get(data["spot"])
        station_id = spot_info["station_id"] if spot_info else st.CAPE_MAY_STATION
        hilo       = st.fetch_tides(station_id, d, d)

        # Determine tide state at session midpoint
        if hilo:
            hilo_sorted = sorted(hilo, key=lambda t: t["t"])
            # Find the nearest hilo event to mid session
            nearest = min(hilo_sorted, key=lambda t: abs(
                (datetime.strptime(t["t"], "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ) - mid_dt).total_seconds()
            ))
            tide_type   = "High" if nearest["type"] == "H" else "Low"
            tide_height = float(nearest["v"])

            # Range = max high - min low of the day
            highs = [float(t["v"]) for t in hilo if t["type"] == "H"]
            lows  = [float(t["v"]) for t in hilo if t["type"] == "L"]
            if highs and lows:
                tidal_range = round(max(highs) - min(lows), 2)

        solar         = st.get_solar(d)
        time_of_day_val = st.time_of_day(mid_dt, solar)
        moon_phase, moon_pct_val = st.moon_phase_label(d)

    except Exception:
        pass   # conditions are optional — don't block the save

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO journal_entries
               (angler_name, spot, session_date, time_start, time_end,
                fish_count, bite_quality, water_temp_f, notes,
                tide_type, tide_height_ft, tidal_range_ft,
                moon_phase, moon_pct, time_of_day)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["angler_name"].strip(),
                data["spot"],
                data["session_date"],
                data["time_start"],
                data["time_end"],
                int(data["fish_count"]),
                int(data["bite_quality"]),
                data.get("water_temp_f") or None,
                (data.get("notes") or "").strip() or None,
                tide_type, tide_height, tidal_range,
                moon_phase, moon_pct_val, time_of_day_val,
            ),
        )
        entry_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM journal_entries WHERE id=?", (entry_id,)
        ).fetchone()

    return jsonify(dict(row)), 201


@app.route("/api/journal/intel")
def journal_intel():
    """
    Return local intel scores per spot.
    Only spots with >= 20 entries get a score.
    Score = weighted avg of (fish_count * bite_quality) across entries.
    Returns upcoming calendar dates where conditions match top historical sessions.
    """
    MIN_ENTRIES = 20

    with get_conn() as conn:
        spots_data = {}
        for spot in SPOTS:
            rows = conn.execute(
                "SELECT * FROM journal_entries WHERE spot=?", (spot,)
            ).fetchall()
            entries = [dict(r) for r in rows]
            count   = len(entries)

            if count < MIN_ENTRIES:
                spots_data[spot] = {"count": count, "qualified": False, "min_entries": MIN_ENTRIES}
                continue

            # Find top sessions (bite_quality >= 4 = "red hot")
            top = [e for e in entries if e["bite_quality"] >= 4]
            avg_score = sum(e["fish_count"] * e["bite_quality"] for e in entries) / count

            # Condition fingerprints from top sessions
            top_conditions = {
                "moon_phases": list({e["moon_phase"] for e in top if e["moon_phase"]}),
                "time_of_day": list({e["time_of_day"] for e in top if e["time_of_day"]}),
                "avg_fish":    round(avg_score / 5, 1),
            }

            spots_data[spot] = {
                "count":      count,
                "qualified":  True,
                "avg_score":  round(avg_score, 1),
                "top_count":  len(top),
                "conditions": top_conditions,
            }

    return jsonify(spots_data)


# ── Surf Forecast API ────────────────────────────────────────────────────────

@app.route("/api/surf")
def api_surf():
    """Surf forecast for a given spot (48h history + 7d projection)."""
    spot  = request.args.get("spot", "Cape May")
    model = request.args.get("model", "gfs")
    if spot not in st.SURF_SPOTS:
        return jsonify({"error": f"Unknown spot: {spot}"}), 400
    if model not in ("gfs", "euro", "striper"):
        return jsonify({"error": f"Unknown model: {model}"}), 400
    key = _key("surf", spot=spot, model=model)
    if key not in _cache:
        try:
            _cache[key] = st.get_surf_forecast(spot, model)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify(_cache[key])


# ── Water Clarity API ─────────────────────────────────────────────────────────

@app.route("/api/clarity")
def api_clarity():
    """Cape May County water clarity forecast (72h)."""
    key = _key("clarity")
    if key not in _cache:
        try:
            _cache[key] = st.get_clarity_forecast()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify(_cache[key])


@app.route("/api/clarity/reports", methods=["GET"])
def clarity_reports_list():
    """Recent clarity reports from anglers."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clarity_reports ORDER BY report_date DESC, report_time DESC LIMIT 30"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/clarity/reports", methods=["POST"])
def clarity_report_post():
    """Submit a live water clarity report."""
    data = request.get_json(force=True)
    required = ["angler_name", "spot", "clarity"]
    for f in required:
        if f not in data or not str(data[f]).strip():
            return jsonify({"error": f"Missing: {f}"}), 400

    valid = [lvl["label"] for lvl in st.CLARITY_LEVELS]
    if data["clarity"] not in valid:
        return jsonify({"error": f"Invalid clarity: {data['clarity']}"}), 400

    # Use provided date/time or default to now
    now = datetime.now(ZoneInfo(st.TIMEZONE))
    report_date = data.get("report_date") or now.strftime("%Y-%m-%d")
    report_time = data.get("report_time") or now.strftime("%H:%M")

    # Snapshot current model prediction for calibration
    predicted = None
    try:
        key = _key("clarity")
        if key in _cache:
            predicted = _cache[key].get("current", {}).get("label")
    except Exception:
        pass

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO clarity_reports
               (angler_name, spot, report_date, report_time, clarity, notes, predicted)
               VALUES (?,?,?,?,?,?,?)""",
            (
                data["angler_name"].strip(),
                data["spot"],
                report_date,
                report_time,
                data["clarity"],
                (data.get("notes") or "").strip() or None,
                predicted,
            ),
        )
        row = conn.execute(
            "SELECT * FROM clarity_reports WHERE id=?", (cur.lastrowid,)
        ).fetchone()

    return jsonify(dict(row)), 201


if __name__ == "__main__":
    init_db()
    print("\n🎣  Striper Tides — http://localhost:5001\n")
    app.run(debug=True, host="0.0.0.0", port=5001, use_reloader=False)
