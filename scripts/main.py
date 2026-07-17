"""
scripts/main.py

Orchestrator chính — theo dõi các chủ đề thời sự ("topics" trong sources.yaml)
cùng lúc qua nhiều báo VN ("outlets"), lọc ra bài THẬT SỰ mới so với lần chạy
trước, xuất kết quả thành new_items.json để Claude đọc và viết bản tổng hợp
"Toàn cảnh: {tên chủ đề}".

Chạy: python -m scripts.main
Output: new_items.json ở thư mục gốc repo.
"""

from __future__ import annotations  # tương thích Python 3.9.6 (xem CLAUDE.md)

import json
import unicodedata
from pathlib import Path

import feedparser
import yaml

from scripts.dedup_store import load_state, save_state, filter_new_items
from scripts.discover_feed import discover_feed

ROOT = Path(__file__).parent.parent
SOURCES_PATH = ROOT / "config" / "sources.yaml"
OUTPUT_PATH = ROOT / "new_items.json"

MAX_ITEMS_PER_SOURCE = 30  # feed thời sự cập nhật dày trong ngày, nên nới rộng
SNIPPET_LENGTH = 150


def build_output(new_items_by_outlet: dict) -> tuple:
    """Biến đổi {outlet: [items]} thành 2 danh sách phẳng dùng chung field
    "id" để tra cứu chéo: index (nhẹ, để cụm nhóm) và detail (đầy đủ, để viết
    "Toàn cảnh" cho các chủ đề đã chọn)."""
    index_items = []
    detail_items = []
    for outlet, items in new_items_by_outlet.items():
        for item in items:
            index_items.append({
                "id": item["id"],
                "outlet": outlet,
                "title": item["title"],
                "snippet": item["summary_raw"][:SNIPPET_LENGTH],
                "link": item["link"],
                "published": item["published"],
            })
            detail_items.append({
                "id": item["id"],
                "outlet": outlet,
                "title": item["title"],
                "summary": item["summary_raw"],
                "link": item["link"],
            })
    return index_items, detail_items


def load_config() -> dict:
    raw = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    return {
        "outlets": raw.get("outlets", []),
        "topics": raw.get("topics", []),
    }


def _normalize(text: str) -> str:
    """Chuẩn hóa Unicode (NFC) + hạ chữ thường, để so khớp từ khóa tiếng Việt
    ổn định bất kể trang nguồn encode dấu theo kiểu tổ hợp (NFD) hay sẵn (NFC)."""
    return unicodedata.normalize("NFC", text or "").lower()


def matches_keywords(item: dict, keywords: list[str]) -> bool:
    haystack = _normalize(item.get("title", "") + " " + item.get("summary_raw", ""))
    return any(_normalize(kw) in haystack for kw in keywords)


def fetch_outlet_items(source: dict) -> list[dict]:
    feed_url = source.get("feed_url")
    if not feed_url:
        feed_url = discover_feed(source["url"])
        if not feed_url:
            print(f"  [!] Không tìm được feed cho '{source['name']}' — bỏ qua, cần kiểm tra thủ công.")
            return []

    parsed = feedparser.parse(feed_url)
    items = []
    for entry in parsed.entries[:MAX_ITEMS_PER_SOURCE]:
        items.append({
            "id": entry.get("id") or entry.get("link"),
            "title": entry.get("title", "(không có tiêu đề)"),
            "link": entry.get("link", ""),
            "published": entry.get("published", entry.get("updated", "")),
            "summary_raw": entry.get("summary", "")[:800],  # cắt bớt, Claude sẽ tự diễn giải lại
        })
    return items


def fetch_all_new_items(outlets: list, state: dict) -> dict:
    """Quét toàn bộ outlets, trả về {tên báo: [bài mới]}. Dedup theo tên báo
    (state key = tên báo, không còn theo chủ đề — mỗi báo chỉ quét một lần
    mỗi ngày, không lặp lại cho từng chủ đề như thiết kế cũ)."""
    result = {}
    for source in outlets:
        name = source["name"]
        print(f"Đang quét: {name}")
        items = fetch_outlet_items(source)
        new_items = filter_new_items(name, items, state)
        result[name] = new_items
        print(f"  -> {len(items)} bài trong feed, {len(new_items)} bài mới")
    return result


def process_topics(topics: list[dict], outlets: list[dict], state: dict) -> dict:
    """Với mỗi chủ đề: quét các báo khai báo (hoặc TẤT CẢ báo trong outlets:
    nếu topic không giới hạn danh sách), giữ lại bài khớp từ khóa VÀ chưa từng
    thấy — dùng khoá "topic::<id>::<tên báo>" trong state để mỗi chủ đề có
    lịch sử dedupe riêng, kể cả khi hai chủ đề cùng quét một báo."""
    outlets_by_name = {o["name"]: o for o in outlets}
    result = {}

    for topic in topics:
        topic_id, name, keywords = topic["id"], topic["name"], topic["keywords"]
        print(f"Đang xử lý chủ đề: {name} ({topic_id})")
        topic_items = []

        wanted_names = topic.get("outlets") or list(outlets_by_name.keys())
        for src_name in wanted_names:
            source = outlets_by_name.get(src_name)
            if source is None:
                print(f"  [!] '{src_name}' không có trong outlets: — kiểm tra lại chính tả trong topics.{topic_id}.outlets")
                continue

            items = fetch_outlet_items(source)
            matched = [item for item in items if matches_keywords(item, keywords)]

            state_key = f"topic::{topic_id}::{src_name}"
            new_items = filter_new_items(state_key, matched, state)
            for item in new_items:
                item["source"] = src_name
            topic_items.extend(new_items)
            print(f"  -> {src_name}: {len(matched)} bài khớp từ khóa, {len(new_items)} bài mới")

        result[topic_id] = {"name": name, "items": topic_items}

    return result


def main():
    config = load_config()
    state = load_state()

    topics_result = process_topics(config["topics"], config["outlets"], state)
    result = {"topics": topics_result}

    save_state(state)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi kết quả vào {OUTPUT_PATH}")
    total_topic_items = sum(len(t["items"]) for t in topics_result.values())
    print(f"Tổng {total_topic_items} bài mới khớp các chủ đề đang theo dõi.")


if __name__ == "__main__":
    main()
