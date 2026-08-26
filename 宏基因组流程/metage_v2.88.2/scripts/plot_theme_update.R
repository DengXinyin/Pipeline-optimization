# Shared, language-neutral plot-style adapter for R/ggplot2.

.metage_script_dir <- function() {
    args <- commandArgs(trailingOnly = FALSE)
    file_arg <- grep("^--file=", args, value = TRUE)
    if (length(file_arg) > 0) {
        return(dirname(normalizePath(sub("^--file=", "", file_arg[1]))))
    }
    getwd()
}

.metage_deep_merge <- function(base, override) {
    if (is.null(override)) return(base)
    utils::modifyList(base, override, keep.null = TRUE)
}

metage_load_plot_style <- function(task_name = Sys.getenv("METAGE_PLOT_TASK", ""),
                                   config_path = Sys.getenv("METAGE_PLOT_CONFIG", "")) {
    if (!requireNamespace("jsonlite", quietly = TRUE)) {
        stop("The jsonlite package is required to load plot style configuration.")
    }

    if (!nzchar(config_path)) {
        config_path <- file.path(.metage_script_dir(), "plot_style.default.json")
    }
    config <- jsonlite::fromJSON(config_path, simplifyVector = FALSE)

    if (nzchar(task_name) &&
        !is.null(config$tasks) &&
        !is.null(config$tasks[[task_name]])) {
        config <- .metage_deep_merge(config, config$tasks[[task_name]])
    }

    legacy_font <- trimws(Sys.getenv("METAGE_PLOT_FONT", ""))
    if (nzchar(legacy_font)) config$global$font_family <- legacy_font
    config
}

.metage_value <- function(value, fallback) {
    if (is.null(value) || length(value) == 0 || identical(value, "")) fallback else value
}

.metage_face <- function(style) {
    bold <- isTRUE(style$bold)
    italic <- isTRUE(style$italic)
    if (bold && italic) return("bold.italic")
    if (bold) return("bold")
    if (italic) return("italic")
    "plain"
}

.metage_hjust <- function(align) {
    switch(.metage_value(align, "center"),
           left = 0,
           center = 0.5,
           right = 1,
           0.5)
}

metage_text_element <- function(config, element_name) {
    style <- config$text[[element_name]]
    if (is.null(style)) style <- list()
    if (identical(style$show, FALSE)) return(ggplot2::element_blank())

    ggplot2::element_text(
        family = .metage_value(style$font_family, config$global$font_family),
        size = .metage_value(style$size, 16),
        face = .metage_face(style),
        hjust = .metage_hjust(style$align)
    )
}

metage_theme <- function(task_name = Sys.getenv("METAGE_PLOT_TASK", ""),
                         config = NULL,
                         base_size = NULL,
                         axis_text_size = NULL,
                         axis_title_size = NULL,
                         legend_text_size = NULL,
                         legend_title_size = NULL,
                         title_size = NULL,
                         style = NULL) {
    if (is.null(config)) config <- metage_load_plot_style(task_name = task_name)

    # Preserve compatibility with older explicit metage_theme(...) calls.
    if (!is.null(base_size)) config$text$axis_text$size <- base_size
    if (!is.null(axis_text_size)) config$text$axis_text$size <- axis_text_size
    if (!is.null(axis_title_size)) config$text$axis_title$size <- axis_title_size
    if (!is.null(legend_text_size)) config$text$legend_text$size <- legend_text_size
    if (!is.null(legend_title_size)) config$text$legend_title$size <- legend_title_size
    if (!is.null(title_size)) config$text$title$size <- title_size
    if (!is.null(style)) config$global$theme <- match.arg(style, c("bw", "classic"))

    family <- .metage_value(config$global$font_family, "Times New Roman")
    selected_theme <- .metage_value(config$global$theme, "bw")
    base_theme <- if (selected_theme == "classic") {
        ggplot2::theme_classic(base_family = family)
    } else {
        ggplot2::theme_bw(base_family = family)
    }

    legend <- config$legend
    legend_position <- .metage_value(legend$position, "right")
    if (identical(legend$show, FALSE) || identical(legend_position, "none")) {
        legend_position <- "none"
    }

    base_theme + ggplot2::theme(
        text = ggplot2::element_text(family = family),
        plot.title = metage_text_element(config, "title"),
        plot.subtitle = metage_text_element(config, "subtitle"),
        axis.title = metage_text_element(config, "axis_title"),
        axis.text = metage_text_element(config, "axis_text"),
        legend.title = metage_text_element(config, "legend_title"),
        legend.text = metage_text_element(config, "legend_text"),
        strip.text = metage_text_element(config, "facet_label"),
        legend.position = legend_position,
        legend.background = if (isTRUE(legend$frame)) {
            ggplot2::element_rect(colour = "black", fill = "white")
        } else {
            ggplot2::element_blank()
        },
        legend.key = ggplot2::element_blank()
    )
}

metage_group_palette <- function(groups, task_name = Sys.getenv("METAGE_PLOT_TASK", ""),
                                  config = NULL) {
    if (is.null(config)) config <- metage_load_plot_style(task_name = task_name)
    groups <- unique(as.character(groups[!is.na(groups) & groups != ""]))
    palette <- unlist(config$group_palette, use.names = FALSE)
    if (length(groups) > length(palette)) {
        stop(sprintf("group_palette has %d colors but %d groups are required",
                     length(palette), length(groups)))
    }
    stats::setNames(palette[seq_along(groups)], groups)
}

metage_ggsave <- function(filename, plot, task_name = Sys.getenv("METAGE_PLOT_TASK", ""),
                          config = NULL, ...) {
    if (is.null(config)) config <- metage_load_plot_style(task_name = task_name)
    ggplot2::ggsave(
        filename = filename,
        plot = plot,
        width = config$global$figure_width,
        height = config$global$figure_height,
        dpi = config$global$dpi,
        ...
    )
}
