from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.build_pbip import build_model, build_report
from scripts.pbip_colors import STATUS_COLOR_MEASURES, color_drift
from scripts.validate_pbip import validate


BACK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACK_ROOT.parent
DEMO_DATA = BACK_ROOT / "artifacts" / "powerbi_demo"


def _visuals(report_definition: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in report_definition.glob("pages/*/visuals/*/visual.json")
    ]


@pytest.mark.skipif(not (REPO_ROOT / "dashboard").is_dir() or not DEMO_DATA.is_dir(), reason="dashboard or demo data missing")
def test_committed_dashboard_keeps_palette() -> None:
    result = validate(REPO_ROOT, DEMO_DATA)
    assert result["status"] == "valid"


def test_generated_report_carries_palette(tmp_path: Path) -> None:
    build_report(tmp_path)
    visuals = _visuals(tmp_path / "EntertainmentAnalytics.Report" / "definition")

    assert visuals
    assert not [v["name"] for v in visuals if color_drift(v)]
    assert "stackedBarChart" not in {v["visual"]["visualType"] for v in visuals}


def test_generated_model_has_color_measures(tmp_path: Path) -> None:
    model = build_model(tmp_path)
    measures = {
        (table["name"], measure["name"])
        for table in model["model"]["tables"]
        for measure in table.get("measures", [])
    }
    for (table, _), (measure, _) in STATUS_COLOR_MEASURES.items():
        assert (table, measure) in measures


def test_drift_is_detected_when_a_color_is_removed(tmp_path: Path) -> None:
    build_report(tmp_path)
    visuals = _visuals(tmp_path / "EntertainmentAnalytics.Report" / "definition")
    chart = next(v for v in visuals if v["visual"]["visualType"] == "lineChart")

    tampered = copy.deepcopy(chart)
    tampered["visual"]["objects"]["dataPoint"] = [{"properties": {}}]

    assert color_drift(tampered)
