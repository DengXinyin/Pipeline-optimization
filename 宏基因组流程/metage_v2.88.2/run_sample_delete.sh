#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUTS_NAME="examples/inputs.reuse.example.json"
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
    *) INPUTS_FILE="${PROJECT_DIR}/${INPUTS_NAME}" ;;
esac
python3 "${PROJECT_DIR}/scripts/edit_sample_sheet.py" \
    --inputs "$INPUTS_FILE" --delete "${DELETE_IDS[@]}"
exec bash "${PROJECT_DIR}/run_workflow.sh" delete --inputs "$INPUTS_FILE"
