# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'
# data_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/data2'
# res_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'

library(vegan)
library(openxlsx)
library(dplyr)

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')

# specie <- species[1]
# class <- classes[1]
# i = 3
for (i in 1: k){
  for (class in classes){
    gro_num <- paste0('group', i)
    type_dir <- paste(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', class, sep = '/')
    
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    colnames(group) <- c('samples','group')
    group$group <- factor(group$group, levels = unique(group$group))
    
    for (specie in species){
      file.name <- paste0(specie, '.xlsx')
      # taxab <- read.xlsx(file.path(type_dir, file.name), 
      #                    sheet = 2, rowNames = T, check.names = F)
      taxab <- readxl::read_excel(file.path(type_dir, file.name), 
                                  sheet = 2) %>% as.data.frame()
      nums_f <- nrow(taxab)
      if (nums_f < 2){
        next
      }
      rownames(taxab) <- taxab[,1]
      taxab <- taxab[,-1]
      
      taxab <- taxab[, colSums(is.na(taxab)) == 0]
      rownum <- nrow(taxab)
      taxab <- taxab[, colSums(taxab == 0) != rownum]
      group <- group[group$samples %in% colnames(taxab),]
      bray <- vegdist(t(taxab),method = 'bray')
      Adonis <- adonis2(bray~group,data=group,distance = "bray",permutations = 999)
      
      resdir <- paste(res_dir, gro_num, '6-TaxStatistical_analysis', class, specie, '7.Adonis', sep = '/')
      if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
      
      write.xlsx(Adonis, file = file.path(resdir, 'Adonis.xlsx'), rowNames = T)
      
    }
  }
}
