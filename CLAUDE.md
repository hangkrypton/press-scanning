# press-scanning

Tự động phát hiện các chủ đề thời sự đang được nhiều báo điện tử Việt Nam cùng đưa tin trong ngày (`config/sources.yaml`: `outlets:`), để thấy "bức tranh chung" — cùng một sự kiện, báo nào khai thác góc nào. Repo: https://github.com/hangkrypton/press-scanning.

This is a **separate project** from `media-briefing-bot` (a different repo/bot on this same machine — daily AI/journalism-industry newsletter digest, no topic tracking) — do not reuse its repo name or log file names for anything in this project.

Không có nguồn Gmail/newsletter nào trong dự án này — toàn bộ dữ liệu đến từ RSS feed của 21 báo trong `outlets:`.

## Architecture: split local (launchd) + cloud routine

**Lịch sử:** trước đây từng chạy toàn bộ trong **một Claude Code scheduled task
local**. Cơ chế đó chỉ chạy nếu app Claude Code đang mở đúng phút hẹn; nếu máy
ngủ / app đóng thì task "chốt sổ" nhưng **không thực thi và không chạy bù** →
nhiều sáng không ra bản tin (19–20/7/2026). Vì vậy đã **đổi ngược lại** sang
đúng mô hình `media-briefing-bot` — dùng launchd (đáng tin cả khi máy ngủ, tự
chạy bù khi máy thức) + một routine cloud. Đánh đổi: phải commit file JSON
runtime lên repo public và có routine cloud trở lại, để lấy độ tin cậy.

Pipeline tách 2 runtime (giống media-briefing, vì cùng ràng buộc sandbox cloud
— xem CLAUDE.md của media-briefing-bot):

- **LOCAL — `scripts/run_daily.sh` qua launchd**
  (`~/Library/LaunchAgents/com.hangkrypton.press-scanning.plist`, **06:00**
  Asia/Saigon). Chạy `python -m scripts.main`: quét RSS toàn bộ `outlets:`,
  dedup theo từng báo so với `state/seen.json`, xuất `new_items.json` (bản nhẹ)
  + `new_items_detail.json` (bản đầy đủ, đánh chỉ mục theo `id`), rồi
  **commit + push** 2 file này lên GitHub. Đây là phần **duy nhất** chạm
  internet / ghi git. Log: `~/Library/Logs/press-scanning.log` / `.err.log`.
- **CLOUD — routine "Press Scanning - Toàn cảnh"** (claude.ai routines, cron
  `30 23 * * *` UTC = **06:30** Asia/Saigon, sau local 30 phút). **Đọc**
  `new_items.json` + `new_items_detail.json` từ repo (cloud sandbox chỉ vào
  được `github.com`, không tự quét RSS được), tự cụm nhóm bài về cùng một sự
  kiện theo ngữ nghĩa (giữ nhóm **≥3 báo khác nhau**), viết mục "Toàn cảnh:
  {tên chủ đề}" (Diễn biến/bối cảnh + Góc khai thác + link tên báo), **lưu 1
  Google Doc "Toàn cảnh - YYYY-MM-DD"** vào thư mục Drive "Press Scanning"
  (**cần bật connector Google Drive trên routine**), và trình bày toàn bộ bản
  tin trong kết quả routine để đọc trong Claude App. Quản lý tại
  claude.ai/code/routines — sửa prompt ở đó, không phải trong repo này.

**Ràng buộc thời điểm:** routine 06:30 đọc dữ liệu mà local đã push. Nếu sáng
đó máy ngủ và mở sau ~06:28, local chưa kịp push → routine phải **kiểm tra độ
mới của `new_items.json`; nếu không phải dữ liệu hôm nay thì báo "chưa có dữ
liệu mới" và dừng**, KHÔNG tạo bản tin cũ. Muốn chắc chắn đúng 06:30 mỗi ngày
thì cần `pmset` tự đánh thức máy (hiện chưa bật theo lựa chọn của người dùng).

`new_items.json` + `new_items_detail.json` **được commit** (cloud cần đọc).
`state/seen.json` **không** commit (state dedup cục bộ; mất chỉ khiến lần chạy
kế tiếp coi mọi bài là "mới" một lần). Repo **phải giữ public** để cloud đọc
được.

## Local environment gotchas

- System Python is 3.9.6 (`/usr/bin/python3`) — **no `X | None` union type syntax**; add `from __future__ import annotations` at the top of any new module using it (already done throughout `scripts/`).
- `git` on this machine uses `credential.helper=osxkeychain` with a cached PAT, so manual `git push` works without an auth prompt. If a push starts failing with an auth prompt, the PAT likely expired (fine-grained tokens were created with a short expiry) and needs regenerating at github.com/settings/tokens.
- Test the pipeline manually before trusting the schedule: `python -m scripts.main`, then check `new_items.json`/`new_items_detail.json` have matching `id`s.

## Tự động phát hiện chủ đề nổi bật (multi-outlet coverage of one event)

Đây là mục đích cốt lõi của bot. `scripts/main.py:fetch_all_new_items()` quét
toàn bộ báo trong `outlets:`, dedupe theo từng báo qua `filter_new_items()`
(state key là tên báo, không còn theo chủ đề). `build_output()` xuất kết quả
thành 2 danh sách phẳng dùng chung `id`. Việc **cụm nhóm bài viết về cùng một
sự kiện** không nằm trong code — Claude tự làm khi routine cloud đọc
`new_items.json`. **Chỉ dẫn chính xác nằm trong prompt của routine cloud**
(quản lý tại claude.ai/code/routines), không phải trong repo này.
`~/.claude/scheduled-tasks/press-scanning/SKILL.md` là bản chỉ dẫn cũ của
scheduled task đã ngừng dùng — giữ lại làm tham chiếu nội dung, không còn được
chạy.

## Known gaps

- Verified live (2026-07-17, from a machine with real network egress — this repo's CI/cloud sandbox has none, see top of file) and fixed in `sources.yaml`: 8 of the 21 `outlets:` feed_urls were dead (404, wrong domain, or empty feed). 6 fixed by finding the current URL — VOV → `https://vov.vn/rss.xml`; Báo Nhân Dân → `https://nhandan.vn/rss/home.rss`; VietnamPlus → `https://www.vietnamplus.vn/rss/home.rss`; Báo Điện tử Chính phủ → `https://baochinhphu.vn/home.rss`; Báo Công an Nhân dân → domain moved to `https://cand.vn/rss/home.rss`; Báo Xây dựng → domain moved to `https://baoxaydung.vn/rss/home.rss`. 2 more fixed afterward: SGGP → `https://www.sggp.org.vn/rss/home.rss`; VnEconomy → `https://vneconomy.vn/tin-moi.rss`. **the pipeline now actually scans 17/21 outlets** (up from 9/21 originally) — confirmed by a real run that surfaced genuine articles from the newly-fixed outlets.
- **4 outlets remain genuinely broken — not fixable by swapping the URL, so don't spend more time guessing new paths for these** (each is flagged with an inline `# LỖI:` comment in `sources.yaml`):
  - **VietNamNet** — no working RSS found anywhere (checked the site's own `<link rel="alternate">` tags, its documented `/rss/tin-moi-nhat.rss`, its legacy `vnn.vietnamnet.vn/rss/` index, and several path guesses — all 404). RSS appears discontinued site-wide.
  - **Báo Lao Động** — every path (including the real feed URLs) returns a JS cookie-challenge page (`document.cookie=...; window.location.reload()`) instead of content, even with a browser User-Agent. `requests`/`feedparser` can't execute JS, so this outlet is unreachable with the current architecture regardless of URL.
  - **Báo Đầu Tư (baodautu.vn)** — feed *infrastructure* is alive (200 OK, valid RSS/XML envelope) but every category feed, including `/trang-chu.rss` and `/diem-tin-noi-bat.rss`, returns zero `<item>` entries. The site's RSS feature appears abandoned on their end.
  - **Báo Quân đội Nhân dân** — `www.qdnd.vn/rss` 302-redirects to itself in an infinite loop for a stateless request. The real feed (`/rss/cate/tin-tuc-moi-nhat.rss`, confirmed 50 entries) only returns content if a session cookie is primed by visiting `/rss` first with a `requests.Session()` — plain `feedparser.parse(url)` (used in `main.py`) has no cookie handling, so this needs a small code change (session-based fetch just for this outlet) if it's ever wanted. Deferred — user decided not to pursue this for now.
