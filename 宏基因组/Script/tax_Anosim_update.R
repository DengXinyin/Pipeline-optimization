# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/宏基因组更新/Result'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

library(vegan)
library(ggplot2)
library(openxlsx)
library(dplyr)
library(plotly)
library(htmlwidgets)

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
    type_dir <- paste(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', class, sep = '/')
    
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    colnames(group) <- c('samples','group')
    group$group <- factor(group$group, levels = unique(group$group))
    
    for (specie in species){
      file.name <- paste0(specie, '.xlsx')
      # taxab <- read.xlsx(file.path(type_dir, file.name), 
      #                        sheet = 2, rowNames = T, check.names = F)
      taxab <- readxl::read_excel(file.path(type_dir, file.name), 
                                      sheet = 2) %>% as.data.frame()
      nums_f <- nrow(taxab)
      if (nums_f < 2){
        next
      }
      rownames(taxab) <- taxab[,1]
      taxab <- taxab[,-1]
      
      taxab <- taxab[, colSums(is.na(taxab)) == 0]
      rownum <- nrow(taxab)
      taxab <- taxab[, colSums(taxab == 0) != rownum]
      idx = colnames(taxab)
      group = group[group[,1] %in% idx, ]
      COMP <- paste(unique(group$group), collapse ='_vs_')
      
      
      bray <- vegdist(t(taxab),method = 'bray')
      anosim_ls <- anosim(bray,group$group,permutations = 999)
      R_value <- sprintf('%.3f',anosim_ls$statistic)
      p_value <- anosim_ls$signif
      df_plot <- data.frame(x=anosim_ls$class.vec,
                            y=anosim_ls$dis.rank)
      p <- ggplot(df_plot,aes(x=x,y=y,fill=x))+
        stat_boxplot(geom = 'errorbar', width=0.3) +
        geom_boxplot() +
        theme_bw(base_family = '宋体',base_size = 12,base_line_size =0.5)+
        theme(panel.grid = element_blank(),    #去网格
              legend.position = 'none',
              axis.title.x = element_blank(),
              plot.title = element_text(hjust = 0.5, size = 12),
              axis.text = element_text(color="black"),
              axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
              axis.title = element_text(size = 11))+
        labs(y='Rank of Distance (Bray_Curtis)') +
        ggtitle(paste0('R=',R_value,', pvalue=',p_value))
      ggp <- ggplotly(p)
      Anosim_df <- data.frame(group=COMP,
                              distance='Bray-Curtis',
                              R=anosim_ls$statistic,
                              p_value=anosim_ls$signif)
      
      
      resdir <- paste(res_dir, gro_num, '6-TaxStatistical_analysis', class, specie, '6.Anosim', sep = '/')
      if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
      
      k_gros <- length(unique(df_plot$x))
      ggsave(filename = paste0(resdir, '/', class, '_', specie,'_Anosim.pdf'), p, 
             width = 6+(k_gros/20)*1.5, height = 6+(k_gros/20)*0.5, device = cairo_pdf)
      saveWidget(ggp,file = paste0(resdir,'/', class, '_', specie,'_Anosim.html'), selfcontained = T)
      write.xlsx(Anosim_df, file = paste0(resdir, '/', class, '_', specie,'_Anosim.xlsx'))
      
    }
  }
}