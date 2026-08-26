#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUTS_FILE="${PROJECT_DIR}/inputs_isbwa_yes_kraken2.json"
KRAKEN2_DB="/cephfs_data/genostack_v3/genostack_php/public_file_data/metagenome-DB/kraken2/minikraken2_v2_8GB_201904_UPDATE"

RUN_ARGS=()
for arg in "$@"; do
    case "${arg}" in
        --clean) RUN_ARGS+=("${arg}") ;;
        *)
            echo "Usage: sudo bash $0 [--clean]" >&2
            echo "Kraken2 输入配置已固定，不接受其他参数: ${arg}" >&2
            exit 2
            ;;
    esac
done

for required_file in hash.k2d opts.k2d taxo.k2d; do
    if [ ! -s "${KRAKEN2_DB}/${required_file}" ]; then
        echo "[Kraken2数据库错误] 缺少或为空: ${KRAKEN2_DB}/${required_file}" >&2
        exit 2
    fi
done

echo "[运行模式] full + Kraken2/Bracken"
echo "[Kraken2数据库] ${KRAKEN2_DB}"
exec bash "${PROJECT_DIR}/run_workflow.sh" full \
    --inputs "${INPUTS_FILE}" "${RUN_ARGS[@]}"
