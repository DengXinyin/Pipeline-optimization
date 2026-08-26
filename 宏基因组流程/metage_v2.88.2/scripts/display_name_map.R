# 公共工具：读取 display_name_map.tsv，返回 internal_id -> display_name 命名向量
# 所有绘图 R 脚本可 source 本文件，在绘图标签处使用 display_name 替换 internal_id

load_display_name_map <- function(data_dir) {
  map_file <- file.path(data_dir, "display_name_map.tsv")
  display_map <- c()
  if (!file.exists(map_file)) {
    return(display_map)
  }
  df <- tryCatch(
    read.table(map_file, sep = "\t", header = TRUE,
               check.names = FALSE, stringsAsFactors = FALSE,
               colClasses = "character", fill = TRUE),
    error = function(e) NULL
  )
  if (is.null(df) || nrow(df) == 0) {
    return(display_map)
  }
  if (!("internal_id" %in% colnames(df) && "display_name" %in% colnames(df))) {
    return(display_map)
  }
  valid <- df$internal_id != "" & df$display_name != "" & df$internal_id != df$display_name
  df <- df[valid, , drop = FALSE]
  if (nrow(df) == 0) {
    return(display_map)
  }
  display_map <- df$display_name
  names(display_map) <- df$internal_id
  return(display_map)
}
