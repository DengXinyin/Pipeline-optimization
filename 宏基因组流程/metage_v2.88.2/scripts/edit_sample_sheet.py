#!/usr/bin/env python3
"""Small, atomic data.xlsx sample-sheet edits used by shell entrypoints."""

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="修改 data.xlsx 的 sample sheet")
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--delete", nargs="+", required=True, dest="delete_samples")
    args = parser.parse_args()

    with open(args.inputs, encoding="utf-8") as handle:
        inputs = json.load(handle)
    data_dir = Path(inputs["metage_v2_88_2.datapath"])
    workbook = data_dir / "data.xlsx"
    if not workbook.exists():
        raise RuntimeError(f"data.xlsx 不存在: {workbook}")

    # Some project files are valid OOXML workbooks but have metadata that
    # makes pandas 1.x incorrectly select xlrd. Force the xlsx engine.
    with pd.ExcelFile(workbook, engine="openpyxl") as excel:
        sheets = {name: pd.read_excel(excel, sheet_name=name, dtype=str) for name in excel.sheet_names}
    if "sample" not in sheets:
        raise RuntimeError("data.xlsx 缺少 sample sheet")
    frame = sheets["sample"].fillna("")
    columns = {str(column).strip().lower(): column for column in frame.columns}
    id_col = next((columns[key] for key in ("fastqfile", "fastq_prefix", "internal_id") if key in columns), frame.columns[0])
    existing = set(frame[id_col].astype(str).str.strip())
    requested = {sample.strip() for sample in args.delete_samples if sample.strip()}
    missing = sorted(requested - existing)
    if missing:
        raise RuntimeError(f"以下样本不在 data.xlsx: {missing}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = workbook.with_name(f"data.xlsx.before_delete_{timestamp}.bak")
    shutil.copy2(workbook, backup)
    sheets["sample"] = frame[~frame[id_col].astype(str).str.strip().isin(requested)].copy()
    temporary = workbook.with_name(f".{workbook.name}.{os.getpid()}.tmp")
    with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
        for name, sheet in sheets.items():
            sheet.to_excel(writer, sheet_name=name, index=False)
    os.replace(temporary, workbook)
    print(f"已删除样本: {sorted(requested)}")
    print(f"样本数: {len(frame)} -> {len(sheets['sample'])}")
    print(f"可回滚备份: {backup}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"修改 data.xlsx 失败: {exc}", file=sys.stderr)
        sys.exit(2)
