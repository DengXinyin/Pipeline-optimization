import pandas as pd
import argparse
import json
import os
import time
from pathlib import Path

start_time = time.time()

parser = argparse.ArgumentParser(description="deal data to metadata")
parser.add_argument("-indir", required=True, type=str, help="dataDir path")
parser.add_argument("-outdir", required=True, type=str, help="output path")
parser.add_argument(
    "--allow-empty-comparison",
    action="store_true",
    help=(
        "仅供 incremental 新增样本上游使用：comparison 为空时，"
        "按 sample.group 生成一个临时 group1。完整项目元数据仍必须提供 comparison。"
    ),
)
args = parser.parse_args()

Path(args.outdir).mkdir(parents=True, exist_ok=True)

# 读取数据：按列指定 dtype，避免类型推断
excel_file = os.path.join(args.indir, "data.xlsx")
df_sample = pd.read_excel(
    excel_file,
    sheet_name="sample",
    dtype={"fastqfile": str, "sample": str, "group": str},
    engine="openpyxl",
)
df_comp = pd.read_excel(
    excel_file,
    sheet_name="comparison",
    header=0,
    dtype=str,
    engine="openpyxl",
)

required_sample_columns = {"fastqfile", "sample", "group"}
missing_sample_columns = required_sample_columns - set(df_sample.columns)
if missing_sample_columns:
    raise ValueError(
        "sample sheet 缺少必要列: " + ", ".join(sorted(missing_sample_columns))
    )

# 客户、项目和报告信息改由测试者提供的独立文件负责；sample sheet 只保存样本信息。
input_project_info_path = os.path.join(args.indir, "project_info.json")
input_report_no_path = os.path.join(args.indir, "report_no.txt")
if not os.path.isfile(input_project_info_path):
    raise FileNotFoundError(f"输入目录缺少 project_info.json: {input_project_info_path}")
if not os.path.isfile(input_report_no_path):
    raise FileNotFoundError(f"输入目录缺少 report_no.txt: {input_report_no_path}")

with open(input_project_info_path, encoding="utf-8-sig") as handle:
    project_info = json.load(handle)
if not isinstance(project_info, dict):
    raise ValueError("project_info.json 顶层必须是 JSON object。")

required_project_fields = ["客户名称", "客户单位", "项目编号", "项目名称"]
missing_project_fields = [
    field for field in required_project_fields
    if field not in project_info or not str(project_info[field]).strip()
]
if missing_project_fields:
    raise ValueError(
        "project_info.json 缺少或未填写必要字段: " + ", ".join(missing_project_fields)
    )
for field in required_project_fields:
    project_info[field] = str(project_info[field]).strip()

with open(input_report_no_path, encoding="utf-8-sig") as handle:
    report_no = handle.read().strip()
if not report_no:
    raise ValueError("report_no.txt 内容为空。")
if "\n" in report_no or "\r" in report_no:
    raise ValueError("report_no.txt 只能包含一个非空报告编号。")

project_info_path = os.path.join(args.outdir, "project_info.json")
with open(project_info_path, "w", encoding="utf-8") as handle:
    json.dump(project_info, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
report_no_path = os.path.join(args.outdir, "report_no.txt")
with open(report_no_path, "w", encoding="utf-8") as handle:
    handle.write(report_no + "\n")

for column in ["fastqfile", "sample", "group"]:
    df_sample[column] = df_sample[column].fillna("").astype(str).str.strip()
    empty_rows = df_sample.index[df_sample[column] == ""].tolist()
    if empty_rows:
        excel_rows = ", ".join(str(i + 2) for i in empty_rows)
        raise ValueError(f"sample sheet 的 {column} 列存在空值，Excel 行: {excel_rows}")

for column in ["fastqfile", "sample"]:
    duplicate_values = sorted(
        df_sample.loc[df_sample[column].duplicated(keep=False), column].unique()
    )
    if duplicate_values:
        raise ValueError(
            f"sample sheet 的 {column} 必须唯一，重复值: {', '.join(duplicate_values)}"
        )

if df_comp.empty and not args.allow_empty_comparison:
    raise ValueError(
        "comparison sheet 仅含表头、没有比较定义。"
        "请至少填写一行比较：第一列为比较名称，后续列填写 sample sheet 的 group 列中的分组值。"
    )

# 生成 sample.txt。第二列是所有分析 task 使用的稳定样本 ID，必须使用
# fastqfile/internal_id；客户展示名只保留在 data.xlsx 和 registry 中。
sample_path = os.path.join(args.outdir, "sample.txt")
df_sample_for_tasks = df_sample[["fastqfile"]].copy()
df_sample_for_tasks["sample"] = df_sample_for_tasks["fastqfile"]
df_sample_for_tasks.to_csv(sample_path, sep="\t", index=False)
display_name_map_path = os.path.join(args.outdir, "display_name_map.tsv")
df_sample[["fastqfile", "sample"]].rename(
    columns={"fastqfile": "internal_id", "sample": "display_name"}
).to_csv(display_name_map_path, sep="\t", index=False)

# 构建 group_map：每一行 comparison 定义一个用于下游比较的分组集合。
# 表头不是比较定义，不能在空表时当作成员使用。
sample_groups = {
    str(value).strip()
    for value in df_sample["group"].dropna()
    if str(value).strip()
}
raw_group_map = []
if df_comp.empty:
    if not sample_groups:
        raise ValueError("incremental 输入没有任何有效 sample.group，无法生成临时分组。")
    raw_group_map.append(sorted(sample_groups))
    print("ℹ️ incremental 输入 comparison 为空：已按 sample.group 生成临时 group1。")
else:
    for row_index, row in df_comp.iterrows():
        comparison_name = "" if pd.isna(row.iloc[0]) else str(row.iloc[0]).strip()
        members = [
            str(value).strip()
            for value in row.iloc[1:].dropna()
            if str(value).strip()
        ]
        if not comparison_name:
            raise ValueError(f"comparison sheet 第 {row_index + 2} 行缺少比较名称。")
        if len(members) < 2:
            raise ValueError(
                f"comparison sheet 第 {row_index + 2} 行（{comparison_name}）至少需填写两个分组。"
            )
        unknown_members = sorted(set(members) - sample_groups)
        if unknown_members:
            raise ValueError(
                f"comparison sheet 第 {row_index + 2} 行（{comparison_name}）包含 sample.group 中不存在的分组: "
                f"{', '.join(unknown_members)}。当前可用分组: {', '.join(sorted(sample_groups))}"
            )
        raw_group_map.append(members)

# 下游脚本（QC_stats、tax_stats 等）期望 metadata 列名为 group1, group2...
groups = [f"group{i+1}" for i in range(len(raw_group_map))]
group_map = dict(zip(groups, raw_group_map))

# 构建元数据：使用 apply 向量化操作
def build_metadata_row(row, groups, group_map):
    # metadata、丰度矩阵和中间文件统一使用 internal_id。展示名在最终
    # collect/rewrite_display_names 阶段替换，改名不会触发上游重跑。
    sid = row["fastqfile"]
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

# 输出一个标准化 data.xlsx：固定包含 sample、comparison、information 三个工作表。
# information 使用纵向“字段/内容”结构，并保留 project_info.json 的全部顶层字段。
information_rows = []
for key, value in project_info.items():
    if str(key) == "报告编号":
        continue
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    elif value is None:
        value = ""
    else:
        value = str(value)
    information_rows.append({"字段": str(key), "内容": value})
information_rows.append({"字段": "报告编号", "内容": report_no})
df_information = pd.DataFrame(information_rows)
normalized_xlsx = os.path.join(args.outdir, "data.xlsx")
with pd.ExcelWriter(normalized_xlsx, engine="openpyxl") as writer:
    df_sample[["fastqfile", "sample", "group"]].to_excel(
        writer, sheet_name="sample", index=False
    )
    df_comp.to_excel(writer, sheet_name="comparison", index=False)
    df_information.to_excel(writer, sheet_name="information", index=False)

elapsed = time.time() - start_time
print(f"\n✅ 完成！耗时: {elapsed:.3f}秒")
print(f"📄 输出: {sample_path}, {metadata_path}, {display_name_map_path}, {project_info_path}, {report_no_path}, {normalized_xlsx}")
