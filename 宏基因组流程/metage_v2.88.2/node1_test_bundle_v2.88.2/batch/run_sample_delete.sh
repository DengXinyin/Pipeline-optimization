#!/bin/bash
set -euo pipefail

BATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$(cd "${BATCH_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BUNDLE_DIR}/../.." && pwd)"
INPUTS_NAME="inputs/inputs.node1.reuse.json"
DELETE_IDS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --inputs)
            [ "$#" -ge 2 ] || { echo "--inputs 缺少文件路径" >&2; exit 2; }
            INPUTS_NAME="$2"
            shift 2
            ;;
        --inputs=*)
            INPUTS_NAME="${1#*=}"
            shift
            ;;
        *)
            DELETE_IDS+=("$1")
            shift
            ;;
    esac
done
[ "${#DELETE_IDS[@]}" -gt 0 ] || {
    echo "Usage: bash $0 <internal_id> [internal_id ...] [--inputs FILE]" >&2
    exit 2
}
case "$INPUTS_NAME" in
    /*) INPUTS_FILE="$INPUTS_NAME" ;;
    *) INPUTS_FILE="${BUNDLE_DIR}/${INPUTS_NAME}" ;;
esac
python3 "${PROJECT_DIR}/scripts/edit_sample_sheet.py" \
    --inputs "$INPUTS_FILE" --delete "${DELETE_IDS[@]}"
exec bash "${BATCH_DIR}/run_workflow.sh" delete --inputs "$INPUTS_FILE"
