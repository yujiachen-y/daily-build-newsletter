#!/bin/zsh -l
# 定时出报入口：launchd 每天 07:00 和 12:05 各调一次（scripts/install-launchd.sh 安装），也可手动执行。
# 做法与社区标准一致：OS 调度器 + agent 无头模式（claude -p），技能由仓库内
# .agent/skills/daily-article-generator 提供。登录 shell（-l）拿 mise/uv 的 PATH。
# 日志：~/Library/Logs/daily-build-newsletter/YYYY-MM-DD.log
#
# 同一天可以重复执行：Obsidian 里已有审查过的当天文件就直接退出；上一轮没跑完（订阅额度、超时）
# 就 --resume 同一个会话接着跑，不重新 ingest。12:05 那次就是 07:00 的保活重试：
# 5 小时额度窗口到那时一定已重置。
#
# 测试用环境变量：DAILY_BUILD_DAY、DAILY_BUILD_LOG_DIR、DAILY_BUILD_OBSIDIAN_DIR 覆盖日期和目录；
# DAILY_BUILD_DRY_RUN=1 只打印 claude 命令不执行，退出码取 DAILY_BUILD_DRY_RC（默认 0）。
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DAY="${DAILY_BUILD_DAY:-$(date +%F)}"
LOG_DIR="${DAILY_BUILD_LOG_DIR:-$HOME/Library/Logs/daily-build-newsletter}"
LOG_FILE="$LOG_DIR/$DAY.log"
mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1

# launchd 的登录 shell 只读 .zprofile（brew 在），~/.local/bin 由 .zshrc 加（不读）——
# 探针实测缺它会导致 article-harvest 不可达；claude 也装在这里。
export PATH="$HOME/.local/bin:$PATH"

cd "$REPO" || { echo "!! repo not found: $REPO"; exit 1; }

DRAFT="$REPO/assets/$DAY/summary.md"
OBSIDIAN_DIR="${DAILY_BUILD_OBSIDIAN_DIR:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/jiachen yu/Newsletter/Daily Build}"
BANNER='> 定时任务兜底同步：agent 没有跑完全流程，本期未经事实审查。'

notify() {
  [[ -n "${DAILY_BUILD_DRY_RUN:-}" ]] && { echo "NOTIFY: $1"; return; }
  osascript -e "display notification \"$1\" with title \"Daily Build $DAY\"" 2>/dev/null || true
}

# launchd 下 TCC 不许本脚本的 zsh、cp、head 读或覆盖 iCloud 里已有的文件（只能新建），python3 和 claude
# （连同它 Bash 里的子进程）可以，11-07 实测。所以脚本自己碰 Obsidian 一律走 python3。
obsidian_first_line() {
  python3 -I -c 'import sys; print(open(sys.argv[1], encoding="utf-8").readline().rstrip("\n"))' "$1"
}

# 当天已同步、且不是兜底的未审查版本，才算完成。读不了文件时按已完成处理并报警，免得天天重跑烧额度。
done_today() {
  [[ -f "$OBSIDIAN_DIR/$DAY.md" ]] || return 1
  local first
  if ! first="$(obsidian_first_line "$OBSIDIAN_DIR/$DAY.md" 2>&1)"; then
    echo "!! cannot read $DAY.md in Obsidian ($first); treating as done"
    return 0
  fi
  [[ "$first" != "$BANNER" ]]
}

# dry-run 的替身只回显参数；正式流程（带 stream-json 的那次）按 DAILY_BUILD_DRY_RC 退出，预检恒成功。
if [[ -n "${DAILY_BUILD_DRY_RUN:-}" ]]; then
  CLAUDE=(sh -c 'echo "DRY RUN: claude $*"; case "$*" in *stream-json*) exit "${DAILY_BUILD_DRY_RC:-0}";; esac' sh)
else
  CLAUDE=(claude)
fi

echo "=== $(date '+%F %T') daily-build start ==="
if done_today; then
  echo "=== $DAY already synced to Obsidian; nothing to do ==="
  exit 0
fi

# 07:00 那轮最多跑 90 分钟，正常不会和 12:05 重叠；锁只防手动执行撞上定时任务。
LOCK="$LOG_DIR/$DAY.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  pid="$(cat "$LOCK/pid" 2>/dev/null)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "=== another run (pid $pid) is still going; skip ==="
    exit 0
  fi
  echo "!! stale lock from pid ${pid:-?}; taking over"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

ATTEMPT="$(grep -c 'daily-build start' "$LOG_FILE")"
rc=0

# App 榜单快照与供给阶段（modules/app-radar，供 Section A 的「App 榜单信号」）：免费，通常 3–5 分钟，
# 供给搜索缓存过期那天约 15 分钟。当天已有报告就不重跑。
# 钥匙串里有 dataxapi-api-key 时顺带拉国内指数（付费，每个词 7 天最多拉一次）。失败不阻断日报。
if [[ ! -f "$REPO/modules/app-radar/data/reports/$DAY.md" ]]; then
  DATAXAPI_API_KEY="${DATAXAPI_API_KEY:-$(security find-generic-password -s dataxapi-api-key -w 2>/dev/null)}" \
    app-radar run --date "$DAY" || echo "!! app-radar failed (rc=$?), continuing without it"
fi

# 上一轮留下的会话：取当天最新一个带 session_id 的 stream 文件。
streams=("$LOG_DIR/$DAY".claude*.jsonl(Nom))  # 按修改时间从新到旧，没有匹配时为空
SESSION_ID="$(print -rl -- $streams | python3 -I -c '
import json, sys
for path in sys.stdin.read().split("\n"):
    if not path:
        continue
    for line in open(path, errors="ignore"):
        try:
            sid = json.loads(line).get("session_id")
        except ValueError:
            continue
        if sid:
            print(sid)
            sys.exit(0)
')"

FRESH_PROMPT="使用本仓库的 daily-article-generator 技能，按 SKILL.md 的完整流程生成今天（$DAY）的日报：检查并 ingest、7 天去重、分类落盘、summary.md（含三条长度自检）、事实审查、主题台账、Obsidian 同步，最后按 step 12 输出收尾报告。SUBSTACK_SID 取不到或 rfcs 源缺 GITHUB_TOKEN 时按 SKILL.md 的降级规则继续，不要中断。等待 subagent 时依赖完成通知，不要用 ScheduleWakeup。"
RESUME_PROMPT="上一轮定时运行没有跑完（可能撞上订阅额度或超时），请继续完成 $DAY 的日报。之前启动的 subagent 已随进程终止，不会再回报：先检查 assets/$DAY/ 现有文件，缺失或不完整的 Section 草稿重新启动 subagent 或自己写。不要重新 ingest，直接使用已落盘的 archive 和分类文件。等待 subagent 时依赖完成通知，不要用 ScheduleWakeup。然后按 SKILL.md 从尚未完成的步骤继续，直到 Obsidian 同步（含 Today.md）和 step 12 收尾报告。Obsidian 里的 $DAY.md 如果是开头写着「未经事实审查」的兜底版本，直接覆盖。"

if [[ -n "$SESSION_ID" && -d "$REPO/assets/$DAY" ]]; then
  MODE=(--resume "$SESSION_ID"); PROMPT="$RESUME_PROMPT"
  echo "=== attempt $ATTEMPT: resume session $SESSION_ID ==="
else
  MODE=(); PROMPT="$FRESH_PROMPT"
  echo "=== attempt $ATTEMPT: fresh run ==="
  # 本地 08:00 起已是 UTC 次日：此时 ingest 会落到下一个 UTC 日期，明天 07:00 那轮会在同一 UTC 日再 ingest。
  (( $(date +%H) >= 8 )) && echo "!! fresh run after UTC midnight; tomorrow's ingest will share this UTC date"
fi

# 无人值守没人批权限弹窗，用 bypassPermissions（与之前 omp --auto-approve 等价）。
# 代价：抓来的网页若藏着 prompt injection，能直接执行命令。
# 模型与 effort 暂定 opus + high，等对比测试再调；stream 里的 result 事件记录耗时和 token 用量。
# 11-07 实测一整轮（两天素材）约占 5 小时额度窗口的 81%。
# 11-06 首轮卡在启动阶段（90 分钟没写出会话记录，被 timeout 杀掉），白天在 launchd 下复现不了。
# 先用 2 分钟上限的小请求把认证、hook、MCP 启动走一遍，卡住重试一次；两次都失败就不跑正式流程。
preflight() {
  timeout --kill-after=10 120 "${CLAUDE[@]}" -p --model sonnet --effort low --permission-mode bypassPermissions \
    --no-session-persistence --debug-file "$LOG_DIR/$DAY.preflight-$ATTEMPT-$1.debug.log" "Reply with: pong" < /dev/null
}
if preflight 1 || { sleep 60; preflight 2; }; then
  # stream-json 边跑边落盘，卡住时能看到停在哪一步；debug 日志记录启动阶段。
  CLAUDE_STREAM="$LOG_DIR/$DAY.claude-$ATTEMPT.jsonl"
  timeout --kill-after=60 5400 "${CLAUDE[@]}" -p "${MODE[@]}" \
    --model opus --effort high --permission-mode bypassPermissions \
    --output-format stream-json --verbose --debug-file "$LOG_DIR/$DAY.claude-$ATTEMPT-debug.log" \
    "$PROMPT" < /dev/null > "$CLAUDE_STREAM" || rc=$?
  echo "=== $(date '+%F %T') claude exit $rc ==="
  python3 -I - "$CLAUDE_STREAM" <<'EOF' || echo "!! no result event in claude stream"
import json, sys
d = None
for line in open(sys.argv[1]):
    try:
        o = json.loads(line)
    except ValueError:
        continue
    if o.get("type") == "result":
        d = o
if d is None:
    sys.exit(1)
u = d.get("usage") or {}
print(d.get("result") or "")
print(f"-- subtype={d.get('subtype')} is_error={d.get('is_error')} "
      f"duration={round((d.get('duration_ms') or 0) / 60000, 1)}min turns={d.get('num_turns')} "
      f"cost_usd={d.get('total_cost_usd')} in={u.get('input_tokens')} out={u.get('output_tokens')} "
      f"cache_read={u.get('cache_read_input_tokens')} cache_write={u.get('cache_creation_input_tokens')}")
EOF
else
  rc=3
  echo "!! claude preflight failed twice; skipped the daily run"
fi

# 兜底：agent 没走到 step 11 时，把已写好的初稿标成未审查后同步，保证 Today.md 是当天的。
# 下一次执行（12:05）不会把这个版本当成完成，会续跑并用审查过的版本覆盖。
if ! done_today; then
  if [[ -s "$DRAFT" ]]; then
    python3 -I - "$BANNER" "$DRAFT" "$OBSIDIAN_DIR/$DAY.md" "$OBSIDIAN_DIR/Today.md" <<'EOF' \
      && echo "!! agent did not sync; copied unchecked draft to Obsidian" \
      || echo "!! failed to copy unchecked draft to Obsidian"
import os, sys
banner, draft, *dests = sys.argv[1:]
text = banner + "\n\n" + open(draft, encoding="utf-8").read()
for dest in dests:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)
EOF
    notify "第 $ATTEMPT 次未跑完，已同步未审查初稿"
  else
    echo "!! no summary.md for $DAY; nothing synced"
    notify "第 $ATTEMPT 次失败：没有生成 summary.md"
  fi
  [[ $rc -eq 0 ]] && rc=2
fi
echo "=== $(date '+%F %T') daily-build exit $rc ==="
exit $rc
