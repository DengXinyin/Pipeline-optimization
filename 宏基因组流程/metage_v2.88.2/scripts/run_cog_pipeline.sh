#!/bin/bash
# ============================================================
# COG-24 standalone pipeline wrapper
# 用法:
#   bash run_cog_pipeline.sh \
#       --prodigal <prodigal_dir> \
#       --bowtie <bowtie_dir> \
#       --metadata <metadata_dir> \
#       --cogdb <cog_db_dir> \
#       --outdir <outdir> \
#       [--cpu 16]
#
# 会在 <outdir> 下生成:
#   cog_anno/    COG 注释结果
#   cog_stats/   COG 丰度表
#   cog_visual/  COG 可视化图表
#   cog_diff/    COG 差异分析结果
# ============================================================
set -euo pipefail

CPU=16
BLASTX="--blastx"

usage() {
    cat <<EOF
Usage: $0 --prodigal <dir> --bowtie <dir> --metadata <dir> --cogdb <dir> --outdir <dir> [--cpu <int>] [--protein]
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prodigal) PRODIGAL_DIR="$2"; shift 2 ;;
        --bowtie) BOWTIE_DIR="$2"; shift 2 ;;
        --metadata) METADATA_DIR="$2"; shift 2 ;;
        --cogdb) COGDB_DIR="$2"; shift 2 ;;
        --outdir) OUTDIR="$2"; shift 2 ;;
        --cpu) CPU="$2"; shift 2 ;;
        --protein) BLASTX=""; shift ;;
        *) echo "未知参数: $1"; usage ;;
    esac
done

for v in PRODIGAL_DIR BOWTIE_DIR METADATA_DIR COGDB_DIR OUTDIR; do
    if [[ -z "${!v:-}" ]]; then
        echo "错误: 缺少 $v"
        usage
    fi
    # 转为绝对路径，docker -v 需要
    eval "$v=$(cd "$(dirname "${!v}")" && pwd)/$(basename "${!v}")"
done

mkdir -p "${OUTDIR}"

COG_ANNO="${OUTDIR}/cog_anno"
COG_STATS="${OUTDIR}/cog_stats"
COG_VISUAL="${OUTDIR}/cog_visual"
COG_DIFF="${OUTDIR}/cog_diff"

IMAGE="dockerhub.genostack.com/sanshu/metage:v2.88.2"
SCRIPT_MOUNT="/root/microbiome/microbiome/metage_v2.88.2"
# wrapper 所在目录即 scripts 目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "COG-24 standalone pipeline"
echo "=========================================="
echo "prodigal : ${PRODIGAL_DIR}"
echo "bowtie   : ${BOWTIE_DIR}"
echo "metadata : ${METADATA_DIR}"
echo "cogdb    : ${COGDB_DIR}"
echo "outdir   : ${OUTDIR}"
echo "cpu      : ${CPU}"
echo "=========================================="

# 1. COG annotation
echo "[Step 1/4] COG annotation ..."
docker run --rm \
    -v "${PRODIGAL_DIR}":/prodigal:ro \
    -v "${COGDB_DIR}":/COG:ro \
    -v "${SCRIPT_DIR}":"${SCRIPT_MOUNT}":ro \
    -v "${COG_ANNO}":/out:rw \
    "${IMAGE}" bash -c "
        source /root/anaconda3/etc/profile.d/conda.sh
        conda activate biobakery
        python ${SCRIPT_MOUNT}/cog_anno_update.py \
            --prodigal /prodigal --dbdir /COG --outdir /out \
            --cpu ${CPU} ${BLASTX}
    "

# 2. COG stats
echo "[Step 2/4] COG abundance statistics ..."
docker run --rm \
    -v "${COG_ANNO}":/cog_anno:ro \
    -v "${BOWTIE_DIR}":/bowtie:ro \
    -v "${METADATA_DIR}":/metadata:ro \
    -v "${SCRIPT_DIR}":"${SCRIPT_MOUNT}":ro \
    -v "${COG_STATS}":/out:rw \
    "${IMAGE}" bash -c "
        source /root/anaconda3/etc/profile.d/conda.sh
        conda activate py39
        python ${SCRIPT_MOUNT}/cog_stats_update.py \
            --cog_anno /cog_anno --bowtie /bowtie -I /metadata --outdir /out
    "

# 3. COG visualization
echo "[Step 3/4] COG visualization ..."
docker run --rm \
    -v "${COG_STATS}":/cog_stats:ro \
    -v "${SCRIPT_DIR}":"${SCRIPT_MOUNT}":ro \
    -v "${COG_VISUAL}":/out:rw \
    "${IMAGE}" bash -c "
        source /root/anaconda3/etc/profile.d/conda.sh
        conda activate r
        Rscript ${SCRIPT_MOUNT}/cog_visual_update.R /cog_stats /out
    "

# 4. COG differential analysis
echo "[Step 4/4] COG differential analysis ..."
docker run --rm \
    -v "${COG_STATS}":/cog_stats:ro \
    -v "${METADATA_DIR}":/metadata:ro \
    -v "${SCRIPT_DIR}":"${SCRIPT_MOUNT}":ro \
    -v "${COG_DIFF}":/out:rw \
    "${IMAGE}" bash -c "
        source /root/anaconda3/etc/profile.d/conda.sh
        conda activate py39
        python ${SCRIPT_MOUNT}/cog_diff_update.py \
            -I /metadata --cog_stats /cog_stats --outdir /out
    "

echo "=========================================="
echo "COG pipeline completed"
echo "输出目录: ${OUTDIR}"
echo "=========================================="
