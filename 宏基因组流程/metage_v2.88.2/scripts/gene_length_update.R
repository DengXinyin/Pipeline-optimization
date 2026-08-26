# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/宏基因组更新/prodigal'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

library(dplyr)
library(openxlsx)
library(ggplot2)
library(reshape2)
library(plotly)
library(htmlwidgets)

yanse <-c("#FF7F00","#984EA3","#4DAF4A","#E41A1C","#377EB8",
          '#00F5FF',"#FFFF33","#DA5724","#74D944","#F781BF",
          "#CE50CA","#D3D93E","#C0717C","#CBD588",
          "#D7C1B1","#5F7FC7","#673770",  "#3F4921","#CD9BCD",
          "#38333E","#689030","#AD6F3B",  '#76EEC6')
sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character', header = T, check.names = F, fill = TRUE)  # 添加 fill = TRUE 参数，避免 sample-metadata.tsv 列数不齐时报错。
# i = 2
for (i in 2: ncol(sample)){
  sap_gro = sample[sample[, i] != '', c(1,i)]
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  gro_dir <- paste0(res_dir, '/', group_id, '/3-GenePredict/')
  if (!file.exists(gro_dir)){dir.create(gro_dir, recursive = T)}
  
  lendat <- read.table(file.path(table_dir, 'unique_length.txt'), 
                      sep='\t', check.names = F)
  colnames(lendat) = c('id', 'len')
  
  plot_len <- lendat %>% count(len)
  colnames(plot_len) = c('length', 'count')
  
  p <- ggplot(plot_len, aes(length, count)) + 
    geom_col(width = 0.8) + 
    metage_theme() + 
    theme(panel.grid = element_blank()) +
    labs(x = "sequence length", y= 'Number of sequences') +
    scale_y_continuous(expand = c(0,0)) +
    scale_x_continuous(expand = c(0,0), limits = c(0, 2000))
  ggp <- ggplotly(p)
  saveWidget(ggp,file = paste0(gro_dir, "/gene_length.html"), selfcontained = T)
  ggsave(paste0(gro_dir, "/gene_length.pdf"), height = 6, width = 6, device = cairo_pdf)
  
  write.table(plot_len, file = file.path(gro_dir, 'unique_gene.length.txt'), 
              sep = '\t', row.names = F)
  
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
