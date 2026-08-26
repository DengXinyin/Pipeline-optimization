# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'
# data_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/data2'
# res_dir <- 'D:/Rawdata/microbiome/SNYC042724032002-郭俊-宏基因组测序/Result'

library(ggplot2)
library(dplyr)
library(pheatmap)
library(devtools)
library(tidyverse)
library(openxlsx)
library(plotly)
library(htmlwidgets)

sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    header = T, check.names = F, fill = TRUE)
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
    
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    rownames(group) <- group$`sample-id`
    group <- group[, -1, drop=F]
    colnames(group) <- 'group'
    group$group <- factor(group$group, levels = unique(group$group))
    
    for (specie in species){
        file.name <- paste0(specie, '.xlsx')
        # readxl解决中文乱码问题，相应需要设置第一列为行名，2024.09.13 by Wang
        # feature_s <- read.xlsx(file.path(type_dir, file.name), 
        #                        sheet = 2, rowNames = T, check.names = F)
        feature_s <- readxl::read_excel(file.path(type_dir, file.name), 
                                        sheet = 2) %>% as.data.frame()
        nums_f <- nrow(feature_s)
        if (nums_f < 2){
          next
        }
        rownames(feature_s) <- feature_s[,1]
        feature_s <- feature_s[,-1]
        
        feature_s <- as.data.frame(t(feature_s))
        group <- group[rownames(group) %in% rownames(feature_s), , drop=F]
        feature_s$Group <- group[match(rownames(group), rownames(feature_s)), ]
        feature_s$Group <- factor(feature_s$Group, levels = unique(feature_s$Group))
        if (length(unique(group$group)) == 2){
          diff <- feature_s %>% 
            select_if(is.numeric) %>%
            map_df(~ broom::tidy(t.test(. ~ Group,data=feature_s)), .id='var')
          # c("holm", "hochberg", "hommel", "bonferroni", "BH", "BY", "fdr", "none")
          diff$p.value <- p.adjust(diff$p.value, "fdr")
          #diff <- diff %>% filter(p.value < opts$pvalue)
          #不筛选p值，转为按p值排序取得排序前20的作图
          diff <- na.omit(diff) %>% arrange(p.value) %>% 
            slice_head(n = 20)
          
          ## 绘图数据构建
          ## 左侧条形图
          abun.bar <- feature_s[,c(diff$var,"Group")] %>% 
            gather(variable,value,-Group) %>% 
            group_by(variable,Group) %>% 
            summarise(Mean=mean(value))
          
          ## 右侧散点图
          diff.mean <- diff[,c("var","estimate","conf.low","conf.high","p.value")]
          diff.mean$Group <- c(ifelse(diff.mean$estimate >0,levels(feature_s$Group)[1],
                                      levels(feature_s$Group)[2]))
          diff.mean <- diff.mean[order(diff.mean$estimate,decreasing=TRUE),]
          
          ## 左侧条形图
          library(ggplot2)
          cbbPalette <- c("#E69F00", "#56B4E9")
          abun.bar$variable <- factor(abun.bar$variable,levels=rev(diff.mean$var))
          p1 <- ggplot(abun.bar,aes(variable,Mean,fill=Group)) +
            scale_x_discrete(limits=levels(diff.mean$var)) +
            coord_flip() +
            xlab("") +
            ylab("Mean proportion") +
            theme(panel.background=element_rect(fill='transparent'),
                  panel.grid=element_blank(),
                  axis.ticks.length=unit(0.4,"lines"), 
                  axis.ticks=element_line(color='black'),
                  axis.line=element_line(colour="black"),
                  axis.title.x=element_text(colour='black', size=14,family='Times New Roman',),
                  axis.text=element_text(colour='black',size=12,family='Times New Roman',),
                  legend.title=element_blank(),
                  legend.text=element_text(size=14,colour="black",family='Times New Roman',
                                           margin=margin(r=20)),
                  legend.position="top",
                  legend.direction="horizontal",
                  legend.key.width=unit(0.8,"cm"),
                  legend.key.height=unit(0.5,"cm"))
          
          
          for (j in 1:(nrow(diff.mean) - 1)) 
            p1 <- p1 + annotate('rect', xmin=j+0.5, xmax=j+1.5, ymin=-Inf, ymax=Inf, 
                                fill=ifelse(j %% 2 == 0, 'white', 'gray95'))
          
          p1 <- p1 + 
            geom_bar(stat="identity",position="dodge",width=0.7,colour="black") +
            scale_fill_manual(values=cbbPalette)
          
          
          ## 右侧散点图
          diff.mean$var <- factor(diff.mean$var,levels=levels(abun.bar$variable))
          diff.mean$p.value <- signif(diff.mean$p.value,3)
          diff.mean$p.value <- as.character(diff.mean$p.value)
          p2 <- ggplot(diff.mean,aes(var,estimate,fill=Group)) +
            theme(panel.background=element_rect(fill='transparent'),
                  panel.grid=element_blank(),
                  axis.ticks.length=unit(0.4,"lines"), 
                  axis.ticks=element_line(color='black'),
                  axis.line=element_line(colour="black"),
                  axis.title.x=element_text(colour='black', size=14,family='Times New Roman'),
                  axis.text=element_text(colour='black',size=12,family='Times New Roman'),
                  axis.text.y=element_blank(),
                  legend.position="none",
                  axis.line.y=element_blank(),
                  axis.ticks.y=element_blank(),
                  plot.title=element_text(size=14,colour="black",hjust=0.5)) +
            scale_x_discrete(limits=levels(diff.mean$var)) +
            coord_flip() +
            xlab("") +
            ylab("Difference in mean proportions") +
            labs(title="95% confidence intervals") 
          
          for (z in 1:(nrow(diff.mean) - 1)) 
            p2 <- p2 + annotate('rect', xmin=z+0.5, xmax=z+1.5, ymin=-Inf, ymax=Inf, 
                                fill=ifelse(z %% 2 == 0, 'white', 'gray95'))
          
          p2 <- p2 +
            geom_errorbar(aes(ymin=conf.low, ymax=conf.high), 
                          position=position_dodge(0.8), width=0.5, size=0.5) +
            geom_point(shape=21,size=3) +
            scale_fill_manual(values=cbbPalette) +
            geom_hline(aes(yintercept=0), linetype='dashed', color='black')
          
          
          p3 <- ggplot(diff.mean,aes(var,estimate,fill=Group)) +
            geom_text(aes(y=0,x=var),label=diff.mean$p.value,
                      hjust=0,inherit.aes=FALSE,size=4.7,family='Times New Roman') +
            geom_text(aes(x=nrow(diff.mean)/2 +0.5,y=0.85),label="P-value (corrected)",
                      family='Times New Roman',srt=90,size=4.7) +
            coord_flip() +
            ylim(c(0,1)) +
            theme(panel.background=element_blank(),
                  panel.grid=element_blank(),
                  axis.line=element_blank(),
                  axis.ticks=element_blank(),
                  axis.text=element_blank(),
                  axis.title=element_blank())
          library(patchwork)
          (p <- p1 + p2 + p3 + plot_layout(widths=c(4,5,2)))
          
          ggp1 <- ggplotly(p1)
          ggp2 <- ggplotly(p2)
          ggp3 <- ggplotly(p3)
          ggp <- subplot(ggp1, ggp2, ggp3, nrows = 1)
          
          resdir <- paste(res_dir, gro_num, '6-TaxStatistical_analysis', class, specie, '3.Stamp', sep = '/')
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          #saveWidget(ggp,file = paste0(resdir,'/', class, '_', specie,'_stamp.html'), selfcontained = T)
          ggsave(paste0(resdir, '/',class, '_', specie,'_stamp.pdf'), p, width =11, height = 7, device = cairo_pdf)
          openxlsx::write.xlsx(diff, paste0(resdir,'/',class, '_', specie, '_stamp.xlsx'), rowNames = F)
          # write.csv(diff, file.path(resdir,'t.test.csv'), row.names = F)
        }

    }
  }
}
