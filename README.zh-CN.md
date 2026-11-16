# datagrid-sdk

[English](README.md)

Datagrid 数据下载 **SDK + CLI**（v0.1）：按数据集批量下载 Episode 产物。

## 功能概览

- **CLI**：`datagrid download dataset ...`
- **SDK**：`from datagrid import download_dataset`
- 支持格式别名（如 `lerobot` / `mcap`）或精确 `node_type`
- 生产任务过滤（模糊匹配 / 精确 UUID）
- `--dry-run` 预览下载计划
- 内网 / 公网 endpoint 自动探测（不改写 OSS host）
- 本地 MD5 校验：一致则跳过，不一致则重下

## 仓库结构

```text
datagrid-sdk/
├── LICENSE
├── README.md              # 英文（默认）
├── README.zh-CN.md        # 中文（本文件）
├── pyproject.toml         # 包元数据与依赖
├── setup.py               # setuptools 兼容入口
└── datagrid/
    ├── __init__.py        # 对外导出 API
    ├── cli.py             # CLI：datagrid
    ├── client.py          # HTTP 客户端
    ├── network.py         # 内网/公网 URL 选择
    └── download/
        ├── __init__.py
        ├── dataset.py     # 数据集下载主流程
        ├── formats.py     # 格式别名与节点选择
        ├── filters.py     # 生产任务过滤 / dry-run
        └── checksum.py    # MD5 校验
```

## 安装

需要 Python **≥ 3.9**。

```bash
git clone git@github.com:infiforce/datagrid-sdk.git
cd datagrid-sdk
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

安装后可用：

| 入口 | 用法 |
|------|------|
| CLI | `datagrid` |
| SDK | `from datagrid import download_dataset` |

## 鉴权

通过环境变量或 CLI 参数提供 API 地址与凭证（`X-Internal-Service-Token`）：

```bash
export DATAGRID_BASE_URL="https://your-datagrid.example.com"
export DATAGRID_API_TOKEN="data_xxxx.yyyy"
```

也可在命令行传入：`--base-url` / `--token`。

## CLI 用法

```bash
# 预览（不下文件）：先确认命中范围
datagrid download dataset \
  --dataset-id <dataset-uuid> \
  --formats lerobot mcap \
  --match-task "室内导航" \
  --limit 10 \
  --dry-run

# 正式下载：最多 10 条有匹配文件的 episode
datagrid download dataset \
  --dataset-id <dataset-uuid> \
  --formats lerobot mcap \
  --match-task "室内导航" \
  --limit 10 \
  --output ./downloads
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `--base-url` / `--token` | API 地址与凭证；也可用 `DATAGRID_*` 环境变量 |
| `--dataset-id` | 数据集 UUID（必填） |
| `--formats` | 格式别名或精确 `node_type`；某 episode 无匹配则跳过该条 |
| `--mode` | `sequential`（默认，按优先级取第一个命中）/ `all`（全部命中格式） |
| `--limit N` | 最多下载 N 条有匹配文件的 episode |
| `--dry-run` | 只规划：打印将下载的路径，不拉文件 |
| `--match-task` | 按生产任务名/编码模糊匹配（默认须唯一命中） |
| `--production-task-id` | 精确生产任务 UUID（可多个；与 `--match-task` 互斥） |
| `--allow-multiple-tasks` | 允许 `--match-task` 命中多个生产任务 |
| `--endpoint` | `auto`（默认）/ `internal` / `public` |
| `--output` | 输出目录（默认 `./downloads`） |
| `--workers` | 并发下载线程数（默认 4） |
| `--episode-id` | 仅下载指定 episode UUID（走接口 `ids` 服务端过滤） |
| `--overwrite` | 强制覆盖本地已有文件 |

### 行为说明

- **断点 / 跳过**：本地已有文件且平台返回 MD5 且一致 → 跳过；不一致 → 重新下载。下载完成后也会做 MD5 校验。
- **`--endpoint auto`**：使用接口返回的 `download_url` 与 `download_url_internal`；探测内网可达则走内网，否则公网。**不会改写** OSS host。

## SDK 用法

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
    match_task="室内导航",
    limit=10,
    dry_run=True,  # 先预览；确认后改 False
)
# result: {"ok": n, "skipped": n, "failed": n, ...}
```

也可使用底层客户端：

```python
from datagrid import DatagridClient

client = DatagridClient(base_url="...", token="...")
detail = client.dataset_detail("<dataset-uuid>")
```

## 输出目录

```text
{output}/
  {dataset_id}/
    {episode_id}/
      {file_name}
```

`file_name` 使用接口返回的 `file_name`（视频为 `video_file_name`）。

## 格式别名

| 输入 | 解析为 node_type |
|------|------------------|
| `lerobot` | `lerobot_v2.1` |
| `mcap` / `raw_mcap` | `raw_mcap` |
| `video` | 预览视频字段 |
| `vis_mcap` | `vis_mcap` |
| `raw_episode` | `raw_episode` |
| `rlds` / `umi_raw` / `zarr_v3` / `hdf5` | 同名 |
| 其它已知类型 / `ann_*` | 原样匹配 |

`--mode sequential`：按 `--formats` 顺序，每个 episode 取**第一个**命中的格式。  
`--mode all`：下载所有命中的格式。

## 许可证

Proprietary — 见 [LICENSE](LICENSE)。版权归 Infiforce 所有。
