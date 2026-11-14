"""Semantic color system for the Entertainment Analytics PBIP report.

Single source of truth for dashboard colors. `build_pbip.py` applies it to every generated
visual and `validate_pbip.py` fails when a visual on disk no longer matches it, so a
regeneration or an accidental Desktop edit cannot silently drop the palette.

Colors are set at visual level on purpose: the registered report theme stays untouched.
"""

from __future__ import annotations

import copy
import json


CYAN, GREEN, AMBER, CORAL, ORANGE = "#22D3EE", "#34D399", "#FBBF24", "#F87171", "#FB923C"
VIOLET, BLUE, PINK, GRAY, WHITE = "#A78BFA", "#60A5FA", "#F472B6", "#94A3B8", "#F7FAFC"
MUTED, LABEL = "#9FB3C8", "#E2E8F0"

# Measure -> color by meaning: revenue/volume, margin/good outcome, cost/latency, risk,
# customers/members, streaming, plan/capacity.
MEASURE_COLORS: dict[str, str] = {
    "Doanh thu thuần": CYAN, "Gross Value": CYAN, "Ticket GMV": CYAN, "Sales Net Revenue": CYAN,
    "Doanh thu sự kiện": CYAN, "MRR event value proxy": CYAN, "Net Spend 12M": CYAN,
    "Customer Value 12M": CYAN, "Lifetime Value Proxy": CYAN, "Current RPS": CYAN,
    "Throughput / phút": CYAN, "Vé đã bán": CYAN, "Vé bán chi tiết": CYAN, "Vé tích lũy thực tế": CYAN,
    "Bookings TB": CYAN,
    "Contribution Margin": GREEN, "Contribution Margin %": GREEN, "Event Contribution Margin": GREEN,
    "Event Margin %": GREEN, "Customer Contribution Margin": GREEN, "Completion Rate": GREEN,
    "Sell-through Rate": GREEN, "Tỷ lệ đạt kế hoạch": GREEN, "Tiến độ hòa vốn": GREEN,
    "Gia hạn": GREEN, "Completed Orders": GREEN,
    "Chi phí biến đổi": AMBER, "Hoàn tiền": AMBER, "Sales Marketing Cost": AMBER,
    "P95 Latency": AMBER, "P95 Latency cao nhất": AMBER, "Queue Depth": AMBER, "Data Lag": AMBER, "Payment Attempts": AMBER,
    "Rebuffer Ratio": CORAL, "Video Start Failure": ORANGE, "No-show Rate": CORAL,
    "Hủy subscription": CORAL, "Error Rate": CORAL, "Dịch vụ cảnh báo": CORAL,
    "High-spend giảm tương tác": CORAL,
    "Khách hàng": VIOLET, "Khách tham gia": VIOLET, "Member Conversions": VIOLET,
    "Đăng ký mới": VIOLET, "Sự kiện subscription": VIOLET, "Gold+ Customer Share": VIOLET,
    "Gold+ Spend Share": VIOLET, "Tỷ lệ khách đa dịch vụ": VIOLET, "Engagement Score Profile": VIOLET,
    "Streaming Conversion": VIOLET, "Affinity Score": VIOLET, "Seat Selections": VIOLET,
    "Subscription Activity TB": VIOLET, "Vé forecast": VIOLET,
    "Watch Hours": BLUE, "Watch Hours TB": BLUE, "Concurrent Viewers": BLUE, "Event Views": BLUE,
    "Attendance TB": PINK,
    "Sức chứa": GRAY, "Tổng Inventory": GRAY, "Mục tiêu doanh thu": GRAY, "Vé tích lũy kế hoạch": GRAY,
}

# Single-measure charts whose category has fixed colors.
CATEGORY_COLORS: dict[str, dict[str, str]] = {
    "business_line": {"Streaming": BLUE, "Ticketing": CYAN, "Sự kiện": PINK, "Thành viên": VIOLET},
    "program_status": {"Đúng kế hoạch": GREEN, "Cần theo dõi": AMBER, "Có rủi ro": ORANGE, "Nghiêm trọng": CORAL},
}

# Same hues as member_rank_color in the data; Basic lifted from #4B5563 for contrast on the dark cards.
RANK_COLORS: dict[str, str] = {
    "Diamond": "#20D9E8", "Platinum": "#D9E2EC", "Gold": "#F5C451", "Silver": "#94A3B8", "Basic": "#64748B",
}
SERIES_COLORS: dict[str, dict[str, str]] = {"member_rank": RANK_COLORS}


def _switch(table: str, column: str, mapping: dict[str, str]) -> str:
    cases = ", ".join(f'"{value}", "{hex_color}"' for value, hex_color in mapping.items())
    return f"SWITCH(SELECTEDVALUE({table}[{column}]), {cases}, BLANK())"


# (table, column) -> (measure, DAX). Used as field-value font color for status columns in tables.
STATUS_COLOR_MEASURES: dict[tuple[str, str], tuple[str, str]] = {
    ("ProgramEvent", "program_status"): (
        "Màu trạng thái chương trình", _switch("ProgramEvent", "program_status", CATEGORY_COLORS["program_status"])),
    # The health tables show the status of the latest 15-minute snapshot (a measure), not every interval.
    ("OperationsRealtime", "Trạng thái hiện tại"): (
        "Màu trạng thái dịch vụ",
        f'SWITCH([Trạng thái hiện tại], "Ổn định", "{GREEN}", "Cảnh báo", "{CORAL}", BLANK())'),
    ("CustomerActivity", "activity_result"): (
        "Màu kết quả hoạt động", _switch("CustomerActivity", "activity_result", {
            "Thành công": GREEN, "Đang xử lý": AMBER, "Thất bại": CORAL, "Thông tin": MUTED})),
    ("Customer360", "behavior_risk"): ("Màu rủi ro hành vi", "SELECTEDVALUE(Customer360[behavior_risk_color])"),
    ("Customer360", "member_rank"): ("Màu hạng thành viên", _switch("Customer360", "member_rank", RANK_COLORS)),
}

CHART_TYPES = {
    "clusteredBarChart", "clusteredColumnChart", "lineChart", "barChart", "columnChart",
    "scatterChart", "hundredPercentStackedBarChart",
}


def color_measures_by_table() -> dict[str, list[tuple[str, str]]]:
    tables: dict[str, list[tuple[str, str]]] = {}
    for (table, _), (name, dax) in STATUS_COLOR_MEASURES.items():
        tables.setdefault(table, []).append((name, dax))
    return tables


def _lit(value: str) -> dict[str, object]:
    return {"expr": {"Literal": {"Value": value}}}


def _color(hex_color: str) -> dict[str, object]:
    return {"solid": {"color": _lit(f"'{hex_color}'")}}


def _set(objects: dict, name: str, props: dict[str, object]) -> None:
    """Merge props into the selector-less entry of objects[name]."""
    entries = objects.setdefault(name, [])
    base = next((entry for entry in entries if "selector" not in entry), None)
    if base is None:
        base = {"properties": {}}
        entries.insert(0, base)
    base.setdefault("properties", {}).update(props)


def _value_selector(column: dict, value: str) -> dict[str, object]:
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0, "Left": {"Column": column}, "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}


def _chart(visual: dict) -> None:
    state = visual["query"]["queryState"]
    objects = visual.setdefault("objects", {})
    measures = state.get("Y", {}).get("projections", [])
    series = state.get("Series", {}).get("projections", [])
    categories = state.get("Category", {}).get("projections", [])
    objects["dataPoint"] = [entry for entry in objects.get("dataPoint", []) if "selector" not in entry]
    multi = False

    series_column = series[0]["field"].get("Column") if series else None
    if series_column and series_column["Property"] in SERIES_COLORS:
        for value, hex_color in SERIES_COLORS[series_column["Property"]].items():
            objects["dataPoint"].append({"properties": {"fill": _color(hex_color)}, "selector": _value_selector(series_column, value)})
        multi = True
    elif len(measures) > 1:
        for projection in measures:
            hex_color = MEASURE_COLORS.get(projection["nativeQueryRef"])
            if hex_color:
                objects["dataPoint"].append({"properties": {"fill": _color(hex_color)}, "selector": {"metadata": projection["queryRef"]}})
        multi = True
    elif measures:
        _set(objects, "dataPoint", {"defaultColor": _color(MEASURE_COLORS.get(measures[0]["nativeQueryRef"], CYAN))})
        category_column = categories[0]["field"].get("Column") if categories else None
        if category_column and category_column["Property"] in CATEGORY_COLORS:
            for value, hex_color in CATEGORY_COLORS[category_column["Property"]].items():
                objects["dataPoint"].append({"properties": {"fill": _color(hex_color)}, "selector": _value_selector(category_column, value)})

    if multi:
        # Several colors on one chart are unreadable without a legend.
        _set(objects, "legend", {"show": _lit("true"), "position": _lit("'Top'"), "labelColor": _color("#D9E2EC")})
    if visual["visualType"] != "scatterChart":
        _set(objects, "labels", {"color": _color(LABEL)})
    if visual["visualType"] == "lineChart":
        _set(objects, "lineStyles", {"strokeWidth": _lit("3D")})
    _set(objects, "valueAxis", {"gridlineColor": _color("#1E3350")})


def _card(visual: dict) -> None:
    measures = visual.get("query", {}).get("queryState", {}).get("Values", {}).get("projections", [])
    if measures:
        _set(visual.setdefault("objects", {}), "labels", {"color": _color(MEASURE_COLORS.get(measures[0]["nativeQueryRef"], WHITE))})


def _table(visual: dict) -> None:
    objects = visual.setdefault("objects", {})
    _set(objects, "values", {"fontColorSecondary": _color("#D9E2EC"), "backColorSecondary": _color("#13263D")})
    _set(objects, "columnHeaders", {"backColor": _color("#1B3A5C"), "fontColor": _color(WHITE)})
    _set(objects, "grid", {"gridHorizontalColor": _color("#29415F"), "gridVerticalColor": _color("#29415F"), "outlineColor": _color("#29415F")})

    rules = []
    projections = visual["query"]["queryState"]["Values"]["projections"]
    for projection in projections:
        ref = projection["field"].get("Column") or projection["field"].get("Measure")
        key = (ref["Expression"]["SourceRef"]["Entity"], ref["Property"])
        if key in STATUS_COLOR_MEASURES:
            rules.append({
                "properties": {"fontColor": {"solid": {"color": {"expr": {"Measure": {
                    "Expression": {"SourceRef": {"Entity": key[0]}}, "Property": STATUS_COLOR_MEASURES[key][0]}}}}}},
                "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": projection["queryRef"]},
            })
    # Drop rules we manage plus any rule left behind for a field that is no longer in the table.
    current = {projection["queryRef"] for projection in projections}
    managed = {rule["selector"]["metadata"] for rule in rules}
    objects["values"] = [
        entry for entry in objects["values"]
        if "selector" not in entry or entry["selector"].get("metadata") in current - managed
    ] + rules


def _slicer(visual: dict) -> None:
    objects = visual.setdefault("objects", {})
    _set(objects, "header", {"fontColor": _color(MUTED)})
    _set(objects, "items", {"fontColor": _color(LABEL), "background": _color("#13263D")})
    _set(objects, "date", {"fontColor": _color(LABEL), "background": _color("#13263D")})
    _set(objects, "slider", {"color": _color(CYAN)})


def _rank_legend(visual: dict) -> None:
    runs = []
    for index, (rank, hex_color) in enumerate(RANK_COLORS.items()):
        runs.append({"value": "■ ", "textStyle": {"fontFamily": "Segoe UI", "fontSize": "12px", "color": hex_color}})
        runs.append({"value": rank.upper() + ("     " if index < len(RANK_COLORS) - 1 else ""),
                     "textStyle": {"fontFamily": "Segoe UI", "fontSize": "12px", "color": "#D9E2EC"}})
    visual["objects"]["general"][0]["properties"]["paragraphs"] = [{"textRuns": runs}]


def apply_colors(container: dict) -> dict:
    """Apply the palette to a visual.json payload in place and return it. Idempotent."""
    visual = container.get("visual", {})
    kind = visual.get("visualType")
    if kind in CHART_TYPES and "query" in visual:
        _chart(visual)
    elif kind == "card":
        _card(visual)
    elif kind == "tableEx":
        _table(visual)
    elif kind == "slicer":
        _slicer(visual)
    elif kind == "textbox" and "DIAMOND" in json.dumps(visual.get("objects", {}), ensure_ascii=False):
        _rank_legend(visual)
    return container


def color_drift(container: dict) -> bool:
    """True when the visual on disk does not already carry the palette."""
    return apply_colors(copy.deepcopy(container)) != container
