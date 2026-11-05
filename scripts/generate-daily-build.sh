#!/bin/zsh -l
# 定时出报入口：launchd 每天调它（scripts/install-launchd.sh 安装），也可手动执行（手动跑就是立即出今天的报）。
# 做法与社区标准一致：OS 调度器 + agent 无头模式（omp -p），技能由仓库内
# .agent/skills/daily-article-generator 提供。登录 shell（-l）拿 mise/uv 的 PATH。
# 日志：~/Library/Logs/daily-build-newsletter/YYYY-MM-DD.log
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$HOME/Library/Logs/daily-build-newsletter"
mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/$(date +%F).log" 2>&1

# launchd 的登录 shell 只读 .zprofile（brew 在），~/.local/bin 由 .zshrc 加（不读）——
# 探针实测缺它会导致 article-harvest 不可达。omp 冷启动在 launchd 下约 100s，max-time 已留足。
export PATH="$HOME/.local/bin:$PATH"

cd "$REPO" || { echo "!! repo not found: $REPO"; exit 1; }

DAY="$(date +%F)"
DRAFT="$REPO/assets/$DAY/summary.md"
OBSIDIAN_DIR="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/jiachen yu/Newsletter/Daily Build"

notify() {
  osascript -e "display notification \"$1\" with title \"Daily Build $DAY\"" 2>/dev/null || true
}

echo "=== $(date '+%F %T') daily-build start ==="
rc=0
# App 榜单快照与供给阶段（modules/app-radar，供 Section A 的「App 榜单信号」）：免费，通常 3–5 分钟，
# 供给搜索缓存过期那天约 15 分钟。
# 钥匙串里有 dataxapi-api-key 时顺带拉国内指数（付费，每个词 7 天最多拉一次）。失败不阻断日报。
DATAXAPI_API_KEY="${DATAXAPI_API_KEY:-$(security find-generic-password -s dataxapi-api-key -w 2>/dev/null)}" \
  app-radar run --date "$DAY" || echo "!! app-radar failed (rc=$?), continuing without it"
# 正常一轮 25–40 分钟。MiniMax 下 fact-check 曾拖到 48 分钟，把 3600 顶穿；给 90 分钟余量，
# 撞上时限时 omp 仍可能返回 0，所以下面以 Obsidian 文件是否落地为准，不信退出码。
# 模型钉在 GLM-5.3（subagent 也继承它），不跟 config.yml 的默认模型走：
# 10-24 默认换成 MiniMax-M3.1-Flash 后连续超时，GLM 期间一轮 26–40 分钟。
omp -p --auto-approve --advisor --max-time 5400 \
  --model zhipu-coding-plan/glm-5.3 --thinking max \
  "使用本仓库的 daily-article-generator 技能，按 SKILL.md 的完整流程生成今天（$DAY）的日报：检查并 ingest、7 天去重、分类落盘、summary.md（含三条长度自检）、事实审查、主题台账、Obsidian 同步，最后按 step 12 输出收尾报告。SUBSTACK_SID 取不到或 rfcs 源缺 GITHUB_TOKEN 时按 SKILL.md 的降级规则继续，不要中断。" \
  || rc=$?
echo "=== $(date '+%F %T') omp exit $rc ==="

# 兜底：agent 没走到 step 11 时，把已写好的初稿标成未审查后同步，保证 Today.md 是当天的。
if [[ ! -f "$OBSIDIAN_DIR/$DAY.md" ]]; then
  if [[ -s "$DRAFT" ]]; then
    mkdir -p "$OBSIDIAN_DIR"
    { printf '> 定时任务兜底同步：omp 没有跑完全流程，本期未经事实审查。\n\n'; cat "$DRAFT"; } \
      > "$OBSIDIAN_DIR/$DAY.md"
    cp "$OBSIDIAN_DIR/$DAY.md" "$OBSIDIAN_DIR/Today.md"
    echo "!! agent did not sync; copied unchecked draft to Obsidian"
    notify "未跑完，已同步未审查初稿"
  else
    echo "!! no summary.md for $DAY; nothing synced"
    notify "失败：没有生成 summary.md"
  fi
  [[ $rc -eq 0 ]] && rc=2
fi
echo "=== $(date '+%F %T') daily-build exit $rc ==="
exit $rc
