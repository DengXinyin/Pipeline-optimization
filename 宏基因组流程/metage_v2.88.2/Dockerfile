# Reproducible build recipe for the published metage_v2.88.2 image.
#
# The base digest is the previously validated v2.88 image in the legacy
# metage_megahit repository. Pinning the digest
# avoids a circular dependency when this build is eventually pushed with the
# new v2.88.2 tag.
FROM dockerhub.genostack.com/sanshu/metage_megahit@sha256:18bd9eff6f0cd3b2643ddc2981e5a602a27c16ea1d481869558bc7fdaf0f83cb

USER root

ENV METAGE_SCRIPTS_PATH=/root/microbiome/microbiome/metage_v2.88.2 \
    METAGE_PLOT_FONT="Times New Roman"

# Optional Kraken2/Bracken taxonomy branch used when use_kraken2=yes.
# The executable environment is installed at image-build time; the database
# remains external on Ceph and no packaged Kraken2 binaries are kept in Git.
RUN /root/anaconda3/bin/conda create -y -n kraken2 -c conda-forge -c bioconda \
      kraken2 bracken && \
    source /root/anaconda3/etc/profile.d/conda.sh && \
    conda activate kraken2 && \
    kraken2 --version && \
    bracken -v && \
    bracken-build -v

# Keep this path unchanged: the WDL and helper scripts call files here.
COPY scripts/ /root/microbiome/microbiome/metage_v2.88.2/

RUN chmod -R a+rX /root/microbiome/microbiome/metage_v2.88.2 && \
    find /root/microbiome/microbiome/metage_v2.88.2 \
      -type f -name "*.sh" -exec chmod 0755 {} \; && \
    rm -rf /root/.cache/matplotlib && \
    fc-cache -f -v >/tmp/fc-cache.log && \
    fc-match "sans-serif" >/dev/null && \
    test -f "${METAGE_SCRIPTS_PATH}/get_report_update.py" && \
    test -f "${METAGE_SCRIPTS_PATH}/merge_upstream_results.py" && \
    test -f "${METAGE_SCRIPTS_PATH}/test_incremental_merge.py" && \
    test -f "${METAGE_SCRIPTS_PATH}/ncbi_taxonomy_tree.py" && \
    test -f "${METAGE_SCRIPTS_PATH}/tax_unifrac_update.py" && \
    test -f "${METAGE_SCRIPTS_PATH}/plot_theme_update.R" && \
    test -f "${METAGE_SCRIPTS_PATH}/metage_v2.88.2.docx" && \
    /root/anaconda3/bin/conda run -n py39 \
      python -c "import Bio, matplotlib, numpy, openpyxl, pandas, sklearn; assert openpyxl.__version__ == '3.1.2'; print('openpyxl', openpyxl.__version__, 'sklearn', sklearn.__version__)" && \
    rm -f /tmp/fc-cache.log

LABEL org.opencontainers.image.version="2.88.2" \
      org.opencontainers.image.title="metage_v2.88.2" \
      org.opencontainers.image.description="metage_v2.88.2 with Kraken2 and default four-distance species beta diversity"

CMD ["/bin/bash"]
