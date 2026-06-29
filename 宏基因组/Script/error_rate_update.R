# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/宏基因组更新/table'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新'

library(ggplot2)
library(plotly)
library(htmlwidgets)

plot_error_rate = function(error_dat, prefix){
  ggplot(data=error_dat, aes(x=reads, y=error_rate)) +
    geom_bar(stat="identity", position="stack", width=0.8, fill='#43CD80') +
    geom_vline(xintercept = 150, linetype = "dashed", size = 0.5) +
    theme_bw(base_family = '宋体',base_size = 12,base_line_size =0.3)+
    theme(panel.grid = element_blank(),   #去网格
          plot.title = element_text(hjust = 0.5, size = 12), #调整标题位置
          axis.text.x  = element_text(color = 'black', angle = 90, vjust = 0.5),
          axis.text.y  = element_text(color = 'black'),
          legend.title = element_blank(),
    ) +
    ggtitle(prefix)+
    labs(x='Position along reads', y='Error rate')
}

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character', header = T, check.names = F, fill = TRUE)
for (i in 2: ncol(sample)){
  sap_gro = na.omit(sample[sample[, i] != '', c(1,i)])
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  for (prefix in samps){
    sam_dir = paste0(res_dir, '/', group_id, '/1-data_quality/', prefix, '/')
    if (!file.exists(sam_dir)){dir.create(sam_dir, recursive = T)}
    
    file_name = paste0(prefix, '_error_rate.tsv')
    error_dat = read.table(file.path(table_dir, file_name), sep = '\t',
                           header = T, check.names = F)
    # write.table(error_dat, file = paste0(sam_dir, file_name), sep = '\t', row.names = F)
    p <- plot_error_rate(error_dat, prefix)
    ggp <- ggplotly(p)
    saveWidget(ggp,file = paste0(sam_dir, 'error_rate.html'), selfcontained = T)
    ggsave(paste0(sam_dir, 'error_rate.pdf'), p, width = 6, height = 5, device = cairo_pdf)
  }

}

  