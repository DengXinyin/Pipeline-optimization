# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# tpm_dir <- 'D:/DEBUG/func_base'
# data_dir <- 'D:/DEBUG/data'
# res_dir <- 'D:/DEBUG/Result'

suppressPackageStartupMessages({
library(metagenomeSeq)
library(openxlsx)
library(dplyr)
library(pheatmap)
library(heatmaply)
library(RColorBrewer)
library(plotly)
library(htmlwidgets)
library(webshot)
})

loadMeta_2 = function(file, sep = "\t") {
  dat2 <- read.table(file, header = FALSE, sep = sep, nrows = 1, quote = '',
                     stringsAsFactors = FALSE)
  ncols <- ncol(dat2)
  if (ncols < 2){
    return(NULL)
  }
  subjects <- as.character(dat2[1, -1])
  classes <- c("character", rep("numeric", length(subjects)))
  dat3 <- read.table(file, header = FALSE, skip = 1, sep = sep, quote = '',
                       colClasses = classes, row.names = 1)
  colnames(dat3) = subjects
  taxa <- rownames(dat3)
  obj <- list(counts = as.data.frame(dat3), taxa = as.data.frame(taxa))
  return(obj)


}


sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
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
    nums_gro <- length(unique(group_o$group))
    
    files = list.files(table_dir, pattern = '_diff.tsv')
    file = files[1]
    for (file in files){
      if (file.exists(file.path(table_dir, file))){
        if (nums_gro == 2){
        prefix <- strsplit(file, '_diff.tsv')
        otu = loadMeta_2(file.path(table_dir, file))
        if (is.null(otu)){
          next
        }
        otu$counts <- otu$counts[, colSums(is.na(otu$counts)) == 0]
        
        #保留group中otu表中有的sample，保留otu表中group中比对组数据
        idx = colnames(otu$counts)
        group = group_o[group_o[,1] %in% idx, ]
        otu$counts <- otu$counts[, match(group[,1], colnames(otu$counts))]
        result <- apply(otu$counts, 1, function(row) all(row == row[1]))
        otu$counts <- otu$counts[result == F, ]
        rownames(group) = group[,1]
        group = group[2]
        
        phenotypeData = AnnotatedDataFrame(group)
        obj = newMRexperiment(otu$counts,phenoData=phenotypeData)
        
        #归一化计算
        res = try(cumNorm(obj, p = cumNormStatFast(obj)))
        if (!'try-error' %in% class(res)){
          obj = res
          pd <- pData(obj)
          mod <- model.matrix(~1 + group, data = pd)
          objres1 = fitFeatureModel(obj, mod)
          des = MRcoefs(objres1, number = nrow(otu$counts))
          des_sign = des[des$pvalues < 0.05, ]
          sheets = list('all'=des, 'diff'=des_sign)
          
          if (!is.null(des_sign) && nrow(des_sign) > 2){
            color <- colorRampPalette(c("blue", "white", "red"))(n = 50)
            des_sign <- arrange(des_sign, by_group= pvalues)
            otus_sign <- rownames(des_sign)[1:50]
            plot_sign <- na.omit(otu$counts[match(otus_sign, rownames(otu$counts)), ])
            p <- pheatmap(plot_sign,scale = 'row',
                          cluster_rows = T, cluster_cols = F,
                          annotation_col = group,
                          border_color = 'transparent',
                          fontsize = 9,
                          color = color,
                          #treeheight_row = 0
            )
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
            gro_color <- Set[as.factor(group$group)]
            gro_color <- as.data.frame(gro_color)
            colnames(gro_color) <- "Group"
            ggp <-  heatmaply(plot_sign,scale = 'row',show_grid  = F,
                              Rowv=T, Colv=F, dendrogram = 'row',
                              col=color, ColSideColors = gro_color,
                              showticklabels = c(T,T),
                              angle_col = 45,labRowSize =0.5,labColSize =0.5,
                              famliy="宋体")
            # 保存结果
            if (type == '1.KEGG'|type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
              resdir = paste(res_dir, gro_num, '8-FunctionStatistical_analysis', type, '5.metagenomeSeq', sep='/')
            } else if (grepl('_Cycle', type)){
              resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '6.Statistical_test_analysis', '5.metagenomeSeq', sep='/')
            } else if (type == 'ARG'){
              resdir = paste(res_dir, gro_num, '10-ARG','6.Statistical_test_analysis', '5.metagenomeSeq', sep='/')
            } else if(type == 'VFDB'){
              resdir = paste(res_dir, gro_num, '11-VFDB', '6.Statistical_test_analysis','5.metagenomeSeq', sep='/')
            } else if(type == 'mobileOG'){
              resdir = paste(res_dir, gro_num, '12-mobileOG', '6.Statistical_test_analysis','5.metagenomeSeq', sep='/')
            } else if(type == 'BacMet2'){
              resdir = paste(res_dir, gro_num, '13-BacMet2', '6.Statistical_test_analysis','5.metagenomeSeq', sep='/')
            } else if(type == 'QS'){
              resdir = paste(res_dir, gro_num, '14-QS', '6.Statistical_test_analysis','5.metagenomeSeq', sep='/')
            }
            
            if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
            
            saveWidget(ggp,file = paste0(resdir, '/', prefix,'_metagenomeSeq.html'), selfcontained = T)
            ggsave(paste0(resdir,'/', prefix,'_metagenomeSeq.pdf'), p, width =9, height = 7, device = cairo_pdf)
            write.xlsx(sheets, paste0(resdir, '/',prefix, '_metagenomeSeq.xlsx'),rowNames =T)
          }
        }
        
        
        
        }
      }
    }
    
  }
}
