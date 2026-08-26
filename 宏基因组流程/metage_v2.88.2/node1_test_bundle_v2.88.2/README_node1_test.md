# metage_v2.88.2：node1 测试包

本包用于在 node1 测试正式发布的 `metage_v2.88.2`。运行脚本已经打入 Docker
镜像，因此不重复打包 `scripts/`；本包也不包含 FASTQ、数据库、Docker tar 或
Cromwell 历史结果。

## 固定版本

- WDL：`workflow/metage_v2.88.2.wdl`（普通版）和
  `workflow/metage_v2.88.2_dehost.wdl`（去宿主版）
- 发布标签：`dockerhub.genostack.com/sanshu/metage:v2.88.2`
- 当前 RepoDigest：`dockerhub.genostack.com/sanshu/metage@sha256:2bbad1518c512ffd3ad453b3078f72d9d1079d0b51362c07daad6fc272018532`
- Image ID：`sha256:e820fc8f28b3e06967e064d8fd8c27ad162aeac578cb911dd7ce9edec375f194`
- 创建时间：`2026-08-19T14:12:46.111566461+08:00`
- 架构：`amd64`

WDL 的常规 task 均使用发布标签 `metage:v2.88.2`；两个分箱 task 继续使用独立的
`192.168.30.202:23099/metage_megahit/metawrap:v1.79`。

当前 WDL 已兼容平台对含空格或 `#` 的 String 重复包双引号的行为：
字体参数请填写无空格形式（例如 `Times_New_Roman`）。`choose_plot_style` 会先剥掉字体和配色值首尾多余的一层双引号，并将字体名中的下划线恢复为空格，再传给镜像脚本。

## 包内文件

```text
node1_test_bundle_v2.88.2/
├── workflow/
│   ├── metage_v2.88.2.wdl                  # 普通版
│   └── metage_v2.88.2_dehost.wdl           # 去宿主版
├── inputs/
│   ├── inputs.node1.full.json
│   ├── inputs.node1.full.kraken2.json
│   ├── inputs.node1.reuse.json
│   └── inputs.node1.incremental.json
├── input_files/
│   ├── README_input_files.md
│   ├── full/data/                          # full 所需的三类文件
│   ├── reuse/data/                         # reuse 所需的三类文件
│   └── incremental/
│       ├── baseline_data/                  # 增量测试前的12样本full基线
│       ├── data/                           # 增量后的完整项目，三类文件
│       └── incremental_data/               # 仅新增样本，三类文件
├── docs/
│   ├── metage_v2.88.2_WDL参数说明.xlsx
│   └── metage_v2.88.2_参数说明.txt
├── options.json                            # 仅本地 Cromwell 需要
├── prepare_full_rawdata.sh                 # 为incremental基线生成12样本FASTQ视图
├── verify_node1_image.sh
├── VERSION
├── MANIFEST.sha256
└── README_node1_test.md
```

## node1 运行前检查

进入测试包根目录后先执行。`MANIFEST.sha256` 中的路径相对于测试包根目录：

```bash
sha256sum -c MANIFEST.sha256
bash verify_node1_image.sh
```

然后确认 node1 能读取宏基因组数据库和测试 FASTQ。数据库不在本包内：

```bash
test -d /public/nfs_data/public_file_data/metagenome-DB/database
```

## 平台需要上传什么

平台工作流页面只需要上传：

1. 普通流程上传 `workflow/metage_v2.88.2.wdl`；去宿主流程上传
   `workflow/metage_v2.88.2_dehost.wdl`
2. 对应运行模式的 `inputs/inputs.node1.*.json`，或在平台参数界面填写同样参数

`options.json` 仅用于命令行 Cromwell，不需要上传到普通平台参数界面。Python/R
脚本和报告模板已经在镜像中，也不需要单独上传。

项目输入文件必须提前放到 node1 与计算节点均可见的共享路径，而不是作为 WDL
附件上传。按运行模式整理好的模板位于 `input_files/`，实际目录应为：

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

必须修改模板中的项目身份、报告编号、样本名、分组和 FASTQ 前缀。FASTQ 文件名
必须与 `data.xlsx` 的 `fastqfile` 一致。

## full 测试

使用 `inputs/inputs.node1.full.json`，将 `<PROJECT_DIR>` 替换为实际项目目录名。
`parent_workflow_dir` 不传。建议首次测试保持：

```text
binning=no
use_kraken2=no
物种 Beta 默认输出四种距离，无需 do_unifrac 或外部树路径。
```

需要同时验证 Kraken2 时，改用 `inputs/inputs.node1.full.kraken2.json`，并把
`kraken2_db` 的占位值替换成 node1 和计算容器均可读取的真实绝对路径。普通 full
模板默认不启用 Kraken2。

当前工作区已有 12 样本、24 个双端 FASTQ，可与
`input_files/incremental/baseline_data/` 配套做一个独立的 12 样本 full 基线测试：

```text
/home/xydeng/Metagenomics_Docker/SNDF042726061801_testdata/testdata
```

不要把该 12 样本 FASTQ 目录与包内 15 样本 `input_files/full/data/data.xlsx` 混用。

full 成功后必须保留：

```text
<PROJECT_ROOT>/data/sample_registry.tsv
```

并记录成功 workflow UUID，供 reuse/incremental 使用。

本测试模板的 full `data.xlsx` 已改为 15 个样本，包含 `RCK_new_1`～
`RCK_new_3`，可直接使用包含 30 个 FASTQ 的原始 `testdata` 目录作为
`rawdatapath`，不再需要创建 12 样本视图。

## reuse 测试

使用 `inputs/inputs.node1.reuse.json`：

- `<PARENT_WORKFLOW_UUID>` 只填写成功父流程 UUID，不填写完整路径。
- 删除、改名、改组只修改 `<PROJECT_ROOT>/data/data.xlsx`。
- 改名只修改 `sample`；稳定 ID `fastqfile` 不变。
- 修改后同步检查 comparison 工作表。
- reuse 不会重跑新增样本上游；有新增样本必须使用 incremental。

## incremental 测试

15 样本 full 已经包含 `RCK_new_1`～`RCK_new_3`，不能再把这三个样本作为其
incremental 新增样本。如果需要单独验证 incremental，必须建立另一个 12 样本
基线项目。测试包内提供了一个混合变化示例：增加 3 个样本、删除 RS2、
将 RS1 改名为 RS1_rename，并把 RS3 改到 RCK 组。

操作时：

1. 先将 `input_files/incremental/baseline_data/` 复制到该测试项目的 `data/`。
2. 使用包内脚本从 15 样本 FASTQ 目录生成 12 样本视图，并以该视图完成 full：

   ```bash
   bash prepare_full_rawdata.sh \
     /cephfs_data/genostack_v3/genostack_php/project_data/21499/SNDF042726061801_testdata/testdata \
     <INCREMENTAL_TEST_PROJECT_ROOT>/rawdata_baseline
   ```

3. 将 `input_files/incremental/data/` 中的三个文件复制到
   `<PROJECT_ROOT>/data/`，不要删除原有 `sample_registry.tsv`。
4. 将整个 `input_files/incremental/incremental_data/` 复制为
   `<PROJECT_ROOT>/incremental_data/`。
5. incremental 的 `rawdatapath` 改为原始 15 样本目录，其中必须包含
   `RCK_new_{1,2,3}_R{1,2}.fq.gz`。
6. 使用 `inputs/inputs.node1.incremental.json`，填写 12 样本基线 full 的成功 workflow UUID。

流程只对新增样本重跑上游和 tax/func/VCA/MBQ/COG/MetaCyc，随后与历史累计结果
按数据库分别合并，最后使用完整项目样本集合重新运行 tax_base、func_base、差异
分析和报告。

已有样本 FASTQ 内容发生变化时必须重新 full，不能按普通 incremental 处理。

## 路径注意事项

- `parent_workflow_dir` 只填写 UUID；WDL 会拼接平台固定 Cromwell 根目录。
- 父流程绝对路径前缀写在 WDL 源文件中，可编辑 WDL 修改，但不会显示为平台输入参数。
- `mapdir` 必须改为 node1 计算容器实际可见的数据库路径。
- `project_root`、`datapath`、`rawdatapath` 必须是所有计算节点可见的共享路径。
- 保留尖括号的 JSON 只是模板，不能直接提交。
- 数据库不在 node1 可见时，镜像验证可以通过，但正式分析 task 会失败。
