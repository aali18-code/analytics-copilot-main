"""Read-only Langfuse metrics for the LLM monitoring screen."""

from __future__ import annotations

import math
import os
import threading
import time
from typing import Literal

from fastapi import APIRouter, HTTPException

from backend_modules.llm_monitoring import observability

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

WINDOW_DAYS = {"7d": 7, "30d": 30, "all": None}
TABLE_ROWS = 200
CACHE_SECONDS = 15
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _number(value) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _display_name(step: str | None) -> str:
    if step in ("plan-code", "fix-code", "explain-result"):
        return "Ask AI"
    if step in ("plan-report", "write-report"):
        return "Report generation"
    if step == "dashboard-insights":
        return "Dashboard insights"
    return step or "Other AI call"


def _summarize(rows: list[dict], window: str) -> dict:
    costs = [_number(row.get("cost")) for row in rows]
    latencies = [_number(row.get("latency")) for row in rows]
    known_latencies = [value for value in latencies if value is not None]
    calls = []
    for row in rows[:TABLE_ROWS]:
        started = row.get("start_time")
        calls.append(
            {
                "name": _display_name(row.get("name")),
                "step": row.get("name"),
                "start_time": started.isoformat() if hasattr(started, "isoformat") else str(started or ""),
                "model": row.get("model") or "Unknown",
                "cost_usd": _number(row.get("cost")),
                "latency_seconds": _number(row.get("latency")),
                "input_tokens": int(_number(row.get("input_tokens")) or 0),
                "output_tokens": int(_number(row.get("output_tokens")) or 0),
                "total_tokens": int(_number(row.get("total_tokens")) or 0),
                "status": row.get("status") or "ok",
            }
        )
    return {
        "configured": True,
        "window": window,
        "display_timezone": os.getenv("INSIGHTS_TIMEZONE", "Asia/Kolkata"),
        "metrics": {
            "calls": len(rows),
            "total_tokens": sum(int(_number(row.get("total_tokens")) or 0) for row in rows),
            "total_cost_usd": sum(value for value in costs if value is not None),
            "average_latency_seconds": sum(known_latencies) / len(known_latencies) if known_latencies else None,
            "costed_calls": sum(value is not None for value in costs),
        },
        "calls": calls,
        "shown_calls": len(calls),
    }


@router.get("/calls")
def get_calls(window: Literal["7d", "30d", "all"] = "30d") -> dict:
    """All-window totals plus the latest 200 calls, refreshed at most every 15 seconds."""
    if not observability.enabled():
        return {
            "configured": False,
            "window": window,
            "display_timezone": os.getenv("INSIGHTS_TIMEZONE", "Asia/Kolkata"),
            "metrics": {"calls": 0, "total_tokens": 0, "total_cost_usd": 0, "average_latency_seconds": None, "costed_calls": 0},
            "calls": [],
            "shown_calls": 0,
        }

    with _cache_lock:
        cached = _cache.get(window)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            rows = observability.fetch_calls(days=WINDOW_DAYS[window])
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Could not read AI call metrics from Langfuse.") from exc
        result = _summarize(rows, window)
        _cache[window] = (time.monotonic(), result)
        return result
