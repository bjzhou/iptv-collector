#!/bin/bash

# Configuration
# ----------------------------------------------------------------
# 设置项目绝对路径 (必须修改为实际路径)
PROJECT_DIR="/opt/iptv-collector"

# 设置输出文件名
OUTPUT_FILENAME="tv_ipv4.m3u"

# 设置 Git 分支
OUTPUT_BRANCH="output"

# 设置 UV 路径 (如果不在 PATH 中，请填写绝对路径，例如 /home/username/.cargo/bin/uv)
UV_BIN="/root/.local/bin/uv"
# ----------------------------------------------------------------

# 1. Enter Project Directory
cd "$PROJECT_DIR" || { echo "Directory not found: $PROJECT_DIR"; exit 1; }

# 2. Update Code (Optional, uncomment if you want auto-update)
# git pull origin main

# 3. Run Collector
echo "Starting IPTV collection..."
$UV_BIN run main.py

if [ ! -f "iptv.m3u" ]; then
    echo "Error: iptv.m3u generation failed."
    exit 1
fi

# 4. Handle Output
echo "Preparing to push results..."

# Rename/Copy to temp to survive branch switch
cp iptv.m3u "/tmp/${OUTPUT_FILENAME}"

# Switch to output branch
# Fetch latest to ensure we know about output branch
git fetch origin

if git rev-parse --verify "origin/${OUTPUT_BRANCH}" >/dev/null 2>&1; then
    # Checkout existing branch
    git checkout "$OUTPUT_BRANCH"
    git reset --hard "origin/${OUTPUT_BRANCH}"
    git pull origin "$OUTPUT_BRANCH"
else
    # Create orphan branch if it doesn't exist locally/remotely
    git checkout --orphan "$OUTPUT_BRANCH"
    git rm -rf .
fi

# Restore file with new name
mv "/tmp/${OUTPUT_FILENAME}" "./${OUTPUT_FILENAME}"

# 5. Commit and Push
git config user.email "bot@cron.job"
git config user.name "Cron Bot"

git add "$OUTPUT_FILENAME"
git commit -m "Auto-update: $(date '+%Y-%m-%d %H:%M:%S')" || echo "No changes to commit"

# Push using local token/ssh config (Ensure authentication is set up)
git push origin "$OUTPUT_BRANCH"

# 6. Switch back to main (Recommended for next run)
git checkout main

echo "Done."
