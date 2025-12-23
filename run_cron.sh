#!/bin/bash

# Configuration
# ----------------------------------------------------------------
# 设置项目绝对路径 (必须修改为实际路径)
PROJECT_DIR="/opt/iptv-collector"

# 设置输出文件名
OUTPUT_FILENAME="tv_ipv4.m3u"

# 设置 Git 分支
OUTPUT_BRANCH="output"

# 设置 UV 路径 (如果不在 PATH 中，请填写绝对路径)
UV_BIN="/root/.local/bin/uv"

# 设置临时工作树路径
WORKTREE_PATH="/tmp/iptv-collector-output"
# ----------------------------------------------------------------

# 1. Enter Project Directory
cd "$PROJECT_DIR" || { echo "Directory not found: $PROJECT_DIR"; exit 1; }

# 2. Run Collector
echo "Starting IPTV collection..."
$UV_BIN run main.py

if [ ! -f "iptv.m3u" ]; then
    echo "Error: iptv.m3u generation failed."
    exit 1
fi

# 3. Handle Output using Git Worktree
echo "Preparing to push results..."

# Clean up any stale worktree
if [ -d "$WORKTREE_PATH" ]; then
    git worktree remove --force "$WORKTREE_PATH" || rm -rf "$WORKTREE_PATH"
    git worktree prune
fi

# Fetch latest from remote
git fetch origin

# Create worktree for the output branch
# If branch exists remote but not local, this creates local tracking branch
if ! git worktree add "$WORKTREE_PATH" "$OUTPUT_BRANCH" 2>/dev/null; then
    # If branch doesn't exist at all, create orphan
    git worktree add --detach "$WORKTREE_PATH"
    cd "$WORKTREE_PATH"
    git checkout --orphan "$OUTPUT_BRANCH"
    git rm -rf .
    cd "$PROJECT_DIR"
fi

# Copy file to worktree
cp iptv.m3u "$WORKTREE_PATH/$OUTPUT_FILENAME"
rm iptv.m3u  # Clean up source file

# 4. Commit and Push from worktree
cd "$WORKTREE_PATH" || exit 1

git config user.email "bot@cron.job"
git config user.name "Cron Bot"

git add "$OUTPUT_FILENAME"
if git diff --staged --quiet; then
    echo "No changes to commit"
else
    git commit -m "Auto-update: $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin "$OUTPUT_BRANCH"
fi

# 5. Cleanup
cd "$PROJECT_DIR"
git worktree remove --force "$WORKTREE_PATH"

echo "Done."
