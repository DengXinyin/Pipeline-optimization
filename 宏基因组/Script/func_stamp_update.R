# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
tpm_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# tpm_dir <- 'D:/宏基因组更新/func_base'
# data_dir <- 'D:/宏基因组更新/data'
# res_dir <- 'D:/宏基因组更新/Result'

suppressPackageStartupMessages({
library(ggplot2)
library(dplyr)
library(pheatmap)
library(devtools)
library(tidyverse)
library(openxlsx)
library(plotly)
library(htmlwidgets)
})

yanse <-c("#377EB8","#FF7F00","#CE50CA",'#20B2AA',"#C0717C",
          '#FFE4E1','#EEDC82','#FFC125','#CD5C5C',"#CBD588",
          "#E41A1C","#DA5724","#74D944","#F781BF","#FFFF33",
          "#689030","#D3D93E","#984EA3","#A65628",
          "#4DAF4A","#AD6F3B",'#00F5FF','#76EEC6',"#38333E",
          "#D7C1B1","#5F7FC7","#673770","#3F4921","#CD9BCD",
          '#8B3A3A')
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
    
    group <- sample[, c(1, i+1)]
    group <- na.omit(group[group[, 2] != '', ])
    rownames(group) <- group$`sample-id`
    group <- group[, -1, drop=F]
    colnames(group) <- 'group'
    group$group <- factor(group$group, levels = unique(group$group))
    
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
        data <- func_s
        # data <- func_s %>% summarise(across(where(is.numeric), ~.x/sum(.x)))
        # rownames(data) <- rownames(func_s)
        
        func_s <- as.data.frame(t(data))
        group <- group[rownames(group) %in% rownames(func_s), , drop=F]
        func_s$Group <- group[match(rownames(group), rownames(func_s)), ]
        func_s$Group <- as.factor(func_s$Group)
        if (length(unique(group$group)) == 2){
          diff <- func_s %>% 
            select_if(is.numeric) %>%
            map_df(~ broom::tidy(t.test(. ~ Group,data=func_s)), .id='var')
          # c("holm", "hochberg", "hommel", "bonferroni", "BH", "BY", "fdr", "none")
          diff$p.value <- p.adjust(diff$p.value, "fdr")
          #diff <- diff %>% filter(p.value < opts$pvalue)
          #不筛选p值，转为按p值排序取得排序前20的作图
          diff <- na.omit(diff) %>% arrange(p.value) %>% 
            slice_head(n = 20)
          
          ## 绘图数据构建
          ## 左侧条形图
          abun.bar <- func_s[,c(diff$var,"Group")] %>% 
            gather(variable,value,-Group) %>% 
            group_by(variable,Group) %>% 
            summarise(Mean=mean(value))
          
          ## 右侧散点图
          diff.mean <- diff[,c("var","estimate","conf.low","conf.high","p.value")]
          diff.mean$Group <- c(ifelse(diff.mean$estimate >0,levels(func_s$Group)[1],
                                      levels(func_s$Group)[2]))
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
                  axis.title.x=element_text(colour='black', size=12,family='宋体',),
                  axis.text=element_text(colour='black',size=10,family='宋体',),
                  legend.title=element_blank(),
                  legend.text=element_text(size=12,colour="black",family='宋体',
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
                  axis.title.x=element_text(colour='black', size=12,family='宋体'),
                  axis.text=element_text(colour='black',size=10,family='宋体'),
                  axis.text.y=element_blank(),
                  legend.position="none",
                  axis.line.y=element_blank(),
                  axis.ticks.y=element_blank(),
                  plot.title=element_text(size=12,colour="black",hjust=0.5)) +
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
                      hjust=0,inherit.aes=FALSE,size=4,family='宋体') +
            geom_text(aes(x=nrow(diff.mean)/2 +0.5,y=0.85),label="P-value (corrected)",
                      family='宋体',srt=90,size=4) +
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
          
          
          # 保存结果
          if (type == '1.KEGG'|type == '2.eggNOG'|type =='3.CAZy'|type == '4.GO'){
            resdir = paste(res_dir, gro_num, '8-FunctionStatistical_analysis', type, '3.Stamp', sep='/')
          } else if (grepl('_Cycle', type)){
            resdir = paste(res_dir, gro_num, '9-METABOLIC', type, '6.Statistical_test_analysis', '3.Stamp', sep='/')
          } else if (type == 'ARG'){
            resdir = paste(res_dir, gro_num, '10-ARG','6.Statistical_test_analysis', '3.Stamp', sep='/')
          } else if(type == 'VFDB'){
            resdir = paste(res_dir, gro_num, '11-VFDB', '6.Statistical_test_analysis','3.Stamp', sep='/')
          } else if(type == 'mobileOG'){
            resdir = paste(res_dir, gro_num, '12-mobileOG', '6.Statistical_test_analysis','3.Stamp', sep='/')
          } else if(type == 'BacMet2'){
            resdir = paste(res_dir, gro_num, '13-BacMet2', '6.Statistical_test_analysis','3.Stamp', sep='/')
          } else if(type == 'QS'){
            resdir = paste(res_dir, gro_num, '14-QS', '6.Statistical_test_analysis','3.Stamp', sep='/')
          }
          if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
          
          saveWidget(ggp,file = paste0(resdir, '/', prefix,'.html'), selfcontained = T)
          ggsave(paste0(resdir, '/', prefix,'.pdf'), p, width =11.5, height = 7, device = cairo_pdf)
          # write.csv(diff, paste0(resdir,'/', prefix,'_t.test.csv'), row.names = F)
        }
        
        
        
        
      }
    }
  }
}
