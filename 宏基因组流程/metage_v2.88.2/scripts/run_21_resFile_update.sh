#!/bin/bash
# ============================================================
# Task 21: resFile (update)
# 用法: bash run_21_resFile_update.sh [test1|test2|test3]
# 默认: test1
# ============================================================
set -euo pipefail

TEST_RUN="${1:-test1}"
echo "=========================================="
echo "  Task 21: resFile (update)"
echo "  批次: ${TEST_RUN}"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

cd /home/xydeng/Metagenomics

# 在宿主机先确定源目录，避免在 docker 命令字符串里做复杂引号判断
if [ -d "/home/xydeng/Metagenomics/results_${TEST_RUN}/19_coll_res/update/Result" ]; then
    SRC="/home/xydeng/Metagenomics/results_${TEST_RUN}/19_coll_res/update/Result"
else
    SRC="/home/xydeng/Metagenomics/results_${TEST_RUN}/19_coll_res/update"
fi

# Task 21: resFile
# 切换批次：改 TEST_RUN 的值（test1 / test2 / test3）
#
# 运行方式：
#   cd /home/xydeng/Metagenomics
#   TEST_RUN="test1"
#   tmux new -s 21_resFile_${TEST_RUN}
#   粘贴下面的 sudo docker run 命令
#   Ctrl+B D 退出 tmux
#

sudo docker run --network=host --rm -it --cpus=24 --memory="128g" \
    -v /home/xydeng/Metagenomics/scripts:/scripts:ro \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_v2.88.2:ro \
    -e METAGE_SCRIPTS_PATH=/scripts \
    -v /home/xydeng/Metagenomics:/home/xydeng/Metagenomics \
    -w /home/xydeng/Metagenomics \
    -e TEST_RUN=${TEST_RUN} \
    -e SRC=${SRC} \
    dockerhub.genostack.com/sanshu/metage:v2.88.2 \
    bash -c "
        set -euo pipefail
        echo '=========================================='
        echo '开始时间: ' && date '+%Y-%m-%d %H:%M:%S'
        echo '=========================================='
        echo '=== 检查输入文件 ==='
        ls -la \"\${SRC}\"
        echo '=== 开始运行 resFile 优化版 ==='
        echo \"[INFO] Source: \${SRC}\"
        time bash /root/microbiome/microbiome/metage_v2.88.2/result_manger_update.sh \
            \"\${SRC}\" \
            /home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/cleaned
        echo '=========================================='
        echo '结束时间: ' && date '+%Y-%m-%d %H:%M:%S'
        echo '=========================================='
        echo '=== 记录输出文件指纹 ==='
        python3 /home/xydeng/Metagenomics/scripts_dxy/Script/sample_double_check.py record-stage \
            -I /home/xydeng/Metagenomics/project/demo/metadatadir \
            --stage resFile \
            --key update \
            --merged \
            --no-md5 \
            --input-samples CK-1 CK-2 CK-3 T-1 T-2 T-3 \
            --files cleaned=/home/xydeng/Metagenomics/results_\${TEST_RUN}/19_coll_res/cleaned
        echo '=== 指纹记录完成 ==='
    " 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/21_resFile_update_${TEST_RUN}_runtime.log

echo ""
echo "=========================================="
echo "  结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""
echo "=== 运行时间 ==="
grep "^real" /home/xydeng/Metagenomics/scripts_dxy/logs/21_resFile_update_${TEST_RUN}_runtime.log 2>/dev/null || echo "(从上方输出查看 real 时间)"
