#!/bin/zsh -l
# 定时出报入口：launchd 每天调它，也可手动执行（手动跑就是立即出今天的报）。
# 做法与社区标准一致：OS 调度器 + agent 无头模式（omp -p），技能由仓库内
# .agent/skills/daily-article-generator 提供。登录 shell（-l）拿 mise/uv 的 PATH。
# 日志：~/Library/Logs/daily-build-newsletter/YYYY-MM-DD.log
set -uo pipefail

REPO="$HOME/Workspace/github.com/yujiachen-y/daily-build-newsletter"
LOG_DIR="$HOME/Library/Logs/daily-build-newsletter"
mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/$(date +%F).log" 2>&1

# launchd 的登录 shell 只读 .zprofile（brew 在），~/.local/bin 由 .zshrc 加（不读）——
# 探针实测缺它会导致 article-harvest 不可达。omp 冷启动在 launchd 下约 100s，max-time 已留足。
export PATH="$HOME/.local/bin:$PATH"

cd "$REPO" || { echo "!! repo not found: $REPO"; exit 1; }

echo "=== $(date '+%F %T') daily-build start ==="
rc=0
omp -p --auto-approve --advisor --max-time 3600 \
  "使用本仓库的 daily-article-generator 技能，按 SKILL.md 的完整流程生成今天（$(date +%F)）的日报：检查并 ingest、7 天去重、分类落盘、summary.md（含三条长度自检）、事实审查、主题台账、Obsidian 同步，最后按 step 12 输出收尾报告。SUBSTACK_SID 取不到或 rfcs 源缺 GITHUB_TOKEN 时按 SKILL.md 的降级规则继续，不要中断。" \
  || rc=$?
echo "=== $(date '+%F %T') daily-build exit $rc ==="
exit $rc
