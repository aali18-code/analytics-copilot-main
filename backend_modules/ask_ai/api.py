"""HTTP API for the existing spreadsheet chat engine."""

from __future__ import annotations

import base64
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from backend_modules.ask_ai import data_loader, engine, session_store

router = APIRouter(prefix="/api/ask-ai", tags=["ask-ai"])

MAX_FILES = 4
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
PREVIEW_ROWS = 100


@dataclass
class _Uploaded:
    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=3000)


def _session(session_id: str) -> session_store.Session:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired. Upload the files again.")
    return session


def _cell(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _cell(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_cell(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _cell(value.item())
        except (TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _records(frame: pd.DataFrame) -> list[dict]:
    return [{str(key): _cell(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _overview(session: session_store.Session) -> dict:
    return {
        "session_id": session.id,
        "tables": _records(data_loader.datasets_summary_frame(session.prepared.datasets)),
        "shared_columns": data_loader.find_shared_columns(session.prepared.datasets),
        "load_errors": session.load_errors,
        "ai_ready": bool(session.settings.usable_models()),
        "ai_setup_notes": session.settings.problems(),
    }


def _answer_display(answer_id: str, answer: engine.AnswerResult) -> dict:
    charts = []
    for chart in answer.plotly_figures:
        try:
            charts.append(json.loads(chart))
        except json.JSONDecodeError:
            continue
    return {
        "id": answer_id,
        "ok": answer.ok,
        "text": answer.text,
        "model": answer.model,
        "runs": answer.runs,
        "steps": answer.steps,
        "tables": [
            {"title": table.title, "columns": [str(column) for column in table.df.columns], "rows": _records(table.df), "total_rows": table.total_rows, "truncated": table.truncated}
            for table in answer.tables
        ],
        "plotly_figures": charts,
        "png_figures": [f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}" for png in answer.figures],
        "has_excel_download": bool(answer.tables),
    }


@router.post("/sessions", status_code=201)
def create_session(files: list[UploadFile] = File(...)) -> dict:
    """Read and clean uploaded CSV/Excel files, then keep the tables in memory."""
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Upload between 1 and {MAX_FILES} files.")
    uploaded = []
    total = 0
    for file in files:
        name = file.filename or "upload"
        if not name.lower().endswith((".csv", ".xlsx", ".xls")):
            raise HTTPException(status_code=415, detail=f"{name}: use CSV, XLSX, or XLS.")
        data = file.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"{name}: file exceeds the 20 MB POC limit.")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="The combined upload exceeds the 25 MB POC limit.")
        uploaded.append(_Uploaded(name, data))

    loaded = data_loader.load_uploaded_files(uploaded)
    if not loaded.datasets:
        raise HTTPException(status_code=422, detail=loaded.errors or ["No usable data tables were found."])
    settings = engine.Settings.from_env()
    prepared = engine.prepare_data(loaded.datasets, settings.sample_rows)
    session = session_store.create(prepared, settings, loaded.errors)
    return _overview(session)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    session = _session(session_id)
    with session.lock:
        return {**_overview(session), "messages": list(session.messages)}


@router.get("/sessions/{session_id}/tables/{alias}")
def get_table(session_id: str, alias: str) -> dict:
    """First 100 rows, column profile, and cleaning notes for one loaded table."""
    session = _session(session_id)
    with session.lock:
        dataset = next((item for item in session.prepared.datasets if item.alias == alias), None)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Table not found in this session.")
        return {
            "alias": dataset.alias,
            "name": dataset.key,
            "rows": _records(dataset.df.head(PREVIEW_ROWS)),
            "total_rows": len(dataset.df),
            "columns": _records(data_loader.column_profile_frame(dataset)),
            "cleaning_notes": dataset.notes,
            "quality_issues": data_loader.quality_issues(dataset),
        }


@router.post("/sessions/{session_id}/questions")
def ask_question(session_id: str, request: QuestionRequest) -> dict:
    session = _session(session_id)
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Type a question about your data.")
    with session.lock:
        try:
            answer = engine.answer_question(
                question, session.prepared, session.router, session.settings, history=session.history,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Analysis failed unexpectedly ({type(exc).__name__}).") from exc
        answer_id = uuid4().hex
        display = _answer_display(answer_id, answer)
        session.remember(question, answer, answer_id)
        return display


@router.post("/sessions/{session_id}/clear")
def clear_chat(session_id: str) -> dict:
    session = _session(session_id)
    with session.lock:
        session.history.clear()
        session.messages.clear()
        session.answers.clear()
    return {"messages": []}


@router.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: str) -> Response:
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return Response(status_code=204)


def _answer(session_id: str, answer_id: str) -> engine.AnswerResult:
    session = _session(session_id)
    with session.lock:
        answer = session.answers.get(answer_id)
        if answer is None:
            raise HTTPException(status_code=404, detail="Answer not found in this session.")
        return answer


@router.get("/sessions/{session_id}/answers/{answer_id}")
def get_answer(session_id: str, answer_id: str) -> dict:
    """Restore one answer's tables and charts without duplicating them in session messages."""
    return _answer_display(answer_id, _answer(session_id, answer_id))


def _sheet_name(title: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "", title).strip()[:28] or "Result"
    name, number = base, 2
    while name.lower() in used:
        name = f"{base[:28 - len(str(number)) - 1]}_{number}"
        number += 1
    used.add(name.lower())
    return name


@router.get("/sessions/{session_id}/answers/{answer_id}/tables.xlsx")
def download_tables(session_id: str, answer_id: str) -> Response:
    answer = _answer(session_id, answer_id)
    if not answer.tables:
        raise HTTPException(status_code=404, detail="This answer has no tables to download.")
    output = io.BytesIO()
    used: set[str] = set()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for table in answer.tables:
                table.df.to_excel(writer, sheet_name=_sheet_name(table.title, used), index=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create the Excel download ({type(exc).__name__}).") from exc
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="answer_{answer_id[:8]}.xlsx"'},
    )


@router.get("/sessions/{session_id}/answers/{answer_id}/charts/{index}.png")
def download_png(session_id: str, answer_id: str, index: int) -> Response:
    answer = _answer(session_id, answer_id)
    if not 0 <= index < len(answer.figures):
        raise HTTPException(status_code=404, detail="PNG chart not found in this answer.")
    return Response(
        content=answer.figures[index], media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="chart_{answer_id[:8]}_{index + 1}.png"'},
    )
