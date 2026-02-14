---
name: daily-article-generator
description: Generate a daily article digest/newsletter by checking article-harvest data, ingesting if needed, deduplicating against the past 7 days, categorizing into four sections (HN/others, GitHub repos, Hugging Face papers, deep reads), and writing section drafts plus a summary. Use when asked to produce the daily build/newsletter content from article-harvest in this repo.
---

# Daily Article Generator

## Overview
生成每日文章所需的完整流程：检查/爬取、去重、分类、落盘（skill assets）、撰写四段小文与汇总稿（中文）。

## Workflow

### 1) 准备
- 确认当前工作目录是仓库根目录。
- 识别“今天”的日期（YYYY-MM-DD，本地时区），后续所有路径使用该日期。
- 若 `article-harvest` CLI 不可用，先按 `modules/article-harvest/README.md` 的 Quick Start 安装依赖。

### 2) 检查今日文章与爬取
- 进入 `modules/article-harvest/` 目录。
- 使用 `article-harvest query archive --on YYYY-MM-DD --json` 检查是否有今日文章。
- 若没有文章，执行 `article-harvest ingest`。
- 若 ingest 失败，重试一次。
- 若重试后依然失败，停止生成日报：
  - 查看 `modules/article-harvest/data/runs/` 的最新 run 记录或 CLI 报错信息，定位问题。
  - 向用户说明问题原因与可能修复方向，并询问是否需要修复。

### 3) 收集标题与元信息
- 从 `article-harvest query archive --on YYYY-MM-DD --json` 输出中提取：标题、来源（source id）、URL、可用的权重指标（HN 分数、GitHub stars、HF 引用等）。
- 建立“标题清单”，后续用于分类与写作。

### 4) 近 7 天去重（选题前置）
- 在本 skill 的 `assets/` 下查找过去 7 天的文件夹（YYYY-MM-DD）。
- 读取这些日期的 `summary.md` 与四个分类文件，建立已报道标题/URL 列表。
- 如发现重复：优先保留今日条目中更新更显著或权重更高的版本，其他条目从今日清单移除，并在写作时避免重复叙述。

### 5) 分类（按权重排序）
将去重后的条目按以下四类归档，并在每类内部按“权重”排序（若无权重则按重要性/影响力/来源知名度排序）：
- (a) Hacker News 和其他网站的最新分享
- (b) GitHub 上的 Repo
- (c) Hugging Face 上的 Paper
- (d) 深度文章（长文分析、长篇技术解读、趋势洞察；可选最近 14 天的深度文章，不限当天）

分类规则：
- HN/其他网站：来源为 hn 或非 GitHub/HF 的一般媒体/博客。
- GitHub Repo：URL 指向 github.com 的仓库页面。
- Hugging Face Paper：URL 指向 huggingface.co/papers 或论文页面。
- 深度文章：具备长文/深度解析特征（标题、来源、摘要判断）。
- 若条目匹配多个分类，选择最贴合的一类，保证分类互斥。

### 6) 写入分类文件（skill assets）
- 在 `assets/YYYY-MM-DD/` 创建当日文件夹。
- 创建四个文件并写入标题清单（标题在前，可附 URL）：
  - `a-hn-and-others.md`
  - `b-github-repos.md`
  - `c-hf-papers.md`
  - `d-deep-reads.md`

### 7) 日报编辑（四段小文）
- 为每个分类撰写约 400 字中文小文章：
  - 概述该类今日更新的主要脉络。
  - 选择其中 1 条重点展开（背景、意义、潜在影响）。
  - 避免与过去 7 天内容重复。

### 8) 生成汇总文章
- 在 `assets/YYYY-MM-DD/summary.md` 创建汇总稿，包含：
  - 开头整体 Summary（150–200 字中文，概览今日四类亮点）。
  - 四个 Section（与上面四类一致），每个 Section 放入对应的 ~400 字小文章。

#### 写作去重原则（Section 内互斥）
- **每条新闻只在一个 Section 中深入展开**，选择最贴合的 Section 作为"主场"。
  - 例：GPT-5.2 物理学突破 → 深度文章（OpenAI 专题）；不在 HN Section 重复展开。
  - 例：moyin-creator → GitHub Section；不在 HN/Techmeme Section 重复讨论 Seedance。
- **Summary 段落是索引而非重述**：用一两句话点出每类的核心亮点，引导读者跳转到对应 Section，不展开论述。
- **跨 Section 引用用一句话带过**：如果 Section A 的内容与 Section B 的某条新闻相关，最多用"（参见深度文章 Section）"或一句话交代关联，不重复叙述背景和细节。
- 省出的字数用于：更深的分析、更多条目的简报覆盖、或补充未被充分报道的内容。

#### 写作深度原则（不做标题搬运工）
- **每条被提及的内容必须提供超越标题的信息增量**。如果只能写出"XXX 发布了 YYY"这种一句话复述，说明信息不足——要么用 WebFetch 抓取原文后展开分析，要么不提。
- **对于 Lobsters / HN 等来源的技术文章**：挑选 2–3 篇有实质内容的展开写（技术细节、社区争论、行业影响），其余仅列标题或直接省略。不要试图覆盖所有条目——宁可少而深，不要多而浅。
- **"展开"的标准**：读者看完这段后，不需要打开原文就能理解核心观点和关键细节。

### 9) 收尾
- 返回生成的文件路径清单，并说明是否发生去重与被移除的标题。

## Assets
- `assets/` 用于保存每日输出文件夹（YYYY-MM-DD）。

## 注意事项：路径处理

**重要**：执行 `article-harvest` CLI 时会进入 `modules/article-harvest/` 子目录，此时工作目录不再是仓库根目录。在查找历史数据和写入 assets 时，**必须使用绝对路径**，否则相对路径会从子目录出发导致找不到文件。

正确做法：
```
# 使用绝对路径访问 skill assets
/Users/.../daily-build-newsletter/.claude/skills/daily-article-generator/assets/
```

错误做法：
```
# 相对路径在 modules/article-harvest/ 下会失效
.claude/skills/daily-article-generator/assets/
```

Skill 的 base directory 在消息开头会给出，形如：
```
Base directory for this skill: /path/to/daily-build-newsletter/.claude/skills/daily-article-generator
```

基于此路径拼接 `assets/YYYY-MM-DD/` 即可。
