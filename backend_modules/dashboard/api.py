"""HTTP API for the existing KPI Dashboard workflow.

Uploads and their parsed rows are temporary. Only calculated snapshots are
kept in the configured snapshot store, which defaults to process memory.
"""

from __future__ import annotations

import io
import threading
import time
from collections import OrderedDict
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend_modules.dashboard import (
    dashboard_ai,
    kpi_engine,
    pptx_writer,
    report_deck,
    snapshot_store,
    sources,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

SOURCE_ORDER = ("ServiceNow", "Traackr", "Sprinklr")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PENDING_UPLOADS = 4
PENDING_SECONDS = 30 * 60

_pending: OrderedDict[str, tuple[float, sources.FileResult]] = OrderedDict()
_notes: dict[tuple[str, str, str], list[str]] = {}
_lock = threading.Lock()


class SaveRequest(BaseModel):
    upload_id: str
    period_start: date
    period_end: date
    generate_ai: bool = True


def clear_workspace() -> None:
    """Clear pending dashboard imports and all saved dashboard results."""
    with _lock:
        _pending.clear()
        _notes.clear()
        snapshot_store.clear()


def _cleanup_pending(now: float) -> None:
    """Called with _lock held."""
    expired = [key for key, (created, _) in _pending.items() if now - created > PENDING_SECONDS]
    for key in expired:
        _pending.pop(key, None)


def _period_snapshots(start: str, end: str) -> dict[str, dict]:
    rows = snapshot_store.list_snapshots(latest_only=True)
    return {
        row["source"]: row
        for row in rows
        if row["period_start"] == start and row["period_end"] == end
    }


def _check_period(start: date, end: date) -> None:
    problems = sources.validate_period(start, end)
    if problems:
        raise HTTPException(status_code=422, detail=problems)


def _write_insights(start: str, end: str) -> dict:
    snaps = _period_snapshots(start, end)
    if not snaps:
        raise HTTPException(status_code=404, detail="No snapshots saved for this period.")

    try:
        model_router = dashboard_ai.make_router()
        if model_router.settings.problems():
            return {"available": False, "entries": {}, "notes": ["No configured AI model is available."]}
        notes = {source: _notes.get((start, end, source), []) for source in snaps}
        payload = dashboard_ai.build_payload(snaps, notes)
        result = dashboard_ai.generate(payload, model_router, (start, end))
    except Exception as exc:  # AI is optional; KPI values remain available.
        return {"available": False, "entries": {}, "notes": [f"AI insights could not be generated: {exc}"]}

    if result.entries:
        snapshot_store.save_ai_insights(start, end, result.to_dict())
    return {"available": bool(result.entries), **result.to_dict()}


@router.post("/uploads/inspect")
def inspect_upload(file: UploadFile = File(...)) -> dict:
    """Recognise one Excel export and return its detected source and period."""
    name = file.filename or "upload"
    if not name.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raise HTTPException(status_code=415, detail="Upload an Excel export (.xlsx, .xlsm, or .xls).")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The upload exceeds the 20 MB POC limit.")
    result = sources.inspect_file(name, data)
    if not result.ok:
        raise HTTPException(status_code=422, detail=result.errors)

    upload_id = uuid4().hex
    with _lock:
        _cleanup_pending(time.monotonic())
        while len(_pending) >= MAX_PENDING_UPLOADS:
            _pending.popitem(last=False)
        _pending[upload_id] = (time.monotonic(), result)

    return {
        "upload_id": upload_id,
        "file_name": name,
        "source": result.source,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "period_note": result.period_note,
        "period_filters_rows": result.source in sources.DATE_FILTERS,
        "row_count": result.row_count,
        "sheets_used": result.table_sheets,
        "skipped_sheets": result.skipped_sheets,
        "warnings": result.warnings,
    }


@router.post("/snapshots", status_code=201)
def save_snapshot(request: SaveRequest) -> dict:
    """Calculate the uploaded export for the confirmed period and save it."""
    _check_period(request.period_start, request.period_end)
    with _lock:
        _cleanup_pending(time.monotonic())
        pending = _pending.get(request.upload_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Upload not found or expired. Upload the file again.")

    result = pending[1]
    calculated = kpi_engine.calculate_snapshot(result, request.period_start, request.period_end)
    if not calculated.ok or calculated.snapshot is None:
        raise HTTPException(status_code=422, detail=calculated.errors)

    start, end = str(request.period_start), str(request.period_end)
    snapshot_id = snapshot_store.save_snapshot(calculated.snapshot)
    with _lock:
        _pending.pop(request.upload_id, None)
    inside = sources.apply_period(result.source, result.tables, request.period_start, request.period_end)
    _notes[(start, end, result.source)] = dashboard_ai.summarise_tables(result.source, inside)
    snapshot_store.save_ai_insights(start, end, {})  # old text may describe replaced KPIs
    ai = _write_insights(start, end) if request.generate_ai else {"available": False, "entries": {}, "notes": []}
    return {
        "snapshot_id": snapshot_id,
        "snapshot": snapshot_store.get_snapshot(result.source, start, end),
        "warnings": calculated.warnings,
        "ai": ai,
    }


@router.get("/periods")
def list_periods() -> dict:
    """Periods offered by the dashboard, newest first."""
    by_period: dict[tuple[str, str], dict] = {}
    for snap in snapshot_store.list_snapshots(latest_only=True):
        key = (snap["period_start"], snap["period_end"])
        item = by_period.setdefault(key, {"period_start": key[0], "period_end": key[1], "sources": [], "last_updated": ""})
        item["sources"].append(snap["source"])
        item["last_updated"] = max(item["last_updated"], snap["saved_at"])
    periods = sorted(by_period.values(), key=lambda item: (item["period_start"], item["period_end"]), reverse=True)
    for item in periods:
        item["sources"].sort(key=SOURCE_ORDER.index)
    return {"periods": periods}


@router.get("/periods/{start}/{end}")
def get_period(start: date, end: date) -> dict:
    """Calculated KPI cards, breakdown data, ranked rows, and saved AI text."""
    _check_period(start, end)
    snapshots = _period_snapshots(str(start), str(end))
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots saved for this period.")
    return {
        "period_start": start,
        "period_end": end,
        "sources": {source: snapshots.get(source) for source in SOURCE_ORDER},
        "ai": snapshot_store.get_ai_insights(start, end) or {},
    }


@router.post("/periods/{start}/{end}/insights")
def regenerate_insights(start: date, end: date) -> dict:
    _check_period(start, end)
    return _write_insights(str(start), str(end))


@router.get("/periods/{start}/{end}/report")
def download_report(start: date, end: date) -> StreamingResponse:
    """Generate the same PowerPoint deck as the Streamlit dashboard."""
    _check_period(start, end)
    snapshots = _period_snapshots(str(start), str(end))
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots saved for this period.")
    items = [(source, snapshots[source], None) for source in SOURCE_ORDER if source in snapshots]
    saved_ai = snapshot_store.get_ai_insights(start, end)
    ai = dashboard_ai.AIResult.from_dict(saved_ai) if saved_ai else None
    try:
        deck = report_deck.build((str(start), str(end)), items, ai)
        content, _warnings = pptx_writer.build_deck(deck)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not build the report: {exc}") from exc
    filename = f"kpi_report_{start}_{end}.pptx"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
