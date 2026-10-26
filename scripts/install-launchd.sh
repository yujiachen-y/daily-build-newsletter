#!/bin/zsh
# 安装（或重装）每天 04:00 跑 generate-daily-build.sh 的 launchd job。
# plist 在这里按本机 $HOME 和仓库位置现生成，仓库里不放带绝对路径的 plist。
set -euo pipefail

LABEL="com.yujiachen.daily-build-newsletter"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/daily-build-newsletter"

# launchd 在 spawn 前打开日志路径，不会自建目录，漏了这步 job 直接 exit 78。
mkdir -p "$LOG_DIR" "$(dirname "$PLIST")"

# 历史 out 报时间 ~04:2x；04:00 起跑留足余量。睡眠错过时 launchd 唤醒后补跑一次。
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-l</string>
        <string>$REPO/scripts/generate-daily-build.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd.err.log</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST"

# 已加载的旧版本先卸掉，否则 bootstrap 报 "Bootstrap failed: 5"。
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL -> $PLIST"
