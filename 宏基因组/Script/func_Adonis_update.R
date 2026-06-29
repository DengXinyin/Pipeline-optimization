# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# tpm_dir <- 'D:/宏基因组更新/func_base'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

suppressPackageStartupMessages({
library(vegan)
library(openxlsx)
library(dplyr)
})

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
    table_dir <- paste(tpm_dir, gro_num, type, sep = '/')
    
    group_o <- sample[, c(1, i+1)]
    group_o <- na.omit(group_o[group_o[, 2] != '', ])
    colnames(group_o) <- c('samples', 'group')
    group_o$group <- as.factor(group_o$group)
    
    files = list.files(table_dir, pattern = '_diff.tsv')
    file = files[1]
    for (file in files){
      if (file.exists(file.path(table_dir, file))){
        prefix <- strsplit(file, '_diff.tsv')
        func_s <- read.table(file.path(table_dir, file), row.names = 1,quote = "",
                             sep = '\t', header = T, check.names = F)
        number_row = nrow(func_s)
        if (number_row < 2){
          next
        }
        
        func_s <- func_s[, colSums(is.na(func_s)) == 0]
        rownum <- nrow(func_s)
        func_s <- func_s[, colSums(func_s == 0) != rownum]
        group <- group_o[group_o$samples %in% colnames(func_s),]
        bray <- vegdist(t(func_s),method = 'bray')
        Adonis <- adonis2(bray~group,data=group,distance = "bray",permutations = 999)
        
        # 保存结果
        if (type == '1.KEGG'|type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
          resdir = paste(res_dir, gro_num, '8-FunctionStatistical_analysis', type, '7.Adonis', sep='/')
        } else if (grepl('_Cycle', type)){
          resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '6.Statistical_test_analysis', '7.Adonis', sep='/')
        } else if (type == 'ARG'){
          resdir = paste(res_dir, gro_num, '10-ARG','6.Statistical_test_analysis', '7.Adonis', sep='/')
        } else if(type == 'VFDB'){
          resdir = paste(res_dir, gro_num, '11-VFDB', '6.Statistical_test_analysis','7.Adonis', sep='/')
        } else if(type == 'mobileOG'){
          resdir = paste(res_dir, gro_num, '12-mobileOG', '6.Statistical_test_analysis','7.Adonis', sep='/')
        } else if(type == 'BacMet2'){
          resdir = paste(res_dir, gro_num, '13-BacMet2', '6.Statistical_test_analysis','7.Adonis', sep='/')
        } else if(type == 'QS'){
          resdir = paste(res_dir, gro_num, '14-QS', '6.Statistical_test_analysis','7.Adonis', sep='/')
        }
        
        if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
        
        write.xlsx(Adonis, file = paste0(resdir, '/', prefix,'_Adonis.xlsx'), rowNames = T)
        
      }
    }
  }
}