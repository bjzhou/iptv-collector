#!/bin/bash

# Configuration
# ----------------------------------------------------------------
# 设置项目绝对路径 (必须修改为实际路径)
PROJECT_DIR="/opt/iptv-collector"

# 设置 Git 分支 (存放结果的分支)
OUTPUT_BRANCH="output"

# 设置 UV 路径
UV_BIN="/root/.local/bin/uv"

# 设置临时工作树路径
WORKTREE_PATH="/tmp/iptv-collector-output"
# ----------------------------------------------------------------

# 0. Check Arguments
if [ -z "$1" ]; then
    echo "Error: Output filename argument is missing."
    echo "Usage: $0 <output_filename>"
    echo "Example: $0 tv_ipv4.m3u"
    exit 1
fi

OUTPUT_FILENAME="$1"

# 1. Enter Project Directory & Sync Source Code
cd "$PROJECT_DIR" || { echo "Directory not found: $PROJECT_DIR"; exit 1; }

echo "Syncing source code..."
# 获取当前分支名称
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
# 拉取远程更新
git fetch origin
# 强制重置为远程最新状态 (防止本地修改冲突)
git reset --hard "origin/$CURRENT_BRANCH"

# 2. Run Collector
echo "Starting IPTV collection..."
# 确保依赖是最新的 (可选)
$UV_BIN sync
$UV_BIN run main.py

if [ ! -f "iptv.m3u" ]; then
    echo "Error: iptv.m3u generation failed."
    exit 1
fi

# 3. Handle Output using Git Worktree
echo "Preparing to push results to $OUTPUT_FILENAME..."

# Clean up any stale worktree
if [ -d "$WORKTREE_PATH" ]; then
    git worktree remove --force "$WORKTREE_PATH" || rm -rf "$WORKTREE_PATH"
    git worktree prune
fi

# Create worktree for the output branch
if ! git worktree add "$WORKTREE_PATH" "$OUTPUT_BRANCH" 2>/dev/null; then
    # If branch doesn't exist at all, create orphan
    git worktree add --detach "$WORKTREE_PATH"
    cd "$WORKTREE_PATH" || exit 1
    git checkout --orphan "$OUTPUT_BRANCH"
    git rm -rf .
    cd "$PROJECT_DIR" || exit 1
fi

# 4. Sync, Copy, Commit and Push
cd "$WORKTREE_PATH" || exit 1

# [关键步骤] 强制同步 output 分支状态，防止 non-fast-forward 报错
if git show-ref --verify --quiet "refs/remotes/origin/$OUTPUT_BRANCH"; then
    echo "Syncing output branch with remote..."
    git fetch origin "$OUTPUT_BRANCH"
    git reset --hard "origin/$OUTPUT_BRANCH"
fi

# Copy file to worktree
# 源文件在 PROJECT_DIR，目标文件名为脚本参数
cp "$PROJECT_DIR/iptv.m3u" "./$OUTPUT_FILENAME"

# 配置 Git 用户
git config user.email "bot@cron.job"
git config user.name "Cron Bot"

# 提交并推送
git add "$OUTPUT_FILENAME"

if git diff --staged --quiet; then
    echo "No changes to commit for $OUTPUT_FILENAME"
else
    git commit -m "Auto-update $OUTPUT_FILENAME: $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin "$OUTPUT_BRANCH"
fi

# 5. Cleanup
# 清理源文件
rm "$PROJECT_DIR/iptv.m3u"

# 切回主目录清理工作树
cd "$PROJECT_DIR" || exit 1
git worktree remove --force "$WORKTREE_PATH"

echo "Done."
