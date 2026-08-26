# Loaded automatically by Rscript when R_PROFILE_USER points to this file.
scripts_dir <- Sys.getenv(
    "METAGE_SCRIPTS_PATH",
    "/root/microbiome/microbiome/metage_v2.88.2"
)
theme_file <- file.path(scripts_dir, "plot_theme_update.R")

if (file.exists(theme_file)) {
    source(theme_file)
    if (requireNamespace("ggplot2", quietly = TRUE)) {
        ggplot2::theme_set(metage_theme())
    }
}
