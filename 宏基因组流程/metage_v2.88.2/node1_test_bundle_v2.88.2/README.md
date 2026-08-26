# metage v2.88.2 测试与运行包

本目录是 v2.88.2 唯一的 WDL、输入模板和本地 Cromwell 测试入口。Python/R 脚本及报告模板由镜像提供；FASTQ、数据库和 Cromwell 历史结果不进入仓库。

## 目录

```text
node1_test_bundle_v2.88.2/
├── workflow/
│   ├── metage_v2.88.2.wdl             # 普通流程（唯一主版本）
│   └── metage_v2.88.2_dehost.wdl      # 去宿主流程
├── inputs/
│   ├── inputs.node1.full.json
│   ├── inputs.node1.full.kraken2.json
│   ├── inputs.node1.reuse.json
│   └── inputs.node1.incremental.json
├── batch/
│   ├── run_sample_full.sh
│   ├── run_sample_full_kraken2.sh
│   ├── run_sample_add.sh
│   ├── run_sample_delete.sh
│   ├── run_sample_rename.sh
│   ├── run_sample_multi_change.sh
│   └── run_workflow.sh                # 公共底层入口
├── config/
│   ├── cromwell_config.conf
│   └── options.json
├── docs/
│   ├── metage_v2.88.2.qmd
│   ├── metage_v2.88.2_WDL参数说明.xlsx
│   └── metage_v2.88.2_参数说明.txt
├── prepare_full_rawdata.sh
└── verify_node1_image.sh
```

## WDL 与输入

- 平台普通流程使用 `workflow/metage_v2.88.2.wdl`；去宿主流程使用 `workflow/metage_v2.88.2_dehost.wdl`。
- 根据运行模式选择 `inputs/` 下对应 JSON，并将其中项目路径、数据库路径和父流程 UUID 替换为真实值。
- `full` 用于首次完整分析；`reuse` 用于不重跑上游而重新汇总；`incremental` 用于新增样本后合并历史有效结果。
- `use_kraken2=yes` 时使用 Kraken2 输入模板；数据库必须为所有计算节点可读的共享路径。

项目目录需要至少包含：

```text
<PROJECT_ROOT>/
├── data/
│   ├── data.xlsx
│   ├── project_info.json
│   └── report_no.txt
└── rawdata/
    ├── SAMPLE_R1.fq.gz
    └── SAMPLE_R2.fq.gz
```

首次 full 成功后保留 `<PROJECT_ROOT>/data/sample_registry.tsv`；reuse/incremental 依赖该文件及一个成功的父流程 UUID。

## 本地运行

在 `batch/` 目录执行。若需自定义输入，`--inputs` 可使用绝对路径或相对于测试包根目录的路径。

```bash
cd node1_test_bundle_v2.88.2/batch

bash run_sample_full.sh
bash run_sample_full_kraken2.sh
bash run_sample_add.sh --inputs inputs/inputs.node1.incremental.json
bash run_sample_delete.sh SAMPLE_ID
bash run_sample_rename.sh --inputs inputs/inputs.node1.reuse.json
bash run_sample_multi_change.sh --inputs inputs/inputs.node1.incremental.json
```

`run_workflow.sh` 负责计划生成、Cromwell 调用与成功后的 registry 提交；除排错外通常不直接运行。

## 运行前检查

```bash
bash verify_node1_image.sh
test -d /public/nfs_data/public_file_data/metagenome-DB/database
```

当前 WDL 使用镜像 `dockerhub.genostack.com/sanshu/metage:v2.88.2`。字体参数如含空格，在平台表单中使用下划线（例如 `Times_New_Roman`）；工作流会还原为字体名。
