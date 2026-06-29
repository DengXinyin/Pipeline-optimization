import pandas as pd
import argparse
import os
import time
from pathlib import Path

start_time = time.time()

parser = argparse.ArgumentParser(description="deal data to metadata")
parser.add_argument("-indir", required=True, type=str, help="dataDir path")
parser.add_argument("-outdir", required=True, type=str, help="output path")
args = parser.parse_args()

Path(args.outdir).mkdir(parents=True, exist_ok=True)

# 读取数据：按列指定 dtype，避免类型推断
excel_file = os.path.join(args.indir, "data.xlsx")
df_sample = pd.read_excel(
    excel_file,
    sheet_name="sample",
    dtype={"fastqfile": str, "sample": str, "group": str}
)
df_comp = pd.read_excel(excel_file, sheet_name="comparison", header=0, dtype=str)

# 生成 sample.txt
sample_path = os.path.join(args.outdir, "sample.txt")
df_sample[["fastqfile", "sample"]].to_csv(sample_path, sep="\t", index=False)

# 构建 group_map
group_map = {}
for _, row in df_comp.iterrows():
    group_name = row.iloc[0]
    members = row.iloc[1:].dropna().astype(str).tolist()
    if members:
        group_map[group_name] = members

groups = list(group_map.keys())

# 构建元数据：使用 apply 向量化操作
def build_metadata_row(row, groups, group_map):
    sid = row["sample"]
    cat = str(row["group"])
    out_row = {"sample-id": sid}
    for g in groups:
        out_row[g] = cat if cat in group_map.get(g, []) else ""
    return out_row

metadata_rows = df_sample.apply(
    lambda row: build_metadata_row(row, groups, group_map),
    axis=1
).tolist()

df_meta = pd.DataFrame(metadata_rows)

# 添加 q2:types 行
type_row = {"sample-id": "#q2:types"}
for g in groups:
    type_row[g] = "categorical"
df_meta = pd.concat([pd.DataFrame([type_row]), df_meta], ignore_index=True)

# 保存
metadata_path = os.path.join(args.outdir, "sample-metadata.tsv")
df_meta.to_csv(metadata_path, sep="\t", index=False)

elapsed = time.time() - start_time
print(f"\n✅ 完成！耗时: {elapsed:.3f}秒")
print(f"📄 输出: {sample_path}, {metadata_path}")
