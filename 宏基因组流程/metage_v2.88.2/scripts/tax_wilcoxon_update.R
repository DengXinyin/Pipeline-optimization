# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# tpm_dir <- 'D:/宏基因组更新/tax_diff'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

library(ggplot2)
library(reshape2)
library(scales)
library(plotly)
library(htmlwidgets)

yanse <- c('#178224','#D51506','#B300B5','#0133C1','#B6BF2D',
          '#2DBFB9','#EE520A','#E90A6D','#F09013','#5FD80A',
          "#A65628","#984EA3","#F781BF","#FFFF33","#377EB8",
          "#D3D93E","#C0717C","#CBD588","#D7C1B1","#673770",
          "#3F4921","#38333E","#689030","#AD6F3B","#D9B3A6",
          "#008B8B","#8B008B","#FF8C00","#8B0000","#FFD700",
          "#00FF00","#00FFFF","#FF00FF","#FF0000","#0000FF",
          "#006400","#FF1493","#FF4500","#FF6347","#FF69B4",
          "#8B658B","#8B4513","#FFD39B","#FFA07A","#FFA500",
          "#CDC9C9","#CD9B9B","#CD6889","#CD3333","#CD0000",
          "#AEEEEE","#8B8B00","#8DB6CD","#8B864E","#8B795E",
          "#9AC0CD","#8B5A2B","#8B4789","#7208BE","#6B0E06",
          "#FFE4C4","#6FDAB9","#1FC1C1","#FFB6C1","#FFAEB9")
sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')

# specie <- species[1]
# class <- classes[1]
# i = 1
for (i in 1: k){
  for (class in classes){
    gro_num <- paste0('group', i)
    table_dir <- paste(tpm_dir, gro_num, 'wilcoxon', class, sep = '/')
    
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    rownames(group) <- group$`sample-id`
    group <- group[, -1, drop=F]
    colnames(group) <- 'group'
    group$group <- factor(group$group, levels = unique(group$group))
    
    for (specie in species){
      file.name <- paste0(specie, '_sign.tsv')
      if (file.exists(file.path(table_dir, file.name))){
        genus_sign <- read.table(file.path(table_dir, file.name), 
                                 sep = '\t', header = T, check.names = F)
        nums <- nrow(genus_sign)
        if (nums > 5){nums =5}
        for (j in 1:nums){
          row <- genus_sign[j,]
          row <- melt(row, id = c(specie, 'statistic', 'p_value', 'padj'))
          row$group <- group[match(row$variable, rownames(group)),]
          p_value <- sprintf('%.3f', unique(row$p_value))
          genus.name <- unique(row[, 1])
          genus.name <- gsub('/', '_', genus.name)
          genus.name <- gsub(':', '_', genus.name)
          p <- ggplot(data = row,aes(x=group, y=value, fill=group)) +
            stat_boxplot(geom = 'errorbar', width=0.3) +
            geom_boxplot()+
            metage_theme()+
            theme(panel.grid = element_blank(),    #去网格
                  legend.position = 'none',
                  axis.title.x = element_blank(),
                  axis.text = element_text(color="black"),
                  axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1))+
            labs(y='Relative abundance')+
            scale_y_continuous(labels = percent_format())+
            scale_fill_manual(values = metage_group_palette(row$group))
          p <- p + ggtitle(paste0(genus.name,', pvalue=',p_value))
          ggp <- ggplotly(p)
          
          resdir <- paste(res_dir,gro_num, '6-TaxStatistical_analysis', class, specie,'2.wilcoxon', sep = '/')
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          k_gros <- length(unique(row$group))
          ggsave(paste0(resdir, '/', genus.name, '.pdf'),p,
                 width =6+(k_gros/20)*1.5, height = 6+(k_gros/20)*0.5, device = cairo_pdf)
          saveWidget(ggp,file = paste0(resdir, '/', genus.name, '.html'), selfcontained = T)
        }
        
      }
    }
  }
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
