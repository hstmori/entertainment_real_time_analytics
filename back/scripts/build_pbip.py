"""Generate the Entertainment Analytics PBIP source project without opening Desktop."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

try:
    from pbip_colors import apply_colors, color_measures_by_table
except ImportError:  # imported as scripts.build_pbip (tests)
    from scripts.pbip_colors import apply_colors, color_measures_by_table


BASE = "https://developer.microsoft.com/json-schemas/fabric/"
PROJECT_NAME = "EntertainmentAnalytics"


def object_id(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:20]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def literal(value: object) -> dict[str, object]:
    if isinstance(value, bool):
        text = str(value).lower()
    elif isinstance(value, (int, float)):
        text = f"{value}D"
    else:
        text = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def color(value: str) -> dict[str, object]:
    return {"solid": {"color": literal(value)}}


def obj(**kwargs: object) -> list[dict[str, object]]:
    return [{"properties": kwargs}]


def field(table: str, prop: str, measure: bool = False) -> dict[str, object]:
    kind = "Measure" if measure else "Column"
    return {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def projection(table: str, prop: str, measure: bool = False) -> dict[str, object]:
    return {
        "field": field(table, prop, measure),
        "queryRef": f"{table}.{prop}",
        "nativeQueryRef": prop,
    }


TABLE_SPECS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "Date": ("date.csv", [("date", "dateTime")]),
    "ContentEngagement": (
        "content_engagement_hourly.csv",
        [
            ("event_hour_utc", "dateTime"), ("event_date_utc", "dateTime"),
            ("content_id", "string"), ("device_type", "string"),
            ("activity_events", "int64"), ("active_users", "int64"),
            ("play_events", "int64"), ("completion_events", "int64"),
            ("completion_per_play_proxy", "double"), ("observed_position_seconds", "double"),
        ],
    ),
    "BookingFunnel": (
        "booking_funnel_daily.csv",
        [
            ("event_date_utc", "dateTime"), ("destination_type", "string"),
            ("destination_id", "string"), ("booking_type", "string"),
            ("channel", "string"), ("currency", "string"),
            ("booking_state_events", "int64"), ("initiated_events", "int64"),
            ("confirmed_events", "int64"), ("cancelled_events", "int64"),
            ("refunded_events", "int64"), ("failed_events", "int64"),
            ("confirmed_quantity", "int64"), ("refunded_quantity", "int64"),
            ("confirmed_amount", "decimal"), ("refunded_amount", "decimal"),
            ("net_booking_value_proxy", "decimal"), ("confirmation_share_proxy", "double"),
        ],
    ),
    "EventPerformance": (
        "event_performance.csv",
        [
            ("entertainment_event_id", "string"), ("currency", "string"),
            ("confirmed_bookings", "int64"), ("refunded_bookings", "int64"),
            ("confirmed_tickets", "int64"), ("refunded_tickets", "int64"),
            ("net_booking_value_proxy", "decimal"), ("attendance_records", "int64"),
            ("checked_in", "int64"), ("no_show", "int64"), ("rejected", "int64"),
            ("attendance_rate_proxy", "double"), ("no_show_rate_proxy", "double"),
            ("first_booking_event_at", "dateTime"), ("last_booking_event_at", "dateTime"),
            ("first_attendance_event_at", "dateTime"), ("last_attendance_event_at", "dateTime"),
        ],
    ),
    "SubscriptionDaily": (
        "subscription_daily.csv",
        [
            ("event_date_utc", "dateTime"), ("plan_id", "string"), ("currency", "string"),
            ("subscription_events", "int64"), ("started_events", "int64"),
            ("renewed_events", "int64"), ("upgraded_events", "int64"),
            ("downgraded_events", "int64"), ("paused_events", "int64"),
            ("cancelled_events", "int64"), ("expired_events", "int64"),
            ("mrr_event_value_proxy", "decimal"), ("cancelled_value_context", "decimal"),
        ],
    ),
    "Customer360": (
        "customer_360.csv",
        [
            ("customer_id", "string"), ("unified_customer_id", "string"),
            ("region", "string"), ("consent_status", "string"),
            ("preferred_device", "string"), ("first_seen_at", "dateTime"),
            ("last_seen_at", "dateTime"), ("observed_days", "int64"),
            ("recency_days", "int64"), ("total_events", "int64"),
            ("activity_events", "int64"), ("active_days", "int64"),
            ("sessions", "int64"), ("watch_hours_90d", "double"),
            ("play_events", "int64"), ("completion_events", "int64"),
            ("completion_rate", "double"), ("search_events", "int64"),
            ("favorite_content_id", "string"), ("booking_state_events", "int64"),
            ("confirmed_bookings", "int64"), ("refunded_bookings", "int64"),
            ("failed_bookings", "int64"), ("confirmed_tickets", "int64"),
            ("ticket_spend_12m", "decimal"), ("subscription_spend_12m", "decimal"),
            ("content_spend_12m", "decimal"), ("refund_value_12m", "decimal"),
            ("net_spend_12m", "decimal"), ("lifetime_value_proxy", "decimal"),
            ("contribution_margin_proxy", "decimal"), ("attendance_records", "int64"),
            ("checked_in_events", "int64"), ("no_show_events", "int64"),
            ("attendance_rate", "double"), ("subscription_events", "int64"),
            ("latest_subscription_status", "string"), ("latest_plan_id", "string"),
            ("active_subscription", "boolean"), ("subscription_tenure_months", "int64"),
            ("domain_count", "int64"), ("service_mix", "string"),
            ("engagement_score", "double"), ("behavior_segment", "string"),
            ("engagement_trend_pct", "double"), ("behavior_risk", "string"),
            ("behavior_risk_color", "string"), ("member_rank", "string"),
            ("member_rank_order", "int64"), ("member_rank_color", "string"),
            ("gold_plus_flag", "boolean"), ("high_spend_low_engagement_flag", "boolean"),
            ("next_best_action", "string"), ("profile_note", "string"),
        ],
    ),
    "CustomerActivity": (
        "customer_activity.csv",
        [
            ("event_id", "string"), ("customer_id", "string"),
            ("occurred_at", "dateTime"), ("event_date_utc", "dateTime"),
            ("event_type", "string"), ("domain", "string"), ("action", "string"),
            ("activity_label", "string"), ("activity_detail", "string"),
            ("activity_result", "string"), ("activity_color", "string"),
            ("source", "string"), ("device_type", "string"),
            ("content_id", "string"), ("destination_id", "string"),
            ("plan_id", "string"), ("quantity", "int64"),
            ("amount", "decimal"), ("currency", "string"), ("event_count", "int64"),
        ],
    ),
    "CustomerAffinity": (
        "customer_affinity.csv",
        [
            ("customer_id", "string"), ("affinity_name", "string"),
            ("affinity_score", "double"), ("affinity_rank", "int64"),
            ("affinity_color", "string"), ("is_preferred", "boolean"),
        ],
    ),
    "CustomerRankShare": (
        "customer_rank_share.csv",
        [
            ("metric_type", "string"), ("member_rank", "string"),
            ("member_rank_order", "int64"), ("member_rank_color", "string"),
            ("metric_value", "decimal"), ("metric_share", "double"),
            ("customer_count", "int64"), ("net_spend_12m", "decimal"),
        ],
    ),
    "RefreshAudit": (
        "refresh_audit.csv",
        [
            ("run_id", "string"), ("model_name", "string"),
            ("refreshed_at", "dateTime"), ("row_count", "int64"),
            ("silver_snapshot_rows", "int64"), ("status", "string"),
        ],
    ),
    "ExecutiveDaily": (
        "executive_daily.csv",
        [
            ("event_date_utc", "dateTime"), ("business_line", "string"),
            ("gross_value", "decimal"), ("net_revenue", "decimal"),
            ("variable_cost", "decimal"), ("contribution_margin", "decimal"),
            ("refund_value", "decimal"), ("transactions", "int64"),
            ("paying_customers_line", "int64"), ("new_customers", "int64"),
            ("marketing_spend", "decimal"), ("target_revenue", "decimal"),
        ],
    ),
    "StreamingRealtime": (
        "streaming_realtime.csv",
        [
            ("event_time_utc", "dateTime"), ("event_date_utc", "dateTime"),
            ("device_type", "string"), ("region", "string"),
            ("concurrent_viewers", "int64"), ("watch_hours", "decimal"),
            ("play_starts", "int64"), ("completions", "int64"),
            ("total_sessions", "int64"), ("rebuffer_events", "int64"),
            ("start_failures", "int64"), ("subscription_conversions", "int64"),
        ],
    ),
    "ProgramEvent": (
        "program_event.csv",
        [
            ("program_id", "string"), ("program_name", "string"),
            ("program_type", "string"), ("region", "string"),
            ("event_date_utc", "dateTime"), ("capacity", "int64"),
            ("tickets_sold", "int64"), ("ticket_gmv", "decimal"),
            ("service_fee", "decimal"), ("sponsor_revenue", "decimal"),
            ("refund_value", "decimal"), ("variable_cost", "decimal"),
            ("fixed_cost", "decimal"),
            ("contribution_margin", "decimal"), ("attendees", "int64"),
            ("no_shows", "int64"), ("new_customers", "int64"),
            ("member_conversions", "int64"), ("sales_pace_index", "double"),
            ("break_even_progress", "double"), ("forecast_margin_rate", "double"),
            ("program_status", "string"),
        ],
    ),
    "EventSalesPace": (
        "event_sales_pace.csv",
        [
            ("program_id", "string"), ("event_date_utc", "dateTime"),
            ("lead_day", "int64"), ("actual_cumulative_tickets", "int64"),
            ("plan_cumulative_tickets", "int64"), ("forecast_cumulative_tickets", "int64"),
        ],
    ),
    "EventSalesDetail": (
        "event_sales_detail.csv",
        [
            ("program_id", "string"), ("event_date_utc", "dateTime"),
            ("channel", "string"), ("ticket_tier", "string"),
            ("inventory", "int64"), ("sold_tickets", "int64"),
            ("event_views", "int64"), ("seat_selections", "int64"),
            ("payment_attempts", "int64"), ("completed_orders", "int64"),
            ("net_revenue", "decimal"), ("marketing_cost", "decimal"),
        ],
    ),
    "OperationsRealtime": (
        "operations_realtime.csv",
        [
            ("event_time_utc", "dateTime"), ("event_date_utc", "dateTime"),
            ("service_name", "string"), ("requests_per_second", "int64"),
            ("p95_latency_ms", "double"), ("error_rate", "double"),
            ("queue_depth", "int64"), ("throughput_per_minute", "int64"),
            ("data_lag_seconds", "double"), ("status", "string"),
        ],
    ),
}


MEASURES: dict[str, list[tuple[str, str, str]]] = {
    "ContentEngagement": [
        ("Sự kiện hoạt động", "SUM(ContentEngagement[activity_events])", "#,0"),
        ("Lượt phát", "SUM(ContentEngagement[play_events])", "#,0"),
        ("Lượt hoàn tất", "SUM(ContentEngagement[completion_events])", "#,0"),
        ("Tỷ lệ hoàn tất proxy", "DIVIDE([Lượt hoàn tất],[Lượt phát])", "0.0%"),
        ("Vị trí quan sát (giây)", "SUM(ContentEngagement[observed_position_seconds])", "#,0.0"),
    ],
    "BookingFunnel": [
        ("Sự kiện booking", "SUM(BookingFunnel[booking_state_events])", "#,0"),
        ("Booking xác nhận", "SUM(BookingFunnel[confirmed_events])", "#,0"),
        ("Booking hoàn tiền", "SUM(BookingFunnel[refunded_events])", "#,0"),
        ("Booking thất bại", "SUM(BookingFunnel[failed_events])", "#,0"),
        ("Vé xác nhận", "SUM(BookingFunnel[confirmed_quantity])", "#,0"),
        ("Giá trị xác nhận", "SUM(BookingFunnel[confirmed_amount])", "#,0"),
        ("Giá trị hoàn tiền", "SUM(BookingFunnel[refunded_amount])", "#,0"),
        ("Giá trị booking ròng proxy", "SUM(BookingFunnel[net_booking_value_proxy])", "#,0;(#,0)"),
        ("Tỷ trọng xác nhận proxy", "DIVIDE([Booking xác nhận],[Sự kiện booking])", "0.0%"),
    ],
    "EventPerformance": [
        ("Sự kiện live", "DISTINCTCOUNT(EventPerformance[entertainment_event_id])", "#,0"),
        ("Vé live xác nhận", "SUM(EventPerformance[confirmed_tickets])", "#,0"),
        ("Check-in", "SUM(EventPerformance[checked_in])", "#,0"),
        ("No-show", "SUM(EventPerformance[no_show])", "#,0"),
        ("Tỷ lệ tham dự proxy", "DIVIDE([Check-in],SUM(EventPerformance[attendance_records]))", "0.0%"),
    ],
    "SubscriptionDaily": [
        ("Sự kiện subscription", "SUM(SubscriptionDaily[subscription_events])", "#,0"),
        ("Đăng ký mới", "SUM(SubscriptionDaily[started_events])", "#,0"),
        ("Gia hạn", "SUM(SubscriptionDaily[renewed_events])", "#,0"),
        ("Hủy subscription", "SUM(SubscriptionDaily[cancelled_events])", "#,0"),
        ("MRR event value proxy", "SUM(SubscriptionDaily[mrr_event_value_proxy])", "#,0"),
    ],
    "Customer360": [
        ("Khách hàng", "COUNTROWS(Customer360)", "#,0"),
        ("Net Spend 12M", "DIVIDE(SUM(Customer360[net_spend_12m]),1000000)", '#,0.0 "triệu"'),
        ("Net Spend TB 12M", "DIVIDE(AVERAGE(Customer360[net_spend_12m]),1000000)", '#,0.0 "triệu"'),
        ("Customer Value 12M", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),DIVIDE(MAX(Customer360[net_spend_12m]),1000000))", '#,0.0 "triệu"'),
        ("Lifetime Value Proxy", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),DIVIDE(MAX(Customer360[lifetime_value_proxy]),1000000))", '#,0.0 "triệu"'),
        ("Customer Contribution Margin", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),DIVIDE(MAX(Customer360[contribution_margin_proxy]),1000000))", '#,0.0 "triệu"'),
        ("Gold+ Customers", "COALESCE(COUNTROWS(FILTER(Customer360,Customer360[gold_plus_flag]=TRUE())),0)", "#,0"),
        ("Gold+ Customer Share", "DIVIDE([Gold+ Customers],[Khách hàng])", "0.0%"),
        ("Gold+ Spend", "DIVIDE(CALCULATE(SUM(Customer360[net_spend_12m]),Customer360[gold_plus_flag]=TRUE()),1000000)", '#,0.0 "triệu"'),
        ("Gold+ Spend Share", "DIVIDE(CALCULATE(SUM(Customer360[net_spend_12m]),Customer360[gold_plus_flag]=TRUE()),SUM(Customer360[net_spend_12m]))", "0.0%"),
        ("Khách đa dịch vụ", "COALESCE(COUNTROWS(FILTER(Customer360,Customer360[domain_count]>=3)),0)", "#,0"),
        ("Tỷ lệ khách đa dịch vụ", "DIVIDE([Khách đa dịch vụ],[Khách hàng])", "0.0%"),
        ("High-spend giảm tương tác", "COALESCE(COUNTROWS(FILTER(Customer360,Customer360[high_spend_low_engagement_flag]=TRUE())),0)", "#,0"),
        ("Engagement Score", "AVERAGE(Customer360[engagement_score])", "0.0"),
        ("Engagement Score Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[engagement_score]))", "0.0"),
        ("Total Activities Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[total_events]))", "#,0"),
        ("Watch Hours Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[watch_hours_90d]))", "#,0.0"),
        ("Watch Hours TB", "AVERAGE(Customer360[watch_hours_90d])", "#,0.0"),
        ("Sessions Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[sessions]))", "#,0"),
        ("Confirmed Tickets Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[confirmed_tickets]))", "#,0"),
        ("Bookings TB", "AVERAGE(Customer360[confirmed_bookings])", "0.0"),
        ("Attendance Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[checked_in_events]))", "#,0"),
        ("Attendance TB", "AVERAGE(Customer360[checked_in_events])", "0.0"),
        ("Subscription Events Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[subscription_events]))", "#,0"),
        ("Subscription Activity TB", "AVERAGE(Customer360[subscription_events])", "0.0"),
        ("Completion Rate Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[completion_rate]))", "0.0%"),
        ("Recency TB (ngày)", "AVERAGE(Customer360[recency_days])", "0.0"),
        ("Recency Profile", "IF(ISFILTERED(Customer360[customer_id]) && HASONEVALUE(Customer360[customer_id]),MAX(Customer360[recency_days]))", "#,0 ngày"),
        ("Active Subscription Customers", "COALESCE(COUNTROWS(FILTER(Customer360,Customer360[active_subscription]=TRUE())),0)", "#,0"),
        ("Member Rank Profile", "SELECTEDVALUE(Customer360[member_rank],\"Chọn 1 khách hàng\")", ""),
        ("Behavior Risk Profile", "SELECTEDVALUE(Customer360[behavior_risk],\"Chọn 1 khách hàng\")", ""),
    ],
    "CustomerActivity": [
        ("Customer Activities", "SUM(CustomerActivity[event_count])", "#,0"),
        ("Activity Amount", "DIVIDE(SUM(CustomerActivity[amount]),1000000)", '#,0.0 "triệu"'),
    ],
    "CustomerAffinity": [
        ("Affinity Score", "AVERAGE(CustomerAffinity[affinity_score])", "0.0"),
    ],
    "CustomerRankShare": [
        ("Rank Share", "VAR Metric=SELECTEDVALUE(CustomerRankShare[metric_type]) VAR Ranks=VALUES(CustomerRankShare[member_rank]) VAR Part=IF(Metric=\"Tỷ lệ chi tiêu\",CALCULATE(SUM(Customer360[net_spend_12m]),KEEPFILTERS(TREATAS(Ranks,Customer360[member_rank]))),CALCULATE(COUNTROWS(Customer360),KEEPFILTERS(TREATAS(Ranks,Customer360[member_rank])))) VAR Total=IF(Metric=\"Tỷ lệ chi tiêu\",SUM(Customer360[net_spend_12m]),COUNTROWS(Customer360)) RETURN DIVIDE(Part,Total)", "0.0%"),
        ("Rank Customer Count", "MAX(CustomerRankShare[customer_count])", "#,0"),
        ("Rank Spend", "DIVIDE(MAX(CustomerRankShare[net_spend_12m]),1000000)", '#,0.0 "triệu"'),
    ],
    "RefreshAudit": [
        ("Số lần refresh", "DISTINCTCOUNT(RefreshAudit[run_id])", "#,0"),
        ("Refresh gần nhất", "MAX(RefreshAudit[refreshed_at])", "dd/MM/yyyy HH:mm"),
        ("Models đã refresh", "COUNTROWS(RefreshAudit)", "#,0"),
    ],
    "ExecutiveDaily": [
        ("Gross Value", "DIVIDE(SUM(ExecutiveDaily[gross_value]),1000000000)", '#,0.0 "tỷ"'),
        ("Doanh thu thuần", "DIVIDE(SUM(ExecutiveDaily[net_revenue]),1000000000)", '#,0.0 "tỷ"'),
        ("Chi phí biến đổi", "DIVIDE(SUM(ExecutiveDaily[variable_cost]),1000000000)", '#,0.0 "tỷ"'),
        ("Contribution Margin", "DIVIDE(SUM(ExecutiveDaily[contribution_margin]),1000000000)", '#,0.0 "tỷ"'),
        ("Contribution Margin %", "DIVIDE([Contribution Margin],[Doanh thu thuần])", "0.0%"),
        ("Hoàn tiền", "DIVIDE(SUM(ExecutiveDaily[refund_value]),1000000000)", '#,0.0 "tỷ"'),
        ("Giao dịch", "SUM(ExecutiveDaily[transactions])", "#,0"),
        ("Khách trả tiền theo dịch vụ", "SUM(ExecutiveDaily[paying_customers_line])", "#,0"),
        ("Khách mới", "SUM(ExecutiveDaily[new_customers])", "#,0"),
        ("Marketing Spend", "DIVIDE(SUM(ExecutiveDaily[marketing_spend]),1000000000)", '#,0.0 "tỷ"'),
        ("Mục tiêu doanh thu", "DIVIDE(SUM(ExecutiveDaily[target_revenue]),1000000000)", '#,0.0 "tỷ"'),
        ("Tiến độ mục tiêu", "DIVIDE([Doanh thu thuần],[Mục tiêu doanh thu])", "0.0%"),
    ],
    "StreamingRealtime": [
        ("Concurrent Viewers", "VAR T=MAX(StreamingRealtime[event_time_utc]) RETURN CALCULATE(SUM(StreamingRealtime[concurrent_viewers]),StreamingRealtime[event_time_utc]=T)", "#,0"),
        ("Watch Hours", "SUM(StreamingRealtime[watch_hours])", "#,0.0"),
        ("Play Starts", "SUM(StreamingRealtime[play_starts])", "#,0"),
        ("Streaming Completions", "SUM(StreamingRealtime[completions])", "#,0"),
        ("Completion Rate", "DIVIDE([Streaming Completions],[Play Starts])", "0.0%"),
        ("Streaming Sessions", "SUM(StreamingRealtime[total_sessions])", "#,0"),
        ("Rebuffer Ratio", "DIVIDE(SUM(StreamingRealtime[rebuffer_events]),[Streaming Sessions])", "0.00%"),
        ("Video Start Failure", "DIVIDE(SUM(StreamingRealtime[start_failures]),[Streaming Sessions])", "0.00%"),
        ("Streaming Conversion", "DIVIDE(SUM(StreamingRealtime[subscription_conversions]),[Streaming Sessions])", "0.00%"),
    ],
    "ProgramEvent": [
        ("Số chương trình", "DISTINCTCOUNT(ProgramEvent[program_id])", "#,0"),
        ("Sức chứa", "SUM(ProgramEvent[capacity])", "#,0"),
        ("Vé đã bán", "SUM(ProgramEvent[tickets_sold])", "#,0"),
        ("Sell-through Rate", "DIVIDE([Vé đã bán],[Sức chứa])", "0.0%"),
        ("Ticket GMV", "DIVIDE(SUM(ProgramEvent[ticket_gmv]),1000000000)", '#,0.0 "tỷ"'),
        ("Doanh thu sự kiện", "DIVIDE(SUM(ProgramEvent[ticket_gmv])+SUM(ProgramEvent[service_fee])+SUM(ProgramEvent[sponsor_revenue])-SUM(ProgramEvent[refund_value]),1000000000)", '#,0.0 "tỷ"'),
        ("Event Contribution Margin", "DIVIDE(SUM(ProgramEvent[contribution_margin]),1000000000)", '#,0.0 "tỷ"'),
        ("Event Margin %", "DIVIDE([Event Contribution Margin],[Doanh thu sự kiện])", "0.0%"),
        ("Khách tham gia", "SUM(ProgramEvent[attendees])", "#,0"),
        ("No-show Rate", "DIVIDE(SUM(ProgramEvent[no_shows]),SUM(ProgramEvent[attendees])+SUM(ProgramEvent[no_shows]))", "0.0%"),
        ("Sales Pace Index", "AVERAGE(ProgramEvent[sales_pace_index])", "0.00"),
        ("Tiến độ hòa vốn", "DIVIDE(SUM(ProgramEvent[contribution_margin]),SUM(ProgramEvent[fixed_cost]))", "0.0%"),
        ("Chương trình đạt kế hoạch", "CALCULATE([Số chương trình],ProgramEvent[program_status]=\"Đúng kế hoạch\")", "#,0"),
        ("Tỷ lệ đạt kế hoạch", "DIVIDE([Chương trình đạt kế hoạch],[Số chương trình])", "0.0%"),
        ("Member Conversions", "SUM(ProgramEvent[member_conversions])", "#,0"),
    ],
    "EventSalesPace": [
        ("Vé tích lũy thực tế", "SUM(EventSalesPace[actual_cumulative_tickets])", "#,0"),
        ("Vé tích lũy kế hoạch", "SUM(EventSalesPace[plan_cumulative_tickets])", "#,0"),
        ("Vé forecast", "SUM(EventSalesPace[forecast_cumulative_tickets])", "#,0"),
    ],
    "EventSalesDetail": [
        ("Tổng Inventory", "SUM(EventSalesDetail[inventory])", "#,0"),
        ("Vé bán chi tiết", "SUM(EventSalesDetail[sold_tickets])", "#,0"),
        ("Event Views", "SUM(EventSalesDetail[event_views])", "#,0"),
        ("Seat Selections", "SUM(EventSalesDetail[seat_selections])", "#,0"),
        ("Payment Attempts", "SUM(EventSalesDetail[payment_attempts])", "#,0"),
        ("Completed Orders", "SUM(EventSalesDetail[completed_orders])", "#,0"),
        ("Funnel Conversion", "DIVIDE([Completed Orders],[Event Views])", "0.0%"),
        ("Sales Net Revenue", "DIVIDE(SUM(EventSalesDetail[net_revenue]),1000000000)", '#,0.0 "tỷ"'),
        ("Sales Marketing Cost", "DIVIDE(SUM(EventSalesDetail[marketing_cost]),1000000000)", '#,0.0 "tỷ"'),
        ("ROAS", "DIVIDE([Sales Net Revenue],[Sales Marketing Cost])", "0.00"),
    ],
    "OperationsRealtime": [
        ("P95 Latency cao nhất", "MAX(OperationsRealtime[p95_latency_ms])", "#,0 ms"),
        ("Trạng thái hiện tại", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN IF(CALCULATE(COUNTROWS(OperationsRealtime),OperationsRealtime[event_time_utc]=T,OperationsRealtime[status]=\"Cảnh báo\")>0,\"Cảnh báo\",\"Ổn định\")", ""),
        ("Current RPS", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN CALCULATE(SUM(OperationsRealtime[requests_per_second]),OperationsRealtime[event_time_utc]=T)", "#,0"),
        ("P95 Latency", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN CALCULATE(MAX(OperationsRealtime[p95_latency_ms]),OperationsRealtime[event_time_utc]=T)", "#,0 ms"),
        ("Error Rate", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN CALCULATE(DIVIDE(SUMX(OperationsRealtime,OperationsRealtime[error_rate]*OperationsRealtime[requests_per_second]),SUM(OperationsRealtime[requests_per_second])),OperationsRealtime[event_time_utc]=T)", "0.00%"),
        ("Queue Depth", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN CALCULATE(SUM(OperationsRealtime[queue_depth]),OperationsRealtime[event_time_utc]=T)", "#,0"),
        ("Throughput / phút", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN CALCULATE(SUM(OperationsRealtime[throughput_per_minute]),OperationsRealtime[event_time_utc]=T)", "#,0"),
        ("Data Lag", "VAR T=MAX(OperationsRealtime[event_time_utc]) RETURN CALCULATE(MAX(OperationsRealtime[data_lag_seconds]),OperationsRealtime[event_time_utc]=T)", "#,0.0 s"),
        ("Dịch vụ cảnh báo", "CALCULATE(DISTINCTCOUNT(OperationsRealtime[service_name]),OperationsRealtime[status]=\"Cảnh báo\")", "#,0"),
    ],
}


VISIBLE_COLUMNS = {
    "Date": {"date"},
    "ContentEngagement": {"event_date_utc", "content_id", "device_type"},
    "BookingFunnel": {"event_date_utc", "destination_type", "destination_id", "booking_type", "channel", "currency"},
    "EventPerformance": {"entertainment_event_id", "currency"},
    "SubscriptionDaily": {"event_date_utc", "plan_id", "currency"},
    "Customer360": {
        "customer_id", "unified_customer_id", "region", "consent_status", "preferred_device",
        "first_seen_at", "last_seen_at", "recency_days", "favorite_content_id",
        "latest_subscription_status", "latest_plan_id", "active_subscription",
        "domain_count", "service_mix", "behavior_segment", "behavior_risk",
        "member_rank", "member_rank_order", "member_rank_color", "next_best_action",
    },
    "CustomerActivity": {
        "customer_id", "occurred_at", "event_date_utc", "domain", "activity_label",
        "activity_detail", "activity_result", "activity_color", "device_type",
        "content_id", "destination_id", "plan_id", "amount", "currency",
    },
    "CustomerAffinity": {"customer_id", "affinity_name", "affinity_rank", "affinity_color", "is_preferred"},
    "CustomerRankShare": {"metric_type", "member_rank", "member_rank_order", "member_rank_color"},
    "RefreshAudit": {"run_id", "model_name", "refreshed_at", "status"},
    "ExecutiveDaily": {"event_date_utc", "business_line"},
    "StreamingRealtime": {"event_time_utc", "event_date_utc", "device_type", "region"},
    "ProgramEvent": {"program_id", "program_name", "program_type", "region", "event_date_utc", "program_status"},
    "EventSalesPace": {"program_id", "event_date_utc", "lead_day"},
    "EventSalesDetail": {"program_id", "event_date_utc", "channel", "ticket_tier"},
    "OperationsRealtime": {"event_time_utc", "event_date_utc", "service_name", "status"},
}


def build_model(data_dir: Path) -> dict[str, object]:
    m_types = {
        "string": "type text", "int64": "Int64.Type", "double": "type number",
        "decimal": "type number", "dateTime": "type datetimezone", "boolean": "type logical",
    }
    tables: list[dict[str, object]] = []
    for name, (filename, columns) in TABLE_SPECS.items():
        selected = ", ".join(f'"{column}"' for column, _ in columns)
        types = ", ".join(f'{{"{column}", {m_types[data_type]}}}' for column, data_type in columns)
        expression = f'''let
    Source = Csv.Document(File.Contents(DataRoot & "\\{filename}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Selected = Table.SelectColumns(Headers, {{{selected}}}),
    Typed = Table.TransformColumnTypes(Selected, {{{types}}}, "en-US")
in
    Typed'''
        table_columns = []
        for column_name, data_type in columns:
            column = {
                "name": column_name,
                "dataType": data_type,
                "sourceColumn": column_name,
                "summarizeBy": "none",
                "isHidden": column_name not in VISIBLE_COLUMNS[name],
            }
            if data_type == "dateTime":
                column["formatString"] = "dd/MM/yyyy HH:mm"
            table_columns.append(column)
        tables.append(
            {
                "name": name,
                "description": f"Governed Gold export: {filename}. Definitions: docs/gold-metric-definitions.md.",
                "columns": table_columns,
                "measures": [
                    {"name": measure, "expression": expression, "formatString": format_string, "displayFolder": "Dashboard"}
                    for measure, expression, format_string in MEASURES.get(name, [])
                ] + [
                    {"name": measure, "expression": expression, "displayFolder": "Formatting"}
                    for measure, expression in color_measures_by_table().get(name, [])
                ],
                "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expression}}],
            }
        )

    relationships = [
        {
            "name": f"Date_{table}",
            "fromTable": table,
            "fromColumn": "event_date_utc",
            "toTable": "Date",
            "toColumn": "date",
            "crossFilteringBehavior": "oneDirection",
        }
        for table in (
            "ContentEngagement", "BookingFunnel", "SubscriptionDaily", "ExecutiveDaily",
            "StreamingRealtime", "ProgramEvent", "OperationsRealtime",
        )
    ]
    relationships.extend(
        [
            {
                "name": "Date_CustomerActivity",
                "fromTable": "CustomerActivity",
                "fromColumn": "event_date_utc",
                "toTable": "Date",
                "toColumn": "date",
                "crossFilteringBehavior": "oneDirection",
            },
            {
                "name": "Customer360_CustomerActivity",
                "fromTable": "CustomerActivity",
                "fromColumn": "customer_id",
                "toTable": "Customer360",
                "toColumn": "customer_id",
                "crossFilteringBehavior": "oneDirection",
            },
            {
                "name": "Customer360_CustomerAffinity",
                "fromTable": "CustomerAffinity",
                "fromColumn": "customer_id",
                "toTable": "Customer360",
                "toColumn": "customer_id",
                "crossFilteringBehavior": "oneDirection",
            },
            {
                "name": "ProgramEvent_EventSalesPace",
                "fromTable": "EventSalesPace",
                "fromColumn": "program_id",
                "toTable": "ProgramEvent",
                "toColumn": "program_id",
                "crossFilteringBehavior": "oneDirection",
            },
            {
                "name": "ProgramEvent_EventSalesDetail",
                "fromTable": "EventSalesDetail",
                "fromColumn": "program_id",
                "toTable": "ProgramEvent",
                "toColumn": "program_id",
                "crossFilteringBehavior": "oneDirection",
            },
        ]
    )
    return {
        "name": PROJECT_NAME,
        "compatibilityLevel": 1600,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps(list(TABLE_SPECS))},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                {"name": "PBI_ProTooling", "value": json.dumps(["MCP-PBIModeling", "DevMode"])},
                {"name": "PBIDesktopVersion", "value": "2.142.1277.0 (25.04)+014fde450f93691fc9537f0758d73d1c5df153ef"},
            ],
            "expressions": [
                {
                    "name": "DataRoot",
                    "kind": "m",
                    "expression": '"' + str(data_dir).replace('"', '""') + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                }
            ],
            "tables": tables,
            "relationships": relationships,
        },
    }


def build_report(root: Path) -> None:
    report = root / f"{PROJECT_NAME}.Report"
    definition = report / "definition"
    write_json(
        root / f"{PROJECT_NAME}.pbip",
        {"version": "1.0", "artifacts": [{"report": {"path": f"{PROJECT_NAME}.Report"}}], "settings": {"enableAutoRecovery": True}},
    )
    write_json(
        report / "definition.pbir",
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{PROJECT_NAME}.SemanticModel"}}},
    )
    write_json(root / f"{PROJECT_NAME}.SemanticModel" / "definition.pbism", {"version": "4.0", "settings": {}})
    write_json(definition / "version.json", {"$schema": BASE + "item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write_json(
        definition / "report.json",
        {
            "$schema": BASE + "item/report/definition/report/1.2.0/schema.json",
            "themeCollection": {"baseTheme": {"name": "CY24SU06", "reportVersionAtImport": "5.55", "type": "SharedResources"}},
            "layoutOptimization": "None",
            "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": True},
        },
    )

    pages = [
        ("overview", "Trung tâm điều hành"),
        ("revenue", "Doanh thu & Lợi nhuận"),
        ("content", "Streaming"),
        ("booking_event", "Vé & Sự kiện"),
        ("program_portfolio", "Hiệu quả Chương trình"),
        ("event_detail", "Chi tiết Sự kiện"),
        ("membership", "Thành viên"),
        ("customer_portfolio", "Customer Portfolio & Spend Ranking"),
        ("customer_profile", "Customer 360 Profile"),
        ("operations", "Vận hành Real-time"),
    ]
    write_json(
        definition / "pages" / "pages.json",
        {"$schema": BASE + "item/report/definition/pagesMetadata/1.0.0/schema.json", "pageOrder": [object_id(slug) for slug, _ in pages], "activePageName": object_id("overview")},
    )

    for page_slug, display_name in pages:
        page_id = object_id(page_slug)
        page_dir = definition / "pages" / page_id
        visuals: list[dict[str, object]] = []

        def add(name: str, kind: str, x: int, y: int, width: int, height: int, title: str | None = None, roles: dict[str, list[dict[str, object]]] | None = None, objects: dict[str, object] | None = None) -> dict[str, object]:
            visual_name = object_id(f"{page_slug}_{name}")
            container = {
                "background": obj(show=literal(True), color=color("#0F1B2D"), transparency=literal(0)),
                "border": obj(show=literal(True), color=color("#29415F"), radius=literal(8)),
                "padding": obj(top=literal(10), bottom=literal(10), left=literal(12), right=literal(12)),
                "title": obj(show=literal(bool(title)), text=literal(title or ""), fontSize=literal(12), fontColor=color("#F7FAFC")),
                "visualHeader": obj(show=literal(False)),
            }
            visual: dict[str, object] = {"visualType": kind, "visualContainerObjects": container, "drillFilterOtherVisuals": False}
            if roles:
                visual["query"] = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
            if objects:
                visual["objects"] = objects
            item = {
                "$schema": BASE + "item/report/definition/visualContainer/1.0.0/schema.json",
                "name": visual_name,
                "position": {"x": x, "y": y, "z": len(visuals) * 1000, "width": width, "height": height, "tabOrder": len(visuals) * 1000},
                "visual": visual,
            }
            visuals.append(item)
            return item

        def textbox(name: str, text: str, x: int, y: int, width: int, height: int, size: int = 14, foreground: str = "#F7FAFC") -> None:
            item = add(name, "textbox", x, y, width, height, objects={"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text, "textStyle": {"fontFamily": "Segoe UI", "fontSize": f"{size}px", "color": foreground}}]}]}}]})
            item["visual"]["visualContainerObjects"]["background"] = obj(show=literal(False))
            item["visual"]["visualContainerObjects"]["padding"] = obj(top=literal(0), bottom=literal(0), left=literal(0), right=literal(0))

        def card(name: str, table: str, measure: str, x: int, width: int, y: int = 118) -> None:
            add(
                name, "card", x, y, width, 98,
                roles={"Values": [projection(table, measure, True)]},
                objects={
                    "labels": obj(fontSize=literal(24), color=color("#F7FAFC")),
                    "categoryLabels": obj(show=literal(True), fontSize=literal(10), color=color("#9FB3C8")),
                },
            )

        def chart(name: str, kind: str, category_table: str, category: str, measure_table: str, measures: list[str], x: int, y: int, width: int, height: int, title: str, sort_desc: bool = False) -> None:
            roles = {"Category": [projection(category_table, category)], "Y": [projection(measure_table, measure, True) for measure in measures]}
            item = add(
                name, kind, x, y, width, height, title, roles,
                {
                    "dataPoint": obj(defaultColor=color("#16D9E3")),
                    "categoryAxis": obj(showAxisTitle=literal(False), fontSize=literal(10), labelColor=color("#9FB3C8")),
                    "valueAxis": obj(showAxisTitle=literal(False), fontSize=literal(10), labelColor=color("#9FB3C8"), start=literal(0)),
                    "labels": obj(show=literal(kind == "clusteredBarChart"), fontSize=literal(9)),
                    "legend": obj(show=literal(len(measures) > 1), labelColor=color("#D9E2EC")),
                },
            )
            sort_field = field(measure_table, measures[0], True) if sort_desc else field(category_table, category)
            item["visual"]["query"]["sortDefinition"] = {"sort": [{"field": sort_field, "direction": "Descending" if sort_desc else "Ascending"}], "isDefaultSort": True}

        def chart_with_series(name: str, kind: str, table: str, category: str, series: str, measure: str, x: int, y: int, width: int, height: int, title: str) -> None:
            item = add(
                name, kind, x, y, width, height, title,
                {
                    "Category": [projection(table, category)],
                    "Series": [projection(table, series)],
                    "Y": [projection(table, measure, True)],
                },
                {
                    "dataPoint": obj(defaultColor=color("#20D9E8")),
                    "categoryAxis": obj(showAxisTitle=literal(False), fontSize=literal(10), labelColor=color("#9FB3C8")),
                    "valueAxis": obj(showAxisTitle=literal(False), fontSize=literal(10), labelColor=color("#9FB3C8"), start=literal(0)),
                    "labels": obj(show=literal(True), fontSize=literal(9)),
                    "legend": obj(show=literal(True), position=literal("Top"), labelColor=color("#D9E2EC")),
                },
            )
            item["visual"]["query"]["sortDefinition"] = {
                "sort": [{"field": field(table, category), "direction": "Ascending"}],
                "isDefaultSort": True,
            }

        def scatter(name: str, x: int, y: int, width: int, height: int, title: str) -> None:
            add(
                name, "scatterChart", x, y, width, height, title,
                {
                    "Category": [projection("Customer360", "customer_id")],
                    "Series": [projection("Customer360", "member_rank")],
                    "X": [projection("Customer360", "Engagement Score Profile", True)],
                    "Y": [projection("Customer360", "Customer Value 12M", True)],
                    "Size": [projection("Customer360", "Total Activities Profile", True)],
                },
                {
                    "dataPoint": obj(defaultColor=color("#20D9E8")),
                    "categoryAxis": obj(showAxisTitle=literal(True), titleText=literal("Engagement Score"), labelColor=color("#9FB3C8"), start=literal(0), end=literal(100)),
                    "valueAxis": obj(showAxisTitle=literal(True), titleText=literal("Net Spend 12M (triệu)"), labelColor=color("#9FB3C8"), start=literal(0)),
                    "legend": obj(show=literal(True), position=literal("Top"), labelColor=color("#D9E2EC")),
                },
            )

        def table_visual(name: str, values: list[tuple[str, str, bool]], x: int, y: int, width: int, height: int, title: str) -> None:
            add(
                name, "tableEx", x, y, width, height, title,
                {"Values": [projection(table, value, measure) for table, value, measure in values]},
                {"columnHeaders": obj(fontSize=literal(10), fontColor=color("#F7FAFC"), backColor=color("#17304D")), "values": obj(fontSize=literal(10), fontColorPrimary=color("#D9E2EC"), backColorPrimary=color("#0F1B2D"))},
            )

        heading_width = 620 if page_slug in {"customer_portfolio", "customer_profile"} else 720 if page_slug == "content" else 900
        textbox("heading", f"ENTERTAINMENT LAKEHOUSE  /  {display_name.upper()}", 24, 18, heading_width, 36, 25)
        textbox("subtitle", "DỮ LIỆU MINH HỌA • UTC • Dataset tổng hợp gọn cho PBIP", 24, 58, heading_width, 26, 13, "#9FB3C8")
        if page_slug not in {"customer_portfolio", "customer_profile"}:
            add(
                "date_filter", "slicer", 1000, 16, 256, 78,
                roles={"Values": [projection("Date", "date")]},
                objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Ngày sự kiện UTC")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))},
            )

        if page_slug == "overview":
            for args in [
                ("revenue_card", "ExecutiveDaily", "Doanh thu thuần", 24, 238),
                ("margin_card", "ExecutiveDaily", "Contribution Margin", 274, 238),
                ("customer_card", "Customer360", "Khách hàng", 524, 220),
                ("program_card", "ProgramEvent", "Số chương trình", 756, 220),
                ("warning_card", "OperationsRealtime", "Dịch vụ cảnh báo", 988, 268),
            ]:
                card(*args)
            chart("revenue_trend", "lineChart", "ExecutiveDaily", "event_date_utc", "ExecutiveDaily", ["Doanh thu thuần", "Contribution Margin"], 24, 238, 650, 260, "Doanh thu & lợi nhuận theo thời gian")
            chart("revenue_mix", "clusteredBarChart", "ExecutiveDaily", "business_line", "ExecutiveDaily", ["Doanh thu thuần"], 694, 238, 562, 260, "Doanh thu theo dịch vụ", True)
            chart("program_status", "clusteredColumnChart", "ProgramEvent", "program_status", "ProgramEvent", ["Số chương trình"], 24, 520, 390, 250, "Trạng thái chương trình")
            chart("streaming_device", "clusteredBarChart", "StreamingRealtime", "device_type", "StreamingRealtime", ["Watch Hours"], 434, 520, 390, 250, "Watch hours theo thiết bị", True)
            table_visual("service_health", [("OperationsRealtime", "service_name", False), ("OperationsRealtime", "P95 Latency", True), ("OperationsRealtime", "Error Rate", True), ("OperationsRealtime", "Data Lag", True), ("OperationsRealtime", "Trạng thái hiện tại", True)], 844, 520, 412, 250, "Sức khỏe hệ thống")
            textbox("scope", "Executive view kết hợp finance, customer, program và vận hành. Dữ liệu hoàn toàn synthetic; amount không phải số kế toán đã sign-off.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "revenue":
            for args in [
                ("gross_card", "ExecutiveDaily", "Gross Value", 24, 238),
                ("revenue_card", "ExecutiveDaily", "Doanh thu thuần", 274, 238),
                ("margin_card", "ExecutiveDaily", "Contribution Margin", 524, 238),
                ("margin_rate_card", "ExecutiveDaily", "Contribution Margin %", 774, 224),
                ("refund_card", "ExecutiveDaily", "Hoàn tiền", 1010, 246),
            ]:
                card(*args)
            chart("revenue_margin_trend", "lineChart", "ExecutiveDaily", "event_date_utc", "ExecutiveDaily", ["Doanh thu thuần", "Contribution Margin", "Mục tiêu doanh thu"], 24, 238, 800, 280, "Doanh thu, margin và mục tiêu")
            chart("line_revenue", "clusteredBarChart", "ExecutiveDaily", "business_line", "ExecutiveDaily", ["Doanh thu thuần", "Chi phí biến đổi"], 844, 238, 412, 280, "Hiệu quả theo dịch vụ", True)
            chart("line_margin", "clusteredColumnChart", "ExecutiveDaily", "business_line", "ExecutiveDaily", ["Contribution Margin"], 24, 540, 390, 230, "Contribution Margin theo dịch vụ")
            chart("program_margin", "clusteredBarChart", "ProgramEvent", "program_name", "ProgramEvent", ["Event Contribution Margin"], 434, 540, 390, 230, "Sự kiện đóng góp lớn nhất", True)
            table_visual("revenue_detail", [("ExecutiveDaily", "business_line", False), ("ExecutiveDaily", "Doanh thu thuần", True), ("ExecutiveDaily", "Chi phí biến đổi", True), ("ExecutiveDaily", "Contribution Margin", True), ("ExecutiveDaily", "Tiến độ mục tiêu", True)], 844, 540, 412, 230, "Revenue detail")
            textbox("scope", "Gross Value và doanh thu thuần được tách riêng; Ticketing chỉ ghi nhận phần doanh thu thuộc doanh nghiệp. Sự kiện ghi nhận theo ngày bán vé và khớp với trang Hiệu quả Chương trình.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "content":
            for args in [
                ("viewers_card", "StreamingRealtime", "Concurrent Viewers", 24, 238),
                ("watch_card", "StreamingRealtime", "Watch Hours", 274, 238),
                ("completion_card", "StreamingRealtime", "Completion Rate", 524, 238),
                ("rebuffer_card", "StreamingRealtime", "Rebuffer Ratio", 774, 224),
                ("failure_card", "StreamingRealtime", "Video Start Failure", 1010, 246),
            ]:
                card(*args)
            add("device_filter", "slicer", 760, 16, 220, 78, roles={"Values": [projection("StreamingRealtime", "device_type")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Thiết bị")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            chart("viewer_timeline", "lineChart", "StreamingRealtime", "event_time_utc", "StreamingRealtime", ["Concurrent Viewers"], 24, 238, 650, 280, "Người xem đồng thời theo 15 phút")
            chart("device_quality", "clusteredColumnChart", "StreamingRealtime", "device_type", "StreamingRealtime", ["Rebuffer Ratio", "Video Start Failure"], 694, 238, 562, 280, "Chất lượng phát theo thiết bị")
            chart("region_watch", "clusteredBarChart", "StreamingRealtime", "region", "StreamingRealtime", ["Watch Hours"], 24, 540, 390, 230, "Watch hours theo khu vực", True)
            chart("device_conversion", "clusteredBarChart", "StreamingRealtime", "device_type", "StreamingRealtime", ["Streaming Conversion"], 434, 540, 390, 230, "Subscription conversion theo thiết bị", True)
            table_visual("streaming_detail", [("StreamingRealtime", "device_type", False), ("StreamingRealtime", "region", False), ("StreamingRealtime", "Watch Hours", True), ("StreamingRealtime", "Completion Rate", True), ("StreamingRealtime", "Rebuffer Ratio", True), ("StreamingRealtime", "Video Start Failure", True)], 844, 540, 412, 230, "Streaming quality detail")
            textbox("scope", "Grain 15 phút × thiết bị × khu vực; đủ minh họa near real-time nhưng chỉ có một ngày vận hành để giữ dataset gọn.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "booking_event":
            for args in [
                ("ticket_card", "ProgramEvent", "Vé đã bán", 24, 238),
                ("sellthrough_card", "ProgramEvent", "Sell-through Rate", 274, 238),
                ("gmv_card", "ProgramEvent", "Ticket GMV", 524, 238),
                ("attendee_card", "ProgramEvent", "Khách tham gia", 774, 224),
                ("noshow_card", "ProgramEvent", "No-show Rate", 1010, 246),
            ]:
                card(*args)
            chart("ticket_type", "clusteredColumnChart", "ProgramEvent", "program_type", "ProgramEvent", ["Vé đã bán", "Sức chứa"], 24, 238, 390, 280, "Vé bán và sức chứa theo loại")
            chart("sales_channel", "clusteredBarChart", "EventSalesDetail", "channel", "EventSalesDetail", ["Sales Net Revenue"], 434, 238, 390, 280, "Doanh thu theo kênh bán", True)
            chart("ticket_tier", "clusteredColumnChart", "EventSalesDetail", "ticket_tier", "EventSalesDetail", ["Vé bán chi tiết", "Tổng Inventory"], 844, 238, 412, 280, "Hiệu quả theo hạng vé")
            chart("funnel_stage", "clusteredBarChart", "EventSalesDetail", "channel", "EventSalesDetail", ["Event Views", "Seat Selections", "Payment Attempts", "Completed Orders"], 24, 540, 600, 230, "Phễu đặt vé theo kênh")
            table_visual("event_detail", [("ProgramEvent", "program_name", False), ("ProgramEvent", "program_type", False), ("ProgramEvent", "region", False), ("ProgramEvent", "Vé đã bán", True), ("ProgramEvent", "Sell-through Rate", True), ("ProgramEvent", "Khách tham gia", True), ("ProgramEvent", "program_status", False)], 644, 540, 612, 230, "Danh mục vé & sự kiện")
            textbox("scope", "Sell-through = vé bán / sức chứa; no-show = vé bán nhưng không tham dự. Dữ liệu chỉ dùng minh họa, không đại diện một promoter thật.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "program_portfolio":
            for args in [
                ("program_card", "ProgramEvent", "Số chương trình", 24, 220),
                ("event_revenue_card", "ProgramEvent", "Doanh thu sự kiện", 256, 252),
                ("event_margin_card", "ProgramEvent", "Event Contribution Margin", 520, 268),
                ("participants_card", "ProgramEvent", "Khách tham gia", 800, 220),
                ("target_card", "ProgramEvent", "Tỷ lệ đạt kế hoạch", 1032, 224),
            ]:
                card(*args)
            add("status_filter", "slicer", 760, 16, 220, 78, roles={"Values": [projection("ProgramEvent", "program_status")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Trạng thái")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            chart("program_margin", "clusteredBarChart", "ProgramEvent", "program_name", "ProgramEvent", ["Event Contribution Margin"], 24, 238, 600, 280, "Contribution Margin theo chương trình", True)
            chart("program_status", "clusteredColumnChart", "ProgramEvent", "program_status", "ProgramEvent", ["Số chương trình"], 644, 238, 300, 280, "Trạng thái danh mục")
            chart("program_region", "clusteredColumnChart", "ProgramEvent", "region", "ProgramEvent", ["Doanh thu sự kiện"], 964, 238, 292, 280, "Doanh thu theo khu vực")
            table_visual("program_matrix", [("ProgramEvent", "program_name", False), ("ProgramEvent", "program_type", False), ("ProgramEvent", "region", False), ("ProgramEvent", "Doanh thu sự kiện", True), ("ProgramEvent", "Event Margin %", True), ("ProgramEvent", "Sales Pace Index", True), ("ProgramEvent", "Tiến độ hòa vốn", True), ("ProgramEvent", "program_status", False)], 24, 540, 1232, 230, "Danh mục chương trình & sự kiện")
            textbox("scope", "Status dựa trên sales pace, hòa vốn và contribution margin; không dùng điểm tổng hợp khó giải thích.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "event_detail":
            add("program_filter", "slicer", 760, 16, 220, 78, roles={"Values": [projection("ProgramEvent", "program_name")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Chọn chương trình")), "selection": obj(selectAllCheckboxEnabled=literal(False), singleSelect=literal(True))})
            for args in [
                ("ticket_card", "ProgramEvent", "Vé đã bán", 24, 220),
                ("sellthrough_card", "ProgramEvent", "Sell-through Rate", 256, 220),
                ("pace_card", "ProgramEvent", "Sales Pace Index", 488, 220),
                ("forecast_margin_card", "ProgramEvent", "Event Margin %", 720, 220),
                ("break_even_card", "ProgramEvent", "Tiến độ hòa vốn", 952, 288),
            ]:
                card(*args)
            chart("pace_timeline", "lineChart", "EventSalesPace", "lead_day", "EventSalesPace", ["Vé tích lũy thực tế", "Vé tích lũy kế hoạch", "Vé forecast"], 24, 238, 650, 280, "Vé bán tích lũy vs. kế hoạch")
            chart("tier_sales", "clusteredColumnChart", "EventSalesDetail", "ticket_tier", "EventSalesDetail", ["Vé bán chi tiết", "Tổng Inventory"], 694, 238, 562, 280, "Hiệu quả theo hạng vé")
            chart("channel_roas", "clusteredBarChart", "EventSalesDetail", "channel", "EventSalesDetail", ["Sales Net Revenue", "Sales Marketing Cost"], 24, 540, 390, 230, "Hiệu quả kênh bán", True)
            chart("channel_funnel", "clusteredColumnChart", "EventSalesDetail", "channel", "EventSalesDetail", ["Event Views", "Completed Orders"], 434, 540, 390, 230, "Funnel theo kênh")
            table_visual("event_summary", [("ProgramEvent", "program_name", False), ("ProgramEvent", "region", False), ("ProgramEvent", "Ticket GMV", True), ("ProgramEvent", "Event Contribution Margin", True), ("ProgramEvent", "Member Conversions", True), ("ProgramEvent", "program_status", False)], 844, 540, 412, 230, "P&L và trạng thái")
            textbox("scope", "Chọn một chương trình để drill-through. Lead day -30 đến 0 cho phép so sánh actual, plan và forecast trước sự kiện.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "membership":
            for args in [
                ("subscription_card", "SubscriptionDaily", "Sự kiện subscription", 24, 220),
                ("new_card", "SubscriptionDaily", "Đăng ký mới", 256, 220),
                ("renewal_card", "SubscriptionDaily", "Gia hạn", 488, 220),
                ("cancel_card", "SubscriptionDaily", "Hủy subscription", 720, 220),
                ("member_conversion_card", "ProgramEvent", "Member Conversions", 952, 288),
            ]:
                card(*args)
            chart("subscription_trend", "lineChart", "SubscriptionDaily", "event_date_utc", "SubscriptionDaily", ["Đăng ký mới", "Gia hạn", "Hủy subscription"], 24, 238, 800, 280, "Subscription events theo thời gian")
            chart("subscription_plan", "clusteredColumnChart", "SubscriptionDaily", "plan_id", "SubscriptionDaily", ["Đăng ký mới", "Gia hạn", "Hủy subscription"], 844, 238, 412, 280, "Hiệu quả theo plan")
            chart("mrr_plan", "clusteredBarChart", "SubscriptionDaily", "plan_id", "SubscriptionDaily", ["MRR event value proxy"], 24, 540, 390, 230, "MRR event value theo plan", True)
            chart("program_member", "clusteredBarChart", "ProgramEvent", "program_name", "ProgramEvent", ["Member Conversions"], 434, 540, 390, 230, "Chuyển đổi thành viên từ sự kiện", True)
            table_visual("membership_detail", [("SubscriptionDaily", "plan_id", False), ("SubscriptionDaily", "Sự kiện subscription", True), ("SubscriptionDaily", "Đăng ký mới", True), ("SubscriptionDaily", "Gia hạn", True), ("SubscriptionDaily", "Hủy subscription", True), ("SubscriptionDaily", "MRR event value proxy", True)], 844, 540, 412, 230, "Membership detail")
            textbox("scope", "MRR event value là proxy từ event; chưa thay thế recognized recurring revenue hoặc cohort churn đã được Finance phê duyệt.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "customer_portfolio":
            add("rank_filter", "slicer", 650, 16, 142, 78, roles={"Values": [projection("Customer360", "member_rank")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Member Rank")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            add("segment_filter", "slicer", 802, 16, 166, 78, roles={"Values": [projection("Customer360", "behavior_segment")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Behavior Segment")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            add("status_filter", "slicer", 978, 16, 148, 78, roles={"Values": [projection("Customer360", "latest_subscription_status")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Subscription")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            add("region_filter", "slicer", 1136, 16, 120, 78, roles={"Values": [projection("Customer360", "region")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Region")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            for args in [
                ("customer_card", "Customer360", "Khách hàng", 24, 185),
                ("spend_card", "Customer360", "Net Spend 12M", 219, 185),
                ("gold_customer_card", "Customer360", "Gold+ Customer Share", 414, 185),
                ("gold_spend_card", "Customer360", "Gold+ Spend Share", 609, 185),
                ("multi_card", "Customer360", "Tỷ lệ khách đa dịch vụ", 804, 185),
                ("risk_card", "Customer360", "High-spend giảm tương tác", 999, 257),
            ]:
                card(*args)
            chart_with_series("rank_share", "hundredPercentStackedBarChart", "CustomerRankShare", "metric_type", "member_rank", "Rank Share", 24, 238, 400, 250, "Cơ cấu khách hàng và chi tiêu theo hạng – 12 tháng gần nhất")
            scatter("spend_engagement", 444, 238, 400, 250, "Chi tiêu × Gắn kết")
            chart("rank_behavior", "clusteredBarChart", "Customer360", "member_rank", "Customer360", ["Watch Hours TB", "Bookings TB", "Attendance TB", "Subscription Activity TB"], 864, 238, 392, 250, "Hành vi sử dụng theo hạng")
            chart("service_mix", "clusteredBarChart", "Customer360", "service_mix", "Customer360", ["Khách hàng"], 24, 508, 380, 245, "Khách hàng theo tổ hợp dịch vụ", True)
            chart_with_series("segment_rank", "barChart","Customer360", "behavior_segment", "member_rank", "Khách hàng", 424, 508, 390, 245, "Behavior Segment × Member Rank")
            table_visual("priority_customers", [("Customer360", "customer_id", False), ("Customer360", "Net Spend 12M", True), ("Customer360", "member_rank", False), ("Customer360", "Engagement Score Profile", True), ("Customer360", "recency_days", False), ("Customer360", "service_mix", False), ("Customer360", "behavior_risk", False), ("Customer360", "next_best_action", False)], 834, 508, 422, 245, "Danh sách khách hàng ưu tiên")
            textbox("rank_legend", "DIAMOND  ■   PLATINUM  ■   GOLD  ■   SILVER  ■   BASIC  ■", 24, 768, 760, 24, 12, "#20D9E8")
            textbox("scope", "Member Rank chỉ dựa trên Net Spend 12M sau hoàn tiền; dữ liệu hành vi được phân tích độc lập. Màu hạng được lưu trong member_rank_color để tái sử dụng.", 24, 798, 1232, 34, 12, "#F5C451")
        elif page_slug == "customer_profile":
            # Open the profile on a representative customer so the profile cards are never blank.
            default_customer = {"filter": {
                "Version": 2,
                "From": [{"Name": "c", "Entity": "Customer360", "Type": 0}],
                "Where": [{"Condition": {"In": {
                    "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "customer_id"}}],
                    "Values": [[{"Literal": {"Value": "'customer-0045'"}}]],
                }}}],
            }}
            add("customer_filter", "slicer", 1012, 16, 244, 78, roles={"Values": [projection("Customer360", "customer_id")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Chọn khách hàng")), "selection": obj(selectAllCheckboxEnabled=literal(False), singleSelect=literal(True)), "general": [{"properties": {"filter": default_customer}}]})
            for args in [
                ("ltv_card", "Customer360", "Lifetime Value Proxy", 24, 238),
                ("spend_card", "Customer360", "Customer Value 12M", 274, 238),
                ("margin_card", "Customer360", "Customer Contribution Margin", 524, 238),
                ("recency_card", "Customer360", "Recency Profile", 774, 224),
                ("engagement_card", "Customer360", "Engagement Score Profile", 1010, 246),
            ]:
                card(*args)
            table_visual("profile_identity", [("Customer360", "unified_customer_id", False), ("Customer360", "member_rank", False), ("Customer360", "region", False), ("Customer360", "consent_status", False), ("Customer360", "preferred_device", False), ("Customer360", "latest_plan_id", False), ("Customer360", "behavior_risk", False)], 24, 238, 280, 280, "Hồ sơ hợp nhất")
            chart("affinity", "clusteredBarChart", "CustomerAffinity", "affinity_name", "CustomerAffinity", ["Affinity Score"], 324, 238, 420, 280, "Sở thích & nội dung", True)
            table_visual("cross_service", [("Customer360", "service_mix", False), ("Customer360", "Watch Hours Profile", True), ("Customer360", "Sessions Profile", True), ("Customer360", "Confirmed Tickets Profile", True), ("Customer360", "Attendance Profile", True), ("Customer360", "Subscription Events Profile", True), ("Customer360", "Completion Rate Profile", True)], 764, 238, 492, 280, "Mức độ gắn kết theo dịch vụ")
            table_visual("recent_activity", [("CustomerActivity", "occurred_at", False), ("CustomerActivity", "domain", False), ("CustomerActivity", "activity_label", False), ("CustomerActivity", "activity_detail", False), ("CustomerActivity", "activity_result", False)], 24, 540, 700, 230, "Hoạt động gần đây theo thời gian")
            table_visual("profile_action", [("Customer360", "member_rank", False), ("Customer360", "behavior_segment", False), ("Customer360", "engagement_trend_pct", False), ("Customer360", "behavior_risk", False), ("Customer360", "next_best_action", False)], 744, 540, 512, 230, "Đề xuất hành động có thể giải thích")
            textbox("scope", "Identity hợp nhất từ dữ liệu demo. Rank chỉ dựa trên chi tiêu; behavior risk và next best action là rule-based proxy để minh họa, không phải quyết định tự động.", 24, 798, 1232, 34, 12, "#F5C451")
        else:
            for args in [
                ("rps_card", "OperationsRealtime", "Current RPS", 24, 220),
                ("latency_card", "OperationsRealtime", "P95 Latency", 256, 220),
                ("error_card", "OperationsRealtime", "Error Rate", 488, 220),
                ("queue_card", "OperationsRealtime", "Queue Depth", 720, 220),
                ("lag_card", "OperationsRealtime", "Data Lag", 952, 288),
            ]:
                card(*args)
            add("service_filter", "slicer", 760, 16, 220, 78, roles={"Values": [projection("OperationsRealtime", "service_name")]}, objects={"data": obj(mode=literal("Dropdown")), "header": obj(show=literal(True), text=literal("Dịch vụ")), "selection": obj(selectAllCheckboxEnabled=literal(True), singleSelect=literal(False))})
            chart("traffic_timeline", "lineChart", "OperationsRealtime", "event_time_utc", "OperationsRealtime", ["Current RPS"], 24, 238, 650, 280, "Lưu lượng theo 15 phút")
            chart("latency_service", "clusteredColumnChart", "OperationsRealtime", "service_name", "OperationsRealtime", ["P95 Latency cao nhất"], 694, 238, 562, 280, "P95 latency cao nhất trong ngày theo dịch vụ")
            chart("queue_service", "clusteredBarChart", "OperationsRealtime", "service_name", "OperationsRealtime", ["Queue Depth"], 24, 540, 390, 230, "Hàng đợi xử lý", True)
            chart("throughput_service", "clusteredBarChart", "OperationsRealtime", "service_name", "OperationsRealtime", ["Throughput / phút"], 434, 540, 390, 230, "Throughput theo dịch vụ", True)
            table_visual("operations_detail", [("OperationsRealtime", "service_name", False), ("OperationsRealtime", "P95 Latency", True), ("OperationsRealtime", "Error Rate", True), ("OperationsRealtime", "Queue Depth", True), ("OperationsRealtime", "Data Lag", True), ("OperationsRealtime", "Trạng thái hiện tại", True)], 844, 540, 412, 230, "Sức khỏe hệ thống")
            textbox("scope", "Grain 15 phút × service. Payment Gateway có một cửa sổ cảnh báo có chủ đích để minh họa anomaly và business impact.", 24, 798, 1232, 34, 12, "#F5C451")

        write_json(
            page_dir / "page.json",
            {
                "$schema": BASE + "item/report/definition/page/1.0.0/schema.json",
                "name": page_id,
                "displayName": display_name,
                "displayOption": "FitToPage",
                "height": 864,
                "width": 1280,
                "objects": {"background": obj(color=color("#07111F"), transparency=literal(0))},
            },
        )
        for visual in visuals:
            write_json(page_dir / "visuals" / visual["name"] / "visual.json", apply_colors(visual))


def backup(path: Path, project: Path) -> None:
    """Copy a folder aside before it is deleted, so Desktop edits are never lost to a regeneration."""
    if not path.exists():
        return
    target = project / "dashboard_backups" / f"{datetime.now():%Y%m%d-%H%M%S}" / path.relative_to(project)
    shutil.copytree(path, target)
    print(f"backup: {target}")


def capture_theme(dashboard: Path) -> tuple[dict[str, object], dict[str, bytes]]:
    """Read the registered theme (report.json entries + StaticResources files) before regeneration."""
    report = dashboard / f"{PROJECT_NAME}.Report"
    report_json = report / "definition" / "report.json"
    settings: dict[str, object] = {}
    if report_json.is_file():
        current = json.loads(report_json.read_text(encoding="utf-8"))
        settings = {key: current[key] for key in ("themeCollection", "resourcePackages") if key in current}
    static = report / "StaticResources"
    files = {str(path.relative_to(report)): path.read_bytes() for path in static.rglob("*") if path.is_file()} if static.is_dir() else {}
    return settings, files


def restore_theme(dashboard: Path, theme: tuple[dict[str, object], dict[str, bytes]]) -> None:
    settings, files = theme
    report = dashboard / f"{PROJECT_NAME}.Report"
    for relative, content in files.items():
        (report / relative).parent.mkdir(parents=True, exist_ok=True)
        (report / relative).write_bytes(content)
    if settings:
        report_json = report / "definition" / "report.json"
        current = json.loads(report_json.read_text(encoding="utf-8"))
        current.update(settings)
        write_json(report_json, current)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    back_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--project-dir", type=Path, default=back_root.parent)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true", help="Replace generated PBIP definitions; may reset later Desktop edits")
    parser.add_argument("--report-only", action="store_true", help="Regenerate PBIR report definitions while preserving the semantic model")
    parser.add_argument("--model-only", action="store_true", help="Regenerate model.bim while preserving PBIR and TMDL files")
    args = parser.parse_args()

    project = args.project_dir.resolve()
    data_dir = (args.data_dir or back_root / "artifacts" / "powerbi_demo").resolve()
    missing = [filename for filename, _ in TABLE_SPECS.values() if not (data_dir / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Power BI exports: {missing}")

    dashboard = project / "dashboard"
    if args.report_only and args.model_only:
        raise ValueError("--report-only and --model-only cannot be combined")
    if args.model_only:
        dashboard.mkdir(parents=True, exist_ok=True)
        write_json(dashboard / "model.bim", build_model(data_dir))
        print(dashboard / "model.bim")
        return
    if args.report_only:
        if not dashboard.exists():
            raise FileNotFoundError("dashboard does not exist")
        report = dashboard / f"{PROJECT_NAME}.Report"
        definition = report / "definition"
        theme = capture_theme(dashboard)
        if definition.exists():
            backup(definition, project)
            shutil.rmtree(definition)
        build_report(dashboard)
        restore_theme(dashboard, theme)
        print(report)
        return
    if dashboard.exists() and not args.overwrite:
        raise FileExistsError("dashboard already exists; use Power BI Refresh, or --overwrite only for intentional regeneration")
    theme = capture_theme(dashboard)
    if dashboard.exists():
        backup(dashboard, project)
        shutil.rmtree(dashboard)
    dashboard.mkdir(parents=True)
    write_json(dashboard / "model.bim", build_model(data_dir))
    build_report(dashboard)
    restore_theme(dashboard, theme)
    print(dashboard)


if __name__ == "__main__":
    main()

