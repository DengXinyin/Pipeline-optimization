# v2.88.2 流程脚本

本目录是 `metage v2.88.2` 的完整镜像脚本目录。Dockerfile 会将其整体复制到：

```text
/root/microbiome/microbiome/metage_v2.88.2/
```

`node1_test_bundle_v2.88.2/workflow/` 内的两份 WDL 仅从该路径调用 Python、R、Shell 脚本和报告模板；不要只复制单个分析脚本后单独构建镜像。

## 命名约定

- `*_update.py`、`*_update.R`、`*_update.sh`：相较旧 v2.87 脚本改造过的流程实现。
- `*_V1.py`、`*_V2.py`：同一模块的保留版本；当前 WDL 调用的版本以 WDL 中的实际文件名为准。
- 无 `_update` 后缀的文件：注册表、增量规划、绘图样式、样本核对、结果整理等新增基础设施脚本，或第三方工具封装；它们同样是完整流程的一部分。
- `*.docx`、`README*.txt`、`plot_style.default.json`、`plot_theme_profile.R`：报告模板、结果说明和绘图配置，必须随脚本目录一同保留。

修改脚本后，应同步检查普通 WDL 和去宿主 WDL 中对应调用路径，并重新构建或更新运行时挂载的脚本目录。
