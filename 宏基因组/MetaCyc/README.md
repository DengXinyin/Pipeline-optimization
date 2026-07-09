# MetaCyc 代谢通路数据库调研报告

> MetaCyc（Metabolic Pathways From all Domains of Life）是 SRI International 维护的、覆盖所有生命域的高质量代谢通路参考数据库，属于 BioCyc 数据库家族的核心参考库。它广泛应用于基因组代谢网络重建、宏基因组功能注释和代谢工程。

---

## 一、数据库概述

| 项目 | 内容 |
|------|------|
| **全称** | Metabolic Pathways From all Domains of Life |
| **维护机构** | SRI International（Stanford Research Institute） |
| **官网** | https://metacyc.org/ |
| **所属家族** | BioCyc（https://biocyc.org/） |
| **数据特点** | 非冗余、经实验验证、人工文献策展的代谢通路 |
| **更新频率** | 每年 3–4 次大版本更新 |
| **许可** | 网站免费访问；数据文件对学术/非营利用户免费开放，商业使用需授权 |

### 核心数据对象

MetaCyc 是一个 Pathway/Genome Database（PGDB），核心对象包括：

- **Pathways（通路）**：实验阐明的代谢途径，包含基础通路（base pathways）和超级通路（super pathways）。
- **Reactions（反应）**：酶促反应、转运反应、自发反应等。
- **Compounds（代谢物）**：参与反应的底物、产物、辅因子等，含 SMILES、InChI、吉布斯自由能等。
- **Proteins / Enzymes（酶/蛋白）**：酶复合物、亚基组成、激活剂、抑制剂、辅因子。
- **Genes（基因）**：编码酶的基因，链接到外部核酸/蛋白数据库。
- **Publications（文献）**：每个条目通常附带来源文献引用。

### 规模参考（版本 27.1，2023 年 8 月）

| 数据类型 | 数量级 |
|----------|--------|
| Pathways | ~3,100+ |
| Reactions | ~18,800+ |
| Metabolites | ~19,100+ |
| 策展文献 | ~76,000+ |

---

## 二、MetaCyc 与 KEGG 的对比

| 对比维度 | MetaCyc | KEGG |
|----------|---------|------|
| **通路定义** | 物种/分支特异性，记录不同生物中的通路变体 | 通用参考图（Reference Map），跨物种汇总 |
| **通路大小** | 较短，生物学意义更明确 | 较长，覆盖全面但可能包含多个变体 |
| **策展方式** | 大量人工文献策展，含详细 mini-review | 部分自动推断，摘要较短 |
| **证据编码** | 有 Evidence Codes（实验/计算证据） | 无 |
| **物种标注** | 通路标注已知存在的物种 | 不强调物种特异性 |
| **代谢物信息** | 含 SMILES、InChI、吉布斯自由能、化学性质 | 基础信息为主 |
| **酶信息** | 含亚基、激活剂、抑制剂、辅因子、动力学常数 | 以反应为中心，酶信息较少 |
| **通路数量** | 更多（~3,100+） | 较少（~400+ 代谢模块） |
| **反应数量** | 更多（~18,800+） | ~12,000 |
| **适用场景** | 精确代谢网络重建、菌种特定通路研究 | 广泛通路覆盖、快速功能注释 |

### 两者关系

- **互补使用**：KEGG 通路覆盖更广、检索更简单；MetaCyc 通路更精细、物种特异性更强，可补充 KEGG 中不全的通路。
- 在宏基因组研究中，常同时报告 KEGG 和 MetaCyc 通路结果，以相互验证。

---

## 三、MetaCyc 在宏基因组研究中的应用

### 1. 代谢通路预测

结合 **Pathway Tools** 的 **PathoLogic** 模块，可从注释基因组或宏基因组基因集中预测代谢通路：

```text
基因注释（EC / MetaCyc Reaction ID）
    ↓
PathoLogic
    ↓
预测 PGDB（每个样本/MAG 一个代谢网络）
    ↓
通路存在性 / 完整度统计
```

### 2. 常用工具链

| 工具 | 作用 |
|------|------|
| **Pathway Tools** | SRI 官方软件，含 PathoLogic、代谢网络可视化、Omics Viewer |
| **mpwt** | 多进程运行 Pathway Tools，批量重建多个基因组的 PGDB |
| **padmet** | 将 PGDB flat files 转为 PADMET 格式，便于 Python 分析 |
| **AuFAMe / AuCoMe** | 基于 eggNOG-mapper + Pathway Tools 的自动化代谢网络重建流程 |
| **MetaPathways** | 针对环境样本的模块化宏基因组通路预测流程 |
| **HUMAnN2/3** | 宏基因组通路定量工具，其部分代谢单元来自 MetaCyc |

### 3. 典型分析流程

```text
宏基因组 contigs / MAGs
    ↓
基因预测（prodigal / Prokka / Bakta）
    ↓
功能注释（eggNOG-mapper / KofamScan / InterProScan）
    ↓
提取 EC 编号、MetaCyc Reaction ID
    ↓
PathoLogic / mpwt 重建 PGDB
    ↓
提取 pathways.col / pathways.dat
    ↓
通路丰度 / 完整度统计、组间差异比较
```

---

## 四、MetaCyc 数据下载

### 官方下载页面

- **BioCyc 下载主页**：https://biocyc.org/download.shtml
- **MetaCyc 官网**：https://metacyc.org/

### 主要数据文件格式

MetaCyc 提供多种格式下载：

| 格式 | 说明 |
|------|------|
| **Pathway Tools attribute-value（.dat）** | 官方 flat file 格式，最完整 |
| **Pathway Tools tabular（.col）** | 制表符分隔，易于 Python/R 解析 |
| **BioPAX（.owl）** | 通路数据交换标准格式 |
| **SBML（.xml）** | 代谢网络建模格式 |
| **Ocelot** | Lisp 格式数据库转储 |
| **Mol files / MetaCyc-Molfiles.tgz** | 代谢物分子结构文件 |

### 常用 .dat / .col 文件说明

| 文件名 | 内容 |
|--------|------|
| `pathways.dat` / `pathways.col` | 通路定义、组成反应、物种范围 |
| `reactions.dat` / `reactions.col` | 化学反应、酶、方向、平衡信息 |
| `compounds.dat` / `compounds.col` | 代谢物、化学标识符 |
| `enzrxns.dat` / `enzymes.col` | 酶促反应与酶的对应关系 |
| `proteins.dat` / `genes.dat` | 蛋白质、基因信息 |
| `species.dat` | 物种列表（MetaCyc 特有） |
| `pubs.dat` | 文献引用 |
| `classes.dat` | 本体分类 |

### 下载示例

```bash
# 1. 注册并登录 BioCyc 账号，进入 download.shtml 选择 MetaCyc 版本
# 2. 下载 flat files 压缩包，解压到本地目录
mkdir -p ~/MetaCyc && cd ~/MetaCyc
# 假设已下载 metacyc_XX.X.tar.gz
tar -xzvf metacyc_XX.X.tar.gz

# 查看核心文件
ls data/
# pathways.dat reactions.dat compounds.dat enzymes.col genes.col ...
```

> **注意**：MetaCyc 数据文件需要注册 BioCyc 账号后下载；Pathway Tools 对学术用户免费，但需签署许可协议。

---

## 五、在 metage_megahit 流程中的整合建议

### 1. 与现有 `func_anno` 的衔接

现有流程使用 `eggNOG-mapper`，其输出已包含：

- **KEGG_ko**
- **EC_number**
- **KEGG_Pathway**
- **COG_category**
- **GOs**

虽然 eggNOG-mapper 不直接输出 MetaCyc Reaction ID，但可以通过 **EC 编号** 或 **KO → Reaction ID** 的映射桥接到 MetaCyc：

```text
eggNOG-mapper annotations
    ├── EC_number
    └── KEGG_ko
            ↓
    MetaCyc reactions.dat（EC / Reaction ID 映射）
            ↓
    pathways.dat（Reaction → Pathway）
            ↓
    通路存在性 / 丰度矩阵
```

### 2. 可选整合方案

#### 方案 A：轻量级——直接基于 EC 映射 MetaCyc 通路

- 从 eggNOG 结果提取 EC 编号。
- 用 MetaCyc `reactions.dat` + `pathways.dat` 建立 EC → Reaction → Pathway 映射。
- 统计每个样本中检测到的 MetaCyc 通路及其丰度。
- **优点**：无需安装 Pathway Tools，快速。
- **缺点**：不考虑通路完整度、物种特异性。

#### 方案 B：完整级——PathoLogic 重建每个 MAG 的 PGDB

- 对宏基因组分箱得到的 MAGs 或单菌基因组，用 Prokka / Bakta 注释。
- 用 `mpwt` 批量调用 Pathway Tools 的 PathoLogic。
- 输出每个基因组的 PGDB，提取通路完整度和代谢网络。
- **优点**：精确、可计算代谢互补性（如 Metage2Metabo）。
- **缺点**：计算量大、依赖 Pathway Tools 许可和安装。

### 3. 推荐落地步骤

1. **短期**：在 `func_anno` 下游新增一个轻量 Task，基于 eggNOG 的 EC 编号映射到 MetaCyc 通路，输出通路丰度表。
2. **中期**：安装 Pathway Tools + mpwt，对代表性 MAGs 重建 PGDB，补充菌种级代谢能力分析。
3. **长期**：整合 KEGG 与 MetaCyc 双通路注释，形成互补的代谢功能视图。

---

## 六、参考链接

| 资源 | 链接 |
|------|------|
| MetaCyc 官网 | https://metacyc.org/ |
| BioCyc 官网 | https://biocyc.org/ |
| BioCyc 下载页 | https://biocyc.org/download.shtml |
| MetaCyc 用户指南 | https://metacyc.org/MetaCycUserGuide.shtml |
| Pathway Tools 下载 | https://biocyc.org/download.shtml |
| Pathway Tools 数据文件格式 | https://bioinformatics.ai.sri.com/ptools/flatfile-format.html |
| mpwt（多进程 Pathway Tools） | https://github.com/AuReMe/mpwt |
| padmet | https://github.com/AuReMe/padmet |
| AuFAMe | https://github.com/AuReMe/AuFAMe |
| AuCoMe | https://github.com/AuReMe/aucome |
| MetaPathways | https://github.com/hallamlab/Metapathways2 |
| MetaCyc NAR 论文（2020） | https://academic.oup.com/nar/article/49/D1/D372/5924430 |
| MetaCyc vs KEGG 系统比较 | https://link.springer.com/content/pdf/10.1186/1471-2105-14-112.pdf |
| BioCyc vs KEGG 对比文档 | https://bioinformatics.ai.sri.com/biocyc/kegg-biocyc-comparison.pdf |

---

## 七、说明

- MetaCyc 是最权威、最精细的代谢通路参考数据库之一，与 KEGG 互补使用可获得更可靠的代谢功能注释。
- 在宏基因组流程中，MetaCyc 适合作为 **KEGG 通路的补充**，尤其在需要精确代谢网络重建、菌种级代谢能力分析时使用。
- 由于其完整功能依赖 Pathway Tools 和人工策展数据，实际部署时需考虑计算资源、许可协议和版本管理。
