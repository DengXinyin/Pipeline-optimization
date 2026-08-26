#!/usr/bin/env python3
"""Build a safe full/incremental/reuse execution plan for one project."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from registry_utils import (  # noqa: E402
    project_identity_matches,
    read_project_info,
    registry_project_identity,
    resolve_registry_path,
    sanitize_filename_part,
)


WORKFLOW_NAME = "metage_v2_88_2"
INPUT_PREFIX = WORKFLOW_NAME + "."
CROMWELL_WORKFLOW_ROOT = Path(
    "/cephfs_data/genostack_v3/genostack_cromwell/cromwell-executions"
) / WORKFLOW_NAME
STATE_PATHS = {
    "clean": ("merged/clean", "call-kneaddata_no/execution/cleandata"),
    "qc_result": ("merged/qc_result", "call-kneaddata_no/execution/Result"),
    "megahit": ("merged/megahit", "call-megahit_no/execution/megahit"),
    "prodigal": ("merged/prodigal", "call-prodig_no/execution/prodigal"),
    "bowtie": ("merged/bowtie", "call-bwa_no/execution/bowtie"),
    "tax_annotation": ("merged/tax_annotation", "call-tax_anno/execution/Annotation"),
    "func_annotation": ("merged/func_annotation", "call-func_anno/execution/Annotation"),
    "annotation": (None, "call-anno_cumulative/execution/Annotation", "call-anno_full/execution/Annotation", "call-anno/execution/Annotation"),
    "ARGs": ("merged/ARGs", "call-VCA_anno_full/execution/ARGs", "call-VCA_anno/execution/ARGs"),
    "CycDB": ("merged/CycDB", "call-VCA_anno_full/execution/CycDB", "call-VCA_anno/execution/CycDB"),
    "VFDB": ("merged/VFDB", "call-VCA_anno_full/execution/VFDB", "call-VCA_anno/execution/VFDB"),
    "BacMet2": ("merged/BacMet2", "call-MBQ_anno_full/execution/BacMet2", "call-MBQ_anno/execution/BacMet2"),
    "QS": ("merged/QS", "call-MBQ_anno_full/execution/QS", "call-MBQ_anno/execution/QS"),
    "mobileOGs": ("merged/mobileOGs", "call-MBQ_anno_full/execution/mobileOGs", "call-MBQ_anno/execution/mobileOGs"),
    "COG": ("merged/COG", "call-COG_anno_full/execution/COG", "call-COG_anno/execution/COG"),
    "MetaCyc": ("merged/MetaCyc", "call-MetaCyc_anno_full/execution/MetaCyc", "call-MetaCyc_anno/execution/MetaCyc"),
}


def state_path(workflow_dir, label):
    """Resolve a cumulative output, with legacy/full and cacheCopy fallbacks."""
    cumulative, *fallbacks = STATE_PATHS[label]
    candidates = []
    if cumulative:
        candidates.extend([
            workflow_dir / "call-merge_upstream_results" / "execution" / cumulative,
            workflow_dir / "call-merge_upstream_results" / "cacheCopy" / "execution" / cumulative,
        ])
    for fallback in fallbacks:
        candidates.append(workflow_dir / fallback)
        call_name, remainder = fallback.split("/execution/", 1)
        candidates.append(workflow_dir / call_name / "cacheCopy" / "execution" / remainder)
    return next((path for path in candidates if path.is_dir()), None)


def input_value(inputs, name, default=""):
    return inputs.get(INPUT_PREFIX + name, default)


def read_samples(data_xlsx):
    try:
        frame = pd.read_excel(data_xlsx, sheet_name="sample", dtype=str, engine="openpyxl").fillna("")
    except Exception as exc:
        raise RuntimeError(f"无法读取 {data_xlsx} 的 sample sheet: {exc}") from exc
    if frame.empty:
        raise RuntimeError("data.xlsx 的 sample sheet 不能为空")

    columns = {str(c).strip().lower(): c for c in frame.columns}
    id_col = next((columns[k] for k in ("fastqfile", "fastq_prefix", "internal_id") if k in columns), frame.columns[0])
    display_col = next((columns[k] for k in ("sample", "display_name", "sample_name") if k in columns), id_col)
    group_col = next((c for c in frame.columns if str(c).strip().lower().startswith("group")), None)

    samples = {}
    duplicate_ids = []
    for _, row in frame.iterrows():
        internal_id = str(row[id_col]).strip()
        if not internal_id:
            continue
        if internal_id in samples:
            duplicate_ids.append(internal_id)
        samples[internal_id] = {
            "display_name": str(row[display_col]).strip() or internal_id,
            "group": str(row[group_col]).strip() if group_col is not None else "",
        }
    if duplicate_ids:
        raise RuntimeError(f"data.xlsx 存在重复 internal_id: {sorted(set(duplicate_ids))}")
    if not samples:
        raise RuntimeError("data.xlsx 未读取到有效样本")
    return samples, id_col, display_col


def read_project_identity_from_json(project_info_path):
    """Read registry identity from tester-provided project_info.json."""
    try:
        identity = read_project_info(project_info_path)
    except Exception as exc:
        raise RuntimeError(f"无法读取 {project_info_path}: {exc}") from exc
    missing = [key for key in ("project_no", "project_name", "customer_name")
               if not str(identity.get(key, "")).strip()]
    if missing:
        raise RuntimeError(
            "project_info.json 缺少项目身份字段: " + ", ".join(missing)
        )
    return identity


def write_planner_project_info(path, identity):
    """Create a planner-only project_info.json for legacy registry scanners."""
    value = {
        "项目编号": identity["project_no"],
        "项目名称": identity["project_name"],
        "客户名称": identity["customer_name"],
    }
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def workflow_identity(workflow_dir):
    candidates = (
        "call-check_input_with_raw/execution/metadatadir/project_info.json",
        "call-check_input_with_raw/cacheCopy/execution/metadatadir/project_info.json",
        "call-check_input_no_raw/execution/metadatadir/project_info.json",
        "call-apply_registry/execution/new_metadatadir/project_info.json",
        "call-apply_registry/cacheCopy/execution/new_metadatadir/project_info.json",
    )
    for relative in candidates:
        path = workflow_dir / relative
        if path.exists():
            return read_project_info(path)
    return {"project_no": "", "project_name": "", "customer_name": ""}


def valid_parent(workflow_dir):
    return workflow_dir.is_dir() and all(state_path(workflow_dir, label) for label in STATE_PATHS)


def discover_registries(workflow_root, current_registry_dir, identity):
    paths = set(current_registry_dir.glob("*_sample_registry.tsv"))
    paths.update((workflow_root / "registry").glob("*_sample_registry.tsv"))
    expected_prefix = sanitize_filename_part(identity["project_no"]) + "_"
    return sorted(
        (p.resolve() for p in paths
         if p.is_file() and p.name.startswith(expected_prefix)
         and project_identity_matches(registry_project_identity(p), identity)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def workflows_from_registry(registry_path):
    try:
        frame = pd.read_csv(registry_path, sep="\t", dtype=str)
    except Exception:
        return set()
    result = set()
    pattern = re.compile(r"(.*/cromwell-executions/" + re.escape(WORKFLOW_NAME) + r"/[^/]+)(?:/|$)")
    for value in frame.get("file_path", pd.Series(dtype=str)).dropna().astype(str):
        match = pattern.search(value)
        if match:
            result.add(Path(match.group(1)).resolve())
    return result


def discover_workflows(workflow_root, registries, identity):
    candidates = set()
    for registry in registries:
        candidates.update(workflows_from_registry(registry))
    candidates.update(workflow_root.glob("*"))

    valid = []
    for workflow_dir in candidates:
        workflow_dir = Path(workflow_dir).resolve()
        if workflow_dir.name == "registry" or not valid_parent(workflow_dir):
            continue
        if not project_identity_matches(workflow_identity(workflow_dir), identity):
            continue
        valid.append(workflow_dir)
    return sorted(valid, key=lambda p: p.stat().st_mtime, reverse=True)


def registry_for_workflow(registries, workflow_dir):
    prefix = str(workflow_dir) + "/"
    for registry in registries:
        try:
            frame = pd.read_csv(registry, sep="\t", usecols=["file_path"], dtype=str)
        except Exception:
            continue
        if frame["file_path"].fillna("").str.startswith(prefix).any():
            return registry
    return None


def initialize_registry(target, source, parent_workflow, project_no, project_dir):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source and source.resolve() != target.resolve():
        shutil.copy2(source, target)
    elif not target.exists() and parent_workflow:
        cmd = [
            sys.executable,
            str(project_dir / "scripts/update_registry_from_wdl.py"),
            "--registry", str(target),
            "--execution-dir", str(parent_workflow),
            "--filter-project-no", project_no,
            "--out", str(target),
        ]
        subprocess.run(cmd, check=True)
    elif not target.exists():
        pd.DataFrame(columns=[
            "internal_id", "display_name", "group", "project_no", "project_name", "customer_name",
            "task", "file_path", "description", "status", "size_bytes", "mtime_ns",
        ]).to_csv(target, sep="\t", index=False)


def scan_current_raw(target, inputs, project_dir, project_info):
    raw_dir = Path(input_value(inputs, "rawdatapath"))
    data_dir = Path(input_value(inputs, "datapath"))
    if not raw_dir.is_dir():
        print(f"警告：rawdatapath 不存在，仅 reuse 模式可继续: {raw_dir}", file=sys.stderr)
        return False
    if not any(raw_dir.glob("*.fq.gz")) and not any(raw_dir.glob("*.fastq.gz")):
        print(f"警告：rawdatapath 中没有 FASTQ，仅 reuse 模式可继续: {raw_dir}", file=sys.stderr)
        return False
    cmd = [
        sys.executable,
        str(project_dir / "scripts/scan_registry.py"),
        "--project-dir", str(raw_dir),
        "--project-info", str(project_info),
        "--data-xlsx", str(data_dir / "data.xlsx"),
        "--out", str(target),
    ]
    if target.exists() and target.stat().st_size:
        cmd.extend(["--existing", str(target)])
    subprocess.run(cmd, check=True)
    return True


def sync_registry_samples(registry_path, current_samples, identity):
    """Make registry membership/metadata follow current data.xlsx, even without raw FASTQ."""
    try:
        frame = pd.read_csv(registry_path, sep="\t", dtype=str).fillna("")
    except Exception as exc:
        raise RuntimeError(f"无法同步 registry 样本信息: {exc}") from exc
    if "internal_id" not in frame.columns:
        raise RuntimeError("registry 缺少 internal_id 列")
    allowed = set(current_samples)
    frame = frame[frame["internal_id"].astype(str).str.strip().isin(allowed | {""})].copy()
    for sample, metadata in current_samples.items():
        mask = frame["internal_id"].astype(str).str.strip() == sample
        if mask.any():
            frame.loc[mask, "display_name"] = metadata["display_name"]
            frame.loc[mask, "group"] = metadata["group"]
    for key in ("project_no", "project_name", "customer_name"):
        if key not in frame.columns:
            frame[key] = ""
        frame.loc[:, key] = identity[key]
    frame.to_csv(registry_path, sep="\t", index=False)


def registry_sample_metadata(registry_path):
    if not registry_path or not registry_path.exists():
        return {}, {}
    try:
        frame = pd.read_csv(registry_path, sep="\t", dtype=str).fillna("")
    except Exception:
        return {}, {}
    display, groups = {}, {}
    for _, row in frame.iterrows():
        sample = str(row.get("internal_id", "")).strip()
        if not sample:
            continue
        if str(row.get("display_name", "")).strip():
            display[sample] = str(row["display_name"]).strip()
        if str(row.get("group", "")).strip():
            groups[sample] = str(row["group"]).strip()
    return display, groups


def parent_samples(workflow_dir):
    if not workflow_dir:
        return set()
    # Workflow metadata is authoritative because result directories from older
    # releases may still be named with the former display_name.  data.xlsx keeps
    # the stable fastqfile/internal_id needed for add/delete/rename planning.
    metadata_candidates = (
        "call-check_input_no_raw/execution/metadatadir/data.xlsx",
        "call-check_input_no_raw/cacheCopy/execution/metadatadir/data.xlsx",
        "call-apply_registry/execution/new_metadatadir/data.xlsx",
        "call-apply_registry/cacheCopy/execution/new_metadatadir/data.xlsx",
        "call-check_input_with_raw/execution/metadatadir/data.xlsx",
        "call-check_input_with_raw/cacheCopy/execution/metadatadir/data.xlsx",
    )
    for relative in metadata_candidates:
        data_xlsx = workflow_dir / relative
        if data_xlsx.exists():
            try:
                samples, _, _ = read_samples(data_xlsx)
                return set(samples)
            except RuntimeError:
                pass
    megahit = state_path(workflow_dir, "megahit")
    if megahit is None:
        return set()
    return {p.name for p in megahit.iterdir() if p.is_dir() and (p / "final.contigs.fa").exists()}


def raw_signatures(raw_dir):
    signatures = {}
    patterns = ("*.fq.gz", "*.fastq.gz")
    for pattern in patterns:
        for path in raw_dir.glob(pattern):
            match = re.match(r"^(.*?)_(?:R)?([12])\.(?:fq|fastq)\.gz$", path.name)
            if not match:
                continue
            stat = path.stat()
            signatures.setdefault(match.group(1), {})[match.group(2)] = (
                str(path.resolve()), str(stat.st_size), str(stat.st_mtime_ns)
            )
    return signatures


def old_raw_signatures(registry_path):
    if not registry_path or not registry_path.exists():
        return {}
    try:
        frame = pd.read_csv(registry_path, sep="\t", dtype=str).fillna("")
    except Exception:
        return {}
    if "task" not in frame.columns:
        return {}
    frame = frame[frame["task"] == "rawdata"]
    result = {}
    for _, row in frame.iterrows():
        sample = str(row.get("internal_id", "")).strip()
        match = re.search(r"_(?:R)?([12])\.(?:fq|fastq)\.gz$", str(row.get("file_path", "")))
        if sample and match:
            result.setdefault(sample, {})[match.group(1)] = (
                str(row.get("file_path", "")), str(row.get("size_bytes", "")), str(row.get("mtime_ns", ""))
            )
    return result


def changed_raw_samples(current, old, common_samples):
    changed = set()
    for sample in common_samples:
        current_pair = current.get(sample, {})
        old_pair = old.get(sample, {})
        if not old_pair:
            continue
        if set(current_pair) != set(old_pair):
            changed.add(sample)
            continue
        for mate in current_pair:
            old_path, old_size, old_mtime = old_pair[mate]
            new_path, new_size, new_mtime = current_pair[mate]
            # 旧 registry 可能由 pandas 写成浮点/科学计数法，这种值已丢失 ns 精度，不用来误判变更。
            has_old_stat = old_size.isdigit() and old_mtime.isdigit()
            if old_path != new_path or (has_old_stat and (old_size != new_size or old_mtime != new_mtime)):
                changed.add(sample)
                break
    return changed


def prepare_incremental_data(source_dir, output_dir, sample_ids, id_col, display_col):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(source_dir, output_dir)
    xlsx = output_dir / "data.xlsx"
    with pd.ExcelFile(xlsx, engine="openpyxl") as excel:
        sheets = {name: pd.read_excel(excel, sheet_name=name, dtype=str) for name in excel.sheet_names}
    if "sample" not in sheets or "comparison" not in sheets:
        raise RuntimeError("data.xlsx 必须包含 sample 和 comparison 工作表")
    sample_frame = sheets["sample"].fillna("")
    wanted = set(sample_ids)
    sample_frame = sample_frame[sample_frame[id_col].astype(str).str.strip().isin(wanted)].copy()
    if sample_frame.empty:
        raise RuntimeError("incremental data.xlsx 未筛选到任何新增样本")
    sample_frame[display_col] = sample_frame[id_col]
    sheets["sample"] = sample_frame
    # 增量上游只处理本次新增样本，完整 comparison 往往还引用历史样本所在
    # 的分组。保留这些比较会让 dealdata_update.py 误判为引用了不存在的
    # 分组。增量 comparison 仅保留表头，由 --allow-empty-comparison 根据
    # 新增样本的 group 生成临时上游分组；下游分析仍读取完整项目 data.xlsx。
    sheets["comparison"] = sheets["comparison"].iloc[0:0].copy()
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)


def choose_mode(requested, has_parent, changes, inputs):
    added = changes["added"]
    deleted = changes["deleted"]
    renamed = changes["renamed"]
    regrouped = changes["regrouped"]
    changed_fastq = changes["fastq_changed"]

    if requested == "full":
        return "full"
    if not has_parent:
        if requested in ("rename", "delete"):
            raise RuntimeError(f"{requested} 模式需要已完成的同项目上游结果")
        return "full"
    if requested == "add" and (deleted or renamed or regrouped):
        raise RuntimeError("检测到删除/改名/改分组，请使用 run_sample_multi_change.sh")
    if requested == "rename" and (added or deleted or changed_fastq):
        raise RuntimeError("改名模式检测到增加/删除/FASTQ 变更，请使用 run_sample_multi_change.sh")
    if requested == "delete" and (added or renamed or regrouped or changed_fastq):
        raise RuntimeError("删除模式检测到其他变更，请使用 run_sample_multi_change.sh")

    if str(input_value(inputs, "binning", "no")).lower() == "yes":
        print("警告：binning=yes 保留原分支行为，本次强制 full 模式", file=sys.stderr)
        return "full"
    if str(input_value(inputs, "use_kraken2", "no")).strip().lower() == "yes" or str(input_value(inputs, "ref_sample", "")).strip():
        print("警告：Kraken2/参考基因组模块不使用增量合并，本次强制 full 模式", file=sys.stderr)
        return "full"
    if changed_fastq:
        print("警告：检测到已有样本 FASTQ 路径/大小/时间戳变化，为保证联合基因集一致性强制 full", file=sys.stderr)
        return "full"
    return "incremental" if added else "reuse"


def main():
    parser = argparse.ArgumentParser(description="规划宏基因组 full/incremental/reuse 运行")
    parser.add_argument("--mode", choices=("full", "add", "rename", "delete", "auto"), required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--plan-dir", required=True)
    parser.add_argument("--output-inputs", required=True)
    parser.add_argument("--output-plan", required=True)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    plan_dir = Path(args.plan_dir).resolve()
    plan_dir.mkdir(parents=True, exist_ok=True)
    with open(args.inputs, encoding="utf-8") as handle:
        inputs = json.load(handle)

    data_dir = Path(input_value(inputs, "datapath")).resolve()
    data_xlsx = data_dir / "data.xlsx"
    identity = read_project_identity_from_json(data_dir / "project_info.json")
    current_samples, id_col, display_col = read_samples(data_xlsx)
    workflow_project_root = Path(
        input_value(inputs, "project_root", str(data_dir.parent))
    ).resolve()
    planner_project_info = plan_dir / "project_info.json"
    write_planner_project_info(planner_project_info, identity)

    workflow_root = CROMWELL_WORKFLOW_ROOT
    registry_dir = workflow_root / "registry"
    target_registry = resolve_registry_path(registry_dir, **identity)
    working_registry = plan_dir / target_registry.name
    registries = discover_registries(workflow_root, registry_dir, identity)
    workflows = discover_workflows(workflow_root, registries, identity)
    # Prefer the valid cumulative state covering the most samples.  mtime only
    # breaks ties; this prevents a small legacy add-batch from hiding a fuller
    # historical state for the same exact project identity.
    parent = max(
        workflows,
        key=lambda path: (len(parent_samples(path)), path.stat().st_mtime),
    ) if workflows else None
    source_registry = registry_for_workflow(registries, parent) if parent else (registries[0] if registries else None)

    old_display, old_groups = registry_sample_metadata(source_registry)
    old_raw = old_raw_signatures(source_registry)
    initialize_registry(working_registry, source_registry, parent, identity["project_no"], project_dir)
    scan_current_raw(
        working_registry,
        inputs,
        project_dir,
        planner_project_info,
    )
    sync_registry_samples(working_registry, current_samples, identity)

    completed = parent_samples(parent)
    current_ids = set(current_samples)
    common = current_ids & completed
    current_raw = raw_signatures(Path(input_value(inputs, "rawdatapath")))
    changes = {
        "added": sorted(current_ids - completed),
        "deleted": sorted(completed - current_ids),
        "renamed": sorted(s for s in common if old_display.get(s, s) != current_samples[s]["display_name"]),
        "regrouped": sorted(s for s in common if old_groups.get(s, "") != current_samples[s]["group"]),
        "fastq_changed": sorted(changed_raw_samples(current_raw, old_raw, common)),
        "unchanged": [],
    }
    changed_ids = set().union(*(set(changes[k]) for k in ("added", "renamed", "regrouped", "fastq_changed")))
    changes["unchanged"] = sorted(common - changed_ids)
    run_mode = choose_mode(args.mode, parent is not None, changes, inputs)
    if run_mode == "full":
        upstream_samples = sorted(current_ids)
    elif run_mode == "incremental":
        upstream_samples = list(changes["added"])
    else:
        upstream_samples = []

    if run_mode in ("full", "incremental"):
        missing_pairs = sorted(sample for sample in upstream_samples if set(current_raw.get(sample, {})) != {"1", "2"})
        if missing_pairs:
            raise RuntimeError(f"待跑上游样本缺少 R1/R2 FASTQ: {missing_pairs}")

    incremental_data = None
    if run_mode == "incremental":
        if not upstream_samples:
            raise RuntimeError("incremental 模式没有需要重跑上游的样本")
        # WDL 固定读取 project_root/incremental_data，不向平台暴露该路径。
        incremental_data = workflow_project_root / "incremental_data"
        prepare_incremental_data(data_dir, incremental_data, upstream_samples, id_col, display_col)

    md5 = hashlib.md5(working_registry.read_bytes()).hexdigest()
    parent_uuid = parent.name if parent and run_mode != "full" else ""
    prepared = dict(inputs)
    prepared[INPUT_PREFIX + "run_mode"] = run_mode
    prepared[INPUT_PREFIX + "isbwa"] = "yes" if run_mode == "full" else "no"
    prepared[INPUT_PREFIX + "parent_workflow_dir"] = parent_uuid
    prepared[INPUT_PREFIX + "project_root"] = str(workflow_project_root)
    # registry 只在 Cromwell 成功后由 run_workflow.sh 提交，不在 WDL 内直接改写。
    for optional_key in (
        "project",
        "report_no",
        "registry_tsv_path",
        "executions_root",
        "skip_workflows",
        "incremental_datapath",
        "sample_registry_tsv",
        "registry_md5",
    ):
        prepared.pop(INPUT_PREFIX + optional_key, None)

    plan = {
        "requested_mode": args.mode,
        "run_mode": run_mode,
        "project": identity,
        "registry": str(target_registry),
        "working_registry": str(working_registry),
        "source_registry": str(source_registry) if source_registry else "",
        "parent_workflow_uuid": parent_uuid,
        "parent_workflow_dir": str(parent) if parent_uuid else "",
        "upstream_samples": upstream_samples,
        "changes": changes,
    }
    with open(args.output_inputs, "w", encoding="utf-8") as handle:
        json.dump(prepared, handle, ensure_ascii=False, indent=2)
    with open(args.output_plan, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"规划失败: {exc}", file=sys.stderr)
        sys.exit(2)
