args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

library(dplyr)
library(openxlsx)
library(ggplot2)
library(reshape2)
library(plotly)
library(htmlwidgets)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

yanse <- c("#FF7F00","#984EA3","#4DAF4A","#E41A1C","#377EB8",
          '#00F5FF',"#FFFF33","#DA5724","#74D944","#F781BF",
          "#CE50CA","#D3D93E","#C0717C","#CBD588",
          "#D7C1B1","#5F7FC7","#673770",  "#3F4921","#CD9BCD",
          "#38333E","#689030","#AD6F3B",  '#76EEC6')

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character', header = T, check.names = F)

for (i in 2: ncol(sample)){
  sap_gro = na.omit(sample[sample[, i] != '', c(1,i)])
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  gro_dir <- paste0(res_dir, '/', group_id, '/2-Assembly/')
  sta_ls = list()
  valid_samps = character()
  for (prefix in samps){
    sam_dir = paste0(res_dir, '/', group_id, '/2-Assembly/', prefix, '/')
    if (!file.exists(sam_dir)){dir.create(sam_dir, recursive = T)}

    file_name = paste0(prefix, '_length.txt')
    file_path = file.path(table_dir, file_name)
    if (!file.exists(file_path)) {
      warning(paste('文件不存在，跳过:', file_path))
      next
    }
    # 检查文件是否只有表头或为空
    lines = readLines(file_path, warn = FALSE)
    if (length(lines) <= 1) {
      warning(paste('长度文件为空或只有表头，跳过:', file_path))
      next
    }
    l_dat = read.table(file_path, sep = '\t', quote = '', header = F, skip = 1)
    colnames(l_dat) = c('id', 'len')
    l_dat$Length <- cut(l_dat$len,
                        breaks = c(500, 1000, 1500, 2000, 2500, 3000, 5000, 10000, 20000, 30000, Inf),
                        labels = c('500~1000', '1000~1500', '1500~2000', '2000~2500',
                                   '2500~3000', '3000~5000', '5000~10000', '10000~20000',
                                   '20000~30000', '>30000'),
                        right = F)
    sta_dat <- data.frame(table(l_dat$Length))
    colnames(sta_dat) <- c('Length', prefix)
    write.table(sta_dat, file=file.path(sam_dir, file_name),
                sep = '\t', quote = F, row.names = F)
    dat_len <- sta_dat[, 1, drop=F]
    sta_ls[[prefix]] <- sta_dat[, 2]
    valid_samps = c(valid_samps, prefix)
  }

  if (length(sta_ls) == 0) {
    warning(paste('group', group_id, '没有有效的长度数据，跳过绘图'))
    next
 }

  sta_df <- as.data.frame(do.call(cbind, sta_ls))
  sta_df <- cbind(dat_len, sta_df)
  write.xlsx(sta_df, file = file.path(gro_dir, 'contigs_length.xlsx'))

  plot_df <- melt(sta_df, id.vars = 'Length')
  plot_df$variable <- factor(plot_df$variable, levels = valid_samps)
  p <- ggplot(data = plot_df, aes(x=variable, y=value, group=Length, fill=Length))+
    geom_bar(stat="identity",width=0.5,position='stack')+
    metage_theme()+
    theme(panel.grid = element_blank(),
          plot.title = element_text(hjust = 0.5, size = 22),
          axis.text.x  = element_text(color = 'black', size = 16, angle = 90, vjust = 0.5),
          axis.text.y  = element_text(color = 'black', size = 16),
          axis.title = element_text(size = 18),
          axis.title.x = element_blank(),
          legend.title = element_blank(),
          legend.text = element_text(size = 18)
    )+
    labs(y = 'Count')+
    scale_fill_manual(values = yanse)

  if (length(display_map) > 0) {
    x_labels <- display_map[levels(plot_df$variable)]
    x_labels[is.na(x_labels)] <- levels(plot_df$variable)[is.na(x_labels)]
    names(x_labels) <- levels(plot_df$variable)
    p <- p + scale_x_discrete(labels = x_labels)
  }

  ggp <- ggplotly(p)
  saveWidget(ggp,file = paste0(gro_dir, 'contig_length.html'), selfcontained = T)
  k_samples <- length(unique(plot_df$variable))
  ggsave(paste0(gro_dir, 'contig_length.pdf'), p,
         width = 9+(k_samples/20), height = 6+(k_samples/40), device = cairo_pdf)
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
