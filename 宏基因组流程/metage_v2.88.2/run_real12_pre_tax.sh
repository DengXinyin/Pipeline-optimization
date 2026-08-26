#!/bin/bash
set -euo pipefail

# 使用 12 个真实双端样本运行 v2.88.2 的 pre-tax 阶段。
# 最后执行的组装分支任务为 bwa_no；不会调度 tax_anno、func_anno 及后续任务。

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
RAW_DIR="/home/xydeng/Metagenomics_Docker/data"
DATA_DIR="/home/xydeng/Metagenomics_Docker/Input/real12_pre_tax/data"
MAP_DIR="/cephfs_data/genostack_v3/genostack_php/public_file_data/metagenome-DB"
KRAKEN2_DB="${MAP_DIR}/kraken2/minikraken2_v2_8GB_201904_UPDATE"
SOURCE_WDL="${PROJECT_DIR}/metage_v2.88.2.wdl"
CONFIG_FILE="${PROJECT_DIR}/cromwell_config.conf"
OPTIONS_FILE="${PROJECT_DIR}/options.json"
CROMWELL_JAR="/home/xydeng/Metagenomics_Docker/cromwell-85.jar"
JAVA_BIN="/home/software/Software/Java/v20.0.1/bin/java"
WORKFLOW_ROOT="/cephfs_data/genostack_v3/genostack_cromwell/cromwell-executions/metage_v2_88_2_pre_tax"
IMAGE="dockerhub.genostack.com/sanshu/metage:v2.88.2"

usage() {
    echo "Usage: sudo bash $0 [--validate-only]" >&2
    exit 2
}

VALIDATE_ONLY=false
if [ "$#" -gt 1 ]; then
    usage
elif [ "$#" -eq 1 ]; then
    [ "$1" = "--validate-only" ] || usage
    VALIDATE_ONLY=true
fi

if [ "${EUID}" -ne 0 ] && ! id -nG "${USER}" | grep -qw docker; then
    exec sudo /bin/bash "$0" "$@"
fi

required_samples=(
    RCK1 RCK2 RCK3 RS1 RS2 RS3
    SCK1 SCK2 SCK3 SS1 SS2 SS3
)

for sample in "${required_samples[@]}"; do
    for mate in R1 R2; do
        fastq="${RAW_DIR}/${sample}_${mate}.fq.gz"
        [ -s "${fastq}" ] || {
            echo "[输入错误] FASTQ 缺少或为空: ${fastq}" >&2
            exit 2
        }
    done
done

root_fastq_count="$(find "${RAW_DIR}" -maxdepth 1 -type f -name '*.fq.gz' | wc -l)"
[ "${root_fastq_count}" -eq 24 ] || {
    echo "[输入错误] ${RAW_DIR} 根目录应有24个双端FASTQ，实际为 ${root_fastq_count}" >&2
    exit 2
}

[ -s "${DATA_DIR}/data.xlsx" ] || {
    echo "[输入错误] 缺少样本表: ${DATA_DIR}/data.xlsx" >&2
    exit 2
}
[ -s "${DATA_DIR}/project_info.json" ] || {
    echo "[输入错误] 缺少项目信息: ${DATA_DIR}/project_info.json" >&2
    exit 2
}
[ -s "${DATA_DIR}/report_no.txt" ] || {
    echo "[输入错误] 缺少报告编号: ${DATA_DIR}/report_no.txt" >&2
    exit 2
}

# 同时核对 Excel 中的12个样本、分组以及根目录24个双端 FASTQ。
python3 - "${DATA_DIR}/data.xlsx" "${RAW_DIR}" <<'PY'
import sys
from pathlib import Path
from openpyxl import load_workbook

xlsx = Path(sys.argv[1])
raw_dir = Path(sys.argv[2])
expected_groups = {
    "RCK": ["RCK1", "RCK2", "RCK3"],
    "RS": ["RS1", "RS2", "RS3"],
    "SCK": ["SCK1", "SCK2", "SCK3"],
    "SS": ["SS1", "SS2", "SS3"],
}
book = load_workbook(xlsx, read_only=True, data_only=True)
if "sample" not in book.sheetnames or "comparison" not in book.sheetnames:
    raise SystemExit("[输入错误] data.xlsx 必须包含 sample 和 comparison 工作表")
rows = list(book["sample"].iter_rows(values_only=True))
if not rows or tuple(rows[0][:3]) != ("fastqfile", "sample", "group"):
    raise SystemExit("[输入错误] sample 工作表表头必须为 fastqfile/sample/group")
observed = {}
for row in rows[1:]:
    if not row[0]:
        continue
    internal_id, display_name, group = (str(v).strip() for v in row[:3])
    if internal_id != display_name:
        raise SystemExit(f"[输入错误] 本次测试要求 fastqfile=sample，异常样本: {internal_id}/{display_name}")
    observed.setdefault(group, []).append(internal_id)
if observed != expected_groups:
    raise SystemExit(f"[输入错误] 样本或分组不符合4组×3设计: {observed}")
samples = [sample for group in expected_groups.values() for sample in group]
expected_fastqs = {f"{sample}_{mate}.fq.gz" for sample in samples for mate in ("R1", "R2")}
actual_fastqs = {path.name for path in raw_dir.glob("*.fq.gz")}
missing = sorted(expected_fastqs - actual_fastqs)
extra = sorted(actual_fastqs - expected_fastqs)
if missing or extra:
    raise SystemExit(f"[输入错误] FASTQ不匹配；缺失={missing}；多余={extra}")
print("[输入核对] data.xlsx=12样本/4组×3；FASTQ=24个双端文件：PASS")
PY

[ -s "${MAP_DIR}/database/GO/GO_map.txt" ] || {
    echo "[数据库错误] metagenome-DB 不完整: ${MAP_DIR}" >&2
    exit 2
}
for required_file in hash.k2d opts.k2d taxo.k2d; do
    [ -s "${KRAKEN2_DB}/${required_file}" ] || {
        echo "[Kraken2数据库错误] 缺少或为空: ${KRAKEN2_DB}/${required_file}" >&2
        exit 2
    }
done

# 临时 WDL 只供 Cromwell 解析，不会作为 Docker task 输入。
TMP_RUN_DIR="$(mktemp -d /tmp/metage_v2.88.2_pre_tax.XXXXXX)"
trap 'rm -rf -- "${TMP_RUN_DIR}"' EXIT
WDL_FILE="${TMP_RUN_DIR}/metage_v2.88.2_pre_tax.wdl"

cat >"${WDL_FILE}" <<WDL_HEADER
workflow metage_v2_88_2_pre_tax {
    String datapath = "${DATA_DIR}"
    String rawdatapath = "/home/xydeng/Metagenomics_Docker/data"
    String mapdir = "/cephfs_data/genostack_v3/genostack_php/public_file_data/metagenome-DB"
    String kraken2_db = "/cephfs_data/genostack_v3/genostack_php/public_file_data/metagenome-DB/kraken2/minikraken2_v2_8GB_201904_UPDATE"

    call choose_plot_style {
        input:
            global_font_family="Times New Roman",
            global_theme="bw",
            global_dpi="300",
            global_width="10",
            global_height="8",
            task_overrides_json=write_lines(["{}"])
    }
    call check_input_with_raw {
        input:
            dataDir=datapath,
            fastq_dir=rawdatapath,
            allow_extra_fastq=false,
            allow_empty_comparison=false
    }
    call kneaddata_no {
        input:
            datapath=check_input_with_raw.result,
            rawdatapath=rawdatapath,
            host="none",
            mapdir=mapdir,
            checkDir=check_input_with_raw.result,
            keep_clean_reads=true,
            plot_style=choose_plot_style.plot_style
    }
    call kraken2_anno {
        input:
            cleandir=kneaddata_no.cleandir,
            datapath=check_input_with_raw.result,
            kraken2_db=kraken2_db,
            threads=16
    }
    call kraken2_tax_base {
        input:
            datapath=check_input_with_raw.result,
            kraken2_out=kraken2_anno.kraken2_out,
            plot_style=choose_plot_style.plot_style
    }
    call megahit_no {
        input:
            datapath=check_input_with_raw.result,
            clean_dir=kneaddata_no.cleandir,
            host="none",
            dehost_dir=kneaddata_no.dohost_dir
    }
    call prodig_no {
        input:
            megahit=megahit_no.megahit,
            datapath=check_input_with_raw.result
    }
    call bwa_no {
        input:
            prodigal=prodig_no.prodigal,
            datapath=check_input_with_raw.result,
            clean_dir=kneaddata_no.cleandir,
            host="none",
            dehost_dir=kneaddata_no.dohost_dir
    }

    output {
        File checked_data = check_input_with_raw.result
        File qc_result = kneaddata_no.Result
        File clean_reads = kneaddata_no.cleandir
        File kraken2_result = kraken2_anno.kraken2_out
        File kraken2_tax_base_result = kraken2_tax_base.Result
        File megahit_result = megahit_no.megahit
        File prodigal_result = prodig_no.prodigal
        File bwa_result = bwa_no.bowtie
    }
}
WDL_HEADER

# 任务定义始终从当前正式 WDL 提取，避免复制出另一套易失同步的任务代码。
awk '
    BEGIN {
        wanted["check_input_with_raw"]=1
        wanted["choose_plot_style"]=1
        wanted["kneaddata_no"]=1
        wanted["megahit_no"]=1
        wanted["prodig_no"]=1
        wanted["bwa_no"]=1
        wanted["kraken2_anno"]=1
        wanted["kraken2_tax_base"]=1
    }
    /^task[[:space:]]+/ {
        name=$2
        sub(/\{.*/, "", name)
        keep=(name in wanted)
    }
    keep { print }
' "${SOURCE_WDL}" >>"${WDL_FILE}"

echo "[样本] 12个（RCK/RS/SCK/SS，每组3个；24个双端FASTQ）"
echo "[测试输入] ${DATA_DIR}"
echo "[范围] check_input -> kneaddata -> Kraken2/Bracken + MEGAHIT -> Prodigal -> BWA"
echo "[停止点] tax_anno 前；tax_anno/func_anno/后续报告均不调度"
echo "[镜像] ${IMAGE}"

# Cromwell 85 的主程序只有 server/run/submit，没有 validate 子命令。
# 这里检查专用 WDL 是否完整生成；正式的 WDL 解析由下方 `cromwell run` 完成。
for task_name in check_input_with_raw choose_plot_style kneaddata_no \
    kraken2_anno kraken2_tax_base megahit_no prodig_no bwa_no; do
    grep -q "^task ${task_name}[[:space:]]*{" "${WDL_FILE}" || {
        echo "[WDL生成错误] 缺少任务: ${task_name}" >&2
        exit 2
    }
done
if grep -q '^task \(tax_anno\|func_anno\)[[:space:]]*{' "${WDL_FILE}"; then
    echo "[WDL生成错误] pre-tax WDL 意外包含注释任务" >&2
    exit 2
fi
echo "[检查] pre-tax WDL 任务集合: PASS"
[ "${VALIDATE_ONLY}" = false ] || exit 0

docker image inspect "${IMAGE}" >/dev/null 2>&1 || docker pull "${IMAGE}"

RUN_LOCK_FILE="${PROJECT_DIR}/.run_workflow.lock"
exec 9>"${RUN_LOCK_FILE}"
if ! flock -n 9; then
    echo "[启动失败] 当前目录已有 Cromwell 流程运行，请等待其结束。" >&2
    exit 3
fi

mkdir -p "${PROJECT_DIR}/cromwell-db" \
    "${PROJECT_DIR}/cromwell-workflow-logs"
DATE_STR="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${PROJECT_DIR}/cromwell_pre_tax_real12_${DATE_STR}.log"
META_FILE="${PROJECT_DIR}/cromwell_pre_tax_real12_metadata_${DATE_STR}.json"

echo "[运行日志] ${LOG_FILE}"
set +e
"${JAVA_BIN}" -Xmx4g -Dconfig.file="${CONFIG_FILE}" \
    -jar "${CROMWELL_JAR}" run \
    -o "${OPTIONS_FILE}" -m "${META_FILE}" "${WDL_FILE}" \
    2>&1 | tee "${LOG_FILE}"
workflow_rc=${PIPESTATUS[0]}
set -e

if [ "${workflow_rc}" -ne 0 ]; then
    echo "[失败] Cromwell 退出码 ${workflow_rc}" >&2
    echo "[日志] ${LOG_FILE}" >&2
    exit "${workflow_rc}"
fi

workflow_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("id", ""))' "${META_FILE}")"
echo "[完成] workflow_id=${workflow_id}"
echo "[结果目录] ${WORKFLOW_ROOT}/${workflow_id}"
echo "[确认] tax_anno 和 func_anno 未运行"
