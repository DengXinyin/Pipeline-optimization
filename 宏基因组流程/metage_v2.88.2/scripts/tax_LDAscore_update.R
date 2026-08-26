# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# tpm_dir <- 'D:/宏基因组更新/tax_diff'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

library(ggplot2)
library(dplyr)
library(plotly)
library(htmlwidgets)

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')

# specie <- species[1]
# class <- classes[1]
# i = 1
for (i in 1: k){
  for (class in classes){
    gro_num <- paste0('group', i)
    table_dir <- paste(tpm_dir, gro_num, 'lefse', class, sep = '/')
    
    for (specie in species){
      file.name <- paste0(specie, '_LDA.tsv')
      if (file.exists(file.path(table_dir, file.name))){
        LDA_tab <- read.csv(file.path(table_dir, file.name),
                            sep = '\t', check.names = F)
        LDA_tab <- LDA_tab %>% arrange(-LDA) %>% top_n(100, wt = LDA)
        LDA_tab <- LDA_tab[, c(1,3,4)]
        LDA_tab <- LDA_tab %>% arrange(Group, -LDA)
        #限制排序顺序，将要排序的变量转化为因子
        LDA_tab$Taxonomy <- factor(LDA_tab$Taxonomy, 
                                   levels=rev(unique(LDA_tab$Taxonomy)))
        LDA_tab$Group <- factor(LDA_tab$Group, levels=unique(LDA_tab$Group))
        xmax = max(LDA_tab$LDA)
        color = c('#178224','#D51506','#B300B5','#0133C1','#B6BF2D',
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
        p <- ggplot(data = LDA_tab,
                    aes(x=LDA,y=Taxonomy, fill=Group))+
          geom_bar(position = position_dodge(),stat = "identity", width = 0.8)+
          metage_theme()+
          theme(panel.border = element_blank(),
                panel.grid = element_blank(),    #去网格
                axis.ticks = element_blank(),
                plot.title = element_text(hjust = 0.5, size = 14),
                axis.text = element_text(color="black"),
                axis.title.y = element_blank(),
                legend.position = 'top',
                legend.title = element_blank())+
          labs(x='LDA SCORE (log 10)') + 
          scale_x_continuous(expand = c(0,0))+
          geom_vline(xintercept=seq(0, xmax, 1),
                     linetype='dashed',linewidth=0.8,color='black') +
          scale_fill_manual(values = color)
        ggp <- ggplotly(p)
        
        resdir <- paste(res_dir,gro_num, '6-TaxStatistical_analysis', class, specie,'9.Lefse', sep = '/')
        if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
        
        plot_nums = nrow(LDA_tab)
        if (plot_nums > 80){
          ggsave(paste0(resdir, '/', class, '_', specie,'_LDA.pdf'),p,
                 width = 10+(plot_nums/50),height = 18+(plot_nums/50)*2, device = cairo_pdf, limitsize = FALSE)
        } else {
          ggsave(paste0(resdir, '/', class, '_', specie,'_LDA.pdf'),p,
                 width = 8+(plot_nums/20),height = 3+(plot_nums/10)*2, device = cairo_pdf)
        }
        
        saveWidget(ggp,file = paste0(resdir, '/', class, '_', specie,'_LDA.html'), selfcontained = T)
      }
    }
  }
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
