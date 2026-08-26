# metage_v2.88.2

本目录是 metage_v2.88.2 的正式发布目录。历史版本目录未修改。

## 版本身份

- WDL：`metage_v2.88.2.wdl`
- Docker 发布标签：`dockerhub.genostack.com/sanshu/metage:v2.88.2`
- 生产固定镜像：`dockerhub.genostack.com/sanshu/metage@sha256:5264730802751d591f1a6f25878597377778493d3a396b5ee324475004e60adf`
- Image ID：`sha256:0fb663a27ae669d6b01e376ccdb93e540e2552a2f52d2903f5316c062e8518da`
- 镜像状态：2026-08-07 已构建、完成镜像内增量回归并推送
- WDL 风格：draft-2 兼容写法
- Docker 基础镜像：固定为 v2.88 digest，再复制本目录 `scripts/` 和字体生成 v2.88.2
- 默认绘图字体：Times New Roman；同时包含 Arial，并继承宋体

WDL、`cromwell_config.conf` 和 `run_workflow.sh` 均已固定到上述
生产 digest；发布标签仅用于构建、验证和推送，不作为生产运行引用。

## 目录内容

```text
metage_v2.88.2/
├── metage_v2.88.2.wdl
├── scripts/                    # 打入镜像的完整运行与绘图脚本
├── fonts/                      # Times New Roman、Arial 字体文件
├── Dockerfile
├── .dockerignore
├── cromwell_config.conf        # node4 本地 Cromwell 示例配置
├── options.json                # call-cache 选项
├── examples/                   # full/reuse/incremental 示例输入
├── node1_test_bundle_v2.88.2/  # node1 测试包展开目录
├── metage_v2.88.2_node1_test_bundle.tar.gz
├── run_workflow.sh             # 本地 Cromwell 辅助入口
├── run_sample_*.sh             # 本地增删改辅助入口
└── README.md
```

归档不包含 Cromwell 历史结果、数据库、日志、metadata、HSQLDB、FASTQ 业务测试数据、`__pycache__`、`.pyc`、`.legacy` 或 `.bk` 文件。

node1 测试时上传 `metage_v2.88.2_node1_test_bundle.tar.gz`；包内包含固定生产
digest 的 WDL、三种运行模式 JSON、项目输入模板、参数说明和镜像验证脚本，具体
操作见包内 `README_node1_test.md`。FASTQ 和数据库不在测试包内。

## 项目数据目录

推荐每个项目使用独立目录：

```text
PROJECT_ROOT/
├── data/
│   ├── data.xlsx
│   ├── project_info.json
│   ├── report_no.txt
│   └── sample_registry.tsv       # 第一次 full 成功后由运行器登记
├── rawdata/                       # 也可以是其他共享 FASTQ 目录
└── incremental_data/
    └── data.xlsx                  # 仅 incremental 模式需要
```

`incremental_data` 和 `sample_registry.tsv` 的路径由 WDL 内部按上述约定确定，不在参数界面填写。

## data.xlsx 规范

测试者必须提供 `data.xlsx`、`project_info.json` 和 `report_no.txt`。输入检查会把
项目信息写入标准化 `data.xlsx` 的 `information` 工作表；原始 `data.xlsx` 至少
包含 `sample` 和 `comparison` 两个工作表。

### sample 工作表

必须包含以下列：

| 列名 | 含义 | 规则 |
|---|---|---|
| `fastqfile` | 内部样本 ID/FASTQ 前缀 | 必须唯一；改名时保持不变 |
| `sample` | 报告显示名 | 必须唯一；允许按客户要求修改 |
| `group` | 当前样本分组 | 必须非空 |

客户名称、客户单位、项目编号和项目名称由外部 `project_info.json` 提供；报告编号
由外部 `report_no.txt` 提供，不再从 sample 工作表读取。

### comparison 工作表

- 第一列是比较名称。
- 后续列填写参与比较的 `group` 值。
- 每一行至少包含两个有效分组。
- 修改、删除或增加分组后，必须同步检查 comparison 中是否仍引用有效分组。
- 完整项目的 `data/data.xlsx` 不允许 comparison 只有表头；`incremental_data/data.xlsx` 可为空，由流程临时生成上游所需分组。

## WDL 路径类型

顶层路径全部以 `String` 或 `String?` 传入，而不是 `Directory`：

- `project_root`
- `datapath`
- `rawdatapath`
- `mapdir`
- `parent_workflow_dir`（可选 String，仅非 full 使用）

`registry_md5`、`registry_tsv_path`、`sample_registry_tsv`、`incremental_datapath` 不属于平台用户输入。WDL 内部读取 `${project_root}/data/sample_registry.tsv`、计算 MD5，并解析 `${project_root}/incremental_data`。

顶层开关 `use_kraken2` 为 String，合法业务值为 `"yes"` 或 `"no"`，默认
`"no"`。分析流程固定开启；物种 Beta 默认输出 Bray-Curtis、Binary Jaccard、
Weighted UniFrac 和 Unweighted UniFrac。无需提交 `analyse`、`do_unifrac`、
`tax_tree` 或 `func_tree`；物种分类树由上游注释和 `mapdir/database/taxonomy`
自动生成。

## 功能注释增强结果

- KEGG 基因级 `KEGG.tpm.csv` 包含单列 `taxonomy`、`KO`、KO pathway 层级、
  `Description`、`Preferred_name`、`EC` 及其他 KEGG 字段，后接各样本丰度列。
- `func_base` 生成 `Result/GeneAnnotationSummary/All_gene_annotation_summary.csv`；
  每个 GeneID 一行，第二列是以下划线连接的界门纲目科属种信息，后续按数据库
  分列保存 KEGG、eggNOG、CAZy、GO、ARG、VFDB、mobileOG、BacMet2、QS、COG、
  MetaCyc 和 CycDB 原始注释字段。
- 行数不超过 Excel 上限时，同时生成 `All_gene_annotation_summary.xlsx`。
- 汇总目录会随 `func_base.Result` 合并到最终 `respath`，对应路径为
  `Result/Result/GeneAnnotationSummary/`。

## full：首次完整运行

适用：新项目、无可复用父流程，或已有样本 FASTQ 内容发生变化需要重新建立联合基因集。

参数界面需要设置：

- `project_root`
- `datapath=${project_root}/data`
- `rawdatapath`：双端 FASTQ 所在目录
- `mapdir`：完整宏基因组数据库根目录
- `run_mode="full"`

`parent_workflow_dir` 留空或不传。示例见 `examples/inputs.full.example.json`。

成功后流程会把项目级 registry 更新到：

```text
${project_root}/data/sample_registry.tsv
```

该文件和本次成功 workflow UUID 是后续复用的基础，不能删除。

## reuse：只重做汇总、统计、可视化和报告

适用：没有新增样本上游数据，仅进行样本删除、显示名修改、分组修改，或按镜像固定样式重新生成图表和报告。

必须：

- 先成功完成一次 full。
- `${project_root}/data/sample_registry.tsv` 存在且非空。
- 在 WDL 参数界面设置 `run_mode="reuse"`。
- 在 WDL 参数界面显式设置 `parent_workflow_dir`，只填写父流程 UUID。
- `data/data.xlsx` 是本次最终完整样本表。

示例见 `examples/inputs.reuse.example.json`。

### 样本改名

只修改 `sample` 列；`fastqfile` 必须保持不变。这样上游中间文件继续按内部 ID 复用，报告和图中使用新显示名。运行模式为 `reuse`。

### 删除样本

从 `sample` 工作表删除对应整行，并同步更新 comparison。必须使用 Excel
的“删除整行”，不能只清空这一行的单元格；删除后 `sample` 工作表的数据区
不能保留空行，尤其不能在两个有效样本行之间出现空白行，否则输入检查会把
该行识别为缺少 `fastqfile`、`sample` 或 `group` 并终止流程。保存前应确认
有效样本行连续排列。不要把其他样本 FASTQ 或父流程结果删除。运行模式为
`reuse`。

### 修改分组

修改 `group` 列，并同步更新 comparison。内部样本 ID 和 FASTQ 不变。运行模式为 `reuse`。

### 同时删除、改名、改组

在同一份最终 `data/data.xlsx` 中完成所有修改，检查 `fastqfile` 唯一、`sample` 唯一、comparison 有效，然后运行一次 `reuse`。

## incremental：增加样本或包含新增样本的 multi-change

适用：在已有 full 结果上增加新样本，同时可以伴随删除、改名和改组。

必须：

- `run_mode="incremental"`
- 参数界面显式传入父流程 UUID：`parent_workflow_dir`
- `${project_root}/data/sample_registry.tsv` 存在
- `data/data.xlsx` 保存变更后的完整最终样本集合
- `${project_root}/incremental_data/data.xlsx` 只保存需要跑上游的新样本
- `rawdatapath` 中能找到新增样本的成对 R1/R2 FASTQ

示例见 `examples/inputs.incremental.example.json`。

### 完整增量执行边界

增量模式不会在累计基因集上重新运行全部数据库比对，实际执行顺序为：

```text
新增样本 QC/MEGAHIT/Prodigal/BWA
  → 新增基因 tax_anno + func_anno
  → 新增基因 anno_new
  → 新增基因 VFDB/ARG/CycDB/mobileOG/BacMet2/QS/COG/MetaCyc
  → 各数据库分别与父流程累计状态合并
  → 在当前完整样本集合上重建 anno、tax_base、func_base、diff 和 report
```

累计合并按 `GeneID` 处理，新增记录覆盖同名历史记录；丰度矩阵只保留当前
`data.xlsx` 中的 internal_id 列。累计 QC Excel、`unique_length.txt` 和
`unique_stats.txt` 会重新生成。新增同时删除样本时，已删除样本的列、样本文件以及
不再被任何当前样本支持的基因记录会从新的累计状态中移除。

该模式的累计基因集是各批次非冗余基因集的并集，不会跨所有历史批次重新运行一次
MMseqs 聚类。物种、KO、pathway 及各功能数据库按类别重新汇总；但 GeneID 层面的
跨批次“一套联合去冗余 catalog”解释仍有限制。需要严格联合 catalog 或已有样本
FASTQ 内容改变时，应使用 `full`。

### 仅增加样本

1. 在完整 `data/data.xlsx` 增加新样本行。
2. 在 `incremental_data/data.xlsx` 仅保留新增样本行。
3. 更新完整表的 comparison。
4. 使用 `incremental` 和父 workflow UUID 运行。

### multi-change

如果同时包含增加、删除、改名和改组：

- 完整 `data/data.xlsx` 表示最终状态：新增行已加入、删除行已移除、显示名和分组已更新。
- `incremental_data/data.xlsx` 仅包含新增样本；删除、改名、改组无需重跑上游。
- 使用 `incremental`。

如果 multi-change 不包含新增样本，则使用 `reuse`，不需要 `incremental_data`。

已有样本的 FASTQ 文件内容、路径、大小或时间戳发生变化时，不能按普通改名处理；本地规划器会为安全起见强制 `full`。

## parent_workflow_dir 规则

- `full`：不传。
- `reuse`：在 WDL 参数界面传入。
- `incremental`：在 WDL 参数界面传入。
- 只填写成功父流程的 UUID，例如：

```text
494a6b8a-43d1-4848-98bb-2efb9e481b31
```

WDL 会固定拼接：

```text
/cephfs_data/genostack_v3/genostack_cromwell/cromwell-executions/metage_v2_88_2/<UUID>
```

首次 incremental 的父流程通常是成功的 full；连续新增时，下一次必须使用最近一次
成功、且包含当前最大累计样本集合的 incremental workflow UUID。不能始终指向首次
full，否则后续新增无法继承前一批新增样本。

父流程定位会优先读取 `call-merge_upstream_results/execution/merged/*` 的累计状态，
并兼容旧 full 的 `call-*` 目录、旧版任务名以及 Cromwell `cacheCopy`。本地规划器按
“项目编号 + 项目名称/内容 + 客户名称”精确匹配 registry，并优先选择覆盖样本最多、
其后时间最新的有效 workflow；平台手工提交时应按同一规则选择 UUID。

WDL 不能仅根据 `project_root` 在云平台中可靠判断应该复用哪个历史 UUID，因此该参数仍由分析人员选择。

## 可视化重分析

云平台 WDL 不暴露 `plot_*` 参数，绘图样式固定读取镜像内的
`plot_style.default.json`。`choose_plot_style` 会生成统一配置，供 R 和 Python
绘图脚本共同读取；因此平台提交时无需填写任何可视化参数。

## 本地辅助脚本

```bash
bash run_sample_full.sh --inputs examples/inputs.full.example.json
bash run_sample_rename.sh --inputs examples/inputs.reuse.example.json
bash run_sample_delete.sh SAMPLE_ID --inputs examples/inputs.reuse.example.json
bash run_sample_add.sh --inputs examples/inputs.incremental.example.json
bash run_sample_multi_change.sh --inputs examples/inputs.incremental.example.json
```

本地 `run_workflow.sh` 会在固定 Cromwell 根目录中扫描历史 registry、选择父流程并
生成执行计划；平台直接上传 WDL 时仍按上文显式填写 `parent_workflow_dir`。固定根目录为：

```text
/cephfs_data/genostack_v3/genostack_cromwell/cromwell-executions/metage_v2_88_2
```

## 构建与推送 v2.88.2

在本目录执行。私有仓库基础镜像需要先登录：

```bash
sudo docker login dockerhub.genostack.com

sudo docker pull \
  dockerhub.genostack.com/sanshu/metage_megahit@sha256:18bd9eff6f0cd3b2643ddc2981e5a602a27c16ea1d481869558bc7fdaf0f83cb
```

如果基础仓库暂时不可访问，可从本机已归档的同一 v2.88 镜像恢复；恢复后必须用
`docker image inspect` 确认其 RepoDigest 是上面的固定 digest：

```bash
sudo docker load --input \
  /home/xydeng/Metagenomics_Docker/metage_megahit:v2.88_taizhou/metage_megahit_v2.88_taizhou.tar.gz

sudo docker image inspect \
  dockerhub.genostack.com/sanshu/metage_megahit@sha256:18bd9eff6f0cd3b2643ddc2981e5a602a27c16ea1d481869558bc7fdaf0f83cb
```

固定基础镜像的 `py39` 环境已包含 `openpyxl==3.1.2`。构建过程会严格验证该版本，
供 `data.xlsx` 和增量合并脚本使用，不需要访问外部 PyPI：

```bash
cd /home/xydeng/Metagenomics_Docker/metage_v2.88.2

sudo docker build \
  -f Dockerfile \
  -t dockerhub.genostack.com/sanshu/metage:v2.88.2 \
  .

sudo docker run --rm \
  dockerhub.genostack.com/sanshu/metage:v2.88.2 \
  bash -lc '
    set -euo pipefail
    test -f /root/microbiome/microbiome/metage_v2.88.2/dealdata_update.py
    test -f /root/microbiome/microbiome/metage_v2.88.2/choose_plot_style.py
    test -f /root/microbiome/microbiome/metage_v2.88.2/merge_upstream_results.py
    test -f /root/microbiome/microbiome/metage_v2.88.2/test_incremental_merge.py
    /root/anaconda3/bin/conda run -n py39 python -c \
      "import Bio, matplotlib, numpy, openpyxl, pandas; assert openpyxl.__version__ == \"3.1.2\""
    /root/anaconda3/bin/conda run -n py39 python \
      /root/microbiome/microbiome/metage_v2.88.2/test_incremental_merge.py
    fc-match "Times New Roman"
    fc-match "Arial"
    fc-match "SimSun"
  '

sudo docker push dockerhub.genostack.com/sanshu/metage:v2.88.2

sudo docker image inspect \
  dockerhub.genostack.com/sanshu/metage:v2.88.2 \
  --format 'ID={{.Id}} RepoDigests={{json .RepoDigests}}'
```

生产运行配置已固定为：

```wdl
docker: "dockerhub.genostack.com/sanshu/metage@sha256:5264730802751d591f1a6f25878597377778493d3a396b5ee324475004e60adf"
```

不得把基础镜像 digest、旧版本 digest 或可变 tag 当作 v2.88.2 的生产镜像。
