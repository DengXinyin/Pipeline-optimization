# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'
# data_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/data'
# res_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'

library(ggplot2)
library(vegan)
library(ggtree)
library(treeio)
library(phangorn)
library(ggstance)
library(reshape2)
library(dplyr)
library(openxlsx)
library(scales)
library(plotly)
library(htmlwidgets)

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
      type_dir <- paste(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', class, sep = '/')
      
      for (specie in species){
        file.name <- paste0(specie, '.xlsx')
        # readxl解决中文乱码问题，相应需要设置第一列为行名，2024.09.13 by Wang
        # feature_s <- read.xlsx(file.path(type_dir, file.name), 
        #                        sheet = 2, rowNames = T, check.names = F)
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
        bray <- vegdist(t(feature_s),method = "bray")
        tree <- upgma(as.matrix(bray), method = 'average') #distance matrix
        group <- sample[, c(1, i+1)]
        group <- na.omit(group[group[, 2] != '', ])
        colnames(group) <- c('label', 'group')
        group$group <- factor(group$group, levels = unique(group$group))
        tree <- full_join(as_tibble(tree), group, by='label')
        tree_p <- as.treedata(tree)
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
        
        order_s <- na.omit(match(sample$`sample-id`, colnames(feature_s)))
        feature_s <- feature_s[, order_s]
        colnames(feature_s) <- factor(colnames(feature_s), levels = colnames(feature_s))
        
        k <- ncol(feature_s)
        feature_s$tax <- rownames(feature_s)
        feature_s$tax <- factor(feature_s$tax,levels = c(rev(rownames(feature_s))))
        feature_s <- melt(feature_s)
        feature_s <- data.frame(label=feature_s$variable,
                                tax=feature_s$tax,
                                value=feature_s$value)
        
        p1 <- ggtree(tree_p) +                      
          geom_tree(size=0.5,aes(color=group)) +
          geom_tiplab(size=3,aes(color=group,x=x*1.5), hjust = 1) +
          guides(color = guide_legend(override.aes = list(label = "", size = 3)))+
          scale_color_discrete(na.translate=FALSE) +
          theme(legend.title = element_blank(),
                text = element_text(size=12, family='宋体'))
        p2 <- ggtree::facet_plot(p1, data = feature_s,
                         panel = 'Taxonomic composition', 
                         geom = geom_barh,
                         mapping = aes(x=value, fill=tax),
                         stat="identity")+ 
          scale_fill_manual(values = yanse) +
          theme(strip.text = element_blank())
        
        resdir <- paste(res_dir, gro_num, '5-TaxAnnotation', '4.Bar_tree', class, sep = '/')
        if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
        if (k < 50){
          ggsave(paste0(resdir,'/',class, '_',specie,'_tree_bar.pdf'),p2,width = 12,height = 8, device = cairo_pdf)
        } else{
          ggsave(paste0(resdir,'/',class,'_', specie,'_tree_bar.pdf'),p2,
                 width = 12+(k/50)*1,height = 9+(k/50)*2, device = cairo_pdf)
        }
        
    }
  }
}