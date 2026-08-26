# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]
host <- args[4]

# table_dir <- 'D:/宏基因组更新/table'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新'
# host <- 'mouse'

library(reshape2)
library(ggplot2)
library(scales)
library(plotly)
library(htmlwidgets)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character', header = T, check.names = F, fill = TRUE)
display_map <- load_display_name_map(data_dir)

get_table = function(sam_dat){
  plot_dat = data.frame(sample_name = sam_dat$Sample_name,
                        Low_quality_Reads = 1 - sam_dat$Removed_low_quality_Reads/sam_dat$Raw_reads,
                        Clean_Reads = sam_dat$Removed_low_quality_Reads/sam_dat$Raw_reads)
  plot_dat = melt(plot_dat)
  plot_dat$value = round(plot_dat$value*100, 2)
  plot_dat$label = paste0(plot_dat$value, '%')
  return(plot_dat)
}

get_table2 <- function(sam_dat){
  plot_dat = data.frame(sample_name = sam_dat$Sample_name,
                        Low_quality_Reads = 1 - sam_dat$Removed_low_quality_Reads/sam_dat$Raw_reads,
                        Clean_Reads = sam_dat$Removed_host_Reads/sam_dat$Raw_reads
  )
  plot_dat$Host_reads <- 1- (plot_dat$Low_quality_Reads + plot_dat$Clean_Reads)
  plot_dat = melt(plot_dat)
  plot_dat$value = round(plot_dat$value*100, 2)
  plot_dat$label = paste0(plot_dat$value, '%')
  return(plot_dat)
}

plot_summary <- function(plot_dat, prefix){
  ggplot(data = plot_dat, aes(x=sample_name, y=value, group=variable, fill=variable))+
    geom_bar(stat="identity",width=0.5,position='stack')+
    geom_text(aes(label=label), position = position_stack(vjust=0.5), family='Times New Roman')+
    coord_polar("y", start=0)+
    metage_theme()+
    theme(panel.border = element_blank(),  #去外框
          panel.grid = element_blank(),   #去网格
          axis.ticks = element_blank(),
          plot.title = element_text(hjust = 0.5, size = 20), #调整标题位置
          axis.text  = element_blank(),
          axis.title = element_blank(),
          legend.title = element_text(size = 18)
    )
}

summary_dat = read.table(file.path(table_dir, 'sumary.txt'), sep = '\t',
                         header = T, check.names = F)
summary_dat$Sample_name <- factor(summary_dat$Sample_name, levels = summary_dat$Sample_name)
for (i in 2: ncol(sample)){
  sap_gro = na.omit(sample[sample[, i] != '', c(1,i)])
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  for (prefix in samps){
    prefix = as.character(prefix)
    sam_dir = paste0(res_dir, '/', group_id, '/1-data_quality/', prefix, '/')
    if (!file.exists(sam_dir)){dir.create(sam_dir, recursive = T)}
    
    display_prefix <- prefix
    if (length(display_map) > 0 && prefix %in% names(display_map)) {
      display_prefix <- display_map[prefix]
    }
    
    sam_dat = summary_dat[summary_dat$Sample_name %in% prefix, ]
    # write.table(sam_dat, file = file.path(sam_dir, 'summary.txt'), sep='\t', row.names = F)
    if (host == 'none'){
      plot_dat = get_table(sam_dat)
    } else {
      plot_dat = get_table2(sam_dat)
    }
    
    p <- plot_summary(plot_dat, display_prefix)
    ggsave(paste0(sam_dir, 'reads_quality_summary.pdf'), p, width = 6, height = 5, device = cairo_pdf)
  }
}
