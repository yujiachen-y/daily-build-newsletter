# 中文信息源盘点与监听方式 Research（2026-06-25）

## 0. 起因

`微信读书 Skill`（即刻 aihot 热搜连上两天 + 知乎/36氪刷屏）、`瑞幸 Skill` 等中文 AI 工具/Skill 生态热点，
在我们的日报里完全缺席。复盘发现这不是单点遗漏，而是结构性缺口：

- **源层**：现有中文源仅 5 个，全是慢源——`zhang-xiaojun` / `onboard` / `sv101`（播客，周更/深度）
  + `sorrycc` / `zero-one-me`（个人博客，不定期）。它们会在趋势峰值数周后才谈到，抓不到"前几天火的"。
- **编排层**：唯一的 Skill 源 `skills-sh` 按**全球安装量**排名（英文生态中心），且 `SKILL.md` 里**零处理规则**，
  靠中文社区截图/KOL 引爆的 Skill 既排不进 top-30，也没有写作指令去 surface。

本文只做**盘点 + 监听可行性**，不含具体改动；改动方案另起。

## 1. 关键结论（先看这里）

1. **没有银弹**。中文 AI 信息分三层，监听方式各不相同，必须分层建。
2. **集成约束**：现有 pipeline 是 `make_rss_source` 轮询 RSS/HTTP。所以任何方案的终点都必须**产出一个可轮询的 RSS URL**——
   新增的不是抓取机制，而是「几个产 feed 的自建服务 + 若干 RSS 源条目」。这与现有架构零冲突。
3. **热榜聚合器 ≠ 垂直社区**。TrendRadar 这类工具覆盖微博/知乎/抖音/百度热榜，**不含即刻、X 中文 AI 圈、公众号**，
   而 Skill 类热点恰恰在后者引爆。热榜层只能"事后捡漏"，垂直社区层才是"提前命中"。
4. **性价比排序**：现成聚合 newsletter（订阅即用） > 公众号（自建方案成熟） > 即刻 > X 中文 KOL（脆弱）
   > 热榜 keyword 过滤（捡漏） >> 知乎/小红书（反爬重，v1 放弃）。

## 2. 中文信息源盘点（按层）

### Tier A — 垂直社区 / 快源（**最高优先，正是缺口所在**）

| 源 | 价值 | 节奏 | 备注 |
|---|---|---|---|
| **即刻** AI 相关圈子 + aihot 热榜 | 工具/Skill 类最早引爆地；"技术人的朋友圈" | 实时 | 微信读书 Skill 即在此连上两天热搜 |
| **X 中文 AI KOL**：宝玉 @dotey、歸藏 @op7418、数字生命卡兹克、向阳乔木、Gorden Sun 等 | 一手解读 + 工具首发；很多 Skill 从这里外溢 | 实时 | 宝玉常做众包调研（如 127 人 2025 关键词调研） |
| **微信公众号**（深度）：量子位、机器之心、新智元、AI 科技评论/AI 前线、Founder Park、晚点 LatePost、硅星人/品玩 | 中文 AI 的深度内容主阵地 | 日/不定期 | 无官方 RSS，见 §3 |

### Tier B — 现成聚合 / Newsletter（**最省事，可先订**）

| 源 | 形态 | 价值 | 风险 |
|---|---|---|---|
| **AI HOT**（aihot.virxact.com/daily） | 每日 8:00 自动生成过去 24h 一手 AI 动态精选 | 直接命中"一手快讯" | 二手聚合，需追溯原始出处 |
| **增长黑客 AI 周报**（范冰 XDash，zengzhang.ai） | 免费邮件 Newsletter，每周四 | 商业/落地视角 | 周更，非快源 |
| **宝玉 / baoyu-skills**（GitHub JimLiu/baoyu-skills，X @dotey） | Skill 合集 + 日常分享 | Skill 生态一手 | — |

### Tier C — 热榜（**keyword 过滤捡漏，事后命中**）

| 源 | 监听 | 价值 |
|---|---|---|
| 微博热搜 / 百度热搜 / 抖音 / B 站 / 今日头条热榜 | TrendRadar（见 §4） | 出圈后的"已经很大"的事 |
| 知乎热榜（科技） | TrendRadar / RSSHub（反爬重） | 同上 |

### Tier D — 开发者社区（补充，低优先）

36 氪快讯、掘金 trending、V2EX hot、思否——节奏快但与 AI 工具/Skill 主线相关度参差。

## 3. 监听方式可行性矩阵（工程核心）

> 中文平台**绝大多数无官方 RSS**，可行性差异极大，这是方案成败的关键。

| 平台 | 推荐方式 | 可行性 | 成本 / 可靠性 |
|---|---|---|---|
| **微信公众号** | **WeWe RSS**（自建，基于微信读书账号，出 atom/rss/json）或 **Wechat2RSS**（托管服务，~6h 时延） | ✅ 成熟 | 中等搭建；WeWe 需一个微信读书账号；Feeddd 已于 2026-01-19 归档弃用 |
| **即刻** | **RSSHub `/jike`**（用户动态 + 圈子/话题） | ⚠️ 中等 | 反爬中等，建议自建 RSSHub |
| **X 中文 AI KOL** | **RSSHub twitter 路由 + `TWITTER_COOKIE`**（登录态 web 的 auth_token+ct0） | ⚠️ 脆弱 | Nitter 已死；需一个 burner X 账号，cookie 会失效需轮换 |
| **微博/百度/抖音/B站/头条热榜** | **TrendRadar**（Docker，关键词过滤，RSS 进/出，MCP） | ✅ 好 | 自建，但本就为此设计 |
| **知乎** | RSSHub `/zhihu`（反爬重，自建也常挂）或退而用 TrendRadar 热榜 keyword 过滤 | ⚠️ 难 | 官方实例常断 |
| **小红书** | RSSHub 路由（脆弱）/ MediaCrawler（Playwright，30k★） | ❌ v1 放弃 | 反爬最重（signature/X-Bogus/xsec_token） |

**共性结论**：RSSHub 是大半个垂直层的底座，但公共实例不稳，**要可靠基本得自托管一个 RSSHub**。
公众号走 WeWe RSS / Wechat2RSS 独立解决。

## 4. 现成聚合器评估（少造轮子）

- **TrendRadar**（sansan0/TrendRadar）：11 个中文大众平台热榜聚合，关键词/正则过滤、AI 智能筛选、
  RSS 订阅、Docker、MCP、多渠道推送。
  - ✅ 适合 Tier C 热榜层：自建一个，配 `frequency_words.txt`（Claude / Skill / Agent / Cursor…）做关键词过滤，输出 RSS 给现有 pipeline 轮询。
  - ❌ **不覆盖即刻 / X / 公众号**——解决不了 Tier A 的核心缺口。定位是"热榜捡漏"，不是"垂直提前命中"。
- **AI HOT daily**：可作 Tier B 二手快讯源直接订阅；写作时须追溯原始出处（同 ainews-smol 的 digest 处理原则）。
- **Follow（RSS 阅读器）**：本质 RSSHub 套壳，证明 RSSHub 是小红书等的事实底座；我们自建 RSSHub 即可，不必引入。

## 5. 推荐的分层监听架构（待决策，非本文落地）

> ⚠️ **2026-06-25 修订**：用户反馈自建常驻服务运维成本过高。本节自建路线**已被 §5′ 低维护方案取代**，保留作为决策留痕。

```
现有 article-harvest pipeline（make_rss_source 轮询）
        ▲ 全部以 RSS URL 形式接入
        │
  ┌─────┴─────────────────────────────────────────────┐
  │ 自建 RSSHub  │ 自建 WeWe RSS │ 自建 TrendRadar │ 直订 newsletter │
  │ 即刻 + X KOL │ 精选公众号    │ 热榜 keyword 过滤 │ AI HOT / 周报   │
  │  (Tier A)    │  (Tier A)     │   (Tier C)       │   (Tier B)      │
  └──────────────┴───────────────┴──────────────────┴─────────────────┘
```

**落地优先级建议**：

1. **Tier B 直订**（半天，立即见效）：AI HOT daily + 增长黑客周报，按 digest 源处理。验证"中文快讯"补得上不。
2. **公众号（WeWe RSS）**：选 5–8 个高信号公众号（量子位/机器之心/Founder Park/晚点…），自建 WeWe RSS。
3. **即刻（自建 RSSHub `/jike`）**：盯 AI 圈子 + 几个高质量用户。
4. **X 中文 KOL（RSSHub twitter + cookie）**：宝玉/歸藏等 5–10 人；接受 cookie 维护成本。
5. **TrendRadar 热榜捡漏**：最后补，keyword 过滤，避免噪声。
6. 知乎/小红书：v1 放弃，观察 §3 反爬状况再说。

**配套编排改动（另起，非本文）**：给 `skills-sh` 写处理规则 + 选题加"中文社区热度"权重 + 新增中文快源的 digest/归类规则。

## 5′. 低维护方案修订（2026-06-25，取代 §5 自建路线）

用户约束更新：**不接受自建常驻服务的运维成本**。重查「现成 serverless 开源」+「托管 SaaS」两方向后，
结论：**可以完全绕开自建**——最重的一项也只是 ~$2/月 的托管 RSSHub（由托管商代运维）。

### 5′.1 修订后的分层方案

| 层 | 推荐（免/低运维） | 运维 | 成本 | 可靠性 |
|---|---|---|---|---|
| **大众热榜**（微博/知乎/**小红书**/抖音/B站/V2EX/GitHub…） | **DailyHotApi**：公共实例 `api-hot.imsyy.top`，或一键部署 Vercel/Railway（**支持 RSS 模式**，50+ 平台） | 零（公共）/ 近零（Vercel 免费） | 免费 | 公共实例尽力而为；自部 Vercel 更稳 |
| **公众号** | 托管 **Wechat2RSS**（~6h，2021 至今稳）/ **WeRss**(werss.app) / **WeChat RSS**(waytomaster) | 零 | 免费~少量 | 高 |
| **即刻 / X KOL / 杂项路由** | **PikaPods 托管 RSSHub**（$1.63/月，自带域名+备份，**无服务器可维护**）；或公共实例 `rsshub.app/jike/...`、`rss.lilydjwg.me/jike_topic/...`（免费但不稳） | 托管商代运维 | ~$2/月 | 自有托管实例 ≫ 公共实例 |
| **X 重度量（可选）** | **twitterapi.io**（$0.00015/读，2M≈$300）/ **GetXAPI**（$0.05/千条）+ 一个小适配器（API→feed） | 零基础设施 | 按量，极低 | 高 |

### 5′.2 关键纠正与取舍

- **Inoreader 不能当 X 中枢**（纠正上轮设想）：它已于 2023-03 停止支持 Twitter。虽能把文件夹/标签**导出 RSS**，
  但既不收 X、又需 Pro 付费；而我们 pipeline 本就自行合并多源——**不需要中枢**，每源各有 RSS URL 即可。故 Inoreader 不进方案。
- **即刻没那么死**：有公共托管路由（rsshub.app / lilydjwg），不必自建；要稳就并进 PikaPods 那只托管 RSSHub。
- **小红书/知乎只能"有限拿到"**：经 DailyHotApi 拿得到**热榜**（已出圈的），但拿不到任意账号/话题的**早期**内容；早期命中仍靠即刻 + X + 公众号。
- **PikaPods 是这次的关键解**：把"RSSHub 全部路由能力"与"不用自己运维"二者兼得，直接消掉你顾虑的运维成本。
  RSSHub 能力面最广（即刻、X-带 cookie、微博、B站…一锅端），过去唯一痛点就是自建运维，PikaPods 正好补掉。

### 5′.3 一个「全托管」组合（零自建服务器）

```
DailyHotApi 公共实例 / Vercel      （热榜：知乎/微博/小红书/V2EX…）
+ Wechat2RSS 或 WeRss 托管          （公众号）
+ PikaPods 托管 RSSHub             （即刻 + X KOL + 杂项路由）
+（可选）twitterapi.io 适配器       （X 重度量）
   └─ 全部以 RSS URL 接入现有 make_rss_source
   └─ 没有一台需要 babysit 的服务器；月成本 ≈ $2 + 可选 X API 按量
```

### 5′.4 修订后落地优先级

1. **DailyHotApi 公共实例**接 3-5 个热榜 → keyword 过滤 Claude/Skill/Agent。**零成本即时验证**。
2. **公众号**：Wechat2RSS/WeRss 订 5-8 个高信号号。
3. **PikaPods RSSHub**：即刻 AI 圈子 + X 中文 KOL（带 cookie）。$2/月。
4. **（可选）X API 适配器**：仅当 KOL 覆盖需更全/更稳时再上。
5. 编排改动（skills-sh 规则 + 中文热度权重）另起。

## 5″. 候选工具综合对比（2026-06-25，回应"再综合对比一下"）

**先厘清：这四个不是同类竞品，是按平台分工的，只有「即刻」一处重叠。**

| 工具 | 覆盖平台 | 监听原理 | 运维 | 成本 | 时延 | 可靠性 | 选号/范围 |
|---|---|---|---|---|---|---|---|
| **DailyHotApi** | 微博/知乎/小红书/抖音/B站/V2EX/GitHub 等 50+ **热榜**（**无即刻**） | 抓各站热榜，60min 缓存 | 公共实例零 / 自部 Vercel 近零 | 免费 | ~1h | 公共实例无 SLA；自部更稳 | 固定热榜，不可选账号 |
| **Wechat2RSS** | 公众号 | 服务端抓取 | 零（托管） | 免费版(已收录 ~300 号) / 付费私有部署(任意号) | ~6h | 高（2021 至今） | **免费仅限其收录的 ~300 号**；要任意号须付费 |
| **WeRss(werss.app)** | 公众号 | 基于微信读书 | 零（托管） | 免费 8 号 | **48h** | ⚠️ **低**（付费线 2025 一度跑路、推送/续订不稳） | 免费仅 8 号 |
| **PikaPods RSSHub** | 即刻 / X / 微博 / B站 / 知乎… RSSHub 全路由 | 托管商运行的 RSSHub | **托管商代运维** | ~$1.63/月 | 近实时~轮询 | 自有实例 ≫ 公共 | 任意路由，最灵活 |
| **即刻官方** | 即刻 | — | — | — | — | — | **不存在官方 API/RSS** |

### 5″.1 「即刻自己的方案」= 实际上没有

- 即刻早期（2015–17）是 RSS 聚合 app，转社交后**砍掉了主题订阅**；2026 **无官方 API / RSS / 数据导出**。
- 它有 web 版（圈子/用户公开页有 URL），所以一切"即刻方案"本质都是**第三方对 web 页抓取**：
  RSSHub `/jike/topic/<id>`、`/jike/user/<id>`、`/jike/topic/text/<id>`，或 lilydjwg 托管路由。
- 圈子是公开页，**通常无需 cookie**（官方文档未明确要求），但依赖"即刻 web 版存续 + 反爬不收紧"——这是即刻这层的**固有脆弱点**，无论谁抓都一样。

### 5″.2 对上轮的三处纠正

1. **WeRss(werss.app) 别当主力**：免费仅 8 号 + **48h 延迟**，付费线 2025 一度跑路、稳定性差。仅作应急。
2. **Wechat2RSS 免费有隐藏边界**：免费只覆盖它**已收录的 ~300 个号**；你要的号不在列表里，就得走**付费私有部署**。
   → 公众号这层"零运维 + 任意选号"**没有免费午餐**：要么号在 Wechat2RSS 列表里（免费），要么花钱（Wechat2RSS 付费托管），要么自建 WeWe RSS（省钱但要运维）。
3. **DailyHot 公共实例无 SLA**：60min 缓存、无限流承诺，且**不含即刻**；要稳就自部 Vercel（免费、近零运维）。

### 5″.3 综合选型（各取所长）

- **热榜层 → DailyHotApi 自部 Vercel**（别赖公共实例；免费近零运维）。
- **公众号层 → 先查目标号在不在 Wechat2RSS 的 ~300 列表**：在 → 免费直用；不在 → Wechat2RSS 付费私有部署（仍是托管，非你自建）；预算敏感再考虑自建 WeWe RSS。
- **即刻 + X 层 → PikaPods RSSHub**（$2/月代运维，覆盖面最广）；即刻先用公共实例零成本验证，确认值得再并入 PikaPods。
- **即刻无官方方案**，接受其反爬脆弱性；或利用"即刻热点通常 1 天内外溢到 X/公众号"间接兜底。

**一句话**：PikaPods RSSHub 是覆盖面/性价比核心（即刻+X+微博一把梭，$2/月代运维）；DailyHot 补热榜（自部 Vercel）；
公众号是唯一可能要花钱买"任意选号 + 零运维"的层；即刻官方方案不存在，不必纠结。

## 6. 待用户决策

- 自建服务的承载：本地常驻 / 一台小 VPS / GitHub Actions 定时？（RSSHub + WeWe RSS + TrendRadar 都支持容器化）
- X 监听是否值得投入（需 burner 账号 + cookie 轮换）？还是先靠公众号/即刻覆盖。
- 公众号选哪几个（深度但日更量大，需控量避免爆仓）。
- 是否接受引入二手聚合源（AI HOT），还是坚持只用一手源。

## 来源

- 微信读书 Skill 热度：<https://36kr.com/p/3823955653300360>、<https://www.zhihu.com/question/2040070496926922044>
- 公众号 RSS 方案：WeWe RSS <https://github.com/cooderl/wewe-rss>、Wechat2RSS <https://wechat2rss.xlab.app/>
- RSSHub 反爬现状：<https://github.com/DIYgod/RSSHub/issues/6784>（知乎）、<https://github.com/DIYgod/RSSHub/issues/21204>（微博）
- X/Twitter 监听：RSSHub TWITTER_COOKIE <https://github.com/DIYgod/RSSHub/discussions/14956>；Nitter 现状 <https://simple-web.org/guides/nitter-alternatives-2026-view-twitter-x-timelines-anonymously>
- TrendRadar：<https://github.com/sansan0/TrendRadar>
- 小红书采集：MediaCrawler <https://github.com/NanmiCoder/MediaCrawler>
- 现成聚合：AI HOT <https://aihot.virxact.com/daily>、增长黑客 AI 周报 <https://www.zengzhang.ai/>
- 中文 AI 信息源盘点参考：<https://zhuanlan.zhihu.com/p/15880912607>

### §5′ 低维护方案补充来源
- DailyHotApi（RSS 模式，50+ 平台，公共实例 api-hot.imsyy.top）：<https://github.com/imsyy/DailyHotApi>
- NewsNow（serverless 热榜聚合，Vercel/CF 部署）：<https://github.com/ourongxing/newsnow>
- PikaPods 托管 RSSHub（$1.63/月免运维）：<https://docs.pikapods.com/apps/rsshub>
- 公众号托管：WeRss <https://werss.app/>、WeChat RSS <https://wechatrss.waytomaster.com/>
- 即刻公共 RSS 路由：<https://rss.lilydjwg.me/>
- 便宜 X 数据 API：twitterapi.io <https://twitterapi.io/>、GetXAPI <https://www.getxapi.com/>
- Inoreader 已停 Twitter（2023-03）：<https://www.inoreader.com/blog/2023/04/twitter-feeds-no-longer-supported.html>
