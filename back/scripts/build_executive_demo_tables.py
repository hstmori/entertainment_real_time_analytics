"""Generate compact deterministic aggregates for the executive PBIP demo.

The tables deliberately use dashboard grains (day, 15-minute interval, program,
lead day and sales breakdown) so the demo remains portable and fast to refresh.
They are synthetic presentation data and never replace governed acceptance data.
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, time, timedelta
import math
from pathlib import Path
import random
from typing import Iterable, Sequence


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[dict[str, object]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _money(value: float) -> str:
    return f"{value:.2f}"


def _ratio(value: float) -> str:
    return f"{max(0.0, min(1.0, value)):.4f}"


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=index) for index in range((end - start).days + 1)]


def build_executive_tables(
    output_dir: Path,
    *,
    start_date: date,
    end_date: date,
    seed: int,
) -> dict[str, int]:
    rng = random.Random(seed + 9_731)
    dates = _date_range(start_date, end_date)
    row_counts: dict[str, int] = {}

    # Extend the shared date dimension for forward-looking event dates.
    date_rows = [{"date": value.isoformat()} for value in _date_range(start_date, end_date + timedelta(days=30))]
    row_counts["date.csv"] = _write_csv(output_dir / "date.csv", ["date"], date_rows)

    # Programs: one shared ticket-sales timeline drives the program P&L, the pace chart, the
    # channel/tier breakdown and the 'Sự kiện' line of ExecutiveDaily, so every page reconciles.
    program_types = ["Concert", "Liveshow", "Nhạc kịch", "Sự kiện đặc biệt"]
    regions_short = ["Hà Nội", "TP.HCM", "Đà Nẵng", "Cần Thơ"]
    channels = ["Website", "Mobile App", "Đối tác", "Box Office"]
    channel_shares = [0.36, 0.32, 0.22, 0.10]
    tiers = [("VIP", 0.16, 2.4), ("A", 0.28, 1.5), ("B", 0.34, 1.0), ("C", 0.22, 0.65)]
    fee_rate = 0.075
    program_rows: list[dict[str, object]] = []
    pace_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    # date -> daily roll-up for the 'Sự kiện' business line
    event_daily: dict[date, dict[str, float]] = {
        value: {"gmv": 0.0, "fee": 0.0, "sponsor": 0.0, "refund": 0.0, "variable": 0.0, "tickets": 0.0,
                "marketing": 0.0, "plan_revenue": 0.0}
        for value in dates
    }

    def plan_share(lead_day: int) -> float:
        progress = (lead_day + 30) / 30
        return 0.04 + 0.96 * progress ** 1.35

    for index in range(24):
        program_id = f"PRG-{index + 1:03d}"
        program_type = program_types[index % len(program_types)]
        region = regions_short[index % len(regions_short)]
        # Sales open 30 days before the event; the first window opens on start_date.
        event_date = start_date + timedelta(days=30 + index * 4)
        capacity = 1_200 + (index % 6) * 600
        avg_price = 450_000 + (index % 5) * 125_000
        target_tickets = round(capacity * (0.86 + (index % 3) * 0.04))
        pace = 0.70 + (index % 7) * 0.075 + rng.uniform(-0.04, 0.04)
        refund_rate = 0.012 + (index % 4) * 0.004
        variable_rate = 0.24 + (index % 3) * 0.04
        fixed_cost = capacity * avg_price * (0.55 + (index % 4) * 0.05)
        sponsor_contract = 40_000_000 + (index % 5) * 30_000_000

        # Lead day of the data snapshot: 0 for completed events, negative while sales are open.
        # -31 means sales have not opened yet at the snapshot.
        as_of_lead = max(-31, min(0, (end_date - event_date).days))
        completed = as_of_lead == 0
        plan = {lead: round(target_tickets * plan_share(lead)) for lead in range(-30, 1)}
        plan[-31] = 0
        actual: dict[int, int] = {}
        previous = 0
        for lead in range(-30, as_of_lead + 1):
            raw = plan[lead] * pace * (0.97 + 0.03 * math.sin(lead / 3 + index))
            previous = min(capacity, max(previous, round(raw)))
            actual[lead] = previous
        tickets_sold = actual.get(as_of_lead, 0)
        pace_index = tickets_sold / plan[as_of_lead] if plan[as_of_lead] else 1.0

        # Forecast continues the actual curve for the days that have not happened yet.
        forecast: dict[int, int] = {}
        if not completed:
            previous = tickets_sold
            for lead in range(as_of_lead, 1):
                projected = tickets_sold + round((plan[lead] - plan[as_of_lead]) * pace_index)
                previous = min(capacity, max(previous, projected))
                forecast[lead] = previous
        projected_tickets = forecast[0] if forecast else tickets_sold

        ticket_gmv = tickets_sold * avg_price
        service_fee = ticket_gmv * fee_rate
        refunds = ticket_gmv * refund_rate
        sponsor_revenue = sponsor_contract if completed else 0.0
        revenue = ticket_gmv + service_fee + sponsor_revenue - refunds
        variable_cost = ticket_gmv * variable_rate
        contribution = revenue - variable_cost

        projected_gmv = projected_tickets * avg_price
        projected_revenue = projected_gmv * (1 + fee_rate - refund_rate) + sponsor_contract
        projected_contribution = projected_revenue - projected_gmv * variable_rate
        projected_break_even = projected_contribution / fixed_cost
        if projected_break_even < 0.85 or pace_index < 0.78:
            status = "Nghiêm trọng"
        elif projected_break_even < 1.0 or pace_index < 0.9:
            status = "Có rủi ro"
        elif pace_index < 1.0:
            status = "Cần theo dõi"
        else:
            status = "Đúng kế hoạch"

        attendees = round(tickets_sold * (0.86 + rng.random() * 0.09)) if completed else 0
        program_rows.append({
            "program_id": program_id,
            "program_name": f"{program_type} {index + 1:02d}",
            "program_type": program_type,
            "region": region,
            "event_date_utc": event_date.isoformat(),
            "capacity": capacity,
            "tickets_sold": tickets_sold,
            "ticket_gmv": _money(ticket_gmv),
            "service_fee": _money(service_fee),
            "sponsor_revenue": _money(sponsor_revenue),
            "refund_value": _money(refunds),
            "variable_cost": _money(variable_cost),
            "fixed_cost": _money(fixed_cost),
            "contribution_margin": _money(contribution),
            "attendees": attendees,
            "no_shows": tickets_sold - attendees if completed else 0,
            "new_customers": round(tickets_sold * (0.18 + rng.random() * 0.12)),
            "member_conversions": round(tickets_sold * (0.025 + rng.random() * 0.035)),
            "sales_pace_index": f"{pace_index:.4f}",
            "break_even_progress": f"{contribution / fixed_cost:.4f}",
            "forecast_margin_rate": f"{projected_contribution / projected_revenue:.4f}",
            "program_status": status,
        })
        for lead in range(-30, 1):
            pace_rows.append({
                "program_id": program_id,
                "event_date_utc": (event_date + timedelta(days=lead)).isoformat(),
                "lead_day": lead,
                "actual_cumulative_tickets": actual.get(lead, ""),
                "plan_cumulative_tickets": plan[lead],
                "forecast_cumulative_tickets": forecast.get(lead, ""),
            })

        # Channel x tier breakdown: allocate exactly tickets_sold (largest remainder, capped by inventory).
        cells = []
        for channel_index, channel in enumerate(channels):
            for tier, tier_share, price_factor in tiers:
                inventory = max(1, round(capacity * tier_share * channel_shares[channel_index]))
                cells.append({"channel_index": channel_index, "channel": channel, "tier": tier,
                              "price_factor": price_factor, "inventory": inventory,
                              "weight": inventory * (0.92 + rng.random() * 0.14), "sold": 0})
        cells[-1]["inventory"] += capacity - sum(cell["inventory"] for cell in cells)
        remaining = tickets_sold
        while remaining > 0:
            open_cells = [cell for cell in cells if cell["sold"] < cell["inventory"]]
            total_weight = sum(cell["weight"] for cell in open_cells)
            shares = [(remaining * cell["weight"] / total_weight, cell) for cell in open_cells]
            allocated = 0
            for share, cell in shares:
                take = min(int(share), cell["inventory"] - cell["sold"])
                cell["sold"] += take
                allocated += take
            for share, cell in sorted(shares, key=lambda item: item[0] - int(item[0]), reverse=True):
                if allocated >= remaining:
                    break
                if cell["sold"] < cell["inventory"]:
                    cell["sold"] += 1
                    allocated += 1
            remaining -= allocated
        price_scale = ticket_gmv / max(1, sum(cell["sold"] * avg_price * cell["price_factor"] for cell in cells))
        program_marketing = 0.0
        for cell in cells:
            sold = cell["sold"]
            cell_gmv = sold * avg_price * cell["price_factor"] * price_scale
            net_revenue = cell_gmv * (1 + fee_rate - refund_rate)
            marketing = net_revenue * (0.07 + cell["channel_index"] * 0.012)
            program_marketing += marketing
            completed_orders = round(sold / (1.6 + rng.random() * 0.6)) if sold else 0
            payment_attempts = round(completed_orders / (0.82 + rng.random() * 0.08))
            seat_selections = round(payment_attempts / (0.68 + rng.random() * 0.10))
            views = round(seat_selections / (0.58 + rng.random() * 0.10))
            detail_rows.append({
                "program_id": program_id,
                "event_date_utc": event_date.isoformat(),
                "channel": cell["channel"],
                "ticket_tier": cell["tier"],
                "inventory": cell["inventory"],
                "sold_tickets": sold,
                "event_views": views,
                "seat_selections": seat_selections,
                "payment_attempts": payment_attempts,
                "completed_orders": completed_orders,
                "net_revenue": _money(net_revenue),
                "marketing_cost": _money(marketing),
            })

        # Daily roll-up: ticket revenue and costs on the day tickets are sold, sponsorship on event day.
        previous = 0
        for lead in range(-30, as_of_lead + 1):
            day = event_date + timedelta(days=lead)
            daily_tickets = actual[lead] - previous
            previous = actual[lead]
            bucket = event_daily[day]
            bucket["tickets"] += daily_tickets
            bucket["gmv"] += daily_tickets * avg_price
            bucket["fee"] += daily_tickets * avg_price * fee_rate
            bucket["refund"] += daily_tickets * avg_price * refund_rate
            bucket["variable"] += daily_tickets * avg_price * variable_rate
            bucket["marketing"] += program_marketing * daily_tickets / max(1, tickets_sold)
        previous_plan = 0
        for lead in range(-30, 1):
            day = event_date + timedelta(days=lead)
            if day in event_daily:
                bucket = event_daily[day]
                bucket["plan_revenue"] += (plan[lead] - previous_plan) * avg_price * (1 + fee_rate - refund_rate)
                if lead == 0:
                    bucket["plan_revenue"] += sponsor_contract
            previous_plan = plan[lead]
        if completed:
            event_daily[event_date]["sponsor"] += sponsor_revenue

    row_counts["program_event.csv"] = _write_csv(output_dir / "program_event.csv", [
        "program_id", "program_name", "program_type", "region", "event_date_utc", "capacity",
        "tickets_sold", "ticket_gmv", "service_fee", "sponsor_revenue", "refund_value",
        "variable_cost", "fixed_cost", "contribution_margin", "attendees", "no_shows", "new_customers",
        "member_conversions", "sales_pace_index", "break_even_progress", "forecast_margin_rate",
        "program_status",
    ], program_rows)
    row_counts["event_sales_pace.csv"] = _write_csv(output_dir / "event_sales_pace.csv", [
        "program_id", "event_date_utc", "lead_day", "actual_cumulative_tickets",
        "plan_cumulative_tickets", "forecast_cumulative_tickets",
    ], pace_rows)
    row_counts["event_sales_detail.csv"] = _write_csv(output_dir / "event_sales_detail.csv", [
        "program_id", "event_date_utc", "channel", "ticket_tier", "inventory", "sold_tickets",
        "event_views", "seat_selections", "payment_attempts", "completed_orders", "net_revenue",
        "marketing_cost",
    ], detail_rows)

    business_profiles = [
        ("Streaming", 185_000_000, 0.58, 0.34, 5_200),
        ("Ticketing", 510_000_000, 0.26, 0.22, 2_900),
        ("Thành viên", 92_000_000, 0.96, 0.19, 2_150),
    ]
    executive_rows: list[dict[str, object]] = []
    for index, current_date in enumerate(dates):
        weekly = 1 + 0.10 * math.sin(index * 2 * math.pi / 7)
        trend = 1 + 0.0024 * index
        campaign = 1.18 if 62 <= index <= 70 else 1.0
        for line_index, (line, gross_base, recognition, cost_rate, customer_base) in enumerate(business_profiles):
            noise = 0.94 + rng.random() * 0.12
            gross = gross_base * weekly * trend * campaign * noise
            net = gross * recognition
            variable_cost = net * (cost_rate + 0.015 * math.sin(index / 9 + line_index))
            refunds = gross * (0.012 + line_index * 0.003 + rng.random() * 0.006)
            net_after_refund = max(0.0, net - refunds * recognition)
            contribution = net_after_refund - variable_cost
            transactions = max(1, round(gross / (285_000 + line_index * 95_000)))
            paying = max(1, round(customer_base * weekly * trend * (0.96 + rng.random() * 0.08)))
            new_customers = max(1, round(paying * (0.035 + rng.random() * 0.025)))
            target = gross_base * recognition * (1 + 0.0027 * index)
            executive_rows.append({
                "event_date_utc": current_date.isoformat(),
                "business_line": line,
                "gross_value": _money(gross),
                "net_revenue": _money(net_after_refund),
                "variable_cost": _money(variable_cost),
                "contribution_margin": _money(contribution),
                "refund_value": _money(refunds),
                "transactions": transactions,
                "paying_customers_line": paying,
                "new_customers": new_customers,
                "marketing_spend": _money(net_after_refund * (0.055 + line_index * 0.008)),
                "target_revenue": _money(target),
            })
        # 'Sự kiện' is the exact daily roll-up of the program tables.
        bucket = event_daily[current_date]
        gross = bucket["gmv"] + bucket["fee"] + bucket["sponsor"]
        net = gross - bucket["refund"]
        orders = round(bucket["tickets"] / 1.9)
        executive_rows.append({
            "event_date_utc": current_date.isoformat(),
            "business_line": "Sự kiện",
            "gross_value": _money(gross),
            "net_revenue": _money(net),
            "variable_cost": _money(bucket["variable"]),
            "contribution_margin": _money(net - bucket["variable"]),
            "refund_value": _money(bucket["refund"]),
            "transactions": orders,
            "paying_customers_line": round(orders * 0.95),
            "new_customers": round(orders * 0.25),
            "marketing_spend": _money(bucket["marketing"]),
            "target_revenue": _money(bucket["plan_revenue"]),
        })
    row_counts["executive_daily.csv"] = _write_csv(output_dir / "executive_daily.csv", [
        "event_date_utc", "business_line", "gross_value", "net_revenue", "variable_cost",
        "contribution_margin", "refund_value", "transactions", "paying_customers_line",
        "new_customers", "marketing_spend", "target_revenue",
    ], executive_rows)

    # One operational day at 15-minute grain, split by device and region.
    devices = [("Web", 0.24), ("iOS", 0.22), ("Android", 0.31), ("Smart TV", 0.23)]
    regions = [("Miền Bắc", 0.34), ("Miền Trung", 0.19), ("Miền Nam", 0.39), ("Quốc tế", 0.08)]
    streaming_rows: list[dict[str, object]] = []
    for slot in range(96):
        current_time = datetime.combine(end_date, time.min, tzinfo=UTC) + timedelta(minutes=15 * slot)
        hour = current_time.hour + current_time.minute / 60
        prime = math.exp(-((hour - 21) / 4.2) ** 2)
        daytime = math.exp(-((hour - 12.5) / 5.5) ** 2)
        total_viewers = 42_000 + 310_000 * prime + 75_000 * daytime
        for device, device_share in devices:
            for region, region_share in regions:
                viewers = max(40, round(total_viewers * device_share * region_share * (0.94 + rng.random() * 0.12)))
                sessions = round(viewers * (1.08 + rng.random() * 0.18))
                plays = round(sessions * (0.88 + rng.random() * 0.06))
                completion_rate = 0.64 + (0.09 if device == "Smart TV" else 0.02) + rng.random() * 0.07
                completions = round(plays * completion_rate)
                rebuffer_rate = 0.006 + (0.009 if device == "Android" else 0.002) + rng.random() * 0.005
                if region == "Quốc tế" and 68 <= slot <= 74:
                    rebuffer_rate += 0.028
                start_failure_rate = 0.0025 + (0.004 if device == "Android" else 0.001) + rng.random() * 0.002
                streaming_rows.append({
                    "event_time_utc": _iso(current_time),
                    "event_date_utc": end_date.isoformat(),
                    "device_type": device,
                    "region": region,
                    "concurrent_viewers": viewers,
                    "watch_hours": _money(viewers * (0.16 + rng.random() * 0.08)),
                    "play_starts": plays,
                    "completions": completions,
                    "total_sessions": sessions,
                    "rebuffer_events": round(sessions * rebuffer_rate),
                    "start_failures": round(sessions * start_failure_rate),
                    "subscription_conversions": round(sessions * (0.003 + rng.random() * 0.004)),
                })
    row_counts["streaming_realtime.csv"] = _write_csv(output_dir / "streaming_realtime.csv", [
        "event_time_utc", "event_date_utc", "device_type", "region", "concurrent_viewers",
        "watch_hours", "play_starts", "completions", "total_sessions", "rebuffer_events",
        "start_failures", "subscription_conversions",
    ], streaming_rows)

    services = [("Streaming API", 18_500), ("Ticketing API", 4_200), ("Payment Gateway", 2_500), ("Event Pipeline", 7_400)]
    operations_rows: list[dict[str, object]] = []
    for slot in range(96):
        current_time = datetime.combine(end_date, time.min, tzinfo=UTC) + timedelta(minutes=15 * slot)
        load_factor = 0.72 + 0.42 * math.exp(-((slot - 78) / 16) ** 2)
        for service_index, (service, base_rps) in enumerate(services):
            incident = service == "Payment Gateway" and 67 <= slot <= 73
            rps = round(base_rps * load_factor * (0.95 + rng.random() * 0.10))
            latency = 105 + service_index * 28 + rps / 180 + rng.random() * 24
            error_rate = 0.0008 + service_index * 0.00035 + rng.random() * 0.0014
            if incident:
                latency += 260
                error_rate += 0.010
            severity = "Cảnh báo" if incident else "Ổn định"
            operations_rows.append({
                "event_time_utc": _iso(current_time),
                "event_date_utc": end_date.isoformat(),
                "service_name": service,
                "requests_per_second": rps,
                "p95_latency_ms": f"{latency:.2f}",
                "error_rate": f"{error_rate:.5f}",
                "queue_depth": max(0, round(rps * (0.8 + rng.random() * 1.2))),
                "throughput_per_minute": round(rps * 60 * (0.92 + rng.random() * 0.06)),
                "data_lag_seconds": f"{18 + service_index * 7 + rng.random() * 16:.2f}",
                "status": severity,
            })
    row_counts["operations_realtime.csv"] = _write_csv(output_dir / "operations_realtime.csv", [
        "event_time_utc", "event_date_utc", "service_name", "requests_per_second",
        "p95_latency_ms", "error_rate", "queue_depth", "throughput_per_minute",
        "data_lag_seconds", "status",
    ], operations_rows)
    return row_counts
