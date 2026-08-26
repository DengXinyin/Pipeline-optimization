# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]
# 第四个参数为上游物种丰度表所在目录（tax_diff_update.py 中 pre_resdir 与 resdir 已分离）
pre_res_dir <- ifelse(length(args) >= 4, args[4], res_dir)

# tpm_dir <- 'D:/Rawdata/microbiome/SNFS042724090301-雷子莹-宏基因组测序/tax_diff'
# data_dir <- 'D:/Rawdata/microbiome/SNFS042724090301-雷子莹-宏基因组测序/data'
# res_dir <- 'D:/Rawdata/microbiome/SNFS042724090301-雷子莹-宏基因组测序/Result'

library(metagenomeSeq)
library(openxlsx)
library(dplyr)
library(pheatmap)
library(heatmaply)
library(RColorBrewer)
library(plotly)
library(htmlwidgets)
library(webshot)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

loadMeta_2 = function(file, sep = "\t") {
  dat2 <- read.table(file, header = FALSE, sep = sep, nrows = 1, quote = '',
                     stringsAsFactors = FALSE)
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

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')

# specie <- species[1]
# class <- classes[1]
# i = 1
for (i in 1: k){
  for (class in classes){
    gro_num <- paste0('group', i)
    table_dir <- paste(pre_res_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', class, sep = '/')
    
    for (specie in species){
      group <- sample[, c(1, i+1)]
      group <- na.omit(group[group[, 2] != '', ])
      colnames(group) <- c('samples', 'group')
      group$group <- factor(group$group, levels = unique(group$group))
      nums_gro <- length(unique(group$group))
      if (nums_gro == 2){
        file.name <- paste0(specie, '.xlsx')
        # feature_s <- read.xlsx(file.path(table_dir, file.name), 
        #                        sheet = 2, check.names = F)
        feature_s <- readxl::read_excel(file.path(table_dir, file.name), 
                                        sheet = 2) %>% as.data.frame()
        nums_f <- nrow(feature_s)
        if (nums_f < 2){
          next
        }
        
        tpmdir = paste(tpm_dir, gro_num, 'metagenome', class, sep = '/' )
        if (!file.exists(tpmdir)){dir.create(tpmdir, recursive = T)}
        write.table(feature_s, paste0(tpmdir, '/', specie, '.tsv'), 
                    sep = '\t', row.names = F, quote = F)
        
        otu = loadMeta_2(paste0(tpmdir, '/', specie, '.tsv'))
        otu$counts <- otu$counts[, colSums(is.na(otu$counts)) == 0]
        
        #保留group中otu表中有的sample，保留otu表中group中比对组数据
        idx = colnames(otu$counts)
        group = group[group[,1] %in% idx, ]
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
            if (length(display_map) > 0) {
              orig_colnames <- as.character(colnames(plot_sign))
              new_colnames <- display_map[orig_colnames]
              new_colnames[is.na(new_colnames)] <- orig_colnames[is.na(new_colnames)]
              colnames(plot_sign) <- new_colnames
              rownames(group) <- new_colnames[match(rownames(group), orig_colnames)]
            }
            p <- pheatmap(plot_sign,scale = 'row',
                          cluster_rows = T, cluster_cols = F,
                          annotation_col = group,
                          border_color = 'transparent',
                          fontsize = 10,
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
                              famliy="Times New Roman")
            resdir <- paste(res_dir, gro_num, '6-TaxStatistical_analysis', class, specie, '5.metagenomeSeq', sep = '/')
            if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
            
            saveWidget(ggp,file = paste0(resdir, '/', class, '_', specie,'_metagenomeSeq.html'), selfcontained = T)
            ggsave(paste0(resdir, '/', class, '_', specie,'_metagenomeSeq.pdf'), p, width =10, height = 7, device = cairo_pdf)
            write.xlsx(sheets, paste0(resdir, '/', class, '_', specie,'_metagenomeSeq.xlsx'),rowNames =T)
          }
      }
      
      
        
      } 
      
    }
  }
}
