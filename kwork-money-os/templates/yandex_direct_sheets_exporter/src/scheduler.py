"""Scheduling helpers for manual or cron-based runs."""

from __future__ import annotations

from datetime import date, timedelta


def default_date_range(today: date | None = None) -> tuple[str, str]:
    current = today or date.today()
    yesterday = current - timedelta(days=1)
    return yesterday.isoformat(), yesterday.isoformat()


def cron_example(project_path: str = "/path/to/project") -> str:
    return f"15 8 * * * cd {project_path} && .venv/bin/python src/main.py >> logs/run.log 2>&1"
