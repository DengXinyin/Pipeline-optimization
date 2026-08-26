#!/usr/bin/env python3
"""Regenerate QC figures after the final sample registry has been applied.

The initial QC task may run before an incremental workflow has applied the
latest group assignments.  This helper renders the three per-sample QC plots
against the final metadata into the assembled Result directory.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

import pandas as pd


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
LOG = logging.getLogger(__name__)


def grouped_samples(metadata: Path) -> list[str]:
    frame = pd.read_csv(metadata / "sample-metadata.tsv", sep="\t", dtype=str)
    if "sample-id" not in frame.columns or len(frame.columns) < 2:
        return []
    groups = frame.iloc[:, 1:].fillna("").astype(str)
    return frame.loc[groups.ne("").any(axis=1), "sample-id"].dropna().tolist()


def run(command: list[str]) -> None:
    LOG.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)


def expected_figures(result_dir: Path, samples: list[str]) -> list[Path]:
    expected: list[Path] = []
    for group_dir in result_dir.glob("group*/1-data_quality"):
        for sample in samples:
            sample_dir = group_dir / sample
            if sample_dir.exists():
                expected.extend(
                    sample_dir / name
                    for name in ("error_rate.pdf", "ATGC_content.pdf", "reads_quality_summary.pdf")
                )
    return expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--host", required=True)
    parser.add_argument("--script-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()

    required = (args.table_dir, args.data_dir / "sample-metadata.tsv", args.result_dir)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("QC replot input missing: " + ", ".join(missing))

    samples = grouped_samples(args.data_dir)
    if not samples:
        raise ValueError("No samples with a non-empty group assignment in sample-metadata.tsv")

    rscript = "/root/anaconda3/envs/r/bin/Rscript"
    for script in ("error_rate_update.R", "atgc_content_update.R"):
        run([rscript, str(args.script_dir / script), str(args.table_dir), str(args.data_dir), str(args.result_dir)])
    run([
        rscript,
        str(args.script_dir / "data_composition_bar_update.R"),
        str(args.table_dir),
        str(args.data_dir),
        str(args.result_dir),
        args.host,
    ])

    missing_figures = [str(path) for path in expected_figures(args.result_dir, samples) if not path.exists()]
    if missing_figures:
        raise RuntimeError("QC figures were not generated: " + ", ".join(missing_figures[:12]))
    LOG.info("QC figures regenerated for %d grouped samples", len(samples))


if __name__ == "__main__":
    main()
