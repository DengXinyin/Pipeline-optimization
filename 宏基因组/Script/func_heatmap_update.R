# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/DEBUG/func_base'
# data_dir <- 'D:/DEBUG/data'
# res_dir <- 'D:/DEBUG/Result'

suppressPackageStartupMessages({
library(pheatmap)
library(dplyr)
library(openxlsx)
library(d3heatmap)
library(htmlwidgets)
library(heatmaply)
})

color <- colorRampPalette(c("blue", "white", "red"))(n = 50)
Set <- c("#33A02C", "#FB9A99","#A6CEE3",  "#B2DF8A", "#E31A1C", 
         "#FDBF6F", "#FF7F00", "#CAB2D6", '#2DBFB9', "#6A3D9A",
         "#FFFF99", "#B15928","#1F78B4","#984EA3", "#F781BF",
         '#EE520A','#E90A6D','#0133C1', "#C0717C","#CBD588")
sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

types <- c('1.KEGG', '2.eggNOG', '3.CAZy', '4.GO', 'Carbon_Cycle',
           'Methane_Cycle','Nitrogen_Cycle','phosphorylation_Cycle',
           'Sulfur_Cycle','ARG', 'VFDB', 'BacMet2', 'mobileOG', 'QS')
pat_s <- c('_sam.tsv', '_group.tsv')
# type <- types[1]
# pat <- pat_s[1]
# i = 1
for (i in 1: k){
  for (type in types){
    for (pat in pat_s){
      gro_num <- paste0('group', i)
      type_dir <- paste(table_dir, gro_num, type, sep = '/')
      files <- list.files(path = type_dir, pattern = pat)
      file <- files[1]
      for (file in files){
        prefix <- strsplit(file, pat)
        feature_s <- read.table(file.path(type_dir, file),quote = '',
                                sep='\t', header = T, check.names = F)
        number_row = nrow(feature_s)
        if (number_row < 3){
          next
        }
        # 去掉全NA的列
        feature_s <- feature_s[, colSums(is.na(feature_s)) == 0]
        data <- feature_s[,-1]
        rownames(data) <- feature_s[, 1]
        # data <- feature_s %>% summarise(across(where(is.numeric), ~.x/sum(.x)))
        # rownames(data) <- feature_s[, 1]
        data <- data %>%
          mutate(mean = rowMeans(across(where(is.numeric)))) %>%
          arrange(-mean) %>%
          slice_head(n=50)
        data <- data[,-ncol(data)]
        data <- data[rowSums(data == 0) != ncol(data), ]
        
        if (pat == '_group.tsv'){
          prefix <- paste0(prefix, '_group')
          order_s <- na.omit(match(unique(sample[, i+1]), colnames(data)))
          data <- data[, order_s]
          colnames(data) <- factor(colnames(data), levels = colnames(data))
          
          ggp <-  heatmaply(data,scale = 'row',show_grid  = F,
                            Rowv=T, Colv=T, dendrogram = 'both',
                            col=color, 
                            showticklabels = c(T,F),
                            angle_col = 45,labRowSize =0.5,labColSize =0.5,
                            famliy="宋体")

          ggp2 <-  heatmaply(data,scale = 'row',show_grid  = F,
                             Rowv=T, Colv=F, dendrogram = 'row',
                             col=color, 
                             showticklabels = c(T,F),
                             angle_col = 45,labRowSize =0.5,labColSize =0.5,
                             famliy="宋体")
          
          samp_nums <- ncol(data)
          if (samp_nums > 35){fontsize = 400/samp_nums}else{fontsize = 12}
          p <- pheatmap(data,scale = 'row',
                        cluster_rows = T, cluster_cols = T,
                        color = color,
                        border_color = 'transparent',
                        fontsize = fontsize,
          )
          p2 <- pheatmap(data,scale = 'row',
                         cluster_rows = T, cluster_cols = F,
                         color = color,
                         border_color = 'transparent',
                         fontsize = fontsize,
          )

        } else {
          order_s <- na.omit(match(sample$`sample-id`, colnames(data)))
          data <- data[, order_s]
          colnames(data) <- factor(colnames(data), levels = colnames(data))
          
          group <- sample[, c(1, i+1)]
          group <- na.omit(group[group[, 2] != '', ])
          # group和data的sample-id保持一致
          group <- group[group$`sample-id` %in% colnames(data),]
          rownames(group) <- group$`sample-id`
          group <- group[, -1, drop=F]
          colnames(group) <- 'group'
          gro_color <- Set[as.factor(group$group)]
          gro_color <- as.data.frame(gro_color)
          colnames(gro_color) <- "group"
          ggp <-  heatmaply(data,scale = 'row',show_grid  = F,
                            Rowv=T, Colv=T, dendrogram = 'both',
                            col=color, ColSideColors = gro_color,
                            showticklabels = c(T,F),
                            angle_col = 45,labRowSize =0.5,labColSize =0.5,
                            famliy="宋体")
          ggp2 <-  heatmaply(data,scale = 'row',show_grid  = F,
                             Rowv=T, Colv=F, dendrogram = 'row',
                             col=color, ColSideColors = gro_color,
                             showticklabels = c(T,F),
                             angle_col = 45,labRowSize =0.5,labColSize =0.5,
                             famliy="宋体")
          
          samp_nums <- ncol(data)
          if (samp_nums > 35){fontsize = 400/samp_nums}else{fontsize = 12}
          p <- pheatmap(data,scale = 'row',
                        cluster_rows = T, cluster_cols = T,
                        annotation_col = group,
                        color = color,
                        border_color = 'transparent',
                        fontsize = fontsize,
          )
          p2 <- pheatmap(data,scale = 'row',
                         cluster_rows = T, cluster_cols = F,
                         annotation_col = group,
                         color = color,
                         border_color = 'transparent',
                         fontsize = fontsize,
          )
        }

          # 保存结果
          if (type == '1.KEGG'| type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
            resdir = paste(res_dir, gro_num, '7-FunctionAnnotation', type, '2.Heatmap', sep='/')
          } else if (grepl('_Cycle', type)){
            resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '2.Heatmap', sep='/')
          } else if (type == 'ARG'){
            resdir = paste(res_dir, gro_num, '10-ARG', '2.Heatmap', sep='/')
          } else if(type == 'VFDB'){
            resdir = paste(res_dir, gro_num, '11-VFDB', '2.Heatmap', sep='/')
          } else if(type == 'mobileOG'){
            resdir = paste(res_dir, gro_num, '12-mobileOG', '2.Heatmap', sep='/')
          } else if(type == 'BacMet2'){
            resdir = paste(res_dir, gro_num, '13-BacMet2', '2.Heatmap', sep='/')
          } else if(type == 'QS'){
            resdir = paste(res_dir, gro_num, '14-QS', '2.Heatmap', sep='/')
          }
        
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
        
          saveWidget(ggp,file = paste0(resdir,'/',prefix,'_heatmap_cluster.html'), selfcontained = T)
          saveWidget(ggp2,file = paste0(resdir,'/',prefix,'_heatmap.html'), selfcontained = T)
          cairo_pdf(paste0(resdir,'/',prefix,'_heatmap_cluster.pdf'),family = '宋体',width = 10,height = 10)
          base::print(p)
          dev.off()
          cairo_pdf(paste0(resdir,'/',prefix,'_heatmap.pdf'),family = '宋体',width = 10,height = 10)
          base::print(p2)
          dev.off()
        
      }
    }
  }
} 