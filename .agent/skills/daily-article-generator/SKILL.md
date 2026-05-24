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
- **新鲜度原则（fetch 层已做 90 天过滤）**：`make_rss_source` 的 `max_age_days` 默认值是 90 天，fetch 层只返回近 90 天发布的条目。所以不再需要在 agent 层按源手动过滤爆仓。但首次 ingest 某新源时，仍会把近 90 天的旧文章的 `archived_at` 标为今天。**日报展开/分析时只选 `published_at` 在近 3 天内的条目**；更早的条目（30-90 天前发布但今天才入库）只在分类文件中作为归档列表，不写入 summary.md。慢节奏源（lilian-weng、gwern-changelog、huyen-chip、onboard 等）90 天内可能无新发布，返回 0 是正常状态。

#### 投融资专项源处理（yc-oss / sec-edgar-form-d / techcrunch-fundings / sifted）

这些源需要特殊处理：

1. **yc-oss**（YC 公司结构化数据）：每次抓取返回数百家公司。**不要逐一列出**。处理策略：
   - 识别当前最新批次（如 “Winter 2026”），仅关注该批次的公司。
   - 与其他源交叉验证：如果某 YC 公司同时出现在 HN/TechCrunch/Sifted，则在对应 Section 中提及其 YC 背景。
   - 若 TechCrunch 有 Demo Day 报道，优先引用该报道而非 yc-oss 原始列表。
   - 在分类文件中可附上当前批次的公司计数和重点方向作为背景信息。

2. **sec-edgar-form-d**（SEC 私募融资披露）：原始监管文件，标题格式为 “Company — Form D”。处理策略：
   - 与当日其他融资新闻交叉比对——如果某公司的 Form D 出现但尚无媒体报道，这是**独家信号**，值得在正文中提及。
   - 若 TechCrunch/Crunchbase 已报道同一融资轮，则 Form D 仅作为验证数据，不需要单独提及。
   - 无法通过 WebFetch 获取更多信息时，仅以”SEC 备案显示 XXX 完成新一轮融资”形式简要提及。

3. **techcrunch-fundings / techcrunch-venture / sifted / crunchbase-news**：这些是投融资新闻的主力来源，条目默认归入 Section A，写作时与 Techmeme 的融资条目合并叙述，避免同一融资轮在不同源的报道之间重复。

#### Digest 源内容提取（ainews-smol / alphasignal-last-email / the-batch）

这些源的单期条目是**汇总型日报/周报**，标题不代表内容（ainews-smol 的标题永远是 "not much happened today"，这是一个 catchphrase）。实际内容存储在 `content.md` 中，包含大量结构化的子条目（新闻、论文、项目等）。

处理流程：
1. 从 archive query 结果中找到 `has_content: true` 的 ainews-smol、alphasignal-last-email、the-batch 条目。
2. 读取其 `content_path` 对应的文件（路径为 `modules/article-harvest/data/{content_path}`）。
3. 解析内容，提取有价值的子条目：
   - **ainews-smol**：内容约 20-30K 字符，按 "AI Twitter Recap" / "AI Reddit Recap" 等分区，每条有标题、URL、活跃度和讨论摘要。重点关注高活跃度（>500）的条目和被多个子区重复提及的话题。
   - **alphasignal-last-email**：内容约 10K 字符，按 "Top News" / "Top Paper" / "Signals" 分区，每条有标题链接和简要描述。"Top Paper" 中的论文应归入 Section C。
   - **the-batch**（DeepLearning.AI 周报）：每期由 Andrew Ng 的 editorial 开篇 + 多条 AI 新闻摘要组成。editorial 本身适合归入 Section D（深度文章）；新闻摘要中的高价值条目（模型发布、行业事件、政策动态）可提取后参与分类。周报节奏，非每日更新。
4. 将提取的子条目加入标题清单，标注来源为 `ainews-smol:extracted` / `alphasignal:extracted` / `the-batch:extracted`，参与后续分类。
5. **不要在正文中直接引用这些 digest 源作为信息来源**——它们是二手聚合源，提取出的子条目应追溯到原始出处。the-batch 的 Andrew Ng editorial 是例外，可以作为观点来源直接引用。

### 4) 近 7 天去重（选题前置）
- 在仓库根目录的 `assets/` 下查找过去 7 天的文件夹（YYYY-MM-DD）。
- 读取这些日期的 `summary.md` 与四个分类文件，建立已报道标题/URL 列表。
- 如发现重复：优先保留今日条目中更新更显著或权重更高的版本，其他条目从今日清单移除，并在写作时避免重复叙述。
- **去重标注必须机械验证**：在分类文件中将条目标注为"去重/已报道"之前，必须用 Grep 在历史 `summary.md` 中搜索该条目的关键实体（人名、公司名、项目名）确认确实出现过。禁止凭上下文中的印象判断——长上下文中同时持有今日抓取数据和历史 summary 时，极易将今日条目的标题与历史内容混淆，导致虚假去重（把新内容错误标记为已报道）。

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
- **HN/其他网站（Section A）**：不属于以上三类的所有条目。包括投融资新闻（来自 techcrunch-venture、techcrunch-fundings、sifted、crunchbase-news、sec-edgar-form-d、techmeme 中的融资条目）。
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

#### Obsidian tag 兼容（`#数字` 模式禁用）
- **禁止在正文里写 `#数字` 紧贴模式**：实测 Obsidian 会把 `Techmeme #25` / `HF Papers #1` / `Lobsters #13` / `Arena #13` / `PR #123` 中的 `#25` / `#1` 等解析为 tag（即使 [Obsidian docs](https://obsidian.md/help/tags) 声称纯数字 tag 无效，实际行为与 docs 不符，见 [forum bug](https://forum.obsidian.md/t/use-of-followed-by-number-is-turned-into-a-tag-by-obsidian/37099)）。用户在 5/03、5/05、5/08、5/15、5/20、5/21 的 Obsidian 同步副本里反复手动删除这些 `#`。
- **修复方案**：直接去掉 `#`。
  - ❌ `HF Papers #1` → ✅ `HF Papers 1`
  - ❌ `Techmeme #25` → ✅ `Techmeme 25`
  - ❌ `Lobsters #13` → ✅ `Lobsters 13`
  - ❌ `Arena #13 overall` → ✅ `Arena 13 overall`
  - ❌ `PR #123` → ✅ `PR 123`
  - ❌ `(alphasignal #5)` → ✅ `(alphasignal 5)`
- **不影响的写法**：
  - markdown heading（`# Section A` / `## HN`）— `#` 后有空格，不会被解析为 tag
  - URL 里的 fragment（`https://techmeme.com/260523/p8#a260523p8`）— 在 `[text](url)` 的 url 部分里，不会被解析为 tag
  - 真要表达 "第 N 名" 可以用：`HF Papers rank 1` / `Techmeme 第 25 条` / `Arena overall 第 13` / `HF #1` 写成 `HF top-1`
- **生成完 summary.md 后用 grep 自检**：`grep -nE '[A-Za-z一-龥][[:space:]]#[0-9]' summary.md`——理论上应该 0 命中。复制到 Obsidian 之前必跑这一步。

### 8) 生成汇总文章
- 在 `assets/YYYY-MM-DD/summary.md` 创建汇总稿，**目标长度 ~120 实质内容行**——这是**质量下限信号，不是写作目标**。如果只能通过列表化更多条目才能达到 120 行，说明 thesis 不足，应当回到合力判断；**宁可 100 行有合力，也不要 130 行流水账**。
- **"一行"的定义**：一条新闻/话题 = 一个自然段落 = 一行。高价值条目的段落可以包含 2-4 句话（提供超越标题的分析），但同一条新闻不得拆成多个段落。用 `grep -cv '^\s*$\|^#\|^---' summary.md` 计算实质行数。
- **每个 Section 需有 1-2 个贯穿性 thesis 段落**：基于本日具体事件的**合力判断**（不是抽象引导段，不是"今日 HN 呈现……"那种总结性开头），把 3-5 条相关条目整合成一个**有论点的故事**。范例（取自 2026-04-28）："OpenAI 治理重构日 = Microsoft 协议解锁 + Musk 庭审第一天 + Copilot 计费转型，三件事拼起来是自 2023 董事会风波以来最深治理重构。"——这种段落把多条独立新闻熔成一句**今天为什么是 X 日**的判断，是 summary 的真正价值所在。
- **thesis 段落优先于速览列表**：先找当日 2-4 个跨条目主题，写成 thesis 段落；再用速览处理 thesis 消化剩下的条目。**Section 不应当全部由独立条目组成**。
- **禁止的凑行手段**：
  - 把同一条新闻拆成 2-3 个段落（如"背景段 + 分析段 + 影响段"）
  - 把多条相关条目拆成独立段落代替整合为 thesis（如同日 9 条 The Information 标题各写成独立一行；同一融资轮在不同源各写一行）——这是流水账，不是扩充。3+ 条相关条目应当融合成一个 thesis 段落。
  - 用空行、分隔线、重复的引导语凑数
  - 物理换行拆分长段落
- **正确的扩充策略**（当初稿不足 120 行时，按优先级使用）：
  - **首选：增加合力（synthesis）**——找出本日 3-5 条相关条目的共同主题，组合成 thesis 段落，给出一个"今天为什么是 X 日"的判断。这是密度最高、价值最大的扩充方式。
  - **次选：增加分析深度**——对高权重条目补充 WebFetch 后的技术细节、社区反应、跨日对照。
  - **再次：增加颗粒度**——Section C 的论文各给独立一行描述（仅当聚类讲已饱和、单篇有独立信息增量时使用）。
  - **末选：增加覆盖面**——补充未被覆盖的 Techmeme / The Information / Lobsters 速览条目。**只有当前三项都饱和才用**；把同日相关条目各写成独立一行不是合力。
- 汇总稿包含：
  - 开头整体 Summary（150–200 字中文，概览今日四类亮点）。
  - 四个 Section（与上面四类一致），每个 Section 放入对应的 ~400 字小文章。

#### 写作去重原则（Section 内互斥）
- **每条新闻只在一个 Section 中深入展开**，选择最贴合的 Section 作为"主场"。
  - 例：GPT-5.2 物理学突破 → 深度文章（OpenAI 专题）；不在 HN Section 重复展开。
  - 例：moyin-creator → GitHub Section；不在 HN/Techmeme Section 重复讨论 Seedance。
- **Summary 段落是索引而非重述**：用一两句话点出每类的核心亮点，不展开论述。
- **各 Section 不写抽象引导段落**：禁止"今日 HN 呈现……" / "本日深度阅读集中在……"这类**没有具体事件内容**的 hook / preview 写法。读者会读完全文，不需要预告。**注意区分**：上文 step 8 要求的 **thesis 段落** ≠ 抽象引导段——thesis 是具体事件的合力判断（"今日 = X 事 + Y 事 + Z 事 → A 结论"），它本身就是 Section 的核心内容；而引导段是"今日有几件大事"这种空话。区别在于**有没有点名具体事件并给出论点**。
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

#### 投融资源处理原则（TechCrunch / Sifted / Crunchbase / SEC EDGAR / yc-oss）
- **融资新闻合并叙述**：同一融资轮可能同时出现在 techcrunch-venture、techcrunch-fundings、sifted、crunchbase-news、techmeme 中。以信息最丰富的版本为主，其余去重。
- **融资速览使用列表格式**：当单日融资新闻超过 3 条时，用 Markdown 列表逐条列出（公司名、金额、估值、领投方），不需要每条都写段落。仅对 1-2 条有行业意义的融资展开分析。
- **SEC EDGAR Form D 的独家价值**：如果某公司仅出现在 Form D 而无媒体报道，简要提及"SEC 备案显示..."——这是其他日报没有的信息增量。若已有媒体报道则不单独提及。
- **yc-oss 作为背景信息**：不直接写"yc-oss 显示..."，而是在提及 YC 公司时补充批次和方向信息（如"该公司来自 YC W2026 批次"）。
- **Sifted 的欧洲视角**：Sifted 覆盖欧洲创投，与美国源互补。在融资速览中注明地理区域以帮助读者区分。

#### 播客源处理原则（20VC / Dwarkesh / Latent Space / Sharp Tech / OnBoard! 等）
- **默认归类**：播客条目归入 Section (a) HN/其他网站。但若本期主题明显是某篇论文讨论，可归 Section (c)；若是某 GitHub 项目讨论，归 Section (b)。
- **展开时必须打开 show notes**：播客 RSS 的 title 通常只写主持人 + 嘉宾，看不出本期实际讨论了什么。要展开写，必须 WebFetch episode URL 或 summary 字段，抽出 3-5 个本期关键话题点。纯标题复述（如"20VC：Harry 采访 XXX"）零信息增量，宁可省略。
- **中文播客（zhang-xiaojun / onboard / sv101）**：内容通常深度较高，适合作为 Section D 的候选。注意本期可能是多嘉宾访谈，要区分嘉宾各自的观点。
- **播客 URL 可能是音频文件**（Training Data 的 Megaphone feed 每条 url 指向 `.mp3`）。这种情况下 WebFetch 音频无意义，需基于 RSS summary/description 字段写作。

#### 具身智能 / 机器人源处理原则（arxiv-cs-ro / physical-intelligence / nvidia-robotics / the-robot-report / ieee-spectrum-robotics / robohub）
- **默认归类**：
  - `arxiv-cs-ro` → Section C，与 `arxiv-cs-ai` 同套处理（每次 30 篇，仅挑 2-3 篇展开，其余作归档列表）。优先选有"VLA / 具身基础模型 / 仿真到真机迁移 / 长程操作"等强叙事的论文。
  - `physical-intelligence` → Section D。该源每几个月才发一篇，但每篇都是 SOTA 发布（π0 / π0.5 / π0.7 等），属高信号必展开，不得仅作列表项一笔带过。
  - `nvidia-robotics`、`the-robot-report`、`ieee-spectrum-robotics`、`robohub` → 默认 Section A。
- **跨源融合叙述**：NVIDIA Isaac/GR00T 发布、Figure/1X 新模型、Boston Dynamics 演示等同一事件常同时出现在多个机器人源 + Techmeme + HF Papers。按"投融资合并叙述"原则处理：以信息最丰富的版本为主，其余去重，避免在 Section A 内重复同一事件。
- **`robohub` 的播客条目**：标题形如 "Robot Talk Episode XXX"，套用上文"播客源处理原则"——必须 WebFetch show notes 抽 3-5 个本期话题点，纯标题复述零信息增量。
- **学术-产业重叠**：一篇 arxiv-cs-ro 论文若被某机器人公司（PI / Skild / Figure 等）官方博客同步发布，归 Section D 走产业视角，不在 Section C 重复列出 arxiv 链接。

#### Newsletter 源处理原则（Interconnects / Import AI / Ahead of AI / Last Week in AI / The Batch）
- **归类倾向 Section D**：这些 Substack/周刊以长文分析或观点聚合为主（Interconnects 是 Nathan Lambert 的 RL/open model 评论，Import AI 是 Jack Clark 的周度 AI 洞察，Ahead of AI 是 Sebastian Raschka 的 ML 技术解析，Last Week in AI 是周度新闻汇总，The Batch 是 DeepLearning.AI 的 Andrew Ng editorial + 新闻摘要）。
- **Last Week in AI 和 The Batch 是 digest 型**：单期含多条子新闻，按上面 "Digest 源内容提取" 的流程处理，提取子条目后参与分类。
- **周刊节奏**：这些源每周 1-3 篇，不是每日都有更新。无更新时不要硬凑篇幅。

#### 付费墙源处理原则（SemiAnalysis / The Information 等）
- **优先使用 RSS 摘要**：这类源的正文通常有付费墙保护，WebFetch 大概率无法获取完整内容。优先基于 RSS 提供的标题和摘要撰写。
- **WebFetch 失败时不反复重试**：尝试一次即可，失败后基于已有元信息（标题、摘要、发布日期）撰写，明确标注为付费内容。
- **归类倾向**：SemiAnalysis 的半导体深度分析和 The Information 的科技商业报道通常适合归入 Section (d) 深度文章。

#### GitHub 存量项目写作原则（避免 star 数字流水账）
- **存量项目（已在前几天报道过的 repo）不要逐一列出 star 数据**。十几个 "项目名 **N 星**（+M）" 的罗列没有叙事价值。
- **只挑出 2–3 个有故事的存量变化展开**：如增速异常（三天翻七倍）、破千星里程碑、品类异常（纯审美项目持续高增长）等。
- **其余存量项目的 star 数据下沉到文末「去重说明」**，作为数据参考而非正文内容。
- **退出 Trending 的项目**：简要列出退出项目名称和原因即可，不需要每个都附 star 数。

### 9) 事实性审查（Fact-check）

summary.md 初稿完成后、收尾之前，**必须**跑一轮事实性审查。主 agent 在长上下文里同时持有"今日 harvest + 过去 7 天历史 + 训练记忆"时，极易出现以下高频失误：

- **填空式幻觉**：基于 RSS 标题臆测正文内容（尤其 Techmeme / The Information / 付费墙源，其 `content.md` 可能只是跳转 stub，不是全文）。
- **训练记忆替代 harvest**：HF 论文 top-N 等列表用 Claude 对"最近热门"的印象而非实际 `has_content: true` 的 hf-papers 条目。
- **去重日期错置**："Apr X 已报道"凭印象标注，实际对应实体在别的日期或根本没出现。
- **跨条目拼接**：同一来源的两条独立说法被拼成一句断言。
- **WebFetch 失败但写成功**：没抓到原文却写出"展开"段落里的细节。

**执行方式：独立 fact-checker subagent**
- 用 `Task` 工具启动单个 `general-purpose` agent（**单 agent 足够**——多 agent 并投不能解决共享训练 prior 的盲区，成本收益不成比例；要加，就按"数字 / 归属 / 跨日去重"正交分工而不是并行投票）。
- 输入给 subagent：
  - 当天的 `summary.md` 全文
  - 当天 `article-harvest query archive --on YYYY-MM-DD --json` 的完整输出（ground truth）
  - 过去 7 天 `assets/YYYY-MM-*/summary.md` 路径清单
  - 四个分类文件路径
- 要求 subagent 独立 WebFetch 可疑 URL（**不得复用主 agent 的结论**），对每条事实断言分类：
  - `[OK]` — harvest 或独立 WebFetch 可验证
  - `[FIX]` — 有错但有正确版本，给出替换文本
  - `[DROP]` — harvest 无证据且 WebFetch 失败/404，建议删除
  - `[VERIFY-FAIL]` — 原文存在但内容无法判断，建议收紧到标题级
  - `[DEDUP-ERROR]` — 去重日期/归属错误，给出正确日期

**重点审查清单**
- 所有数字：HN 分数、GitHub stars、SWE-Bench 跑分、估值、融资金额
- Techmeme / The Information / SemiAnalysis 等付费或聚合源的正文展开段落
- Section C 的论文榜单是否全部来自 hf-papers 的 `has_content: true` 条目
- 每条"Apr X 已报道"的去重标注在对应 summary 里能否 grep 到实体
- WebFetch 未命中却出现超越标题/RSS summary 的细节
- **合力（synthesis）密度审查**：每个 Section 是否至少有 1 个 thesis 段落（把 3+ 条相关条目熔成一个论点的合力判断），还是仅由独立条目段落 / bullet 列表组成？若一个 Section 全部为独立条目而无 thesis，标记为**结构性问题**（非事实错误，但写作质量回退到"流水账"），在收尾报告中提示，下期写作前重读本规则。

**处理 subagent 报告**
- `[FIX]` / `[DEDUP-ERROR]` / `[VERIFY-FAIL]` 逐条按建议修改。
- `[DROP]` **必须交叉校验**：subagent 没有主 agent 的 WebFetch cache，它的 [DROP] 可能是 false positive（主 agent 已成功 WebFetch 过）。仅当主 agent 这侧也无证据时才删除。
- 修正后重算 `grep -cv '^\s*$\|^#\|^---' summary.md` 确认实质行数仍接近 120，必要时按 step 8 的扩充策略补行（不得用凑行手段）。
- 若单次审查抓到 `[FIX]` + `[DROP]` ≥ 5 条，说明写作阶段整体失控，应在日报末尾或 memory 中留一条警示，下期提前警惕同类来源。

### 10) 同步到 Obsidian / iCloud（手机可查看）

`summary.md` 修正完成后，复制一份到用户的 Obsidian iCloud 目录，文件名重命名为 `YYYY-MM-DD.md`，方便用户从手机 / iPad 上查看。

**目录约定**：
```
/Users/yujiachen/Library/Mobile Documents/iCloud~md~obsidian/Documents/jiachen yu/Newsletter/Daily Build/YYYY-MM-DD.md
```

- 一级目录 `Newsletter/` 是 Obsidian 总日报目录（其他 agent 也可能并列建子目录）。
- 二级目录 `Daily Build/` 是本日报系列专属。
- **只复制 `summary.md` 这一个文件**，重命名为 `YYYY-MM-DD.md`；分类文件 (`a-hn-and-others.md` 等) 不上传。
- 若 `Newsletter/Daily Build/` 不存在则用 `mkdir -p` 创建（路径包含空格，**bash 中必须加引号**）。
- 若同名文件已存在（同日重跑），直接覆盖。
- **复制前必跑 `#数字` 自检**（参见 step 7 末尾的 "Obsidian tag 兼容" 规则）：`grep -nE '[A-Za-z一-龥][[:space:]]#[0-9]' summary.md` 必须 0 命中。命中则全部改成去掉 `#` 的写法（`Techmeme #25` → `Techmeme 25`），改完再复制到 Obsidian 目录。

完成后在收尾报告中给出 Obsidian 路径，确认 iCloud 同步路径已更新。

### 11) 收尾
- 返回生成的文件路径清单（含 Obsidian 同步路径），并说明是否发生去重与被移除的标题。
- 附上 fact-check 轮次结果摘要（`[FIX]`/`[DROP]`/`[DEDUP-ERROR]` 条数）。

## Assets
- 仓库根目录 `assets/` 用于保存每日输出文件夹（YYYY-MM-DD），已加入 `.gitignore`。
- Obsidian iCloud 镜像路径：`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/jiachen yu/Newsletter/Daily Build/`（仅 `summary.md`，重命名为 `YYYY-MM-DD.md`）。

## 注意事项：路径处理

**重要**：执行 `article-harvest` CLI 时会进入 `modules/article-harvest/` 子目录，此时工作目录不再是仓库根目录。在查找历史数据和写入 assets 时，**必须使用绝对路径或先回到仓库根目录**。

assets 路径为仓库根目录下的 `assets/`，即：
```
/path/to/daily-build-newsletter/assets/YYYY-MM-DD/
```
