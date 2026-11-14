from __future__ import annotations

import json

from entertainment_pipeline.producer import main


def test_dry_run_validates_without_kafka(capsys) -> None:
    exit_code = main(
        [
            "--dry-run",
            "--count",
            "8",
            "--rate",
            "0",
            "--seed",
            "7",
            "--base-time",
            "2026-11-06T00:00:00Z",
            "--sample-limit",
            "0",
        ]
    )

    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert exit_code == 0
    assert summary["status"] == "validated"
    assert summary["generated"] == 8
    assert summary["delivered"] == 0
    assert set(summary["generated_by_topic"].values()) == {2}

