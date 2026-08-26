#!/usr/bin/env python3
"""Commit a run-plan registry after a successful Cromwell workflow."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="成功运行后提交并清理 registry")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--workflow-dir", required=True)
    parser.add_argument("--project-dir", required=True)
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    with open(args.plan, encoding="utf-8") as handle:
        plan = json.load(handle)
    with open(args.inputs, encoding="utf-8") as handle:
        inputs = json.load(handle)

    target = Path(plan["registry"])
    working = Path(plan["working_registry"])
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(working, target)

    subprocess.run([
        sys.executable, str(project_dir / "scripts/update_registry_from_wdl.py"),
        "--registry", str(target),
        "--execution-dir", args.workflow_dir,
        "--filter-project-no", plan["project"]["project_no"],
        "--drop-missing", "--out", str(target),
    ], check=True)

    prefix = "metage_v2_88_2."
    project_info = Path(inputs[prefix + "datapath"]) / "project_info.json"
    subprocess.run([
        sys.executable, str(project_dir / "scripts/scan_registry.py"),
        "--project-dir", inputs[prefix + "rawdatapath"],
        "--project-info", str(project_info),
        "--data-xlsx", str(Path(inputs[prefix + "datapath"]) / "data.xlsx"),
        "--existing", str(target), "--out", str(target),
    ], check=True)
    print(f"registry 已提交: {target}")


if __name__ == "__main__":
    main()
