#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "${PROJECT_DIR}/run_workflow.sh" auto "$@"
