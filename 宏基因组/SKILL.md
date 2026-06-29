# 宏基因组流程优化协作 Skill

## 1. 本 Skill 的用途

用于指导任意 AI 助手参与 **宏基因组 `metage_megahit.wdl` 流程优化项目** 的协作。核心目标是：

- 保持原代码（`scripts/`）只读，所有优化代码放在 `scripts_dxy/Script/*_update.*`。
- 每个 task 跑完原代码和优化版后，由 AI 助手快速核对运行时间、记录优化点，并同步到展示文档和统计表。
- 所有规范以 `Todo_list.txt` 为准；AI 助手不应凭空改动工作流本身，除非用户明确要求。

## 2. 项目关键文件与分工

| 文件/目录 | 角色 | AI 助手能否修改 |
|-----------|------|----------------|
| `scripts/` | 原代码，只读 | ❌ 禁止修改 |
| `scripts_dxy/Script/*_update.*` | 用户编写的优化版代码 | ❌ 原则上由用户编写；AI 可应用户要求协助，但需保留 `_update` 后缀 |
| `scripts_dxy/logs/<序号>_<task>_<original\|update>_runtime.log` | 运行日志 | ❌ AI 不直接生成，只读取 |
| `scripts_dxy/Readme_dxy.Qmd` | 用户维护：记录每个 task 的命令、时间、问题、优化点 | ❌ 用户主笔；AI 只读取 |
| `scripts_dxy/Metagenomic_pipeline_optimization_kimi.Qmd` | Kimi/AI 维护：汇总展示优化结果 | ✅ 按规范同步更新 |
| `scripts_dxy/宏基因组优化效率统计.xlsx` | Kimi/AI 维护：效率统计表 | ✅ 按规范同步更新 |
| `scripts_dxy/Todo_list.txt` | 工作流规范与当前状态 | ✅ 可按用户要求补充状态/改进点；不擅自改流程 |
| `scripts_dxy/Metagenomic_pipeline_overall.qmd` | 流程总览说明书 | ✅ 可更新 task 状态/时间 |

## 3. 单个 Task 的标准工作流（6 + 1 步）

```text
Step 1: 用户运行原代码 → logs/<序号>_<task>_original_runtime.log
Step 2: 用户在 Readme_dxy.Qmd 记录原代码时间、数据量、问题
Step 3: 用户编写优化代码 scripts_dxy/Script/<script>_update.*
Step 4: 用户运行优化版 → logs/<序号>_<task>_update_runtime.log
Step 5: 用户在 Readme_dxy.Qmd 记录优化版时间、优化点、提升效率
Step 6: 用户通知 AI 同步 → AI 更新 kimi.Qmd 和 xlsx
Step 7: AI 运行时间复核（见第 5 节）
```

AI 助手主要在 **Step 6~7** 介入。

## 4. 必须遵守的规范

### 4.1 时间与日志

- **时间以 Linux `time` 命令输出的 `real`（wall-clock）为准**。
- 所有时间戳对话统一使用 **北京时间（CST, UTC+8）**；服务器本地时间为 EDT，需要换算时加 12 小时（按夏令时）。
- 日志命名：`<序号>_<task_name>_<original|update>_runtime.log`。
  - 序号严格按 WDL `isbwa == "yes"` 主流程 task 顺序：01~21。
  - 非 WDL task（如 `R 脚本修改`、`check_input_no_raw`）不占用主序号，可用 `00_` 前缀。
- 日志必须包含统一的开始/结束时间头和 `real/user/sys` 行。

### 4.2 代码与目录

- 优化脚本必须加 `_update` 后缀。
- 优化版应支持参数化输出目录（如 `--resdir`、`--func_tmp`、`--tpmdir`），**优先输出到独立目录**，避免覆盖 `Result/`。
- 推荐使用 `subprocess.run(..., check=True)` / `set -euo pipefail`，实现失败即停。
- 调用 R 脚本时，原 `scripts/` 挂载到 `/scripts` 并设置 `METAGE_SCRIPTS_PATH=/scripts`，优化目录挂载到 `/root/microbiome/microbiome/metage_megahit`。

### 4.3 Qmd 文档

- `Metagenomic_pipeline_optimization_kimi.Qmd` 中每个 Task 章节按统一结构：
  1. 原代码路径及运行方式
  2. 优化后代码路径及运行方式
  3. 主要优化点及优化结果（8 列表格）
  4. 原代码内容
  5. 优化代码内容
- 8 列表格必须包含：模块 / 内容 / 数据量 / 优化前时间 / 优化后时间 / 提升效率 / 代码位置 / 备注。
- 章节标题 `## N.M` / `### N.M.K` 必须与 Task 编号一致。

### 4.4 Excel 统计表

- 工作表 `"效率统计"` 8 列：模块 / 内容 / 数据量 / 优化前时间 / 优化后时间 / 提升效率 / 代码位置 / 备注。
- 代码位置列使用完整路径，例如：
  ```text
  /home/xydeng/Metagenomics/scripts/func_stats.py → /home/xydeng/Metagenomics/scripts_dxy/Script/func_stats_update.py
  ```

## 5. AI 同步与复核操作（重点）

### 5.1 触发条件

当用户说以下任一语句时，AI 应执行同步：

- "Readme_dxy.Qmd 已更新"
- "更新 kimi Qmd"
- "同步优化结果"
- "<task> 跑完了"
- "deHOST 时间补上了"

### 5.2 同步步骤

1. 读取 `Readme_dxy.Qmd` 中该 task 的章节，提取最新 `real` 时间、数据量、优化点。
2. 读取 `Todo_list.txt` 确认当前 task 状态。
3. （如用户明确要求复核）读取以下 4 个文件中该 task 的对应章节：
   - `Metagenomic_pipeline_optimization_kimi.Qmd`
   - `Readme_dxy.Qmd`
   - `Todo_list.txt`
   - `宏基因组优化效率统计.xlsx`
   核对时间是否一致，并将优化改进点补充到 `Todo_list.txt`。
4. 更新 `Metagenomic_pipeline_optimization_kimi.Qmd`：
   - 顶部“宏基因组优化效率统计汇总”表
   - Task 章节内的 8 列表格
   - 必要时更新运行方式注释
5. 更新 `宏基因组优化效率统计.xlsx` 中该 task 行。
6. 读取更新后的 `kimi.Qmd` 相关部分，确认格式正确。
7. 回复用户已同步的内容及变更摘要。

### 5.3 复核原则

- **只读取当前 task 对应章节**，不要全量读取无关板块。
- 提升效率以 `real` 时间计算，保留 1 位小数。
- 改进点应具体：并行化、bug 修复、参数化、失败即停、输出隔离、列名/文件名修复等。

## 6. 常见错误与排查

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| `tax_diff*.py` 报 `No such file ... phylum.xlsx` | `/Result` 下缺少 `tax_base` 输出 | 挂载 `Result_update:/Result` 作为输入 |
| `vfdb_stats_update.py` 报找不到 `VFDB.tpm.csv` | 实际文件名为 `gene.vf.tpm.csv` | 修正读取文件名和分组列名 |
| `mobileOG_stats_update.py` 报 `mobileOG` 列不存在 | 实际列为 `mobileOG Entry Name` / `Major mobileOG Category` | 修正列名并取前 11 列元数据 |
| `BacMet2_stats_update.py` 分组列报错 | 实际列为 `Gene_name` / `Compound` | 修正列名并取前 7 列元数据 |
| `QS_stats_update.py` 分组列报错 | 实际列为 `Entry` / `Protein family`，且需先 drop `Length` | 修正列名、列数并 drop Length |
| 后台 `sudo docker` 失败 | 非交互式 shell 无法输入 sudo 密码 | 改为用户在 tmux 中手动执行 |
| 优化版覆盖 `Result/` 原内容 | 未使用 `--resdir` 隔离输出 | 指定 `Result_update/` 或独立输出目录 |

## 7. 当前 Task 状态速查（截至本 Skill 生成时）

已完成的 task（可直接同步/复核）：

- `check_input_no_raw`、`check_input_with_raw`、`kneaddata_no`、`megahit_no`、`prodig_no`、`bwa_no`、`tax_anno`、`func_anno`、`anno`、`VCA_anno`、`MBQ_anno`、`tax_base`、`func_base`

待运行/待回填的 task：

- `tax_diff`、`func_diff`、`coll_res_ana`、`res2json`、`resFile`
- `bins`、`bins_drep`、`quant_classify`、`bins_stats` 尚未开始优化

> 实际状态以 `Todo_list.txt` 实时内容为准。

## 8. 通用化替换（用于其他项目）

| 本项目路径 | 通用替换 |
|------------|----------|
| `/home/xydeng/Metagenomics/` | 你的项目根目录 |
| `scripts/` | 原代码目录 |
| `scripts_dxy/Script/` | 优化代码目录 |
| `scripts_dxy/logs/` | 日志目录 |
| `Readme_dxy.Qmd` | 优化记录文档 |
| `Metagenomic_pipeline_optimization_kimi.Qmd` | AI 维护展示文档 |
| `宏基因组优化效率统计.xlsx` | 效率统计表格 |
| `metage_megahit.wdl` | 你的工作流文件 |

## 9. 记忆口诀

- **原代码不动，优化加 `_update`**。
- **时间看 `real`，对话用北京时间**。
- **日志命名按 `序号_task_类型_runtime.log`**。
- **用户写 Readme，AI 写 kimi.Qmd 和 xlsx**。
- **同步前先看 Todo_list，同步后给出摘要**。
