# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'
# data_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/data'
# res_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'

library(ggplot2)
library(reshape2)
library(dplyr)
library(openxlsx)
library(scales)
library(plotly)
library(htmlwidgets)

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character', header = T, check.names = F, fill = TRUE)
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
      
        for (specie in species){
          file.name <- paste0(specie, '.xlsx')
          # readxl解决中文乱码问题，相应需要设置第一列为行名，2024.09.13 by Wang
          # openxlsx::read.xlsx(file.path(type_dir, file.name), 
          #              sheet = 2, rowNames = T, check.names = F)
          feature_s <- readxl::read_excel(file.path(type_dir, file.name), 
                                          sheet = 2) %>% as.data.frame()
          nums_f <- nrow(feature_s)
          if (nums_f == 0){
            next
          }
          rownames(feature_s) <- feature_s[,1]
          feature_s <- feature_s[,-1]
          
          feature_s <- feature_s %>%
            mutate(mean = rowMeans(across(where(is.numeric)))) %>%
            arrange(-mean) %>%
            slice_head(n=20)
          feature_s <- feature_s[,-ncol(feature_s)]
          
          row_nums <- nrow(feature_s)
          
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
            feature_s <- as.data.frame(t(feature_s)) %>% 
              mutate(Others = (1 - rowSums((across(where(is.numeric)))))) %>%
              t() %>% as.data.frame()
          }
          

          nums <- ncol(feature_s)

          if (type == 'Groups'){
            order_s <- na.omit(match(unique(sample[, i+1]), colnames(feature_s)))
            feature_s <- feature_s[, order_s]
            colnames(feature_s) <- factor(colnames(feature_s), levels = colnames(feature_s))
          } else {
            order_s <- na.omit(match(sample$`sample-id`, colnames(feature_s)))
            feature_s <- feature_s[, order_s]
            colnames(feature_s) <- factor(colnames(feature_s), levels = colnames(feature_s))
          }
          
          feature_s$tax <- rownames(feature_s)
          feature_s$tax <- factor(feature_s$tax,levels = c(rev(rownames(feature_s))))
          feature_s <- melt(feature_s)

          p1 <- ggplot(data = feature_s, aes(x=variable, y=value, fill=tax))+
            geom_bar(stat="identity", position="stack", width=0.8) +
            theme_bw(base_family = '宋体',base_size = 12,base_line_size =0.3)+
            theme(panel.border = element_blank(),  #去外框
                  panel.grid = element_blank(),   #去网格
                  axis.line = element_line(linetype=1, color = 'black'), #加x,y轴
                  plot.title = element_text(hjust = 0.5, size = 12), #调整标题位置
                  axis.text.x  = element_text(color = 'black', angle = 90, vjust = 0.5),
                  axis.text.y  = element_text(color = 'black'),
                  axis.title.x = element_blank(),
                  legend.title = element_blank(),
            )+
            ggtitle(specie)+
            labs(y='Relative abundance (%)') +
            scale_y_continuous(expand = c(0,0), labels = percent_format()) +
            scale_fill_manual(values = yanse)
          
          ggp1 <- ggplotly(p1)
          resdir <- paste(res_dir, gro_num, '5-TaxAnnotation', '3.Barplot', type, class, sep = '/')
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          saveWidget(ggp1,file = paste0(resdir, '/', class, '_', specie,'.html'), selfcontained = T)
          
          if (nums > 25){
            p1 <- p1 + theme(legend.position = 'bottom',
                             legend.margin = ggplot2::margin(0,1,0.5,1,unit ='cm')) +
              guides(fill = guide_legend(ncol = ceiling(nums/25), byrow = T))
            ggsave(paste0(resdir, '/',class,'_', specie,'.pdf'), p1,
                   width =10+(nums/25)*2.5, height = 6+(nums/30), device = cairo_pdf)
            # ggsave(paste0(resdir, '/', specie,'.pdf'), p1, width =14, height = 7, device = cairo_pdf)
          } else {
            ggsave(paste0(resdir, '/',class,'_', specie,'.pdf'), p1, width =12, height = 7, device = cairo_pdf)
          }

          
        }
        
    }
  }
}






