#!/bin/bash
# Task 08: prodig_no (update)
# 用法: bash run_08_prodig_no_update.sh [test1|test2]
set -euo pipefail
TEST_RUN="${1:-test1}"
echo "=== Task 08: prodig_no (update) — 批次: ${TEST_RUN} ==="
cd /home/xydeng/Metagenomics
sudo docker run --network=host --rm --cpus=72 --memory="640g" \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/03_megahit_no/update_V2:/megahit:ro \
    -v /home/xydeng/Metagenomics/scripts:/scripts:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_v2.88.2:ro \
    -v /home/xydeng/Metagenomics/project/demo/metadatadir:/metadatadir:ro \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/08_prodig_no/update:/prodigal \
    -e METAGE_SCRIPTS_PATH=/scripts \
    -e TEST_RUN=${TEST_RUN} \
    dockerhub.genostack.com/sanshu/metage:v2.88.2 \
    bash -c "
        echo '==========================================' "
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S' "
        echo '==========================================' "
        source /root/anaconda3/etc/profile.d/conda.sh "
        conda activate megahit "
        echo '=== 检查输入文件 ===' "
        ls -la /megahit/sample.name.txt "
        ls -la /megahit/*/final.contigs.fa "
        echo '=== prodigal_update ===' "
        time python /root/microbiome/microbiome/metage_v2.88.2/prodigal_update.py \
            --megahit /megahit --prodigal /prodigal \
            --cdhitdir /app/cd-hit-v4.8.1-2019-0228 --threads 60 --chunk-size-mb 200 "
        echo '=== 记录输出文件指纹 ===' "
        python3 /root/microbiome/microbiome/metage_v2.88.2/sample_double_check.py record-stage \
            -I /metadatadir --stage prodig_no --key update --merged --no-md5 \
            --input-samples CK-1 CK-2 CK-3 T-1 T-2 T-3 \
            --files all_fa=/prodigal/all.fa unique_gene=/prodigal/unique_gene.fasta "
        echo '==========================================' "
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S' "
        echo '=========================================='
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/08_prodig_no_update_${TEST_RUN}_runtime.log
grep "^real" /home/xydeng/Metagenomics/scripts_dxy/logs/08_prodig_no_update_${TEST_RUN}_runtime.log 2>/dev/null
