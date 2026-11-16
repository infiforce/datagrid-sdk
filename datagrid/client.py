"""HTTP client for Datagrid / data-platform APIs."""

from __future__ import annotations

from typing import Any

import requests


class APIError(RuntimeError):
    pass


class DatagridClient:
    """Authenticated client using X-Internal-Service-Token (API credential)."""

    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Internal-Service-Token": token,
                "Accept": "application/json",
            }
        )

    def _unwrap(self, resp: requests.Response) -> Any:
        try:
            payload = resp.json()
        except ValueError as exc:
            raise APIError(
                f"non-JSON response HTTP {resp.status_code}: {resp.text[:300]}"
            ) from exc
        if resp.status_code >= 400:
            raise APIError(
                f"HTTP {resp.status_code}: {payload.get('errmsg') or payload}"
            )
        errno = payload.get("errno")
        if errno not in (0, None):
            raise APIError(
                f"API errno={errno}: {payload.get('errmsg') or payload}"
            )
        return payload.get("data")

    def get(self, path: str, **kwargs: Any) -> Any:
        resp = self.session.get(
            f"{self.base_url}{path}", timeout=self.timeout, **kwargs
        )
        return self._unwrap(resp)

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = self.session.post(
            f"{self.base_url}{path}", json=json or {}, timeout=self.timeout
        )
        return self._unwrap(resp)

    def dataset_detail(self, dataset_id: str) -> dict[str, Any]:
        return self.get(f"/api/v1/dataset/detail/{dataset_id}")

    def list_episodes(
        self,
        dataset_id: str,
        page: int,
        limit: int,
        *,
        production_task_ids: list[str] | None = None,
        task_template_ids: list[int] | None = None,
        episode_ids: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "dataset_id": dataset_id,
            "page": page,
            "limit": limit,
        }
        if production_task_ids:
            if len(production_task_ids) == 1:
                body["production_task_id"] = production_task_ids[0]
            else:
                body["production_task_ids"] = list(production_task_ids)
        if task_template_ids:
            if len(task_template_ids) == 1:
                body["task_template_id"] = task_template_ids[0]
            else:
                body["task_template_ids"] = list(task_template_ids)
        if episode_ids:
            # Server-side filter: EpisodeListRequest.EpisodeIDs (`ids`).
            cleaned = [str(x).strip() for x in episode_ids if str(x).strip()]
            if cleaned:
                body["ids"] = cleaned
        body.update(extra)
        return self.post("/api/v1/episode/list", json=body)

    def list_production_tasks(
        self,
        dataset_id: str,
        *,
        keyword: str = "",
        page: int = 1,
        limit: int = 50,
        ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fuzzy/exact production-task lookup via data-platform → crowd proxy."""
        body: dict[str, Any] = {
            "dataset_id": dataset_id,
            "page": page,
            "limit": limit,
        }
        if keyword.strip():
            body["keyword"] = keyword.strip()
        if ids:
            body["ids"] = list(ids)
        return self.post("/api/v1/crowdsource/production-tasks", json=body) or {}

    def file_download_url(self, file_id: str) -> dict[str, Any]:
        return self.get(f"/api/v1/file/{file_id}/download-url")
