#!/bin/bash
# ============================================================
# Task 10: tax_anno (update — 默认版本，当前映射到 V2 实现)
# 用法: bash run_10_tax_anno_update.sh [test1|test2|test3]
# 默认: test1
# ============================================================
# 说明：
#   本脚本为 tax_anno 优化版的默认入口。
#   当前默认实现为 V2：DIAMOND v2.1.8 --fast + --block-size 8，
#   配合 daa-meganizer + daa2info 输出 Tax_id.tmp.txt。
#   如需回退到 V1，请使用 run_10_tax_anno_update_V1.sh。
# ============================================================
set -euo pipefail

TEST_RUN="${1:-test1}"
echo "=========================================="
echo "  Task 10: tax_anno (update / 默认 V2)"
echo "  批次: ${TEST_RUN}"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

cd /home/xydeng/Metagenomics

# 默认输出目录（不带 V1/V2 后缀）
OUT_DIR="/home/xydeng/Metagenomics/results_${TEST_RUN}/10_tax_anno/update"
LOG_FILE="/home/xydeng/Metagenomics/scripts_dxy/logs/10_tax_anno_update_${TEST_RUN}_runtime.log"

# 若旧输出目录存在，则重命名备份，避免覆盖历史结果
if [[ -e "$OUT_DIR" ]]; then
    BACKUP_DIR="${OUT_DIR}.bak"
    echo "[INFO] 发现旧输出目录，备份为: $BACKUP_DIR"
    if [[ -w "$(dirname "$OUT_DIR")" ]]; then
        mv "$OUT_DIR" "$BACKUP_DIR"
    else
        echo "[INFO] 旧目录为 root 所有，尝试使用 sudo 备份..."
        sudo mv "$OUT_DIR" "$BACKUP_DIR"
    fi
fi

# 运行方式：
#   cd /home/xydeng/Metagenomics
#   tmux new -s 10_tax_anno_${TEST_RUN}
#   bash /home/xydeng/Metagenomics/scripts_dxy/Script/run_10_tax_anno_update.sh [test1|test2|test3]
#   Ctrl+B D 退出 tmux

sudo docker run --network=host --rm -it --cpus=62 --memory="200g" \
    -v /home/xydeng/Metagenomics/results_${TEST_RUN}/08_prodig_no/update:/prodigal:ro \
    -v /data/data2/metagenome-DB:/metagenome-DB:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_v2.88.2:ro \
    -v /home/xydeng/Metagenomics:/workdir \
    -v /home/xydeng/Metagenomics/project/demo/metadatadir:/metadatadir \
    -e TEST_RUN=${TEST_RUN} \
    dockerhub.genostack.com/sanshu/metage:v2.88.2 \
    bash -c "
        echo '==========================================' 
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S' 
        echo '==========================================' 
        source /root/anaconda3/etc/profile.d/conda.sh 
        conda activate biobakery 
        echo '=== 检查输入文件 ===' 
        ls -la /prodigal/unique_gene.fasta 
        ls -la /metagenome-DB/database/NR/metage2.dmnd 
        ls -la /opt/megan7/tools/daa-meganizer 
        ls -la /opt/megan7/tools/daa2info 
        echo '=== 开始运行 tax_anno 默认版本（V2: --fast, --block-size 8）===' 
        time python /root/microbiome/microbiome/metage_v2.88.2/tax_ano_1_update_V2.py \
            --prodigal /prodigal \
            --dbdir /metagenome-DB/database/NR \
            --megandir /opt/megan7/ \
            --Annotation /workdir/results_\${TEST_RUN}/10_tax_anno/update \
            --threads 60 \
            --block-size 8 
        echo '==========================================' 
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S' 
        echo '=========================================='
        echo '=== 记录输出文件指纹 ===' 
        python3 /root/microbiome/microbiome/metage_v2.88.2/sample_double_check.py record-stage \
            -I /metadatadir \
            --stage tax_anno \
            --key update \
            --merged \
            --no-md5 \
            --input-samples CK-1 CK-2 CK-3 T-1 T-2 T-3 \
            --files taxid=/workdir/results_\${TEST_RUN}/10_tax_anno/update/Tax_id.tmp.txt \
                    daa=/workdir/results_\${TEST_RUN}/10_tax_anno/update/unique.daa 
        echo '=== 指纹记录完成 ===' 
    " 2>&1 | tee "$LOG_FILE"

echo ""
echo "=========================================="
echo "  结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""
echo "=== 运行时间 ==="
grep "^real" "$LOG_FILE" 2>/dev/null || echo "(从上方输出查看 real 时间)"
