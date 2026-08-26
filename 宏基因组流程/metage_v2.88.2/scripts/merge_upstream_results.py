#!/usr/bin/env python3
"""Build one cumulative state from a parent run and one incremental batch.

The merger is deliberately database-agnostic at the workflow boundary, but it
knows the stable files produced by this pipeline.  Gene matrices and annotation
tables are merged by GeneID, sample columns are restricted to the current
data.xlsx/sample.txt, and derived QC/gene-catalog summaries are rebuilt.
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd


GENE_TABLES = {
    "VFDB": ("gene.vf.tpm.csv", "GeneID"),
    "ARGs": ("ARG.tpm.csv", "GeneID"),
    "mobileOGs": ("mobileOG.tpm.csv", "GeneID"),
    "BacMet2": ("BacMet2.tpm.csv", "GeneID"),
    "QS": ("QS.tpm.csv", "GeneID"),
    "COG": ("COG.tpm.csv", "GeneID"),
    "MetaCyc": ("MetaCyc.tpm.csv", "GeneID"),
}

RAW_ANNOTATIONS = {
    "VFDB": "vf_anno.txt",
    "ARGs": "ARGs_anno.txt",
    "mobileOGs": "mobileOG_anno.txt",
    "BacMet2": "BacMet_anno.txt",
    "QS": "QS_anno.txt",
    "COG": "COG_anno.txt",
    "MetaCyc": "MetaCyc_anno.txt",
}

CYCLES = ("Carbon", "Methane", "Nitrogen", "phosphorylation", "Sulfur")


def link_or_copy(source, target):
    """Copy an input artifact without sharing an inode with Cromwell inputs.

    Several merged files are rewritten in place after the overlay.  Hard links
    would therefore truncate the localized parent/new input as well.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(source, target)


def overlay_tree(source, target):
    source = Path(source)
    if not source.is_dir():
        raise FileNotFoundError("待合并目录不存在: %s" % source)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file() and not path.is_symlink():
            link_or_copy(path, destination)


def read_active_samples(datapath):
    sample_txt = Path(datapath) / "sample.txt"
    frame = pd.read_csv(sample_txt, sep="\t", dtype=str).fillna("")
    if frame.shape[1] < 2:
        raise ValueError("sample.txt 至少需要两列: %s" % sample_txt)
    samples = [str(value).strip() for value in frame.iloc[:, 1] if str(value).strip()]
    if not samples or len(samples) != len(set(samples)):
        raise ValueError("sample.txt 的 active sample 为空或重复")
    return samples


def csv_header(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def numeric_nonzero(value):
    try:
        return float(value or 0) != 0
    except (TypeError, ValueError):
        return False


def normalized_row(row, annotation_columns, active_samples):
    return [row.get(column, "") for column in annotation_columns] + [
        row.get(sample, "0") or "0" for sample in active_samples
    ]


def merge_gene_csv(old_path, new_path, output_path, key, active_samples,
                   historical_samples, drop_all_zero=False, allowed_gene_db=None):
    """Stream old rows and keep new rows in an on-disk index.

    New rows replace duplicate GeneIDs.  This avoids a pandas outer join of the
    complete abundance matrix, which can exceed task memory for large catalogs.
    """
    old_header = csv_header(old_path)
    new_header = csv_header(new_path)
    if key not in old_header or key not in new_header:
        raise ValueError("基因表缺少 %s: %s / %s" % (key, old_path, new_path))
    sample_set = set(historical_samples) | set(active_samples)
    annotation_columns = []
    for column in old_header + new_header:
        if column not in sample_set and column not in annotation_columns:
            annotation_columns.append(column)
    if key not in annotation_columns:
        annotation_columns.insert(0, key)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, database_name = tempfile.mkstemp(prefix="merge_gene_", suffix=".sqlite", dir=str(output_path.parent))
    os.close(fd)
    database = sqlite3.connect(database_name)
    try:
        database.execute(
            "CREATE TABLE new_rows (gene_id TEXT PRIMARY KEY, seq INTEGER, payload TEXT NOT NULL)"
        )
        with open(new_path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            batch = []
            for seq, row in enumerate(reader):
                gene_id = str(row.get(key, "")).strip()
                if not gene_id:
                    continue
                if allowed_gene_db is not None and not gene_exists(allowed_gene_db, gene_id):
                    continue
                values = normalized_row(row, annotation_columns, active_samples)
                if drop_all_zero and not any(numeric_nonzero(v) for v in values[-len(active_samples):]):
                    continue
                batch.append((gene_id, seq, json.dumps(values, ensure_ascii=False)))
                if len(batch) >= 10000:
                    database.executemany("INSERT OR REPLACE INTO new_rows VALUES (?, ?, ?)", batch)
                    database.commit()
                    batch = []
            if batch:
                database.executemany("INSERT OR REPLACE INTO new_rows VALUES (?, ?, ?)", batch)
                database.commit()

        with open(output_path, "w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(annotation_columns + active_samples)
            with open(old_path, "r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    gene_id = str(row.get(key, "")).strip()
                    if not gene_id:
                        continue
                    if database.execute("SELECT 1 FROM new_rows WHERE gene_id=?", (gene_id,)).fetchone():
                        continue
                    if allowed_gene_db is not None and not gene_exists(allowed_gene_db, gene_id):
                        continue
                    values = normalized_row(row, annotation_columns, active_samples)
                    if drop_all_zero and not any(numeric_nonzero(v) for v in values[-len(active_samples):]):
                        continue
                    writer.writerow(values)
            for payload, in database.execute("SELECT payload FROM new_rows ORDER BY seq"):
                writer.writerow(json.loads(payload))
    finally:
        database.close()
        os.unlink(database_name)


def create_gene_index(gene_tpm, output_dir):
    database_path = output_dir / ".active_genes.sqlite"
    database = sqlite3.connect(str(database_path))
    database.execute("CREATE TABLE genes (gene_id TEXT PRIMARY KEY)")
    with open(gene_tpm, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        key = reader.fieldnames[0]
        batch = []
        for row in reader:
            gene_id = str(row.get(key, "")).strip()
            if gene_id:
                batch.append((gene_id,))
            if len(batch) >= 20000:
                database.executemany("INSERT OR IGNORE INTO genes VALUES (?)", batch)
                database.commit()
                batch = []
        if batch:
            database.executemany("INSERT OR IGNORE INTO genes VALUES (?)", batch)
            database.commit()
    return database, database_path


def gene_exists(database, gene_id):
    return database.execute("SELECT 1 FROM genes WHERE gene_id=?", (gene_id,)).fetchone() is not None


def fasta_id(line):
    return line[1:].split(None, 1)[0]


def fasta_ids(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(">"):
                yield fasta_id(line)


def write_selected_fasta(source, output, allowed_gene_db, skip_database=None):
    keep = False
    with open(source, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(">"):
                gene_id = fasta_id(line)
                keep = gene_exists(allowed_gene_db, gene_id) and (
                    skip_database is None or
                    skip_database.execute("SELECT 1 FROM ids WHERE gene_id=?", (gene_id,)).fetchone() is None
                )
            if keep:
                output.write(line)


def merge_fasta(old_path, new_path, output_path, allowed_gene_db):
    fd, database_name = tempfile.mkstemp(prefix="merge_fasta_", suffix=".sqlite", dir=str(output_path.parent))
    os.close(fd)
    database = sqlite3.connect(database_name)
    try:
        database.execute("CREATE TABLE ids (gene_id TEXT PRIMARY KEY)")
        batch = []
        for gene_id in fasta_ids(new_path):
            if gene_exists(allowed_gene_db, gene_id):
                batch.append((gene_id,))
            if len(batch) >= 20000:
                database.executemany("INSERT OR IGNORE INTO ids VALUES (?)", batch)
                database.commit()
                batch = []
        if batch:
            database.executemany("INSERT OR IGNORE INTO ids VALUES (?)", batch)
            database.commit()
        with open(output_path, "w", encoding="utf-8") as output:
            write_selected_fasta(old_path, output, allowed_gene_db, database)
            write_selected_fasta(new_path, output, allowed_gene_db)
    finally:
        database.close()
        os.unlink(database_name)


def fasta_lengths(path):
    name = None
    length = 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(">"):
                if name is not None:
                    yield name, length
                name = fasta_id(line)
                length = 0
            else:
                length += len(line.strip())
    if name is not None:
        yield name, length


def nxx(lengths, fraction):
    threshold = sum(lengths) * fraction
    running = 0
    for index, length in enumerate(sorted(lengths, reverse=True), 1):
        running += length
        if running >= threshold:
            return length, index
    return 0, 0


def rebuild_gene_statistics(prodigal_dir):
    fasta = prodigal_dir / "unique_gene.fasta"
    records = list(fasta_lengths(fasta))
    if not records:
        raise ValueError("累计 unique_gene.fasta 为空")
    with open(prodigal_dir / "unique_length.txt", "w", encoding="utf-8") as handle:
        handle.write("#name\tlength\n")
        for name, length in records:
            handle.write("%s\t%d\n" % (name, length))
    lengths = [length for _, length in records]
    n50, n50n = nxx(lengths, 0.5)
    n70, n70n = nxx(lengths, 0.7)
    n90, n90n = nxx(lengths, 0.9)
    # Keep the legacy assembly-stats column contract: prodigal_stats_update.py
    # reads columns 0..5 and column 8 as N50.
    columns = ["filename", "total_length", "number", "mean_length", "longest", "shortest",
               "N_count", "Gaps", "N50", "N50n", "N70", "N70n", "N90", "N90n"]
    values = [str(fasta), sum(lengths), len(lengths), sum(lengths) / len(lengths),
              max(lengths), min(lengths), 0, 0, n50, n50n, n70, n70n, n90, n90n]
    pd.DataFrame([values], columns=columns).to_csv(
        prodigal_dir / "unique_stats.txt", sep="\t", index=False
    )


def rebuild_all_predicted_genes(prodigal_dir, active_samples):
    """Recreate all.fa from active per-sample Prodigal nucleotide FASTA files."""
    with open(prodigal_dir / "all.fa", "w", encoding="utf-8") as output:
        for sample in active_samples:
            source = prodigal_dir / (sample + ".fastq")
            if not source.exists():
                raise FileNotFoundError("累计 Prodigal 缺少样本文件: %s" % source)
            with open(source, encoding="utf-8", errors="replace") as handle:
                shutil.copyfileobj(handle, output, length=1024 * 1024)


def merge_tabular_records(old_path, new_path, output_path, allowed_gene_db=None,
                          replace_by_first=True):
    """Merge tabular records by the first field without loading old history."""
    fd, database_name = tempfile.mkstemp(prefix="merge_tab_", suffix=".sqlite", dir=str(output_path.parent))
    os.close(fd)
    database = sqlite3.connect(database_name)
    try:
        database.execute("CREATE TABLE new_records (record_id TEXT PRIMARY KEY, seq INTEGER, line TEXT)")
        comments = []
        with open(new_path, encoding="utf-8", errors="replace") as handle:
            batch = []
            for seq, line in enumerate(handle):
                if not line.strip():
                    continue
                if line.startswith("#") or line.split("\t", 1)[0] in ("qseqid", "query"):
                    comments.append(line)
                    continue
                gene_id = line.split("\t", 1)[0]
                if allowed_gene_db is not None and not gene_exists(allowed_gene_db, gene_id):
                    continue
                record_id = gene_id if replace_by_first else hashlib.sha256(line.rstrip("\n").encode("utf-8")).hexdigest()
                batch.append((record_id, seq, line))
                if len(batch) >= 10000:
                    database.executemany("INSERT OR REPLACE INTO new_records VALUES (?, ?, ?)", batch)
                    database.commit()
                    batch = []
            if batch:
                database.executemany("INSERT OR REPLACE INTO new_records VALUES (?, ?, ?)", batch)
                database.commit()
        with open(output_path, "w", encoding="utf-8") as output:
            if comments:
                output.write(comments[0])
            with open(old_path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    if line.startswith("#") or line.split("\t", 1)[0] in ("qseqid", "query"):
                        if not comments and output.tell() == 0:
                            output.write(line)
                        continue
                    gene_id = line.split("\t", 1)[0]
                    if allowed_gene_db is not None and not gene_exists(allowed_gene_db, gene_id):
                        continue
                    record_id = gene_id if replace_by_first else hashlib.sha256(line.rstrip("\n").encode("utf-8")).hexdigest()
                    if not database.execute("SELECT 1 FROM new_records WHERE record_id=?", (record_id,)).fetchone():
                        output.write(line)
            for line, in database.execute("SELECT line FROM new_records ORDER BY seq"):
                output.write(line)
    finally:
        database.close()
        os.unlink(database_name)


def merge_sample_summary(old_path, new_path, output_path, active_samples):
    old = pd.read_csv(old_path, sep="\t", encoding="utf-8-sig", dtype={"Sample_name": str})
    new = pd.read_csv(new_path, sep="\t", encoding="utf-8-sig", dtype={"Sample_name": str})
    key = "Sample_name"
    if key not in old.columns or key not in new.columns or list(old.columns) != list(new.columns):
        raise ValueError("质控汇总表结构不一致: %s / %s" % (old_path, new_path))
    new = new.drop_duplicates(key, keep="last")
    old = old.drop_duplicates(key, keep="last")
    merged = pd.concat([old.loc[~old[key].isin(new[key])], new], ignore_index=True)
    order = {sample: index for index, sample in enumerate(active_samples)}
    merged = merged.loc[merged[key].isin(active_samples)].copy()
    merged["__order"] = merged[key].map(order)
    merged = merged.sort_values("__order").drop(columns="__order")
    merged.to_csv(output_path, sep="\t", index=False, encoding="utf-8")


def rebuild_qc_excel(qc_dir, clean_dir, datapath):
    summary = pd.read_csv(clean_dir / "table" / "sumary.txt", sep="\t", dtype={"Sample_name": str})
    metadata = pd.read_csv(Path(datapath) / "sample-metadata.tsv", sep="\t", dtype=str).fillna("")
    metadata = metadata.loc[~metadata.iloc[:, 0].astype(str).str.startswith("#")]
    for path in qc_dir.glob("group*/1-data_quality/data_quality.xlsx"):
        path.unlink()
    for index, group_column in enumerate(metadata.columns[1:], 1):
        selected = metadata.loc[metadata[group_column].astype(str).str.strip() != "", [metadata.columns[0], group_column]]
        result = selected.merge(summary, left_on=metadata.columns[0], right_on="Sample_name", how="inner")
        result = result.drop(columns=[metadata.columns[0], group_column])
        destination = qc_dir / ("group%d" % index) / "1-data_quality" / "data_quality.xlsx"
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.to_excel(destination, index=False)


def prune_sample_artifacts(output_root, active_samples, historical_samples):
    inactive = sorted(set(historical_samples) - set(active_samples), key=len, reverse=True)
    if not inactive:
        return

    def belongs_to_sample(label, path, sample):
        if label == "clean":
            return (path.name.startswith(sample + "_") or
                    path.name.startswith(sample + ".") or path.name == sample)
        if label == "megahit":
            return path.name == sample or (
                path.parent.name == "length" and path.name.startswith(sample + "_")
            )
        if label == "prodigal":
            if path.name in (sample + ".gff3", sample + ".fastq", sample + ".faa"):
                return True
            return ".chunks_v2" in path.parts and sample in path.parts
        if label == "bowtie":
            if path.name in ("gene_count.csv", "gene_tpm.csv"):
                return False
            return path.name.startswith(sample + ".") or path.name.startswith(sample + "_")
        return False

    for label in ("clean", "megahit", "prodigal", "bowtie"):
        root = output_root / label
        for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            matched = any(belongs_to_sample(label, path, sample) for sample in inactive)
            if not matched:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()


def merge_cycdb(old_dir, new_dir, output_dir, active_samples, historical_samples, active_gene_db):
    sample_set = set(historical_samples) | set(active_samples)
    for cycle in CYCLES:
        filename = cycle + "_Cycle.xlsx"
        old_path, new_path = old_dir / filename, new_dir / filename
        if not old_path.exists() and not new_path.exists():
            continue
        frames = [
            pd.read_excel(path, dtype=str, engine="openpyxl")
            for path in (old_path, new_path) if path.exists()
        ]
        annotations = []
        for frame in frames:
            for column in frame.columns:
                if column not in sample_set and column not in annotations:
                    annotations.append(column)
        merged = pd.concat(frames, ignore_index=True, sort=False).fillna("")
        merged = merged.loc[merged["GeneID"].astype(str).map(lambda value: gene_exists(active_gene_db, value))]
        keys = [column for column in annotations if column != "taxonomy"]
        merged = merged.drop_duplicates(subset=keys, keep="last")
        for sample in active_samples:
            if sample not in merged.columns:
                merged[sample] = 0
            merged[sample] = pd.to_numeric(merged[sample], errors="coerce").fillna(0)
        merged = merged.loc[:, annotations + active_samples]
        merged.to_excel(output_dir / filename, index=False)
        if "Pathway" in merged.columns:
            merged.groupby("Pathway")[active_samples].sum().to_excel(
                output_dir / (cycle + "_Cycle_pathway.xlsx"), index=True
            )


def rebuild_category_tables(label, output_dir, active_samples):
    configurations = {
        "VFDB": ("gene.vf.tpm.csv", [("VF_Name", "vf.tpm.xlsx"), ("VFcategory", "vf.category.tpm.xlsx")]),
        "ARGs": ("ARG.tpm.csv", [("Type", "ARG.Category.tpm.xlsx")]),
        "COG": ("COG.tpm.csv", [("COG", "COG.Category.tpm.xlsx")]),
        "MetaCyc": ("MetaCyc.tpm.csv", [("MetaCyc", "MetaCyc.Category.tpm.xlsx")]),
    }
    if label not in configurations:
        return
    filename, summaries = configurations[label]
    frame = pd.read_csv(output_dir / filename, encoding="utf-8-sig", low_memory=False)
    for key, target in summaries:
        frame.groupby(key, dropna=True)[active_samples].sum().to_excel(output_dir / target, index=True)


def main():
    parser = argparse.ArgumentParser(description="合并历史累计结果和本次新增样本结果")
    parser.add_argument("--pair", nargs=3, action="append", metavar=("LABEL", "OLD_DIR", "NEW_DIR"), required=True)
    parser.add_argument("--datapath", required=True, help="当前完整项目 metadata 目录")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    active_samples = read_active_samples(args.datapath)
    pairs = {label: (Path(old_dir), Path(new_dir)) for label, old_dir, new_dir in args.pair}

    bowtie_old, bowtie_new = pairs["bowtie"]
    historical_samples = []
    for path in (bowtie_old / "gene_tpm.csv", bowtie_new / "gene_tpm.csv"):
        for column in csv_header(path)[1:]:
            if column not in historical_samples:
                historical_samples.append(column)

    for label, (old_dir, new_dir) in pairs.items():
        print("合并 %s: %s + %s" % (label, old_dir, new_dir))
        output_dir = output_root / label
        output_dir.mkdir(parents=True, exist_ok=True)
        overlay_tree(old_dir, output_dir)
        overlay_tree(new_dir, output_dir)

    clean_old, clean_new = pairs["clean"]
    summary = Path("table") / "sumary.txt"
    merge_sample_summary(clean_old / summary, clean_new / summary,
                         output_root / "clean" / summary, active_samples)

    for filename in ("gene_count.csv", "gene_tpm.csv"):
        merge_gene_csv(
            bowtie_old / filename, bowtie_new / filename,
            output_root / "bowtie" / filename, "GeneID", active_samples,
            historical_samples, drop_all_zero=True,
        )

    active_gene_db, active_gene_db_path = create_gene_index(
        output_root / "bowtie" / "gene_tpm.csv", output_root
    )
    try:
        prodigal_old, prodigal_new = pairs["prodigal"]
        for filename in ("unique_gene.fasta", "clusterRes_rep_seq.fasta", "clusterRes_all_seqs.fasta"):
            if (prodigal_old / filename).exists() and (prodigal_new / filename).exists():
                merge_fasta(prodigal_old / filename, prodigal_new / filename,
                            output_root / "prodigal" / filename, active_gene_db)
        rebuild_gene_statistics(output_root / "prodigal")

        for label in ("tax_annotation", "func_annotation"):
            old_dir, new_dir = pairs[label]
            filenames = ("Tax_id.tmp.txt",) if label == "tax_annotation" else (
                "func.emapper.annotations", "func.emapper.hits", "func.emapper.seed_orthologs"
            )
            for filename in filenames:
                if (old_dir / filename).exists() and (new_dir / filename).exists():
                    merge_tabular_records(old_dir / filename, new_dir / filename,
                                          output_root / label / filename, active_gene_db)

        for label, (filename, key) in GENE_TABLES.items():
            if label not in pairs:
                continue
            old_dir, new_dir = pairs[label]
            merge_gene_csv(old_dir / filename, new_dir / filename,
                           output_root / label / filename, key, active_samples,
                           historical_samples, allowed_gene_db=active_gene_db)
            raw_name = RAW_ANNOTATIONS.get(label)
            if raw_name and (old_dir / raw_name).exists() and (new_dir / raw_name).exists():
                merge_tabular_records(old_dir / raw_name, new_dir / raw_name,
                                      output_root / label / raw_name, active_gene_db,
                                      replace_by_first=False)
            rebuild_category_tables(label, output_root / label, active_samples)

        if "CycDB" in pairs:
            old_dir, new_dir = pairs["CycDB"]
            merge_cycdb(old_dir, new_dir, output_root / "CycDB", active_samples,
                        historical_samples, active_gene_db)
    finally:
        active_gene_db.close()
        active_gene_db_path.unlink()

    prune_sample_artifacts(output_root, active_samples, historical_samples)
    rebuild_all_predicted_genes(output_root / "prodigal", active_samples)
    megahit_dir = output_root / "megahit"
    with open(megahit_dir / "sample.name.txt", "w", encoding="utf-8") as handle:
        for sample in active_samples:
            handle.write(str((megahit_dir / sample).resolve()) + "\n")
    rebuild_qc_excel(output_root / "qc_result", output_root / "clean", args.datapath)


if __name__ == "__main__":
    main()
