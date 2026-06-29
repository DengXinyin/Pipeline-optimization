#!/bin/bash
# 使用优化版代码运行 Task 10 tax_anno
# 输入：/home/xydeng/Metagenomics/prodigal_update/unique_gene.fasta
# 数据库：/data/data2/metagenome-DB/database/NR/
# 输出：/home/xydeng/Metagenomics/tax_anno_update/
# 日志：/home/xydeng/Metagenomics/scripts_dxy/logs/10_tax_anno_update_runtime.log

set -euo pipefail

cd /home/xydeng/Metagenomics

# 清空旧输出（如存在），由脚本自行创建目录
rm -rf /home/xydeng/Metagenomics/tax_anno_update

docker run --network=host --rm -it \
    --cpus=62 --memory="200g" \
    -v /home/xydeng/Metagenomics/prodigal_update:/prodigal \
    -v /data/data2/metagenome-DB:/metagenome-DB \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_megahit \
    -v /home/xydeng/Metagenomics:/workdir \
    192.168.30.202:23099/metage_megahit/metage:v2.87 \
    bash -c "
        set -euo pipefail
        echo '==========================================' && \
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S' && \
        echo '==========================================' && \
        source /root/anaconda3/etc/profile.d/conda.sh && \
        conda activate biobakery && \
        echo '=== 检查输入文件 ===' && \
        ls -la /prodigal/unique_gene.fasta && \
        ls -la /metagenome-DB/database/NR/metage2.dmnd && \
        ls -la /opt/megan7/tools/daa-meganizer && \
        ls -la /opt/megan7/tools/daa2info && \
        echo '=== 开始运行 tax_anno 优化版 ===' && \
        time python /root/microbiome/microbiome/metage_megahit/tax_ano_1_update.py \
            --prodigal /prodigal \
            --dbdir /metagenome-DB/database/NR \
            --megandir /opt/megan7/ \
            --Annotation /workdir/tax_anno_update \
            --threads 60 && \
        echo '==========================================' && \
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S' && \
        echo '=========================================='
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/10_tax_anno_update_runtime.log
