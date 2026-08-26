#!/usr/bin/env Rscript
# COG 可视化（standalone 版）
# 输入：COG 统计输出目录（含 COG.Category.xlsx, COG.Function.xlsx, COG.xlsx）
# 输出：barplot.pdf/html, heatmap.pdf/html

args <- commandArgs(trailingOnly = TRUE)
cog_dir <- args[1]
res_dir <- args[2]

suppressPackageStartupMessages({
  library(ggplot2)
  library(reshape2)
  library(dplyr)
  library(openxlsx)
  library(scales)
  library(plotly)
  library(htmlwidgets)
  library(pheatmap)
})

if (!dir.exists(res_dir)) dir.create(res_dir, recursive = TRUE)

# 配色
cog_colors <- c("#377EB8", "#FF7F00", "#CE50CA", "#20B2AA", "#C0717C",
                "#FFE4E1", "#EEDC82", "#FFC125", "#CD5C5C", "#CBD588",
                "#E41A1C", "#DA5724", "#74D944", "#F781BF", "#FFFF33",
                "#689030", "#D3D93E", "#984EA3", "#A65628", "#4DAF4A",
                "#AD6F3B", "#00F5FF", "#76EEC6", "#38333E", "#D7C1B1")

plot_stacked_bar <- function(df, out_pdf, out_html, title, ylabel = "Relative abundance (%)") {
  if (nrow(df) == 0) return()
  names(df)[1] <- "pathway"
  # 仅对数值列（样本列）计算均值；兼容 COG.xlsx 中的 description 等字符列
  num_cols <- names(df)[sapply(df, is.numeric)]
  if (length(num_cols) == 0) {
    warning(paste("No numeric columns found in", title, "- skipping plot"))
    return()
  }
  # 保留 top 20，其余归为 Others
  df$mean <- rowMeans(df[, num_cols, drop = FALSE], na.rm = TRUE)
  df <- df %>% arrange(-mean)
  if (nrow(df) > 20) {
    top <- df[1:20, ]
    others <- df[21:nrow(df), num_cols, drop = FALSE] %>% colSums(na.rm = TRUE)
    others_df <- data.frame(pathway = "Others", t(others), stringsAsFactors = FALSE)
    colnames(others_df)[-1] <- num_cols
    top <- top[, c("pathway", num_cols)]
    df <- bind_rows(top, others_df)
  } else {
    df <- df[, c("pathway", num_cols)]
  }

  df$pathway <- as.character(df$pathway)
  df$pathway <- factor(df$pathway, levels = rev(unique(df$pathway)))
  df_melt <- melt(df, id.vars = "pathway")
  df_melt$value <- as.numeric(df_melt$value)

  p <- ggplot(df_melt, aes(x = variable, y = value, fill = pathway)) +
    geom_bar(stat = "identity", position = "stack", width = 0.8) +
    metage_theme() +
    theme(panel.border = element_blank(),
          panel.grid = element_blank(),
          axis.line = element_line(color = "black"),
          plot.title = element_text(hjust = 0.5, size = 20),
          axis.text.x = element_text(angle = 90, vjust = 0.5),
          axis.title.x = element_blank(),
          legend.title = element_blank()) +
    labs(title = title, y = ylabel) +
    scale_y_continuous(expand = c(0, 0), labels = percent_format()) +
    scale_fill_manual(values = cog_colors)

  ggsave(out_pdf, p, width = 12, height = 7, device = cairo_pdf)
  saveWidget(ggplotly(p), file = out_html, selfcontained = TRUE)
}

plot_heatmap <- function(df, out_pdf, out_html, title) {
  if (nrow(df) == 0) return()
  names(df)[1] <- "pathway"
  # 仅对数值列（样本列）构建矩阵；兼容 COG.xlsx 中的 description 等字符列
  num_cols <- names(df)[sapply(df, is.numeric)]
  if (length(num_cols) == 0) {
    warning(paste("No numeric columns found in", title, "- skipping heatmap"))
    return()
  }
  mat <- as.matrix(df[, num_cols])
  rownames(mat) <- df[[1]]
  mat <- mat[rowSums(mat) > 0, , drop = FALSE]
  if (nrow(mat) > 30) {
    # 按行均值取 top 30
    row_means <- rowMeans(mat)
    mat <- mat[order(row_means, decreasing = TRUE)[1:min(30, nrow(mat))], ]
  }
  # 按行标准化
  mat_z <- t(scale(t(mat)))
  mat_z[is.nan(mat_z)] <- 0
  mat_z[is.infinite(mat_z)] <- 0

  p <- pheatmap(mat_z, main = title, cluster_rows = TRUE, cluster_cols = TRUE,
                show_rownames = TRUE, fontsize_row = 10, fontsize_col = 12,
                color = colorRampPalette(c("#2c7bb6", "#ffffbf", "#d7191c"))(100),
                silent = TRUE)
  ggsave(out_pdf, p$gtable, width = 10, height = 8)
  saveWidget(ggplotly(ggplot() + annotation_custom(p$gtable)), file = out_html, selfcontained = TRUE)
}

# 读取数据（第一列为 feature 名称：COG / Category / Function group）
# 先用 rowNames = TRUE 正确读取数值列，再把行名转换为 pathway 列，避免 legend 变成数字
read_cog_xlsx <- function(file, sheet = "samples.relative") {
  df <- read.xlsx(file, sheet = sheet, rowNames = TRUE)
  df <- as.data.frame(df)
  df$pathway <- rownames(df)
  # 把 pathway 列放到最前面
  df <- df[, c("pathway", setdiff(names(df), "pathway"))]
  return(df)
}

cat_df <- read_cog_xlsx(file.path(cog_dir, "COG.Category.xlsx"))
fun_df <- read_cog_xlsx(file.path(cog_dir, "COG.Function.xlsx"))
cog_df <- read_cog_xlsx(file.path(cog_dir, "COG.xlsx"))

# Category 堆叠图
plot_stacked_bar(cat_df,
                 file.path(res_dir, "COG_category_barplot.pdf"),
                 file.path(res_dir, "COG_category_barplot.html"),
                 "COG Category Relative Abundance")

# Function group 堆叠图
plot_stacked_bar(fun_df,
                 file.path(res_dir, "COG_function_barplot.pdf"),
                 file.path(res_dir, "COG_function_barplot.html"),
                 "COG Function Group Relative Abundance")

# Top COG 堆叠图
plot_stacked_bar(cog_df,
                 file.path(res_dir, "COG_top_barplot.pdf"),
                 file.path(res_dir, "COG_top_barplot.html"),
                 "Top COG Relative Abundance")

# Heatmap
plot_heatmap(cat_df,
             file.path(res_dir, "COG_category_heatmap.pdf"),
             file.path(res_dir, "COG_category_heatmap.html"),
             "COG Category Heatmap (Z-score)")

plot_heatmap(fun_df,
             file.path(res_dir, "COG_function_heatmap.pdf"),
             file.path(res_dir, "COG_function_heatmap.html"),
             "COG Function Group Heatmap (Z-score)")

plot_heatmap(cog_df,
             file.path(res_dir, "COG_heatmap.pdf"),
             file.path(res_dir, "COG_heatmap.html"),
             "Top COG Heatmap (Z-score)")

cat("COG 可视化完成，输出目录:", res_dir, "\n")
source('/root/microbiome/microbiome/metage_v2.88.2/plot_theme_update.R')
