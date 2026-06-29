#!/bin/bash
# 并行化修改说明（2026-06-17）：
# 1. 使用 GNU parallel 按样本并行运行 bowtie2 去宿主 + fastp 二次质控。
# 2. 通过 --halt soon,fail=1 实现：任意一个并行任务失败时立即终止整个流程。
# 3. 脚本使用 set -uo pipefail；关键命令通过显式判断返回码来报错，
#    最终由上层 Python 流程捕获非零退出码并终止后续步骤。
#
# bowtie2 并行策略说明：
#   本脚本采用“样本间并行 + 样本内多线程”的两层并行策略：
#   - 样本间并行：由 GNU parallel 的 -j 参数控制，同时运行 N 个样本的去宿主流程。
#   - 样本内并行：每个 bowtie2 进程通过 -p 参数使用多线程；每个 fastp 二次质控
#     通过 --thread 参数使用多线程。
#   理论峰值线程数 = parallel -j N × max(bowtie2 -p, fastp --thread)
#
#   默认配置：-j 6，bowtie2 -p 64，fastp --thread 64
#   峰值线程数 ≈ 6 × 64 = 384 线程
#   该配置适合超大内存/超多核机器；普通 Docker 环境（如 32 CPU）会严重超配，
#   可能导致性能下降甚至系统负载过高。
#
#   推荐配置（根据 Docker CPU 数调整，尽量让峰值线程数 ≤ CPU 数）：
#   - 32 CPU：parallel -j 2，bowtie2 -p 16，fastp --thread 16  → 峰值 32 线程
#   - 64 CPU：parallel -j 4，bowtie2 -p 16，fastp --thread 16  → 峰值 64 线程
#   - 96 CPU：parallel -j 4，bowtie2 -p 24，fastp --thread 24  → 峰值 96 线程
#   也可改为“高并行度 + 低单任务线程”，例如 32 CPU 时用 -j 8 + -p 4，
#   但 bowtie2/fastp 单任务线程过低时效率会下降，建议单任务至少 8~16 线程。
set -uo pipefail

if ! source ~/anaconda3/etc/profile.d/conda.sh; then
    echo "[ERROR] Failed to source conda" >&2
    exit 1
fi
if ! conda activate biobakery; then
    echo "[ERROR] Failed to activate conda env 'biobakery'" >&2
    exit 1
fi

datadir=${1}
mapdir=${2}
cleandatadir=${3}
host_dir=${4}
host_str=${5}

# 创建 qc 目录
mkdir -p ${host_dir}/qc
mkdir -p ${host_dir}/logs

# 定义处理单个样本的函数
process_sample() {
    local sample=$1
    local rc=0

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing dehost: ${sample}"

    # 1. bowtie2 去宿主
    bowtie2 -p 64 --no-unal \
        -x ${mapdir}/${host_str} \
        -1 ${cleandatadir}/${sample}_clean_1.fastq.gz \
        -2 ${cleandatadir}/${sample}_clean_2.fastq.gz \
        --un-conc-gz ${host_dir}/${sample}_de_host.fastq.gz \
        > ${host_dir}/logs/${sample}_bowtie.log 2>&1 || rc=$?

    if [ ${rc} -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: bowtie2 failed for ${sample}, see ${host_dir}/logs/${sample}_bowtie.log" >&2
        return ${rc}
    fi

    # 2. 重命名去宿主文件
    if [ -f "${host_dir}/${sample}_de_host.fastq.1.gz" ]; then
        mv ${host_dir}/${sample}_de_host.fastq.1.gz ${host_dir}/${sample}_dehost_1.fastq.gz
        mv ${host_dir}/${sample}_de_host.fastq.2.gz ${host_dir}/${sample}_dehost_2.fastq.gz
    fi

    # 3. fastp 二次质控
    fastp -Q -L -A --thread 64 \
        -i ${host_dir}/${sample}_dehost_1.fastq.gz \
        -I ${host_dir}/${sample}_dehost_2.fastq.gz \
        -o ${cleandatadir}/${sample}_rm_1.fastq.gz \
        -O ${cleandatadir}/${sample}_rm_2.fastq.gz \
        -h ${host_dir}/qc/${sample}.html \
        -j ${host_dir}/qc/${sample}.json \
        > ${host_dir}/logs/${sample}_fastp.log 2>&1 || rc=$?

    if [ ${rc} -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: fastp (dehost) failed for ${sample}, see ${host_dir}/logs/${sample}_fastp.log" >&2
        return ${rc}
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finished dehost: ${sample}"
}
export -f process_sample
export mapdir cleandatadir host_dir host_str

# 提取所有样本名（跳过表头，取第2列），每行一个样本传给 parallel
# --halt soon,fail=1：只要有一个样本失败，立即终止其余并行任务并返回非零退出码
echo "Starting parallel dehost with parallel..."
if ! awk 'NR!=1 {print $2}' "${datadir}/sample.txt" | \
    parallel -j 6 --halt soon,fail=1 --bar process_sample {}; then
    echo "[ERROR] dehost parallel processing failed. Please check logs in ${host_dir}/logs/" >&2
    exit 1
fi

# 清理中间文件
rm -f ${cleandatadir}/*clean*.fastq.gz
rm -f ${cleandatadir}/*rm*.fastq.gz

echo '------------dehost finish!------------'
