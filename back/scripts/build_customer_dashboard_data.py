"""Build reusable Customer 360 and customer-portfolio demo tables.

All hand-tunable options live in the configuration block immediately below.
The generated data is deterministic and is designed to stay logically aligned
with the synthetic Entertainment event stream used by the rest of the demo.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import math
from pathlib import Path
import random
import sys
from typing import Any, Iterable, Sequence


# ---------------------------------------------------------------------------
# MANUAL CONFIGURATION — edit these values when you want a different render.
# ---------------------------------------------------------------------------
DEFAULT_EVENT_COUNT = 1_200
DEFAULT_RANDOM_SEED = 20_261_107
DEFAULT_BASE_TIME_UTC = "2026-07-29T00:00:00Z"
DEFAULT_EVENT_INTERVAL_SECONDS = 7_200
DEFAULT_CUSTOMER_POOL_SIZE = 200

SPEND_WINDOW_MONTHS = 12
BEHAVIOR_WINDOW_DAYS = 90
TREND_WINDOW_DAYS = 30
RECENT_ACTIVITY_ROWS_PER_CUSTOMER = 8

# Rank is based ONLY on trailing-12-month net spend after refunds.
RANK_RULES = (
    ("Diamond", Decimal("10000000"), 1, "#20D9E8"),
    ("Platinum", Decimal("5000000"), 2, "#D9E2EC"),
    ("Gold", Decimal("2000000"), 3, "#F5C451"),
    ("Silver", Decimal("500000"), 4, "#94A3B8"),
    ("Basic", Decimal("0"), 5, "#4B5563"),
)

PLAN_MONTHLY_FEES = {
    "mobile-monthly": Decimal("99000"),
    "standard-monthly": Decimal("149000"),
    "family-monthly": Decimal("249000"),
    "premium-monthly": Decimal("299000"),
}

REGIONS = ("Hà Nội", "TP.HCM", "Đà Nẵng", "Cần Thơ")
DEVICES = ("Smart TV", "mobile", "web", "tablet")
AFFINITY_COLORS = {
    "Action": "#20D9E8",
    "Concert": "#8B5CF6",
    "Family": "#22C55E",
    "Sports": "#F5C451",
}
RISK_COLORS = {"Cao": "#F45B69", "Trung bình": "#F5C451", "Thấp": "#22C55E"}
ACTIVITY_COLORS = {
    "Thành công": "#22C55E",
    "Thất bại": "#F45B69",
    "Đang xử lý": "#F5C451",
    "Thông tin": "#20D9E8",
}

# Historical spend fills the part of the 12-month window outside the compact
# observed event sample. It is deterministic and remains subordinate to the
# actual observed booking/subscription amounts.
HISTORICAL_SPEND_MEDIAN = Decimal("1250000")
HISTORICAL_SPEND_SIGMA = 1.18
MAX_NET_SPEND_12M = Decimal("25000000")
HIGH_SPEND_RANKS = {"Diamond", "Platinum"}
LOW_ENGAGEMENT_THRESHOLD = 45.0


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


CUSTOMER_360_COLUMNS = [
    "customer_id", "unified_customer_id", "region", "consent_status", "preferred_device",
    "first_seen_at", "last_seen_at", "observed_days", "recency_days", "total_events",
    "activity_events", "active_days", "sessions", "watch_hours_90d", "play_events",
    "completion_events", "completion_rate", "search_events", "favorite_content_id",
    "booking_state_events", "confirmed_bookings", "refunded_bookings", "failed_bookings",
    "confirmed_tickets", "ticket_spend_12m", "subscription_spend_12m", "content_spend_12m",
    "refund_value_12m", "net_spend_12m", "lifetime_value_proxy", "contribution_margin_proxy",
    "attendance_records", "checked_in_events", "no_show_events", "attendance_rate",
    "subscription_events", "latest_subscription_status", "latest_plan_id",
    "active_subscription", "subscription_tenure_months", "domain_count", "service_mix",
    "engagement_score", "behavior_segment", "engagement_trend_pct", "behavior_risk",
    "behavior_risk_color", "member_rank", "member_rank_order", "member_rank_color",
    "gold_plus_flag", "high_spend_low_engagement_flag", "next_best_action", "profile_note",
]

CUSTOMER_ACTIVITY_COLUMNS = [
    "event_id", "customer_id", "occurred_at", "event_date_utc", "event_type", "domain",
    "action", "activity_label", "activity_detail", "activity_result", "activity_color",
    "source", "device_type", "content_id", "destination_id", "plan_id", "quantity",
    "amount", "currency", "event_count",
]

CUSTOMER_AFFINITY_COLUMNS = [
    "customer_id", "affinity_name", "affinity_score", "affinity_rank", "affinity_color",
    "is_preferred",
]

CUSTOMER_RANK_SHARE_COLUMNS = [
    "metric_type", "member_rank", "member_rank_order", "member_rank_color", "metric_value",
    "metric_share", "customer_count", "net_spend_12m",
]


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _decimal(value: object | None) -> Decimal:
    return Decimal("0") if value in (None, "") else Decimal(str(value))


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[dict[str, object]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow(
                {
                    key: (
                        "true" if value is True else
                        "false" if value is False else
                        format(value, "f") if isinstance(value, Decimal) else
                        value
                    )
                    for key, value in row.items()
                }
            )
    return len(materialized)


def _rank_for_spend(net_spend: Decimal) -> tuple[str, int, str]:
    for rank, threshold, order, rank_color in RANK_RULES:
        if net_spend >= threshold:
            return rank, order, rank_color
    raise AssertionError("RANK_RULES must include a zero floor")


def _action(payload: dict[str, Any], event_type: str) -> str:
    field = {
        "user_activity": "activity_type",
        "booking": "booking_status",
        "subscription": "subscription_status",
        "event_attendance": "attendance_status",
    }[event_type]
    return str(payload[field]).lower()


def _activity_copy(event_type: str, payload: dict[str, Any]) -> tuple[str, str, str, str]:
    action = _action(payload, event_type)
    label_map = {
        "play": "Bắt đầu xem", "resume": "Tiếp tục xem", "complete": "Xem hoàn tất",
        "search": "Tìm kiếm nội dung", "initiated": "Bắt đầu đặt vé",
        "confirmed": "Mua vé thành công", "failed": "Thanh toán thất bại",
        "cancelled": "Hủy đặt vé", "refunded": "Hoàn tiền",
        "checked_in": "Tham dự sự kiện", "no_show": "Không tham dự",
        "rejected": "Check-in bị từ chối", "started": "Bắt đầu subscription",
        "renewed": "Gia hạn subscription", "upgraded": "Nâng gói subscription",
        "downgraded": "Hạ gói subscription", "paused": "Tạm dừng subscription",
        "expired": "Subscription hết hạn",
    }
    if action in {"confirmed", "checked_in", "started", "renewed", "upgraded", "complete"}:
        result = "Thành công"
    elif action in {"failed", "rejected", "no_show", "cancelled", "expired"}:
        result = "Thất bại"
    elif action in {"initiated", "paused", "downgraded"}:
        result = "Đang xử lý"
    else:
        result = "Thông tin"
    destination = (
        payload.get("entertainment_event_id") or payload.get("content_id") or
        payload.get("plan_id") or "Không có định danh"
    )
    amount = _decimal(payload.get("amount"))
    detail = str(destination)
    if amount > 0:
        detail += f" • {amount:,.0f} {payload.get('currency') or 'VND'}"
    return action, label_map.get(action, action.replace("_", " ").title()), detail, result


def _behavior_segment(engagement: float, recency_days: int, observed_days: int, domain_count: int) -> str:
    if observed_days <= 21:
        return "New"
    if recency_days > 30:
        return "At Risk"
    if engagement >= 75 and domain_count >= 3:
        return "Champions"
    if engagement >= 60:
        return "Loyal"
    if engagement >= 40:
        return "Growth Potential"
    return "Low Engagement"


def _risk_and_action(
    rank: str,
    engagement: float,
    recency_days: int,
    trend_pct: float,
    latest_subscription_status: str,
) -> tuple[str, str]:
    cancelled = latest_subscription_status in {"cancelled", "expired", "paused"}
    if recency_days > 30 or trend_pct <= -0.45 or cancelled:
        risk = "Cao"
    elif recency_days > 14 or trend_pct <= -0.20 or engagement < 45:
        risk = "Trung bình"
    else:
        risk = "Thấp"
    if rank in HIGH_SPEND_RANKS and risk == "Cao":
        action = "Chiến dịch giữ chân VIP: ưu đãi sự kiện phù hợp"
    elif rank in HIGH_SPEND_RANKS and engagement < 55:
        action = "Nhắc quay lại bằng nội dung và sự kiện phù hợp"
    elif latest_subscription_status in {"cancelled", "expired", "paused"}:
        action = "Kích hoạt lại subscription bằng ưu đãi phù hợp"
    elif engagement >= 70:
        action = "Tăng gắn kết bằng nội dung hoặc sự kiện độc quyền"
    else:
        action = "Gợi ý nội dung và ưu đãi theo sở thích quan sát"
    return risk, action


def build_customer_dashboard_tables(
    output_dir: Path,
    *,
    events: Sequence[dict[str, Any]],
    snapshot_at: datetime,
    seed: int = DEFAULT_RANDOM_SEED,
    customer_pool_size: int = DEFAULT_CUSTOMER_POOL_SIZE,
) -> dict[str, int]:
    """Render all reusable customer dashboard tables from one event snapshot."""
    by_customer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in events:
        by_customer[item["payload"]["customer_id"]].append(item)
    customer_ids = [f"customer-{index:04d}" for index in range(1, customer_pool_size + 1)]
    customer_ids = sorted(set(customer_ids) | set(by_customer))

    customer_rows: list[dict[str, object]] = []
    activity_rows: list[dict[str, object]] = []
    affinity_rows: list[dict[str, object]] = []
    active_statuses = {"started", "renewed", "upgraded", "downgraded"}

    for customer_index, customer_id in enumerate(customer_ids, start=1):
        customer_events = sorted(
            by_customer.get(customer_id, []),
            key=lambda item: (_parse_utc(item["payload"]["occurred_at"]), item["payload"]["event_id"]),
        )
        rng = random.Random(seed + customer_index * 104_729)
        event_times = [_parse_utc(item["payload"]["occurred_at"]) for item in customer_events]
        first_seen = min(event_times, default=snapshot_at - timedelta(days=rng.randint(30, 360)))
        last_seen = max(event_times, default=first_seen)
        observed_days = max(1, (last_seen.date() - first_seen.date()).days + 1)
        recency_days = max(0, (snapshot_at.date() - last_seen.date()).days)

        content_events = [item for item in customer_events if item["event_type"] == "user_activity"]
        bookings = [item for item in customer_events if item["event_type"] == "booking"]
        attendance = [item for item in customer_events if item["event_type"] == "event_attendance"]
        subscriptions = [item for item in customer_events if item["event_type"] == "subscription"]
        booking_statuses = Counter(item["payload"]["booking_status"] for item in bookings)
        attendance_statuses = Counter(item["payload"]["attendance_status"] for item in attendance)
        content_counts = Counter(
            item["payload"].get("content_id") for item in content_events if item["payload"].get("content_id")
        )
        favorite_content = ""
        if content_counts:
            favorite_content = sorted(content_counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]

        latest_subscription = max(
            subscriptions,
            key=lambda item: (_parse_utc(item["payload"]["occurred_at"]), item["payload"]["event_id"]),
            default=None,
        )
        latest_status = "none" if latest_subscription is None else latest_subscription["payload"]["subscription_status"]
        latest_plan = "none" if latest_subscription is None else latest_subscription["payload"]["plan_id"]
        active_subscription = latest_status in active_statuses

        confirmed_amount = sum(
            (_decimal(item["payload"].get("amount")) for item in bookings
             if item["payload"]["booking_status"] == "confirmed"),
            Decimal("0"),
        )
        observed_refunds = sum(
            (_decimal(item["payload"].get("amount")) for item in bookings
             if item["payload"]["booking_status"] == "refunded"),
            Decimal("0"),
        )
        confirmed_tickets = sum(
            int(item["payload"].get("quantity") or 0) for item in bookings
            if item["payload"]["booking_status"] == "confirmed"
        )
        positive_subscription_amount = sum(
            (_decimal(item["payload"].get("amount")) for item in subscriptions
             if item["payload"]["subscription_status"] in active_statuses),
            Decimal("0"),
        )

        historical_spend = Decimal(str(rng.lognormvariate(math.log(float(HISTORICAL_SPEND_MEDIAN)), HISTORICAL_SPEND_SIGMA)))
        historical_spend = min(historical_spend, MAX_NET_SPEND_12M)
        activity_factor = min(Decimal("1.50"), Decimal("0.70") + Decimal(len(customer_events)) / Decimal("20"))
        historical_spend *= activity_factor
        plan_fee = PLAN_MONTHLY_FEES.get(latest_plan, Decimal("0"))
        tenure_months = 0
        if subscriptions:
            tenure_months = min(12, max(1, observed_days // 30 + rng.randint(1, 5)))
        elif active_subscription:
            tenure_months = rng.randint(2, 12)
        subscription_spend = max(positive_subscription_amount, plan_fee * tenure_months)
        content_spend = Decimal("0")
        if content_events:
            content_spend = Decimal(rng.choice([0, 99000, 149000, 199000, 299000])) * max(1, len(content_events) // 3)
        ticket_weight = Decimal("0.65") if bookings or attendance else Decimal("0.30")
        ticket_spend = confirmed_amount + historical_spend * ticket_weight
        subscription_spend += historical_spend * (Decimal("0.25") if subscriptions or active_subscription else Decimal("0.10"))
        content_spend += historical_spend * (Decimal("0.20") if content_events else Decimal("0.05"))
        refund_value = observed_refunds
        if bookings and rng.random() < 0.12:
            refund_value += min(ticket_spend * Decimal("0.08"), Decimal("450000"))
        gross_spend = ticket_spend + subscription_spend + content_spend
        refund_value = min(refund_value, gross_spend)
        net_spend = max(Decimal("0"), gross_spend - refund_value)
        if net_spend > MAX_NET_SPEND_12M:
            target_gross = MAX_NET_SPEND_12M + refund_value
            scale = target_gross / gross_spend
            ticket_spend *= scale
            subscription_spend *= scale
            content_spend *= scale
            net_spend = MAX_NET_SPEND_12M
        rank, rank_order, rank_color = _rank_for_spend(net_spend)

        current_cutoff = snapshot_at - timedelta(days=TREND_WINDOW_DAYS)
        previous_cutoff = snapshot_at - timedelta(days=TREND_WINDOW_DAYS * 2)
        current_events = sum(_parse_utc(item["payload"]["occurred_at"]) > current_cutoff for item in customer_events)
        previous_events = sum(
            previous_cutoff < _parse_utc(item["payload"]["occurred_at"]) <= current_cutoff
            for item in customer_events
        )
        trend_pct = _ratio(current_events - previous_events, max(previous_events, 1))
        sessions = len({item["payload"].get("session_id") for item in content_events if item["payload"].get("session_id")})
        watch_seconds = sum(_decimal(item["payload"].get("position_seconds")) for item in content_events)
        watch_hours = float(watch_seconds / Decimal("3600")) + len(content_events) * rng.uniform(1.2, 3.8)
        completion_events = sum(item["payload"]["activity_type"] == "complete" for item in content_events)
        # Every completion implies a play, even when its play event fell outside the sample.
        play_events = max(completion_events, sum(item["payload"]["activity_type"] == "play" for item in content_events))
        search_events = sum(item["payload"]["activity_type"] == "search" for item in content_events)
        active_days = len({_parse_utc(item["payload"]["occurred_at"]).date() for item in customer_events})
        domain_count = len({item["event_type"] for item in customer_events})
        recency_component = max(0.0, 100.0 - recency_days * 2.5)
        frequency_component = min(100.0, len(customer_events) * 9.0)
        breadth_component = min(100.0, domain_count * 25.0)
        completion_component = min(100.0, _ratio(completion_events, max(play_events, 1)) * 100.0)
        engagement = round(
            0.35 * recency_component + 0.30 * frequency_component +
            0.20 * breadth_component + 0.15 * completion_component,
            1,
        )
        segment = _behavior_segment(engagement, recency_days, observed_days, domain_count)
        risk, next_action = _risk_and_action(rank, engagement, recency_days, trend_pct, latest_status)
        high_spend_low_engagement = rank in HIGH_SPEND_RANKS and (engagement < LOW_ENGAGEMENT_THRESHOLD or risk == "Cao")

        service_labels = []
        if content_events:
            service_labels.append("Streaming")
        if bookings:
            service_labels.append("Ticketing")
        if attendance:
            service_labels.append("Events")
        if subscriptions:
            service_labels.append("Membership")
        service_mix = ", ".join(service_labels) if service_labels else "Observed only"
        preferred_device = Counter(
            item["payload"].get("device_type") for item in content_events if item["payload"].get("device_type")
        ).most_common(1)
        preferred_device_value = preferred_device[0][0] if preferred_device else DEVICES[customer_index % len(DEVICES)]

        customer_rows.append(
            {
                "customer_id": customer_id,
                "unified_customer_id": f"UC-{customer_index:07d}",
                "region": REGIONS[(customer_index * 7) % len(REGIONS)],
                "consent_status": "Đã đồng ý" if customer_index % 11 else "Hạn chế marketing",
                "preferred_device": preferred_device_value,
                "first_seen_at": _iso(first_seen), "last_seen_at": _iso(last_seen),
                "observed_days": observed_days, "recency_days": recency_days,
                "total_events": len(customer_events), "activity_events": len(content_events),
                "active_days": active_days, "sessions": sessions,
                "watch_hours_90d": round(watch_hours, 2), "play_events": play_events,
                "completion_events": completion_events,
                "completion_rate": round(_ratio(completion_events, max(play_events, 1)), 4),
                "search_events": search_events, "favorite_content_id": favorite_content,
                "booking_state_events": len(bookings), "confirmed_bookings": booking_statuses["confirmed"],
                "refunded_bookings": booking_statuses["refunded"], "failed_bookings": booking_statuses["failed"],
                "confirmed_tickets": confirmed_tickets,
                "ticket_spend_12m": ticket_spend.quantize(Decimal("1")),
                "subscription_spend_12m": subscription_spend.quantize(Decimal("1")),
                "content_spend_12m": content_spend.quantize(Decimal("1")),
                "refund_value_12m": refund_value.quantize(Decimal("1")),
                "net_spend_12m": net_spend.quantize(Decimal("1")),
                "lifetime_value_proxy": (net_spend * Decimal(str(1.2 + min(observed_days, 365) / 365))).quantize(Decimal("1")),
                "contribution_margin_proxy": (net_spend * Decimal("0.56")).quantize(Decimal("1")),
                "attendance_records": len(attendance), "checked_in_events": attendance_statuses["checked_in"],
                "no_show_events": attendance_statuses["no_show"],
                "attendance_rate": round(_ratio(attendance_statuses["checked_in"], len(attendance)), 4),
                "subscription_events": len(subscriptions), "latest_subscription_status": latest_status,
                "latest_plan_id": latest_plan, "active_subscription": active_subscription,
                "subscription_tenure_months": tenure_months, "domain_count": domain_count,
                "service_mix": service_mix, "engagement_score": engagement,
                "behavior_segment": segment, "engagement_trend_pct": round(trend_pct, 4),
                "behavior_risk": risk, "behavior_risk_color": RISK_COLORS[risk],
                "member_rank": rank, "member_rank_order": rank_order, "member_rank_color": rank_color,
                "gold_plus_flag": rank in {"Diamond", "Platinum", "Gold"},
                "high_spend_low_engagement_flag": high_spend_low_engagement,
                "next_best_action": next_action,
                "profile_note": "Synthetic demo: Rank chỉ dựa trên Net Spend 12M; hành vi được phân tích độc lập.",
            }
        )

        genre_scores = {genre: rng.uniform(18, 48) for genre in AFFINITY_COLORS}
        for item in content_events:
            content_id = str(item["payload"].get("content_id") or "content-0000")
            digits = "".join(char for char in content_id if char.isdigit())
            genre = tuple(AFFINITY_COLORS)[int(digits or 0) % len(AFFINITY_COLORS)]
            genre_scores[genre] += 14
        genre_scores["Concert"] += 10 * (len(bookings) + len(attendance))
        if "family" in latest_plan:
            genre_scores["Family"] += 18
        ordered_affinity = sorted(genre_scores.items(), key=lambda pair: (-pair[1], pair[0]))
        peak = max(score for _, score in ordered_affinity)
        for affinity_rank, (genre, score) in enumerate(ordered_affinity, start=1):
            affinity_rows.append(
                {
                    "customer_id": customer_id, "affinity_name": genre,
                    "affinity_score": round(min(100.0, score / peak * 100.0), 1),
                    "affinity_rank": affinity_rank, "affinity_color": AFFINITY_COLORS[genre],
                    "is_preferred": affinity_rank == 1,
                }
            )

        for item in customer_events[-RECENT_ACTIVITY_ROWS_PER_CUSTOMER:]:
            payload = item["payload"]
            occurred_at = _parse_utc(payload["occurred_at"])
            action, label, detail, result = _activity_copy(item["event_type"], payload)
            activity_rows.append(
                {
                    "event_id": payload["event_id"], "customer_id": customer_id,
                    "occurred_at": _iso(occurred_at), "event_date_utc": occurred_at.date().isoformat(),
                    "event_type": item["event_type"],
                    "domain": {
                        "user_activity": "Streaming", "booking": "Ticketing",
                        "event_attendance": "Events", "subscription": "Membership",
                    }[item["event_type"]],
                    "action": action, "activity_label": label, "activity_detail": detail,
                    "activity_result": result, "activity_color": ACTIVITY_COLORS[result],
                    "source": payload.get("source") or "", "device_type": payload.get("device_type") or "",
                    "content_id": payload.get("content_id") or "",
                    "destination_id": payload.get("entertainment_event_id") or payload.get("content_id") or "",
                    "plan_id": payload.get("plan_id") or "", "quantity": int(payload.get("quantity") or 0),
                    "amount": _decimal(payload.get("amount")), "currency": payload.get("currency") or "",
                    "event_count": 1,
                }
            )

    rank_aggregate: dict[str, dict[str, object]] = {
        rank: {"order": order, "color": rank_color, "customers": 0, "spend": Decimal("0")}
        for rank, _, order, rank_color in RANK_RULES
    }
    for row in customer_rows:
        aggregate = rank_aggregate[str(row["member_rank"])]
        aggregate["customers"] = int(aggregate["customers"]) + 1
        aggregate["spend"] = _decimal(aggregate["spend"]) + _decimal(row["net_spend_12m"])
    total_customers = len(customer_rows)
    total_spend = sum((_decimal(row["net_spend_12m"]) for row in customer_rows), Decimal("0"))
    rank_share_rows: list[dict[str, object]] = []
    for metric_type in ("Tỷ lệ khách hàng", "Tỷ lệ chi tiêu"):
        for rank, _, order, rank_color in RANK_RULES:
            aggregate = rank_aggregate[rank]
            metric_value = aggregate["customers"] if metric_type == "Tỷ lệ khách hàng" else aggregate["spend"]
            denominator = total_customers if metric_type == "Tỷ lệ khách hàng" else total_spend
            rank_share_rows.append(
                {
                    "metric_type": metric_type, "member_rank": rank, "member_rank_order": order,
                    "member_rank_color": rank_color, "metric_value": metric_value,
                    "metric_share": round(_ratio(float(metric_value), float(denominator)), 6),
                    "customer_count": aggregate["customers"], "net_spend_12m": aggregate["spend"],
                }
            )

    counts = {
        "customer_360.csv": _write_csv(output_dir / "customer_360.csv", CUSTOMER_360_COLUMNS, customer_rows),
        "customer_activity.csv": _write_csv(output_dir / "customer_activity.csv", CUSTOMER_ACTIVITY_COLUMNS, activity_rows),
        "customer_affinity.csv": _write_csv(output_dir / "customer_affinity.csv", CUSTOMER_AFFINITY_COLUMNS, affinity_rows),
        "customer_rank_share.csv": _write_csv(output_dir / "customer_rank_share.csv", CUSTOMER_RANK_SHARE_COLUMNS, rank_share_rows),
    }
    obsolete = output_dir / "customer_journey.csv"
    if obsolete.exists():
        obsolete.unlink()
    customer_manifest = {
        "classification": "deterministic synthetic customer dashboard demo data",
        "snapshot_at": _iso(snapshot_at), "seed": seed,
        "spend_window_months": SPEND_WINDOW_MONTHS,
        "behavior_window_days": BEHAVIOR_WINDOW_DAYS,
        "rank_rules": [
            {"rank": rank, "minimum_net_spend_12m": str(threshold), "order": order, "color": rank_color}
            for rank, threshold, order, rank_color in RANK_RULES
        ],
        "row_counts": counts,
    }
    (output_dir / "customer_dashboard_manifest.json").write_text(
        json.dumps(customer_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return counts


def _generate_events(
    *, count: int, seed: int, base_time: datetime, event_interval_seconds: float,
    customer_pool_size: int, contracts_dir: Path, validate_contracts: bool,
) -> list[dict[str, Any]]:
    from entertainment_pipeline.generator import EventGenerator
    generator = EventGenerator(
        seed=seed, base_time=base_time, customer_pool_size=customer_pool_size,
        event_interval_seconds=event_interval_seconds,
    )
    registry = None
    if validate_contracts:
        from entertainment_pipeline.contracts import ContractRegistry
        registry = ContractRegistry(contracts_dir)
    events: list[dict[str, Any]] = []
    for generated in generator.iter_events(count=count, event_type="all"):
        payload = dict(generated.payload)
        if registry is not None:
            registry.validate(generated.event_type, payload)
        events.append({"event_type": generated.event_type, "payload": payload})
    return events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/powerbi_demo"))
    parser.add_argument("--count", type=int, default=DEFAULT_EVENT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--base-time", default=DEFAULT_BASE_TIME_UTC)
    parser.add_argument("--event-interval-seconds", type=float, default=DEFAULT_EVENT_INTERVAL_SECONDS)
    parser.add_argument("--customer-pool-size", type=int, default=DEFAULT_CUSTOMER_POOL_SIZE)
    parser.add_argument("--contracts-dir", type=Path, default=Path("contracts/jsonschema"))
    parser.add_argument("--skip-contract-validation", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    events = _generate_events(
        count=args.count, seed=args.seed, base_time=_parse_utc(args.base_time),
        event_interval_seconds=args.event_interval_seconds,
        customer_pool_size=args.customer_pool_size, contracts_dir=args.contracts_dir,
        validate_contracts=not args.skip_contract_validation,
    )
    snapshot_at = max(_parse_utc(item["payload"]["occurred_at"]) for item in events)
    counts = build_customer_dashboard_tables(
        args.output_dir, events=events, snapshot_at=snapshot_at,
        seed=args.seed, customer_pool_size=args.customer_pool_size,
    )
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
