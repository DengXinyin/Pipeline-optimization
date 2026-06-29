# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/宏基因组更新/func_base'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

suppressPackageStartupMessages({
library(vegan)
library(ape)
library(ggplot2)
library(ggsci)
library(ggrepel)
library(openxlsx)
library(ggforce)
library(plotly)
library(htmlwidgets)
})

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

types <- c('1.KEGG', '2.eggNOG', '3.CAZy', '4.GO', 'Carbon_Cycle',
           'Methane_Cycle','Nitrogen_Cycle','phosphorylation_Cycle',
           'Sulfur_Cycle','ARG', 'VFDB', 'BacMet2', 'mobileOG', 'QS')
beta_indexs <- c('bray', 'jaccard')
pat <- '_sam.tsv'

# beta <- beta_indexs[1]
# type <- types[1]
# i = 1
for (i in 1: k){
  for (type in types){
    gro_num <- paste0('group', i)
    type_dir <- paste(table_dir, gro_num, type, sep = '/')
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    rownames(group) <- group$`sample-id`
    group <- group[, -1, drop=F]
    colnames(group) <- 'group'
    group$group <- factor(group$group, levels = unique(group$group))
    
    files <- list.files(path = type_dir, pattern = pat)
    file <- files[1]
    for (file in files){
      for (beta in beta_indexs){
      prefix <- strsplit(file, pat)
      prefix <- paste0(prefix, '_', beta)
      feature_s <- read.table(file.path(type_dir, file),row.names = 1,
                              quote = '',sep='\t', header = T, check.names = F)
      # 去掉全为NA的列
      feature_s <- feature_s[, colSums(is.na(feature_s)) != nrow(feature_s)]
      
      nums <- nrow(feature_s)
      if (nums > 2){
        dis_matrix <- vegdist(t(feature_s),method = beta)
        
        df.pcoa<-pcoa(dis_matrix,correction = "cailliez")   #distance  dist/matrix
        df.plot<-data.frame(df.pcoa$vectors)
        df.plot$group <- group[match(row.names(df.plot), row.names(group)),]
        
        p_nums <- ncol(df.plot)
        if (p_nums > 2){
          if (is.null(df.pcoa$values$Relative_eig)) {
            x_label<-round(df.pcoa$values$Rel_corr_eig[1]*100,2)
            y_label<-round(df.pcoa$values$Rel_corr_eig[2]*100,2)
          } else {
            x_label<-round(df.pcoa$values$Relative_eig[1]*100,2)
            y_label<-round(df.pcoa$values$Relative_eig[2]*100,2)
          }
          
          p1 <- ggplot(data=df.plot,aes(x=Axis.1,y=Axis.2,color=group))+
            geom_point(size=3)+
            theme_bw(base_family = '宋体',base_size = 12,base_line_size =0.5)+
            theme(panel.grid = element_blank(),    #去网格
                  plot.title = element_text(hjust = 0.5, size = 12),
                  axis.text = element_text(color="black"),
                  axis.title = element_text(size = 11))+
            geom_hline(yintercept=0,linetype='dashed',linewidth=0.8,color='grey') +
            geom_vline(xintercept=0,linetype='dashed',linewidth=0.8,color='grey') +
            labs(x=paste0("PCoA1 (",x_label,"%)"),
                 y=paste0("PCoA2 (",y_label,"%)")) +
            ggtitle(beta)+
            scale_color_manual(values = yanse)+
            lims(x = c(min(df.plot$Axis.1)*1.2, max(df.plot$Axis.1)*1.2), 
                 y = c(min(df.plot$Axis.2)*1.2, max(df.plot$Axis.2)*1.2))+
            guides(color = guide_legend(override.aes = list(label = "", size = 3)))
          
          p2 <- p1 + geom_text_repel(label = rownames(df.plot), size=3, max.overlaps = 50)
          p3 <- p2 + ggforce::geom_mark_ellipse(aes(color=group), alpha=0.1)
          ggp1 <- ggplotly(p1)
          
          if (is.null(df.pcoa$values$Relative_eig)){
            pcoa_loading <- df.pcoa$values[,c(3,5)]
            res <- pcoa_loading$Cum_corr_eig<0.80
            k = sum(res == TRUE) +1 
            if (k > 30){
              k = 30
            } else if ( k == 1 ){
              k = 2
            }
              pcoa_loading <- pcoa_loading[1:k,]
              colnames(pcoa_loading) <- c('R2X','R2X(cum)')
              rownames(pcoa_loading) <- paste0('PCoA',rep(1:k))
              pcoa_aex <- df.plot[,1:k]
              colnames(pcoa_aex) <- paste0('PCoA',rep(1:k))
          } else {
            pcoa_loading <- df.pcoa$values[,c(2,4)]
            res <- pcoa_loading$Cumul_eig < 0.80
            k = sum(res == TRUE) +1 
            if (k > 30){
              k = 30
            } else if ( k == 1 ){
              k = 2
            }
            pcoa_loading <- pcoa_loading[1:k,]
            colnames(pcoa_loading) <- c('R2X','R2X(cum)')
            rownames(pcoa_loading) <- paste0('PCoA',rep(1:k))
            pcoa_aex <- df.plot[,1:k]
            colnames(pcoa_aex) <- paste0('PCoA',rep(1:k))
          }
          sheets = list('pcoa_model'=pcoa_loading, 'pcoa_axes'=pcoa_aex)
          
          # 保存结果
          if (type == '1.KEGG'| type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
            resdir = paste(res_dir, gro_num, '7-FunctionAnnotation', type, '4.PCoA', sep='/')
          } else if (grepl('_Cycle', type)){
            resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '4.PCoA', sep='/')
          } else if (type == 'ARG'){
            resdir = paste(res_dir, gro_num, '10-ARG', '4.PCoA', sep='/')
          } else if(type == 'VFDB'){
            resdir = paste(res_dir, gro_num, '11-VFDB', '4.PCoA', sep='/')
          } else if(type == 'mobileOG'){
            resdir = paste(res_dir, gro_num, '12-mobileOG', '4.PCoA', sep='/')
          } else if(type == 'BacMet2'){
            resdir = paste(res_dir, gro_num, '13-BacMet2', '4.PCoA', sep='/')
          } else if(type == 'QS'){
            resdir = paste(res_dir, gro_num, '14-QS', '4.PCoA', sep='/')
          }
          
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          saveWidget(ggp1,file = paste0(resdir, '/', prefix,'_PCoA.html'), selfcontained = T)
          ggsave(paste0(resdir, '/', prefix,'_PCoA.pdf'), p1, width =7.5, height = 6, device = cairo_pdf)
          ggsave(paste0(resdir, '/', prefix,'_PCoA_labeled.pdf'), p2, width =7.5, height = 6, device = cairo_pdf)
          ggsave(paste0(resdir, '/', prefix,'_PCoA_ellipse.pdf'), p3, width =7.5, height = 6, device = cairo_pdf)
          write.xlsx(sheets, file = paste0(resdir,'/', prefix, '_PCoA.xlsx'),rowNames =T)

          
        }
      }
      
     }
    }
  }
}
