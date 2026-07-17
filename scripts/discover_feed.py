"""
scripts/discover_feed.py

Tự động tìm URL feed RSS/Atom thật từ một trang chủ, theo đúng cách các trình
đọc RSS chuẩn làm (không đoán mò, không hardcode):

1. Tải HTML trang chủ, tìm thẻ <link rel="alternate" type="application/rss+xml"|"application/atom+xml">
2. Nếu không có, thử lần lượt các đường dẫn phổ biến: /feed/, /feed, /rss.xml,
   /rss/, /atom.xml, /blog/feed.xml, /index.xml
3. Trả về feed_url đầu tiên hoạt động (HTTP 200 + nội dung parse được bằng feedparser)

Dùng làm module import trong main.py, hoặc chạy độc lập để kiểm tra một nguồn:
    python -m scripts.discover_feed https://www.niemanlab.org
"""

from __future__ import annotations

import sys
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin

COMMON_PATHS = [
    "/feed/", "/feed", "/rss.xml", "/rss/", "/atom.xml",
    "/blog/feed.xml", "/blog/rss.xml", "/index.xml",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MediaBriefingBot/1.0; +personal research digest)"
}

TIMEOUT = 10


def _looks_like_feed(text: str) -> bool:
    """Kiểm tra nhanh nội dung có phải RSS/Atom hợp lệ không."""
    parsed = feedparser.parse(text)
    return bool(parsed.entries) or parsed.get("version", "") != ""


def discover_feed(homepage_url: str) -> str | None:
    """Trả về feed_url tìm được, hoặc None nếu không tìm thấy."""
    try:
        resp = requests.get(homepage_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [!] Không tải được {homepage_url}: {e}", file=sys.stderr)
        return None

    # Bước 1: tìm thẻ <link rel="alternate"> trong HTML
    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("link", rel="alternate"):
        type_ = (link.get("type") or "").lower()
        if "rss" in type_ or "atom" in type_:
            href = link.get("href")
            if href:
                candidate = urljoin(homepage_url, href)
                if _verify_feed(candidate):
                    return candidate

    # Bước 2: thử các đường dẫn phổ biến
    for path in COMMON_PATHS:
        candidate = urljoin(homepage_url, path)
        if _verify_feed(candidate):
            return candidate

    return None


def _verify_feed(url: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and _looks_like_feed(r.text):
            return True
    except requests.RequestException:
        pass
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Dùng: python -m scripts.discover_feed <homepage_url>")
        sys.exit(1)
    url = sys.argv[1]
    found = discover_feed(url)
    print(found or "KHÔNG TÌM THẤY — cần kiểm tra thủ công")
