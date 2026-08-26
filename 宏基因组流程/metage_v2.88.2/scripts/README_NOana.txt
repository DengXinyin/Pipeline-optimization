Result/
├── group1 ： 各个比较组结果
│   ├── 1-data_quality
│   │   ├── data_quality.xlsx：原始数据质控结果表
│   │   ├── sample-XXX：不同样本
│   │   │   ├── ATGC_content.png：测序碱基含量分布图
│   │   │   ├── error_rate.png：原始数据碱基质量值分布图
│   │   │   ├── reads_quality_summary.png：原始数据组成图
│   │   └── ...
│   ├── 2-Assembly
│   │   ├── assembly_stat.xlsx：组装结果统计表
│   │   ├── contig_length.png：Contigs长度分布图
│   │   ├── contigs_length.xlsx：Contigs长度分布表
│   │   ├── sample-XXX：不同样本
│   │   │   └── XXX_length.txt：该样本Contigs序列长度分布
│   │   └── ...
│   ├── 3-GenePredict
│   │   ├── gene_length.png：gene catalogue长度分布图
│   │   ├── unique_gene.fasta：基因集序列
│   │   ├── unique_gene.length.txt：gene catalogue长度分布表
│   │   └── unique_gene.stat.xlsx：gene catalogue信息统计
│   ├── 4-GeneAbundance
│   │   ├── gene_count.xlsx：各个样本基因count统计
│   │   ├── gene_tpm.xlsx：各个样本基因tpm
│   │   ├── Sample_correlation
│   │   │   ├── correlation.xlsx：样品间相关系数表
│   │   │   └── sample.corr_heatmap.png：样品间相关系数热图
│   │   └── Venn
│   │       └── upset.png：样品间基因数目upset图
│   ├── 5-TaxAnnotation
│   │   ├── 1.Tables
│   │   │   ├── gene.taxonomy.xlsx：基因物种注释表
│   │   │   ├── Groups
│   │   │   │   └── ...
│   │   │   └── Samples
│   │   │       ├── All：包含所有分类信息
│   │   │       ├── Archaea：仅包含古细菌分类信息
│   │   │       ├── bacteria：仅包含细菌分类信息
│   │   │       ├── Fungi：仅包含真菌分类信息
│   │   │       └── Virus：仅包含病毒分类信息
│   ├── 7-FunctionAnnotation
│   │   ├── 1.KEGG：KEGG功能注释结果
│   │   │   ├── KEGG.tpm.xlsx：基因功能注释表
│   │   │   ├── level1.tpm.xlsx：KEGG level1层级功能注释表
│   │   │   ├── level2.tpm.xlsx：KEGG level2层级功能注释表
│   │   │   └── level3.tpm.xlsx：KEGG level3层级功能注释表
│   │   ├── 2.eggNOG：eggNOG功能注释结果
│   │   │   ├── ...
│   │   ├── 3.CAZy：CAZy功能注释结果
│   │   │   ├── ...
│   │   └── 4.GO：GO功能注释结果
│   ├── 9-METABOLIC：生物化学地球循环功能注释及分析结果
│       ├── Carbon_Cycle：碳循环
│       │   ├── Carbon_Cycle_pathway.xlsx：碳循环pathway功能注释结果
│       │   └── Carbon_Cycle.xlsx：碳循环功能注释结果
│       ├── Methane_Cycle：甲烷代谢
│       │   ├── ...
│       ├── Nitrogen_Cycle：氮循环
│       ├── phosphorylation_Cycle：磷循环
│       └── Sulfur_Cycle：硫循环
│   ├── 10-ARG：抗性基因功能注释及分析结果
│   │   ├── ARG.Category.tpm.xlsx：ARG
│   │   ├── ARG.tpm.xlsx：ARG结果统计
│   │   └── gene.ARG.tpm.xlsx：ARG功能注释结果
│   ├──11-VFDB：毒力因子结果
│   │   ├── gene.vf.tpm.xlsx
│   │   ├── vf.category.tpm.xlsx
│   │   └── vf.tpm.xlsx
│   ├──12-mobileOG：可移动元件结果
│   ...
│   ├──13-BacMet2：重金属抗性基因结果
│   ...
│   ├──14-QS：群体感应基因结果
│   ...
├── group...：别的比较组