---
name: daily-article-generator
description: Generate a daily article digest/newsletter by checking article-harvest data, ingesting if needed, deduplicating against the past 7 days, categorizing into four archive files that are written up as three sections (HN/others incl. capital & equity deals; open source & research; deep reads), and writing section drafts plus a summary. Use when asked to produce the daily build/newsletter content from article-harvest in this repo.
---

# Daily Article Generator

## Overview
生成每日文章所需的完整流程：检查/爬取、去重、分类、落盘（仓库根目录 `assets/`）、撰写三段小文与汇总稿（中文）。

## Workflow

### 1) 准备
- 确认当前工作目录是仓库根目录。
- 识别“今天”的日期（YYYY-MM-DD，本地时区），后续所有路径使用该日期。
- 若 `article-harvest` CLI 不可用，先按 `modules/article-harvest/README.md` 的 Quick Start 安装依赖。

### 2) 检查今日文章与爬取
- 进入 `modules/article-harvest/` 目录。
- 使用 `article-harvest query archive --on YYYY-MM-DD --json` 检查是否有今日文章。
- 若没有文章，执行 `GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token --user yujiachen-y)}" article-harvest ingest`。
  - token 只给 `claude-code-rfcs` / `pi-rfcs` 两个源用（它们要调 GitHub GraphQL），只存在于这条命令的进程环境里，不写入任何文件，也不要 echo 出来。
  - 单个源失败不会让 ingest 整体失败。若 run 记录里这两个源报 `GITHUB_TOKEN not set`，是 gh 未登录或账号名变了——**其他源照常，不要因此停止生成日报**，在收尾报告里提一句即可。
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
   - **alphasignal-last-email**：内容约 10K 字符，按 "Top News" / "Top Paper" / "Signals" 分区，每条有标题链接和简要描述。"Top Paper" 中的论文应归入 Section B 的论文部分。
   - **the-batch**（DeepLearning.AI 周报）：每期由 Andrew Ng 的 editorial 开篇 + 多条 AI 新闻摘要组成。editorial 本身适合归入 Section C（深度文章）；新闻摘要中的高价值条目（模型发布、行业事件、政策动态）可提取后参与分类。周报节奏，非每日更新。
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

> **归档四类，成稿三个 Section**：分类文件保持四个不变（step 4 的历史去重依赖这些文件名），
> 但 summary.md 里 (b) 与 (c) 合并为「**Section B · 开源与研究**」，(d) 顺延为「**Section C · 深度文章**」。
> 合并只发生在呈现层，理由与写法见 step 8「Section B 合并写作原则」。

分类规则：
- **学术论文（归入 Section B，写入 `c-papers.md`）**——按 URL 和来源综合判断，不限于 HuggingFace：
  - 来源为 `hf-papers`，或 URL 指向 `huggingface.co/papers`
  - URL 指向 `arxiv.org`（abs / pdf / html）
  - URL 指向 `openreview.net`
  - 从 ainews-smol / alphasignal 内容中提取的、明确标注为论文的子条目
  - 来自 HN / Lobsters 等源但 URL 指向上述论文平台的条目
- **GitHub Repo（归入 Section B，写入 `b-github-repos.md`）**：URL 指向 github.com 的仓库页面（排除论文类 GitHub 页面如 awesome-xxx-papers）。
- **上游依赖跟踪（归入 Section B 的「上游动态」小节）**：`codex-releases` / `openclaw-releases` /
  `pi-releases` / `openai-node-releases` / `anthropic-api-release-notes` / `deepseek-harness-releases` /
  `kimi-code-releases` / `hyperframes-releases` / `claude-code-releases`，以及维护者 RFC 源
  `claude-code-rfcs` / `pi-rfcs`。这些源的条目**不参与常规 Section B 排序**，也不进 Section A——即使
  `anthropic-api-release-notes` 的 URL 是 docs.claude.com。
- **深度文章（Section C）**：具备长文/深度解析特征（标题、来源、摘要判断）。
- **HN/其他网站（Section A）**：不属于以上三类的所有条目。包括投融资与股权交易新闻（来自 techcrunch-venture、techcrunch-fundings、sifted、crunchbase-news、sec-edgar-form-d、kr36-motif、techmeme 中的融资条目）。
- 若条目匹配多个分类，选择最贴合的一类，保证分类互斥。

### 6) 写入分类文件
- 在仓库根目录 `assets/YYYY-MM-DD/` 创建当日文件夹。
- 创建四个文件并写入标题清单（标题在前，可附 URL）：
  - `a-hn-and-others.md` → Section A
  - `b-github-repos.md` ┐
  - `c-papers.md`       ┴ 两个文件合并写成 Section B
  - `d-deep-reads.md` → Section C

### 7) 日报编辑（三段小文）

当消息源数量较多（>80 条）时，**推荐使用 agent team 并行撰写**以避免上下文溢出和质量下降：

#### Agent Team 模式（推荐用于大规模数据）
1. 使用 `TeamCreate` 创建 team。
2. 使用 `TaskCreate` 为三个 Section 各建一个任务（Section B 的任务同时拿到 `b-github-repos.md` 与 `c-papers.md` 两份清单），任务描述中包含：
   - 该 Section 的文章列表（标题、URL、分数、来源）
   - 去重规则（过去 7 天已报道的条目及处理方式）
   - 跨 Section 互斥规则（哪些条目归属其他 Section，不要重复）
   - 写作规则（字数、深度要求、WebFetch 建议）
3. 用 `Task` 工具为每个 Section 启动一个 `general-purpose` agent（`run_in_background=true`），指定 `team_name`。
4. **关键：要求 agent 将写好的 Section 内容直接写入仓库根目录 `assets/YYYY-MM-DD/section-a-draft.md` 等文件**，而非通过 SendMessage 传递——文件写入比消息传递更可靠，team lead 可直接 Read 文件获取结果。
5. 等待所有任务完成后，team lead 读取三个 draft 文件，审校、调整跨 Section 一致性，组装为最终 `summary.md`。
6. **组装后审查（防 Section 内重复）**：如果需要扩充内容以达到目标行数，**必须先搜索当前 Section 已有文本**，确认新增内容与同 Section 内已有条目不重复。付费墙源（如 The Information）条目多且标题相似，尤其容易在"要闻提炼列表"和"主题展开段落"之间产生重复。具体做法：扩充前对该 Section 内的关键实体（公司名、人名、产品名）做一次文本搜索，命中则合并而非新增。
7. 用 `SendMessage(type=shutdown_request)` 关闭所有 agent，用 `TeamDelete` 清理。

#### 单 agent 模式（适用于数据量较小的日期）
- 为每个分类撰写约 250 字中文小文章：
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

#### 长度硬约束（三条同时生效，缺一条另两条即失效）

> 这三条是**硬上限，不是目标**。写作过程中随时可以更短。2026-07-19 至 07-27 期间日报字数从历史中位 1.7 万字漂到 6.3 万字（峰值 10.7 万），读者明确反馈"看不动"，2026-08-29 起进一步收紧到下表的一半（原为 120 行 / 20,000 字）——读者时间有限，宁可少写不要写满。

| 指标 | 硬上限 | 目标区间 | 自检命令 |
|---|---|---|---|
| 实质内容行 | **60（不得超过）** | 40–60 | `grep -cv '^\s*$\|^#\|^---' summary.md` |
| 总字数（不含空白） | **10,000（不得超过）** | 7,000–9,000 | 见下方 Python 自检脚本 |
| 单段字数 | **300（不得超过）** | 平均 130–180 | 见下方 Python 自检脚本 |

- **行数上限单独存在时是无效约束**：「一行」= 一个段落，段落可以写到 600 字，因此 60 行也能是 3 万字。必须同时守字数。130–180 字是宽松区间，不是苛刻要求。
- **三条冲突时以字数为准**：若 45 行已达 10,000 字，就该删内容而不是继续加行；若 60 行只有 6,000 字，不要为凑字数注水。
- **60 行意味着必须取舍**：单日 150–230 条素材压到 60 行，覆盖面本来就不可能完整。取舍顺序是先保 thesis 合力段落，再保当日 top 权重条目，其余整条丢弃——**不要为了"提一句"而把 20 条挤进速览列表**。
- **超限时的处理顺序**（从上到下删）：① 删掉可以下沉到分类文件的归档式列举 ② 把 3 句话的分析压成 1 句核心判断 ③ 删掉低权重速览条目整条 ④ 合并同主题段落。**不要**靠删 thesis 段落来减字——thesis 是最高密度的内容，删它等于把日报退化成流水账。
- **"一行"的定义**：一条新闻/话题 = 一个自然段落 = 一行。同一条新闻不得拆成多个段落。
- **落盘前必跑三条自检**，任一超限则必须删改后重跑：

**必须用 Python 跑，不要用 `wc -m` / `awk`**：这两个在非 UTF-8 locale 下按**字节**计数，中文会虚报约 2.1 倍，照它删会把合格稿子砍到一半长度。

```bash
cd assets/YYYY-MM-DD && python3 - <<'EOF'
lines=[l for l in open('summary.md') if l.strip() and not l.startswith(('#','---'))]
n=lambda l: len(''.join(l.split()))
L,C=len(lines),sum(n(l) for l in lines)
print(f"实质行 {L}/60   字数 {C}/10000   每行均 {C//max(L,1)}（目标 130-180）")
if L>60: print("!! 行数超限")
if C>10000: print("!! 字数超限")
print("超 300 字单段:", [(i+1,n(l)) for i,l in enumerate(lines) if n(l)>300] or "无")
EOF
```
- **每个 Section 需有 1-2 个贯穿性 thesis 段落**（60 行档下取 1 个即可）：基于本日具体事件的**合力判断**（不是抽象引导段，不是"今日 HN 呈现……"那种总结性开头），把 3-5 条相关条目整合成一个**有论点的故事**。范例（取自 2026-04-28）："OpenAI 治理重构日 = Microsoft 协议解锁 + Musk 庭审第一天 + Copilot 计费转型，三件事拼起来是自 2023 董事会风波以来最深治理重构。"——这种段落把多条独立新闻熔成一句**今天为什么是 X 日**的判断，是 summary 的真正价值所在。
- **thesis 段落优先于速览列表**：先找当日 2-4 个跨条目主题，写成 thesis 段落；再用速览处理 thesis 消化剩下的条目。**Section 不应当全部由独立条目组成**。
- **禁止的凑行手段**：
  - 把同一条新闻拆成 2-3 个段落（如"背景段 + 分析段 + 影响段"）
  - 把多条相关条目拆成独立段落代替整合为 thesis（如同日 9 条 The Information 标题各写成独立一行；同一融资轮在不同源各写一行）——这是流水账，不是扩充。3+ 条相关条目应当融合成一个 thesis 段落。
  - 用空行、分隔线、重复的引导语凑数
  - 物理换行拆分长段落
- **只有当实质行数不足 40 且字数不足 7,000 时才需要扩充**（按优先级）：
  - **首选：增加合力（synthesis）**——找出本日 3-5 条相关条目的共同主题，组合成 thesis 段落，给出一个"今天为什么是 X 日"的判断。这是密度最高、价值最大的扩充方式。
  - **次选：增加分析深度**——对高权重条目补充 WebFetch 后的技术细节、社区反应、跨日对照。
  - **再次：增加颗粒度**——Section B 的论文部分各给独立一行描述（仅当聚类讲已饱和、单篇有独立信息增量时使用）。
  - **末选：增加覆盖面**——补充未被覆盖的 Techmeme / The Information / Lobsters 速览条目。**只有当前三项都饱和才用**；把同日相关条目各写成独立一行不是合力。
  - **周末档不适用**：arXiv 不发布、多数博客无更新的日子，行数天然偏低（周末常在 20–30 行）。此时**不要扩充**，如实写短并说明数据窗口情况即可。
- 汇总稿包含：
  - 开头整体 Summary（100–150 字中文，概览今日三个 Section 的亮点）。
  - 三个 Section（A / B / C，见 step 5 的合并说明），每个 Section 约 2,000–3,000 字（三段合计需落在总字数上限内）。

#### Section B 合并写作原则（开源与研究）

2026-09 之前 B（GitHub）与 C（论文）长期各只有 1,000–1,800 字，都不到 A / D 的一半（9 期实测：B 1021–1799，C 1250–2264，A 2253–3891，D 1572–3150）。合并后与另两个 Section 齐平。合并不是把两段拼起来：

- **优先找跨类 thesis**：论文常自带 repo，同一件事本来就被拆在两个归档文件里。先按主题聚类（例："某 VLA 论文 + 其官方实现 + trending 上的第三方复现"），把 arxiv 与 github 条目熔进同一段——这是合并的主要收益，不做聚类就等于白合并。
- **找不到交叉时才分两块写**：先开源后研究，各自内部按权重排序，中间不写过渡句。
- **不设二级小标题**：Section B 内部用段落组织，不要再切「B1 开源 / B2 论文」——那等于把刚合并的 Section 又拆回去。
- **归档仍是两个文件**：`b-github-repos.md` 与 `c-papers.md` 结构不变，合并只发生在 summary.md。

#### 写作去重原则（Section 内互斥）
- **每条新闻只在一个 Section 中深入展开**，选择最贴合的 Section 作为"主场"。
  - 例：GPT-5.2 物理学突破 → 深度文章（OpenAI 专题）；不在 HN Section 重复展开。
  - 例：moyin-creator → Section B；不在 HN/Techmeme Section 重复讨论 Seedance。
- **Summary 段落是索引而非重述**：用一两句话点出每类的核心亮点，不展开论述。
- **各 Section 不写抽象引导段落**：禁止"今日 HN 呈现……" / "本日深度阅读集中在……"这类**没有具体事件内容**的 hook / preview 写法。读者会读完全文，不需要预告。**注意区分**：上文 step 8 要求的 **thesis 段落** ≠ 抽象引导段——thesis 是具体事件的合力判断（"今日 = X 事 + Y 事 + Z 事 → A 结论"），它本身就是 Section 的核心内容；而引导段是"今日有几件大事"这种空话。区别在于**有没有点名具体事件并给出论点**。
- **跨 Section 引用用一句话带过**：如果 Section A 的内容与 Section B 的某条新闻相关，最多用"（参见深度文章 Section）"或一句话交代关联，不重复叙述背景和细节。
- 省出的字数用于：更深的分析、更多条目的简报覆盖、或补充未被充分报道的内容。
- **Section 内不重复同一条目**：同一条新闻不得在同一 Section 中出现两次（如先在速览列表中提及，又在展开段落中重复）。常见陷阱：The Information 等付费源条目多，容易在"要闻提炼"列表和"主题分析"段落之间重复同一公司/事件。扩充行数时必须先搜索 Section 内已有实体名再决定是补充新条目还是合并到已有段落。

#### 写作深度原则（不做标题搬运工）
- **每条被提及的内容必须提供超越标题的信息增量**。如果只能写出"XXX 发布了 YYY"这种一句话复述，说明信息不足——要么用 WebFetch 抓取原文后展开分析，要么不提。
- **对于 Lobsters / HN 等来源的技术文章**：挑选 1–2 篇有实质内容的展开写（技术细节、社区争论、行业影响），其余仅列标题或直接省略。不要试图覆盖所有条目——宁可少而深，不要多而浅。
- **"展开"的标准**：读者看完这段后，不需要打开原文就能理解核心观点和关键细节。
- **速览段落中被简要提及的条目也需要信息增量**。即使只用一句话介绍，也必须让读者理解"这篇文章在说什么"，而非只知道"有这么篇文章"。如果 WebFetch 后仍无法用一句话概括出有意义的内容，直接省略该条目。
  - 反面例子：「**A Single Reason To Not Vibe Code**（30 分）从某角度反思开发者与 AI 的关系。」——读者看完不知道"某角度"是什么。
  - 正面例子：「**A Single Reason To Not Vibe Code**（30 分）从神经科学角度论证：编程所需的时序逻辑能力像肌肉一样用进废退，长期外包给 LLM 会导致认知萎缩。」——一句话传递了核心论点。

#### 低信号源处理原则（Releasebot / Product Hunt / GlobeNewswire Earnings）
- **Releasebot、Product Hunt 和 GlobeNewswire Earnings 默认不出现在正文中**。这些来源的条目绝大多数是常规版本更新、早期产品发布或例行财报披露，以纯名称列表形式出现时零信息增量。
- **例外**：如果某条内容具有行业影响力（如重大框架发布、知名产品重大版本、重大科技公司业绩超预期/暴雷），可以提升到正文中，但必须附带实质描述，不能只列名称。
- 仅在分类文件（`a-hn-and-others.md`）中保留完整列表作为归档记录。

#### 投融资源处理原则（TechCrunch / Sifted / Crunchbase / SEC EDGAR / yc-oss / kr36-motif）
- **融资新闻合并叙述**：同一融资轮可能同时出现在 techcrunch-venture、techcrunch-fundings、sifted、crunchbase-news、techmeme 中。以信息最丰富的版本为主，其余去重。
- **融资速览使用列表格式**：当单日融资新闻超过 3 条时，用 Markdown 列表逐条列出（公司名、金额、估值、领投方），不需要每条都写段落。仅对 1-2 条有行业意义的融资展开分析。
- **SEC EDGAR Form D 的独家价值**：如果某公司仅出现在 Form D 而无媒体报道，简要提及"SEC 备案显示..."——这是其他日报没有的信息增量。若已有媒体报道则不单独提及。
- **yc-oss 作为背景信息**：不直接写"yc-oss 显示..."，而是在提及 YC 公司时补充批次和方向信息（如"该公司来自 YC W2026 批次"）。
- **Sifted 的欧洲视角**：Sifted 覆盖欧洲创投，与美国源互补。在融资速览中注明地理区域以帮助读者区分。
- **在 Section A 内固定起小标题「资本与交易」**：投融资条目日均只有 1–4 条（2026-09-04 至 09-09 实测：4/1/1/0/2/3），撑不起独立 Section，但散落在 Section A 各处读者又找不着。做法是在 Section A 末尾起一个加粗行 `**资本与交易**`（用加粗而非 markdown heading，避免影响 step 8 的行数统计口径），把当日融资 / 老股交易 / 并购条目收在它下面。**当日 0 条时整块省略**，不写"今日无融资新闻"这种占位句。
- **不要为凑这块去找源**：2026-09-09 实测 axios pro-rata（404）、fortune term sheet（404）、pitchbook news（403）、forge global（403）、caplight（404）、strictlyvc（feed 停更在 2020）、hiive（0 条）——投融资赛道的 RSS 生态基本被 newsletter 和付费墙吃掉，registry 现有的四个源已接近能日更抓取的上限。量少是这条线的常态，如实写短即可。

#### 36kr 资情留言板（kr36-motif）处理原则
- **月更源，不是日更**：实测各期间隔 3–6 周（第 179–183 期分别发布于 2026-02-04 / 03-06 / 03-20 / 04-17 / 05-26）。绝大多数日子没有新期属正常，不要因为它没更新就去找替代内容填坑。
- **有新期必展开**，套用 `physical-intelligence` 的低频高信号处理方式。每期标题形如"求购 Deepseek 老股份额；求购长鑫存储老股份额｜资情留言板第 183 期"，正文是一级市场老股与基金 LP 份额的求购 / 转让挂牌。
- **独家价值在买方意愿**：TechCrunch / Crunchbase 报道的是**已完成**的融资轮，留言板反映的是**尚未成交的买方报价意愿**（如"求购 Anthropic 老股份额""转让持有 xAI 老股的基金 LP 份额"）——这是其他源给不了的角度。写作时点明这层区别，不要处理成普通融资新闻。
- **只挑与日报主线相关的标的**：每期约一半是国内硬科技（长鑫存储、新凯来、长征火箭、清微智能等），与 AI / 工程主线弱相关，直接略过。挑 AI / 芯片 / 机器人相关的 1–3 条即可。
- **不写具体联系方式与报价细节**：留言板含交易撮合信息，日报只做趋势观察，不转载对接方式。
- **归入 Section A 的「资本与交易」小标题下。**

#### 播客源处理原则（20VC / Dwarkesh / Latent Space / Sharp Tech / OnBoard! 等）
- **默认归类**：播客条目归入 Section A（HN/其他网站）。但若本期主题明显是某篇论文或某个 GitHub 项目的讨论，可归 Section B。
- **展开时必须打开 show notes**：播客 RSS 的 title 通常只写主持人 + 嘉宾，看不出本期实际讨论了什么。要展开写，必须 WebFetch episode URL 或 summary 字段，抽出 3-5 个本期关键话题点。纯标题复述（如"20VC：Harry 采访 XXX"）零信息增量，宁可省略。
- **中文播客（zhang-xiaojun / onboard / sv101）**：内容通常深度较高，适合作为 Section C 的候选。注意本期可能是多嘉宾访谈，要区分嘉宾各自的观点。
- **播客 URL 可能是音频文件**（Training Data 的 Megaphone feed 每条 url 指向 `.mp3`）。这种情况下 WebFetch 音频无意义，需基于 RSS summary/description 字段写作。

#### 具身智能 / 机器人源处理原则（arxiv-cs-ro / physical-intelligence / nvidia-robotics / the-robot-report / ieee-spectrum-robotics / robohub）
- **默认归类**：
  - `arxiv-cs-ro` → Section B 的论文部分，与 `arxiv-cs-ai` 同套处理（每次 30 篇，仅挑 2-3 篇展开，其余作归档列表）。优先选有"VLA / 具身基础模型 / 仿真到真机迁移 / 长程操作"等强叙事的论文。
  - `physical-intelligence` → Section C。该源每几个月才发一篇，但每篇都是 SOTA 发布（π0 / π0.5 / π0.7 等），属高信号必展开，不得仅作列表项一笔带过。
  - `nvidia-robotics`、`the-robot-report`、`ieee-spectrum-robotics`、`robohub` → 默认 Section A。
- **跨源融合叙述**：NVIDIA Isaac/GR00T 发布、Figure/1X 新模型、Boston Dynamics 演示等同一事件常同时出现在多个机器人源 + Techmeme + HF Papers。按"投融资合并叙述"原则处理：以信息最丰富的版本为主，其余去重，避免在 Section A 内重复同一事件。
- **`robohub` 的播客条目**：标题形如 "Robot Talk Episode XXX"，套用上文"播客源处理原则"——必须 WebFetch show notes 抽 3-5 个本期话题点，纯标题复述零信息增量。
- **学术-产业重叠**：一篇 arxiv-cs-ro 论文若被某机器人公司（PI / Skild / Figure 等）官方博客同步发布，归 Section C 走产业视角，不在 Section B 重复列出 arxiv 链接。

#### Newsletter 源处理原则（Interconnects / Import AI / Ahead of AI / Last Week in AI / The Batch）
- **归类倾向 Section C**：这些 Substack/周刊以长文分析或观点聚合为主（Interconnects 是 Nathan Lambert 的 RL/open model 评论，Import AI 是 Jack Clark 的周度 AI 洞察，Ahead of AI 是 Sebastian Raschka 的 ML 技术解析，Last Week in AI 是周度新闻汇总，The Batch 是 DeepLearning.AI 的 Andrew Ng editorial + 新闻摘要）。
- **Last Week in AI 和 The Batch 是 digest 型**：单期含多条子新闻，按上面 "Digest 源内容提取" 的流程处理，提取子条目后参与分类。
- **周刊节奏**：这些源每周 1-3 篇，不是每日都有更新。无更新时不要硬凑篇幅。

#### 付费墙源处理原则（SemiAnalysis / The Information 等）
- **优先使用 RSS 摘要**：这类源的正文通常有付费墙保护，WebFetch 大概率无法获取完整内容。优先基于 RSS 提供的标题和摘要撰写。
- **WebFetch 失败时不反复重试**：尝试一次即可，失败后基于已有元信息（标题、摘要、发布日期）撰写，明确标注为付费内容。
- **归类倾向**：SemiAnalysis 的半导体深度分析和 The Information 的科技商业报道通常适合归入 Section C 深度文章。

#### GitHub 存量项目写作原则（避免 star 数字流水账）
- **存量项目（已在前几天报道过的 repo）不要逐一列出 star 数据**。十几个 "项目名 **N 星**（+M）" 的罗列没有叙事价值。
- **只挑出 2–3 个有故事的存量变化展开**：如增速异常（三天翻七倍）、破千星里程碑、品类异常（纯审美项目持续高增长）等。
- **其余存量项目的 star 数据下沉到文末「去重说明」**，作为数据参考而非正文内容。
- **退出 Trending 的项目**：简要列出退出项目名称和原因即可，不需要每个都附 star 数。

#### 上游动态写作原则（Section B 末尾的固定小节）

跟踪的是**固定清单**，回答"我在用的工具变了什么"；这与 github-trending 的"今天什么火了"是两种信号，
互不挤占篇幅。做法与 Section A 的「资本与交易」对称：在 Section B 末尾起一个加粗行 `**上游动态**`
（加粗而非 heading，不影响行数口径），**当日无实质变更时整块省略**，不写"今日无更新"。

- **绝对不要列版本号流水账**。"codex 发布 0.153.4、openclaw 发布 2026.9.3、pi 发布 v0.85.1"这种
  三行等于零信息增量，和上面禁掉的 star 数字流水账是同一个毛病。**版本号只在需要定位时出现一次**，
  正文写的是"这个版本能干什么了"。
- **判据是能力变化，不是发版事件**：读 release notes 里的 `## New Features` / `Breaking` /
  `### Features` 段，只写会改变用户用法的条目（新命令、新 API 参数、行为变更、废弃）。纯 bugfix
  和依赖 bump 直接略过——当日五个源全是 bugfix 就整块省略，这是常态而非异常。
- **openclaw 的 release notes 极长**（实测单版 114KB，v2026.9.2 是 65KB）。**不要整篇读**，
  grep `New Features` / `Breaking` 小节即可，否则会吃掉大量上下文还读不出重点。
- **`codex-releases` 每次只有一条**（走 GitHub `/releases/latest` 端点，因为该仓库一天发 8 个
  alpha，会把 releases.atom 的 10 条窗口占满）。它没有"今日多个版本"的情况，同一版本会连续几天
  是最新——**靠 step 4 的 7 天去重挡住重复报道**，不要因为它还在 latest 就每天重写一遍。
- **`anthropic-api-release-notes` 是细粒度 API 变更**（新 endpoint、新 beta header、SDK 方法），
  比 `claude-blog` 更早也更细。两者撞车时以 changelog 的技术描述为准，博客只用来补背景。
- **`deepseek-harness-releases` 的版本号带 alpha 是正常的**：该项目至今没发过正式版（GitHub 的
  `/releases/latest` 对它返回 404），alpha 就是它的正式发布节奏。它的 notes 是中英双语的完整
  「新增功能」章节（3.5–12.5KB），信息量不输别家的 stable，**不要因为看到 alpha 就判定"不稳定、
  不值得报道"**。
- **`kimi-code-releases` 的 notes 同样很长**（单版实测 11KB，格式是 changesets 的
  `### Minor Changes` + PR 链接列表）。和 openclaw 一样只读小节标题下的条目，不要整篇读。
  注意仓库是 `MoonshotAI/kimi-code`，与 `MoonshotAI/kimi-cli` 是两个不同的项目，别写混。
- **`hyperframes-releases` 是唯一的非 coding-agent 源**（HeyGen 的 HTML→视频渲染引擎），
  写作时不要硬套进"AI 编程工具"的叙事里凑合力段落。
- **`openai-node-releases` 是 OpenAI 侧的替代信号**：官方 changelog 页面
  （platform.openai.com/docs/changelog）是客户端渲染的，抓不到内容，所以用 Node SDK 的
  release notes 反推新 API 能力（例："Add API key expiration controls"）。写作时注意这是
  **SDK 侧的证据**，不要写成"OpenAI 官方宣布"——除非另有 developers.openai.com/blog 佐证。

**路线图（`claude-code-rfcs` / `pi-rfcs`）与已发布（`*-releases`）必须分开写。** releases 回答"已经发了什么"，
RFC 回答"快要来什么"，两者写混是这一小节最容易出的事实错误。

- **RFC 内容一律按路线图写，不许写成已发布**。实测 claude-code#91870 里的 function hooks / Claude Mods 在全部
  390 个版本的 CHANGELOG 里出现 0 次，当时只能靠 feature flag（`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`）试用，
  并标注"几周内发布"。❌「Claude Code 推出 Claude Mods」 ✅「Claude Code 维护者预告 Claude Mods 数周内发布，
  目前可用环境变量开启测试」。原文里 still iterating、N weeks 这类限定词必须保留，不许压成断言。
- **同一个 RFC 按「修订日」产生多条**：URL 形如 `.../issues/91870#rev-2026-09-09`，每个编辑日一条
  （harvest 按 URL 去重，不这样做正文更新会被静默丢弃）。写作时**只写这次新增的内容**：先 grep 过去 7 天
  summary.md 里的 issue 编号；已报道过的，从 manifest 取同一 issue 的上一版 `content_path` 做 diff——
  `python3 -c "import json;[print(r['published_at'],r['content_path']) for r in map(json.loads,open('data/sources/claude-code-rfcs/manifest.jsonl')) if '/issues/91870#' in r['url']]"`。
  不要用 `ls items/*关键词*` 找目录：同一 issue 的多个修订 slug 前缀相同，会取错版本。
- **`published_at` 是修订日，不是开 issue 的日子**。从未编辑过的老 issue 用创建日，会自然落进 step 3
  "3 天外只归档"的规则——维护者的老 issue 只是多了评论，不算路线图更新。
- **只跟正文，不跟评论**：#91870 的作者在 156 条评论里回了 24 条，这些回复不在 harvest 里。要引用评论
  就 WebFetch issue 页面，并注明出自评论区。
- **`pi-rfcs` 是工程设计笔记，不是面向用户的路线图**（mitsuhiko / badlogic 写的 harness 重构、session
  生命周期 meta issue）。只有涉及用户可见行为或 API 变化时才进正文，否则只留在分类文件里。
- **这两个源失败 ≠ 没有 RFC**：它们依赖 `GITHUB_TOKEN`（见 step 2），失败多半是 token 问题。收尾时提一句，
  不要在正文写"今日无路线图更新"。

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
- Section B 的论文部分是否全部来自 hf-papers 的 `has_content: true` 条目
- 「上游动态」里来自 `*-rfcs` 的内容是否被写成了已发布（应为预告 / 计划 / 测试中）；版本号与功能的对应是否出自 release notes 原文
- 每条"Apr X 已报道"的去重标注在对应 summary 里能否 grep 到实体
- WebFetch 未命中却出现超越标题/RSS summary 的细节
- **合力（synthesis）密度审查**：每个 Section 是否至少有 1 个 thesis 段落（把 3+ 条相关条目熔成一个论点的合力判断），还是仅由独立条目段落 / bullet 列表组成？若一个 Section 全部为独立条目而无 thesis，标记为**结构性问题**（非事实错误，但写作质量回退到"流水账"），在收尾报告中提示，下期写作前重读本规则。

**处理 subagent 报告**
- `[FIX]` / `[DEDUP-ERROR]` / `[VERIFY-FAIL]` 逐条按建议修改。
- `[DROP]` **必须交叉校验**：subagent 没有主 agent 的 WebFetch cache，它的 [DROP] 可能是 false positive（主 agent 已成功 WebFetch 过）。仅当主 agent 这侧也无证据时才删除。
- 修正后重跑 step 8 的三条长度自检（行数 ≤60、字数 ≤10,000、无 >300 字单段）。**修正常常会加长正文**（补 hedge、补出处、补口径说明），因此这一步比初稿时更容易超限；超了就按 step 8 的删除顺序压缩，不得为保留细节而突破上限。
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
