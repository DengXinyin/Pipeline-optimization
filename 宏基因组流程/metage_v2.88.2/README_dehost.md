# metage v2.88.2 去宿主 WDL

`metage_v2.88.2_dehost.wdl` 是从 `metage_v2.88.2.wdl` 派生的独立去宿主版本；原 WDL 未修改。

## 使用方式

- 人源样本：`host = "human"`
- 小鼠样本：`host = "mouse"`
- 自定义宿主：`host = "<name>"`
- 本版本禁止 `host = "none"`

默认值为 `human`。完整运行示例见 `examples/inputs.dehost.full.example.json`。

## 宿主索引目录

人源索引前缀：

```text
<mapdir>/database/kneaddata_database/human_genome/hg37dec_v0.1
```

小鼠索引前缀：

```text
<mapdir>/database/kneaddata_database/mouse_C57BL_6NJ/mouse_C57BL_6NJ
```

自定义宿主索引前缀：

```text
<mapdir>/database/kneaddata_database/<name>/<name>
```

索引必须包含完整的 Bowtie2 `.bt2` 或 `.bt2l` 六个索引文件。工作流会在处理 FASTQ 前检查索引。

## 最终 reads

每个样本在去宿主后保留以下兼容名称，内容均来自二次 fastp 产生的 `*_rm_*` reads：

```text
cleandata/<sample>_rm_1.fastq.gz
cleandata/<sample>_rm_2.fastq.gz
cleandata/<sample>_clean_1.fastq.gz
cleandata/<sample>_clean_2.fastq.gz
de_host/<sample>_dehost_1.fastq.gz
de_host/<sample>_dehost_2.fastq.gz
```

其中 MEGAHIT 和基因丰度 Bowtie2 使用 `de_host/*_dehost_*`，Kraken2 优先使用 `cleandata/*_rm_*`，参考组装/比对使用 `cleandata/*_clean_*`。
