#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' 'This legacy standalone runner is disabled. Use the top-level WDL launchers in ../.' >&2
printf '%s\n' "The original script is preserved as $0.legacy." >&2
exit 2
