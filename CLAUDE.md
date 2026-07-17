# press-scanning

Tự động phát hiện các chủ đề thời sự đang được nhiều báo điện tử Việt Nam cùng đưa tin trong ngày (`config/sources.yaml`: `outlets:`), để thấy "bức tranh chung" — cùng một sự kiện, báo nào khai thác góc nào. Repo: https://github.com/hangkrypton/press-scanning.

This is a **separate project** from `media-briefing-bot` (a different repo/bot on this same machine — daily AI/journalism-industry newsletter digest, no topic tracking) — do not reuse its repo name, LaunchAgent label, or log file names for anything in this project.

Không có nguồn Gmail/newsletter nào trong dự án này — toàn bộ dữ liệu đến từ RSS feed của 21 báo trong `outlets:`. Cloud routine vì vậy không cần bật connector Gmail.

## Architecture: một scheduled task local duy nhất

Toàn bộ pipeline chạy trong **một** Claude Code scheduled task local — không
còn tách local script + cloud routine như thiết kế trước đây (lý do và quá
trình quyết định: `docs/superpowers/specs/2026-07-17-auto-topic-detection-design.md`).
Task chạy tuần tự mỗi ngày:

1. **Fetch & dedup** — `python -m scripts.main` quét RSS toàn bộ báo trong
   `outlets:`, lọc bài mới so với `state/seen.json` (dedup theo từng báo),
   xuất `new_items.json` (bản nhẹ) và `new_items_detail.json` (bản đầy đủ,
   đánh chỉ mục theo `id`).
2. **Cụm nhóm** — Claude đọc `new_items.json`, tự nhận diện các bài viết về
   cùng một sự kiện theo hiểu ngữ nghĩa (không so khớp từ khóa), giữ lại nhóm
   có **≥3 báo khác nhau** cùng đưa tin.
3. **Viết tổng hợp** — với mỗi nhóm được chọn, tra cứu (Grep theo `id`) chi
   tiết trong `new_items_detail.json`, viết mục "Toàn cảnh: {tên chủ đề}".
4. **Lưu Drive** — nếu có ≥1 chủ đề đạt ngưỡng, lưu 1 Google Doc "Toàn cảnh -
   YYYY-MM-DD" vào thư mục "Press Scanning" trên Google Drive (**cần bật
   connector Google Drive** trên task này). Không có chủ đề nào đạt ngưỡng →
   bỏ qua, không tạo file rỗng.

`state/seen.json`, `new_items.json`, `new_items_detail.json` là dữ liệu
runtime cục bộ, **không** commit vào git (xem `.gitignore`) — mất file này chỉ
khiến lần chạy kế tiếp coi mọi bài là "mới" một lần.

Vì không còn cloud routine đọc-only nào cần clone repo, **repo không còn bắt
buộc phải public**.

## Local environment gotchas

- System Python is 3.9.6 (`/usr/bin/python3`) — **no `X | None` union type syntax**; add `from __future__ import annotations` at the top of any new module using it (already done throughout `scripts/`).
- `git` on this machine uses `credential.helper=osxkeychain` with a cached PAT — non-interactive `git push` from launchd works as-is. If pushes start failing with an auth prompt, the PAT likely expired (fine-grained tokens were created with a short expiry) and needs regenerating at github.com/settings/tokens.
- Test the pipeline manually before trusting the schedule: `python -m scripts.main`, then check `new_items.json`/`new_items_detail.json` have matching `id`s.

## Tự động phát hiện chủ đề nổi bật (multi-outlet coverage of one event)

Đây là mục đích cốt lõi của bot. `scripts/main.py:fetch_all_new_items()` quét
toàn bộ báo trong `outlets:`, dedupe theo từng báo qua `filter_new_items()`
(state key là tên báo, không còn theo chủ đề). `build_output()` xuất kết quả
thành 2 danh sách phẳng dùng chung `id`. Việc **cụm nhóm bài viết về cùng một
sự kiện** không nằm trong code — Claude tự làm khi đọc `new_items.json` trong
bước chạy scheduled task (chỉ dẫn chính xác nằm ở
`~/.claude/scheduled-tasks/press-scanning/SKILL.md`, không phải trong repo
này).

## Known gaps

- Verified live (2026-07-17, from a machine with real network egress — this repo's CI/cloud sandbox has none, see top of file) and fixed in `sources.yaml`: 8 of the 21 `outlets:` feed_urls were dead (404, wrong domain, or empty feed). 6 fixed by finding the current URL — VOV → `https://vov.vn/rss.xml`; Báo Nhân Dân → `https://nhandan.vn/rss/home.rss`; VietnamPlus → `https://www.vietnamplus.vn/rss/home.rss`; Báo Điện tử Chính phủ → `https://baochinhphu.vn/home.rss`; Báo Công an Nhân dân → domain moved to `https://cand.vn/rss/home.rss`; Báo Xây dựng → domain moved to `https://baoxaydung.vn/rss/home.rss`. 2 more fixed afterward: SGGP → `https://www.sggp.org.vn/rss/home.rss`; VnEconomy → `https://vneconomy.vn/tin-moi.rss`. **`topics:` now actually scans 17/21 outlets** (up from 9/21 originally) — confirmed by a real run that surfaced 4 genuine matching articles from the newly-fixed outlets.
- **4 outlets remain genuinely broken — not fixable by swapping the URL, so don't spend more time guessing new paths for these** (each is flagged with an inline `# LỖI:` comment in `sources.yaml`):
  - **VietNamNet** — no working RSS found anywhere (checked the site's own `<link rel="alternate">` tags, its documented `/rss/tin-moi-nhat.rss`, its legacy `vnn.vietnamnet.vn/rss/` index, and several path guesses — all 404). RSS appears discontinued site-wide.
  - **Báo Lao Động** — every path (including the real feed URLs) returns a JS cookie-challenge page (`document.cookie=...; window.location.reload()`) instead of content, even with a browser User-Agent. `requests`/`feedparser` can't execute JS, so this outlet is unreachable with the current architecture regardless of URL.
  - **Báo Đầu Tư (baodautu.vn)** — feed *infrastructure* is alive (200 OK, valid RSS/XML envelope) but every category feed, including `/trang-chu.rss` and `/diem-tin-noi-bat.rss`, returns zero `<item>` entries. The site's RSS feature appears abandoned on their end.
  - **Báo Quân đội Nhân dân** — `www.qdnd.vn/rss` 302-redirects to itself in an infinite loop for a stateless request. The real feed (`/rss/cate/tin-tuc-moi-nhat.rss`, confirmed 50 entries) only returns content if a session cookie is primed by visiting `/rss` first with a `requests.Session()` — plain `feedparser.parse(url)` (used in `main.py`) has no cookie handling, so this needs a small code change (session-based fetch just for this outlet) if it's ever wanted. Deferred — user decided not to pursue this for now.
