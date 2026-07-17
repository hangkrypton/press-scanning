"""
scripts/dedup_store.py

Lưu lại "đã thấy mục nào" giữa các lần chạy, để mỗi ngày chỉ xử lý tin THẬT SỰ
mới — đây là phần giúp tiết kiệm token nhiều nhất so với để Claude tự đọc lại
toàn bộ trang mỗi lần.

State lưu tại state/seen.json, có cấu trúc:
{
  "Nieman Lab": ["<id bài 1>", "<id bài 2>", ...],
  ...
}

Chỉ giữ tối đa MAX_IDS_PER_SOURCE id gần nhất mỗi nguồn để file không phình to
mãi theo thời gian.
"""

import json
from pathlib import Path

STATE_PATH = Path(__file__).parent.parent / "state" / "seen.json"
MAX_IDS_PER_SOURCE = 500


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_new_items(source_name: str, items: list[dict], state: dict) -> list[dict]:
    """
    items: list các dict có ít nhất khoá "id" (dùng link bài viết hoặc message-id làm id).
    Trả về những item CHƯA có trong state, đồng thời cập nhật state (nhưng chưa ghi file
    — gọi save_state() sau khi xử lý xong toàn bộ để tránh mất dữ liệu nếu lỗi giữa chừng).
    """
    seen_ids = set(state.get(source_name, []))
    new_items = [item for item in items if item["id"] not in seen_ids]

    updated_ids = list(seen_ids) + [item["id"] for item in new_items]
    state[source_name] = updated_ids[-MAX_IDS_PER_SOURCE:]

    return new_items
