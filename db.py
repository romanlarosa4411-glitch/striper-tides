"""
db.py — SQLite database setup for Striper Tides journal
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "striper_tides.db"

SPOTS = [
    # Ocean / Inlet
    "Corsons Inlet",
    "Townsends Inlet",
    "Hereford Inlet",
    "Cape May Inlet",
    "Cape May Point",
    # Back Bay
    "Grassy Sound",
    "Stone Harbor",
    "Avalon Back Bay",
    "Sea Isle Back Bay",
    "Townsends Back Bay",
    "Cape May Back Bay",
    "The Thorofare",
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                angler_name   TEXT    NOT NULL,
                spot          TEXT    NOT NULL,
                session_date  TEXT    NOT NULL,   -- YYYY-MM-DD
                time_start    TEXT    NOT NULL,   -- HH:MM
                time_end      TEXT    NOT NULL,   -- HH:MM
                fish_count    INTEGER NOT NULL DEFAULT 0,
                bite_quality  INTEGER NOT NULL DEFAULT 1,  -- 1 (slow) to 5 (red hot)
                water_temp_f  REAL,
                notes         TEXT,
                -- NOAA-derived conditions (auto-filled at log time)
                tide_type     TEXT,   -- 'Rising' | 'Falling' | 'High' | 'Low'
                tide_height_ft REAL,
                tidal_range_ft REAL,
                moon_phase    TEXT,
                moon_pct      INTEGER,
                time_of_day   TEXT,   -- 'dawn' | 'day' | 'dusk' | 'night'
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_entries_spot ON journal_entries(spot);
            CREATE INDEX IF NOT EXISTS idx_entries_date ON journal_entries(session_date);

            -- Water clarity ground-truth reports from anglers
            CREATE TABLE IF NOT EXISTS clarity_reports (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                angler_name   TEXT    NOT NULL,
                spot          TEXT    NOT NULL,
                report_date   TEXT    NOT NULL,   -- YYYY-MM-DD
                report_time   TEXT    NOT NULL,   -- HH:MM
                clarity       TEXT    NOT NULL,   -- Crystal|Clean|Stained|Muddy|Blown Out
                notes         TEXT,
                -- snapshot of model prediction at report time (for calibration)
                predicted     TEXT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_clarity_date ON clarity_reports(report_date);
        """)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
