"""Download dataset episode artifacts."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from datagrid.client import APIError, DatagridClient
from datagrid.download.checksum import is_md5_algo, local_matches_checksum, md5_file
from datagrid.download.filters import print_dry_run_plan, resolve_production_task_ids
from datagrid.download.formats import (
    episode_video_node,
    resolve_formats,
    select_nodes,
)
from datagrid.network import EndpointMode, pick_download_url


def filename_from_url(url: str, fallback: str) -> str:
    path = unquote(urlparse(url).path)
    name = Path(path).name
    return name or fallback


def safe_file_name(name: str, fallback: str) -> str:
    """Use API file_name; keep only the basename to avoid path traversal."""
    cleaned = Path(str(name or "").strip()).name
    if cleaned and cleaned not in {".", ".."}:
        return cleaned
    return fallback


def episode_dir_name(episode: dict[str, Any]) -> str:
    """Directory name under the dataset folder: episode UUID."""
    eid = str(episode.get("id") or "").strip()
    return eid or "unknown"


def resolve_node_urls(
    client: DatagridClient, node: dict[str, Any]
) -> tuple[str, str, str, str, str]:
    """Return (public_url, internal_url, file_name, checksum, checksum_algo)."""
    public = (node.get("download_url") or "").strip()
    internal = (node.get("download_url_internal") or "").strip()
    node_type = node.get("node_type") or "file"
    fallback = f"{node_type}.bin"
    file_name = safe_file_name(str(node.get("file_name") or ""), "")
    checksum = (node.get("checksum") or "").strip()
    checksum_algo = (node.get("checksum_algo") or "").strip()

    def _merge_from_file_api(file_id: str) -> None:
        nonlocal public, internal, file_name, checksum, checksum_algo
        data = client.file_download_url(file_id) or {}
        if not public:
            public = (data.get("download_url") or "").strip()
        if not internal:
            internal = (data.get("download_url_internal") or "").strip()
        if not file_name:
            file_name = safe_file_name(str(data.get("file_name") or ""), "")
        if not checksum:
            checksum = (data.get("checksum") or "").strip()
        if not checksum_algo:
            checksum_algo = (data.get("checksum_algo") or "").strip()

    if public or internal:
        if not file_name or not checksum:
            file_id = (node.get("file_id") or "").strip()
            if file_id:
                _merge_from_file_api(file_id)
        if not file_name:
            file_name = filename_from_url(public or internal, fallback)
        return public, internal, file_name, checksum, checksum_algo

    file_id = (node.get("file_id") or "").strip()
    if not file_id:
        raise APIError(f"node {node.get('node_id')} has no download_url/file_id")

    _merge_from_file_api(file_id)
    if not public and not internal:
        raise APIError(f"empty download_url for file_id={file_id}")
    if not file_name:
        file_name = filename_from_url(public or internal, f"{file_id}.bin")
    return public, internal, file_name, checksum, checksum_algo


def planned_file_name(node: dict[str, Any]) -> str:
    """Best-effort name for dry-run without calling download-url."""
    node_type = node.get("node_type") or "file"
    name = safe_file_name(str(node.get("file_name") or ""), "")
    if name:
        return name
    return f"{node_type}.bin"


def download_file(
    url: str,
    dest: Path,
    *,
    overwrite: bool,
    timeout: float,
    retries: int = 3,
    checksum: str = "",
    checksum_algo: str = "",
) -> str:
    """Download to dest. Skip when local MD5 matches platform checksum."""
    expected = (checksum or "").strip()
    if dest.exists() and not overwrite:
        if expected and is_md5_algo(checksum_algo):
            if local_matches_checksum(dest, expected, checksum_algo):
                return "skipped"
            # Exists but corrupt / stale → re-download.
        else:
            # No usable checksum: keep previous skip-if-exists behavior.
            return "skipped"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            fh.write(chunk)
            if expected and is_md5_algo(checksum_algo):
                actual = md5_file(tmp)
                if actual != expected.lower():
                    tmp.unlink(missing_ok=True)
                    raise APIError(
                        f"md5 mismatch for {dest.name}: "
                        f"expected={expected.lower()} actual={actual}"
                    )
            tmp.replace(dest)
            return "downloaded"
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
    raise APIError(f"download failed after {retries} retries: {last_err}")


def iter_all_episodes(
    client: DatagridClient,
    dataset_id: str,
    page_size: int,
    *,
    production_task_ids: list[str] | None = None,
    task_template_ids: list[int] | None = None,
    episode_ids: list[str] | None = None,
):
    page = 1
    total: int | None = None
    fetched = 0
    while True:
        data = (
            client.list_episodes(
                dataset_id,
                page=page,
                limit=page_size,
                production_task_ids=production_task_ids,
                task_template_ids=task_template_ids,
                episode_ids=episode_ids,
            )
            or {}
        )
        items = data.get("list") or []
        if total is None:
            total = int(data.get("total") or 0)
        if not items:
            break
        for item in items:
            yield item
        fetched += len(items)
        if total is not None and fetched >= total:
            break
        if len(items) < page_size:
            break
        page += 1


def build_jobs(
    client: DatagridClient,
    dataset_id: str,
    format_groups: list[list[str]],
    mode: str,
    output_dir: Path,
    page_size: int,
    limit: int | None = None,
    episode_ids: list[str] | None = None,
    endpoint: EndpointMode = "auto",
    production_task_ids: list[str] | None = None,
    task_template_ids: list[int] | None = None,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    episode_count = 0
    endpoint_logged = False
    for episode in iter_all_episodes(
        client,
        dataset_id,
        page_size,
        production_task_ids=production_task_ids,
        task_template_ids=task_template_ids,
        episode_ids=episode_ids,
    ):
        nodes_in = list(episode.get("data_nodes") or [])
        video = episode_video_node(episode)
        if video is not None:
            nodes_in.append(video)
        nodes = select_nodes(nodes_in, format_groups, mode)
        if not nodes:
            continue
        episode_count += 1
        if limit is not None and episode_count > limit:
            break
        # {output}/{dataset_id}/{episode_id}/{file_name}
        ep_dir = output_dir / dataset_id / episode_dir_name(episode)
        for node in nodes:
            node_type = node.get("node_type") or "unknown"
            checksum = (node.get("checksum") or "").strip()
            checksum_algo = (node.get("checksum_algo") or "").strip()
            if dry_run:
                file_name = planned_file_name(node)
                url = ""
            else:
                public, internal, file_name, checksum, checksum_algo = resolve_node_urls(
                    client, node
                )
                url = pick_download_url(
                    public,
                    internal,
                    endpoint,
                    log=not endpoint_logged,
                )
                endpoint_logged = True
            dest = ep_dir / file_name
            jobs.append(
                {
                    "episode_id": episode.get("id"),
                    "episode_index": episode.get("episode_index"),
                    "node_type": node_type,
                    "url": url,
                    "dest": dest,
                    "checksum": checksum,
                    "checksum_algo": checksum_algo,
                }
            )
    return jobs


def download_dataset(
    *,
    base_url: str,
    token: str,
    dataset_id: str,
    formats: list[str],
    mode: str = "sequential",
    output: str | Path = "./downloads",
    page_size: int = 50,
    workers: int = 4,
    timeout: float = 120.0,
    limit: int | None = None,
    episode_ids: list[str] | set[str] | None = None,
    endpoint: EndpointMode = "auto",
    overwrite: bool = False,
    dry_run: bool = False,
    match_task: str | None = None,
    production_task_ids: list[str] | None = None,
    allow_multiple_tasks: bool = False,
) -> dict[str, int]:
    if mode not in ("all", "sequential"):
        raise ValueError("mode must be 'all' or 'sequential'")
    if endpoint not in ("auto", "internal", "public"):
        raise ValueError("endpoint must be 'auto', 'internal', or 'public'")

    format_groups = resolve_formats(formats)
    client = DatagridClient(base_url=base_url, token=token, timeout=timeout)

    detail = client.dataset_detail(dataset_id) or {}
    dataset_name = detail.get("dataset_name") or dataset_id
    print(f"dataset: {dataset_name} ({dataset_id})")
    print(f"format mode: {mode}")
    print(
        "formats: "
        + (
            " > ".join("|".join(group) for group in format_groups)
            if mode == "sequential"
            else ", ".join("|".join(group) for group in format_groups)
        )
    )

    resolved_task_ids = resolve_production_task_ids(
        client,
        dataset_id,
        query=match_task,
        ids=production_task_ids,
        require_unique=not allow_multiple_tasks,
    )

    output_dir = Path(output).expanduser().resolve()
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        print(f"limit: {limit} episodes")
    if dry_run:
        print("dry-run: planning only (no files will be downloaded)")
    print("collecting download jobs...")
    ep_ids: list[str] | None = None
    if episode_ids:
        # Preserve order, drop empties/dupes; server filters via episode/list ids.
        seen: set[str] = set()
        ep_ids = []
        for raw in episode_ids:
            eid = str(raw).strip()
            if not eid or eid in seen:
                continue
            seen.add(eid)
            ep_ids.append(eid)
        if not ep_ids:
            ep_ids = None
        else:
            print(f"episode ids: {len(ep_ids)}")
    jobs = build_jobs(
        client=client,
        dataset_id=dataset_id,
        format_groups=format_groups,
        mode=mode,
        output_dir=output_dir,
        page_size=page_size,
        limit=limit,
        episode_ids=ep_ids,
        endpoint=endpoint,
        production_task_ids=resolved_task_ids or None,
        dry_run=dry_run,
    )
    if not jobs:
        print("no matching downloadable files found")
        return {"downloaded": 0, "skipped": 0, "failed": 0, "planned": 0}

    if dry_run:
        print_dry_run_plan(jobs)
        return {
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "planned": len(jobs),
        }

    print(f"jobs: {len(jobs)}")
    ok = skipped = failed = 0

    def _one(job: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
        try:
            status = download_file(
                job["url"],
                job["dest"],
                overwrite=overwrite,
                timeout=timeout,
                checksum=str(job.get("checksum") or ""),
                checksum_algo=str(job.get("checksum_algo") or ""),
            )
            return status, job, None
        except Exception as exc:  # noqa: BLE001
            return "failed", job, str(exc)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_one, job) for job in jobs]
        for fut in as_completed(futures):
            status, job, err = fut.result()
            label = (
                f"ep={job.get('episode_index')} "
                f"type={job['node_type']} -> {job['dest']}"
            )
            if status == "downloaded":
                ok += 1
                print(f"[ok] {label}")
            elif status == "skipped":
                skipped += 1
                print(f"[skip] {label}")
            else:
                failed += 1
                print(f"[fail] {label}: {err}", file=sys.stderr)

    print(f"done: downloaded={ok} skipped={skipped} failed={failed}")
    return {"downloaded": ok, "skipped": skipped, "failed": failed, "planned": len(jobs)}
