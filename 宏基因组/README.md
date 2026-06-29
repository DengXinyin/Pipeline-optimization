# 宏基因组流程优化项目

基于 `metage_megahit.wdl` 的宏基因组分析流程优化，21 个 task 逐个比对原代码与优化版的运行效率。

## 项目结构

```
Pipeline-optimization/
└── 宏基因组/
    ├── README.md                                    # 本文件：项目说明与更新规则
    ├── SKILL.md                                     # AI 协作规范（Skill 定义）
    ├── Todo_list.txt                                # 工作流规范与当前状态（用户 + AI 共同维护）
    ├── Readme_dxy.Qmd                               # 用户维护：每个 task 的优化过程记录
    ├── Metagenomic_pipeline_optimization_kimi.Qmd    # AI 维护：优化结果展示文档
    ├── Metagenomic_pipeline_overall.qmd              # 流程总览说明书
    └── 宏基因组优化效率统计.xlsx                      # AI 维护：效率统计表
```

## 文件角色与更新规则

### 谁更新什么

| 文件 | 维护者 | 何时更新 | 说明 |
|------|--------|----------|------|
| `Todo_list.txt` | 用户 + AI | task 状态变化时 | 工作流规范，定义每个 task 的步骤和状态 |
| `Readme_dxy.Qmd` | **用户** | 每次运行完原代码或优化版后 | 记录命令、时间、问题、优化点 |
| `Metagenomic_pipeline_optimization_kimi.Qmd` | **AI** | 用户通知同步时 | 汇总展示所有 task 的优化结果 |
| `Metagenomic_pipeline_overall.qmd` | AI | task 状态/时间更新时 | 流程总览，标注每个 task 的状态 |
| `宏基因组优化效率统计.xlsx` | **AI** | 用户通知同步时 | 8 列效率统计表 |

### 每次同步要更新哪些文件

当用户说 **"同步优化结果"** / **"更新 kimi Qmd"** / **"<task> 跑完了"** 时，AI 需要更新：

1. ✅ `Metagenomic_pipeline_optimization_kimi.Qmd` — 顶部汇总表 + 对应 task 的 8 列表格
2. ✅ `宏基因组优化效率统计.xlsx` — 对应 task 行的数据
3. ✅ `Metagenomic_pipeline_overall.qmd` — 对应 task 状态/时间

**用户不需要手动改这三个文件。**

## 标准工作流（6 + 1 步）

```
Step 1: 用户运行原代码 → 生成日志
Step 2: 用户在 Readme_dxy.Qmd 记录原代码时间、问题
Step 3: 用户编写优化代码（Script/*_update.*）
Step 4: 用户运行优化版 → 生成日志
Step 5: 用户在 Readme_dxy.Qmd 记录优化版时间、优化点
Step 6: 用户通知 AI 同步 → AI 更新 kimi.Qmd、xlsx、overall.qmd
Step 7: AI 运行时间复核（核对 4 个文件的一致性）
```

## 版本控制策略

### 代码版本（V1 → V2 → V3）

优化脚本每次大改动时：

- **工作目录中**：V1 保留为 `*_update_V1.py`，当前版本为 `*_update.py`
- **Git 仓库中**：每次发布稳定版本后打 tag

```bash
# 完成一轮优化后打标签
git tag -a v1.0 -m "完成 Task 01-12 优化"
git tag -a v2.0 -m "完成 Task 13-21 优化"
git push --tags
```

### 找回历史版本

```bash
# 查看所有版本标签
git tag -l

# 查看某个历史版本的文件
git show v1.0:宏基因组/Readme_dxy.Qmd

# 恢复某个历史版本到本地
git checkout v1.0 -- 宏基因组/

# 查看文件变更历史
git log --oneline -- 宏基因组/
```

### Git 自动保留一切

每次 `git commit` 都是完整快照。即使不打 tag，也可以通过 `git log` 和 `git checkout <commit>` 找回任何历史版本。**不会丢失任何数据。**

## 核心规范速查

- **原代码不动**：`scripts/` 只读，所有优化放 `scripts_dxy/Script/`
- **优化加 `_update`**：优化脚本必须加 `_update` 后缀
- **时间看 `real`**：以 Linux `time` 命令 `real` 时间为准
- **日志命名**：`<序号>_<task>_<original|update>_runtime.log`
- **用户写 Readme，AI 写 kimi.Qmd 和 xlsx**

## 推送到 GitHub

```bash
cd /home/xydeng/Pipeline-optimization

# 添加所有变更
git add -A

# 提交（注明更新了哪些 task）
git commit -m "同步 Task 17-19 优化结果"

# 推送
git push origin main
```

## 本地目录对应关系

| GitHub 路径 | 服务器实际路径 |
|-------------|---------------|
| `宏基因组/` | `/home/xydeng/Metagenomics/scripts_dxy/`（部分文件） |
| 原代码（不在本仓库） | `/home/xydeng/Metagenomics/scripts/` |
| 优化代码（后续加入） | `/home/xydeng/Metagenomics/scripts_dxy/Script/` |
| 运行日志（后续加入） | `/home/xydeng/Metagenomics/scripts_dxy/logs/` |
