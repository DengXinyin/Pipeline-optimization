# COG 蛋白质直系同源簇（Clusters of Orthologous Genes）

> COG 是 NCBI 维护的蛋白质直系同源簇数据库，广泛应用于宏基因组功能注释与分类统计。本文件夹整理了宏基因组（metage_megahit）流程中关于 COG 数据库的调研资料、注释脚本、流程图表以及与 eggNOG-mapper 的整合脚本。

## 文件说明

| 文件 | 说明 |
|------|------|
| `宏基因组分析流程说明.docx` | 完整的宏基因组流程说明文档，末尾包含 COG 数据库调研报告（含官方链接、版本说明、下载方法、注释工具、脚本示例） |
| `cog_annotate.py` | 基于 DIAMOND 比对结果和 NCBI COG2024 定义文件，将基因映射到 COG 功能类别的 Python 脚本 |
| `func_ano_1_update.py` | 宏基因组流程中调用 `emapper.py`（eggNOG-mapper）对非冗余基因集进行功能注释的包装脚本 |
| `func_ano_2_update.py` | 将 `func.emapper.annotations` 与基因丰度表整合，生成 eggNOG / KEGG / COG / GO / CAZy 丰度表的下游处理脚本 |
| `宏基因组分析流程图.png` | 宏基因组分析主干流程图（高清图片） |
| `宏基因组分析流程图.pptx` | 宏基因组分析主干流程图 PPT（共 2 页） |

## 快速使用

### 1. 使用 eggNOG-mapper 获取 COG 注释（推荐，与流程整合）

`func_ano_1_update.py` 封装了 `emapper.py` 的调用，可直接对 `prodigal/unique_gene.fasta` 运行注释：

```bash
python func_ano_1_update.py \
    --prodigal prodigal \
    --Annotation Annotation \
    --dbdir /data/data2/metagenome-DB/database \
    --emapperdir /app/eggnog-mapper \
    --cpu 50 \
    --evalue 1e-5 \
    --prefix func
```

`emapper.py` 命令示例：

```bash
emapper.py -m diamond \
    -i unique_gene.faa \
    --itype proteins \
    --data_dir /path/to/eggnog-data \
    -o metagenome_cog \
    --output_dir ./eggnog_results/ \
    --cpu 20
```

下游整合使用 `func_ano_2_update.py` 将注释结果与基因丰度表合并，输出 COG 类别丰度：

```bash
python func_ano_2_update.py \
    --Annotation Annotation \
    --mapdir /path/to/annotation-mapping \
    --gene_tpm gene_tpm.csv
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

## COG2024 官方下载链接

- **COG2024 FTP 主目录**：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/
- **COG2024 说明文件**：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/Readme.COG2024.txt
- **COG2024 蛋白序列**（用于 DIAMOND 建库）：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/COGorg24.faa.gz
- **COG 定义表**：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/cog-24.def.tab
- **COG 功能类别表**：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/cog-24.fun.tab
- **COG 基因列表**：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/cog-24.cog.csv
- **COG 物种信息**：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/cog-24.org.tab

> 提示：`.tab` 文件为纯文本制表符分隔格式，浏览器可能直接显示文本。若需下载，请在链接上右键选择“存储链接为…”或使用 `curl -O` 命令。

## 主要参考链接

- NCBI COG 主页：https://www.ncbi.nlm.nih.gov/research/COG
- NCBI COG2024 论文：https://academic.oup.com/nar/article/53/D1/D356/7874847
- NCBI CDD Batch CD-Search：https://www.ncbi.nlm.nih.gov/Structure/bwrpsb/bwrpsb.cgi
- eggNOG-mapper：https://github.com/eggnogdb/eggnog-mapper
- COG2024 FTP：https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/

## 说明

COG 最适合汇入到现有 metage_megahit 工作流的 `func_anno`（功能注释）和 `func_base`（功能基础统计）两个 Task 中。由于 `func_anno` 使用的 eggNOG-mapper 输出已包含 COG 分类信息，通常无需额外新增 Task；如需独立控制 COG 数据库版本，可参照 `VCA_anno` / `MBQ_anno` 的模式新增独立 COG 注释步骤。
