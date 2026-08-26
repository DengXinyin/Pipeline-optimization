#!/bin/bash
# ============================================================
# Task 19: coll_res_ana (update)
# 用法: bash run_19_coll_res_ana_update.sh [test1|test2|test3] [full|key|none]
# 默认: test1 none（与原流程一致，不插入结果图）
# image-mode: full=插入全部结果图；key=只插入关键图；none=不插入结果图
# ============================================================
set -euo pipefail

TEST_RUN="${1:-test1}"
# 优化版本报告默认按原流程样式生成：不插入结果图
IMAGE_MODE="${2:-${IMAGE_MODE:-none}}"
echo "=========================================="
echo "  Task 19: coll_res_ana (update)"
echo "  批次: ${TEST_RUN}"
echo "  图片模式: ${IMAGE_MODE}"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

cd /home/xydeng/Metagenomics

# Task 19: coll_res_ana
# 切换批次：改 TEST_RUN 的值（test1 / test2 / test3）
#
# 运行方式：
#   cd /home/xydeng/Metagenomics
#   TEST_RUN="test1"
#   tmux new -s 19_coll_res_ana_${TEST_RUN}
#   粘贴下面的 sudo docker run 命令
#   Ctrl+B D 退出 tmux
#

sudo docker run --network=host --rm -it --cpus=24 --memory="128g" \
    -v /home/xydeng/Metagenomics/metadatadir:/metadatadir:ro \
    -v /home/xydeng/Metagenomics/scripts:/scripts:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_v2.88.2:ro \
    -e METAGE_SCRIPTS_PATH=/scripts \
    -v /home/xydeng/Metagenomics:/home/xydeng/Metagenomics \
    -e TEST_RUN=${TEST_RUN} \
    -e IMAGE_MODE=${IMAGE_MODE} \
    dockerhub.genostack.com/sanshu/metage:v2.88.2 \
    bash -c "
        set -euo pipefail
        echo '=========================================='
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S'
        echo '=========================================='
        source /root/anaconda3/etc/profile.d/conda.sh
        conda activate py39
        cd /home/xydeng/Metagenomics
        # 清理旧的 Result/，避免 collect_res 递归复制自身时 FileExistsError
        rm -rf /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update/Result
        time python /root/microbiome/microbiome/metage_v2.88.2/collect_res_update.py \
            --res1 /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update \
            --res2 /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update \
            --res3 /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update \
            --res4 /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update \
            --res5 /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update \
            --readme /scripts \
            --outdir /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update
        time python /root/microbiome/microbiome/metage_v2.88.2/pdf2png_update.py \
            -resDir /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update/Result -j 8
        time python /root/microbiome/microbiome/metage_v2.88.2/get_report_update.py \
            -I /metadatadir --res_dir /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update/Result \
            --micro_docx_path /scripts --analyse yes --binning no --image-mode \${IMAGE_MODE}
        time python /root/microbiome/microbiome/metage_v2.88.2/get_groups_update.py \
            -I /metadatadir --res /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update/Result
        time python /root/microbiome/microbiome/metage_v2.88.2/xlsx_trans_update.py \
            --res /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update/Result -j 8
        echo '=========================================='
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S'
        echo '=========================================='
        echo '=== 记录输出文件指纹 ==='
        python3 /home/xydeng/Metagenomics/scripts_dxy/Script/sample_double_check.py record-stage \
            -I /home/xydeng/Metagenomics/project/demo/metadatadir \
            --stage coll_res_ana \
            --key update \
            --merged \
            --no-md5 \
            --input-samples CK-1 CK-2 CK-3 T-1 T-2 T-3 \
            --files Result=/home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/update
        echo '=== 指纹记录完成 ==='
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/19_coll_res_ana_update_${TEST_RUN}_runtime.log

echo ""
echo "=========================================="
echo "  结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""
echo "=== 运行时间 ==="
grep "^real" /home/xydeng/Metagenomics/scripts_dxy/logs/19_coll_res_ana_update_${TEST_RUN}_runtime.log 2>/dev/null || echo "(从上方输出查看 real 时间)"
