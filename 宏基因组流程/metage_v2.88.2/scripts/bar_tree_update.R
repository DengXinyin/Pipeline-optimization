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

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')
display_map <- load_display_name_map(data_dir)

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    colClasses = 'character',header = T, check.names = F, fill = TRUE)
k = ncol(sample) -1

species <- c('phylum', 'class', 'order', 'family', 'genus', 'species')
classes <- c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')

# 稀疏分类表（尤其是 Archaea/Virus）可能包含全零样本。Bray-Curtis
# 对两个空样本的距离没有定义，继续传给 hclust 会产生 NA 并终止整个流程。
# 将跳过信息同时写入任务日志和结构化 TSV，便于报告阶段追踪缺图原因。
skip_log <- file.path(res_dir, 'logs', 'tax_base', 'bar_tree_skipped.tsv')
record_skip <- function(group_name, tax_class, tax_rank, reason, samples = character()) {
  log_dir <- dirname(skip_log)
  if (!dir.exists(log_dir)) {
    dir.create(log_dir, recursive = TRUE, showWarnings = FALSE)
  }
  sample_text <- if (length(samples) == 0) '' else paste(samples, collapse = ',')
  entry <- data.frame(
    group = group_name,
    class = tax_class,
    rank = tax_rank,
    reason = reason,
    samples = sample_text,
    stringsAsFactors = FALSE
  )
  append_log <- file.exists(skip_log)
  write.table(entry, skip_log, sep = '\t', quote = FALSE, row.names = FALSE,
              col.names = !append_log, append = append_log)
  message(sprintf('[SKIP] bar_tree %s/%s/%s: %s%s',
                  group_name, tax_class, tax_rank, reason,
                  if (nzchar(sample_text)) paste0('; samples=', sample_text) else ''))
}

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
          record_skip(gro_num, class, specie, 'no_taxa')
          next
        }
        rownames(feature_s) <- feature_s[,1]
        feature_s <- feature_s[,-1]

        # 丰度列应为数值；缺失值或非有限值按 0 处理，避免污染距离矩阵。
        feature_s[] <- lapply(feature_s, function(x) suppressWarnings(as.numeric(x)))
        feature_s[!is.finite(as.matrix(feature_s))] <- 0

        feature_s <- feature_s %>%
          mutate(mean = rowMeans(across(where(is.numeric)))) %>%
          arrange(-mean) %>%
          slice_head(n=20)
        feature_s <- feature_s[,-ncol(feature_s)]

        sample_totals <- colSums(feature_s, na.rm = TRUE)
        empty_samples <- names(sample_totals)[!is.finite(sample_totals) | sample_totals <= 0]
        if (length(empty_samples) > 0) {
          message(sprintf('[INFO] bar_tree %s/%s/%s: remove %d all-zero sample(s): %s',
                          gro_num, class, specie, length(empty_samples),
                          paste(empty_samples, collapse = ',')))
          feature_s <- feature_s[, setdiff(colnames(feature_s), empty_samples), drop = FALSE]
        }

        if (ncol(feature_s) < 2) {
          record_skip(gro_num, class, specie,
                      sprintf('fewer_than_2_nonzero_samples (%d)', ncol(feature_s)),
                      empty_samples)
          next
        }

        bray <- vegdist(t(feature_s),method = "bray")
        if (length(bray) == 0 || any(!is.finite(bray))) {
          record_skip(gro_num, class, specie, 'non_finite_bray_distance', empty_samples)
          next
        }
        tree <- upgma(as.matrix(bray), method = 'average') #distance matrix
        group <- sample[, c(1, i+1)]
        group <- na.omit(group[group[, 2] != '', ])
        colnames(group) <- c('label', 'group')
        group <- group[group$label %in% colnames(feature_s), , drop = FALSE]
        group$group <- factor(group$group, levels = unique(group$group))
        tree <- left_join(as_tibble(tree), group, by='label')
        if (length(display_map) > 0) {
          tree$display_label <- display_map[tree$label]
          tree$display_label[is.na(tree$display_label)] <- tree$label[is.na(tree$display_label)]
        } else {
          tree$display_label <- tree$label
        }
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
          geom_tiplab(size=4.4,aes(label=display_label,color=group,x=x*1.5), hjust = 1) +
          guides(color = guide_legend(override.aes = list(label = "", size = 3)))+
          scale_color_discrete(na.translate=FALSE) +
          theme(legend.title = element_blank(),
                legend.text = element_text(size = 18),
                axis.title = element_text(size = 18),
                axis.text = element_text(size = 16),
                plot.title = element_text(size = 22, hjust = 0.5),
                text = element_text(size=16, family='Times New Roman'))
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
