#!/bin/bash
set -euo pipefail

# 内部统一运行器；用户通常只需调用 run_sample_*.sh。
usage() {
    echo "Usage: bash $0 <full|add|rename|delete|auto> [--inputs FILE] [--clean]" >&2
    exit 2
}

[ "$#" -ge 1 ] || usage
REQUESTED_MODE="$1"
shift
case "${REQUESTED_MODE}" in
    full|add|rename|delete|auto) ;;
    *) usage ;;
esac

ORIGINAL_ARGS=("${REQUESTED_MODE}" "$@")
INPUTS_NAME="inputs/inputs.node1.full.json"
CLEAN_RUNS=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --inputs)
            [ "$#" -ge 2 ] || usage
            INPUTS_NAME="$2"
            shift 2
            ;;
        --inputs=*)
            INPUTS_NAME="${1#*=}"
            shift
            ;;
        --clean)
            CLEAN_RUNS=true
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            ;;
    esac
done

# Docker socket may be available through group membership, ACLs, or an
# already configured remote context. Test the daemon directly before falling
# back to sudo; group-name checks alone incorrectly reject ACL-based access.
if [ "${EUID}" -ne 0 ] && ! docker info >/dev/null 2>&1; then
    exec sudo /bin/bash "$0" "${ORIGINAL_ARGS[@]}"
fi

BATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$(cd "${BATCH_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BUNDLE_DIR}/../.." && pwd)"

# 文件型 HSQLDB 只允许一个 Cromwell 进程写入。持有此文件描述符直到
# run_workflow.sh 退出，避免重复运行脚本造成数据库锁或恢复冲突。
RUN_LOCK_FILE="${PROJECT_DIR}/.run_workflow.lock"
exec 9>"${RUN_LOCK_FILE}"
if ! flock -n 9; then
    echo "[启动失败] 当前目录已有一个 run_workflow.sh/Cromwell 正在运行。" >&2
    echo "[锁文件] ${RUN_LOCK_FILE}" >&2
    exit 3
fi

case "${INPUTS_NAME}" in
    /*) INPUTS_FILE="${INPUTS_NAME}" ;;
    *) INPUTS_FILE="${BUNDLE_DIR}/${INPUTS_NAME}" ;;
esac
[ -f "${INPUTS_FILE}" ] || { echo "Inputs file not found: ${INPUTS_FILE}" >&2; exit 2; }

# 在启动 Cromwell 前验证公共数据库。Docker 的旧式 `-v` 会在源路径
# 不存在时静默创建空目录；即使现已改用 `--mount`，这里仍检查核心
# 文件，避免已有的空目录通过路径存在性检查。
MAPDIR="$(python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    inputs = json.load(handle)
print(inputs.get(
    "metage_v2_88_2.mapdir",
    "/cephfs_data/genostack_v3/genostack_php/public_file_data/metagenome-DB",
))
' "${INPUTS_FILE}")"
if [ ! -d "${MAPDIR}" ]; then
    echo "[数据库错误] mapdir 不存在: ${MAPDIR}" >&2
    exit 2
fi
if [ ! -s "${MAPDIR}/database/GO/GO_map.txt" ]; then
    echo "[数据库错误] 缺少或为空: ${MAPDIR}/database/GO/GO_map.txt" >&2
    echo "[终止] 未启动 Cromwell；请先恢复完整 metagenome-DB。" >&2
    exit 2
fi
for taxonomy_file in nodes.dmp names.dmp merged.dmp; do
    if [ ! -s "${MAPDIR}/database/taxonomy/${taxonomy_file}" ]; then
        echo "[数据库错误] 默认物种四距离缺少: ${MAPDIR}/database/taxonomy/${taxonomy_file}" >&2
        echo "[终止] 未启动 Cromwell；请先解压 NCBI taxdump。" >&2
        exit 2
    fi
done

CROMWELL_JAR="/home/xydeng/Metagenomics_Docker/cromwell-85.jar"
JAVA_BIN="/home/software/Software/Java/v20.0.1/bin/java"
CONFIG_FILE="${BUNDLE_DIR}/config/cromwell_config.conf"
OPTIONS_FILE="${BUNDLE_DIR}/config/options.json"
WDL_FILE="${BUNDLE_DIR}/workflow/metage_v2.88.2.wdl"
WORKFLOW_ROOT="/cephfs_data/genostack_v3/genostack_cromwell/cromwell-executions/metage_v2_88_2"
REGISTRY_DIR="${WORKFLOW_ROOT}/registry"

mkdir -p "${REGISTRY_DIR}" "${PROJECT_DIR}/cromwell-db" \
    "${PROJECT_DIR}/cromwell-workflow-logs" "${PROJECT_DIR}/run-plans"

if [ "${CLEAN_RUNS}" = true ]; then
    echo "[清理] 删除当前归档目录中的旧 workflow，保留 registry"
    find "${WORKFLOW_ROOT}" -mindepth 1 -maxdepth 1 -type d ! -name registry -exec rm -rf -- {} +
fi

DATE_STR="$(date +%Y%m%d_%H%M%S)"
PLAN_DIR="${PROJECT_DIR}/run-plans/${DATE_STR}_$$"
mkdir -p "${PLAN_DIR}"
PREPARED_INPUTS="${PLAN_DIR}/inputs.json"
PLAN_JSON="${PLAN_DIR}/plan.json"
LOG_FILE="${PROJECT_DIR}/cromwell_run_${DATE_STR}.log"
META_FILE="${PROJECT_DIR}/cromwell_metadata_${DATE_STR}.json"

python3 "${PROJECT_DIR}/scripts/incremental_planner.py" \
    --mode "${REQUESTED_MODE}" \
    --inputs "${INPUTS_FILE}" \
    --project-dir "${PROJECT_DIR}" \
    --plan-dir "${PLAN_DIR}" \
    --output-inputs "${PREPARED_INPUTS}" \
    --output-plan "${PLAN_JSON}" | tee "${PLAN_DIR}/planner.log"

REGISTRY_TSV="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["registry"])' "${PLAN_JSON}")"
RUN_MODE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["run_mode"])' "${PLAN_JSON}")"
echo "[计划] requested=${REQUESTED_MODE}, run_mode=${RUN_MODE}"
echo "[计划] ${PLAN_JSON}"

ensure_docker_image() {
    local image="$1"
    if docker image inspect "${image}" >/dev/null 2>&1; then
        return
    fi
    echo "[Docker] 本地无 ${image}，开始拉取"
    docker pull "${image}"
}
ensure_docker_image "dockerhub.genostack.com/sanshu/metage:v2.88.2"

echo "[运行] WDL=${WDL_FILE}"
echo "[运行] log=${LOG_FILE}"
set +e
"${JAVA_BIN}" -XX:ActiveProcessorCount=32 -Xmx4g \
    -Dconfig.file="${CONFIG_FILE}" -jar "${CROMWELL_JAR}" run \
    -i "${PREPARED_INPUTS}" -o "${OPTIONS_FILE}" -m "${META_FILE}" "${WDL_FILE}" \
    2>&1 | tee "${LOG_FILE}"
WORKFLOW_EXIT_STATUS=${PIPESTATUS[0]}
set -e

if [ "${WORKFLOW_EXIT_STATUS}" -ne 0 ]; then
    echo "[失败] Cromwell 退出码 ${WORKFLOW_EXIT_STATUS}；registry 不会写入未完成结果" >&2
    echo "[保留] 计划和临时 inputs: ${PLAN_DIR}" >&2
    exit "${WORKFLOW_EXIT_STATUS}"
fi

WORKFLOW_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("id", ""))' "${META_FILE}")"
WORKFLOW_DIR="${WORKFLOW_ROOT}/${WORKFLOW_ID}"
if [ -n "${WORKFLOW_ID}" ] && [ -d "${WORKFLOW_DIR}" ]; then
    python3 "${PROJECT_DIR}/scripts/commit_registry.py" \
        --plan "${PLAN_JSON}" --inputs "${PREPARED_INPUTS}" \
        --workflow-dir "${WORKFLOW_DIR}" --project-dir "${PROJECT_DIR}" \
        2>&1 | tee -a "${LOG_FILE}"
else
    echo "[警告] 未找到本次 workflow 目录，registry 未更新" >&2
fi

echo "[完成] workflow_id=${WORKFLOW_ID}"
echo "[完成] registry=${REGISTRY_TSV}"
