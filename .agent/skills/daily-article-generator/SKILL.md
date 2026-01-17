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

### 9) 收尾
- 返回生成的文件路径清单，并说明是否发生去重与被移除的标题。

## Assets
- `assets/` 用于保存每日输出文件夹（YYYY-MM-DD）。
