#!/bin/bash
# Chạy hằng ngày qua launchd (06:00 Asia/Saigon): quét RSS toàn bộ báo trong
# config/sources.yaml, lọc bài mới so với state/seen.json, ghi new_items.json +
# new_items_detail.json rồi commit + push lên GitHub. Routine cloud (chạy sau,
# 06:30) đọc 2 file này từ repo để viết bản "Toàn cảnh". Đây là phần DUY NHẤT
# chạm internet / ghi git — xem CLAUDE.md (mô hình local + cloud).
set -euo pipefail

cd "$(dirname "$0")/.."

/usr/bin/python3 -m pip install --quiet -r requirements.txt
/usr/bin/python3 -m scripts.main

git add new_items.json new_items_detail.json

if ! git diff --cached --quiet; then
  git commit -m "Daily fetch $(date +%Y-%m-%d)"
  git push origin main
else
  echo "Không có thay đổi mới, bỏ qua commit/push."
fi
