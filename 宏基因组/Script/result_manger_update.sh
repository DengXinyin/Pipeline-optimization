#!/bin/bash
set -euo pipefail

src="${1:?Usage: $0 <source_result_dir> [output_dir]}"
out="${2:-./Result}"

if [[ ! -d "$src" ]]; then
    echo "[ERROR] Source directory not found: $src" >&2
    exit 1
fi

echo "[INFO] Copying $src -> $out"
rm -rf "$out.tmp"
cp -r "$src" "$out.tmp"

echo "[INFO] Cleaning HTML dependency directories"
find "$out.tmp" -type d -name "*_files" -print0 | xargs -0 -I {} rm -rf {}

echo "[INFO] Cleaning HTML files except krona.html"
find "$out.tmp" -type f -name "*.html" ! -name "krona.html" -print0 | xargs -0 -I {} rm -f {}

mv "$out.tmp" "$out"
echo "[INFO] Result prepared at $out"
