import pandas as pd
import argparse
import os
import time
from pathlib import Path

# 记录开始时间
start_time = time.time()

parser = argparse.ArgumentParser(description="deal data to metadata")
parser.add_argument("-indir", required=True, type=str, help="dataDir path")
parser.add_argument("-outdir", required=True, type=str, help="output path")
args = parser.parse_args()

# 确保输出目录存在
Path(args.outdir).mkdir(parents=True, exist_ok=True)

# =========================
# 1. 读取 Excel
# =========================
excel_file = os.path.join(args.indir, "data.xlsx")

df_sample = pd.read_excel(
    excel_file, 
    sheet_name="sample",
    dtype={"fastqfile": str, "sample": str, "group": str}
)
df_comp = pd.read_excel(
    excel_file, 
    sheet_name="comparison",
    header=0,
    dtype=str
)

# =========================
# 2. 生成 sample.txt
# =========================
sample_txt_path = os.path.join(args.outdir, "sample.txt")
df_sample[["fastqfile", "sample"]].to_csv(
    sample_txt_path,
    sep="\t",
    index=False,
    header=True
)

# =========================
# 3. 构建 comparison 映射
# =========================
group_map = {}
for _, row in df_comp.iterrows():
    g = row.iloc[0]
    cats = row.iloc[1:].dropna().astype(str).tolist()
    if cats:
        group_map[g] = cats

groups = list(group_map.keys())

# =========================
# 4. 构建 sample-metadata
# =========================
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

# =========================
# 5. 插入 #q2:types 行
# =========================
type_row = {"sample-id": "#q2:types"}
for g in groups:
    type_row[g] = "categorical"

df_meta = pd.concat(
    [pd.DataFrame([type_row]), df_meta],
    ignore_index=True
)

# =========================
# 6. 保存 sample-metadata.tsv
# =========================
metadata_path = os.path.join(args.outdir, "sample-metadata.tsv")
df_meta.to_csv(
    metadata_path,
    sep="\t",
    index=False
)

# =========================
# 7. 输出运行信息
# =========================
end_time = time.time()
elapsed = end_time - start_time

print(f"\n✅ dealdata.py 运行完成！")
print(f"⏱️  总耗时: {elapsed:.3f} 秒")
print(f"📁 输入目录: {args.indir}")
print(f"📁 输出目录: {args.outdir}")
print(f"📄 生成文件:")
print(f"   - {os.path.basename(sample_txt_path)}")
print(f"   - {os.path.basename(metadata_path)}")