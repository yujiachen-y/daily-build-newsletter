# Plugin Radar Module

Daily heat signals for agent plugins and skills, written up as the newsletter's
「插件与技能热度」 block (Section A, after 「App 榜单信号」).

It answers one question: which plugins and skills are people installing more than before, and
can the number be trusted? Every rate is per day over the real gap between two observations,
every install counter is checked against GitHub (stars, repo age), and history is backfilled
from the Internet Archive so the first run already compares against last week.

## What each platform exposes

Checked on 2026-11-22. "Popularity" means a per-plugin number that moves.

| Platform | Source used | Popularity number | Notes |
|---|---|---|---|
| Claude Code | `anthropics/claude-plugins-official` marketplace.json + git history; `plugin-details.json` | Frozen | `plugin-details.json` (what `/plugin` sorts by) was last generated 2026-10-21. The install counts on claude.com/marketplace have not changed since at least 2026-09-29 (Internet Archive captures). Listings and removals are live. |
| Codex | `openai/plugins` marketplace.json + git history | None | The client's `/backend-api/ps/plugins/list` needs a ChatGPT session; the binary has no install-count field. |
| WorkBuddy | SkillHub (`api.skillhub.cn`), the "SkillHub" tab of WorkBuddy's skill market | Cumulative downloads, favourites, SkillHub's own trending list | The 使用量 / 安装量 on the 推荐 and 套件 tabs need the desktop client and a login. |
| ZCode | `zai-org/zcode-plugins` marketplace.json + git history | None | The open-source client has no install-count field. |
| Kimi Work | kimi.com/features/plugins (public showcase) | None | The full list is on the open platform (`/v1/plugins`, API key). Changes start from the second run. |
| 豆包 | Not covered | None | The skill store lives only inside the PC client. |
| Cross-agent | skills.sh (pages), ClawHub (`clawhub.ai/api/v1/skills`) | skills.sh: total installs, 8 complete weeks, last 24 h. ClawHub: cumulative downloads and installs | skills.sh counts `npx skills` installs from any agent; ClawHub is OpenClaw's registry. |

## Signals

- **skills.sh rising**: installs per day over the last ~7 days (base: own snapshot, or an
  Internet Archive capture on the first run), against the higher of last week's and the
  previous four weeks' daily average. Needs ≥300 a day and ≥1.5×.
- **Weekly acceleration**: the newest complete week (UTC Monday to Sunday) against the four
  before it. `weeklyInstalls` rolls over early on Monday UTC, so it changes once a week.
- **Breakouts**: rows in the 24-hour top 100 whose last day is ≥25% of their total, or that are
  not yet in the all-time top 600.
- **Suspected farming**: ≥1,000 installs a day on a repo with <100 stars, ≥5,000 a day at more
  than 20 a day per star, or the same skill name pushed by ≥3 repos under 500 stars. Suspects and
  non-GitHub sources ("well-known" domains) are kept out of every list above. On 2026-11-22, 38%
  of the 24-hour installs came from such repos (e.g. `beltsh/superpowers`, 3 stars, created
  2026-11-13, #1 with 29,456 installs).
- **One row per repo**: `npx skills add owner/repo` installs every skill in a repo at once, so
  siblings are folded into the strongest row.
- **Official listings**: plugins added or removed in the last 7 days, dated by the commit that
  made the change; Kimi diffs against the previous snapshot.
- **SkillHub / ClawHub**: download growth per day against an earlier snapshot (from the second
  run), and skills listed in the last 14 days ranked by downloads per day since listing.

## Layout

```
modules/plugin-radar/
├── data/                            # ignored by git
│   ├── snapshots/<source>/<day>.json  # parsed observation; origin live or wayback
│   ├── raw/<day>/*.gz               # the responses those snapshots were parsed from
│   ├── runs/<day>.json              # per-source status
│   └── reports/<day>.{md,json}
└── src/plugin_radar/
    ├── skillssh.py   # pages + Internet Archive backfill
    ├── hubs.py       # SkillHub, ClawHub
    ├── catalogs.py   # official marketplaces, Kimi page, Claude install file
    ├── github.py     # stars and repo age (GraphQL with a token, 40 REST calls without)
    ├── signals.py    # pure functions over snapshots
    └── report.py
```

Days are local dates, matching `scripts/generate-daily-build.sh`. Re-running a day overwrites
that day's files; a source that fails on a re-run keeps the earlier same-day snapshot
(status `reused`). A source that failed and has no same-day snapshot is left out of the report
and listed as `failed`; yesterday's data is never shown as today's.

## Quick Start

```bash
uv tool install --force --managed-python --python 3.10 -c constraints.txt -e .
GITHUB_TOKEN="$(gh auth token)" plugin-radar run   # about 2 minutes
plugin-radar report --date 2026-11-22                # rebuild from saved snapshots, offline
plugin-radar backfill --date 2026-11-22              # only the Internet Archive step
```

Without `GITHUB_TOKEN` only the 40 highest-priority repos get a star check and the rest show as
unverified, which keeps them out of the signal lists.

## Development

```bash
uv venv --managed-python --python 3.10 --clear && source .venv/bin/activate
uv pip install -c constraints.txt -e ".[dev]"
pytest && ruff check .
```
