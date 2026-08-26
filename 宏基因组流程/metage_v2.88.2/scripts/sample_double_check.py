#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
宏基因组样本核对与文件指纹管理脚本（sample_double_check）

【快速概览】
  1. 核心功能：对任意目录执行扫描，提取文件指纹（size、mtime、MD5），输出文件信息报告；
     再次扫描同一目录时，自动与历史记录对比，识别新增、删除、重命名及内容变更。
  2. 最常用入口为 scan-dir：指定任意路径即可扫描，不限于 FASTQ，生成可读 .txt 报告，
     并在同目录保存隐藏 .json 供后续对比。
  3. 默认行为为只读记录，不修改、不删除被扫描文件。

【函数分类地图】
  为便于阅读和维护，脚本中函数大致分为以下几类：
    1. 文件指纹工具：compute_md5、get_file_type、file_fingerprint、
       fingerprint_files 等：计算并缓存文件大小、MD5、类型、修改时间。
    2. Manifest 管理：ManifestManager 类：负责 .sample_manifest.json 的读写、
       版本迁移、并发安全及变更检测。
    3. 子命令入口：cmd_scan_dir、cmd_data_check、cmd_check_input_with_raw、
       cmd_record_stage、cmd_show、cmd_lineage、cmd_show_task_map：每个子命令
       对应一个入口函数。
    4. FASTQ 样本工具：read_sample_txt、find_fastq_pair、scan_batch、
       prefix_to_sample、rewrite_sample_txt 等：仅供 data-check / check-input-with-raw
       使用，用于样本名解析与 sample.txt 维护。
    5. 下游同步工具：delete_sample_results、rename_sample_results、
       expand_sync_patterns：仅供 data-check --do-modify 使用，同步下游结果目录。
    6. 扫描日志工具：scan_directory、save_scan_log、load_latest_scan_log、
       compare_scan_logs：仅供 scan-dir 使用，负责历史日志对比。

缩写说明：
  SDC : Sample Double Check，本脚本在 shell 命令中的常用变量名（用户可自定义）。
  mtime: modification time，文件最后修改时间（Unix 时间戳或格式化后的本地时间）。
  MD5 : Message-Digest Algorithm 5，文件内容哈希，用于检测内容变更。
  CLI : Command Line Interface，命令行调用模式。
  WDL : Workflow Description Language，工作流描述语言。

核心定位：
  作为流程的前置核对环节，也可被每个 task 调用，记录各阶段输入/输出文件指纹。
  通过文件大小、修改时间（mtime）、MD5 校验，识别样本的【新增/删除/重命名/内容变更/未变更】信息，
  并支持对合并产生的中间文件（如 all.fa、unique_gene.fasta）进行指纹记录。

适用场景：
  1. 客户在任意阶段增加、删减或重命名样本。
  2. 流程中间产物被合并处理（如 prodigal 的 all.fa、mmseqs 的 unique_gene.fasta）。
  3. 需要追溯每个结果文件是由哪些样本产生的。
  4. 在 WDL 工作流的每个 task 结束后记录输出文件指纹，实现全链路可追溯。

三种使用方式：
  A. 命令行模式：核对原始 FASTQ 样本变更（最开始的入口）。
  B. 库模式：被各 task Python 脚本 import，记录该 task 的输入/输出文件指纹。
  C. WDL 模式：在每个 WDL task 的 command 块末尾调用 `python sample_double_check.py record-stage`。

record_stage() 的行为说明：
  - 对指定的文件：**只读取**（计算 size/mtime/MD5），不会修改、移动或删除原文件。
  - 对 manifest：**写入/更新** `<metadatadir>/.sample_manifest.json`。
  - 因此可在 WDL 工作流中安全地追加到每个 task 命令末尾，不影响原有输出。

Manifest 结构（version 2）：
{
  "version": 2,
  "created_at": "...",
  "updated_at": "...",
  "samples": ["CK-1", "CK-2", ...],
  "stages": {
    "rawdata": {
      "CK-1": {
        "files": {"/rawdata/CK_1_R1.fq.gz": {"size": ..., "mtime": ..., "md5": ...}, ...},
        "input_samples": ["CK-1"],
        "is_merged": false,
        "recorded_at": "..."
      }
    },
    "prodigal": {
      "all": {
        "files": {"/prodigal/all.fa": {...}, "/prodigal/unique_gene.fasta": {...}},
        "input_samples": ["CK-1", "CK-2", ...],
        "is_merged": true,
        "recorded_at": "..."
      }
    }
  }
}

命令行示例：
  # 核对原始 FASTQ 变更（只扫描，不执行）
  python sample_double_check.py data-check \
      -i /rawdata -I /metadatadir \
      --output-dirs cleandata de_host megahit_update prodigal_original

  # 确认后执行修改
  python sample_double_check.py data-check \
      -i /rawdata -I /metadatadir \
      --output-dirs cleandata de_host megahit_update prodigal_original \
      --do-modify

  # 增量式多路径/多批次 FASTQ 核对（check_input_with_raw）
  python sample_double_check.py check-input-with-raw \
      --fastq-dirs /rawdata/batch1:batch1 /rawdata/batch2:batch2 \
      -I /metadatadir \
      --task-id run_001

  # 指定任意目录，读取、输出并保存扫描日志；再次扫描自动与历史日志对比
  python sample_double_check.py scan-dir \
      --dir /path/to/any_folder

库模式示例：
  from sample_double_check import ManifestManager
  mm = ManifestManager('/metadatadir')
  mm.record_stage('megahit', 'CK-1', {
      '/megahit_update/CK-1/final.contigs.fa': '/megahit_update/CK-1/final.contigs.fa'
  }, input_samples=['CK-1'])

WDL 集成示例：
  在每个 WDL task 的 command 块末尾追加 record-stage 调用。要求：
    1. Docker 镜像中可用 Python 3 及标准库（脚本仅依赖标准库）。
    2. `scripts_dxy/Script/` 挂载到容器内的 `/root/microbiome/microbiome/metage_v2.88.2/` 或 `/scripts/`。
    3. `metadatadir` 挂载到容器内可写路径（ manifest 需要写入 `.sample_manifest.json`）。
    4. 并发安全：`ManifestManager.save()` 已使用文件锁 + 原子写入，多个 task 同时写 manifest 不会互相覆盖。

  重要注意事项：
    - WDL 用 `${var}` 解析自身的变量，shell 变量应避免使用 `${shellvar}` 形式，改用 `$shellvar`。
    - 若 shell 变量后面紧跟后缀，可用 `"$var"_suffix` 拼接，避免 WDL 误解析。
    - `--files` 支持 `logical_name=real_path` 形式，便于 manifest 中识别每个文件的含义。
    - 对目录输出请加 `--no-md5`（只记录 size/mtime），否则会因为 `IsADirectoryError` 失败。
    - 对可能不存在的文件请加 `--skip-missing`，避免 task 因某个可选文件缺失而失败。

  task megahit_no 示例（单样本输出）：
  ```wdl
  task megahit_no {
      String metadatadir
      String cleandatadir
      String megahit_dir
      String host

      command {
          source /root/anaconda3/etc/profile.d/conda.sh
          conda activate megahit
          python /root/microbiome/microbiome/metage_v2.88.2/megahit.py \
              -I ${metadatadir} --cleandir ${cleandatadir} --host ${host} \
              --host_dir /de_host --megahit ${megahit_dir}

          # 记录每个样本的组装结果指纹
          for sample in $(awk 'NR>1 {print $2}' ${metadatadir}/sample.txt); do
              if [ -d "${megahit_dir}/$sample" ]; then
                  python /root/microbiome/microbiome/metage_v2.88.2/sample_double_check.py record-stage \
                      -I ${metadatadir} \
                      --stage megahit \
                      --key $sample \
                      --files contigs="${megahit_dir}/$sample"/final.contigs.fa \
                      --input-samples $sample
              fi
          done
      }
      runtime { ... }
  }
  ```

  task prodig_no 示例（合并文件输出，带逻辑名）：
  ```wdl
  task prodig_no {
      String metadatadir
      File megahit
      String prodigal_dir

      command {
          source /root/anaconda3/etc/profile.d/conda.sh
          conda activate megahit
          python /root/microbiome/microbiome/metage_v2.88.2/prodigal.py \
              --megahit ${megahit} --cdhitdir /app/cd-hit-v4.8.1-2019-0228

          # 记录合并产生的非冗余基因集指纹
          all_samples=$(awk 'NR>1 {print $2}' ${metadatadir}/sample.txt | tr '\n' ' ')
          python /root/microbiome/microbiome/metage_v2.88.2/sample_double_check.py record-stage \
              -I ${metadatadir} \
              --stage prodigal \
              --key all \
              --files all_fa="${prodigal_dir}/all.fa" unique_gene="${prodigal_dir}/unique_gene.fasta" \
              --input-samples $all_samples \
              --merged
      }
      runtime { ... }
  }
  ```

  task tax_anno 示例（目录输出，禁用 MD5）：
  ```wdl
  task tax_anno {
      String metadatadir
      String mapdir
      File prodigal

      command {
          source /root/anaconda3/etc/profile.d/conda.sh
          conda activate biobakery
          python /root/microbiome/microbiome/metage_v2.88.2/tax_ano_1.py \
              --prodigal ${prodigal} --dbdir ${mapdir}/database/NR --megandir /opt/megan7/

          all_samples=$(awk 'NR>1 {print $2}' ${metadatadir}/sample.txt | tr '\n' ' ')
          python /root/microbiome/microbiome/metage_v2.88.2/sample_double_check.py record-stage \
              -I ${metadatadir} \
              --stage tax_anno \
              --key all \
              --files annotation=Annotation \
              --input-samples $all_samples \
              --merged --no-md5
      }
      runtime { ... }
  }
  ```

  task bwa_no 示例（可能缺失的文件使用 --skip-missing）：
  ```wdl
  task bwa_no {
      String metadatadir
      String host
      File clean_dir
      File prodigal
      File dehost_dir

      command {
          source /root/anaconda3/etc/profile.d/conda.sh
          conda activate biobakery
          python /root/microbiome/microbiome/metage_v2.88.2/bwa.py \
              -I ${metadatadir} --cleandir ${clean_dir} --host ${host} \
              --prodigal ${prodigal} --host_dir ${dehost_dir}

          for sample in $(awk 'NR>1 {print $2}' ${metadatadir}/sample.txt); do
              python /root/microbiome/microbiome/metage_v2.88.2/sample_double_check.py record-stage \
                  -I ${metadatadir} \
                  --stage bwa \
                  --key $sample \
                  --files bam=bowtie/"$sample".bam bai=bowtie/"$sample".bam.bai \
                  --input-samples $sample \
                  --skip-missing
          done
      }
      runtime { ... }
  }
  ```
"""

import os
import sys
import re
import json
import argparse
import hashlib
import shutil
import glob
import fcntl
import fnmatch
from datetime import datetime
from collections import defaultdict


# ---------------------------------------------------------------------------
# 默认 FASTQ 配对规则
# ---------------------------------------------------------------------------
DEFAULT_FASTQ_PATTERNS = [
    ("{prefix}_R1.fq.gz", "{prefix}_R2.fq.gz"),
    ("{prefix}_R1.fastq.gz", "{prefix}_R2.fastq.gz"),
    ("{prefix}_1.fq.gz", "{prefix}_2.fq.gz"),
    ("{prefix}_1.fastq.gz", "{prefix}_2.fastq.gz"),
]

# 扩展 FASTQ 配对规则：支持未压缩的 .fastq / .fq
EXTRA_FASTQ_PATTERNS = [
    ("{prefix}_R1.fq", "{prefix}_R2.fq"),
    ("{prefix}_R1.fastq", "{prefix}_R2.fastq"),
    ("{prefix}_1.fq", "{prefix}_2.fq"),
    ("{prefix}_1.fastq", "{prefix}_2.fastq"),
]

# 默认下游结果目录同步模式
DEFAULT_SYNC_PATTERNS = {
    "cleandata": [
        "{sample}_clean_*.fastq.gz",
        "qc/{sample}.json",
        "qc/{sample}.html",
        "logs/{sample}.log",
        "table/{sample}_error_rate.tsv",
        "table/{sample}_content.tsv",
    ],
    "de_host": [
        "{sample}_dehost_*.fastq.gz",
        "{sample}_de_host*.fastq.gz",
        "qc/{sample}.json",
        "qc/{sample}.html",
        "logs/{sample}_bowtie.log",
        "logs/{sample}_fastp.log",
    ],
    "megahit": [
        "{sample}/",
        "length/{sample}_length.txt",
        "length/{sample}_stats.txt",
    ],
    "megahit_update": [
        "{sample}/",
        "length/{sample}_length.txt",
        "length/{sample}_stats.txt",
    ],
    "prodigal": [
        "{sample}.gff3",
        "{sample}.fastq",
        "{sample}.faa",
    ],
    "prodigal_original": [
        "{sample}.gff3",
        "{sample}.fastq",
        "{sample}.faa",
    ],
    "bowtie": [
        "{sample}.*",
    ],
}


# ---------------------------------------------------------------------------
# 文件指纹工具函数
# ---------------------------------------------------------------------------
def compute_md5(filepath, chunk_size=8192 * 1024):
    """计算文件 MD5，支持大文件分块读取。"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def get_file_type(filepath):
    """
    根据文件后缀提取文件类型与是否压缩。
    返回 (file_type, is_compressed)。
    例如：
      CK_1_R1.fastq       -> ("fastq", False)
      CK_1_R1.fastq.gz    -> ("fastq.gz", True)
      CK_1_R1.fq.gz       -> ("fq.gz", True)
      final.contigs.fa    -> ("fa", False)
      bowtie/CK-1.bam     -> ("bam", False)
    """
    name = os.path.basename(filepath).lower()
    if name.endswith(".gz"):
        base = name[:-3]
        is_compressed = True
    else:
        base = name
        is_compressed = False

    ext = os.path.splitext(base)[1].lstrip(".")
    if not ext:
        return "unknown", is_compressed
    if is_compressed:
        return f"{ext}.gz", is_compressed
    return ext, is_compressed


def format_mtime(mtime):
    """将 Unix 时间戳（mtime）格式化为本地可读字符串：YYYY-MM-DD HH:MM:SS。"""
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")


def file_fingerprint(filepath):
    """返回文件指纹字典：大小、修改时间（mtime）、MD5、文件类型、是否压缩。"""
    stat = os.stat(filepath)
    file_type, is_compressed = get_file_type(filepath)
    return {
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "mtime_human": format_mtime(stat.st_mtime),
        "md5": compute_md5(filepath),
        "file_type": file_type,
        "is_compressed": is_compressed,
    }


def get_cached_or_compute_fingerprint(filepath, previous_files):
    """
    优先使用缓存的 MD5：当文件大小和修改时间（mtime）未变时，直接复用 previous_files 中的 md5。
    否则重新计算 MD5。
    file_type / is_compressed 根据当前路径实时推导，不缓存。
    """
    stat = os.stat(filepath)
    file_type, is_compressed = get_file_type(filepath)
    prev = previous_files.get(filepath) if previous_files else None
    if prev and prev.get("size") == stat.st_size and prev.get("mtime") == stat.st_mtime:
        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "mtime_human": format_mtime(stat.st_mtime),
            "md5": prev["md5"],
            "file_type": file_type,
            "is_compressed": is_compressed,
        }
    return {
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "mtime_human": format_mtime(stat.st_mtime),
        "md5": compute_md5(filepath),
        "file_type": file_type,
        "is_compressed": is_compressed,
    }


def fingerprint_files(file_paths, previous_files=None, use_md5=True):
    """
    对文件列表计算指纹。
    file_paths: 文件路径列表，或 {logical_name: real_path} 字典。
    返回 {logical_name: fingerprint}。
    """
    result = {}
    if isinstance(file_paths, dict):
        items = file_paths.items()
    else:
        items = [(p, p) for p in file_paths]

    for logical_name, real_path in items:
        real_path = os.path.abspath(real_path)
        if not os.path.exists(real_path):
            raise FileNotFoundError(f"文件不存在: {real_path}")
        if use_md5:
            fp = get_cached_or_compute_fingerprint(real_path, previous_files)
        else:
            stat = os.stat(real_path)
            file_type, is_compressed = get_file_type(real_path)
            fp = {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "mtime_human": format_mtime(stat.st_mtime),
                "md5": None,
                "file_type": file_type,
                "is_compressed": is_compressed,
            }
        result[logical_name] = fp
    return result


# ---------------------------------------------------------------------------
# ManifestManager：通用指纹/阶段管理
# ---------------------------------------------------------------------------
class ManifestManager:
    """
    管理 .sample_manifest.json 的通用类。
    支持记录任意 stage 的输入/输出文件指纹，包括 per-sample 和 merged 文件。
    """

    def __init__(self, metadatadir, manifest_name=".sample_manifest.json"):
        self.metadatadir = os.path.abspath(metadatadir)
        self.manifest_path = os.path.join(self.metadatadir, manifest_name)
        self.data = self._load()

    @staticmethod
    def _migrate_v1_to_v2(old):
        """将 version 1 的 manifest 升级为 version 2。"""
        new = {
            "version": 2,
            "created_at": old.get("created_at") or datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "samples": sorted(old.get("samples", {}).keys()),
            "stages": {},
        }
        rawdata_stage = {}
        for sample, info in old.get("samples", {}).items():
            rawdata_stage[sample] = {
                "files": info.get("files", {}),
                "input_samples": [sample],
                "is_merged": False,
                "recorded_at": old.get("created_at") or datetime.now().isoformat(),
            }
        new["stages"]["rawdata"] = rawdata_stage
        return new

    def _read_file(self):
        """读取 manifest 文件（不加锁），返回 dict 或 None。"""
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != 2:
                data = self._migrate_v1_to_v2(data)
            return data
        return None

    def _load(self):
        data = self._read_file()
        if data is not None:
            return data
        return {
            "version": 2,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "samples": [],
            "stages": {},
        }

    def save(self, replace_stages=None):
        """
        保存 manifest，使用文件锁保证 WDL 多任务并发写入安全。
        保存前会重新读取磁盘上的最新 manifest，并将当前内存中的 stage 数据合并进去，
        避免并行任务互相覆盖。

        参数：
          replace_stages: 需要完整替换的 stage 名列表（如 ["rawdata"]）。
                          对于完整扫描类命令，旧条目中已不存在的样本需要被删除，
                          因此需要替换整个 stage，而不是 update。
                          WDL 的 record-stage 调用应保持默认 None，使用 update。
        """
        replace_stages = set(replace_stages or [])
        self.data["updated_at"] = datetime.now().isoformat()
        os.makedirs(self.metadatadir, exist_ok=True)
        lock_path = self.manifest_path + ".lock"
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except (OSError, IOError):
                pass  # 如果锁不可用，仍尝试写入（单进程场景）
            try:
                latest = self._read_file() or {
                    "version": 2,
                    "created_at": self.data.get("created_at") or datetime.now().isoformat(),
                    "updated_at": self.data["updated_at"],
                    "samples": [],
                    "stages": {},
                }
                # 合并当前内存中的 stage 数据到最新磁盘数据
                for stage_name, stage_data in self.data.get("stages", {}).items():
                    latest_stage = latest.setdefault("stages", {}).setdefault(stage_name, {})
                    if stage_name in replace_stages:
                        # 完整替换：删除旧 keys，写入当前 keys
                        latest_stage.clear()
                        latest_stage.update(stage_data)
                    else:
                        latest_stage.update(stage_data)
                # 同步顶层样本列表
                rawdata = latest.get("stages", {}).get("rawdata", {})
                latest["samples"] = sorted(rawdata.keys())
                latest["updated_at"] = self.data["updated_at"]
                if "created_at" not in latest:
                    latest["created_at"] = self.data.get("created_at") or datetime.now().isoformat()
                # 原子写入：先写入临时文件，再 rename，避免读取到半写入文件
                tmp_path = f"{self.manifest_path}.tmp.{os.getpid()}"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(latest, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.manifest_path)
                self.data = latest
            finally:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except (OSError, IOError):
                    pass

    def get_stage(self, stage_name):
        return self.data.setdefault("stages", {}).setdefault(stage_name, {})

    def get_previous_files(self):
        """返回所有 stage 中记录过的文件指纹，用于 MD5 缓存。"""
        files = {}
        for stage_name, stage_data in self.data.get("stages", {}).items():
            for key, entry in stage_data.items():
                files.update(entry.get("files", {}))
        return files

    def record_stage(self, stage_name, key, file_paths, input_samples=None,
                     is_merged=False, use_md5=True, metadata=None):
        """
        记录某个 stage 的指纹。

        该方法只读取文件（计算 size/mtime/MD5），不会修改、移动或删除被记录的文件。
        写入操作仅针对 manifest（<metadatadir>/.sample_manifest.json），因此可以安全地
        在 WDL 工作流的每个 task command 块末尾调用。

        参数：
          stage_name: 阶段名，如 'rawdata', 'cleandata', 'megahit', 'prodigal'。
          key: 该条目的标识，通常用样本名（如 'CK-1'）；对合并文件可用 'all' 或自定义名。
          file_paths: 文件路径列表或 {logical_name: real_path} 字典。
                      使用字典时，manifest 中会用 logical_name 作为键，便于识别。
          input_samples: 产生该结果的输入样本列表。
          is_merged: 是否由多个样本合并产生（如 all.fa、unique_gene.fasta）。
          use_md5: 是否计算 MD5。对目录输出建议设为 False，避免 IsADirectoryError。
          metadata: 额外元数据字典（如命令、参数、版本等）。

        WDL 中使用建议：
          - 单样本输出：在 shell 循环中逐样本调用，key 用样本名。
          - 合并输出：key 用 'all'，input_samples 填入所有样本，is_merged=True。
          - 目录输出：use_md5=False（或 CLI 中加 --no-md5）。
          - 可能缺失的文件：在 CLI 中加 --skip-missing。
        """
        previous_files = self.get_previous_files() if use_md5 else None
        fingerprints = fingerprint_files(file_paths, previous_files, use_md5=use_md5)
        entry = {
            "files": fingerprints,
            "input_samples": sorted(input_samples or []),
            "is_merged": bool(is_merged),
            "recorded_at": datetime.now().isoformat(),
        }
        if metadata:
            entry["metadata"] = metadata
        stage = self.get_stage(stage_name)
        stage[key] = entry
        # 同步顶层 samples 列表
        self._update_sample_list()
        return entry

    def _update_sample_list(self):
        """根据 rawdata stage 更新顶层样本列表。"""
        rawdata = self.data.get("stages", {}).get("rawdata", {})
        self.data["samples"] = sorted(rawdata.keys())

    def detect_changes(self, stage_name, current_entries):
        """
        检测某个 stage 的变更。

        current_entries: {key: {'files': {...}, 'input_samples': [...], 'is_merged': bool}}
        返回：{"added": [...], "deleted": [...], "renamed": [...], "changed": [...], "unchanged": [...]}
        """
        previous = self.get_stage(stage_name)
        current_keys = set(current_entries.keys())
        previous_keys = set(previous.keys())

        unchanged = []
        changed = []
        for key in current_keys & previous_keys:
            cur_files = current_entries[key]["files"]
            prev_files = previous[key].get("files", {})
            if self._files_equal(cur_files, prev_files):
                unchanged.append(key)
            else:
                changed.append(key)

        added_keys = list(current_keys - previous_keys - set(changed))
        deleted_keys = list(previous_keys - current_keys)

        # 重命名检测：在 added 和 deleted 中按文件指纹匹配
        renamed = []
        remaining_added = []
        remaining_deleted = set(deleted_keys)

        # 为删除的条目建立文件指纹索引
        deleted_index = defaultdict(list)
        for old_key in deleted_keys:
            files = previous[old_key].get("files", {})
            fp_key = self._files_fingerprint_key(files)
            deleted_index[fp_key].append(old_key)

        for new_key in added_keys:
            cur_files = current_entries[new_key]["files"]
            fp_key = self._files_fingerprint_key(cur_files)
            candidates = deleted_index.get(fp_key, [])
            if candidates:
                old_key = candidates[0]
                renamed.append({"old_key": old_key, "new_key": new_key})
                remaining_deleted.discard(old_key)
            else:
                remaining_added.append(new_key)

        return {
            "added": sorted(remaining_added),
            "deleted": sorted(remaining_deleted),
            "renamed": renamed,
            "changed": sorted(changed),
            "unchanged": sorted(unchanged),
        }

    @staticmethod
    def _files_equal(files1, files2):
        """比较两组文件指纹是否相等（比较 size 和 md5，忽略 mtime）。"""
        if set(files1.keys()) != set(files2.keys()):
            return False
        for name, fp1 in files1.items():
            fp2 = files2[name]
            if fp1.get("size") != fp2.get("size"):
                return False
            if fp1.get("md5") and fp2.get("md5") and fp1["md5"] != fp2["md5"]:
                return False
        return True

    @staticmethod
    def _files_fingerprint_key(files):
        """
        为文件集合生成一个用于重命名匹配的指纹键。
        仅按文件内容（size + md5）排序后拼接，忽略文件名/路径，
        因此即使样本被重命名、文件路径变化，只要内容不变就能匹配到旧样本。
        """
        parts = []
        for fp in files.values():
            md5 = fp.get("md5") or ""
            parts.append(f"{fp.get('size', 0)}:{md5}")
        return "|".join(sorted(parts))

    def get_sample_lineage(self, sample):
        """获取某个样本在各 stage 中的记录。"""
        lineage = {}
        for stage_name, stage_data in self.data.get("stages", {}).items():
            if sample in stage_data:
                lineage[stage_name] = stage_data[sample]
            else:
                # 查找 merged 结果中包含该样本的记录
                for key, entry in stage_data.items():
                    if sample in entry.get("input_samples", []):
                        lineage.setdefault(stage_name, {})[key] = entry
        return lineage


# ---------------------------------------------------------------------------
# sample.txt 读取
# ---------------------------------------------------------------------------
def read_sample_txt(path):
    """读取 sample.txt，返回 {sample_name: fastqfile_prefix}。"""
    samples = {}
    if not os.path.exists(path):
        return samples
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline()
        if header and not header.strip().lower().startswith("fastqfile"):
            parts = header.strip().split("\t")
            if len(parts) >= 2:
                samples[parts[1].strip()] = parts[0].strip()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                fastqfile = parts[0].strip()
                sample = parts[1].strip()
                if fastqfile and sample:
                    samples[sample] = fastqfile
    return samples


def find_fastq_pair(rawdatadir, prefix, patterns=None):
    """根据前缀查找 R1/R2 文件对。"""
    patterns = patterns or DEFAULT_FASTQ_PATTERNS
    found = []
    for r1_pat, r2_pat in patterns:
        r1 = os.path.join(rawdatadir, r1_pat.format(prefix=prefix))
        r2 = os.path.join(rawdatadir, r2_pat.format(prefix=prefix))
        if os.path.exists(r1) and os.path.exists(r2):
            found.append((r1, r2))
    return found


# ---------------------------------------------------------------------------
# 增量式 check_input_with_raw 辅助函数（支持多路径/多批次）
# ---------------------------------------------------------------------------
def parse_fastq_dirs(arglist):
    """解析 --fastq-dirs 参数，支持 path 或 path:batch_name。"""
    result = []
    for item in arglist:
        if ":" in item:
            path, batch = item.split(":", 1)
        else:
            path = item
            batch = os.path.basename(os.path.normpath(path))
        result.append((os.path.abspath(path), batch))
    return result


def extract_prefix(filename):
    """从 FASTQ 文件名提取样本前缀（去掉 _R1/_R2 和扩展名）。"""
    name = filename
    if name.endswith(".gz"):
        name = name[:-3]
    for ext in (".fastq", ".fq"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return re.sub(r"([_\-\.])(R?[12])$", "", name)


def scan_batch(fastq_dir, batch, previous_files, patterns=None):
    """
    扫描一个 FASTQ 目录，按前缀配对 R1/R2。
    返回 ({prefix: info}, unmatched_prefixes)。
    """
    if not os.path.isdir(fastq_dir):
        raise FileNotFoundError(f"FASTQ 目录不存在: {fastq_dir}")

    all_patterns = (patterns or DEFAULT_FASTQ_PATTERNS) + EXTRA_FASTQ_PATTERNS

    files = [
        f
        for f in os.listdir(fastq_dir)
        if f.lower().endswith((".fastq", ".fastq.gz", ".fq", ".fq.gz"))
    ]
    prefixes = {extract_prefix(f) for f in files if extract_prefix(f)}

    samples = {}
    unmatched = []
    for prefix in sorted(prefixes):
        pairs = find_fastq_pair(fastq_dir, prefix, all_patterns)
        if not pairs:
            unmatched.append(prefix)
            continue
        r1, r2 = pairs[0]
        file_dict = {r1: r1, r2: r2}
        fps = fingerprint_files(file_dict, previous_files, use_md5=True)
        samples[prefix] = {
            "files": fps,
            "paths": {"R1": r1, "R2": r2},
            "batch": batch,
        }

    return samples, unmatched


def load_sample_mapping(sample_txt_path):
    """读取 sample.txt，返回 {prefix: sample}。"""
    mapping = {}
    if not os.path.exists(sample_txt_path):
        return mapping
    with open(sample_txt_path, "r", encoding="utf-8") as f:
        header = f.readline()
        if header and not header.strip().lower().startswith("fastqfile"):
            parts = header.strip().split("\t")
            if len(parts) >= 2:
                mapping[parts[0].strip()] = parts[1].strip()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                mapping[parts[0].strip()] = parts[1].strip()
    return mapping


def prefix_to_sample(prefix, mapping):
    """根据已有映射决定 sample 名；无映射时自动推导。"""
    if prefix in mapping:
        return mapping[prefix]
    auto = prefix.replace("_", "-")
    # 避免与已有 sample 名冲突
    if auto in mapping.values():
        i = 1
        while f"{auto}_{i}" in mapping.values():
            i += 1
        auto = f"{auto}_{i}"
    return auto


def append_sample_txt(sample_txt_path, new_entries):
    """向 sample.txt 追加新增样本。new_entries: [(prefix, sample), ...]"""
    existing = set()
    lines = []
    if os.path.exists(sample_txt_path):
        with open(sample_txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                existing.add(parts[1].strip())
    else:
        lines = ["fastqfile\tsample\n"]

    added = 0
    for prefix, sample in new_entries:
        if sample not in existing:
            lines.append(f"{prefix}\t{sample}\n")
            existing.add(sample)
            added += 1

    with open(sample_txt_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return added


def append_metadata(metadata_path, new_samples, group):
    """向 sample-metadata.tsv 追加新增样本（保持 QIIME 格式）。"""
    lines = []
    if not os.path.exists(metadata_path):
        lines = ["sample-id\tgroup1\n", "#q2:types\tcategorical\n"]
    else:
        with open(metadata_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    existing = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("sample-id") or stripped.startswith("#q2:types"):
            continue
        parts = stripped.split("\t")
        if parts:
            existing.add(parts[0])

    added = 0
    for s in sorted(new_samples):
        if s not in existing:
            lines.append(f"{s}\t{group}\n")
            added += 1

    with open(metadata_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return added


def rewrite_sample_txt(sample_txt_path, prefix_sample_list):
    """
    根据当前样本列表重写 sample.txt。
    prefix_sample_list: [(prefix, sample), ...]
    """
    lines = ["fastqfile\tsample\n"]
    for prefix, sample in prefix_sample_list:
        lines.append(f"{prefix}\t{sample}\n")
    with open(sample_txt_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return len(prefix_sample_list)


def update_sample_txt(sample_txt_path, prefix_sample_list):
    """
    根据当前扫描结果更新 sample.txt：保留未变更条目，更新重命名条目，
    追加新增条目，删除已不存在的条目。
    prefix_sample_list: [(prefix, sample), ...]
    """
    current = {prefix: sample for prefix, sample in prefix_sample_list}
    kept = []

    # 先读取旧文件顺序，保留仍存在的 prefix（sample 名以当前扫描结果为准）
    if os.path.exists(sample_txt_path):
        with open(sample_txt_path, "r", encoding="utf-8") as f:
            header = f.readline()
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    prefix = parts[0].strip()
                    if prefix in current:
                        kept.append((prefix, current[prefix]))

    existing_prefixes = {prefix for prefix, _ in kept}
    # 追加新 prefix
    for prefix, sample in prefix_sample_list:
        if prefix not in existing_prefixes:
            kept.append((prefix, sample))

    lines = ["fastqfile\tsample\n"]
    for prefix, sample in kept:
        lines.append(f"{prefix}\t{sample}\n")

    with open(sample_txt_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return len(kept)


def rewrite_metadata(metadata_path, sample_group_list):
    """
    根据当前样本列表重写 sample-metadata.tsv。
    sample_group_list: [(sample, group), ...]
    """
    lines = ["sample-id\tgroup1\n", "#q2:types\tcategorical\n"]
    for sample, group in sample_group_list:
        lines.append(f"{sample}\t{group}\n")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return len(sample_group_list)


# ---------------------------------------------------------------------------
# 结果目录同步工具（用于 data-check 命令）
# ---------------------------------------------------------------------------
def expand_sync_patterns(output_dir, sample, patterns):
    matched = []
    for pat in patterns:
        expanded = pat.format(sample=sample)
        full_pat = os.path.join(output_dir, expanded)
        if expanded.endswith("/"):
            if os.path.exists(full_pat.rstrip("/")):
                matched.append(full_pat.rstrip("/"))
        else:
            matched.extend(glob.glob(full_pat))
    return matched


def delete_sample_results(sample, output_dir, patterns, dry_run=True):
    paths = expand_sync_patterns(output_dir, sample, patterns)
    for p in paths:
        if not os.path.exists(p):
            continue
        rel = os.path.relpath(p, output_dir)
        if dry_run:
            print(f"  [只扫描] 将删除: {output_dir}/[{rel}]")
        else:
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                print(f"  [DELETED] {output_dir}/[{rel}]")
            except Exception as e:
                print(f"  [ERROR] 删除失败 {output_dir}/[{rel}]: {e}", file=sys.stderr)


def rename_sample_results(old_sample, new_sample, output_dir, patterns, dry_run=True):
    paths = expand_sync_patterns(output_dir, old_sample, patterns)
    for old_path in paths:
        if not os.path.exists(old_path):
            continue
        rel = os.path.relpath(old_path, output_dir)
        new_rel = rel.replace(old_sample, new_sample, 1)
        new_path = os.path.join(output_dir, new_rel)
        if dry_run:
            print(f"  [只扫描] 将重命名: {output_dir}/[{rel}] -> {output_dir}/[{new_rel}]")
        else:
            try:
                os.makedirs(os.path.dirname(new_path) or ".", exist_ok=True)
                shutil.move(old_path, new_path)
                print(f"  [RENAMED] {output_dir}/[{rel}] -> {output_dir}/[{new_rel}]")
            except Exception as e:
                print(f"  [ERROR] 重命名失败 {output_dir}/[{rel}]: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 命令：data-check（原始 FASTQ 核对入口）
# ---------------------------------------------------------------------------
def cmd_check_raw(args):
    rawdatadir = os.path.abspath(args.rawdatadir)
    metadatadir = os.path.abspath(args.metadatadir)
    manifest_path = args.manifest or os.path.join(metadatadir, ".sample_manifest.json")
    use_md5 = not args.no_md5

    mm = ManifestManager(metadatadir, os.path.basename(manifest_path))
    previous_raw = mm.get_stage("rawdata")

    sample_txt_path = os.path.join(metadatadir, "sample.txt")
    # 读取已有 sample.txt 的 prefix -> sample 映射，用于保留客户自定义命名
    mapping = load_sample_mapping(sample_txt_path)

    # 自动扫描 rawdata 目录，发现所有 FASTQ 对
    if not os.path.isdir(rawdatadir):
        print(f"[ERROR] FASTQ 目录不存在: {rawdatadir}", file=sys.stderr)
        sys.exit(1)

    all_patterns = (args.fastq_patterns or DEFAULT_FASTQ_PATTERNS) + EXTRA_FASTQ_PATTERNS
    files = [
        f
        for f in os.listdir(rawdatadir)
        if f.lower().endswith((".fastq", ".fastq.gz", ".fq", ".fq.gz"))
    ]
    prefixes = {extract_prefix(f) for f in files if extract_prefix(f)}

    # 只保留当前仍然存在的 prefix 的 sample 名映射；已删除的 prefix 会在 sample.txt 中移除
    mapping = {p: s for p, s in mapping.items() if p in prefixes}

    current_entries = {}
    previous_files = mm.get_previous_files() if use_md5 else None
    unmatched = []
    for prefix in sorted(prefixes):
        pairs = find_fastq_pair(rawdatadir, prefix, all_patterns)
        if not pairs:
            unmatched.append(prefix)
            continue
        r1, r2 = pairs[0]
        # 优先沿用 sample.txt 中已有的 sample 名；新增 prefix 自动推导
        sample = mapping.get(prefix)
        if not sample:
            sample = prefix_to_sample(prefix, mapping)
            mapping[prefix] = sample
        file_dict = {r1: r1, r2: r2}
        try:
            fps = fingerprint_files(file_dict, previous_files, use_md5)
        except FileNotFoundError as e:
            unmatched.append(f"{prefix}: {e}")
            continue
        current_entries[sample] = {
            "files": fps,
            "file_paths": file_dict,
            "input_samples": [sample],
            "is_merged": False,
        }

    if unmatched:
        print("[WARN] 以下前缀未找到完整 FASTQ 文件对：", file=sys.stderr)
        for item in unmatched:
            print(f"  {item}", file=sys.stderr)

    # 强制重处理
    force_set = set(args.force or [])
    for s in force_set:
        if s in current_entries and s not in (previous_raw or {}):
            # 新增样本被强制，无需处理
            pass

    changes = mm.detect_changes("rawdata", current_entries)

    # 强制样本从 unchanged 移到 changed
    for s in force_set:
        if s in changes["unchanged"]:
            changes["unchanged"].remove(s)
            changes["changed"].append(s)
        # 若被强制样本在 renamed 中，拆开处理
        for r in list(changes["renamed"]):
            if r["new_key"] == s:
                changes["renamed"].remove(r)
                changes["changed"].append(s)
                changes["deleted"].append(r["old_key"])
    changes["changed"] = sorted(set(changes["changed"]))
    changes["deleted"] = sorted(set(changes["deleted"]))

    # 输出报告
    print("\n" + "=" * 70)
    print("原始 FASTQ 样本变更核对报告")
    print("=" * 70)
    print(f"当前样本总数: {len(current_entries)}")
    print(f"  未变更: {len(changes['unchanged'])}  {changes['unchanged']}")
    print(f"  新增:   {len(changes['added'])}    {changes['added']}")
    print(f"  删除:   {len(changes['deleted'])}    {changes['deleted']}")
    print(f"  重命名: {len(changes['renamed'])}    ", end="")
    if changes['renamed']:
        print(", ".join([f"{r['old_key']} -> {r['new_key']}" for r in changes['renamed']]))
    else:
        print("无")
    print(f"  内容变更: {len(changes['changed'])}  {changes['changed']}")
    print("=" * 70)

    # 加载同步配置
    sync_patterns = DEFAULT_SYNC_PATTERNS.copy()
    if args.sync_config:
        with open(args.sync_config, "r", encoding="utf-8") as f:
            sync_patterns.update(json.load(f))

    # 同步结果目录
    mode = "执行修改" if args.do_modify else "只扫描"
    print(f"\n[{mode}] 同步下游结果目录...")

    for sample in changes["deleted"]:
        print(f"\n[删除样本] {sample}")
        for outdir in args.output_dirs:
            outdir_abs = outdir if os.path.isabs(outdir) else os.path.join(os.getcwd(), outdir)
            if not os.path.exists(outdir_abs):
                continue
            patterns = sync_patterns.get(os.path.basename(outdir_abs), [])
            delete_sample_results(sample, outdir_abs, patterns, dry_run=not args.do_modify)

    for rename in changes["renamed"]:
        old_sample = rename["old_key"]
        new_sample = rename["new_key"]
        print(f"\n[重命名样本] {old_sample} -> {new_sample}")
        for outdir in args.output_dirs:
            outdir_abs = outdir if os.path.isabs(outdir) else os.path.join(os.getcwd(), outdir)
            if not os.path.exists(outdir_abs):
                continue
            patterns = sync_patterns.get(os.path.basename(outdir_abs), [])
            rename_sample_results(old_sample, new_sample, outdir_abs, patterns, dry_run=not args.do_modify)

    for sample in changes["changed"]:
        print(f"\n[内容变更，删除旧结果] {sample}")
        for outdir in args.output_dirs:
            outdir_abs = outdir if os.path.isabs(outdir) else os.path.join(os.getcwd(), outdir)
            if not os.path.exists(outdir_abs):
                continue
            patterns = sync_patterns.get(os.path.basename(outdir_abs), [])
            delete_sample_results(sample, outdir_abs, patterns, dry_run=not args.do_modify)

    if changes["added"]:
        print(f"\n[新增样本，等待下游处理] {changes['added']}")

    # 准备当前 prefix -> sample 列表，用于更新 sample.txt 与 samples_to_process.txt
    current_prefix_sample = sorted(mapping.items(), key=lambda x: x[1])

    # 更新 sample.txt：保留已有顺序，追加新增，删除已消失，更新重命名
    if args.do_modify:
        update_sample_txt(sample_txt_path, current_prefix_sample)
        print(f"\n[SAVED] sample.txt 已更新: {sample_txt_path}")
    else:
        print("\n[只扫描] sample.txt 将更新为：")
        for prefix, sample in current_prefix_sample:
            print(f"  {prefix}\t{sample}")

    # 生成待处理清单
    to_process = sorted(set(changes["added"] + changes["changed"]))
    target = os.path.join(metadatadir, "samples_to_process.txt")
    if to_process:
        lines = ["fastqfile\tsample\n"]
        for prefix, sample in current_prefix_sample:
            if sample in to_process:
                lines.append(f"{prefix}\t{sample}\n")
        if args.do_modify:
            with open(target, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"\n[SAVED] {target}")
        else:
            print(f"\n[只扫描] 将生成: {target}")
            print("".join(lines).strip())
    else:
        # 没有需要处理的样本时，清理旧的待处理清单，避免误导下游流程
        if args.do_modify:
            if os.path.exists(target):
                os.remove(target)
                print(f"\n[REMOVED] {target}（无新增/变更样本）")
        else:
            if os.path.exists(target):
                print(f"\n[只扫描] 将删除: {target}（无新增/变更样本）")

    # 更新 manifest
    if args.do_modify:
        for sample, entry in current_entries.items():
            mm.record_stage("rawdata", sample, entry["file_paths"],
                            input_samples=entry["input_samples"],
                            is_merged=entry["is_merged"],
                            use_md5=use_md5)
        # 清理已删除或已重命名走的旧条目
        rawdata_stage = mm.get_stage("rawdata")
        for old_sample in list(rawdata_stage.keys()):
            if old_sample not in current_entries:
                del rawdata_stage[old_sample]
        mm._update_sample_list()
        # rawdata stage 是完整扫描结果，需要替换整个 stage
        mm.save(replace_stages=["rawdata"])
        print(f"\n[SAVED] manifest 已更新: {mm.manifest_path}")
    else:
        print(f"\n[只扫描] manifest 未更新。如需执行，请加上 --do-modify")


# ---------------------------------------------------------------------------
# 命令：check-input-with-raw（增量式多路径/多批次 FASTQ 核对入口）
# ---------------------------------------------------------------------------
def cmd_check_input_with_raw(args):
    """
    增量式 check_input_with_raw。

    设计目标：
      1. 只读扫描一个或多个 FASTQ 目录，计算 size / mtime / MD5 指纹。
      2. 与 .sample_manifest.json 中的 rawdata stage 做对比，自动识别：
         - 新增样本（added）
         - 删除样本（deleted）
         - 内容变更（changed）
         - 重命名（renamed，按文件指纹匹配）
         - 未变更（unchanged）
      3. 支持为每个扫描目录标注“批次名”（如 batch1、batch2），实现不同路径/批次整合。
      4. 使用 task_id 标记本次录入，便于后续追溯“哪个 task 产生了/更新了哪些文件”。
      5. 可选 --scan-only（只扫描）：只检测不写入；否则自动补充 sample.txt、sample-metadata.tsv
         和 manifest。

    使用示例：
        # 第一次：扫描 batch1
        python sample_double_check.py check-input-with-raw \
            --fastq-dirs rawdata/batch1:batch1 \
            --metadatadir metadata \
            --task-id run_001

        # 客户新增 batch2 后再运行：自动检测 T-1/T-2 并补充
        python sample_double_check.py check-input-with-raw \
            --fastq-dirs rawdata/batch1:batch1 rawdata/batch2:batch2 \
            --metadatadir metadata \
            --task-id run_002

        # 只检测不写入
        python sample_double_check.py check-input-with-raw \
            --fastq-dirs rawdata/batch1:batch1 rawdata/batch2:batch2 \
            --metadatadir metadata \
            --scan-only
    """
    metadatadir = os.path.abspath(args.metadatadir)
    os.makedirs(metadatadir, exist_ok=True)
    sample_txt = os.path.join(metadatadir, "sample.txt")
    metadata_tsv = os.path.join(metadatadir, "sample-metadata.tsv")
    task_id = args.task_id or f"check_input_with_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    mm = ManifestManager(metadatadir)
    previous_files = mm.get_previous_files()
    dirs = parse_fastq_dirs(args.fastq_dirs)

    # 1) 扫描所有目录
    all_batch_samples = {}
    print("\n" + "=" * 70)
    print("FASTQ 目录扫描")
    print("=" * 70)
    for d, batch in dirs:
        samples, unmatched = scan_batch(d, batch, previous_files, args.fastq_patterns)
        all_batch_samples[batch] = samples
        print(f"  [{batch}] {d}: {len(samples)} 个样本")
        for prefix, info in sorted(samples.items()):
            print(f"      {prefix} -> R1={os.path.basename(info['paths']['R1'])}, "
                  f"R2={os.path.basename(info['paths']['R2'])}")
        if unmatched:
            print(f"      ⚠️ 未成功配对的样本前缀: {unmatched}")

    # 2) 读取已有 sample.txt 映射
    mapping = load_sample_mapping(sample_txt)

    # 3) 构建 current_entries，同时记录 prefix -> sample
    current_entries = {}
    sample_prefix = {}
    for batch, prefixes in all_batch_samples.items():
        for prefix, info in sorted(prefixes.items()):
            sample = prefix_to_sample(prefix, mapping)
            if sample in current_entries:
                raise ValueError(
                    f"样本 {sample} 在多个批次/路径中出现，请检查命名冲突或手动指定映射"
                )
            sample_prefix[sample] = prefix
            current_entries[sample] = {
                "files": info["files"],
                "file_paths": list(info["paths"].values()),
                "input_samples": [sample],
                "is_merged": False,
            }
            # 把路径/批次/task_id 放入 metadata，便于后续追溯
            current_entries[sample]["metadata"] = {
                "task_id": task_id,
                "batch": batch,
                "paths": info["paths"],
                "recorded_at": datetime.now().isoformat(),
            }

    # 4) 与 manifest 对比
    changes = mm.detect_changes("rawdata", current_entries)

    # 5) 输出报告
    print("\n" + "=" * 70)
    print("原始 FASTQ 增量核对报告")
    print("=" * 70)
    print(f"task_id: {task_id}")
    print(f"当前样本总数: {len(current_entries)}")
    print(f"  未变更 : {len(changes['unchanged'])}  {changes['unchanged']}")
    print(f"  新增   : {len(changes['added'])}    {changes['added']}")
    print(f"  删除   : {len(changes['deleted'])}    {changes['deleted']}")
    print(f"  重命名 : {len(changes['renamed'])}    ", end="")
    if changes['renamed']:
        print(", ".join([f"{r['old_key']} -> {r['new_key']}" for r in changes['renamed']]))
    else:
        print("无")
    print(f"  内容变更: {len(changes['changed'])}  {changes['changed']}")
    print("=" * 70)

    # 6) 保留未变更样本的原始 task_id，实现“哪个 task 产生了这个文件”可追溯
    previous_raw = mm.get_stage("rawdata")
    for sample in changes["unchanged"]:
        prev_meta = previous_raw.get(sample, {}).get("metadata", {})
        if prev_meta.get("task_id"):
            current_entries[sample]["metadata"]["task_id"] = prev_meta["task_id"]
            current_entries[sample]["metadata"]["batch"] = prev_meta.get("batch")

    # 7) 写入文件（如果不是只扫描模式）
    if args.scan_only:
        print("\n[只扫描] 未修改 sample.txt / sample-metadata.tsv / manifest")
        return

    # 读取已有的 metadata 分组，便于在重写时保留未变更/重命名样本的分组
    existing_groups = {}
    if os.path.exists(metadata_tsv):
        with open(metadata_tsv, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("sample-id") or stripped.startswith("#q2:types"):
                    continue
                parts = stripped.split("\t")
                if len(parts) >= 2:
                    existing_groups[parts[0]] = parts[1]

    # 重命名样本的分组继承旧名
    rename_group_map = {}
    for r in changes["renamed"]:
        old_key = r["old_key"]
        new_key = r["new_key"]
        if old_key in existing_groups:
            rename_group_map[new_key] = existing_groups[old_key]

    # 构建当前 sample.txt 与 metadata 内容
    current_prefix_sample = []
    current_sample_group = []
    for sample in sorted(current_entries.keys()):
        current_prefix_sample.append((sample_prefix[sample], sample))
        group = existing_groups.get(sample) or rename_group_map.get(sample) or args.default_group
        current_sample_group.append((sample, group))

    n_txt = rewrite_sample_txt(sample_txt, current_prefix_sample)
    n_meta = rewrite_metadata(metadata_tsv, current_sample_group)

    # 更新 manifest
    for sample, entry in current_entries.items():
        mm.record_stage(
            "rawdata",
            sample,
            entry["file_paths"],
            input_samples=entry["input_samples"],
            is_merged=entry["is_merged"],
            metadata=entry["metadata"],
        )

    # 清理已删除或已重命名走的旧条目，避免残留条目反复被报为 deleted
    rawdata_stage = mm.get_stage("rawdata")
    for old_sample in list(rawdata_stage.keys()):
        if old_sample not in current_entries:
            del rawdata_stage[old_sample]
    mm._update_sample_list()

    # rawdata stage 是完整扫描结果，需要替换整个 stage，删除已不存在的旧条目
    mm.save(replace_stages=["rawdata"])

    print(f"\n[SAVED] sample.txt 已重写为 {n_txt} 条")
    print(f"[SAVED] sample-metadata.tsv 已重写为 {n_meta} 条")
    print(f"[SAVED] manifest: {mm.manifest_path}")


# ---------------------------------------------------------------------------
# 扫描日志工具函数
# ---------------------------------------------------------------------------
def get_scan_log_path(scan_dir, log_dir=".", task_id=None):
    """计算扫描日志文件路径（基于当前时间戳），不实际写入。
    文件名时间戳格式：YYYY-MM-DD_HH-MM-SS（年月日_时分秒，便于阅读）。
    返回可见的 .txt 输出文件路径；对应的隐藏结构化 .json 文件通过
    _get_hidden_json_path() 获得。
    """
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    basename = os.path.basename(os.path.normpath(scan_dir))
    parts = ["scan_log", basename]
    if task_id:
        parts.append(task_id)
    parts.append(timestamp)
    filename = "_".join(parts) + ".txt"
    return os.path.join(log_dir, filename)


def _get_hidden_json_path(txt_path):
    """根据可见的 .txt 路径，得到隐藏的结构化 .json 路径（同目录，点前缀）。"""
    directory = os.path.dirname(txt_path)
    base = os.path.basename(txt_path)  # e.g. scan_log_case1_2026-06-23_23-40-07.txt
    json_name = "." + base.replace(".txt", ".json")
    return os.path.join(directory, json_name)


def save_scan_log(scan_dir, files_data, output_text, log_dir=".", task_id=None,
                  filepath=None, comparison=None):
    """
    保存扫描结果到文件：
      - 可见的 .txt 文件：内容与控制台输出完全一致，便于人工查看。
      - 隐藏的同名的 .json 文件：保存结构化数据（files、comparison），
        供下次扫描时做历史对比使用。
    返回保存的可见 .txt 文件路径。
    """
    if filepath is None:
        filepath = get_scan_log_path(scan_dir, log_dir, task_id)

    # 1. 保存可读的 .txt 输出文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(output_text)

    # 2. 保存隐藏的结构化 .json 文件，用于后续对比
    json_path = _get_hidden_json_path(filepath)
    data = {
        "version": 1,
        "scan_dir": os.path.abspath(scan_dir),
        "scan_dir_basename": os.path.basename(os.path.normpath(scan_dir)),
        "scanned_at": datetime.now().isoformat(),
        "files": files_data,
        "comparison": comparison or {"status": "first_scan"},
        "output": output_text,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


def load_latest_scan_log(scan_dir, log_dir="."):
    """
    从当前目录（或指定目录）加载同一扫描目录的最新隐藏结构化日志（.json）。
    没有找到返回 None。
    """
    if not os.path.isdir(log_dir):
        return None
    basename = os.path.basename(os.path.normpath(scan_dir))
    # 隐藏 json 文件名以 .scan_log_ 开头
    pattern = f".scan_log_{basename}_*.json"
    files = [f for f in os.listdir(log_dir) if fnmatch.fnmatch(f, pattern)]
    if not files:
        return None
    # 按文件名降序，时间戳在最后的通常最大
    files.sort(reverse=True)
    latest = os.path.join(log_dir, files[0])
    try:
        with open(latest, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def compare_scan_logs(current_files, previous_files):
    """
    对比两次扫描结果，返回 added/deleted/renamed/changed/unchanged。
    current_files / previous_files: {rel_path: fingerprint}
    """
    current_keys = set(current_files.keys())
    previous_keys = set(previous_files.keys())

    unchanged = []
    changed = []
    for key in current_keys & previous_keys:
        if ManifestManager._files_equal(
            {key: current_files[key]}, {key: previous_files[key]}
        ):
            unchanged.append(key)
        else:
            changed.append(key)

    added_keys = list(current_keys - previous_keys - set(changed))
    deleted_keys = list(previous_keys - current_keys)

    # 重命名检测：按内容指纹匹配
    renamed = []
    remaining_added = []
    deleted_index = defaultdict(list)
    for old_key in deleted_keys:
        fp = previous_files[old_key]
        fp_key = ManifestManager._files_fingerprint_key({old_key: fp})
        deleted_index[fp_key].append(old_key)

    for new_key in added_keys:
        fp = current_files[new_key]
        fp_key = ManifestManager._files_fingerprint_key({new_key: fp})
        candidates = deleted_index.get(fp_key, [])
        if candidates:
            old_key = candidates.pop(0)
            renamed.append({"old_key": old_key, "new_key": new_key})
        else:
            remaining_added.append(new_key)

    return {
        "added": sorted(remaining_added),
        "deleted": sorted([k for k in deleted_keys if k not in [r["old_key"] for r in renamed]]),
        "renamed": renamed,
        "changed": sorted(changed),
        "unchanged": sorted(unchanged),
    }


# ---------------------------------------------------------------------------
# 命令：scan-dir（指定任意目录，读取并输出其中所有文件信息）
# ---------------------------------------------------------------------------
def scan_directory(scan_dir, batch, previous_files=None, recursive=False, pattern=None):
    """
    通用目录扫描：读取目录下所有文件（不限于 FASTQ），计算指纹。

    参数：
      scan_dir: 要扫描的目录
      batch: 批次名
      previous_files: 缓存的指纹，用于 MD5 加速
      recursive: 是否递归扫描子目录
      pattern: glob 过滤模式，如 "*.fastq.gz"；None 表示不过滤

    返回：
      files: {relative_path: fingerprint}
      abs_paths: [absolute_path, ...]
      metadata: {dir, batch, files_info: {rel: abs}}
    """
    if recursive:
        walk_iter = os.walk(scan_dir)
    else:
        walk_iter = [(scan_dir, [], [f for f in os.listdir(scan_dir)
                                      if os.path.isfile(os.path.join(scan_dir, f))])]

    file_dict = {}
    abs_paths = []
    files_info = {}

    # 需要排除的元数据/记录文件（由 sample_double_check 自身或其他检查步骤生成）
    EXCLUDED_PATTERNS = [
        '.sample_manifest.json',        # manifest 文件自身
        '.sample_manifest.json.lock',   # manifest 文件锁
    ]
    EXCLUDED_PREFIXES = [
        '.scan_log_',                   # 隐藏的扫描日志 JSON
        '.tmp.',                        # 原子写入临时文件
    ]
    EXCLUDED_SUFFIXES = []  # 不再盲目排除所有 .txt/.json，仅排除已知的元数据文件

    for root, dirs, files in walk_iter:
        for filename in sorted(files):
            if pattern and not fnmatch.fnmatch(filename, pattern):
                continue
            # 跳过元数据/记录文件
            if filename in EXCLUDED_PATTERNS:
                continue
            if any(filename.startswith(p) for p in EXCLUDED_PREFIXES):
                continue
            if any(filename.endswith(s) for s in EXCLUDED_SUFFIXES):
                continue
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, scan_dir)
            file_dict[rel_path] = abs_path
            abs_paths.append(abs_path)
            files_info[rel_path] = abs_path

    fingerprints = fingerprint_files(file_dict, previous_files, use_md5=True)
    metadata = {
        "dir": os.path.abspath(scan_dir),
        "batch": batch,
        "files_info": files_info,
    }
    return fingerprints, abs_paths, metadata


def cmd_scan_dir(args):
    """
    用户指定任意目录路径，程序读取该目录下的所有文件并输出信息。

    特点：
      - 不限于 FASTQ，任意文件类型均可扫描。
      - 自动保存扫描日志到当前目录（或 --log-dir 指定目录），文件名带时间戳。
        可见文件为 .txt（内容与控制台输出一致），同名隐藏 .json 保存结构化对比数据。
        文件名时间戳格式：YYYY-MM-DD_HH-MM-SS（年月日_时分秒）。
      - 自动读取同一目录的历史扫描日志，对比输出新增/删除/重命名/变更的文件。
      - 首次扫描会标注为"首次扫描"。
      - 控制台和 JSON 中，mtime（修改时间）均以 YYYY-MM-DD HH:MM:SS 的本地时间显示。

    使用示例：
        # 扫描并保存日志
        python sample_double_check.py scan-dir \
            --dir /path/to/any_folder

        # 只扫描 .fastq.gz 文件
        python sample_double_check.py scan-dir \
            --dir /path/to/any_folder \
            --pattern "*.fastq.gz"

        # 指定日志保存目录
        python sample_double_check.py scan-dir \
            --dir /path/to/any_folder \
            --log-dir logs
    """
    scan_dir = os.path.abspath(args.dir)
    if not os.path.isdir(scan_dir):
        print(f"[ERROR] 目录不存在: {scan_dir}", file=sys.stderr)
        sys.exit(1)

    batch = args.batch or os.path.basename(os.path.normpath(scan_dir))
    log_dir = os.path.abspath(args.log_dir) if args.log_dir else "."

    # 扫描目录
    fingerprints, abs_paths, scan_metadata = scan_directory(
        scan_dir, batch, previous_files=None, recursive=args.recursive, pattern=args.pattern
    )

    # 构建输出文本（同时用于控制台输出和保存到 JSON）
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("目录文件扫描结果")
    lines.append("=" * 70)
    lines.append(f"扫描目录: {scan_dir}")
    lines.append(f"批次名称: {batch}")
    lines.append(f"文件总数: {len(fingerprints)}")
    if args.pattern:
        lines.append(f"过滤模式: {args.pattern}")
    if args.recursive:
        lines.append("递归扫描: 是")
    lines.append("-" * 70)

    for rel_path in sorted(fingerprints.keys()):
        fp = fingerprints[rel_path]
        abs_path = scan_metadata["files_info"][rel_path]
        lines.append("")
        lines.append(f"文件: {rel_path}")
        lines.append(f"  绝对路径: {abs_path}")
        lines.append(f"  大小: {fp['size']} bytes")
        lines.append(f"  类型: {fp['file_type']}")
        lines.append(f"  压缩: {'是' if fp['is_compressed'] else '否'}")
        lines.append(f"  MD5 : {fp['md5']}")
        lines.append(f"  修改时间（mtime）: {fp['mtime_human']}")

    # 与历史扫描日志对比
    previous_log = load_latest_scan_log(scan_dir, log_dir)
    lines.append("")
    lines.append("=" * 70)
    lines.append("与历史扫描日志对比")
    lines.append("=" * 70)

    if previous_log is None:
        lines.append("状态: 首次扫描，无历史扫描日志可比较")
        lines.append("  新增   : 无")
        lines.append("  删除   : 无")
        lines.append("  重命名 : 无")
        lines.append("  内容变更: 无")
        comparison = {
            "status": "first_scan",
            "previous_log_scanned_at": None,
            "unchanged": [],
            "added": [],
            "deleted": [],
            "renamed": [],
            "changed": [],
        }
    else:
        lines.append(f"对比日志: {previous_log.get('scanned_at', '未知时间')}")
        previous_files = previous_log.get("files", {})
        changes = compare_scan_logs(fingerprints, previous_files)
        lines.append(f"  未变更 : {len(changes['unchanged'])}  {changes['unchanged']}")
        lines.append(f"  新增   : {len(changes['added'])}    {changes['added'] if changes['added'] else '无'}")
        lines.append(f"  删除   : {len(changes['deleted'])}    {changes['deleted'] if changes['deleted'] else '无'}")
        rename_str = ", ".join([f"{r['old_key']} -> {r['new_key']}" for r in changes['renamed']]) if changes['renamed'] else "无"
        lines.append(f"  重命名 : {len(changes['renamed'])}    {rename_str}")
        lines.append(f"  内容变更: {len(changes['changed'])}  {changes['changed'] if changes['changed'] else '无'}")
        comparison = {
            "status": "compared",
            "previous_log_scanned_at": previous_log.get("scanned_at"),
            "unchanged": changes["unchanged"],
            "added": changes["added"],
            "deleted": changes["deleted"],
            "renamed": changes["renamed"],
            "changed": changes["changed"],
        }
    lines.append("=" * 70)

    # 保存扫描日志：可见 .txt（控制台输出）+ 隐藏 .json（结构化对比数据）
    if not args.no_log:
        log_path = get_scan_log_path(scan_dir, log_dir, task_id=args.task_id)
        lines.append(f"\n[SAVED] 扫描日志: {log_path}")
        output_text = "\n".join(lines)
        save_scan_log(scan_dir, fingerprints, output_text, log_dir, task_id=args.task_id,
                      filepath=log_path, comparison=comparison)
    else:
        lines.append("\n[SKIP] 未保存扫描日志（--no-log）")
        output_text = "\n".join(lines)

    print(output_text)


# ---------------------------------------------------------------------------
# 命令：record-stage（库/CLI 通用：记录任意 stage）
# ---------------------------------------------------------------------------
def cmd_record_stage(args):
    mm = ManifestManager(args.metadatadir)
    file_dict = {}
    for item in args.files:
        if "=" in item:
            logical, real = item.split("=", 1)
            file_dict[logical.strip()] = real.strip()
        else:
            file_dict[item.strip()] = item.strip()
    if args.skip_missing:
        existing = {}
        for logical, real in file_dict.items():
            if os.path.exists(real):
                existing[logical] = real
            else:
                print(f"[SKIP] 文件不存在，跳过: {real}", file=sys.stderr)
        file_dict = existing
    mm.record_stage(
        args.stage,
        args.key,
        file_dict,
        input_samples=args.input_samples,
        is_merged=args.merged,
        use_md5=not args.no_md5,
        metadata=args.metadata,
    )
    mm.save()
    print(f"[SAVED] stage={args.stage}, key={args.key}, files={len(file_dict)}")


# ---------------------------------------------------------------------------
# 命令：show（查看 manifest 内容）
# ---------------------------------------------------------------------------
def cmd_show(args):
    mm = ManifestManager(args.metadatadir)
    data = mm.data
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 命令：lineage（查看某个样本的完整谱系）
# ---------------------------------------------------------------------------
def cmd_lineage(args):
    mm = ManifestManager(args.metadatadir)
    lineage = mm.get_sample_lineage(args.sample)
    print(json.dumps(lineage, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 命令：show-task-map（查看 task_id -> 文件路径映射）
# ---------------------------------------------------------------------------
def cmd_show_task_map(args):
    """
    从 manifest 中提取 task_id -> 文件路径 的映射关系。
    等价于原 show_task_map.py 的功能，已并入 sample_double_check.py。
    """
    mm = ManifestManager(args.metadatadir)
    data = mm.data

    task_map = defaultdict(list)
    for stage_name, stage_data in data.get("stages", {}).items():
        for key, entry in stage_data.items():
            task_id = entry.get("metadata", {}).get("task_id", "__unknown__")
            for logical_path, real_path in entry.get("metadata", {}).get("paths", {}).items():
                task_map[task_id].append((stage_name, key, logical_path, real_path))
            # 兜底：如果 metadata.paths 没有，尝试 files 的 key
            if not entry.get("metadata", {}).get("paths"):
                for real_path in entry.get("files", {}).keys():
                    task_map[task_id].append((stage_name, key, "-", real_path))

    print("\n" + "=" * 70)
    print("task_id -> 文件路径 映射")
    print("=" * 70)
    for task_id in sorted(task_map.keys()):
        print(f"\ntask_id: {task_id}")
        for stage, key, logical, real in sorted(task_map[task_id]):
            print(f"  {stage} / {key} / {logical} -> {real}")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="宏基因组样本核对与全阶段文件指纹管理")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # data-check（原始 FASTQ 核对入口）
    p_data = subparsers.add_parser("data-check", help="核对原始 FASTQ 样本变更")
    p_data.add_argument("-i", "--rawdatadir", required=True, help="原始 fastq 数据目录")
    p_data.add_argument("-I", "--metadatadir", required=True, help="元数据目录")
    p_data.add_argument("--manifest", default=None, help="manifest 路径")
    p_data.add_argument("--output-dirs", nargs="+", default=[],
                        help="需要同步的下游结果目录")
    p_data.add_argument("--sync-config", default=None, help="自定义同步模式 JSON")
    p_data.add_argument("--do-modify", dest="do_modify", action="store_true",
                        help="执行修改：同步下游结果目录并更新 manifest（默认只扫描不修改）")
    p_data.add_argument("--no-md5", action="store_true", help="不使用 MD5")
    p_data.add_argument("--fastq-patterns", nargs="+", default=None,
                        help="自定义 FASTQ 配对模式")
    p_data.add_argument("--force", nargs="+", default=[],
                        help="强制重处理指定样本")
    p_data.set_defaults(func=cmd_check_raw)

    # check-input-with-raw
    p_input = subparsers.add_parser("check-input-with-raw",
                                    help="增量式多路径/多批次 FASTQ 核对（check_input_with_raw）")
    p_input.add_argument("--fastq-dirs", nargs="+", required=True,
                         help="FASTQ 目录，可带批次名如 /path/to/raw:batch1")
    p_input.add_argument("-I", "--metadatadir", required=True,
                         help="元数据输出目录（存放 sample.txt、manifest 等）")
    p_input.add_argument("--task-id", default=None,
                         help="本次录入的 task ID，默认生成 check_input_with_raw_<时间戳>")
    p_input.add_argument("--default-group", default="新增组",
                         help="新增样本默认分组名")
    p_input.add_argument("--scan-only", "--dry-run", dest="scan_only", action="store_true",
                         help="只扫描：只检测并打印报告，不修改 sample.txt、metadata、manifest")
    p_input.add_argument("--fastq-patterns", nargs="+", default=None,
                         help="自定义 FASTQ 配对模式")
    p_input.set_defaults(func=cmd_check_input_with_raw)

    # scan-dir
    p_scan = subparsers.add_parser("scan-dir",
                                   help="指定任意目录，读取并输出其中所有文件的信息，并保存扫描日志")
    p_scan.add_argument("--dir", required=True,
                        help="要扫描的目录路径")
    p_scan.add_argument("--batch", default=None,
                        help="批次名/条目名，默认取目录 basename")
    p_scan.add_argument("--pattern", default=None,
                        help="glob 过滤模式，如 '*.fastq.gz'，默认不过滤")
    p_scan.add_argument("--recursive", action="store_true",
                        help="递归扫描子目录")
    p_scan.add_argument("--log-dir", default=None,
                        help="扫描日志保存目录，默认当前目录")
    p_scan.add_argument("--task-id", default=None,
                        help="扫描日志标识，会加入文件名")
    p_scan.add_argument("--no-log", action="store_true",
                        help="不保存扫描日志")
    p_scan.set_defaults(func=cmd_scan_dir)

    # record-stage
    p_record = subparsers.add_parser("record-stage", help="记录任意阶段的文件指纹")
    p_record.add_argument("-I", "--metadatadir", required=True, help="元数据目录")
    p_record.add_argument("--stage", required=True, help="阶段名")
    p_record.add_argument("--key", required=True, help="条目标识（如样本名或 all）")
    p_record.add_argument("--files", nargs="+", required=True,
                          help="文件路径，可带逻辑名如 name=/path/to/file")
    p_record.add_argument("--input-samples", nargs="*", default=[],
                          help="输入样本列表")
    p_record.add_argument("--merged", action="store_true",
                          help="标记为合并产生的文件")
    p_record.add_argument("--no-md5", action="store_true", help="不使用 MD5")
    p_record.add_argument("--metadata", type=json.loads, default=None,
                          help="JSON 格式的额外元数据")
    p_record.add_argument("--skip-missing", action="store_true",
                          help="跳过不存在的文件（不报错）")
    p_record.set_defaults(func=cmd_record_stage)

    # show
    p_show = subparsers.add_parser("show", help="查看 manifest 内容")
    p_show.add_argument("-I", "--metadatadir", required=True, help="元数据目录")
    p_show.set_defaults(func=cmd_show)

    # lineage
    p_lineage = subparsers.add_parser("lineage", help="查看某个样本的完整谱系")
    p_lineage.add_argument("-I", "--metadatadir", required=True, help="元数据目录")
    p_lineage.add_argument("--sample", required=True, help="样本名")
    p_lineage.set_defaults(func=cmd_lineage)

    # show-task-map
    p_taskmap = subparsers.add_parser("show-task-map",
                                      help="查看 manifest 中的 task_id 到文件路径映射")
    p_taskmap.add_argument("-I", "--metadatadir", required=True, help="元数据目录")
    p_taskmap.set_defaults(func=cmd_show_task_map)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
