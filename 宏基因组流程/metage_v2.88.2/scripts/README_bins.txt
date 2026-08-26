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
│   │   ├── 2.Krona：Krona物种注释结果图
│   │   ├── 3.Barplot：物种分布柱状图
│   │   ├── 4.Bar_tree：UPGMA聚类树与柱状图结合绘图
│   │   ├── 5.Heatmap：物种组成聚类热图
│   │   └── 6.Beta_diversity_analysis
│   │   │       ├── All：所有分类β多样性分析结果
│   │   │       │   ├── class：纲水平
│   │   │       │   │   ├── 1.PCA
│   │   │       │   │   ├── 2.PCoA
│   │   │       │   │   └── 3.NMDS
│   │   │       │   ├── family：科水平
│   │   │       │   │   ├── ...
│   │   │       │   ├── genus：属水平
│   │   │       │   ├── order：目水平
│   │   │       │   ├── phylum：门水平
│   │   │       │   └── species：种水平
│   │   │       ├── Archaea：古细菌β多样性分析结果
│   │   │       ├── bacteria：细菌β多样性分析结果
│   │   │       ├── Fungi：真菌β多样性分析结果
│   │   │       └── Virus：病毒β多样性分析结果
│   ├── 6-TaxStatistical_analysis
│   │   ├── All：所有分类物种差异分析结果
│   │   │   ├── class
│   │   │   │   ├── 1.ANOVA
│   │   │   │   ├── 2.wilcoxon
│   │   │   │   ├── 3.Stamp
│   │   │   │   ├── 4.Random_Forest
│   │   │   │   ├── 5.metagenomeSeq
│   │   │   │   ├── 6.Anosim
│   │   │   │   ├── 7.Adonis
│   │   │   │   ├── 8.MRPP
│   │   │   │   └── 9.Lefse
│   │   │   ├── family
│   │   │   ├── genus
│   │   │   ├── order
│   │   │   ├── phylum
│   │   │   └── species
│   │   ├── Archaea：古细菌物种差异分析结果
│   │   ├── bacteria：细菌物种差异分析结果
│   │   ├── Fungi：真菌物种差异分析结果
│   │   └── Virus：病毒物种差异分析结果
│   ├── 7-FunctionAnnotation
│   │   ├── 1.KEGG：KEGG功能注释结果
│   │   │   ├── 1.Barplot：功能注释柱状图
│   │   │   ├── 2.Heatmap：功能注释聚类热图
│   │   │   ├── 3.PCA：功能注释PCA分析
│   │   │   ├── 4.PCoA：功能注释PCoA分析
│   │   │   ├── 5.NMDS：功能注释NMDS分析
│   │   │   ├── KEGG.tpm.xlsx：基因功能注释表
│   │   │   ├── level1.tpm.xlsx：KEGG level1层级功能注释表
│   │   │   ├── level2.tpm.xlsx：KEGG level2层级功能注释表
│   │   │   └── level3.tpm.xlsx：KEGG level3层级功能注释表
│   │   ├── 2.eggNOG：eggNOG功能注释结果
│   │   │   ├── ...
│   │   ├── 3.CAZy：CAZy功能注释结果
│   │   │   ├── ...
│   │   └── 4.GO：GO功能注释结果
│   ├── 8-FunctionStatistical_analysis
│   │   ├── 1.KEGG：KEGG功能差异分析结果
│   │   │   ├── 1.ANOVA
│   │   │   ├── 2.wilcoxon
│   │   │   ├── 3.Stamp
│   │   │   ├── 4.Random_Forest
│   │   │   ├── 5.metagenomeSeq
│   │   │   ├── 6.Anosim
│   │   │   ├── 7.Adonis
│   │   │   ├── 8.MRPP
│   │   │   └── 9.Lefse
│   │   ├── 2.eggNOG：eggNOG差异分析结果
│   │   │   ├── ...
│   │   ├── 3.CAZy：CAZy差异分析结果
│   │   │   ├── ...
│   │   └── 4.GO：GO差异分析结果
│   ├── 9-METABOLIC：生物化学地球循环功能注释及分析结果
│       ├── Carbon_Cycle：碳循环
│       │   ├── 1.Barplot
│       │   ├── 2.Heatmap
│       │   ├── 3.PCA
│       │   ├── 4.PCoA
│       │   ├── 5.NMDS
│       │   ├── 6.Statistical_test_analysis：差异分析
│       │   │   ├── 1.ANOVA
│       │   │   ├── ...
		     └── 9.Lefse
│       │   ├── Carbon_Cycle_pathway.xlsx：碳循环pathway功能注释结果
│       │   └── Carbon_Cycle.xlsx：碳循环功能注释结果
│       ├── Methane_Cycle：甲烷代谢
│       │   ├── ...
│       ├── Nitrogen_Cycle：氮循环
│       ├── phosphorylation_Cycle：磷循环
│       └── Sulfur_Cycle：硫循环
│   ├── 10-ARG：抗性基因功能注释及分析结果
│   │   ├── 1.Barplot
│   │   ├── ...
│   │   ├── 6.Statistical_test_analysis
│       │   │   ├── 1.ANOVA
│       │   │   ├── ...
		     └── 9.Lefse
│   │   ├── ARG.Category.tpm.xlsx：ARG
│   │   ├── ARG.tpm.xlsx：ARG结果统计
│   │   └── gene.ARG.tpm.xlsx：ARG功能注释结果
│   ├──11-VFDB：毒力因子结果
│   │   ├── 1.Barplot
│   │   ├── ...
│   │   ├── 6.Statistical_test_analysis
│       │   │   ├── 1.ANOVA
│       │   │   ├── ...
		     └── 9.Lefse
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
├── binning：分箱结果
│   ├──1.Bin：分箱bins和分箱统计信息
│   ├──2.Bin_Plot：分箱GC-coverage图/表
│   ├──3.Bin_Abundance：分箱丰度统计图/表
│   ├──4.Bin_classify：分箱物种注释文件