# App Radar Module

Daily snapshots of Apple App Store charts plus signals for the newsletter's 「App 榜单信号」 block.
It watches for the pattern "a proven app template is being copied into a new niche or market":
young apps (first released within 365 days) climbing grossing charts, several sellers launching
look-alike apps at once, and rating counts growing fast.

## Data sources

| Source | Cost | What it gives |
|---|---|---|
| Legacy iTunes RSS `itunes.apple.com/{cc}/rss/{chart}/limit=100/genre={id}/json` | free | Top-grossing and top-free top 100 per country and genre. The newer `rss.marketingtools.apple.com` feed dropped top-grossing (502). |
| iTunes lookup API | free | Rating count, release date, languages and description of each young app, per storefront |
| [DataXAPI](https://dataxapi.com/apis/) (optional) | ~$0.1 / $0.006 / $0.04 per call | WeChat Index, Douyin 巨量算数 index, Xiaohongshu 蒲公英 search index for the keywords in `config/keywords.json` |

Defaults: 7 countries (us, gb, de, fr, jp, kr, cn) × 7 non-game genres (Health & Fitness,
Lifestyle, Productivity, Education, Photo & Video, Utilities, Entertainment) × 2 charts = 98 chart
requests; a full run takes about 3 minutes.

## Layout

```
modules/app-radar/
├── config/keywords.json        # keywords for the paid indices
├── config/supply.json          # watch list and per-country baseline for the supply stage
├── config/backtest.json        # waves, controls and baseline for the back-test
├── data/                       # ignored by git
│   ├── charts/YYYY-MM-DD.jsonl # one row per chart placement
│   ├── lookups/YYYY-MM-DD.jsonl
│   ├── runs/YYYY-MM-DD.json    # request counts and failures
│   ├── indices/{platform}/{keyword}.json
│   ├── reports/YYYY-MM-DD.{md,json}
│   ├── supply/                  # search cache + YYYY-MM-DD.json
│   └── backtest/                # raw series cache + report.{md,json}
└── src/app_radar/
```

Days are local dates, matching `scripts/generate-daily-build.sh`. Re-running a day overwrites
that day's files. Signals that compare days (rank climbs, rating growth, "first time in this
chart") need earlier snapshots and say which base day they used.

## Quick Start

```bash
uv tool install --force --managed-python --python 3.10 -c constraints.txt -e .
app-radar run                 # fetch + indices (if DATAXAPI_API_KEY is set) + report
app-radar fetch --countries us,cn --genres 6013
app-radar report --date 2026-11-05
```

Paid indices: put the key in the macOS keychain once, and the daily script picks it up.

```bash
security add-generic-password -s dataxapi-api-key -a "$USER" -w '<key>'
DATAXAPI_API_KEY="$(security find-generic-password -s dataxapi-api-key -w)" app-radar indices
```

Each keyword is fetched at most once per `min_interval_days` (default 7); WeChat only returns
the last 30 days, so history exists only from the first fetch on.

## Supply stage

`app-radar supply` (also part of `run`) searches the App Store for each of the day's top themes
and for the watch list in `config/supply.json`, counts look-alike launches per storefront, and
compares them with a baseline of evergreen niche utilities searched the same way. Report section
6 labels each niche: crowded (10+ launches in the last 91 days), has a winner but not crowded,
scattered, or almost empty. When every search term hits the 200-result limit, the stage reads
"capped" unless the lower bound already shows a crowd. Searches are cached for 7 days and the
baseline for 28, so a warm run takes about a minute and a cold one about 12.

## Back-test

`app-radar backtest` checks which signals would have caught past app waves, using only sources
that keep history: Wikipedia pageviews (from 2015-07), Hacker News story counts, GitHub
repositories created per month, and App Store search results with release dates. Waves,
controls and the baseline live in `config/backtest.json`; raw series are cached under
`data/backtest/raw/`, and the report goes to `data/backtest/report.{md,json}`.

```bash
GITHUB_TOKEN="$(gh auth token)" app-radar backtest   # about 30 minutes on a cold cache
```

Known biases: the search API returns at most 200 apps per term and country, removed apps are
missing, and renamed apps keep their original release date.

## Development

```bash
uv venv --managed-python --python 3.10 --clear && source .venv/bin/activate
uv pip install -c constraints.txt -e ".[dev]"
pytest
ruff check .
```
