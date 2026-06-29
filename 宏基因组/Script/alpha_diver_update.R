library(vegan)
library(dplyr)
library(tibble)
library(ggsignif)
library(purrr)
library(plotly)
library(htmlwidgets)
library(ggplot2)

# 允许通过环境变量覆盖 R 库路径
rlib <- Sys.getenv('METAGE_RLIB', '/root/anaconda3/envs/r/lib/R/library')
if (nzchar(rlib) && dir.exists(rlib)) {
    .libPaths(rlib)
}

args <- commandArgs(trailingOnly = TRUE)
stopifnot('请提供 3 个参数：data_dir taxdir res_dir' = length(args) >= 3)
data_dir <- args[1]
taxdir <- args[2]
res_dir <- args[3]
font_family <- Sys.getenv('METAGE_FONT', '宋体')

# 读入样本元数据
sample <- read.table(
    file.path(data_dir, 'sample-metadata.tsv'),
    sep = '\t', header = TRUE, check.names = FALSE, fill = TRUE
)
n_groups <- ncol(sample) - 1

for (g in seq_len(n_groups)) {
    gro_num <- paste0('group', g)
    genecountfile <- file.path(taxdir, gro_num, '4-GeneAbundance', 'gene_count.csv')
    taxfile <- file.path(taxdir, gro_num, '5-TaxAnnotation', '1.Tables', 'gene.taxonomy.csv')

    if (!file.exists(genecountfile)) {
        stop(paste('文件不存在:', genecountfile))
    }
    if (!file.exists(taxfile)) {
        stop(paste('文件不存在:', taxfile))
    }

    otu <- read.csv(genecountfile, header = TRUE, row.names = 1, check.names = FALSE)
    otu$genes <- rownames(otu)
    tax <- read.csv(taxfile, header = TRUE, row.names = 1, check.names = FALSE)
    tax$genes <- rownames(tax)

    tax_otu_raw <- merge(tax, otu, by = 'genes')
    tax_otu_raw <- tax_otu_raw[, 8:ncol(tax_otu_raw)]

    tax_otu_raw <- tax_otu_raw %>%
        group_by(species) %>%
        summarise_all(sum) %>%
        as.data.frame() %>%
        column_to_rownames('species')
    tax_otu_raw <- t(tax_otu_raw)

    samples <- sample %>%
        mutate(across(everything(), as.character))
    samples <- samples[samples[, gro_num] != '', c('sample.id', gro_num)]

    for (j in c('All', 'Archaea', 'bacteria', 'Fungi', 'Virus')) {
        print(j)
        specicestaxfile <- file.path(
            taxdir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', j, paste0(j, '.taxonomy.csv')
        )
        if (!file.exists(specicestaxfile)) {
            warning(paste('文件不存在，跳过:', specicestaxfile))
            next
        }
        sp <- read.csv(specicestaxfile, header = TRUE, check.names = FALSE)
        tax_otu <- tax_otu_raw[samples$`sample.id`, colnames(tax_otu_raw) %in% sp$species]
        print(ncol(tax_otu))

        Chao1 <- estimateR(tax_otu)[2, ]
        ACE <- estimateR(tax_otu)[4, ]

        resdir <- file.path(res_dir, gro_num, '5-TaxAnnotation', '7.alpha_diversity_analysis', j)
        if (!file.exists(resdir)) {
            dir.create(resdir, recursive = TRUE)
        }

        Shannon <- diversity(tax_otu, index = 'shannon', base = exp(1))
        Gini_simpson <- diversity(tax_otu, index = 'simpson')

        diver_index <- data.frame(Chao1, ACE, Shannon, Gini_simpson)

        xlsx::write.xlsx(diver_index, file.path(resdir, 'diversity_index.xlsx'))

        diver_index$sample <- rownames(diver_index)
        diver_index$group <- samples[, gro_num]
        diver_index[is.na(diver_index)] <- 0

        calculate_p_value <- function(data1, data2) {
            if (var(data1, na.rm = TRUE) * var(data2, na.rm = TRUE) > 0) {
                if (shapiro.test(data1)$p.value > 0.05 && shapiro.test(data2)$p.value > 0.05) {
                    testtry <- try(t.test(data1, data2), silent = TRUE)
                    if (class(testtry) == 'try-error') {
                        p_value <- NA
                    } else {
                        p_value <- testtry$p.value
                        p_value <- round(p_value, 6)
                    }
                } else {
                    testtry <- try(wilcox.test(data1, data2), silent = TRUE)
                    if (class(testtry) == 'try-error') {
                        p_value <- NA
                    } else {
                        p_value <- testtry$p.value
                        p_value <- round(p_value, 6)
                    }
                }
            } else {
                testtry <- try(wilcox.test(data1, data2), silent = TRUE)
                if (class(testtry) == 'try-error') {
                    p_value <- NA
                } else {
                    p_value <- testtry$p.value
                    p_value <- round(p_value, 6)
                }
            }
            return(p_value)
        }

        for (i in 1:4) {
            index <- colnames(diver_index)[i]
            ANOVA <- aov(diver_index[, i] ~ group, data = diver_index)
            p <- summary(ANOVA)[[1]][['Pr(>F)']][1]
            p <- round(p, 4)
            groups <- unique(diver_index$group)
            group_pairs <- combn(groups, 2, simplify = FALSE)
            p_value_results <- map_df(group_pairs, ~ {
                data1 <- diver_index %>% filter(group == .x[1]) %>% pull(i)
                data2 <- diver_index %>% filter(group == .x[2]) %>% pull(i)
                tibble(
                    group1 = .x[1],
                    group2 = .x[2],
                    p_value = calculate_p_value(data1, data2)
                )
            })
            print(p_value_results)

            # 输出成对比较 p 值表
            if (nrow(p_value_results) > 0) {
                write.table(
                    p_value_results,
                    file = file.path(resdir, paste0(index, '_pairwise_pvalue.tsv')),
                    sep = '\t', row.names = FALSE, quote = FALSE
                )
            }

            if (nrow(p_value_results) > 0) {
                comparisons <- map2(p_value_results$group1, p_value_results$group2, ~ c(.x, .y))
                annotations <- ifelse(
                    p_value_results$p_value < 0.001, '***',
                    ifelse(
                        p_value_results$p_value < 0.01, '**',
                        ifelse(p_value_results$p_value < 0.05, '*', sprintf('p=%.3f', p_value_results$p_value))
                    )
                )
                y_positions <- max(diver_index[, i]) * (1 + 0.1 * seq_along(comparisons))
            } else {
                comparisons <- list()
                annotations <- character()
                y_positions <- numeric()
            }

            diver_p <- ggplot(diver_index, aes(x = group, y = diver_index[, i], color = group)) +
                geom_boxplot() +
                geom_point() +
                {
                    if (length(comparisons) > 0) {
                        geom_signif(
                            comparisons = comparisons,
                            annotations = annotations,
                            y_position = y_positions,
                            tip_length = 0.01,
                            color = 'black'
                        )
                    }
                } +
                theme_bw(base_family = font_family, base_size = 12) +
                theme(
                    panel.grid.major = element_blank(), panel.grid.minor = element_blank(),
                    axis.text.x = element_text(angle = 45, hjust = 1),
                    axis.title.x = element_blank(),
                    title = element_text(size = 9)
                ) +
                ggtitle(paste('ANOVA: p=', p)) +
                labs(y = index)

            ggp1 <- ggplotly(diver_p)
            saveWidget(
                ggp1,
                file = file.path(resdir, paste0(index, '.html')),
                selfcontained = TRUE
            )

            ggsave(
                file.path(resdir, paste0(index, '.pdf')),
                diver_p, width = 6, height = 4, device = cairo_pdf
            )
        }
    }
}
