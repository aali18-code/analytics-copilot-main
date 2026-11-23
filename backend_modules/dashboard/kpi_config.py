"""kpi_config.py - the KPI catalogue (plain Python, no Streamlit).

A KPI is a fixed calculation (one number, breakdown or ranked table), never an LLM result.
Formulas read COMMON column names. sources.py maps each file's real columns to them:

  ServiceNow  table "main"      Stage->state, SLA definition->sla_definition,
                                Business duration->business_duration, Created->created
  Sprinklr    table "organic"   Account Type->account_type, Total Engagements (SUM)->engagements
              table "paid"      Spent in USD (SUM)->spend
  Traackr     table "brands"    Keyword Group->brand, Posts->posts, Engagements->engagements,
                                Est Impressions->est_impressions, Video Views->video_views,
                                Potential Reach->potential_reach
              table "campaigns" Start Date->start_date, Total Spend->total_spend

STATUS: ServiceNow formulas are placeholders; Traackr and Sprinklr follow the ranked-table specification.
Change a formula here and bump the relevant source version so old snapshots stay traceable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import pandas as pd

KPI_VERSION = "1.0-servicenow-jun-jul-hours"
RANKED_TABLE_VERSION = "0.4-ranked-tables"


def version_for_source(source: str) -> str:
    return KPI_VERSION if source == "ServiceNow" else RANKED_TABLE_VERSION

# ---- Assumed values (confirm with the business) ------------------------------
# ServiceNow "Stage" values seen in the file: Completed, Cancelled, Paused, In progress
COMPLETED_STATES = {"completed", "complete", "closed complete"}
CANCELLED_STATES = {"cancelled", "canceled"}


@dataclass(frozen=True)
class KPI:
    key: str                       # stable id, used in snapshots
    name: str                      # label shown on the dashboard
    source: str                    # "ServiceNow" | "Sprinklr" | "Traackr"
    formula: Callable[..., Any]       # df -> calculated value; period-aware formulas also receive dates
    required_columns: tuple[str, ...]       # common column names it needs
    chart_type: str                # "card" | "bar" | "donut" | "line"
    unit: str                      # "count" | "%" | "currency" | "hours"
    kind: str = "single"           # "single" number or "breakdown" (dict by category)
    table: str = "main"            # which sheet/table it reads
    columns: tuple[str, ...] = ()    # displayed columns for a table KPI
    rank_by: str = ""               # ranking metric shown to the insight writer
    period_aware: bool = False       # formula reads unfiltered history and the selected period
    additional: bool = False         # shown after the original source KPIs
    display: Callable[[pd.DataFrame, Any], str] | None = None  # optional card text


# ---- Helpers -----------------------------------------------------------------
def _lower(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """Column as numbers. Also handles text like '$52.63' or '1,200'."""
    series = df[col]
    if not pd.api.types.is_numeric_dtype(series):  # text such as "$52.63"
        series = series.astype(str).str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(series, errors="coerce")


def _share(mask: pd.Series) -> float | None:
    """Percent of rows where mask is True. None if there are no rows."""
    return round(float(mask.mean()) * 100, 2) if len(mask) else None


def _by_category(df: pd.DataFrame, value_col: str, cat_col: str, top: int | None = None) -> dict[str, float]:
    grouped = _num(df, value_col).groupby(df[cat_col].astype(str)).sum().sort_values(ascending=False)
    if top:
        grouped = grouped.head(top)
    return {str(k): float(v) for k, v in grouped.items()}


# ---- ServiceNow formulas -------------------------------------------------------
def total_tasks(df: pd.DataFrame) -> int:
    return int(len(df))


def completion_rate(df: pd.DataFrame) -> float | None:
    return _share(_lower(df["state"]).isin(COMPLETED_STATES))


def cancelled_tasks(df: pd.DataFrame) -> int:
    return int(_lower(df["state"]).isin(CANCELLED_STATES).sum())


def tasks_by_sla(df: pd.DataFrame) -> dict[str, int]:
    counts = df["sla_definition"].astype(str).value_counts()
    return {str(k): int(v) for k, v in counts.items()}


def avg_business_duration(df: pd.DataFrame) -> float | None:
    """Average business duration in HOURS. The ServiceNow column is in seconds, so divide by 3600."""
    mean = _num(df, "business_duration").mean() / 3600
    return round(float(mean), 2) if pd.notna(mean) else None

def _clean_labels(series: pd.Series) -> pd.Series:
    """Text labels without hidden zero-width or non-breaking spaces; blanks become '(blank)'."""
    return series.fillna("(blank)").astype(str).str.replace("[\u200b\u00a0]", " ", regex=True).str.strip()


def _count_by(df: pd.DataFrame, col: str) -> dict[str, int]:
    return {str(k): int(v) for k, v in _clean_labels(df[col]).value_counts().items()}


def tasks_by_request_type(df: pd.DataFrame) -> dict[str, int]:
    return _count_by(df, "request_type")


def avg_hours_by_request_type(df: pd.DataFrame) -> dict[str, float]:
    hours = _num(df, "business_duration") / 3600  # file value is in seconds
    means = hours.groupby(_clean_labels(df["request_type"])).mean().dropna().sort_values(ascending=False)
    return {str(k): round(float(v), 2) for k, v in means.items()}


def tasks_by_region(df: pd.DataFrame) -> dict[str, int]:
    return _count_by(df, "region")


def tasks_by_country(df: pd.DataFrame) -> dict[str, int]:
    return _count_by(df, "country")


def tasks_by_priority(df: pd.DataFrame) -> dict[str, int]:
    return _count_by(df, "priority")


def _latest_request_month(df: pd.DataFrame) -> tuple[str, int] | None:
    months = pd.to_datetime(df["opened"], errors="coerce").dt.to_period("M")
    counts = months.dropna().value_counts().sort_index()
    if counts.empty:
        return None
    return str(counts.index[-1]), int(counts.iloc[-1])


def monthly_request_volume(df: pd.DataFrame) -> int | None:
    """Count requests in the latest Opened month within the selected period."""
    latest = _latest_request_month(df)
    return latest[1] if latest else None


def monthly_volume_display(df: pd.DataFrame, value: int | None) -> str:
    latest = _latest_request_month(df)
    return f"{value:,} ({latest[0]})" if latest and value is not None else "n/a"


def avg_duration_all_request_types(df: pd.DataFrame) -> float | None:
    """Overall mean from Sheet1, where Business duration is stored in seconds."""
    return avg_business_duration(df)


def _request_type_monthly_counts(df: pd.DataFrame, start: date, end: date) -> list[dict]:
    """Show current and previous request counts by type for the latest complete month."""
    created = pd.to_datetime(df["created"], errors="coerce")
    selected = created.between(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1), inclusive="left")
    if not selected.any():
        return []
    candidate_months = sorted(created[selected].dt.to_period("M").dropna().unique(), reverse=True)
    current_month = next((month for month in candidate_months
                          if month.start_time.date() >= start and month.end_time.date() <= end), None)
    if current_month is None:
        return []
    previous_month = current_month - 1
    types = _clean_labels(df["request_type"])
    months = created.dt.to_period("M")
    current = types[months == current_month].value_counts()
    previous = types[months == previous_month].value_counts()
    previous_present = bool((months == previous_month).any())
    names = sorted(set(current.index) | set(previous.index), key=lambda name: (-int(current.get(name, 0)), str(name)))
    rows = []
    for name in names:
        now = int(current.get(name, 0))
        before = int(previous.get(name, 0)) if previous_present else None
        rows.append({"Request type": str(name), "Current month": str(current_month),
                     "Current requests": now, "Previous month": before})
    return rows


def monthly_request_type_change(df: pd.DataFrame, start: date, end: date) -> list[dict]:
    return _request_type_monthly_counts(df, start, end)


def june_july_average_hours_by_type(df: pd.DataFrame, _start: date, _end: date) -> dict | None:
    """For each Short Description, sum In hours and divide by its row count in each month."""
    created_month = pd.to_datetime(df["created"], errors="coerce").dt.to_period("M")
    request_type = _clean_labels(df["request_type"])
    hours = _num(df, "in_hours")
    months = []
    totals: dict[str, int] = {}
    for period, label in ((pd.Period("2026-06"), "June 2026"),
                          (pd.Period("2026-07"), "July 2026")):
        selected = created_month == period
        if not selected.any():
            return None
        rows = pd.DataFrame({"request_type": request_type[selected], "hours": hours[selected]})
        counts = rows["request_type"].value_counts()
        sums = rows.groupby("request_type")["hours"].sum()
        for name, count in counts.items():
            totals[str(name)] = totals.get(str(name), 0) + int(count)
        months.append({"month": str(period), "label": label, "total_requests": int(selected.sum()),
                       "counts": counts.to_dict(), "sums": sums.to_dict()})
    labels = sorted(totals, key=lambda name: (-totals[name], name))
    for month in months:
        month["rows"] = [
            {"request_type": name, "count": int(month["counts"].get(name, 0)),
             "sum_hours": round(float(month["sums"].get(name, 0)), 2),
             "average_hours": (round(float(month["sums"][name]) / int(month["counts"][name]), 2)
                               if month["counts"].get(name, 0) else None)}
            for name in labels
        ]
        del month["counts"], month["sums"]
    return {"labels": labels, "months": months}


# ---- Sprinklr formulas -------------------------------------------------------
def _display(value: Any) -> Any:
    """Preserve Excel text, dates and numbers in a JSON-safe table cell."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, str):
        return value.strip()
    if hasattr(value, "item"):
        return value.item()
    return value


def _percent(value: Any, *, already_percent: bool = False) -> str | None:
    """Traackr ratios may be fractions; Sprinklr's 'in %' values are percentage points."""
    if pd.isna(value) or str(value).strip() == "":
        return None
    raw = str(value).strip()
    number = pd.to_numeric(raw.replace(",", "").replace("%", ""), errors="coerce")
    if pd.isna(number):
        return raw
    if "%" not in raw and not already_percent and abs(number) <= 1:
        number *= 100
    return f"{number:,.2f}%"


def _ranked(df: pd.DataFrame, label: str, metric: str, limit: int) -> pd.DataFrame:
    ranked = df.copy()
    ranked["_label"] = ranked[label].fillna("").astype(str).str.strip()
    ranked["_rank"] = _num(ranked, metric)
    ranked = ranked[(ranked["_label"] != "") &
                    ~ranked["_label"].str.casefold().isin(("total", "grand total")) &
                    ranked["_rank"].notna()]
    ranked = ranked.sort_values("_rank", ascending=False, kind="stable")
    ranked["_unique_label"] = ranked["_label"].str.casefold()
    return ranked.drop_duplicates("_unique_label", keep="first").head(limit)


CAMPAIGN_COLUMNS = ("Name", "Start Date", "End Date", "Engagement Rate", "Creators", "Posts", "VIT", "Brand")
BRAND_COLUMNS = ("Brand", "VIT", "VIT Rate", "Engagement Rate", "Engagements", "Video Views", "VVR")
MOM_COLUMNS = ("Request type", "Current month", "Current requests", "Previous month")
PAID_COLUMNS = ("Ad Account", "Engagement Rate in %", "Engagements (SUM)", "Impressions (SUM)",
                "Cost Per 1,000 Impressions (CPM) in USD (SUM)", "Partnership Ad?")
ORGANIC_COLUMNS = ("Outbound Post", "Account", "Engagement Rate in %", "Post Reach (SUM)", "Total Engagements (SUM)")


def top_paid_posts(df: pd.DataFrame) -> list[dict]:
    return [{"Ad Account": _display(row.ad_variant),
             "Engagement Rate in %": _percent(row.engagement_rate, already_percent=True),
             "Engagements (SUM)": _display(row.engagements),
             "Impressions (SUM)": _display(row.impressions),
             "Cost Per 1,000 Impressions (CPM) in USD (SUM)": _display(row.cpm),
             "Partnership Ad?": _display(row.partnership_ad)}
            for row in _ranked(df, "ad_variant", "engagement_rate", 3).itertuples()]


def top_organic_posts(df: pd.DataFrame) -> list[dict]:
    return [{"Outbound Post": _display(row.outbound_post), "Account": _display(row.account),
             "Engagement Rate in %": _percent(row.engagement_rate, already_percent=True),
             "Post Reach (SUM)": _display(row.reach),
             "Total Engagements (SUM)": _display(row.engagements)}
            for row in _ranked(df, "outbound_post", "reach", 3).itertuples()]


def top_campaigns(df: pd.DataFrame) -> list[dict]:
    return [{"Name": _display(row.campaign_name), "Start Date": _display(row.start_date),
             "End Date": _display(row.end_date), "Engagement Rate": _percent(row.engagement_rate),
             "Creators": _display(row.creators), "Posts": _display(row.posts),
             "VIT": _display(row.vit), "Brand": _display(row.brand)}
            for row in _ranked(df, "campaign_name", "posts", 3).itertuples()]


def _brand_rows(df: pd.DataFrame, limit: int, names: tuple[str, ...] = ()) -> list[dict]:
    ranked = _ranked(df, "brand", "vit_score", len(df))
    if names:
        lookup = {name.casefold(): index for index, name in enumerate(names)}
        ranked = ranked[ranked["_label"].str.casefold().isin(lookup)].copy()
        ranked["_order"] = ranked["_label"].str.casefold().map(lookup)
        ranked = ranked.sort_values("_order", kind="stable")
    return [{"Brand": _display(row.brand), "VIT": _display(row.vit_score),
             "VIT Rate": _percent(row.vit_rate), "Engagement Rate": _percent(row.engagement_rate),
             "Engagements": _display(row.engagements), "Video Views": _display(row.video_views),
             "VVR": _percent(row.video_view_rate)}
            for row in ranked.head(limit).itertuples()]


def top_diageo_brands(df: pd.DataFrame) -> list[dict]:
    return _brand_rows(df, 4)


def top_market_brands(df: pd.DataFrame) -> list[dict]:
    return _brand_rows(df, 10)


def rum_global(df: pd.DataFrame) -> list[dict]:
    return _brand_rows(df, 3, ("Bacardi", "Captain Morgan", "Malibu"))


def total_engagements(df: pd.DataFrame) -> float:
    return float(_num(df, "engagements").sum())


def engagements_by_account_type(df: pd.DataFrame) -> dict[str, float]:
    return _by_category(df, "engagements", "account_type")

def paid_engagements(df: pd.DataFrame) -> float:
    return float(_num(df, "engagements").sum())


def paid_impressions(df: pd.DataFrame) -> float:
    return float(_num(df, "impressions").sum())


def paid_cpm(df: pd.DataFrame) -> float | None:
    """Cost per 1,000 impressions = spend / impressions x 1000 (worked out from the totals, not summed)."""
    impressions = _num(df, "impressions").sum()
    return round(float(_num(df, "spend").sum()) / impressions * 1000, 2) if impressions else None
def total_ad_spend(df: pd.DataFrame) -> float:
    return float(_num(df, "spend").sum())


# ---- Traackr formulas ----------------------------------------------------------
def tr_total_posts(df: pd.DataFrame) -> float:
    return float(_num(df, "posts").sum())


def tr_total_engagements(df: pd.DataFrame) -> float:
    return float(_num(df, "engagements").sum())


def tr_total_impressions(df: pd.DataFrame) -> float:
    return float(_num(df, "est_impressions").sum())


def tr_total_video_views(df: pd.DataFrame) -> float:
    return float(_num(df, "video_views").sum())


def tr_engagement_rate(df: pd.DataFrame) -> float | None:
    # Same definition as the Traackr file: engagements / potential reach, as a percent.
    reach = _num(df, "potential_reach").sum()
    return round(float(_num(df, "engagements").sum()) / reach * 100, 3) if reach else None
def tr_vit_score(df: pd.DataFrame) -> float:
    return round(float(_num(df, "vit_score").sum()), 2)


def tr_visibility(df: pd.DataFrame) -> float:
    return round(float(_num(df, "visibility").sum()), 2)


def tr_impact(df: pd.DataFrame) -> float:
    return round(float(_num(df, "impact").sum()), 2)


def tr_trust(df: pd.DataFrame) -> float:
    return round(float(_num(df, "trust").sum()), 3)

def tr_engagements_by_brand(df: pd.DataFrame) -> dict[str, float]:
    return _by_category(df, "engagements", "brand", top=10)


def tr_campaign_count(df: pd.DataFrame) -> int:
    return int(len(df))


def tr_campaign_spend(df: pd.DataFrame) -> float:
    # Note: in the sample file only 3 of 18 campaigns had a spend value.
    return float(_num(df, "total_spend").sum())


# ---- The catalogue ---------------------------------------------------------------
KPIS: list[KPI] = [
    # ServiceNow
    KPI("sn_total_tasks", "Total tasks", "ServiceNow", total_tasks, ("state",), "card", "count"),
    KPI("sn_completion_rate", "Completion rate", "ServiceNow", completion_rate, ("state",), "card", "%"),
    KPI("sn_cancelled_tasks", "Cancelled tasks", "ServiceNow", cancelled_tasks, ("state",), "card", "count"),
    KPI("sn_tasks_by_sla", "Tasks by SLA type", "ServiceNow", tasks_by_sla,
        ("sla_definition",), "bar", "count", kind="breakdown"),
    KPI("sn_tasks_by_request_type", "Tasks by request type", "ServiceNow", tasks_by_request_type,
        ("request_type",), "bar", "count", kind="breakdown", table="requests"),
    KPI("sn_tasks_by_region", "Tasks by region", "ServiceNow", tasks_by_region,
        ("region",), "bar", "count", kind="breakdown", table="request_detail"),
    KPI("sn_tasks_by_country", "Tasks by country", "ServiceNow", tasks_by_country,
        ("country",), "bar", "count", kind="breakdown", table="request_detail"),
    KPI("sn_tasks_by_priority", "Tasks by priority", "ServiceNow", tasks_by_priority,
        ("priority",), "bar", "count", kind="breakdown", table="request_detail"),    
    KPI("sn_monthly_request_volume", "Monthly request volume (July tab)", "ServiceNow", monthly_request_volume,
        ("opened",), "card", "count", table="request_detail",
        additional=True, display=monthly_volume_display),
    KPI("sn_avg_duration_all_types", "Average business duration, all request types", "ServiceNow", avg_duration_all_request_types,
        ("business_duration",), "card", "hours", table="requests", additional=True),
    KPI("sn_hours_by_request_type", "Avg hours by request type", "ServiceNow", avg_hours_by_request_type,
        ("request_type", "business_duration"), "bar", "hours", kind="breakdown", table="requests", additional=True),
    KPI("sn_monthly_type_change", "Monthly request volumes by type", "ServiceNow", monthly_request_type_change,
        ("request_type", "created"), "table", "count", kind="table", table="requests",
        columns=MOM_COLUMNS, period_aware=True, additional=True),
    KPI("sn_june_july_avg_hours_by_type", "Average hours by request type: June vs July 2026", "ServiceNow",
        june_july_average_hours_by_type, ("request_type", "in_hours", "created"), "bar", "hours",
        kind="paired_bars", table="requests", period_aware=True, additional=True),
    # Traackr: each KPI is a ranked table, in dashboard order.
    KPI("tr_cross_campaign", "Cross-Campaign Performance Analysis", "Traackr", top_campaigns,
        ("campaign_name", "start_date", "end_date", "engagement_rate", "creators", "posts", "vit", "brand"),
        "table", "", kind="table", table="campaigns", columns=CAMPAIGN_COLUMNS, rank_by="Posts"),
    KPI("tr_top_diageo_brands", "Top Diageo Brands", "Traackr", top_diageo_brands,
        ("brand", "vit_score", "vit_rate", "engagement_rate", "engagements", "video_views", "video_view_rate"),
        "table", "", kind="table", table="brands", columns=BRAND_COLUMNS, rank_by="VIT"),
    KPI("tr_top_market_brands", "Top Brands Across All Markets", "Traackr", top_market_brands,
        ("brand", "vit_score", "vit_rate", "engagement_rate", "engagements", "video_views", "video_view_rate"),
        "table", "", kind="table", table="all_markets", columns=BRAND_COLUMNS, rank_by="VIT"),
    KPI("tr_rum_global", "Rum Global Dashboard", "Traackr", rum_global,
        ("brand", "vit_score", "vit_rate", "engagement_rate", "engagements", "video_views", "video_view_rate"),
        "table", "", kind="table", table="all_markets", columns=BRAND_COLUMNS),
    # Sprinklr
    KPI("sp_top_paid_posts", "Top Paid Posts", "Sprinklr", top_paid_posts,
        ("ad_variant", "engagement_rate", "engagements", "impressions", "cpm", "partnership_ad"),
        "table", "", kind="table", table="paid", columns=PAID_COLUMNS, rank_by="Engagement Rate in %"),
    KPI("sp_top_organic_posts", "Top Non-Paid Posts", "Sprinklr", top_organic_posts,
        ("outbound_post", "account", "engagement_rate", "reach", "engagements"),
        "table", "", kind="table", table="organic", columns=ORGANIC_COLUMNS, rank_by="Post Reach (SUM)"),
]
# ---- Dashboard IDs ---------------------------------------------------------------
# The LLM is given these IDs and returns its insight and recommendation under them.
DASHBOARD_IDS: dict[str, str] = {
    # ServiceNow
    "sn_total_tasks": "SN1",
    "sn_completion_rate": "SN2",
    "sn_cancelled_tasks": "SN3",
    "sn_tasks_by_sla": "SN4",
    "sn_tasks_by_request_type": "SN5",
    "sn_tasks_by_region": "SN6",
    "sn_tasks_by_country": "SN7",
    "sn_tasks_by_priority": "SN8",
    "sn_monthly_request_volume": "SN9",
    "sn_avg_duration_all_types": "SN10",
    "sn_hours_by_request_type": "SN11",
    "sn_monthly_type_change": "SN12",
    "sn_june_july_avg_hours_by_type": "SN13",
    # Traackr
    "tr_cross_campaign": "TC1",
    "tr_top_diageo_brands": "TC2",
    "tr_top_market_brands": "TC3",
    "tr_rum_global": "TC4",
    # Sprinklr
    "sp_top_paid_posts": "SP1",
    "sp_top_organic_posts": "SP2",
}


def dashboard_id(kpi_key: str) -> str | None:
    """The dashboard ID (SN1, TC1, SP1...) of a KPI, or None if it has none."""
    return DASHBOARD_IDS.get(kpi_key)

# ---- Lookups used by kpi_engine.py ------------------------------------------------
def kpis_for_source(source: str) -> list[KPI]:
    """All KPIs defined for a source."""
    return [k for k in KPIS if k.source == source]


def split_by_columns(source: str, columns_by_table: dict[str, list[str]]) -> tuple[list[KPI], list[KPI]]:
    """Return (runnable, skipped). A KPI is skipped if its table or a needed column is missing.

    columns_by_table example: {"main": ["state", "created", ...]}
    """
    runnable, skipped = [], []
    for kpi in kpis_for_source(source):
        have = set(columns_by_table.get(kpi.table, []))
        (runnable if set(kpi.required_columns) <= have else skipped).append(kpi)
    return runnable, skipped
