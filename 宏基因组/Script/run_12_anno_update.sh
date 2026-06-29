#!/bin/bash
set -euo pipefail

echo '=========================================='
echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S'
echo '=========================================='

source /root/anaconda3/etc/profile.d/conda.sh
conda activate biobakery

echo '=== 检查输入文件 ==='
ls -la /home/xydeng/Metagenomics/bowtie_original
ls -la /home/xydeng/Metagenomics/tax_anno_original
ls -la /home/xydeng/Metagenomics/func_anno_original
ls -la /metagenome-DB/database/NR

echo '=== 开始运行 anno 优化版 ==='
mkdir -p /home/xydeng/Metagenomics/anno_update
cd /home/xydeng/Metagenomics/anno_update

time python /root/microbiome/microbiome/metage_megahit/tax_ano_2_update.py \
    --tax_anno /home/xydeng/Metagenomics/tax_anno_original \
    --dbdir /metagenome-DB/database/NR \
    --bowtie /home/xydeng/Metagenomics/bowtie_original \
    --Annotation /home/xydeng/Metagenomics/anno_update

time python /root/microbiome/microbiome/metage_megahit/func_ano_2_update.py \
    --fun_anno /home/xydeng/Metagenomics/func_anno_original \
    --dbdir /metagenome-DB/database \
    --mapdir /metagenome-DB \
    --bowtie /home/xydeng/Metagenomics/bowtie_original \
    --Annotation /home/xydeng/Metagenomics/anno_update

echo '=========================================='
echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S'
echo '=========================================='
