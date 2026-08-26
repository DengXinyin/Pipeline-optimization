#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据一次或多次 WDL 运行结果，以文件级别更新 sample_registry.tsv。

每一行代表一个文件（或目录），包含所属样本、项目、task、文件绝对路径等信息。

功能：
1. 从 call-check_input_with_raw/execution/metadatadir/project_info.json 提取项目编号和项目名称。
2. 递归扫描 WDL 执行目录下所有 call-* task 目录中的文件。
3. 为每个文件生成一条 registry 记录，追加到现有 registry（按 file_path 去重）。
4. 跨批次匹配：按 project_no + project_name + customer_name 识别同一客户同一项目。
5. 支持扫描多个 execution 目录，或自动扫描 cromwell-executions 下的所有历史 workflow 目录。

用法示例：
  # 扫描单个 workflow 执行目录
  python3 scripts/update_registry_from_wdl.py \
      --registry cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv \
      --execution-dir cromwell-executions/metage_v2_88_2/750c07e1-4cda-4d74-a55e-11ed3adc5119 \
      --out cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv

  # 扫描多个 workflow 执行目录
  python3 scripts/update_registry_from_wdl.py \
      --registry cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv \
      --execution-dir dir1 --execution-dir dir2 \
      --out cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv

  # 自动扫描 cromwell-executions 下所有历史 workflow 目录
  python3 scripts/update_registry_from_wdl.py \
      --registry cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv \
      --auto-scan-parent cromwell-executions \
      --skip-workflow test_workflow \
      --out cromwell-executions/metage_v2_88_2/registry/sample_registry.tsv
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

# 复用 registry 工具函数
sys.path.insert(0, str(Path(__file__).parent))
from registry_utils import build_registry_filename, sanitize_filename_part


REGISTRY_COLUMNS = [
    "internal_id", "display_name", "group", "project_no", "project_name", "customer_name",
    "task", "file_path", "description", "status",
]


def empty_registry():
    """Return an empty registry with the canonical schema."""
    return pd.DataFrame(columns=REGISTRY_COLUMNS)


def read_project_info(execution_dir):
    """从 workflow 执行目录中查找 project_info.json 读取项目信息。"""
    execution_dir = Path(execution_dir)
    candidates = [
        # 优先从原始输入 task 读取
        execution_dir / "call-check_input_with_raw" / "execution" / "metadatadir" / "project_info.json",
        execution_dir / "call-check_input_no_raw" / "execution" / "metadatadir" / "project_info.json",
        # cache miss 时 check_input 可能没产生 execution/metadatadir，从 apply_registry 的输出读取
        execution_dir / "call-apply_registry" / "execution" / "new_metadatadir" / "project_info.json",
        # 再从 inputs 目录查找
        execution_dir / "call-apply_registry" / "inputs" / "733964819" / "metadatadir" / "project_info.json",
        # call-cache 命中时，文件可能出现在 cacheCopy 子目录中
        execution_dir / "call-check_input_with_raw" / "cacheCopy" / "execution" / "metadatadir" / "project_info.json",
        execution_dir / "call-check_input_no_raw" / "cacheCopy" / "execution" / "metadatadir" / "project_info.json",
        execution_dir / "call-apply_registry" / "cacheCopy" / "execution" / "new_metadatadir" / "project_info.json",
        execution_dir / "call-resFile" / "cacheCopy" / "Input" / "project_info.json",
    ]
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


def read_sample_metadata(execution_dir):
    """从 workflow 执行目录中查找 sample-metadata.tsv，提取每个 internal_id 的 group 和 display_name。

    优先查找 check_input_* / apply_registry 输出中的 sample-metadata.tsv，
    并尝试同目录下的 display_name_map.tsv 作为 display_name 来源。
    """
    execution_dir = Path(execution_dir)
    candidates = [
        execution_dir / "call-check_input_with_raw" / "execution" / "metadatadir" / "sample-metadata.tsv",
        execution_dir / "call-check_input_no_raw" / "execution" / "metadatadir" / "sample-metadata.tsv",
        execution_dir / "call-apply_registry" / "execution" / "new_metadatadir" / "sample-metadata.tsv",
        execution_dir / "call-check_input_with_raw" / "cacheCopy" / "execution" / "metadatadir" / "sample-metadata.tsv",
        execution_dir / "call-check_input_no_raw" / "cacheCopy" / "execution" / "metadatadir" / "sample-metadata.tsv",
        execution_dir / "call-apply_registry" / "cacheCopy" / "execution" / "new_metadatadir" / "sample-metadata.tsv",
    ]
    group_map = {}
    display_map = {}
    for meta_path in candidates:
        if not meta_path.exists():
            continue
        try:
            df = pd.read_csv(meta_path, sep="\t", dtype=str, comment=None)
            sample_col = None
            for col in ["sample-id", "sample", "Sample", "sample_id"]:
                if col in df.columns:
                    sample_col = col
                    break
            if sample_col is None:
                continue
            for _, r in df.iterrows():
                iid = str(r[sample_col]).strip()
                if not iid or iid.startswith("#"):
                    continue
                for col in df.columns:
                    if col == sample_col:
                        continue
                    val = str(r.get(col, "")).strip()
                    if not val:
                        continue
                    if col.lower().startswith("group"):
                        if not group_map.get(iid, ""):
                            group_map[iid] = val
            # 尝试同目录下的 display_name_map.tsv
            display_path = meta_path.parent / "display_name_map.tsv"
            if display_path.exists():
                try:
                    disp_df = pd.read_csv(display_path, sep="\t", dtype=str)
                    if "internal_id" in disp_df.columns and "display_name" in disp_df.columns:
                        for _, r in disp_df.iterrows():
                            iid = str(r["internal_id"]).strip()
                            disp = str(r["display_name"]).strip()
                            if iid and disp and not display_map.get(iid, ""):
                                display_map[iid] = disp
                except Exception as e:
                    print(f"警告：读取 display_name_map {display_path} 失败: {e}", file=sys.stderr)
            return group_map, display_map
        except Exception as e:
            print(f"警告：读取 {meta_path} 失败: {e}", file=sys.stderr)
    return group_map, display_map


def copy_registry_to_dir(registry_path, target_dir, project_no, project_name, customer_name):
    """将 registry 复制到 target_dir，并按项目信息重命名。"""
    registry_path = Path(registry_path)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = build_registry_filename(project_no, project_name, customer_name)
    target_path = target_dir / target_name
    shutil.copy2(registry_path, target_path)
    print(f"复制 registry 到 task execution 目录: {target_path}")
    return target_path


def infer_internal_id(file_path, task_name, known_ids=None):
    """
    尝试从文件路径/名推断 internal_id。
    策略：
    1. 优先从 FASTQ-like 文件名推断：{sample}_R1.fq.gz 等。
    2. 尝试从 .sort.bam 文件名推断：{sample}.sort.bam。
    3. 如果提供了 known_ids，检查文件路径中是否出现某个已知 internal_id（用于识别按样本目录存放的文件）。
    """
    known_ids = known_ids or set()
    file_path_str = str(file_path)

    # 1. FASTQ-like 文件名
    m = re.search(r"/([A-Za-z0-9_-]+)_R?[12]\.(fq|fastq)\.gz", file_path_str)
    if m:
        return m.group(1)
    # 2. .sort.bam 文件名
    m = re.search(r"/([A-Za-z0-9_-]+)\.sort\.bam", file_path_str)
    if m:
        return m.group(1)
    # 3. 路径目录名中匹配已知样本名
    if known_ids:
        for iid in sorted(known_ids, key=len, reverse=True):
            if not iid:
                continue
            if f"/{iid}/" in file_path_str:
                return iid
    # 4. 文件名前缀/内嵌匹配已知样本名（如 RCK1_mapped.txt、RCK1.faa、RCK1_length.txt）
    if known_ids:
        fname = file_path.name
        for iid in sorted(known_ids, key=len, reverse=True):
            if not iid:
                continue
            # 文件名以 iid 开头，后接 _ 或 .
            if fname.startswith(f"{iid}_") or fname.startswith(f"{iid}."):
                return iid
    return ""


def scan_wdl_files(execution_dir, known_ids=None):
    """
    扫描 execution_dir 下所有 call-* 目录中的文件，返回文件记录列表。
    默认跳过 Cromwell 运行时元数据、脚本、日志以及 megahit 的 intermediate_contigs 等中间目录。
    known_ids: 已知的 internal_id 集合，用于从路径目录名识别样本。
    """
    execution_dir = Path(execution_dir)
    records = []

    # 跳过的文件名（Cromwell 运行时元数据）
    skip_names = {
        "script", "script.submit", "script.background",
        "stdout", "stderr", "stdout.background", "stderr.background",
        "rc", "docker_cid", "memory_retry_rc", "background",
        "submit", "list",
        "script.kill", "stdout.kill", "stderr.kill",
    }
    # 跳过的扩展名
    skip_suffixes = {".log", ".tmp", ".lock"}
    # 跳过 registry 文件自身，避免把 registry 复制进 registry
    skip_name_patterns = (r"_sample_registry\.tsv$",)
    # 跳过的前端资源文件扩展名（HTML 报告依赖，但本身无分析价值）
    skip_asset_suffixes = {".js", ".css", ".scss", ".map"}
    # 跳过的空占位文件
    skip_empty_files = {".file"}
    # 跳过的中间目录名（任何路径片段匹配即跳过）
    skip_dir_parts = {
        "intermediate_contigs",  # megahit 中间 contig
        "cacheCopy",             # Cromwell call caching 拷贝目录
        "tmp",                   # 临时目录
        "jquery-3.5.1",          # R/htmlwidgets 报告依赖库
    }
    # 按目录名后缀/前缀匹配跳过
    skip_dir_suffixes = ("_files",)  # R 生成的 HTML 报告资源目录
    skip_dir_prefixes = ("jquery-",)  # jQuery 资源目录

    for call_dir in sorted(execution_dir.glob("call-*")):
        if not call_dir.is_dir():
            continue
        task_name = call_dir.name[len("call-"):]
        exec_dir = call_dir / "execution"
        if not exec_dir.exists():
            exec_dir = call_dir

        # 递归扫描文件
        for file_path in sorted(exec_dir.rglob("*")):
            if not file_path.is_file():
                continue

            if file_path.name in skip_names:
                continue
            if file_path.name in skip_empty_files:
                continue
            if any(re.search(p, file_path.name) for p in skip_name_patterns):
                continue
            suffix = file_path.suffix.lower()
            if suffix in skip_suffixes:
                continue
            if suffix in skip_asset_suffixes:
                continue

            # 跳过中间目录
            rel_parts = file_path.relative_to(exec_dir).parts
            parts = set(rel_parts)
            if parts & skip_dir_parts:
                continue
            if any(p.endswith(skip_dir_suffixes) for p in rel_parts):
                continue
            if any(p.startswith(skip_dir_prefixes) for p in rel_parts):
                continue

            internal_id = infer_internal_id(file_path, task_name, known_ids)
            records.append({
                "internal_id": internal_id,
                "task": task_name,
                "file_path": str(file_path.resolve()),
                "description": file_path.name,
            })
    return records


def load_registry(registry_path):
    """读取现有 registry；首次 full 运行允许文件不存在或内容为空。"""
    registry_path = Path(registry_path)
    if not registry_path.exists():
        print(f"registry 不存在，将初始化新文件: {registry_path}")
        return empty_registry()
    try:
        return pd.read_csv(registry_path, sep="\t", dtype=str)
    except pd.errors.EmptyDataError:
        # full 模式首次运行时 registry 可能尚未创建，测试包中也可能只有
        # 一个空白占位文件。此处负责初始化；reuse/incremental 对非空
        # registry 的要求仍由 WDL prepare_registry_context 严格校验。
        print(f"registry 为空，将按标准字段初始化: {registry_path}")
        return empty_registry()


def update_registry(registry_df, project_info, file_records, filter_project_no=None,
                      metadata_group_map=None, metadata_display_map=None):
    """更新文件级别的 registry DataFrame。

    1. 先读取已有 registry 中的 display_name/group 作为历史 fallback。
    2. 当前 workflow metadata 中的值覆盖历史值。
    3. 更新后，对所有相同 internal_id 的 registry 记录统一刷新。
    """
    project_no = project_info.get("project_no", "")
    project_name = project_info.get("project_name", "")
    customer_name = project_info.get("customer_name", "")

    if not project_no:
        print("警告：未提取到项目编号", file=sys.stderr)

    # 如果指定了 filter_project_no，要求 project_no 必须匹配
    if filter_project_no and project_no and project_no != filter_project_no:
        print(f"跳过：执行目录项目编号 {project_no} 与目标 {filter_project_no} 不一致")
        return registry_df

    # 尝试从 registry 推断项目名称
    if not project_name and not registry_df.empty:
        inferred = registry_df.loc[registry_df.get("project_no", "") == project_no, "project_name"].dropna()
        inferred = inferred[inferred != ""].unique()
        if len(inferred) == 1:
            project_name = inferred[0]
            print(f"提示：project_info.json 未提供项目名称，已从 registry 推断为: {project_name}")

    # 为 internal_id 建立 display_name/group 映射；当前 workflow metadata
    # 是权威状态，必须覆盖 registry 历史值。
    display_map = {}
    group_map = {}
    if not registry_df.empty and "internal_id" in registry_df.columns:
        for _, r in registry_df.iterrows():
            iid = str(r["internal_id"]).strip() if pd.notna(r["internal_id"]) else ""
            if not iid:
                continue
            if "display_name" in r and pd.notna(r["display_name"]) and str(r["display_name"]).strip():
                display_map[iid] = str(r["display_name"]).strip()
            if "group" in r and pd.notna(r["group"]) and str(r["group"]).strip():
                group_map[iid] = str(r["group"]).strip()

    if metadata_group_map:
        for iid, grp in metadata_group_map.items():
            if iid and grp:
                group_map[iid] = grp
    if metadata_display_map:
        for iid, disp in metadata_display_map.items():
            if iid and disp:
                display_map[iid] = disp

    new_rows = []
    for rec in file_records:
        iid = rec["internal_id"]
        new_rows.append({
            "internal_id": iid,
            "display_name": display_map.get(iid, rec.get("display_name", "")),
            "group": group_map.get(iid, ""),
            "project_no": project_no,
            "project_name": project_name,
            "customer_name": customer_name,
            "task": rec["task"],
            "file_path": rec["file_path"],
            "description": rec["description"],
            "status": "done",
        })

    new_df = pd.DataFrame(new_rows, columns=REGISTRY_COLUMNS)
    if registry_df.empty:
        return new_df

    merged = pd.concat([registry_df, new_df], ignore_index=True)
    merged = merged.drop_duplicates(subset=["file_path"], keep="last")

    # 当前成功 workflow 的 metadata 是样本显示名/分组的权威状态。必须覆盖
    # 所有历史文件记录，否则 rename/regroup 后 registry 仍保留旧值，下一次
    # 规划会重复报告同一变更。
    if not merged.empty and "internal_id" in merged.columns:
        for iid, grp in group_map.items():
            if not iid or not grp:
                continue
            mask = merged["internal_id"] == iid
            if mask.any():
                merged.loc[mask, "group"] = grp
        for iid, disp in display_map.items():
            if not iid or not disp:
                continue
            mask = merged["internal_id"] == iid
            if mask.any():
                merged.loc[mask, "display_name"] = disp

    return merged


def reorder_columns(registry_df):
    """调整列顺序。"""
    ordered = [c for c in REGISTRY_COLUMNS if c in registry_df.columns]
    ordered += [c for c in registry_df.columns if c not in REGISTRY_COLUMNS]
    return registry_df[ordered]


def discover_execution_dirs(parent_dir, skip_workflows=None):
    """
    自动发现 parent_dir 下所有 WDL workflow 执行目录。
    规则：
    - parent_dir 下每个 workflow 类型目录（如 metage_v2_88_2）
    - 其下每个 UUID 子目录（如 750c07e1-...）
    - 只要该子目录下存在 call-* 目录，即视为有效执行目录
    """
    parent_dir = Path(parent_dir)
    skip_workflows = set(skip_workflows or [])
    dirs = []
    for workflow_dir in sorted(parent_dir.iterdir()):
        if not workflow_dir.is_dir():
            continue
        if workflow_dir.name in skip_workflows:
            print(f"跳过 workflow 目录: {workflow_dir}")
            continue
        for run_dir in sorted(workflow_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            if any(d.name.startswith("call-") for d in run_dir.iterdir() if d.is_dir()):
                dirs.append(str(run_dir.resolve()))
    return dirs


def main():
    parser = argparse.ArgumentParser(description="根据 WDL 运行结果更新文件级别的 sample_registry.tsv")
    parser.add_argument("--registry", required=True, help="现有 registry TSV 路径")
    parser.add_argument("--execution-dir", action="append", default=None,
                        help="WDL workflow 执行目录（可多次指定）")
    parser.add_argument("--auto-scan-parent", default=None,
                        help="自动扫描该父目录下所有 workflow 执行目录（如 cromwell-executions）")
    parser.add_argument("--skip-workflow", action="append", default=None,
                        help="自动扫描时跳过的 workflow 名称（可多次指定，如 test_workflow）")
    parser.add_argument("--out", required=True,
                        help="输出 registry TSV 路径；如果指向目录，则根据项目信息自动生成命名文件")
    parser.add_argument("--copy-to", default=None,
                        help="将更新后的 registry 额外复制到该目录（如 WDL task execution 目录），使用项目信息命名")
    parser.add_argument("--filter-project-no", default=None,
                        help="只保留/更新指定项目编号的记录；默认从第一个执行目录的 project_info.json 或 registry 推断")
    parser.add_argument("--drop-missing", action="store_true",
                        help="清理 file_path 已不存在的记录（用于解决历史 workflow 目录被删除后留下的死记录）")
    args = parser.parse_args()

    # 收集所有待扫描的执行目录
    execution_dirs = []
    if args.execution_dir:
        execution_dirs.extend(args.execution_dir)
    if args.auto_scan_parent:
        auto_dirs = discover_execution_dirs(args.auto_scan_parent, args.skip_workflow)
        print(f"自动扫描到 {len(auto_dirs)} 个 workflow 执行目录")
        execution_dirs.extend(auto_dirs)

    if not execution_dirs:
        print("错误：未指定任何执行目录。请使用 --execution-dir 或 --auto-scan-parent", file=sys.stderr)
        sys.exit(1)

    registry_df = load_registry(args.registry)

    # 确定目标 project_no
    filter_project_no = args.filter_project_no
    if not filter_project_no:
        # 尝试从 registry 文件名推断：{项目编号}_xxx_sample_registry.tsv
        reg_basename = Path(args.registry).name
        parts = reg_basename.split("_")
        if parts and parts[0]:
            filter_project_no = parts[0]
            print(f"从 registry 文件名推断目标项目编号: {filter_project_no}")

    # 如果仍未确定，从第一个执行目录读取 project_info
    if not filter_project_no and execution_dirs:
        first_exec = Path(execution_dirs[0])
        if first_exec.exists():
            pi = read_project_info(first_exec)
            filter_project_no = pi.get("project_no", "")
            if filter_project_no:
                print(f"从执行目录推断目标项目编号: {filter_project_no}")

    # 对已有 registry 按 project_no 过滤，删除跨项目记录
    if filter_project_no and not registry_df.empty and "project_no" in registry_df.columns:
        before = len(registry_df)
        registry_df = registry_df[registry_df["project_no"].astype(str).str.strip() == filter_project_no]
        dropped = before - len(registry_df)
        if dropped:
            print(f"已清理 {dropped} 条跨项目记录（目标 project_no={filter_project_no}）")

    # 收集 registry 中已有的 internal_id，用于从路径目录名识别样本
    known_ids = set()
    if not registry_df.empty and "internal_id" in registry_df.columns:
        known_ids = set(registry_df["internal_id"].dropna().astype(str).str.strip())
        known_ids.discard("")

    # 逐个 execution_dir 扫描并更新 registry
    total_files = 0
    for exec_dir in execution_dirs:
        exec_dir = Path(exec_dir)
        if not exec_dir.exists():
            print(f"警告：执行目录不存在，跳过: {exec_dir}", file=sys.stderr)
            continue

        project_info = read_project_info(exec_dir)
        file_records = scan_wdl_files(exec_dir, known_ids)
        metadata_group_map, metadata_display_map = read_sample_metadata(exec_dir)
        if metadata_group_map:
            print(f"[{exec_dir.name}] 从 sample-metadata.tsv 回填 group: {len(metadata_group_map)} 个样本")

        print(f"[{exec_dir.name}] 项目信息：{project_info['project_no']} / {project_info['project_name']}，扫描到 {len(file_records)} 个文件")
        total_files += len(file_records)

        registry_df = update_registry(
            registry_df, project_info, file_records, filter_project_no,
            metadata_group_map=metadata_group_map,
            metadata_display_map=metadata_display_map,
        )
        # 更新 known_ids，使后续扫描能识别新出现的样本名
        new_ids = {rec["internal_id"] for rec in file_records if rec["internal_id"]}
        known_ids.update(new_ids)

    # 清理不存在的文件路径
    if args.drop_missing and not registry_df.empty and "file_path" in registry_df.columns:
        before = len(registry_df)
        registry_df = registry_df[registry_df["file_path"].apply(lambda p: Path(str(p)).exists())]
        dropped = before - len(registry_df)
        if dropped:
            print(f"已清理 {dropped} 条文件路径已不存在的记录")

    registry_df = reorder_columns(registry_df)

    # 解析 --out：如果是目录，根据项目信息生成命名文件
    out_path = Path(args.out)
    if out_path.is_dir():
        first_exec = Path(execution_dirs[0]) if execution_dirs else None
        project_info = read_project_info(first_exec) if first_exec and first_exec.exists() else {}
        project_no = project_info.get("project_no", "")
        project_name = project_info.get("project_name", "")
        customer_name = project_info.get("customer_name", "")

        if not project_no and "project_no" in registry_df.columns:
            pnos = registry_df["project_no"].dropna().astype(str).str.strip()
            pnos = pnos[pnos != ""]
            if not pnos.empty:
                project_no = pnos.iloc[0]
        if not project_name and "project_name" in registry_df.columns:
            pnames = registry_df["project_name"].dropna().astype(str).str.strip()
            pnames = pnames[pnames != ""]
            if not pnames.empty:
                project_name = pnames.iloc[0]

        out_filename = build_registry_filename(project_no, project_name, customer_name)
        out_path = out_path / out_filename
        args.out = str(out_path)

    registry_df.to_csv(args.out, sep="\t", index=False)
    print(f"已更新 registry: {args.out}，共 {len(registry_df)} 条记录，{len(registry_df.columns)} 列（本次累计扫描 {total_files} 个文件）")

    # 如果指定了 --copy-to，额外复制一份到 task execution 目录
    if args.copy_to and not registry_df.empty:
        # 使用第一个执行目录的项目信息；若无法读取则从 registry 推断
        first_exec = Path(execution_dirs[0]) if execution_dirs else None
        project_info = read_project_info(first_exec) if first_exec and first_exec.exists() else {}
        project_no = project_info.get("project_no", "")
        project_name = project_info.get("project_name", "")
        customer_name = project_info.get("customer_name", "")

        if not project_no and "project_no" in registry_df.columns:
            pnos = registry_df["project_no"].dropna().astype(str).str.strip()
            pnos = pnos[pnos != ""]
            if not pnos.empty:
                project_no = pnos.iloc[0]
        if not project_name and "project_name" in registry_df.columns:
            pnames = registry_df["project_name"].dropna().astype(str).str.strip()
            pnames = pnames[pnames != ""]
            if not pnames.empty:
                project_name = pnames.iloc[0]

        copy_registry_to_dir(args.out, args.copy_to, project_no, project_name, customer_name)


if __name__ == "__main__":
    main()
