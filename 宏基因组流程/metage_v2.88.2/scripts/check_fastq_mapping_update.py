#!/usr/bin/env python3
import os
import re
import sys
import time
import argparse
import pandas as pd
from pathlib import Path
from typing import Set, List, Tuple

# =========================
# 1. 命令行参数解析
# =========================
def parse_args():
    parser = argparse.ArgumentParser(
        description="验证 fastq 文件与 mapping/metadata 的一致性",
        epilog="示例: python check_fastq_mapping.py /path/to/fastq /path/to/sample.txt /path/to/metadata.tsv"
    )
    parser.add_argument(
        "fastq_dir",
        type=str,
        help="fastq 文件所在目录"
    )
    parser.add_argument(
        "mapping_file",
        type=str,
        help="样本映射文件 (sample.txt)，包含 fastqfile 和 samples 列"
    )
    parser.add_argument(
        "metadata_file",
        type=str,
        help="样本元数据文件 (sample-metadata.tsv)，包含 sample-id 列"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细信息"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="将验证结果输出到指定文件"
    )
    parser.add_argument(
        "--allow-extra-fastq",
        action="store_true",
        help="允许 FASTQ 目录包含 mapping 之外的样本（用于只处理新增样本的增量模式）"
    )
    return parser.parse_args()


# =========================
# 2. 提取样本基名
# =========================
def extract_sample_name(filename: str) -> str:
    """
    从 fastq 文件名中提取样本基名，去掉尾部的配对标记。
    
    示例:
        CK_1_R1.fq.gz  -> CK_1
        sample-R1.fastq -> sample
        sample_R2.fq    -> sample
    """
    name = filename
    
    # 1) 去掉 .gz
    if name.endswith('.gz'):
        name = name[:-3]
    
    # 2) 去掉 .fastq 或 .fq
    for ext in ('.fastq', '.fq'):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break
    
    # 3) 去掉末尾的配对标记
    #   支持: _R1/_R2, -R1/-R2, _1/_2, -1/-2
    base = re.sub(r'([_\-\.](?:R?[12]))$', '', name)
    return base


# =========================
# 3. 查找列名（容错）
# =========================
def find_col(df, candidates: List[str]) -> str:
    """在 DataFrame 中查找列名，支持忽略大小写"""
    for c in candidates:
        if c in df.columns:
            return c
    # 忽略大小写匹配
    lower_map = {col.lower(): col for col in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


# =========================
# 4. 加载并解析 fastq 文件
# =========================
def load_fastq_files(fastq_dir: str, verbose: bool = False) -> Set[str]:
    """扫描 fastq 目录，返回所有样本基名"""
    if not os.path.isdir(fastq_dir):
        print(f"❌ 错误: fastq 目录不存在: {fastq_dir}")
        sys.exit(1)
    
    # 支持的 fastq 扩展名
    fastq_exts = (".fq", ".fq.gz", ".fastq", ".fastq.gz")
    fastq_files = [f for f in os.listdir(fastq_dir) 
                   if f.lower().endswith(fastq_exts)]
    
    if not fastq_files:
        print(f"⚠️  警告: 在 {fastq_dir} 中未找到 fastq 文件")
        return set()
    
    if verbose:
        print(f"📁 找到 {len(fastq_files)} 个 fastq 文件")
    
    fastq_sample_names = set()
    for f in fastq_files:
        base = extract_sample_name(f)
        if base:
            fastq_sample_names.add(base)
            if verbose:
                print(f"   {f} -> {base}")
    
    return fastq_sample_names


# =========================
# 5. 加载 mapping 文件
# =========================
def load_mapping_file(mapping_file: str) -> Tuple[pd.DataFrame, str, str]:
    """加载并解析 mapping 文件"""
    if not os.path.isfile(mapping_file):
        print(f"❌ 错误: mapping 文件不存在: {mapping_file}")
        sys.exit(1)
    
    # 自动检测分隔符
    map_df = pd.read_csv(mapping_file, sep=None, engine='python')
    
    # 查找列名
    fastq_col = find_col(map_df, ['fastqfile', 'fastq_file', 'fastq', 'fastq_file_name'])
    sample_col = find_col(map_df, ['samples', 'sample', 'sample-id', 'sample_id'])
    
    if fastq_col is None or sample_col is None:
        print("❌ 错误: mapping 文件缺少 'fastqfile' 或 'samples' 列")
        print(f"   实际列名: {list(map_df.columns)}")
        sys.exit(1)
    
    return map_df, fastq_col, sample_col


# =========================
# 6. 加载 metadata 文件
# =========================
def load_metadata_file(metadata_file: str) -> Tuple[pd.DataFrame, str]:
    """加载并解析 metadata 文件"""
    if not os.path.isfile(metadata_file):
        print(f"❌ 错误: metadata 文件不存在: {metadata_file}")
        sys.exit(1)
    
    # 读取 metadata（跳过注释行）
    meta_df = pd.read_csv(metadata_file, sep='\t', comment='#', engine='python')
    
    # 查找 sample-id 列
    meta_sample_col = find_col(meta_df, ['sample-id', 'sample_id', 'sample', 'sampleid'])
    
    if meta_sample_col is None:
        print(f"❌ 错误: metadata 文件缺少 'sample-id' 列")
        print(f"   实际列名: {list(meta_df.columns)}")
        sys.exit(1)
    
    return meta_df, meta_sample_col


# =========================
# 7. 执行验证
# =========================
def validate(
    fastq_bases: Set[str],
    map_df: pd.DataFrame,
    fastq_col: str,
    sample_col: str,
    meta_df: pd.DataFrame,
    meta_sample_col: str,
    allow_extra_fastq: bool = False
) -> Tuple[bool, List[str], List[str], List[str], List[str]]:
    """执行验证，返回 (是否通过, 缺失fastq, 多余fastq, 缺失样本, 多余样本)"""
    
    # 获取 mapping 中的 fastq 列表
    map_fastq_bases = list(map_df[fastq_col].astype(str).tolist())
    
    # 获取 mapping 中的样本列表
    map_samples = list(map_df[sample_col].astype(str).tolist())
    
    # 获取 metadata 中的样本列表
    meta_samples = set(meta_df[meta_sample_col].astype(str).tolist())
    
    # 检查 fastq
    missing_fastqs = [f for f in map_fastq_bases if f not in fastq_bases]
    extra_fastqs = [f for f in fastq_bases if f not in map_fastq_bases]
    
    # 检查样本
    missing_samples = [s for s in map_samples if s not in meta_samples]
    extra_samples = [s for s in meta_samples if s not in map_samples]
    
    # 判断是否全部通过
    blocking_extra_fastqs = [] if allow_extra_fastq else extra_fastqs
    all_passed = not (missing_fastqs or blocking_extra_fastqs or missing_samples or extra_samples)
    
    return all_passed, missing_fastqs, extra_fastqs, missing_samples, extra_samples


# =========================
# 8. 输出报告
# =========================
def print_report(
    all_passed: bool,
    missing_fastqs: List[str],
    extra_fastqs: List[str],
    missing_samples: List[str],
    extra_samples: List[str],
    output_file: str = None,
    allow_extra_fastq: bool = False
):
    """打印验证报告"""
    
    lines = []
    
    if all_passed:
        lines.append("✅ All checks passed!")
        if allow_extra_fastq and extra_fastqs:
            lines.append(
                f"ℹ️  增量模式：忽略 mapping 之外的历史 FASTQ 样本: {sorted(extra_fastqs)}"
            )
    else:
        lines.append("❌ Validation failed:")
        if missing_fastqs:
            lines.append(f"  - Mapping 中这些 fastqfile 在目录中找不到匹配的 fastq: {missing_fastqs}")
        if extra_fastqs and not allow_extra_fastq:
            lines.append(f"  - 目录中存在未在 mapping 表中定义的样本: {sorted(extra_fastqs)}")
        if missing_samples:
            lines.append(f"  - Mapping 中的 sample 未在 metadata 中找到: {missing_samples}")
        if extra_samples:
            lines.append(f"  - Metadata 中存在但不在 mapping 中的 sample: {sorted(extra_samples)}")
        if allow_extra_fastq and extra_fastqs:
            lines.append(
                f"ℹ️  增量模式：忽略 mapping 之外的历史 FASTQ 样本: {sorted(extra_fastqs)}"
            )
    
    # 输出到屏幕
    for line in lines:
        print(line)
    
    # 输出到文件
    if output_file:
        with open(output_file, 'w') as f:
            f.write("\n".join(lines))
        print(f"📄 报告已保存至: {output_file}")
    
    return all_passed


# =========================
# 9. 主函数
# =========================
def main():
    start_time = time.time()
    
    # 解析参数
    args = parse_args()
    
    print("🔍 开始 fastq 映射验证...")
    
    # 加载数据
    fastq_bases = load_fastq_files(args.fastq_dir, args.verbose)
    map_df, fastq_col, sample_col = load_mapping_file(args.mapping_file)
    meta_df, meta_sample_col = load_metadata_file(args.metadata_file)
    
    if args.verbose:
        print(f"\n📊 统计:")
        print(f"   fastq 样本数: {len(fastq_bases)}")
        print(f"   mapping 条目数: {len(map_df)}")
        print(f"   metadata 样本数: {len(meta_df)}")
    
    # 执行验证
    all_passed, missing_fastqs, extra_fastqs, missing_samples, extra_samples = validate(
        fastq_bases, map_df, fastq_col, sample_col, meta_df, meta_sample_col,
        allow_extra_fastq=args.allow_extra_fastq
    )
    
    # 输出报告
    print_report(
        all_passed, missing_fastqs, extra_fastqs, missing_samples, extra_samples,
        args.output, allow_extra_fastq=args.allow_extra_fastq
    )
    
    # 耗时
    elapsed = time.time() - start_time
    print(f"⏱️  耗时: {elapsed:.3f} 秒")
    
    # 退出码
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
