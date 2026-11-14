"""Validate the generated PBIP source project without opening Power BI Desktop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Iterator

try:
    from pbip_colors import color_drift, color_measures_by_table
except ImportError:  # imported as scripts.validate_pbip (tests)
    from scripts.pbip_colors import color_drift, color_measures_by_table


EXPECTED_EXPORTS = {
    "booking_funnel_daily.csv",
    "content_engagement_hourly.csv",
    "customer_360.csv",
    "customer_activity.csv",
    "customer_affinity.csv",
    "customer_rank_share.csv",
    "date.csv",
    "event_performance.csv",
    "refresh_audit.csv",
    "subscription_daily.csv",
    "executive_daily.csv",
    "streaming_realtime.csv",
    "program_event.csv",
    "event_sales_pace.csv",
    "event_sales_detail.csv",
    "operations_realtime.csv",
}
EXPECTED_PAGES = {
    "Trung tâm điều hành",
    "Doanh thu & Lợi nhuận",
    "Streaming",
    "Vé & Sự kiện",
    "Hiệu quả Chương trình",
    "Chi tiết Sự kiện",
    "Thành viên",
    "Customer Portfolio & Spend Ranking",
    "Customer 360 Profile",
    "Vận hành Real-time",
}
EXPECTED_RELATIONSHIPS = 12


def walk(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(project_dir: Path, data_dir: Path | None = None) -> dict[str, object]:
    dashboard = project_dir / "dashboard"
    report = dashboard / "EntertainmentAnalytics.Report"
    semantic = dashboard / "EntertainmentAnalytics.SemanticModel"
    pages_root = report / "definition" / "pages"
    data_dir = data_dir or project_dir / "artifacts" / "powerbi"

    required = [
        dashboard / "EntertainmentAnalytics.pbip",
        dashboard / "model.bim",
        report / "definition.pbir",
        report / "definition" / "report.json",
        report / "definition" / "version.json",
        pages_root / "pages.json",
        semantic / "definition.pbism",
        semantic / "definition" / "database.tmdl",
        semantic / "definition" / "model.tmdl",
        semantic / "definition" / "relationships.tmdl",
        semantic / "definition" / "expressions.tmdl",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"Missing PBIP files: {missing}")

    export_names = {path.name for path in data_dir.glob("*.csv")}
    if export_names != EXPECTED_EXPORTS:
        raise ValueError(f"Unexpected Power BI exports: {sorted(export_names)}")

    json_files = [path for path in dashboard.rglob("*.json") if ".pbi" not in path.parts]
    for path in json_files:
        load_json(path)

    report_settings = load_json(report / "definition" / "report.json")
    assert isinstance(report_settings, dict)
    missing_theme_files = [
        str(report / "StaticResources" / package["name"] / item["path"])
        for package in report_settings.get("resourcePackages", [])
        for item in package.get("items", [])
        if not (report / "StaticResources" / package["name"] / item["path"]).is_file()
    ]
    if missing_theme_files:
        raise ValueError(f"Theme files referenced by report.json are missing: {missing_theme_files}")

    model = load_json(dashboard / "model.bim")
    assert isinstance(model, dict)
    tables = model["model"]["tables"]  # type: ignore[index]
    table_fields: dict[str, set[str]] = {}
    for table in tables:  # type: ignore[union-attr]
        column_names = {column["name"] for column in table.get("columns", [])}
        measure_names = {measure["name"] for measure in table.get("measures", [])}
        duplicate_names = column_names & measure_names
        if duplicate_names:
            raise ValueError(
                f"Column/measure name collision in {table['name']}: {sorted(duplicate_names)}"
            )
        table_fields[table["name"]] = {
            *column_names,
            *measure_names,
        }

    pages_metadata = load_json(pages_root / "pages.json")
    assert isinstance(pages_metadata, dict)
    page_ids = pages_metadata.get("pageOrder", [])
    page_names: set[str] = set()
    visual_files: list[Path] = []
    visual_types: set[str] = set()
    invalid_references: list[str] = []
    color_drifted: list[str] = []
    for page_id in page_ids:
        page_path = pages_root / str(page_id) / "page.json"
        page = load_json(page_path)
        assert isinstance(page, dict)
        page_names.add(str(page.get("displayName")))
        current_visuals = list((page_path.parent / "visuals").rglob("visual.json"))
        if not current_visuals:
            raise ValueError(f"Page has no visuals: {page_path}")
        visual_files.extend(current_visuals)
        for visual_path in current_visuals:
            visual = load_json(visual_path)
            assert isinstance(visual, dict)
            visual_definition = visual.get("visual", {})
            if isinstance(visual_definition, dict) and visual_definition.get("visualType"):
                visual_types.add(str(visual_definition["visualType"]))
            if color_drift(visual):
                color_drifted.append(f"{visual_path} ({visual_definition.get('visualType')})")
            # Saved slicer selections reference tables through aliases declared in "From".
            aliases = {
                item["Name"]: item["Entity"]
                for node in walk(visual) for item in node.get("From", []) if isinstance(node.get("From"), list)
                if isinstance(item, dict) and "Name" in item and "Entity" in item
            }
            for node in walk(visual):
                for kind in ("Column", "Measure"):
                    field = node.get(kind)
                    if not isinstance(field, dict):
                        continue
                    expression = field.get("Expression", {})
                    source = expression.get("SourceRef", {}) if isinstance(expression, dict) else {}
                    table_name = source.get("Entity") if isinstance(source, dict) else None
                    if table_name is None and isinstance(source, dict):
                        table_name = aliases.get(source.get("Source"))
                    property_name = field.get("Property")
                    if table_name not in table_fields or property_name not in table_fields[str(table_name)]:
                        invalid_references.append(f"{visual_path}: {kind} {table_name}.{property_name}")

    if page_names != EXPECTED_PAGES:
        raise ValueError(f"Unexpected report pages: {sorted(page_names)}")
    if invalid_references:
        raise ValueError("Invalid visual model references:\n" + "\n".join(invalid_references))
    if color_drifted:
        raise ValueError(
            "Visuals no longer match scripts/pbip_colors.py (colors lost or edited):\n" + "\n".join(color_drifted)
        )

    table_tmdl = list((semantic / "definition" / "tables").glob("*.tmdl"))
    missing_color_measures = []
    for table_name, color_measures in color_measures_by_table().items():
        tmdl_text = (semantic / "definition" / "tables" / f"{table_name}.tmdl").read_text(encoding="utf-8")
        for measure_name, _ in color_measures:
            if measure_name not in table_fields.get(table_name, set()):
                missing_color_measures.append(f"model.bim: {table_name}[{measure_name}]")
            if f"measure '{measure_name}'" not in tmdl_text:
                missing_color_measures.append(f"TMDL: {table_name}[{measure_name}]")
    if missing_color_measures:
        raise ValueError("Missing color measures:\n" + "\n".join(missing_color_measures))

    # Power BI Desktop reads TMDL; the validator and generator read model.bim. They must not drift apart.
    bim_measures = {
        (table["name"], measure["name"]): " ".join(measure["expression"].split())
        for table in tables for measure in table.get("measures", [])  # type: ignore[union-attr]
    }
    bim_columns = {(table["name"], column["name"]) for table in tables for column in table.get("columns", [])}  # type: ignore[union-attr]
    tmdl_measures: dict[tuple[str, str], str] = {}
    tmdl_columns: set[tuple[str, str]] = set()
    name = r"(?:'((?:[^']|'')+)'|([^\s=']+))"
    for path in table_tmdl:
        text = path.read_text(encoding="utf-8")
        table_match = re.search(r"^table " + name, text, re.M)
        table_name = (table_match.group(1) or table_match.group(2)).replace("''", "'") if table_match else path.stem
        for match in re.finditer(r"^\tmeasure " + name + r" = (.+)$", text, re.M):
            tmdl_measures[(table_name, (match.group(1) or match.group(2)).replace("''", "'"))] = " ".join(match.group(3).split())
        for match in re.finditer(r"^\tcolumn " + name + r"\s*$", text, re.M):
            tmdl_columns.add((table_name, (match.group(1) or match.group(2)).replace("''", "'")))
    drift = [f"measure only in model.bim: {key}" for key in bim_measures.keys() - tmdl_measures.keys()]
    drift += [f"measure only in TMDL: {key}" for key in tmdl_measures.keys() - bim_measures.keys()]
    drift += [f"measure expression differs: {key}" for key in bim_measures.keys() & tmdl_measures.keys()
              if bim_measures[key] != tmdl_measures[key]]
    drift += [f"column only in model.bim: {key}" for key in bim_columns - tmdl_columns]
    drift += [f"column only in TMDL: {key}" for key in tmdl_columns - bim_columns]
    if drift:
        raise ValueError("model.bim and TMDL disagree:\n" + "\n".join(sorted(drift)))

    relationship_text = (semantic / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    relationship_count = sum(line.startswith("relationship ") for line in relationship_text.splitlines())
    if len(table_tmdl) != len(table_fields) or relationship_count != EXPECTED_RELATIONSHIPS:
        raise ValueError(
            f"TMDL mismatch: tables={len(table_tmdl)}, relationships={relationship_count}"
        )

    binary_artifacts = list(dashboard.rglob("*.pbix")) + list(dashboard.rglob("*.abf"))
    exposed_artifacts = [path for path in binary_artifacts if ".pbi" not in path.parts]
    if exposed_artifacts:
        raise ValueError(f"Power BI binary artifacts outside ignored .pbi cache: {exposed_artifacts}")
    ignored_cache_files = sum(
        1 for path in dashboard.rglob("*") if path.is_file() and ".pbi" in path.parts
    )

    measure_count = sum(len(table.get("measures", [])) for table in tables)  # type: ignore[union-attr]
    return {
        "status": "valid",
        "json_files": len(json_files),
        "pages": len(page_ids),
        "visuals": len(visual_files),
        "visual_types": sorted(visual_types),
        "tables": len(table_fields),
        "measures": measure_count,
        "relationships": relationship_count,
        "exports": len(export_names),
        "ignored_local_cache_files": ignored_cache_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    back_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--project-dir", type=Path, default=back_root.parent)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    data_dir = back_root / "artifacts" / "powerbi_demo" if args.data_dir is None else args.data_dir.resolve()
    result = validate(args.project_dir.resolve(), data_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
