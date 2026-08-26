#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据文件级别的 sample_registry.tsv 重写 metadatadir 中的 sample.txt 和 sample-metadata.tsv。

原则：
- internal_id 保持不变，用于定位上游结果文件路径和中间结果目录。
- sample.txt 和 sample-metadata.tsv 中的 sample 列保持 internal_id，仅更新 group 和删除已移除样本。
- display_name 仅通过 display_name_map.tsv 输出，在最终报告阶段（coll_res_ana / resFile）由 rewrite_display_names.py 替换展示。
- 将 registry 中的信息写入 new_metadatadir/sample-registry.json，便于追溯。

sample_registry.tsv 为文件级别，每行代表一个文件/记录，包含：
  internal_id, display_name, group, project_no, project_name, task, file_path, description, status
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd


def load_registry(registry_tsv):
    try:
        df = pd.read_csv(registry_tsv, sep="\t", dtype=str)
    except (pd.errors.EmptyDataError, Exception):
        print(f"警告：registry 文件为空或无法读取，将使用空注册表")
        df = pd.DataFrame(columns=["internal_id", "display_name", "group", "project_no", "project_name", "task", "file_path", "description", "status"])
    required = {"internal_id", "display_name", "group"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"registry 缺少必要列: {missing}")

    # 按 internal_id 聚合，取每个样本的 display_name、group、project_no、project_name
    # 遍历所有记录，后续非空值覆盖前面的，确保 rawdata 记录的更新能生效
    sample_records = {}
    project_no = ""
    project_name = ""
    for _, r in df.iterrows():
        iid = str(r["internal_id"]) if pd.notna(r["internal_id"]) else ""
        iid = iid.strip()
        if not iid:
            # 项目级记录
            if r.get("project_no"):
                project_no = r["project_no"]
            if r.get("project_name"):
                project_name = r["project_name"]
            continue
        if iid not in sample_records:
            sample_records[iid] = {
                "display_name": "",
                "group": "",
                "project_no": "" if pd.isna(r.get("project_no", "")) else str(r.get("project_no", "")),
                "project_name": "" if pd.isna(r.get("project_name", "")) else str(r.get("project_name", "")),
                "status": "" if pd.isna(r.get("status", "done")) else str(r.get("status", "done")),
                "files": [],
            }
        # 用后续非空值覆盖：display_name / group 从 data.xlsx → scan_registry → registry
        # rawdata 记录排在 task 记录之后，所以最后生效的是 rawdata 中的最新值
        dn = r.get("display_name", "")
        if pd.notna(dn) and str(dn).strip():
            sample_records[iid]["display_name"] = str(dn).strip()
        grp = r.get("group", "")
        if pd.notna(grp) and str(grp).strip():
            sample_records[iid]["group"] = str(grp).strip()
        pn = r.get("project_no", "")
        if pd.notna(pn) and str(pn).strip() and not sample_records[iid]["project_no"]:
            sample_records[iid]["project_no"] = str(pn).strip()
        pnm = r.get("project_name", "")
        if pd.notna(pnm) and str(pnm).strip() and not sample_records[iid]["project_name"]:
            sample_records[iid]["project_name"] = str(pnm).strip()
        sample_records[iid]["files"].append({
            "task": r.get("task", ""),
            "file_path": r.get("file_path", ""),
            "description": r.get("description", ""),
        })

    return sample_records, project_no, project_name


def read_project_info(datadir):
    """从 datadir/project_info.json 读取项目编号、项目名称、客户名称。"""
    info_path = Path(datadir) / "project_info.json"
    if not info_path.exists():
        return {"project_no": "", "project_name": "", "customer_name": ""}
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


def sanitize_filename_part(s):
    """清理文件名中的非法字符，替换为空格安全的形式。"""
    if s is None:
        return ""
    s = str(s)
    if not s:
        return ""
    # 替换 Windows/Unix 非法字符以及空白为下划线
    s = re.sub(r'[\\/:*?"<>|\s]+', "_", s)
    # 去除首尾下划线
    s = s.strip("_")
    return s


def build_registry_filename(project_no, project_name, customer_name):
    """构建 registry 文件名：项目编号_项目内容_客户名称_sample_registry.tsv"""
    project_no = sanitize_filename_part(project_no)
    project_name = sanitize_filename_part(project_name)
    customer_name = sanitize_filename_part(customer_name)

    if not project_no:
        project_no = "UNKNOWN_PROJECT"

    parts = [project_no]
    if project_name:
        parts.append(project_name)
    if customer_name:
        parts.append(customer_name)
    parts.append("sample_registry.tsv")
    return "_".join(parts)


def copy_registry_with_name(registry_tsv, outdir, project_info, registry_project_no, registry_project_name):
    """将 registry 复制到 outdir，并按项目信息重命名。"""
    registry_tsv = Path(registry_tsv)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    project_no = project_info.get("project_no") or registry_project_no
    project_name = project_info.get("project_name") or registry_project_name
    customer_name = project_info.get("customer_name", "")

    target_name = build_registry_filename(project_no, project_name, customer_name)
    target_path = outdir / target_name
    shutil.copy2(registry_tsv, target_path)
    print(f"复制 registry 到 task execution 目录: {target_path}")
    return target_path


def copy_datadir(datadir, outdir):
    """复制整个 datadir 到 outdir。"""
    if outdir.exists():
        shutil.rmtree(outdir)
    shutil.copytree(datadir, outdir)


def write_display_name_map(registry, out_tsv):
    """输出 internal_id -> display_name 映射表，供最终报告替换展示名。"""
    rows = []
    for iid, rec in registry.items():
        display_name = rec.get("display_name", "")
        if pd.isna(display_name):
            display_name = ""
        rows.append({"internal_id": iid, "display_name": display_name or iid})
    df = pd.DataFrame(rows, columns=["internal_id", "display_name"])
    df.to_csv(out_tsv, sep="\t", index=False)
    print(f"写入 display_name_map: {out_tsv}")


def find_col_index(header, candidates):
    """在 header 中查找候选列名，返回第一个匹配的索引。"""
    for col in candidates:
        for i, h in enumerate(header):
            if h.strip().lower() == col.lower():
                return i
    return None


def rewrite_sample_metadata(meta_tsv, registry, out_meta_tsv, sample_txt):
    """重写 sample-metadata.tsv：sample 列保持 internal_id，group 列按 registry 更新；
    不在 registry 中的样本会被删除。

    sample_txt 用于构建 display_name -> internal_id 映射，
    因为 sample-metadata.tsv 的 sample-id 列在改名后是 display_name。
    """
    # 构建 display_name -> internal_id 映射
    id_map = _build_id_map_from_sample_txt(sample_txt)

    with open(meta_tsv) as f:
        lines = f.readlines()

    if len(lines) < 2:
        raise ValueError(f"{meta_tsv} 内容不足")

    header = lines[0].strip().split("\t")
    sample_idx = find_col_index(header, ["sample-id", "sample", "Sample", "sample_id"])
    group_idx = find_col_index(header, ["group1", "group", "Group"])
    if sample_idx is None:
        raise ValueError(f"{meta_tsv} 缺少 sample 列（尝试：sample-id, sample, Sample, sample_id）")
    if group_idx is None:
        raise ValueError(f"{meta_tsv} 缺少 group 列（尝试：group1, group, Group）")

    out_lines = [lines[0]]
    if len(lines) > 1 and lines[1].strip().startswith("#"):
        out_lines.append(lines[1])

    for line in lines[1:]:
        line = line.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < max(sample_idx, group_idx) + 1:
            continue
        display_name = parts[sample_idx].strip()
        # 通过 sample.txt 映射找到 internal_id，用于匹配 registry
        internal_id = id_map.get(display_name, display_name)
        if internal_id not in registry:
            print(f"  从 sample-metadata.tsv 删除样本: {display_name}")
            continue
        # sample-id 列强制写回 internal_id，display_name 仅通过 display_name_map 传递
        parts[sample_idx] = internal_id
        group = registry[internal_id].get("group", "")
        group = "" if pd.isna(group) else str(group).strip()
        if not group:
            group = parts[group_idx].strip()
        parts[group_idx] = group
        out_lines.append("\t".join(parts) + "\n")

    with open(out_meta_tsv, "w") as f:
        f.writelines(out_lines)


def _build_id_map_from_sample_txt(sample_txt):
    """从 sample.txt 构建 display_name -> internal_id 映射。
    sample.txt 格式: fastqfile(internal_id)\tsample(display_name)
    """
    id_map = {}
    with open(sample_txt) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            # 跳过表头
            if parts[0].strip().lower() in ("fastqfile", "internal_id"):
                continue
            iid = parts[0].strip()   # fastqfile = internal_id
            dname = parts[1].strip()  # sample = display_name
            if iid:
                id_map[dname] = iid
    return id_map


def rewrite_sample_txt(sample_txt, registry, out_sample_txt):
    """重写 sample.txt：删除不在 registry 中的样本行。
    使用 fastqfile 列（parts[0]）匹配 registry internal_id。
    sample 列（parts[1]）强制写回 internal_id，因为下游 task 用它定位文件。
    display_name 只通过 display_name_map.tsv 传递。
    """
    with open(sample_txt) as f:
        lines = f.readlines()

    if not lines:
        raise ValueError(f"{sample_txt} 为空")

    header = lines[0].rstrip("\n")
    out_lines = [header + "\n"]

    for line in lines[1:]:
        line = line.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        # parts[0] = fastqfile (internal_id), parts[1] = sample (可能被改为 display_name)
        internal_id = parts[0].strip()
        if internal_id not in registry:
            print(f"  从 sample.txt 删除样本: {internal_id}")
            continue
        # 强制 sample 列 = internal_id，下游 task 用它定位文件
        parts[1] = internal_id
        out_lines.append("\t".join(parts) + "\n")

    with open(out_sample_txt, "w") as f:
        f.writelines(out_lines)
    print(f"重写 sample.txt 完成: {out_sample_txt}")


def write_registry_json(registry, project_no, project_name, out_json):
    """将样本级 registry 信息写入 JSON。"""
    output = {
        "project_no": project_no,
        "project_name": project_name,
        "samples": registry,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="根据文件级别 registry 重写 metadatadir")
    parser.add_argument("--datadir", required=True, help="原始 metadatadir")
    parser.add_argument("--registry", default=None, help="sample_registry.tsv（可选）")
    parser.add_argument("--outdir", required=True, help="输出目录（如 new_metadatadir）")
    parser.add_argument("--execution-dir", default=None,
                        help="task execution 目录，复制命名后的 registry 到该目录（默认=outdir 的父目录）")
    parser.add_argument("--copy-to-execution", action="store_true",
                        help="将 registry 按项目信息命名后复制到 execution-dir")
    args = parser.parse_args()

    datadir = Path(args.datadir)
    outdir = Path(args.outdir)

    if args.registry:
        registry, project_no, project_name = load_registry(args.registry)
    else:
        registry, project_no, project_name = {}, "", ""

    print(f"复制 {datadir} -> {outdir}")
    copy_datadir(datadir, outdir)

    if not registry:
        print("未提供 registry，直接复制，不重写")
        return

    # sample.txt 保持 internal_id，但删除 registry 中不存在的样本
    print("重写 sample.txt（保持 internal_id，删除已移除样本）")
    rewrite_sample_txt(
        datadir / "sample.txt",
        registry,
        outdir / "sample.txt"
    )

    print("重写 sample-metadata.tsv（仅更新 group，sample 保持 internal_id，删除已移除样本）")
    rewrite_sample_metadata(
        datadir / "sample-metadata.tsv",
        registry,
        outdir / "sample-metadata.tsv",
        datadir / "sample.txt"
    )

    print("写入 sample-registry.json")
    write_registry_json(registry, project_no, project_name, outdir / "sample-registry.json")

    print("写入 display_name_map.tsv")
    write_display_name_map(registry, outdir / "display_name_map.tsv")

    if args.copy_to_execution and args.registry:
        print("复制 registry 到 task execution 目录")
        project_info = read_project_info(datadir)
        execution_dir = Path(args.execution_dir) if args.execution_dir else outdir.parent
        copy_registry_with_name(args.registry, execution_dir, project_info, project_no, project_name)
        # 同时把 display_name_map 复制到 execution 目录，便于调试
        shutil.copy2(outdir / "display_name_map.tsv", execution_dir / "display_name_map.tsv")

    print("完成")


if __name__ == "__main__":
    main()
