# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# tpm_dir <- 'D:/宏基因组更新/func_diff'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

get_name = function(funcname){
  func.name <- gsub('/', '_', func.name)
  func.name <- gsub(':', '_', func.name)
  func.name <- gsub('->', '_', func.name)
  func.name <- gsub('=>', '_', func.name)
  func.name <- gsub(' ', '', func.name)
  func.name <- gsub('[.(]', '', func.name)
  func.name <- gsub('[.)]', '', func.name)
  # 只保留func.name前60个字符串，后面的字符串用...代替
  if (nchar(func.name) > 60){
    func.name <- substr(func.name, 1, 60)
    func.name <- paste0(func.name, '...')
  }
  return(func.name)
}

suppressPackageStartupMessages({
library(ggplot2)
library(reshape2)
library(scales)
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

# type <- types[1]
# i = 1
for (i in 1: k){
  for (type in types){
    gro_num <- paste0('group', i)
    table_dir <- paste(tpm_dir, gro_num, 'anova', type, sep = '/')
    
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    rownames(group) <- group$`sample-id`
    group <- group[, -1, drop=F]
    colnames(group) <- 'group'
    group$group <- factor(group$group, levels = unique(group$group))
    
    files = list.files(table_dir, pattern = '_sign.tsv')
    file = files[1]
    for (file in files){
      if (file.exists(file.path(table_dir, file))){
        prefix <- strsplit(file, '_sign.tsv')
        func_sign <- read.table(file.path(table_dir, file), quote = '',
                                 sep = '\t', header = T, check.names = F)
        nums <- nrow(func_sign)
        if (nums > 5){nums =5}
        for (j in 1:nums){
          row <- func_sign[j,]
          colnames(row)[1] <- 'pathway'
          row <- melt(row, id = c('pathway', 'F_value', 'p_value', 'padj'))
          row$group <- group[match(row$variable, rownames(group)),]
          p_value <- sprintf('%.3f', unique(row$p_value))
          func.name <- unique(row[,1])
          func.name <- get_name(func.name)
          p <- ggplot(data = row,aes(x=group, y=value, fill=group)) +
            stat_boxplot(geom = 'errorbar', width=0.3) +
            geom_boxplot()+
            theme_bw(base_family = '宋体',base_size = 12,base_line_size =0.5)+
            theme(panel.grid = element_blank(),    #去网格
                  legend.position = 'none',
                  axis.title.x = element_blank(),
                  plot.title = element_text(hjust = 0.5, size = 10),
                  axis.text = element_text(color="black"),
                  axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
                  axis.title = element_text(size = 11))+
            labs(y='Abundance')+
            scale_fill_manual(values = yanse)+
            ggtitle(paste0(func.name,', pvalue=',p_value))
          ggp <- ggplotly(p)
          
          # 保存结果
          if (type == '1.KEGG'){
            resdir = paste(res_dir, gro_num, '8-FunctionStatistical_analysis', type, '1.ANOVA', prefix, sep='/')
          } else if (type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
            resdir = paste(res_dir, gro_num, '8-FunctionStatistical_analysis', type, '1.ANOVA', sep='/')
          } else if (grepl('_Cycle', type)){
            resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '6.Statistical_test_analysis', '1.ANOVA', sep='/')
          } else if (type == 'ARG'){
            resdir = paste(res_dir, gro_num, '10-ARG','6.Statistical_test_analysis', '1.ANOVA', sep='/')
          } else if(type == 'VFDB'){
            resdir = paste(res_dir, gro_num, '11-VFDB', '6.Statistical_test_analysis','1.ANOVA', sep='/')
          } else if(type == 'mobileOG'){
            resdir = paste(res_dir, gro_num, '12-mobileOG', '6.Statistical_test_analysis','1.ANOVA', sep='/')
          } else if(type == 'BacMet2'){
            resdir = paste(res_dir, gro_num, '13-BacMet2', '6.Statistical_test_analysis','1.ANOVA', sep='/')
          } else if(type == 'QS'){
            resdir = paste(res_dir, gro_num, '14-QS', '6.Statistical_test_analysis','1.ANOVA', sep='/')
          }
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          saveWidget(ggp,file = paste0(resdir, '/', func.name,'.html'), selfcontained = T)
          k_gros <- length(unique(row$group))
          ggsave(paste0(resdir, '/', func.name,'.pdf'), p,
                 width =6+(k_gros/20)*1.5, height =  6+(k_gros/20)*0.5, device = cairo_pdf)
        }
        
      }
    }
    
    
    
  }
}