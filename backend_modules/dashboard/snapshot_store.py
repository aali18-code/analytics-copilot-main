"""snapshot_store.py - save and load snapshots (plain Python, no Streamlit).

A snapshot is a saved record of CALCULATED results for one source and one period
(never raw rows). Snapshots are immutable: saving the same source and period again
creates a NEW version, and older versions are kept.

Backends (pick with the STORE_BACKEND environment variable):
  memory  (default) shared by every browser tab, lost when the server restarts
  sqlite  a local file (SNAPSHOT_DB, default "snapshots.db"), survives restarts
Later: a Supabase/Postgres backend can be added in this file only.
Note: a hosted app (e.g. Streamlit Cloud) wipes local files on redeploy, so SQLite
only persists when you run the app on your own machine.

The functions at the bottom are the interface the rest of the app uses.
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

from . import kpi_config

REQUIRED_KEYS = ("source", "period_start", "period_end", "kpis")
RETIRED_KPI_KEYS = {"sn_avg_duration", "sn_yearly_type_change"}
RETIRED_DASHBOARD_IDS = {"SN14"}


# ---- Small helpers -----------------------------------------------------------
def _iso(value) -> str:
    """Accept a date or an ISO string and return the ISO string."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _validate(snapshot: dict) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("A snapshot must be a dict.")
    missing = [k for k in REQUIRED_KEYS if k not in snapshot]
    if missing:
        raise ValueError(f"Snapshot is missing: {', '.join(missing)}.")
    if not snapshot["kpis"]:
        raise ValueError("Refusing to save a snapshot with no KPIs.")


def _stamp(snapshot: dict, version: int) -> dict:
    """Copy the snapshot and add id, version and saved_at (the original is never changed)."""
    row = copy.deepcopy(snapshot)
    row["period_start"] = _iso(row["period_start"])
    row["period_end"] = _iso(row["period_end"])
    row["version"] = version
    row["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row["id"] = f"{row['source']}|{row['period_start']}|{row['period_end']}|v{version}"
    return row


def _same_period(row: dict, source: str, start: str, end: str) -> bool:
    return row["source"] == source and row["period_start"] == start and row["period_end"] == end


def _latest_versions(rows: list[dict]) -> list[dict]:
    """Keep only the highest version of each source + period."""
    best: dict[tuple, dict] = {}
    for row in rows:
        key = (row["source"], row["period_start"], row["period_end"])
        if key not in best or row["version"] > best[key]["version"]:
            best[key] = row
    return list(best.values())


def _sort(rows: list[dict]) -> list[dict]:
    """Newest period first, then highest version."""
    return sorted(rows, key=lambda r: (r["period_start"], r["period_end"], r["version"]), reverse=True)


def _current_view(snapshot: dict | None) -> dict | None:
    """Present older snapshots in the current KPI order and hide retired entries."""
    if snapshot is None:
        return None
    snapshot = copy.deepcopy(snapshot)
    for key in RETIRED_KPI_KEYS:
        snapshot.get("kpis", {}).pop(key, None)
    if snapshot.get("source") == "ServiceNow":
        saved = snapshot.get("kpis", {})
        current = {}
        for kpi in kpi_config.kpis_for_source("ServiceNow"):
            if kpi.key not in saved:
                continue
            item = {**saved[kpi.key], "dashboard_id": kpi_config.dashboard_id(kpi.key),
                    "name": kpi.name, "unit": kpi.unit, "kind": kpi.kind,
                    "chart_type": kpi.chart_type, "columns": list(kpi.columns),
                    "additional": kpi.additional}
            if kpi.key == "sn_monthly_request_volume" and isinstance(item.get("value"), list):
                rows = item["value"]
                latest = max(rows, key=lambda row: row.get("Month", ""), default=None)
                item["value"] = int(latest["Requests"]) if latest else None
                item["display_value"] = (f"{item['value']:,} ({latest['Month']})"
                                         if latest else "n/a")
            if kpi.key == "sn_monthly_type_change" and isinstance(item.get("value"), list):
                item["value"] = [{name: value for name, value in row.items() if name != "Change (%)"}
                                 for row in item["value"]]
            current[kpi.key] = item
        snapshot["kpis"] = current
    snapshot["charts"] = [chart for chart in snapshot.get("charts", [])
                          if chart.get("kpi_key") not in RETIRED_KPI_KEYS]
    snapshot["skipped_kpis"] = [item for item in snapshot.get("skipped_kpis", [])
                                if item.get("key") not in RETIRED_KPI_KEYS]
    return snapshot


# ---- Memory backend ----------------------------------------------------------
class MemoryStore:
    """Lives in the server process: shared by all tabs, lost on restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()  # Streamlit runs each session in its own thread
        self._rows: list[dict] = []    # in the order they were saved
        self._ai: dict[tuple[str, str], dict] = {}  # (period_start, period_end) -> latest AI text

    def save(self, snapshot: dict) -> str:
        _validate(snapshot)
        start, end = _iso(snapshot["period_start"]), _iso(snapshot["period_end"])
        with self._lock:
            versions = [r["version"] for r in self._rows if _same_period(r, snapshot["source"], start, end)]
            row = _stamp(snapshot, max(versions, default=0) + 1)
            self._rows.append(row)
            return row["id"]

    def all(self, source: str | None = None) -> list[dict]:
        with self._lock:
            rows = [r for r in self._rows if source is None or r["source"] == source]
            return copy.deepcopy(rows)  # in save order; callers get copies

    def save_ai(self, start: str, end: str, data: dict) -> None:
        with self._lock:
            self._ai[(start, end)] = copy.deepcopy(data)

    def get_ai(self, start: str, end: str) -> dict | None:
        with self._lock:
            return copy.deepcopy(self._ai.get((start, end)))
        
    def change_token(self) -> str:
        with self._lock:
            return f"{len(self._rows)}:{self._rows[-1]['id'] if self._rows else ''}"

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()
            self._ai.clear()


# ---- SQLite backend ----------------------------------------------------------
class SqliteStore:
    """A local file: survives restarts. The snapshot is stored as JSON text."""

    def __init__(self, path: str = "snapshots.db") -> None:
        self._path = path
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshots ("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, source TEXT, "
                "period_start TEXT, period_end TEXT, version INTEGER, saved_at TEXT, data TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS ai_insights ("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, period_start TEXT, period_end TEXT, "
                "saved_at TEXT, data TEXT)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def save(self, snapshot: dict) -> str:
        _validate(snapshot)
        start, end = _iso(snapshot["period_start"]), _iso(snapshot["period_end"])
        with self._lock, self._connect() as db:
            current = db.execute(
                "SELECT MAX(version) FROM snapshots WHERE source=? AND period_start=? AND period_end=?",
                (snapshot["source"], start, end),
            ).fetchone()[0]
            row = _stamp(snapshot, (current or 0) + 1)
            db.execute(
                "INSERT INTO snapshots (id, source, period_start, period_end, version, saved_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["source"], start, end, row["version"], row["saved_at"], json.dumps(row)),
            )
            return row["id"]

    def all(self, source: str | None = None) -> list[dict]:
        query, args = "SELECT data FROM snapshots", ()
        if source is not None:
            query, args = query + " WHERE source=?", (source,)
        with self._lock, self._connect() as db:
            return [json.loads(text) for (text,) in db.execute(query + " ORDER BY seq", args)]
        
    def save_ai(self, start: str, end: str, data: dict) -> None:
        saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO ai_insights (period_start, period_end, saved_at, data) VALUES (?, ?, ?, ?)",
                (start, end, saved_at, json.dumps(data)),
            )

    def get_ai(self, start: str, end: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT data FROM ai_insights WHERE period_start=? AND period_end=? ORDER BY seq DESC LIMIT 1",
                (start, end),
            ).fetchone()
        return json.loads(row[0]) if row else None
    
    def change_token(self) -> str:
        with self._lock, self._connect() as db:
            count, last = db.execute("SELECT COUNT(*), COALESCE(MAX(seq), 0) FROM snapshots").fetchone()
            return f"{count}:{last}"

    def clear(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM snapshots")
            db.execute("DELETE FROM ai_insights")


# ---- Choosing the backend ----------------------------------------------------
_store = None
_store_lock = threading.Lock()


def get_store():
    """One shared store per server process, chosen by STORE_BACKEND (default: memory)."""
    global _store
    with _store_lock:
        if _store is None:
            backend = os.getenv("STORE_BACKEND", "memory").strip().lower()
            if backend == "sqlite":
                _store = SqliteStore(os.getenv("SNAPSHOT_DB", "snapshots.db"))
            else:  # "memory", or anything unknown
                _store = MemoryStore()
        return _store


# ---- The interface the rest of the app uses ------------------------------------
def save_snapshot(snapshot: dict) -> str:
    """Save a new snapshot (a new version if the source + period exist). Returns its id."""
    return get_store().save(snapshot)


def get_snapshot(source: str, period_start, period_end, version: int | None = None) -> dict | None:
    """One snapshot for a source + period. version=None means the highest version."""
    start, end = _iso(period_start), _iso(period_end)
    rows = [r for r in get_store().all(source) if _same_period(r, source, start, end)]
    if version is not None:
        rows = [r for r in rows if r["version"] == version]
    return _current_view(max(rows, key=lambda r: r["version"], default=None))


def list_snapshots(source: str | None = None, latest_only: bool = False) -> list[dict]:
    """Snapshots, newest period first. latest_only=True keeps only the top version per period."""
    rows = get_store().all(source)
    return [_current_view(row) for row in _sort(_latest_versions(rows) if latest_only else rows)]


def latest_snapshot(source: str) -> dict | None:
    """The most recently SAVED snapshot for a source (what the dashboard shows by default)."""
    rows = get_store().all(source)
    return _current_view(rows[-1]) if rows else None


def change_token() -> str:
    """Cheap value that changes whenever anything is saved. The dashboard polls this."""
    return get_store().change_token()


def clear() -> None:
    """Remove every saved KPI snapshot and its AI commentary."""
    get_store().clear()

def save_ai_insights(period_start, period_end, data: dict) -> None:
    """Save the AI text (AIResult.to_dict()) for one period. Saving again replaces what get returns."""
    get_store().save_ai(_iso(period_start), _iso(period_end), data)


def get_ai_insights(period_start, period_end) -> dict | None:
    """The latest saved AI text for a period, or None if there is none."""
    result = get_store().get_ai(_iso(period_start), _iso(period_end))
    if result and isinstance(result.get("entries"), dict):
        saved = [row for row in get_store().all("ServiceNow")
                 if _same_period(row, "ServiceNow", _iso(period_start), _iso(period_end))]
        previous = max(saved, key=lambda row: row["version"]) if saved else {}
        old_ids = {value.get("dashboard_id"): kpi_config.dashboard_id(key)
                   for key, value in previous.get("kpis", {}).items()
                   if key not in RETIRED_KPI_KEYS} if saved else {}
        stale_commentary = ({previous["kpis"][key].get("dashboard_id")
                             for key in ("sn_monthly_request_volume", "sn_monthly_type_change")
                             if key in previous.get("kpis", {})}
                            if previous.get("kpi_version") != kpi_config.KPI_VERSION else set())
        result["entries"] = {
            (old_ids.get(dash_id) if dash_id.startswith("SN") else dash_id): entry
            for dash_id, entry in result["entries"].items()
            if dash_id not in RETIRED_DASHBOARD_IDS
            and dash_id not in stale_commentary
            and (not dash_id.startswith("SN") or old_ids.get(dash_id))
        }
    return result
