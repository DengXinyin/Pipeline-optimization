#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry 文件命名与查找工具函数。

registry 文件名格式：
    {项目编号}_{项目内容}_{客户名称}_sample_registry.tsv
    例如：SNWD042726060201_宏基因组测序_李梦娇_sample_registry.tsv

规则：
- 项目编号（project_no）必填，没有则使用 UNKNOWN_PROJECT
- 项目内容（project_name）可选
- 客户名称（customer_name）可选
- 所有部分清理非法字符（替换空白和 Windows/Unix 非法字符为下划线）
"""

import json
import re
import sys
from pathlib import Path


def sanitize_filename_part(s):
    """清理文件名中的非法字符。"""
    if s is None:
        return ""
    s = str(s)
    if not s:
        return ""
    s = re.sub(r'[\\/:*?"<>|\s]+', "_", s)
    s = s.strip("_")
    return s


def build_registry_filename(project_no, project_name, customer_name):
    """构建 registry 文件名。"""
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


def read_project_info(info_path):
    """读取 project_info.json，返回项目编号、项目名称、客户名称。"""
    info_path = Path(info_path)
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


def registry_project_identity(registry_path):
    """Read project identity from registry contents, falling back to its name."""
    import pandas as pd

    registry_path = Path(registry_path)
    identity = {"project_no": "", "project_name": "", "customer_name": ""}
    try:
        frame = pd.read_csv(registry_path, sep="\t", dtype=str, nrows=200)
        for key in identity:
            if key in frame.columns:
                values = frame[key].dropna().astype(str).str.strip()
                values = values[values != ""]
                if not values.empty:
                    identity[key] = values.iloc[0]
    except Exception as exc:
        print(f"警告：读取 registry 项目信息失败 {registry_path}: {exc}", file=sys.stderr)

    stem = registry_path.name
    suffix = "_sample_registry.tsv"
    if stem.endswith(suffix):
        parts = stem[:-len(suffix)].split("_")
        if not identity["project_no"] and parts:
            identity["project_no"] = parts[0]
        if not identity["project_name"] and len(parts) >= 2:
            identity["project_name"] = parts[1]
        if not identity["customer_name"] and len(parts) >= 3:
            identity["customer_name"] = "_".join(parts[2:])
    return identity


def project_identity_matches(actual, expected):
    """Require exact normalized project number/name/customer matching."""
    return all(
        sanitize_filename_part(actual.get(key, "")) == sanitize_filename_part(expected.get(key, ""))
        for key in ("project_no", "project_name", "customer_name")
    )


def find_registry_file(registry_dir, project_no, project_name="", customer_name=""):
    """
    在 registry_dir 中按项目编号、项目名称、客户名称三项精确查找。
    返回第一个匹配的文件路径，如果没有则返回 None。
    """
    registry_dir = Path(registry_dir)
    if not registry_dir.exists():
        return None
    expected = {
        "project_no": str(project_no or "").strip(),
        "project_name": str(project_name or "").strip(),
        "customer_name": str(customer_name or "").strip(),
    }
    prefix = sanitize_filename_part(project_no) + "_"
    for f in sorted(registry_dir.iterdir()):
        if not (f.is_file() and f.name.startswith(prefix) and f.name.endswith("_sample_registry.tsv")):
            continue
        if project_identity_matches(registry_project_identity(f), expected):
            return f
    return None


def resolve_registry_path(registry_dir, project_no, project_name, customer_name):
    """
    解析 registry 文件路径：
    - 如果 registry_dir 下已有三项身份都匹配的文件，返回该文件
    - 否则返回按项目信息生成的新文件路径
    """
    registry_dir = Path(registry_dir)
    registry_dir.mkdir(parents=True, exist_ok=True)

    existing = find_registry_file(registry_dir, project_no, project_name, customer_name)
    if existing:
        return existing

    filename = build_registry_filename(project_no, project_name, customer_name)
    return registry_dir / filename


def find_best_upstream_workflow(registry_tsv, project_root, workflow_name="metage_v2_88_2", required_calls=None):
    """
    自动匹配最近可用的上游 workflow ID。

    逻辑：
    1. 读取 registry，从 file_path 中提取曾为当前项目产出过文件的所有 workflow ID；
    2. 在 cromwell-executions/<workflow_name>/<workflow_id>/ 下检查关键上游 task 的 execution 目录是否存在；
    3. 返回最近（目录 mtime 最大）且关键 task 齐全的 workflow ID。

    参数：
        registry_tsv: registry TSV 文件路径
        project_root: 项目根目录（用于定位 cromwell-executions）
        workflow_name: WDL workflow 名称
        required_calls: 必须存在的 call 目录列表，默认检查 kneaddata_no / megahit_no / func_anno / tax_anno

    返回 workflow ID 字符串；未找到返回 None。
    """
    import pandas as pd

    registry_tsv = Path(registry_tsv)
    project_root = Path(project_root)

    required_calls = required_calls or [
        "call-kneaddata_no",
        "call-megahit_no",
        "call-func_anno",
        "call-tax_anno",
    ]

    # 从 registry file_path 中提取 workflow ID
    workflow_ids = set()
    if registry_tsv.exists():
        try:
            df = pd.read_csv(registry_tsv, sep="\t", dtype=str)
            if "file_path" in df.columns:
                pattern = re.compile(r"/cromwell-executions/" + re.escape(workflow_name) + r"/([^/]+)/")
                for fp in df["file_path"].dropna().astype(str):
                    m = pattern.search(fp)
                    if m:
                        workflow_ids.add(m.group(1))
        except Exception as e:
            print(f"警告：读取 registry 提取 workflow ID 失败: {e}", file=sys.stderr)

    executions_root = project_root / "cromwell-executions" / workflow_name
    if not executions_root.exists():
        return None

    candidates = []
    for wf_id in workflow_ids:
        wf_dir = executions_root / wf_id
        if not wf_dir.is_dir():
            continue
        missing = [c for c in required_calls if not (wf_dir / c / "execution").is_dir()]
        if missing:
            continue
        try:
            mtime = wf_dir.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, wf_id))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]
