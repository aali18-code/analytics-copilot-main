"""Check added ServiceNow measures against a multi-period synthetic workbook."""

from __future__ import annotations

import io
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from backend_modules.dashboard import dashboard_pptx_writer, kpi_engine, report_deck, snapshot_store, sources


def _workbook() -> bytes:
    raw = pd.DataFrame({
        "Number": ["R1", "R2"],
        "SLA definition": ["Standard", "Standard"],
        "Stage": ["Completed", "Completed"],
        "Business duration": [3600, 7200],
        "Created": ["2026-07-03", "2026-08-02"],
    })
    requests = pd.DataFrame({
        "Number": ["H1", "H2", "J1", "J2", "C1", "C2", "C3", "A1"],
        "Short Description": ["Access", "Access", "Access", "Content", "Access", "Access", "Content", "Access"],
        "Business duration": [3600, 3600, 7200, 0, 3600, 7200, 3600, 1800],
        "In hours": [1, 1, 2, 0, 1, 2, 1, 0.5],
        "Created": ["2025-07-02", "2025-12-15", "2026-06-10", "2026-06-11", "2026-07-03",
                    "2026-07-07", "2026-07-10", "2026-08-02"],
    })
    july = pd.DataFrame({
        "Number": ["C1", "C2"],
        "Priority": ["Low", "High"],
        "Region": ["Europe", "Europe"],
        "Country": ["UK", "UK"],
        "Opened": ["2026-07-03", "2026-07-07"],
    })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        raw.to_excel(writer, sheet_name="Raw Data", index=False)
        requests.to_excel(writer, sheet_name="Sheet1", index=False)
        july.to_excel(writer, sheet_name="July", index=False)
    return output.getvalue()


class ServiceNowAdditionalKpisTest(unittest.TestCase):
    def test_original_and_additional_metrics(self) -> None:
        uploaded = sources.inspect_file("ServiceNow2.xlsx", _workbook())
        self.assertTrue(uploaded.ok, uploaded.errors)
        result = kpi_engine.calculate_snapshot(uploaded, date(2026, 7, 1), date(2026, 7, 31))
        self.assertTrue(result.ok, result.errors)
        kpis = result.snapshot["kpis"]

        self.assertEqual(len(kpis), 13)
        self.assertNotIn("sn_avg_duration", kpis)
        self.assertEqual(kpis["sn_tasks_by_region"]["dashboard_id"], "SN6")
        self.assertEqual(kpis["sn_tasks_by_region"]["value"], {"Europe": 2})
        self.assertEqual(kpis["sn_monthly_request_volume"]["value"], 2)
        self.assertEqual(kpis["sn_monthly_request_volume"]["display_value"], "2 (2026-07)")
        self.assertEqual(kpis["sn_monthly_request_volume"]["kind"], "single")
        self.assertEqual(kpis["sn_monthly_request_volume"]["dashboard_id"], "SN9")
        self.assertEqual(kpis["sn_avg_duration_all_types"]["value"], 1.33)
        self.assertEqual(kpis["sn_avg_duration_all_types"]["dashboard_id"], "SN10")
        self.assertEqual(kpis["sn_hours_by_request_type"]["dashboard_id"], "SN11")
        self.assertTrue(kpis["sn_hours_by_request_type"]["additional"])
        self.assertEqual(kpis["sn_hours_by_request_type"]["value"], {"Access": 1.5, "Content": 1.0})
        self.assertEqual([value["dashboard_id"] for value in kpis.values()], [f"SN{i}" for i in range(1, 14)])

        paired = kpis["sn_june_july_avg_hours_by_type"]
        self.assertEqual(paired["dashboard_id"], "SN13")
        self.assertEqual(paired["value"]["labels"], ["Access", "Content"])
        june, july = paired["value"]["months"]
        self.assertEqual(june["total_requests"], 2)
        self.assertEqual(june["rows"][0], {"request_type": "Access", "count": 1,
                                           "sum_hours": 2.0, "average_hours": 2.0})
        self.assertEqual(july["rows"][0], {"request_type": "Access", "count": 2,
                                           "sum_hours": 3.0, "average_hours": 1.5})
        paired_charts = [chart for chart in result.snapshot["charts"]
                         if chart.get("parent_kpi_key") == "sn_june_july_avg_hours_by_type"]
        self.assertEqual(len(paired_charts), 2)
        self.assertTrue(all(chart["multicolor"] for chart in paired_charts))

        mom = {row["Request type"]: row for row in kpis["sn_monthly_type_change"]["value"]}
        self.assertEqual(mom["Access"]["Previous month"], 1)
        self.assertEqual(mom["Access"]["Current requests"], 2)
        self.assertNotIn("Change (%)", mom["Access"])
        self.assertNotIn("Change (%)", kpis["sn_monthly_type_change"]["columns"])

        deck = report_deck.build(("2026-07-01", "2026-07-31"), [("ServiceNow", result.snapshot, None)])
        self.assertTrue(any("SN12" in slide["title"] for slide in deck["slides"]))
        self.assertFalse(any("SN13" in slide["title"] for slide in deck["slides"]))
        self.assertTrue(any(card["value"] == "2 (2026-07)" for slide in deck["slides"]
                            for card in slide.get("cards", [])))
        self.assertEqual(len([slide for slide in deck["slides"]
                              if slide.get("kpi_key", "").startswith("sn_june_july_avg_hours_by_type_")]), 2)
        presentation, warnings = dashboard_pptx_writer.build_deck(deck)
        self.assertTrue(presentation.startswith(b"PK"), warnings)

    def test_comparison_uses_latest_month_within_selected_period(self) -> None:
        uploaded = sources.inspect_file("ServiceNow2.xlsx", _workbook())
        result = kpi_engine.calculate_snapshot(uploaded, date(2026, 7, 1), date(2026, 8, 31))
        self.assertTrue(result.ok, result.errors)
        mom = result.snapshot["kpis"]["sn_monthly_type_change"]["value"]
        access = next(row for row in mom if row["Request type"] == "Access")
        self.assertEqual(access["Current month"], "2026-08")
        self.assertEqual(access["Current requests"], 1)
        self.assertEqual(access["Previous month"], 2)
        self.assertNotIn("Change (%)", access)
        self.assertNotIn("sn_yearly_type_change", result.snapshot["kpis"])

        partial = kpi_engine.calculate_snapshot(uploaded, date(2026, 7, 15), date(2026, 8, 15))
        self.assertTrue(partial.ok, partial.errors)
        self.assertNotIn("sn_monthly_type_change", partial.snapshot["kpis"])
        self.assertNotIn("sn_yearly_type_change", partial.snapshot["kpis"])

    def test_retired_metric_is_hidden_in_older_saved_snapshots(self) -> None:
        with patch.object(snapshot_store, "_store", snapshot_store.MemoryStore()):
            snapshot_store.save_snapshot({
                "source": "ServiceNow", "period_start": "2026-07-01", "period_end": "2026-07-31",
                "kpi_version": "0.7-servicenow-no-sn14",
                "kpis": {"sn_total_tasks": {"value": 2},
                         "sn_avg_duration": {"value": 3, "dashboard_id": "SN5"},
                         "sn_hours_by_request_type": {"value": {"Access": 1}, "dashboard_id": "SN7"},
                         "sn_tasks_by_region": {"value": {"Europe": 2}, "dashboard_id": "SN8"},
                         "sn_monthly_request_volume": {"value": [{"Month": "2026-07", "Requests": 2}],
                                                       "dashboard_id": "SN11"},
                         "sn_avg_duration_all_types": {"value": 1, "dashboard_id": "SN12"},
                         "sn_monthly_type_change": {"value": [{"Request type": "Access", "Change (%)": "n/a"}],
                                                    "dashboard_id": "SN13"},
                         "sn_yearly_type_change": {"value": []}},
            })
            snapshot_store.save_ai_insights("2026-07-01", "2026-07-31", {
                "entries": {"SN1": {"insight": "kept"}, "SN5": {"insight": "retired duration"},
                            "SN7": {"insight": "grouped"}, "SN8": {"insight": "region"},
                            "SN11": {"insight": "monthly"}, "SN12": {"insight": "overall"},
                            "SN13": {"insight": "by type"},
                            "SN14": {"insight": "retired"}},
            })
            saved = snapshot_store.get_snapshot("ServiceNow", "2026-07-01", "2026-07-31")
            self.assertNotIn("sn_avg_duration", saved["kpis"])
            self.assertNotIn("sn_yearly_type_change", saved["kpis"])
            self.assertEqual(saved["kpis"]["sn_tasks_by_region"]["dashboard_id"], "SN6")
            self.assertEqual(saved["kpis"]["sn_monthly_request_volume"]["dashboard_id"], "SN9")
            self.assertEqual(saved["kpis"]["sn_monthly_request_volume"]["value"], 2)
            self.assertEqual(saved["kpis"]["sn_monthly_request_volume"]["display_value"], "2 (2026-07)")
            self.assertEqual(saved["kpis"]["sn_avg_duration_all_types"]["dashboard_id"], "SN10")
            self.assertEqual(saved["kpis"]["sn_hours_by_request_type"]["dashboard_id"], "SN11")
            self.assertEqual(saved["kpis"]["sn_monthly_type_change"]["dashboard_id"], "SN12")
            self.assertEqual(saved["kpis"]["sn_monthly_type_change"]["columns"],
                             ["Request type", "Current month", "Current requests", "Previous month"])
            self.assertNotIn("Change (%)", saved["kpis"]["sn_monthly_type_change"]["value"][0])
            self.assertTrue(saved["kpis"]["sn_hours_by_request_type"]["additional"])
            self.assertNotIn("sn_yearly_type_change", snapshot_store.list_snapshots()[0]["kpis"])
            ai = snapshot_store.get_ai_insights("2026-07-01", "2026-07-31")["entries"]
            self.assertNotIn("SN14", ai)
            self.assertNotIn("SN5", ai)
            self.assertNotIn("SN9", ai)
            self.assertNotIn("SN12", ai)
            self.assertEqual(ai["SN6"]["insight"], "region")
            self.assertEqual(ai["SN10"]["insight"], "overall")
            self.assertEqual(ai["SN11"]["insight"], "grouped")


if __name__ == "__main__":
    unittest.main()
