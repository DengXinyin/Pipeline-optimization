# COG 数据库调研与宏基因组流程整合资料

本文件夹整理了宏基因组（metage_megahit）流程中关于 COG 数据库的调研资料、注释脚本和流程图表。

## 文件说明

| 文件 | 说明 |
|------|------|
| `宏基因组分析流程说明.docx` | 完整的宏基因组流程说明文档，末尾包含 COG 数据库调研报告（含官方链接、版本说明、下载方法、注释工具、脚本示例） |
| `cog_annotate.py` | 基于 DIAMOND 比对结果和 NCBI COG2024 定义文件，将基因映射到 COG 功能类别的 Python 脚本 |
| `宏基因组分析流程图.png` | 宏基因组分析主干流程图（高清图片） |
| `宏基因组分析流程图.pptx` | 宏基因组分析主干流程图 PPT（共 2 页） |

## 快速使用

### 1. 使用 eggNOG-mapper 获取 COG 注释（推荐）

```bash
emapper.py -m diamond \
    -i unique_gene.faa \
    --itype proteins \
    --data_dir /path/to/eggnog-data \
    -o metagenome_cog \
    --output_dir ./eggnog_results/ \
    --cpu 20
```

### 2. 使用 DIAMOND + 自建 COG2024 数据库

```bash
# 下载并解压 COG2024 蛋白序列
mkdir -p ~/COG2024 && cd ~/COG2024
curl -O https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/COGorg24.faa.gz
curl -O https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/cog-24.def.tab
curl -O https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/cog-24.fun.tab
gunzip COGorg24.faa.gz

# 建库并比对
diamond makedb --in COGorg24.faa --db COG2024.dmnd
diamond blastp -d COG2024.dmnd -q unique_gene.faa -o cog_diamond_out.m8 \
    -e 1e-5 -k 1 --sensitive --threads 20 \
    --outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore stitle

# 用 cog_annotate.py 映射到 COG 功能类别
python cog_annotate.py cog_diamond_out.m8 cog-24.def.tab cog-24.fun.tab gene_cog_annotation.tsv
```

## 主要参考链接

- NCBI COG 主页：https://www.ncbi.nlm.nih.gov/research/COG
- NCBI COG2024 论文：https://academic.oup.com/nar/article/53/D1/D356/7874847
- NCBI CDD Batch CD-Search：https://www.ncbi.nlm.nih.gov/Structure/bwrpsb/bwrpsb.cgi
- eggNOG-mapper：https://github.com/eggnogdb/eggnog-mapper
- COG2024 FTP：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/

## 说明

COG 最适合汇入到现有 metage_megahit 工作流的 `func_anno`（功能注释）和 `func_base`（功能基础统计）两个 Task 中。由于 `func_anno` 使用的 eggNOG-mapper 输出已包含 COG 分类信息，通常无需额外新增 Task；如需独立控制 COG 数据库版本，可参照 `VCA_anno` / `MBQ_anno` 的模式新增独立 COG 注释步骤。
