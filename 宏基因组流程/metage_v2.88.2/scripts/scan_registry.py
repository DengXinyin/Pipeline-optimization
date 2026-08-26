#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描项目目录，自动生成/更新文件级别的 sample_registry.tsv。

每一行代表一个文件（或目录），包含所属样本、项目、task、文件绝对路径等信息。

功能：
1. 读取项目目录下的 project_info.json，提取项目编号和项目名称。
2. 扫描目录中的 FASTQ 文件，按 sample 名配对 R1/R2。
3. 输出/追加到 registry TSV。

用法示例：
  # 从单个项目目录生成新 registry
  python3 scripts/scan_registry.py --project-dir /path/to/project --out cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv

  # 追加多个项目目录到现有 registry
  python3 scripts/scan_registry.py --project-dir /path/to/project1 --project-dir /path/to/project2 \
      --existing cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv --out cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv

  # 指定分组信息（JSON 文件：{"sample_name": "group", ...}）
  python3 scripts/scan_registry.py --project-dir /path/to/project --group-map groups.json --out registry.tsv
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd


def read_project_info(project_dir, project_info_path=None):
    """读取 project_info.json，返回 (project_no, project_name, project_info_path)。"""
    candidates = []
    if project_info_path:
        candidates.append(Path(project_info_path))
    project_dir = Path(project_dir)
    candidates.extend([project_dir / "project_info.json", project_dir.parent / "project_info.json"])
    for info_path in candidates:
        if info_path.exists():
            try:
                with open(info_path, encoding="utf-8") as f:
                    info = json.load(f)
                return {
                    "project_no": str(info.get("项目编号", "")).strip(),
                    "project_name": str(info.get("项目名称", "")).strip(),
                    "customer_name": str(info.get("客户名称", "")).strip(),
                }
            except Exception as e:
                print(f"警告：读取 {info_path} 失败: {e}", file=sys.stderr)
    return {"project_no": "", "project_name": "", "customer_name": ""}


def find_fastq_pairs(project_dir):
    """
    扫描目录中的 FASTQ 文件，按 sample 名返回 {sample: (r1_path, r2_path)}。
    """
    project_dir = Path(project_dir)
    fastqs = sorted(project_dir.glob("*.fq.gz")) + sorted(project_dir.glob("*.fastq.gz"))

    r1_patterns = [
        re.compile(r"^(.*?)_R1\.(fq|fastq)\.gz$"),
        re.compile(r"^(.*?)_1\.(fq|fastq)\.gz$"),
    ]
    r2_patterns = [
        re.compile(r"^(.*?)_R2\.(fq|fastq)\.gz$"),
        re.compile(r"^(.*?)_2\.(fq|fastq)\.gz$"),
    ]

    r1_map = {}
    r2_map = {}
    for fq in fastqs:
        name = fq.name
        for pat in r1_patterns:
            m = pat.match(name)
            if m:
                r1_map[m.group(1)] = str(fq.resolve())
                break
        for pat in r2_patterns:
            m = pat.match(name)
            if m:
                r2_map[m.group(1)] = str(fq.resolve())
                break

    samples = sorted(set(r1_map.keys()) | set(r2_map.keys()))
    pairs = {}
    for s in samples:
        pairs[s] = (r1_map.get(s, ""), r2_map.get(s, ""))
    return pairs


def read_sample_xlsx(path):
    """读取客户上游的 data.xlsx，返回 {internal_id: {display_name, group}}。

    默认读取名为 'sample' 的 sheet，不存在则取第一个 sheet。
    列名识别：fastqfile / fastq_prefix / internal_id -> internal_id；
              sample / display_name / sample_name -> display_name；
              group / group1 / group2 ... -> group（取第一个非空值）。
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        try:
            df = pd.read_excel(path, sheet_name="sample", dtype=str, engine="openpyxl")
        except ValueError:
            df = pd.read_excel(path, sheet_name=0, dtype=str, engine="openpyxl")
    except Exception as e:
        print(f"警告：读取 {path} 失败: {e}", file=sys.stderr)
        return {}

    if df.empty:
        return {}

    fastq_col = None
    sample_col = None
    group_cols = []
    for col in df.columns:
        c = str(col).strip().lower()
        if c in ("fastqfile", "fastq_prefix", "internal_id"):
            fastq_col = col
        elif c in ("sample", "display_name", "sample_name"):
            sample_col = col
        elif c.startswith("group"):
            group_cols.append(col)

    if fastq_col is None:
        fastq_col = df.columns[0]
    if sample_col is None:
        sample_col = fastq_col
    if not group_cols:
        # fallback: 任意非 id/name 列作为 group
        for col in df.columns:
            if col != fastq_col and col != sample_col:
                group_cols.append(col)
                break

    metadata = {}
    for _, r in df.iterrows():
        iid = str(r[fastq_col]).strip()
        if not iid:
            continue
        display_name = str(r[sample_col]).strip() if sample_col and pd.notna(r[sample_col]) else iid
        group = ""
        for gc in group_cols:
            g = str(r[gc]).strip() if pd.notna(r[gc]) else ""
            if g:
                group = g
                break
        metadata[iid] = {
            "display_name": display_name or iid,
            "group": group,
        }
    return metadata


def load_json_map(path):
    """加载 JSON 映射文件。"""
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scan_projects(project_dirs, group_map=None, display_name_map=None, project_info_path=None, exclude_samples=None, metadata=None):
    """扫描多个项目目录，生成文件级别的 registry DataFrame。

    exclude_samples: 需要排除的样本名集合（set），这些样本的 FASTQ 记录不会被写入 registry。
    metadata: 从 data.xlsx 读取的样本元数据 {internal_id: {display_name, group}}。
              提供时，只写入 metadata 中列出的样本，并按其 display_name/group 填充。
    """
    group_map = group_map or {}
    display_name_map = display_name_map or {}
    exclude_samples = set(exclude_samples or [])
    metadata = metadata or {}
    allowed_ids = set(metadata.keys())

    rows = []
    for project_dir in project_dirs:
        project_dir = Path(project_dir)
        if not project_dir.exists():
            print(f"警告：目录不存在: {project_dir}", file=sys.stderr)
            continue

        project_info = read_project_info(project_dir, project_info_path)
        project_no = project_info["project_no"]
        project_name = project_info["project_name"]
        customer_name = project_info["customer_name"]

        # 项目级文件
        info_path = project_dir / "project_info.json"
        if info_path.exists():
            rows.append({
                "internal_id": "",
                "display_name": "",
                "group": "",
                "project_no": project_no,
                "project_name": project_name,
                "customer_name": customer_name,
                "task": "input",
                "file_path": str(info_path.resolve()),
                "description": "project_info.json",
                "status": "done",
            })

        # FASTQ 文件
        pairs = find_fastq_pairs(project_dir)
        for sample, (r1, r2) in pairs.items():
            if sample in exclude_samples:
                print(f"  排除样本: {sample}", file=sys.stderr)
                continue
            if metadata and sample not in allowed_ids:
                print(f"  跳过不在 data.xlsx 中的样本: {sample}", file=sys.stderr)
                continue
            if metadata:
                display_name = metadata[sample]["display_name"]
                group = metadata[sample]["group"]
            else:
                display_name = display_name_map.get(sample, sample)
                group = group_map.get(sample, "")
            base = {
                "internal_id": sample,
                "display_name": display_name,
                "group": group,
                "project_no": project_no,
                "project_name": project_name,
                "customer_name": customer_name,
                "task": "rawdata",
                "status": "done",
            }
            if r1:
                stat = Path(r1).stat()
                rows.append({**base, "file_path": r1, "description": "R1 FASTQ",
                             "size_bytes": str(stat.st_size), "mtime_ns": str(stat.st_mtime_ns)})
            if r2:
                stat = Path(r2).stat()
                rows.append({**base, "file_path": r2, "description": "R2 FASTQ",
                             "size_bytes": str(stat.st_size), "mtime_ns": str(stat.st_mtime_ns)})

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    cols = ["internal_id", "display_name", "group", "project_no", "project_name",
            "customer_name", "task", "file_path", "description", "status",
            "size_bytes", "mtime_ns"]
    df = df[[c for c in cols if c in df.columns]]
    return df


def main():
    parser = argparse.ArgumentParser(description="扫描项目目录生成文件级别的 sample_registry.tsv")
    parser.add_argument("--project-dir", required=True, action="append",
                        help="项目目录（可多次指定，包含 FASTQ 文件；project_info.json 可通过 --project-info 指定）")
    parser.add_argument("--project-info", default=None,
                        help="project_info.json 路径（当 project-dir 下没有 project_info.json 时使用）")
    parser.add_argument("--existing", default=None,
                        help="现有 registry TSV，新扫描结果将追加并去重（按 file_path）")
    parser.add_argument("--group-map", default=None,
                        help="分组映射 JSON 文件，格式：{\"sample\": \"group\", ...}")
    parser.add_argument("--display-name-map", default=None,
                        help="display_name 映射 JSON 文件，格式：{\"sample\": \"display_name\", ...}")
    parser.add_argument("--data-xlsx", default=None,
                        help="客户上游的 data.xlsx 路径，包含 sample 元数据（fastqfile/sample/group）")
    parser.add_argument("--exclude-samples", default=None,
                        help="逗号分隔的样本名，这些样本的 FASTQ 记录不会被扫描添加")
    parser.add_argument("--out", required=True, help="输出 registry TSV 路径")
    args = parser.parse_args()

    group_map = load_json_map(args.group_map)
    display_name_map = load_json_map(args.display_name_map)
    exclude_samples = set()
    if args.exclude_samples:
        exclude_samples = set([s.strip() for s in args.exclude_samples.split(",") if s.strip()])

    metadata = None
    if args.data_xlsx:
        metadata = read_sample_xlsx(args.data_xlsx)
        if metadata:
            print(f"从 {args.data_xlsx} 读取样本元数据: {len(metadata)} 个样本", file=sys.stderr)
        else:
            print(f"警告：未能从 {args.data_xlsx} 读取样本元数据", file=sys.stderr)

    new_df = scan_projects(args.project_dir, group_map, display_name_map, args.project_info, exclude_samples, metadata)
    if new_df.empty:
        print("未扫描到任何文件", file=sys.stderr)
        sys.exit(1)

    if args.existing:
        try:
            existing_df = pd.read_csv(args.existing, sep="\t", dtype=str)
            if existing_df.empty:
                print(f"注意：已有 registry 为空，将新建", file=sys.stderr)
                args.existing = None
        except (pd.errors.EmptyDataError, Exception) as e:
            print(f"注意：已有 registry 无法读取 ({e})，将新建", file=sys.stderr)
            args.existing = None
    if args.existing:
        merged = pd.concat([existing_df, new_df], ignore_index=True)

        def last_non_empty(s):
            """对同一 file_path 的多条记录，取最后一个非空值。"""
            s = s.dropna().astype(str).str.strip()
            s = s[s != ""]
            if s.empty:
                return ""
            return s.iloc[-1]

        # 当新的扫描记录 group/display_name 为空时，保留已有 registry 中的非空值
        for col in ["group", "display_name"]:
            if col in merged.columns:
                merged[col] = merged.groupby("file_path")[col].transform(last_non_empty)

        merged = merged.drop_duplicates(subset=["file_path"], keep="last")

        # 如果提供了 data.xlsx，registry 以 data.xlsx 中样本为界，删除已不在其中的样本记录
        if metadata:
            allowed_ids = set(metadata.keys()) | {""}
            if not merged.empty and "internal_id" in merged.columns:
                before = len(merged)
                merged = merged[merged["internal_id"].astype(str).isin(allowed_ids)]
                dropped = before - len(merged)
                if dropped:
                    print(f"  已清理 {dropped} 条不在 data.xlsx 中的旧记录", file=sys.stderr)

        cols = [c for c in new_df.columns if c in merged.columns]
        # 保持列顺序
        other_cols = [c for c in merged.columns if c not in cols]
        merged = merged[cols + other_cols]
        out_df = merged
    else:
        out_df = new_df

    out_df.to_csv(args.out, sep="\t", index=False)
    print(f"已生成 registry: {args.out}，共 {len(out_df)} 条记录，{len(out_df.columns)} 列")


if __name__ == "__main__":
    main()
