#!/bin/bash
# Task 15: tax_base (update) — 4个统计脚本串行
# 用法: bash run_15_tax_base_update.sh [test1|test2|test3]
set -euo pipefail
TEST_RUN="${1:-test1}"
echo "=== Task 15: tax_base (update) — 批次: ${TEST_RUN} ==="
cd /home/xydeng/Metagenomics
sudo docker run --network=host --rm --cpus=24 --memory="320g" \
    -v /home/xydeng/Metagenomics/metadatadir:/metadatadir:ro \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/03_megahit_no/update:/megahit \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/08_prodig_no/update:/prodigal \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/09_bwa_no/update:/bowtie \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/12_anno/update/Annotation:/Annotation \
    -v /home/xydeng/Metagenomics/scripts:/scripts:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_v2.88.2:ro \
    -e METAGE_SCRIPTS_PATH=/scripts \
    -v /home/xydeng/Metagenomics:/home/xydeng/Metagenomics \
    -e TEST_RUN=${TEST_RUN} \
    dockerhub.genostack.com/sanshu/metage:v2.88.2 \
    bash -c "
        set -euo pipefail
        echo '=========================================='
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S'
        echo '=========================================='
        source /root/anaconda3/etc/profile.d/conda.sh
        conda activate py39
        time python /root/microbiome/microbiome/metage_v2.88.2/megahit_statistics_update.py \
            -I /metadatadir --megahit /megahit --resdir /home/xydeng/Metagenomics/results_\${TEST_RUN}/15_tax_base/update
        time python /root/microbiome/microbiome/metage_v2.88.2/prodigal_stats_update.py \
            -I /metadatadir --prodigal /prodigal --resdir /home/xydeng/Metagenomics/results_\${TEST_RUN}/15_tax_base/update
        time python /root/microbiome/microbiome/metage_v2.88.2/bwa_stats_update.py \
            -I /metadatadir --bowtie /bowtie --resdir /home/xydeng/Metagenomics/results_\${TEST_RUN}/15_tax_base/update
        time python /root/microbiome/microbiome/metage_v2.88.2/tax_stats_update.py \
            -I /metadatadir --Annotation /Annotation --resdir /home/xydeng/Metagenomics/results_\${TEST_RUN}/15_tax_base/update
        echo '=========================================='
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S'
        echo '=========================================='
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/15_tax_base_update_${TEST_RUN}_runtime.log
grep "^real" /home/xydeng/Metagenomics/scripts_dxy/logs/15_tax_base_update_${TEST_RUN}_runtime.log 2>/dev/null
