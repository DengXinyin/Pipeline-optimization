#!/bin/bash
# ============================================================
# Task 00: check_input_no_raw (update)
# 用法: bash run_00_check_input_no_raw_update.sh [test1|test2|test3]
# 默认: test1
# ============================================================
set -euo pipefail

TEST_RUN="${1:-test1}"
echo "=========================================="
echo "  Task 00: check_input_no_raw (update)"
echo "  批次: ${TEST_RUN}"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

cd /home/xydeng/Metagenomics

# Task 00: check_input_no_raw
# 切换批次：改 TEST_RUN 的值（test1 / test2 / test3）
#
# 运行方式：
#   cd /home/xydeng/Metagenomics
#   TEST_RUN="test1"
#   tmux new -s 00_check_input_no_raw_${TEST_RUN}
#   粘贴下面的 sudo docker run 命令
#   Ctrl+B D 退出 tmux
#

sudo docker run --network=host --rm -it --cpus=40 --memory="200g" \
    -v /home/xydeng/Metagenomics/project/demo/data:/data:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy:/scripts:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy/Output:/output \
    -v /home/xydeng/Metagenomics/project/demo/metadatadir:/metadatadir \
    dockerhub.genostack.com/sanshu/metage:v2.88.2 \
    bash -c "
        echo '==========================================' "
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S' "
        echo '==========================================' "
        echo '=== 检查输入文件 ===' "
        ls -la /data/data.xlsx "
        echo '=== 开始运行 dealdata_update.py ===' "
        time python /scripts/Script/dealdata_update.py -indir /data -outdir /output "
        echo '==========================================' "
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S' "
        echo '=========================================='
        echo '=== 记录输出文件指纹 ===' "
        python3 /scripts/Script/sample_double_check.py record-stage \
            -I /metadatadir \
            --stage check_input_no_raw \
            --key update \
            --merged \
            --no-md5 \
            --input-samples CK-1 CK-2 CK-3 T-1 T-2 T-3 \
            --files sample_txt=/output/sample.txt \
                    metadata=/output/sample-metadata.tsv "
        echo '=== 指纹记录完成 ===' "
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/00_check_input_no_raw_update_${TEST_RUN}_runtime.log

echo ""
echo "=========================================="
echo "  结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""
echo "=== 运行时间 ==="
grep "^real" /home/xydeng/Metagenomics/scripts_dxy/logs/00_check_input_no_raw_update_${TEST_RUN}_runtime.log 2>/dev/null || echo "(从上方输出查看 real 时间)"
