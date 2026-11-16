"""Datagrid SDK: download dataset artifacts from the Datagrid / data-platform API."""

from __future__ import annotations

from datagrid.client import APIError, DatagridClient
from datagrid.download import download_dataset

__version__ = "0.1.0"

__all__ = [
    "APIError",
    "DatagridClient",
    "download_dataset",
    "__version__",
]
