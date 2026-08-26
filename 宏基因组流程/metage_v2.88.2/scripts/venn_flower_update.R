# 20260618更新：在sample-metadata.tsv的read.table读取过程中补充fill = TRUE参数，避免 sample-metadata.tsv 列数不齐时报错。
args <- commandArgs(trailingOnly = TRUE)
table_dir <- args[1]
data_dir <- args[2]
res_dir <- args[3]

# table_dir <- 'D:/新建文件夹'
# data_dir <- 'D:/新建文件夹/data'
# res_dir <- 'D:/新建文件夹/Result'

library(ggplot2)
library(ggvenn)
library(dplyr)
library(UpSetR)
library(plotrix)
library(openxlsx)
library(plotly)
library(htmlwidgets)
library(ggVennDiagram)
library(sf)

source('/root/microbiome/microbiome/metage_v2.88.2/display_name_map.R')

plot_venn2 <- function(venn_list){
  venn <- ggVennDiagram::Venn(venn_list)
  venn_data<- ggVennDiagram::process_data(venn)
  items <- venn_region(venn_data) %>%
    dplyr::rowwise() %>%
    dplyr::mutate(text = yulab.utils::str_wrap(paste0(.data$item, collapse = "; "),
                                               width = 40)) %>%
    sf::st_as_sf()
  
  label_coord = sf::st_centroid(items$geometry) %>% sf::st_coordinates()
  p <- ggplot(items) +
    geom_sf(aes_string(fill="count")) +
    geom_sf_text(aes_string(label = "name"), size = 5.4,
                 data = venn_data@setLabel,
                 inherit.aes = F) +
    geom_text(aes_string(label = "count", text = "text"),
              x = label_coord[,1],
              y = label_coord[,2],
              size = 5.4,
              show.legend = FALSE) +
    theme_void(base_family = 'Times New Roman', base_size = 16) +
    theme(legend.text = element_text(size = 18),
          legend.title = element_text(size = 20)) +
    scale_fill_distiller(palette = "RdBu")
  ax <- list(
    showline = FALSE
  )
  ggp <- plotly::ggplotly(p, tooltip = c("text")) %>%
    plotly::layout(
      xaxis = ax, yaxis = ax,
      font = list(family = 'Times New Roman', size = 16),
      legend = list(font = list(size = 18), title = list(font = list(size = 20)))
    )
  return(list(img=p,html=ggp))
}

# UpSetR 的部分子图不会显式设置 panel.border，因此会继承全局
# theme_bw() 的矩形框线。仅在绘制 UpSet 图时关闭面板边框，保留坐标轴线。
plot_upset_no_frame <- function(upset_data, output_pdf) {
  previous_theme <- ggplot2::theme_get()
  device_before <- grDevices::dev.cur()
  on.exit({
    if (grDevices::dev.cur() != device_before) grDevices::dev.off()
    ggplot2::theme_set(previous_theme)
  }, add = TRUE)

  ggplot2::theme_set(
    previous_theme + ggplot2::theme(panel.border = ggplot2::element_blank())
  )
  grDevices::cairo_pdf(
    output_pdf, width = 8, height = 8, family = 'Times New Roman'
  )
  upset_plot <- UpSetR::upset(
    upset_data, nsets = 30, nintersects = 45,
    order.by = "freq", decreasing = TRUE,
    matrix.color = '#2E86C1',
    main.bar.color = '#1F618D', show.numbers = FALSE,
    sets.bar.color = '#424949',
    text.scale = 1.4
  )
  print(upset_plot)
  grDevices::dev.off()
  ggplot2::theme_set(previous_theme)
}

tpm <- read.csv(file.path(table_dir, 'gene_tpm.csv'), check.names = F, row.names = 1)
sample = read.table(file.path(data_dir, 'sample-metadata.tsv'), sep = '\t',
                    header = T, check.names = F, fill = TRUE) # 添加 fill = TRUE 参数，避免 sample-metadata.tsv 列数不齐时报错。
display_map <- load_display_name_map(data_dir)
for (i in 2: ncol(sample)){
  sap_gro = sample[sample[, i] != '', c(1,i)]
  samps = sap_gro$`sample-id`
  group_id = paste0('group', i-1)
  resdir <- paste0(res_dir, '/', group_id, '/4-GeneAbundance/Venn/')
  if (!file.exists(resdir)){dir.create(resdir, recursive = T)}
  
  sam_tpm <- as.data.frame(t(tpm[, colnames(tpm) %in% sap_gro$`sample-id`]))
  
  # Venn
  tpm_ls <- split(sam_tpm, rownames(sam_tpm))
  venn_ls <- list()
  for (j in 1:length(tpm_ls)){
    Var_name = names(tpm_ls)[j]
    Var_value = tpm_ls[[j]]
    Var_value = Var_value[, which(colSums(Var_value) > 0)]
    venn_ls[[Var_name]] = colnames(Var_value)
  }
  if (length(display_map) > 0) {
    venn_names <- names(venn_ls)
    new_venn_names <- display_map[venn_names]
    new_venn_names[is.na(new_venn_names)] <- venn_names[is.na(new_venn_names)]
    names(venn_ls) <- new_venn_names
  }
  if (length(tpm_ls) == 2) {
    # 两两韦恩图
    venn_res <- plot_venn2(venn_ls)
    p <- venn_res$img
    ggp <- venn_res$html
    saveWidget(ggp,file = paste0(resdir,'/venn.html'), selfcontained = T)
    cairo_pdf(paste0(resdir,'/venn.pdf'),width = 5,height = 5,family = 'Times New Roman')
    print(p)
    dev.off()
  } else if (length(tpm_ls) < 5){
    # 韦恩图
    cairo_pdf(paste0(resdir,'/venn.pdf'),width = 5,height = 5,family = 'Times New Roman')
    pVenn <- ggvenn(data = venn_ls,
                    stroke_color = F,
                    label_sep = "\n", 
                    set_name_size = 5.4,
                    text_size = 5.4,
                    show_percentage = F
    )
    print(pVenn)
    dev.off()
  } else {
    # upset图
    tpm_upset <- ifelse(sam_tpm==0, 0, 1) %>% t() %>% as.data.frame()
    if (length(display_map) > 0) {
      upset_cols <- colnames(tpm_upset)
      new_upset_cols <- display_map[upset_cols]
      new_upset_cols[is.na(new_upset_cols)] <- upset_cols[is.na(new_upset_cols)]
      colnames(tpm_upset) <- new_upset_cols
    }
    plot_upset_no_frame(tpm_upset, paste0(resdir, '/upset.pdf'))
  }
  
}
