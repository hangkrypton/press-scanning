#!/bin/bash
# Chạy hằng ngày qua launchd: lấy tin RSS/GitHub mới rồi push lên repo,
# để routine cloud (chạy sau đó) đọc new_items.json và viết bản tóm tắt.
set -euo pipefail

cd "$(dirname "$0")/.."

/usr/bin/python3 -m pip install --quiet -r requirements.txt
/usr/bin/python3 -m scripts.main

git add new_items.json state/seen.json

if ! git diff --cached --quiet; then
  git commit -m "Daily fetch $(date +%Y-%m-%d)"
  git push origin main
else
  echo "Không có thay đổi mới, bỏ qua commit/push."
fi
