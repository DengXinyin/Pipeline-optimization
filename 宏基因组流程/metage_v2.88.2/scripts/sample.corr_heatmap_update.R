# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/新建文件夹'
# data_dir <- 'D:/新建文件夹/data'
# res_dir <- 'D:/新建文件夹/Result'

library(corrplot)
library(openxlsx)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

tpm <- read.csv(file.path(table_dir, 'gene_tpm.csv'), check.names = F, row.names = 1)
sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    header = T, check.names = F, fill = TRUE)  # 添加 fill = TRUE 参数，避免 sample-metadata.tsv 列数不齐时报错。
for (i in 2: ncol(sample)){
  sap_gro = sample[sample[, i] != '', c(1,i)]
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  resdir <- paste0(res_dir, '/', group_id, '/4-GeneAbundance/Sample_correlation/')
  if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
  
  sam_tpm <- tpm[, colnames(tpm) %in% sap_gro$`sample-id`]
  cor.r <- cor(sam_tpm,method="spearman")
  if (length(display_map) > 0) {
    new_labels <- display_map[colnames(cor.r)]
    new_labels[is.na(new_labels)] <- colnames(cor.r)[is.na(new_labels)]
    colnames(cor.r) <- new_labels
    rownames(cor.r) <- new_labels
  }
  col <- colorRampPalette(c('blue',"#4477AA", "#FFFFFF", "#BB4444", "red"))
  cairo_pdf(file.path(resdir, 'sample.corr_heatmap.pdf'), width = 6, height = 6, family = 'Times New Roman')
  corrplot(cor.r, type="full",
           tl.col="black",
           diag=F,
           col=col(100))
  dev.off()
  write.xlsx(as.data.frame(cor.r), file.path(resdir, 'correlation.xlsx'), rowNames = T)
  
}