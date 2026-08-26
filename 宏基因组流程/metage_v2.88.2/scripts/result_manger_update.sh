#!/bin/bash
set -euo pipefail

src="${1:?Usage: $0 <source_result_dir> [output_dir]}"
out="${2:-./Result}"

if [[ ! -d "$src" ]]; then
    echo "[ERROR] Source directory not found: $src" >&2
    exit 1
fi

# Prevent output from being inside source, which would cause infinite recursion
src_abs="$(cd "$src" && pwd)"
out_abs="$(cd "$(dirname "$out")" && pwd)/$(basename "$out")"
if [[ "$out_abs" == "$src_abs" || "$out_abs" == "$src_abs/"* ]]; then
    echo "[ERROR] Output directory cannot be the same as or inside source directory" >&2
    exit 1
fi

# Clean up stale intermediate directories from previous failed runs
rm -rf "$out.tmp" "$out.old"

echo "[INFO] Copying $src -> $out.tmp"
cp -r "$src" "$out.tmp"

echo "[INFO] Cleaning HTML dependency directories"
find "$out.tmp" -type d -name "*_files" -print0 | xargs -0 -I {} rm -rf {}

echo "[INFO] Cleaning HTML files except krona.html"
find "$out.tmp" -type f -name "*.html" ! -name "krona.html" -print0 | xargs -0 -I {} rm -f {}

# Atomically replace the output directory:
# 1. Move existing output out of the way (if any)
# 2. Move the cleaned temp directory to the final location
# 3. Remove the old output
if [[ -e "$out" ]]; then
    mv "$out" "$out.old"
fi
mv "$out.tmp" "$out"

# Clean up the old output directory. If it contains files owned by root
# (e.g. created inside Docker) and this script is run as a normal user,
# the cleanup may fail with permission errors. The new output is already
# in place, so we just warn and let the user remove it with sudo/Docker.
rm -rf "$out.old" 2>/dev/null || true
if [[ -e "$out.old" ]]; then
    echo "[WARN] Could not remove old output directory: $out.old" >&2
    echo "[WARN] It may contain root-owned files from Docker runs." >&2
    echo "[WARN] Remove it manually with: sudo rm -rf $out.old" >&2
fi

echo "[INFO] Result prepared at $out"
