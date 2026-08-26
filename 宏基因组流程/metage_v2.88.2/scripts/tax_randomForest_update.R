# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/宏基因组更新/Result'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

library(randomForest)
library(openxlsx)
library(ggplot2)
library(patchwork)
library(dplyr)
library(reshape2)
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
    rownames(group) <- group$`sample-id`
    group <- group[, -1, drop=F]
    colnames(group) <- 'group'
    group$group <- factor(group$group, levels = unique(group$group))
    
    for (specie in species){
      file.name <- paste0(specie, '.xlsx')
      # readxl解决中文乱码问题，相应需要设置第一列为行名，2024.09.13 by Wang
      # feature_s <- read.xlsx(file.path(type_dir, file.name), 
      #                        sheet = 2, rowNames = T, check.names = F)
      feature_s <- readxl::read_excel(file.path(type_dir, file.name), 
                                      sheet = 2) %>% as.data.frame()
      nums_f <- nrow(feature_s)
      if (nums_f < 2){
        next
      }
      rownames(feature_s) <- feature_s[,1]
      feature_s <- feature_s[,-1]
      
      feature_s <- as.data.frame(t(feature_s))
      group <- group[rownames(group) %in% rownames(feature_s), , drop=F]
      feature_s$group <- group[match(rownames(group), rownames(feature_s)), ]
      numg <- length(unique(feature_s$group))
      if (numg > 1) {
        taxab = na.omit(feature_s)
        result <- apply(taxab, 2, function(row) all(row == row[1]))
        taxab <- taxab[, result == F]
        
        if (is.data.frame(taxab)){
          taxab$group = as.factor(taxab$group)
          set.seed(123)
          taxab.rf = randomForest(x=taxab[,-ncol(taxab)], 
                                  y=taxab$group, importance=TRUE, proximity=TRUE)
          save_tab = data.frame(round(importance(taxab.rf), 2), 
                                MDA.p = taxab.rf$importanceSD[4])
          plot_tab <- save_tab['MeanDecreaseGini'] %>% 
            dplyr::filter(MeanDecreaseGini > 0) %>%
            arrange(-MeanDecreaseGini) %>%
            slice_head(n=10)
          plot_tab$tax = rownames(plot_tab)
          
          
          p1 <- ggplot(data = plot_tab, aes(x=MeanDecreaseGini, y = reorder(tax,MeanDecreaseGini))) +
            geom_bar(position = position_dodge(),
                     width = 0.7,
                     stat = "identity",
                     fill="steelblue")+
            metage_theme() +
            theme(panel.grid = element_blank(),    #去网格
                  panel.border = element_blank(),
                  axis.ticks.y = element_blank(),
                  #axis.line = element_line(linetype=1, colour = 'grey'),
                  axis.text = element_text(color="black"),
                  axis.title = element_text(size = 16),
                  axis.title.y = element_blank()
            )
          plot_tax = taxab[,c(plot_tab$tax, 'group')]
          plot_tax <- melt(plot_tax)
          plot_tax = plot_tax %>% group_by(group,variable) %>% 
            mutate(mean = mean(value), sd= sd(value))
          xmax_n = max(plot_tax$mean+plot_tax$sd) + 0.01
          mcolor = c('#178224','#D51506','#B300B5','#0133C1','#B6BF2D',
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
          p2 <- ggplot(data = plot_tax, aes(x=mean, y=variable, fill=group))+
            geom_errorbar(aes(xmin=ifelse(mean-sd <0, 0, mean-sd),xmax=mean+sd),
                          width=0.7,
                          color="#939596",size=0.2,
                          position = position_dodge())+
            geom_bar(position = position_dodge(),
                     width = 0.7,
                     stat = "identity")+
            metage_theme() +
            theme(panel.grid = element_blank(),    #去网格
                  panel.border = element_blank(),
                  axis.ticks.y = element_blank(),
                  axis.text.y = element_blank(),
                  #axis.line = element_line(linetype=1, colour = 'grey'),
                  axis.text = element_text(color="black"),
                  axis.title = element_text(size = 16),
                  axis.title.y = element_blank())+
            xlab('Abundance')+
            scale_fill_manual(values = mcolor)
          p <- p1+p2+plot_layout(nrow = 1, widths = c(2, 2),
                                 guides = "collect")
          ggp1 <- ggplotly(p1)
          ggp2 <- ggplotly(p2)
          ggp <- subplot(ggp1, ggp2, nrows = 1)
          
          resdir <- paste(res_dir, gro_num, '6-TaxStatistical_analysis', class, specie, '4.Random_Forest', sep = '/')
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          saveWidget(ggp,file = paste0(resdir, '/', class, '_', specie,'_random_forest.html'), selfcontained = T)
          ggsave(paste0(resdir, '/', class, '_', specie,'_random_forest.pdf'), p, width =10.5, height = 7, device = cairo_pdf)
          xlsx::write.xlsx(save_tab, paste0(resdir,'/',class, '_', specie, '_random_forest.xlsx'), row.names = T)
          # write.csv(save_tab, file.path(resdir,'random_forest.csv'), row.names = T)
        }
      }
      
    }
  }
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
