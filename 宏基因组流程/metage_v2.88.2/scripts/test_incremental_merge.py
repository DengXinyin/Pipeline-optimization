#!/usr/bin/env python3
"""Synthetic regression test for two consecutive increments and add+delete."""

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

import incremental_planner as planner
import update_registry_from_wdl as registry_update


SCRIPT = Path(__file__).with_name("merge_upstream_results.py")
DEALDATA = Path(__file__).with_name("dealdata_update.py")
LABELS = (
    "clean", "qc_result", "megahit", "prodigal", "bowtie",
    "tax_annotation", "func_annotation", "VFDB", "ARGs", "CycDB",
    "mobileOGs", "BacMet2", "QS", "COG", "MetaCyc",
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def metadata(root, samples):
    root.mkdir(parents=True, exist_ok=True)
    write(root / "sample.txt", "fastqfile\tsample\n" + "".join("%s\t%s\n" % (s, s) for s in samples))
    write(
        root / "sample-metadata.tsv",
        "sample-id\tgroup1\n#q2:types\tcategorical\n" +
        "".join("%s\t%s\n" % (s, "G1" if index % 2 == 0 else "G2") for index, s in enumerate(samples)),
    )


def batch(root, samples):
    for label in LABELS:
        (root / label).mkdir(parents=True, exist_ok=True)
    genes = ["g" + sample for sample in samples]
    summary_columns = ["Sample_name", "Raw_reads", "Raw_bases(G)", "Removed_low_quality_Reads",
                       "Removed_Low_Qualitybases(G)", "Q20(%)", "Q30(%)", "GC_content(%)"]
    (root / "clean/table").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [[sample, 100, 1, 90, 0.9, 0.9, 0.8, 0.5] for sample in samples],
        columns=summary_columns,
    ).to_csv(root / "clean/table/sumary.txt", sep="\t", index=False)
    write(root / "qc_result/marker.txt", "qc\n")
    for sample in samples:
        write(root / ("megahit/%s/final.contigs.fa" % sample), ">seq_%s.1\nACGT\n" % sample)
    write(root / "megahit/sample.name.txt", "".join(str(root / "megahit" / s) + "\n" for s in samples))

    fasta = "".join(">%s\n%s\n" % (gene, "ACGT" * (index + 1)) for index, gene in enumerate(genes))
    for name in ("unique_gene.fasta", "clusterRes_rep_seq.fasta", "clusterRes_all_seqs.fasta"):
        write(root / "prodigal" / name, fasta)
    for sample in samples:
        write(root / ("prodigal/%s.fastq" % sample), ">g%s\nACGT\n" % sample)

    rows = []
    for gene_index, gene in enumerate(genes):
        rows.append([gene] + [10 if index == gene_index else 0 for index in range(len(samples))])
    for name in ("gene_tpm.csv", "gene_count.csv"):
        write_csv(root / "bowtie" / name, ["GeneID"] + list(samples), rows)
    write(root / "tax_annotation/Tax_id.tmp.txt", "".join("%s\ttax_%s\n" % (g, g) for g in genes))
    for name in ("func.emapper.annotations", "func.emapper.hits", "func.emapper.seed_orthologs"):
        write(root / "func_annotation" / name, "#query\tvalue\n" + "".join("%s\tfunc_%s\n" % (g, g) for g in genes))

    simple_tables = {
        "VFDB": ("gene.vf.tpm.csv", ["GeneID", "taxonomy", "VF_Name", "VFcategory"]),
        "ARGs": ("ARG.tpm.csv", ["GeneID", "taxonomy", "Type", "ARG"]),
        "mobileOGs": ("mobileOG.tpm.csv", ["taxonomy", "mobileOG Entry Name", "GeneID"]),
        "BacMet2": ("BacMet2.tpm.csv", ["taxonomy", "Gene_name", "GeneID"]),
        "QS": ("QS.tpm.csv", ["taxonomy", "Entry", "GeneID"]),
        "COG": ("COG.tpm.csv", ["GeneID", "taxonomy", "COG"]),
        "MetaCyc": ("MetaCyc.tpm.csv", ["GeneID", "taxonomy", "MetaCyc"]),
    }
    for label, (filename, annotation_columns) in simple_tables.items():
        table_rows = []
        for gene_index, gene in enumerate(genes):
            annotations = [gene if column == "GeneID" else "%s_%s" % (column, gene) for column in annotation_columns]
            table_rows.append(annotations + [10 if index == gene_index else 0 for index in range(len(samples))])
        write_csv(root / label / filename, annotation_columns + list(samples), table_rows)
        raw = {
            "VFDB": "vf_anno.txt", "ARGs": "ARGs_anno.txt", "mobileOGs": "mobileOG_anno.txt",
            "BacMet2": "BacMet_anno.txt", "QS": "QS_anno.txt", "COG": "COG_anno.txt",
            "MetaCyc": "MetaCyc_anno.txt",
        }[label]
        write(root / label / raw, "qseqid\tsseqid\n" + "".join("%s\thit\n" % gene for gene in genes))

    cycle_rows = []
    for gene_index, gene in enumerate(genes):
        cycle_rows.append([gene, "tax", "K1", "path", "detail"] +
                          [10 if index == gene_index else 0 for index in range(len(samples))])
    pd.DataFrame(cycle_rows, columns=["GeneID", "taxonomy", "KO", "Pathway", "Detail"] + list(samples)).to_excel(
        root / "CycDB/Carbon_Cycle.xlsx", index=False
    )
    return root


def run_merge(old, new, data, output):
    command = [sys.executable, str(SCRIPT)]
    for label in LABELS:
        command.extend(["--pair", label, str(old / label), str(new / label)])
    command.extend(["--datapath", str(data), "--out", str(output)])
    subprocess.run(command, check=True)


def assert_internal_id_contract(root):
    source = root / "dealdata_source"
    source.mkdir(parents=True)
    with pd.ExcelWriter(source / "data.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([
            {"fastqfile": "S01", "sample": "客户展示名", "group": "case"},
            {"fastqfile": "S02", "sample": "另一个展示名", "group": "control"},
        ]).to_excel(writer, sheet_name="sample", index=False)
        pd.DataFrame([{"comparison": "case_vs_control", "left": "case", "right": "control"}]).to_excel(
            writer, sheet_name="comparison", index=False
        )
    write(source / "project_info.json", '{"客户名称":"客户","客户单位":"单位","项目编号":"P1","项目名称":"测试"}\n')
    write(source / "report_no.txt", "R1\n")
    output = root / "dealdata_output"
    subprocess.run([sys.executable, str(DEALDATA), "-indir", str(source), "-outdir", str(output)], check=True)
    sample = pd.read_csv(output / "sample.txt", sep="\t", dtype=str)
    assert list(sample["sample"]) == ["S01", "S02"]
    meta = pd.read_csv(output / "sample-metadata.tsv", sep="\t", dtype=str)
    assert list(meta["sample-id"].iloc[1:]) == ["S01", "S02"]
    display_map = pd.read_csv(output / "display_name_map.tsv", sep="\t", dtype=str)
    assert list(display_map["display_name"]) == ["客户展示名", "另一个展示名"]
    normalized = pd.read_excel(output / "data.xlsx", sheet_name="sample", dtype=str, engine="openpyxl")
    assert list(normalized["sample"]) == ["客户展示名", "另一个展示名"]


def assert_parent_state_resolution(root):
    workflow = root / "workflow_parent"
    for label, (cumulative, *fallbacks) in planner.STATE_PATHS.items():
        if cumulative:
            path = workflow / "call-merge_upstream_results/execution" / cumulative
        else:
            path = workflow / fallbacks[0]
        path.mkdir(parents=True, exist_ok=True)
    data_dir = workflow / "call-check_input_no_raw/execution/metadatadir"
    data_dir.mkdir(parents=True)
    with pd.ExcelWriter(data_dir / "data.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([
            {"fastqfile": "S01", "sample": "旧展示名", "group": "G1"},
            {"fastqfile": "S02", "sample": "另一个旧展示名", "group": "G2"},
        ]).to_excel(writer, sheet_name="sample", index=False)
    # Result directory names are intentionally unrelated; planner must read the
    # stable IDs from historical data.xlsx and must prefer merged/megahit.
    write(workflow / "call-merge_upstream_results/execution/merged/megahit/旧展示名/final.contigs.fa", ">x\nA\n")
    assert planner.valid_parent(workflow)
    assert planner.parent_samples(workflow) == {"S01", "S02"}
    assert "call-merge_upstream_results" in str(planner.state_path(workflow, "megahit"))


def assert_registry_metadata_refresh():
    previous = pd.DataFrame([{
        "internal_id": "S01", "display_name": "旧名称", "group": "old",
        "project_no": "P1", "project_name": "项目", "customer_name": "客户",
        "task": "megahit", "file_path": "/old/result", "description": "result", "status": "done",
    }])
    updated = registry_update.update_registry(
        previous,
        {"project_no": "P1", "project_name": "项目", "customer_name": "客户"},
        [], "P1", metadata_group_map={"S01": "new"},
        metadata_display_map={"S01": "新名称"},
    )
    assert updated.loc[0, "group"] == "new"
    assert updated.loc[0, "display_name"] == "新名称"


def assert_state(root, samples):
    matrix = pd.read_csv(root / "bowtie/gene_tpm.csv", encoding="utf-8-sig")
    assert list(matrix.columns) == ["GeneID"] + list(samples), matrix.columns
    assert set(matrix["GeneID"]) == {"g" + sample for sample in samples}
    extension = pd.read_csv(root / "VFDB/gene.vf.tpm.csv", encoding="utf-8-sig")
    assert list(extension.columns[-len(samples):]) == list(samples)
    assert set(extension["GeneID"]) == set(matrix["GeneID"])
    summary = pd.read_csv(root / "clean/table/sumary.txt", sep="\t")
    assert list(summary["Sample_name"]) == list(samples)
    fasta = (root / "prodigal/unique_gene.fasta").read_text(encoding="utf-8")
    assert all(">g%s\n" % sample in fasta for sample in samples)
    assert (root / "qc_result/group1/1-data_quality/data_quality.xlsx").exists()


def main():
    with tempfile.TemporaryDirectory(prefix="metage_incremental_test_") as temporary:
        root = Path(temporary)
        assert_internal_id_contract(root)
        assert_parent_state_resolution(root)
        assert_registry_metadata_refresh()
        first_data = root / "data_abc"
        metadata(first_data, ["A", "B", "C"])
        first = root / "merged_abc"
        run_merge(batch(root / "full_ab", ["A", "B"]), batch(root / "new_c", ["C"]), first_data, first)
        assert_state(first, ["A", "B", "C"])

        second_data = root / "data_abcd"
        metadata(second_data, ["A", "B", "C", "D"])
        second = root / "merged_abcd"
        run_merge(first, batch(root / "new_d", ["D"]), second_data, second)
        assert_state(second, ["A", "B", "C", "D"])

        final_data = root / "data_acde"
        metadata(final_data, ["A", "C", "D", "E"])
        final = root / "merged_acde"
        run_merge(second, batch(root / "new_e", ["E"]), final_data, final)
        assert_state(final, ["A", "C", "D", "E"])
        assert ">gB\n" not in (final / "prodigal/unique_gene.fasta").read_text(encoding="utf-8")
    print("PASS: stable IDs/parent resolution; full A+B -> +C -> +D -> delete B + add E")


if __name__ == "__main__":
    main()
