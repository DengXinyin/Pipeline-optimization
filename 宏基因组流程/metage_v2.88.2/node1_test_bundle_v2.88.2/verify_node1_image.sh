#!/bin/bash
set -euo pipefail

IMAGE='dockerhub.genostack.com/sanshu/metage:v2.88.2'
EXPECTED_ID='sha256:e820fc8f28b3e06967e064d8fd8c27ad162aeac578cb911dd7ce9edec375f194'
EXPECTED_DIGEST='dockerhub.genostack.com/sanshu/metage@sha256:2bbad1518c512ffd3ad453b3078f72d9d1079d0b51362c07daad6fc272018532'

if ! sudo docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "ERROR: node1 本地不存在镜像: $IMAGE" >&2
  echo "请先由有权限的用户执行 docker pull。校验脚本不会自动拉取或改变镜像标签。" >&2
  exit 2
fi

ACTUAL_ID="$(sudo docker image inspect "$IMAGE" --format '{{.Id}}')"
ACTUAL_DIGESTS="$(sudo docker image inspect "$IMAGE" --format '{{join .RepoDigests "\n"}}')"
sudo docker image inspect "$IMAGE" \
  --format 'ID={{.Id}} Created={{.Created}} Architecture={{.Architecture}} Size={{.Size}} Digests={{json .RepoDigests}}'

if [ "$ACTUAL_ID" != "$EXPECTED_ID" ]; then
  echo "ERROR: Image ID 不匹配: expected=$EXPECTED_ID actual=$ACTUAL_ID" >&2
  exit 2
fi
if ! printf '%s\n' "$ACTUAL_DIGESTS" | grep -Fqx "$EXPECTED_DIGEST"; then
  echo "ERROR: RepoDigest 不匹配: expected=$EXPECTED_DIGEST" >&2
  exit 2
fi

sudo docker run --rm --entrypoint /bin/bash "$IMAGE" -lc '
  set -euo pipefail
  SCRIPT_DIR=/root/microbiome/microbiome/metage_v2.88.2
  PY39=/root/anaconda3/envs/py39/bin/python

  test -f "$SCRIPT_DIR/dealdata_update.py"
  test -f "$SCRIPT_DIR/merge_upstream_results.py"
  test -f "$SCRIPT_DIR/test_incremental_merge.py"
  test -f "$SCRIPT_DIR/metage_v2.88.2.docx"

  "$PY39" -c "import Bio, matplotlib, numpy, openpyxl, pandas; assert openpyxl.__version__ == \"3.1.2\"; print(\"Python dependencies: PASS; openpyxl\", openpyxl.__version__)"
  "$PY39" "$SCRIPT_DIR/test_incremental_merge.py"

  fc-match "Times New Roman"
  fc-match "Arial"
  fc-match "SimSun"
  echo "metage_v2.88.2 node1 image verification: PASS"
'
