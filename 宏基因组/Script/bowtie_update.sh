#!/usr/bin/env bash
set -euo pipefail

# 优化版 bowtie 比对流程
# 优化点：
#   1. parallel -j 6 + bowtie2 -p 12 = 72 线程，避免原代码 7*12=84 线程超配
#   2. bowtie2 直接管道到 samtools sort，不写中间 .sam 文件，减少磁盘 IO 和空间占用
#   3. 移除保守的 --memfree 50G
#   4. set -euo pipefail，失败即停

datadir=${1}
cle_hodir=${2}
prodigal_dir=${3}
bowtie_dir=${4}
type=${5}

# 清空输出目录内容（保留挂载点）
rm -rf "${bowtie_dir}"/*

# 生成样本列表
awk 'NR!=1 {print}' "${datadir}/sample.txt" | while read id; do
  sample=$(echo "${id}" | awk '{print $2}' | tr -d '\n\r')
  if [ "${type}" = 'none' ]; then
    echo "${cle_hodir}/${sample}_clean_1.fastq.gz" >> "${bowtie_dir}/sample1.txt"
    echo "${cle_hodir}/${sample}_clean_2.fastq.gz" >> "${bowtie_dir}/sample2.txt"
  else
    echo "${cle_hodir}/${sample}_dehost_1.fastq.gz" >> "${bowtie_dir}/sample1.txt"
    echo "${cle_hodir}/${sample}_dehost_2.fastq.gz" >> "${bowtie_dir}/sample2.txt"
  fi
  echo "${bowtie_dir}/${sample}" >> "${bowtie_dir}/sample.name.txt"
done

# 构建索引
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始 bowtie2-build..."
bowtie2-build --threads 72 -f "${prodigal_dir}/unique_gene.fasta" "${bowtie_dir}/uniq"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] bowtie2-build 完成"

# 比对并直接排序为 BAM（不写 SAM 中间文件）
# 6 个样本并行 * 12 线程 = 72 线程
export BOWTIE2_INDEX="${bowtie_dir}/uniq"

run_align() {
    local prefix=$1
    local r1=$2
    local r2=$3
    bowtie2 -p 12 -x "${BOWTIE2_INDEX}" -1 "${r1}" -2 "${r2}" | \
        samtools sort -@12 -o "${prefix}.sort.bam" - && \
        samtools index "${prefix}.sort.bam" && \
        samtools idxstats "${prefix}.sort.bam" > "${prefix}_mapped.txt" && \
        sed -i '1i GeneID\tlength\tmapped_read\tunmapped_read' "${prefix}_mapped.txt" && \
        cut -f 1-3 "${prefix}_mapped.txt" > "${prefix}_mapped_cut.txt"
}
export -f run_align

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始 bowtie2 比对..."
parallel -j 6 --xapply \
    'run_align {1} {2} {3}' \
    :::: "${bowtie_dir}/sample.name.txt" \
    :::: "${bowtie_dir}/sample1.txt" \
    :::: "${bowtie_dir}/sample2.txt"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] bowtie2 比对完成"
