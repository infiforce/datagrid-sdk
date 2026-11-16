"""Episode / production-task filter helpers for download."""

from __future__ import annotations

import sys
from typing import Any

from datagrid.client import APIError, DatagridClient


def _task_id(item: dict[str, Any]) -> str:
    """Prefer Crowd/DP ``id``; accept a few aliases just in case."""
    for key in ("id", "production_task_id", "task_id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def resolve_production_task_ids(
    client: DatagridClient,
    dataset_id: str,
    *,
    query: str | None = None,
    ids: list[str] | None = None,
    require_unique: bool = True,
) -> list[str]:
    """Resolve production task IDs from exact ids and/or ``--match-task`` keyword.

    When ``query`` is set, calls data-platform crowdsource proxy (Crowd keyword
    search on task_name / task_code). If ``require_unique`` and the keyword
    matches 0 or >1 tasks, raises ValueError to avoid accidental bulk download.
    """
    exact = [x.strip() for x in (ids or []) if str(x).strip()]
    q = (query or "").strip()

    if exact and q:
        raise ValueError("use either match_task or production_task_ids, not both")
    if exact:
        return exact
    if not q:
        return []

    # Page through Crowd results (limit 100 per page).
    matched: list[dict[str, Any]] = []
    page = 1
    while True:
        data = client.list_production_tasks(
            dataset_id, keyword=q, page=page, limit=100
        )
        items = data.get("list") or []
        matched.extend(items)
        total = int(data.get("total") or 0)
        if not items or len(matched) >= total or len(items) < 100:
            break
        page += 1
        if page > 50:
            break

    if not matched:
        raise ValueError(
            f"--match-task {q!r} matched 0 tasks; "
            "refine the keyword or pass --production-task-id"
        )
    if require_unique and len(matched) > 1:
        lines = []
        for item in matched[:20]:
            lines.append(
                f"  - id={_task_id(item) or item.get('id')} "
                f"code={item.get('task_code')!r} "
                f"name={item.get('task_name')!r}"
            )
        more = "" if len(matched) <= 20 else f"\n  ... and {len(matched) - 20} more"
        raise ValueError(
            f"--match-task {q!r} matched {len(matched)} tasks; "
            "refine the keyword, pass a precise --production-task-id, "
            "or use --allow-multiple-tasks:\n" + "\n".join(lines) + more
        )

    out: list[str] = []
    for item in matched:
        tid = _task_id(item)
        if tid:
            out.append(tid)
    if not out:
        sample = matched[0] if matched else {}
        raise APIError(
            f"--match-task {q!r} returned {len(matched)} task(s) without id; "
            f"sample keys={sorted(sample.keys())}"
        )

    print(f"production tasks matched by {q!r}: {len(out)}", flush=True)
    for item in matched[:10]:
        print(
            f"  - {item.get('task_code')} / {item.get('task_name')} "
            f"({_task_id(item)})",
            flush=True,
        )
    if len(matched) > 10:
        print(f"  ... and {len(matched) - 10} more", flush=True)
    return out


def print_dry_run_plan(
    jobs: list[dict[str, Any]],
    *,
    max_lines: int = 50,
) -> None:
    episodes: set[str] = set()
    for job in jobs:
        eid = str(job.get("episode_id") or "")
        if eid:
            episodes.add(eid)
    print(
        f"dry-run: would download {len(jobs)} file(s) "
        f"across {len(episodes)} episode(s)",
        flush=True,
    )
    for job in jobs[:max_lines]:
        print(
            f"  [plan] ep={job.get('episode_index')} "
            f"type={job.get('node_type')} -> {job.get('dest')}",
            flush=True,
        )
    if len(jobs) > max_lines:
        print(f"  ... and {len(jobs) - max_lines} more", flush=True, file=sys.stderr)
