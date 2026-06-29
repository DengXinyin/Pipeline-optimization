# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/新建文件夹/table'
# data_dir <- 'D:/新建文件夹/data'
# res_dir <- 'D:/新建文件夹'

library(reshape2)
library(ggplot2)
library(scales)
library(plotly)
library(htmlwidgets)

plot_dist = function(content, prefix){
  ggplot(data = content, aes(x=reads, y=value, group=variable, color=variable))+
    geom_line(linewidth=0.3)+
    geom_vline(xintercept = 150, linetype = "dashed", size = 0.3) +
    theme_bw(base_family = '宋体',base_size = 12,base_line_size =0.3)+
    theme(panel.grid = element_blank(),   #去网格
          plot.title = element_text(hjust = 0.5, size = 12), #调整标题位置
          axis.text.x  = element_text(color = 'black', angle = 90, vjust = 0.5),
          axis.text.y  = element_text(color = 'black'),
          legend.title = element_blank(),
    ) +
    ggtitle(prefix)+
    labs(x='Position along reads', y='Percentage (%)')+
    scale_y_continuous(labels = percent_format()) +
    scale_color_manual(values = c('red', 'blue', 'green', 'orange', 'gray'))
}

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
for (i in 2: ncol(sample)){
  sap_gro = na.omit(sample[sample[, i] != '', c(1,i)])
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  for (prefix in samps){
    sam_dir = paste0(res_dir, '/', group_id, '/1-data_quality/', prefix, '/')
    if (!file.exists(sam_dir)){dir.create(sam_dir, recursive = T)}
    
    filename = paste0(prefix, '_content.tsv')
    content = read.table(file = file.path(table_dir, filename), sep = '\t',
                         header = T)
    # write.table(content, file = paste0(sam_dir, filename), sep = '\t', row.names = F)
    content = content[, -7]
    content = melt(content, id.vars = 'reads')
    p <- plot_dist(content, prefix)
    ggp <- ggplotly(p)
    saveWidget(ggp,file = paste0(sam_dir, 'ATGC_content.html'), selfcontained = T)
    ggsave(paste0(sam_dir, 'ATGC_content.pdf'), p, width = 6, height = 5, device = cairo_pdf)

  }
  
}
