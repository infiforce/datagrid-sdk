"""Datagrid CLI: ``datagrid download dataset ...``."""

from __future__ import annotations

import argparse
import os
import sys
import warnings

# macOS system Python is often built with LibreSSL; urllib3 v2 warns on import.
warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL.*")

import requests

from datagrid.client import APIError
from datagrid.download.dataset import download_dataset


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datagrid",
        description="Datagrid CLI — download data from Datagrid / data-platform.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="download resources")
    download_sub = download.add_subparsers(dest="resource", required=True)

    ds = download_sub.add_parser(
        "dataset",
        help="download episode artifacts for a dataset",
        description=(
            "Download dataset episode files. "
            "Auth uses API credential token via X-Internal-Service-Token."
        ),
    )
    ds.add_argument(
        "--base-url",
        default=_env("DATAGRID_BASE_URL"),
        help="API base URL (or DATAGRID_BASE_URL)",
    )
    ds.add_argument(
        "--token",
        default=_env("DATAGRID_API_TOKEN"),
        help="API credential (or DATAGRID_API_TOKEN)",
    )
    ds.add_argument("--dataset-id", required=True, help="dataset UUID")
    ds.add_argument(
        "--formats",
        required=True,
        nargs="+",
        help=(
            "formats in priority order, e.g. lerobot mcap. "
            "Aliases or exact node_type like lerobot_v2.1"
        ),
    )
    ds.add_argument(
        "--mode",
        choices=("all", "sequential"),
        default="sequential",
        help=(
            "all: every matched format; "
            "sequential: first available format in --formats order (default)"
        ),
    )
    ds.add_argument(
        "--output",
        default="./downloads",
        help="output directory (default: ./downloads)",
    )
    ds.add_argument("--page-size", type=int, default=50)
    ds.add_argument("--workers", type=int, default=4)
    ds.add_argument("--timeout", type=float, default=120.0)
    ds.add_argument(
        "--limit",
        type=int,
        default=None,
        help="download at most N matching episodes (default: all)",
    )
    ds.add_argument(
        "--episode-id",
        nargs="+",
        default=None,
        help="only these episode UUIDs (server-side filter via episode/list ids)",
    )
    ds.add_argument(
        "--match-task",
        default=None,
        help=(
            "fuzzy match production task by name/code within the dataset; "
            "must resolve to exactly one task unless --allow-multiple-tasks"
        ),
    )
    ds.add_argument(
        "--production-task-id",
        nargs="+",
        default=None,
        help="exact production task UUID(s); mutually exclusive with --match-task",
    )
    ds.add_argument(
        "--allow-multiple-tasks",
        action="store_true",
        help="allow --match-task to match multiple production tasks",
    )
    ds.add_argument(
        "--dry-run",
        action="store_true",
        help="plan only: show matched files/paths without downloading",
    )
    ds.add_argument(
        "--endpoint",
        choices=("auto", "internal", "public"),
        default="auto",
        help=(
            "auto: probe API download_url_internal then fall back to public "
            "(default); internal/public force selection"
        ),
    )
    ds.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite existing local files",
    )
    return parser


def _run_download_dataset(args: argparse.Namespace) -> int:
    if not args.base_url:
        print(
            "error: --base-url or DATAGRID_BASE_URL is required",
            file=sys.stderr,
        )
        return 2
    if not args.token:
        print(
            "error: --token or DATAGRID_API_TOKEN is required",
            file=sys.stderr,
        )
        return 2
    if args.limit is not None and args.limit < 1:
        print("error: --limit must be >= 1", file=sys.stderr)
        return 2
    if args.match_task and args.production_task_id:
        print(
            "error: use either --match-task or --production-task-id",
            file=sys.stderr,
        )
        return 2

    result = download_dataset(
        base_url=args.base_url,
        token=args.token,
        dataset_id=args.dataset_id,
        formats=args.formats,
        mode=args.mode,
        output=args.output,
        page_size=args.page_size,
        workers=args.workers,
        timeout=args.timeout,
        limit=args.limit,
        episode_ids=args.episode_id,
        endpoint=args.endpoint,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        match_task=args.match_task,
        production_task_ids=args.production_task_id,
        allow_multiple_tasks=args.allow_multiple_tasks,
    )
    return 1 if result.get("failed") else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "download" and args.resource == "dataset":
            return _run_download_dataset(args)
        parser.error(f"unsupported command: {args.command} {args.resource}")
        return 2
    except (APIError, ValueError, requests.RequestException) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
