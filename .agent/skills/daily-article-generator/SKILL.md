---
name: daily-article-generator
description: Generate a daily article digest/newsletter by checking article-harvest data, ingesting if needed, deduplicating against the past 7 days, categorizing into four sections (HN/others, GitHub repos, academic papers, deep reads), and writing section drafts plus a summary. Use when asked to produce the daily build/newsletter content from article-harvest in this repo.
---

# Daily Article Generator

## Overview
生成每日文章所需的完整流程：检查/爬取、去重、分类、落盘（仓库根目录 `assets/`）、撰写四段小文与汇总稿（中文）。

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
- 建立”标题清单”，后续用于分类与写作。

#### Digest 源内容提取（ainews-smol / alphasignal-last-email）

这两个源的每日条目是**汇总型日报**，标题不代表内容（ainews-smol 的标题永远是 “not much happened today”，这是一个 catchphrase）。实际内容存储在 `content.md` 中，包含大量结构化的子条目（新闻、论文、项目等）。

处理流程：
1. 从 archive query 结果中找到 `has_content: true` 的 ainews-smol 和 alphasignal-last-email 条目。
2. 读取其 `content_path` 对应的文件（路径为 `modules/article-harvest/data/{content_path}`）。
3. 解析内容，提取有价值的子条目：
   - **ainews-smol**：内容约 20-30K 字符，按 “AI Twitter Recap” / “AI Reddit Recap” 等分区，每条有标题、URL、活跃度和讨论摘要。重点关注高活跃度（>500）的条目和被多个子区重复提及的话题。
   - **alphasignal-last-email**：内容约 10K 字符，按 “Top News” / “Top Paper” / “Signals” 分区，每条有标题链接和简要描述。”Top Paper” 中的论文应归入 Section C。
4. 将提取的子条目加入标题清单，标注来源为 `ainews-smol:extracted` 或 `alphasignal:extracted`，参与后续分类。
5. **不要在正文中直接引用 ainews-smol 或 alphasignal 作为信息来源**——它们是二手聚合源，提取出的子条目应追溯到原始出处。

### 4) 近 7 天去重（选题前置）
- 在仓库根目录的 `assets/` 下查找过去 7 天的文件夹（YYYY-MM-DD）。
- 读取这些日期的 `summary.md` 与四个分类文件，建立已报道标题/URL 列表。
- 如发现重复：优先保留今日条目中更新更显著或权重更高的版本，其他条目从今日清单移除，并在写作时避免重复叙述。

### 5) 分类（按权重排序）
将去重后的条目按以下四类归档，并在每类内部按”权重”排序（若无权重则按重要性/影响力/来源知名度排序）：
- (a) Hacker News 和其他网站的最新分享
- (b) GitHub 上的 Repo
- (c) 学术论文与研究
- (d) 深度文章（长文分析、长篇技术解读、趋势洞察；可选最近 14 天的深度文章，不限当天）

分类规则：
- **学术论文（Section C）**——按 URL 和来源综合判断，不限于 HuggingFace：
  - 来源为 `hf-papers`，或 URL 指向 `huggingface.co/papers`
  - URL 指向 `arxiv.org`（abs / pdf / html）
  - URL 指向 `openreview.net`
  - 从 ainews-smol / alphasignal 内容中提取的、明确标注为论文的子条目
  - 来自 HN / Lobsters 等源但 URL 指向上述论文平台的条目
- **GitHub Repo（Section B）**：URL 指向 github.com 的仓库页面（排除论文类 GitHub 页面如 awesome-xxx-papers）。
- **深度文章（Section D）**：具备长文/深度解析特征（标题、来源、摘要判断）。
- **HN/其他网站（Section A）**：不属于以上三类的所有条目。
- 若条目匹配多个分类，选择最贴合的一类，保证分类互斥。

### 6) 写入分类文件
- 在仓库根目录 `assets/YYYY-MM-DD/` 创建当日文件夹。
- 创建四个文件并写入标题清单（标题在前，可附 URL）：
  - `a-hn-and-others.md`
  - `b-github-repos.md`
  - `c-papers.md`
  - `d-deep-reads.md`

### 7) 日报编辑（四段小文）

当消息源数量较多（>80 条）时，**推荐使用 agent team 并行撰写**以避免上下文溢出和质量下降：

#### Agent Team 模式（推荐用于大规模数据）
1. 使用 `TeamCreate` 创建 team。
2. 使用 `TaskCreate` 为四个 Section 各建一个任务，任务描述中包含：
   - 该 Section 的文章列表（标题、URL、分数、来源）
   - 去重规则（过去 7 天已报道的条目及处理方式）
   - 跨 Section 互斥规则（哪些条目归属其他 Section，不要重复）
   - 写作规则（字数、深度要求、WebFetch 建议）
3. 用 `Task` 工具为每个 Section 启动一个 `general-purpose` agent（`run_in_background=true`），指定 `team_name`。
4. **关键：要求 agent 将写好的 Section 内容直接写入仓库根目录 `assets/YYYY-MM-DD/section-a-draft.md` 等文件**，而非通过 SendMessage 传递——文件写入比消息传递更可靠，team lead 可直接 Read 文件获取结果。
5. 等待所有任务完成后，team lead 读取四个 draft 文件，审校、调整跨 Section 一致性，组装为最终 `summary.md`。
6. **组装后审查（防 Section 内重复）**：如果需要扩充内容以达到目标行数，**必须先搜索当前 Section 已有文本**，确认新增内容与同 Section 内已有条目不重复。付费墙源（如 The Information）条目多且标题相似，尤其容易在"要闻提炼列表"和"主题展开段落"之间产生重复。具体做法：扩充前对该 Section 内的关键实体（公司名、人名、产品名）做一次文本搜索，命中则合并而非新增。
7. 用 `SendMessage(type=shutdown_request)` 关闭所有 agent，用 `TeamDelete` 清理。

#### 单 agent 模式（适用于数据量较小的日期）
- 为每个分类撰写约 400 字中文小文章：
  - 直接进入具体内容，不写概述/引导段落（读者会读完全文，不需要 hook）。
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
- **Summary 段落是索引而非重述**：用一两句话点出每类的核心亮点，不展开论述。
- **各 Section 不写概述/引导段落**：直接进入第一条具体内容，不要写"今日 HN 呈现……"之类的总结性开头。读者是唯一读者，会读完全文，不需要 hook 或 preview。
- **跨 Section 引用用一句话带过**：如果 Section A 的内容与 Section B 的某条新闻相关，最多用"（参见深度文章 Section）"或一句话交代关联，不重复叙述背景和细节。
- 省出的字数用于：更深的分析、更多条目的简报覆盖、或补充未被充分报道的内容。
- **Section 内不重复同一条目**：同一条新闻不得在同一 Section 中出现两次（如先在速览列表中提及，又在展开段落中重复）。常见陷阱：The Information 等付费源条目多，容易在"要闻提炼"列表和"主题分析"段落之间重复同一公司/事件。扩充行数时必须先搜索 Section 内已有实体名再决定是补充新条目还是合并到已有段落。

#### 写作深度原则（不做标题搬运工）
- **每条被提及的内容必须提供超越标题的信息增量**。如果只能写出"XXX 发布了 YYY"这种一句话复述，说明信息不足——要么用 WebFetch 抓取原文后展开分析，要么不提。
- **对于 Lobsters / HN 等来源的技术文章**：挑选 2–3 篇有实质内容的展开写（技术细节、社区争论、行业影响），其余仅列标题或直接省略。不要试图覆盖所有条目——宁可少而深，不要多而浅。
- **"展开"的标准**：读者看完这段后，不需要打开原文就能理解核心观点和关键细节。
- **速览段落中被简要提及的条目也需要信息增量**。即使只用一句话介绍，也必须让读者理解"这篇文章在说什么"，而非只知道"有这么篇文章"。如果 WebFetch 后仍无法用一句话概括出有意义的内容，直接省略该条目。
  - 反面例子：「**A Single Reason To Not Vibe Code**（30 分）从某角度反思开发者与 AI 的关系。」——读者看完不知道"某角度"是什么。
  - 正面例子：「**A Single Reason To Not Vibe Code**（30 分）从神经科学角度论证：编程所需的时序逻辑能力像肌肉一样用进废退，长期外包给 LLM 会导致认知萎缩。」——一句话传递了核心论点。

#### 低信号源处理原则（Releasebot / Product Hunt / GlobeNewswire Earnings）
- **Releasebot、Product Hunt 和 GlobeNewswire Earnings 默认不出现在正文中**。这些来源的条目绝大多数是常规版本更新、早期产品发布或例行财报披露，以纯名称列表形式出现时零信息增量。
- **例外**：如果某条内容具有行业影响力（如重大框架发布、知名产品重大版本、重大科技公司业绩超预期/暴雷），可以提升到正文中，但必须附带实质描述，不能只列名称。
- 仅在分类文件（`a-hn-and-others.md`）中保留完整列表作为归档记录。

#### Twitter/X 内容处理原则
- **权重排序**：Twitter/X 条目使用 likes + retweets 作为权重信号（而非 HN 分数），按 engagement 从高到低排序。
- **展开时必须补充上下文**：推文本身通常信息量有限（短文本、碎片化），展开写作时需要通过 WebFetch 原推或相关链接获取完整背景，避免只复述推文文字。
- **归类**：Twitter/X 条目默认归入 Section (a) HN/其他网站，但如果推文内容实质上是某个 GitHub 项目或学术论文的讨论，应归入对应 Section。

#### 付费墙源处理原则（SemiAnalysis / The Information 等）
- **优先使用 RSS 摘要**：这类源的正文通常有付费墙保护，WebFetch 大概率无法获取完整内容。优先基于 RSS 提供的标题和摘要撰写。
- **WebFetch 失败时不反复重试**：尝试一次即可，失败后基于已有元信息（标题、摘要、发布日期）撰写，明确标注为付费内容。
- **归类倾向**：SemiAnalysis 的半导体深度分析和 The Information 的科技商业报道通常适合归入 Section (d) 深度文章。

#### GitHub 存量项目写作原则（避免 star 数字流水账）
- **存量项目（已在前几天报道过的 repo）不要逐一列出 star 数据**。十几个 "项目名 **N 星**（+M）" 的罗列没有叙事价值。
- **只挑出 2–3 个有故事的存量变化展开**：如增速异常（三天翻七倍）、破千星里程碑、品类异常（纯审美项目持续高增长）等。
- **其余存量项目的 star 数据下沉到文末「去重说明」**，作为数据参考而非正文内容。
- **退出 Trending 的项目**：简要列出退出项目名称和原因即可，不需要每个都附 star 数。

### 9) 收尾
- 返回生成的文件路径清单，并说明是否发生去重与被移除的标题。

## Assets
- 仓库根目录 `assets/` 用于保存每日输出文件夹（YYYY-MM-DD），已加入 `.gitignore`。

## 注意事项：路径处理

**重要**：执行 `article-harvest` CLI 时会进入 `modules/article-harvest/` 子目录，此时工作目录不再是仓库根目录。在查找历史数据和写入 assets 时，**必须使用绝对路径或先回到仓库根目录**。

assets 路径为仓库根目录下的 `assets/`，即：
```
/path/to/daily-build-newsletter/assets/YYYY-MM-DD/
```
