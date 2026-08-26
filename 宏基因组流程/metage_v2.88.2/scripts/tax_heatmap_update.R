# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'
# data_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/data'
# res_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'

library(pheatmap)
library(dplyr)
library(openxlsx)
library(d3heatmap)
library(htmlwidgets)
library(heatmaply)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

color <- colorRampPalette(c("blue", "white", "red"))(n = 50)
Set <- c('#178224','#D51506','#B300B5','#0133C1','#B6BF2D',
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
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
types <- c('Samples', 'Groups')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')

# specie <- species[1]
# type <- types[2]
# class <- classes[1]
# i = 1
for (i in 1: k){
  for (type in types){
    for (class in classes){
      gro_num <- paste0('group', i)
      type_dir <- paste(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', type, class, sep = '/')
      resdir <- paste(res_dir, gro_num, '5-TaxAnnotation', '5.Heatmap', type, class, sep = '/')
      if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
      
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
        
        feature_s <- feature_s %>%
          mutate(mean = rowMeans(across(where(is.numeric)))) %>%
          arrange(-mean) %>%
          slice_head(n=50)
        feature_s <- feature_s[,-ncol(feature_s)] 
        feature_s <- feature_s[rowSums(feature_s == 0) != ncol(feature_s), ]
        
        if (type == 'Groups'){
          order_s <- na.omit(match(unique(sample[, i+1]), colnames(feature_s)))
          feature_s <- feature_s[, order_s]
          colnames(feature_s) <- factor(colnames(feature_s), levels = colnames(feature_s))
          nums_k <- ncol(feature_s)
          if (nums_k > 35) {fontsize = 400/nums_k + 4} else {fontsize = 16}
          
          ggp <-  heatmaply(feature_s,scale = 'row',show_grid  = F,
                            Rowv=T, Colv=T, dendrogram = 'both',
                            col=color, 
                            showticklabels = c(T,F),
                            angle_col = 45,labRowSize =16,labColSize =16,
                            famliy="Times New Roman")
          saveWidget(ggp,file = paste0(resdir,'/',class, '_',specie,'_heatmap_cluster.html'), selfcontained = T)
          
          ggp2 <-  heatmaply(feature_s,scale = 'row',show_grid  = F,
                             Rowv=T, Colv=F, dendrogram = 'row',
                             col=color, 
                             showticklabels = c(T,F),
                             angle_col = 45,labRowSize =16,labColSize =16,
                             famliy="Times New Roman")
          saveWidget(ggp2,file = paste0(resdir,'/',class, '_',specie,'_heatmap.html'), selfcontained = T)
          
          cairo_pdf(paste0(resdir,'/',class, '_',specie,'_heatmap_cluster.pdf'),family = 'Times New Roman',width = 10,height = 10)
          p <- pheatmap(feature_s,scale = 'row',
                        cluster_rows = T, cluster_cols = T,
                        color = color,
                        border_color = 'transparent',
                        fontsize = fontsize,
          )
          dev.off()
          cairo_pdf(paste0(resdir,'/',class, '_',specie,'_heatmap.pdf'),family = 'Times New Roman',width = 10,height = 10)
          p2 <- pheatmap(feature_s,scale = 'row',
                         cluster_rows = T, cluster_cols = F,
                         color = color,
                         border_color = 'transparent',
                         fontsize = fontsize,
          )
          dev.off()
          
        } else {
          order_s <- na.omit(match(sample$`sample-id`, colnames(feature_s)))
          feature_s <- feature_s[, order_s]
          colnames(feature_s) <- factor(colnames(feature_s), levels = colnames(feature_s))
          nums_k <- ncol(feature_s)
          if (nums_k > 35) {fontsize = 400/nums_k + 4} else {fontsize = 16}
          
          group <- sample[, c(1, i+1)]
          group <- na.omit(group[group[, 2] != '', ])
          rownames(group) <- group$`sample-id`
          group <- group[, -1, drop=F]
          colnames(group) <- 'group'
          group$group <- factor(group$group, levels = unique(group$group))
          gro_color <- Set[as.factor(group$group)]
          gro_color <- as.data.frame(gro_color)
          colnames(gro_color) <- "group"
          if (length(display_map) > 0) {
            orig_colnames <- as.character(colnames(feature_s))
            new_colnames <- display_map[orig_colnames]
            new_colnames[is.na(new_colnames)] <- orig_colnames[is.na(new_colnames)]
            colnames(feature_s) <- new_colnames
            rownames(group) <- new_colnames[match(rownames(group), orig_colnames)]
          }
          ggp <-  heatmaply(feature_s,scale = 'row',show_grid  = F,
                            Rowv=T, Colv=T, dendrogram = 'both',
                            col=color, ColSideColors = gro_color,
                            showticklabels = c(T,F),
                            angle_col = 45,labRowSize =16,labColSize =16,
                            famliy="Times New Roman")
          
          saveWidget(ggp,file = paste0(resdir,'/',class, '_',specie,'_heatmap_cluster.html'), selfcontained = T)
          
          ggp2 <-  heatmaply(feature_s,scale = 'row',show_grid  = F,
                             Rowv=T, Colv=F, dendrogram = 'row',
                             col=color, ColSideColors = gro_color,
                             showticklabels = c(T,F),
                             angle_col = 45,labRowSize =16,labColSize =16,
                             famliy="Times New Roman")
          saveWidget(ggp2,file = paste0(resdir,'/',class, '_',specie,'_heatmap.html'), selfcontained = T)
          
          cairo_pdf(paste0(resdir,'/',class, '_',specie,'_heatmap_cluster.pdf'),family = 'Times New Roman',width = 10,height = 10)
          p <- pheatmap(feature_s,scale = 'row',
                        cluster_rows = T, cluster_cols = T,
                        annotation_col = group,
                        color = color,
                        border_color = 'transparent',
                        fontsize = fontsize,
          )
          dev.off()
          cairo_pdf(paste0(resdir,'/',class, '_',specie,'_heatmap.pdf'),family = 'Times New Roman',width = 10,height = 10)
          p2 <- pheatmap(feature_s,scale = 'row',
                         cluster_rows = T, cluster_cols = F,
                         annotation_col = group,
                         color = color,
                         border_color = 'transparent',
                         fontsize = fontsize,
          )
          dev.off()
        }
        

        
      }
    }
  }
}
