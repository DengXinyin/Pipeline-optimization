# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/宏基因组更新/Result'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

library(vegan)
library(ape)
library(ggplot2)
library(ggsci)
library(ggrepel)
library(openxlsx)
library(ggforce)
library(plotly)
library(htmlwidgets)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

yanse <-c('#178224','#D51506','#B300B5','#0133C1','#B6BF2D',
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

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')
beta_indexs <- c('bray', 'jaccard')

# specie <- species[1]
# class <- classes[1]
# beta <- beta_indexs[1]
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
      for (beta in beta_indexs){
        file.name <- paste0(specie, '.xlsx')
        # readxl解决中文乱码问题，相应需要设置第一列为行名，2024.09.13 by Wang
        # feature_s <- read.xlsx(file.path(type_dir, file.name), 
        #                        sheet = 2, rowNames = T, check.names = F)
        feature_s <- readxl::read_excel(file.path(type_dir, file.name), 
                                        sheet = 2) %>% as.data.frame()
        rownames(feature_s) <- feature_s[,1]
        feature_s <- feature_s[,-1]
        
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
              metage_theme()+
              theme(panel.grid = element_blank(),    #去网格
                    axis.text = element_text(color="black"),
                    legend.background = element_blank(),
                    legend.box.background = element_blank(),
                    legend.key = element_blank())+
              geom_hline(yintercept=0,linetype='dashed',linewidth=0.8,color='grey') +
              geom_vline(xintercept=0,linetype='dashed',linewidth=0.8,color='grey') +
              labs(x=paste0("PCoA1 (",x_label,"%)"),
                   y=paste0("PCoA2 (",y_label,"%)")) +
              ggtitle(beta)+
              scale_color_manual(values = metage_group_palette(df.plot$group))+
              lims(x = c(min(df.plot$Axis.1)*1.2, max(df.plot$Axis.1)*1.2), 
                   y = c(min(df.plot$Axis.2)*1.2, max(df.plot$Axis.2)*1.2))+
              guides(color = guide_legend(override.aes = list(label = "", size = 3)))
            pcoa_labels <- rownames(df.plot)
            if (length(display_map) > 0) {
              pcoa_labels <- display_map[pcoa_labels]
              pcoa_labels[is.na(pcoa_labels)] <- rownames(df.plot)[is.na(pcoa_labels)]
            }
            p2 <- p1 + geom_text_repel(label = pcoa_labels, size=4.4, max.overlaps = 50)
            # Ellipse outlines should not add rectangular glyphs to the point legend.
            p3 <- p2 + ggforce::geom_mark_ellipse(
              aes(color=group), alpha=0.1, show.legend=FALSE
            )
            ggp1 <- ggplotly(p1)
            
            resdir <- paste(res_dir, gro_num,'5-TaxAnnotation', '6.Beta_diversity_analysis', class, specie, '2.PCoA', sep = '/')
            if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
            
            saveWidget(ggp1,file = paste0(resdir, '/', beta,'_', class, '_', specie,'_PCoA.html'), selfcontained = T)
            ggsave(paste0(resdir,'/', beta,'_',class, '_', specie,'_PCoA.pdf'),p1, width =7.5, height = 6, device = cairo_pdf)
            ggsave(paste0(resdir,'/', beta,'_',class, '_', specie,'_PCoA_labeled.pdf'),p2, width =7.5, height = 6, device = cairo_pdf)
            ggsave(paste0(resdir,'/', beta,'_',class, '_', specie,'_PCoA_ellipse.pdf'),p3, width =7.5, height = 6, device = cairo_pdf)
            
            if (is.null(df.pcoa$values$Relative_eig)){
              pcoa_loading <- df.pcoa$values[,c(3,5)]
              res <- pcoa_loading$Cum_corr_eig<0.80
              k = sum(res == TRUE) +1 
              if (k > 30){ k = 30 } else if ( k == 1 ){ k = 2 }
              if ( k > 1){
                pcoa_loading <- pcoa_loading[1:k,]
                colnames(pcoa_loading) <- c('R2X','R2X(cum)')
                rownames(pcoa_loading) <- paste0('PCoA',rep(1:k))
                pcoa_aex <- df.plot[,1:k]
                colnames(pcoa_aex) <- paste0('PCoA',rep(1:k))} 
              else {
                pcoa_loading <- pcoa_loading[1:2,]
                colnames(pcoa_loading) <- c('R2X','R2X(cum)')
                rownames(pcoa_loading) <- paste0('PCoA',rep(1:2))
                pcoa_aex <- df.plot[,1:2]
                colnames(pcoa_aex) <- paste0('PCoA',rep(1:2))
              }
            } else {
              pcoa_loading <- df.pcoa$values[,c(2,4)]
              res <- pcoa_loading$Cumul_eig < 0.80
              k = sum(res == TRUE) +1 
              if (k ==1){
                k = 2
              }
              pcoa_loading <- pcoa_loading[1:k,]
              colnames(pcoa_loading) <- c('R2X','R2X(cum)')
              rownames(pcoa_loading) <- paste0('PCoA',rep(1:k))
              pcoa_aex <- df.plot[,1:k]
              colnames(pcoa_aex) <- paste0('PCoA',rep(1:k))
            }
            sheets = list('pcoa_model'=pcoa_loading, 'pcoa_axes'=pcoa_aex)
            write.xlsx(sheets, file = paste0(resdir,'/', beta,'_PCoA.xlsx'),rowNames =T)
          }
          
        }
       
        
       }
     }
    
  }
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
