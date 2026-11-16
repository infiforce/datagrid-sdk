# datagrid-sdk

[中文文档](README.zh-CN.md)

Datagrid download **SDK + CLI** (v0.1): batch-download episode artifacts by dataset.

## Features

- **CLI**: `datagrid download dataset ...`
- **SDK**: `from datagrid import download_dataset`
- Format aliases (e.g. `lerobot` / `mcap`) or exact `node_type`
- Production-task filtering (fuzzy match / exact UUID)
- `--dry-run` to preview the download plan
- Auto internal / public endpoint selection (does **not** rewrite OSS hosts)
- Local MD5 checks: skip when matching, re-download when mismatched

## Repository layout

```text
datagrid-sdk/
├── LICENSE
├── README.md              # English (this file)
├── README.zh-CN.md        # Chinese
├── pyproject.toml         # package metadata & dependencies
├── setup.py               # setuptools compatibility shim
└── datagrid/
    ├── __init__.py        # public exports
    ├── cli.py             # CLI entry: datagrid
    ├── client.py          # HTTP client
    ├── network.py         # internal vs public URL selection
    └── download/
        ├── __init__.py
        ├── dataset.py     # dataset download pipeline
        ├── formats.py     # format aliases & node selection
        ├── filters.py     # production-task filters / dry-run
        └── checksum.py    # MD5 helpers
```

## Install

Requires Python **≥ 3.9**.

```bash
git clone git@github.com:infiforce/datagrid-sdk.git
cd datagrid-sdk
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

After install:

| Entry | Usage |
|-------|--------|
| CLI | `datagrid` |
| SDK | `from datagrid import download_dataset` |

## Authentication

Provide API base URL and credential (`X-Internal-Service-Token`) via env or CLI flags:

```bash
export DATAGRID_BASE_URL="https://your-datagrid.example.com"
export DATAGRID_API_TOKEN="data_xxxx.yyyy"
```

Or pass `--base-url` / `--token` on the command line.

## CLI

```bash
# Preview only (no downloads)
datagrid download dataset \
  --dataset-id <dataset-uuid> \
  --formats lerobot mcap \
  --match-task "indoor-nav" \
  --limit 10 \
  --dry-run

# Download up to 10 episodes that have matching files
datagrid download dataset \
  --dataset-id <dataset-uuid> \
  --formats lerobot mcap \
  --match-task "indoor-nav" \
  --limit 10 \
  --output ./downloads
```

### Common options

| Option | Description |
|--------|-------------|
| `--base-url` / `--token` | API URL & credential; or `DATAGRID_*` env vars |
| `--dataset-id` | Dataset UUID (required) |
| `--formats` | Format aliases or exact `node_type`; skip episode if none match |
| `--mode` | `sequential` (default: first hit) / `all` (every matched format) |
| `--limit N` | Download at most N episodes with matching files |
| `--dry-run` | Plan only: print paths, do not download |
| `--match-task` | Fuzzy match production task by name/code (must be unique by default) |
| `--production-task-id` | Exact production-task UUID(s); mutually exclusive with `--match-task` |
| `--allow-multiple-tasks` | Allow `--match-task` to resolve to multiple tasks |
| `--endpoint` | `auto` (default) / `internal` / `public` |
| `--output` | Output directory (default `./downloads`) |
| `--workers` | Concurrent download workers (default 4) |
| `--episode-id` | Restrict to these episode UUIDs (server-side `ids` filter) |
| `--overwrite` | Force overwrite existing local files |

### Behavior notes

- **Skip / re-download**: if a local file exists and the platform MD5 matches → skip; if it differs → re-download. MD5 is also verified after download.
- **`--endpoint auto`**: uses API-returned `download_url` and `download_url_internal`; prefers internal when reachable, otherwise public. Does **not** rewrite OSS hosts.

## SDK

```python
from datagrid import download_dataset

result = download_dataset(
    base_url="https://your-datagrid.example.com",
    token="data_xxxx.yyyy",
    dataset_id="<dataset-uuid>",
    formats=["lerobot", "mcap"],
    mode="sequential",
    output="./downloads",
    endpoint="auto",
    match_task="indoor-nav",
    limit=10,
    dry_run=True,  # preview first; set False to download
)
# result: {"ok": n, "skipped": n, "failed": n, ...}
```

Low-level client:

```python
from datagrid import DatagridClient

client = DatagridClient(base_url="...", token="...")
detail = client.dataset_detail("<dataset-uuid>")
```

## Output layout

```text
{output}/
  {dataset_id}/
    {episode_id}/
      {file_name}
```

`file_name` comes from the API (`video_file_name` for preview videos).

## Format aliases

| Input | Resolves to node_type |
|-------|------------------------|
| `lerobot` | `lerobot_v2.1` |
| `mcap` / `raw_mcap` | `raw_mcap` |
| `video` | preview video fields |
| `vis_mcap` | `vis_mcap` |
| `raw_episode` | `raw_episode` |
| `rlds` / `umi_raw` / `zarr_v3` / `hdf5` | same name |
| other known types / `ann_*` | matched as-is |

`--mode sequential`: for each episode, take the **first** format that matches `--formats` order.  
`--mode all`: download every matched format.

## License

Proprietary — see [LICENSE](LICENSE). Copyright Infiforce. All rights reserved.
