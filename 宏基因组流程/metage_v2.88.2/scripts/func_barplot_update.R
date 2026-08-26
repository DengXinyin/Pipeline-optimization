# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/DEBUG/func_base'
# data_dir <- 'D:/DEBUG/data'
# res_dir <- 'D:/DEBUG/Result'

suppressPackageStartupMessages({
library(ggplot2)
library(reshape2)
library(dplyr)
library(openxlsx)
library(scales)
library(plotly)
library(htmlwidgets)
})

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

types <- c('1.KEGG', '2.eggNOG', '3.CAZy', '4.GO', 'Carbon_Cycle',
           'Methane_Cycle','Nitrogen_Cycle','phosphorylation_Cycle',
           'Sulfur_Cycle','ARG', 'VFDB', 'BacMet2', 'mobileOG', 'QS', 'COG', 'MetaCyc')
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
        if (number_row == 0){
          next
        }
        data <- feature_s[,-1]
        rownames(data) <- feature_s[, 1]
        # data <- feature_s %>% summarise(across(where(is.numeric), ~.x/sum(.x)))
        # rownames(data) <- feature_s[, 1]
        data <- data %>%
          mutate(mean = rowMeans(across(where(is.numeric)))) %>%
          arrange(-mean) %>%
          slice_head(n=20)
        data <- data[,-ncol(data)]
        row_nums <- nrow(data)
        if (row_nums != 20){
          yanse <-c("#377EB8","#FF7F00","#CE50CA",'#20B2AA',"#C0717C",
                    '#FFE4E1','#EEDC82','#FFC125','#CD5C5C',"#CBD588",
                    "#E41A1C","#DA5724","#74D944","#F781BF","#FFFF33",
                    "#689030","#D3D93E","#984EA3","#A65628",
                    "#4DAF4A","#AD6F3B",'#00F5FF','#76EEC6',"#38333E",
                    "#D7C1B1","#5F7FC7","#673770","#3F4921","#CD9BCD",
                    '#8B3A3A')
        } else{
          yanse <-c("#A6ACAF","#A65628","#FF7F00","#C0717C","#CBD588",
                    '#FFE4E1','#20B2AA','#EEDC82','#FFC125','#CD5C5C',
                    "#E41A1C","#DA5724","#74D944","#F781BF","#FFFF33",
                    "#689030","#CE50CA","#D3D93E","#377EB8","#984EA3",
                    "#4DAF4A","#AD6F3B",'#00F5FF','#76EEC6',"#38333E",
                    "#D7C1B1","#5F7FC7","#673770","#3F4921","#CD9BCD",
                    '#8B3A3A')
          data <- as.data.frame(t(data)) %>%
            mutate(Others = (1 - rowSums((across(where(is.numeric)))))) %>%
            t() %>% as.data.frame()
        }

        if (pat == '_group.tsv'){
          order_s <- na.omit(match(unique(sample[, i+1]), colnames(data)))
          data <- data[, order_s]
          colnames(data) <- factor(colnames(data), levels = colnames(data))
          prefix <- paste0(prefix, '_group')
          nums <- ncol(data)
        } else {
          order_s <- na.omit(match(sample$`sample-id`, colnames(data)))
          data <- data[, order_s]
          colnames(data) <- factor(colnames(data), levels = colnames(data))
          nums <- ncol(data)
        }

        data$pathway <- rownames(data)
        data$pathway <- factor(data$pathway,levels = c(rev(rownames(data))))
        data <- melt(data, id.vars = 'pathway')

        p1 <- ggplot(data = data, aes(x=variable, y=value, fill=pathway))+
          geom_bar(stat="identity", position="stack", width=0.8) +
          metage_theme()+
          theme(panel.border = element_rect(color = 'black', fill = NA, linewidth = 0.5),
                panel.grid = element_blank(),
                text = element_text(family = 'Times New Roman', size = 16),
                plot.title = element_text(hjust = 0.5, size = 22),
                axis.text.x  = element_text(color = 'black', size = 16, angle = 90, vjust = 0.5),
                axis.text.y  = element_text(color = 'black', size = 16),
                axis.title.x = element_blank(),
                axis.title.y = element_text(size = 18),
                legend.title = element_blank(),
                legend.text = element_text(size = 18),
                legend.background = element_blank(),
                legend.box.background = element_blank(),
                legend.key = element_blank()
          )+
          labs(y='Relative abundance (%)') +
          scale_y_continuous(expand = c(0,0), labels = percent_format()) +
          scale_fill_manual(values = yanse)

        if (pat != '_group.tsv' && length(display_map) > 0) {
          x_labels <- display_map[levels(data$variable)]
          x_labels[is.na(x_labels)] <- levels(data$variable)[is.na(x_labels)]
          names(x_labels) <- levels(data$variable)
          p1 <- p1 + scale_x_discrete(labels = x_labels)
        }

        ggp1 <- ggplotly(p1)

        # 保存结果
        if (type == '1.KEGG'| type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
          resdir = paste(res_dir, gro_num, '7-FunctionAnnotation', type, '1.Barplot', sep='/')
        } else if (grepl('_Cycle', type)){
          resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '1.Barplot', sep='/')
        } else if (type == 'ARG'){
          resdir = paste(res_dir, gro_num, '10-ARG', '1.Barplot', sep='/')
        } else if(type == 'VFDB'){
          resdir = paste(res_dir, gro_num, '11-VFDB', '1.Barplot', sep='/')
        } else if(type == 'mobileOG'){
          resdir = paste(res_dir, gro_num, '12-mobileOG', '1.Barplot', sep='/')
        } else if(type == 'BacMet2'){
          resdir = paste(res_dir, gro_num, '13-BacMet2', '1.Barplot', sep='/')
        } else if(type == 'QS'){
          resdir = paste(res_dir, gro_num, '14-QS', '1.Barplot', sep='/')
        } else if(type == 'COG'){
          resdir = paste(res_dir, gro_num, '15-COG', '1.Barplot', sep='/')
        } else if(type == 'MetaCyc'){
          resdir = paste(res_dir, gro_num, '16-MetaCyc', '1.Barplot', sep='/')
        }
        if (!file.exists(resdir)){dir.create(resdir, recursive = T)}

        saveWidget(ggp1,file = paste0(resdir, '/', prefix,'.html'), selfcontained = T)
        if (nums > 25){
          p1 <- p1 + theme(legend.position = 'bottom',
                           legend.margin = ggplot2::margin(0,1,0.5,1,unit ='cm')) +
            guides(fill = guide_legend(ncol = ceiling(nums/25), byrow = T))
          ggsave(paste0(resdir, '/', prefix,'.pdf'), p1,
                 width =10+(nums/25)*2.5, height = 6+(nums/30), device = cairo_pdf)
        } else {
          ggsave(paste0(resdir, '/', prefix,'.pdf'), p1, width =12, height = 7, device = cairo_pdf)
        }

      }
    }
  }
}
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
