# metage v2.88.2

本目录是 `metage_megahit_no_v2.87` 的优化版源码。唯一的工作流与本地测试入口统一放在 `node1_test_bundle_v2.88.2/`，避免同一 WDL、输入模板和运行脚本出现多份副本。

## 目录结构

```text
metage_v2.88.2/
├── Dockerfile                         # v2.88.2 镜像构建配方
├── scripts/                           # 镜像内使用的完整流程脚本
├── node1_test_bundle_v2.88.2/         # 唯一的测试/运行包
│   ├── workflow/                      # 唯一 WDL：普通版与去宿主版
│   ├── inputs/                        # full/reuse/incremental/Kraken2 输入模板
│   ├── batch/                         # full、add、delete、rename、multi-change 入口
│   ├── config/                        # 本地 Cromwell 配置与 options
│   ├── docs/                          # 参数说明及 QMD 文档
│   ├── prepare_full_rawdata.sh        # 增量测试辅助工具
│   ├── verify_node1_image.sh          # 发布镜像校验工具
│   └── README.md                      # 测试包使用说明
├── 优化说明.md                         # v2.88.2 相对 v2.87 的主要改动
├── README_dehost.md                   # 去宿主版说明
└── VERSION
```

## 使用入口

进入 `node1_test_bundle_v2.88.2/batch/` 后按需要执行：

```bash
bash run_sample_full.sh
bash run_sample_full_kraken2.sh
bash run_sample_add.sh --inputs ../inputs/inputs.node1.incremental.json
bash run_sample_delete.sh SAMPLE_ID
bash run_sample_rename.sh --inputs ../inputs/inputs.node1.reuse.json
bash run_sample_multi_change.sh --inputs ../inputs/inputs.node1.incremental.json
```

`run_workflow.sh` 是上述脚本共用的底层入口，通常无需直接调用。详细测试条件、输入目录约定和 full/reuse/incremental 使用方法见 [node1_test_bundle_v2.88.2/README.md](node1_test_bundle_v2.88.2/README.md)。

## 脚本版本约定

`scripts/` 是构建镜像时完整复制到 `/root/microbiome/microbiome/metage_v2.88.2/` 的脚本集合。流程改造后的分析脚本通常以 `_update` 或明确版本后缀（例如 `_V2`）标识；WDL 仍会保留少量基础设施脚本的原名，如注册表、绘图配置和结果整理脚本。

## 镜像构建

Kraken2/Bracken 在镜像构建阶段通过 Conda 安装，Kraken2 数据库仍使用 Ceph 上的外部数据库路径；仓库不再保存其二进制环境或字体文件。
