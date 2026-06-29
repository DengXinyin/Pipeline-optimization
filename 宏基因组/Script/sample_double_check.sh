#!/usr/bin/env bash
# 宏基因组样本核对与文件指纹管理 Docker 运行脚本
# 对应 Python 脚本：/scripts/sample_double_check.py
#
# 【快速概览】
#   1. 本脚本是 sample_double_check.py 的 Docker 封装，用于生产环境中执行 data-check 子命令。
#      若仅需任意目录扫描与历史对比，可直接调用 sample_double_check.py 的 scan-dir。
#   2. 通过 docker run 将本机的 rawdata、metadatadir 及各下游结果目录挂载到容器内对应路径，
#      在容器中调用 Python 脚本完成样本核对与指纹记录。
#   3. 默认以只扫描模式输出变更报告；确认无误后，执行 ./sample_double_check.sh --do-modify
#      以触发下游结果目录的实际同步。
#
# 功能：
#   1. 核对当前 sample.txt 与上次 manifest 的差异。
#   2. 检测新增、删除、重命名、内容变更样本。
#   3. 默认只扫描，仅打印报告；加 --do-modify 才会真正同步结果目录。
#   4. 维护 .sample_manifest.json，记录原始 FASTQ 文件指纹。
#
# 使用方式：
#   # 1. 先只扫描查看变更
#   ./sample_double_check.sh
#
#   # 2. 确认后执行同步
#   ./sample_double_check.sh --do-modify
#
# WDL 工作流集成说明：
#   本脚本只用于流程最开始的人工/半自动核对入口（data-check 子命令）。
#   在 WDL 的每个 task 中，应直接调用 Python 脚本的 record-stage 子命令，
#   在 command 块末尾记录该 task 的输出文件指纹。详细示例请参见：
#     /scripts/sample_double_check.py  顶部的模块文档字符串
#   关键要点：
#     - scripts_dxy/Script/ 需要挂载到容器内 /root/microbiome/microbiome/metage_megahit/
#     - metadatadir 必须对容器可写
#     - 目录输出加 --no-md5，可能缺失的文件加 --skip-missing
#     - 脚本已实现文件锁 + 原子写入，支持 WDL 多 task 并发写 manifest

set -uo pipefail

cd /home/xydeng/Metagenomics || exit 1

# 默认参数
DO_MODIFY_FLAG=""
if [[ "${1:-}" == "--do-modify" ]]; then
    DO_MODIFY_FLAG="--do-modify"
fi

# 建议用 tmux 运行：
#   tmux new -s sample_double_check
#   ./sample_double_check.sh [--do-modify]
#   # Ctrl+B D detach

sudo docker run --network=host --rm -it --cpus=8 --memory="32g" \
    -v /home/xydeng/Metagenomics/project/demo/rawdata:/rawdata \
    -v /home/xydeng/Metagenomics/metadatadir:/metadatadir \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/scripts \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_megahit \
    -v /home/xydeng/Metagenomics/cleandata:/cleandata \
    -v /home/xydeng/Metagenomics/de_host:/de_host \
    -v /home/xydeng/Metagenomics/megahit_update:/megahit_update \
    -v /home/xydeng/Metagenomics/prodigal_original:/prodigal_original \
    -v /home/xydeng/Metagenomics/Result:/Result \
    192.168.30.202:23099/metage_megahit/metage:v2.87 \
    bash -c "
        echo '==========================================' && \
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S' && \
        echo '==========================================' && \
        source /root/anaconda3/etc/profile.d/conda.sh && \
        conda activate py39 && \
        echo '=== 运行样本核对与指纹管理 ===' && \
        time python /scripts/sample_double_check.py data-check \
            -i /rawdata \
            -I /metadatadir \
            --output-dirs cleandata de_host megahit_update prodigal_original \
            ${DO_MODIFY_FLAG} && \
        echo '==========================================' && \
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S' && \
        echo '=========================================='
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/sample_double_check.log
