"""Render the Phase 6B P95 latency comparison as a dependency-free SVG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def render(summary_path: Path, output_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    sla_seconds = summary["silver_latency"]["sla_milliseconds"] / 1_000
    stages = [
        ("Processor first-seen", summary["silver_latency"]["processing_latency_ms"]["p95"] / 1_000),
        ("Silver query upper bound", summary["silver_latency"]["query_upper_bound_latency_ms"]["p95"] / 1_000),
        ("Gold refresh upper bound", summary["gold_query_upper_bound"]["query_upper_bound_latency_ms"]["p95"] / 1_000),
        ("Power BI export upper bound", summary["export_upper_bound"]["query_upper_bound_latency_ms"]["p95"] / 1_000),
    ]

    width, height = 1_000, 510
    left, right, top, bottom = 260, 70, 100, 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    axis_max = max(65.0, sla_seconds * 1.08)
    row_height = plot_height / len(stages)
    colors = ("#2563EB", "#0F766E", "#7C3AED", "#B45309")

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Phase 6B P95 latency versus 60-second SLA</title>',
        '<desc id="desc">Four horizontal bars compare processing, Silver query, Gold refresh, and Power BI export P95 latency. Every value is below the 60-second target.</desc>',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<text x="40" y="42" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">Phase 6B: P95 latency remains below the 60-second SLA</text>',
        '<text x="40" y="70" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#4B5563">Fresh 40-event batch · local simulated deployment · 2026-11-06</text>',
    ]

    for tick in range(0, 61, 10):
        x = left + (tick / axis_max) * plot_width
        lines.extend(
            [
                f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{height - bottom}" stroke="#E5E7EB" stroke-width="1"/>',
                f'<text x="{x:.1f}" y="{height - bottom + 28}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="#6B7280">{tick}s</text>',
            ]
        )

    sla_x = left + (sla_seconds / axis_max) * plot_width
    lines.extend(
        [
            f'<line x1="{sla_x:.1f}" y1="{top - 18}" x2="{sla_x:.1f}" y2="{height - bottom}" stroke="#DC2626" stroke-width="3" stroke-dasharray="8 6"/>',
            f'<text x="{sla_x - 6:.1f}" y="{top - 28}" text-anchor="end" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="700" fill="#B91C1C">SLA {sla_seconds:.0f}s</text>',
        ]
    )

    for index, ((label, value), color) in enumerate(zip(stages, colors, strict=True)):
        y = top + index * row_height + 16
        bar_y = y + 12
        bar_width = (value / axis_max) * plot_width
        lines.extend(
            [
                f'<text x="{left - 16}" y="{bar_y + 21}" text-anchor="end" font-family="Segoe UI, Arial, sans-serif" font-size="15" fill="#1F2937">{label}</text>',
                f'<rect x="{left}" y="{bar_y}" width="{bar_width:.1f}" height="32" rx="5" fill="{color}"/>',
                f'<text x="{left + bar_width + 10:.1f}" y="{bar_y + 22}" font-family="Segoe UI, Arial, sans-serif" font-size="15" font-weight="700" fill="#111827">{value:.3f}s</text>',
            ]
        )

    lines.extend(
        [
            '<text x="40" y="492" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#6B7280">Upper bounds are observed after each completed stage; event-to-visual was not measured because Power BI Desktop refresh remained manual.</text>',
            "</svg>",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    render(args.summary, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
