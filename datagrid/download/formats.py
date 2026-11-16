"""Format aliases and per-episode node selection."""

from __future__ import annotations

from typing import Any

FORMAT_ALIASES: dict[str, list[str]] = {
    "lerobot": ["lerobot_v2.1"],
    "mcap": ["raw_mcap"],
    "raw_mcap": ["raw_mcap"],
    "vis_mcap": ["vis_mcap"],
    "raw_episode": ["raw_episode"],
    "video": ["video"],
    "rlds": ["rlds"],
    "umi_raw": ["umi_raw"],
    "zarr_v3": ["zarr_v3"],
    "hdf5": ["hdf5"],
}

KNOWN_NODE_TYPES = {
    "raw_mcap",
    "raw_episode",
    "video",
    "lerobot_v2.1",
    "lerobot_v3.0",
    "rlds",
    "vis_mcap",
    "umi_raw",
    "zarr_v3",
    "hdf5",
    "depth_estimation",
    "hand_pose_estimation",
    "task_segments",
    "localization_result",
}


def resolve_formats(raw_formats: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    for item in raw_formats:
        key = item.strip().lower()
        if not key:
            continue
        if key in FORMAT_ALIASES:
            groups.append(list(FORMAT_ALIASES[key]))
            continue
        if key in KNOWN_NODE_TYPES or key.startswith("ann_"):
            groups.append([key])
            continue
        raise ValueError(
            f"unknown format {item!r}; "
            f"supported aliases={sorted(FORMAT_ALIASES)} "
            f"or exact node_type"
        )
    if not groups:
        raise ValueError("at least one format is required")
    return groups


def episode_video_node(episode: dict[str, Any]) -> dict[str, Any] | None:
    url = (episode.get("video_file_url") or "").strip()
    url_internal = (episode.get("video_file_url_internal") or "").strip()
    file_id = (episode.get("video_file_id") or "").strip()
    file_name = (episode.get("video_file_name") or "").strip()
    if not url and not url_internal and not file_id:
        return None
    return {
        "node_id": file_id or "video",
        "node_type": "video",
        "file_id": file_id,
        "file_name": file_name,
        "checksum": (episode.get("video_file_checksum") or "").strip(),
        "checksum_algo": (episode.get("video_file_checksum_algo") or "").strip(),
        "download_url": url,
        "download_url_internal": url_internal,
    }


def _node_downloadable(node: dict[str, Any]) -> bool:
    return bool(
        (node.get("download_url") or "").strip()
        or (node.get("download_url_internal") or "").strip()
        or (node.get("file_id") or "").strip()
    )


def select_nodes(
    data_nodes: list[dict[str, Any]],
    format_groups: list[list[str]],
    mode: str,
) -> list[dict[str, Any]]:
    by_type: dict[str, dict[str, Any]] = {}
    for node in data_nodes:
        node_type = (node.get("node_type") or "").strip()
        if not node_type:
            continue
        if not _node_downloadable(node):
            continue
        by_type.setdefault(node_type, node)

    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add_node(node: dict[str, Any]) -> None:
        key = node.get("node_id") or node.get("file_id") or node.get("node_type")
        if key in seen_ids:
            return
        seen_ids.add(str(key))
        selected.append(node)

    if mode == "sequential":
        for group in format_groups:
            for node_type in group:
                node = by_type.get(node_type)
                if node is not None:
                    add_node(node)
                    return selected
        return selected

    for group in format_groups:
        for node_type in group:
            node = by_type.get(node_type)
            if node is not None:
                add_node(node)
    return selected
