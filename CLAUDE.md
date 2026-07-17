# press-scanning

Theo dõi một sự kiện/chủ đề thời sự cùng lúc qua nhiều báo điện tử Việt Nam (`config/sources.yaml`: `outlets:` + `topics:`), để thấy "bức tranh chung" — cùng một sự kiện, báo nào khai thác góc nào. Repo: https://github.com/hangkrypton/press-scanning (phải luôn **public** — xem lý do bên dưới).

This is a **separate project** from `media-briefing-bot` (a different repo/bot on this same machine — daily AI/journalism-industry newsletter digest, no topic tracking) — do not reuse its repo name, LaunchAgent label, or log file names for anything in this project.

Không có nguồn Gmail/newsletter nào trong dự án này — toàn bộ dữ liệu đến từ RSS feed của 21 báo trong `outlets:`. Cloud routine vì vậy không cần bật connector Gmail.

## Architecture: split local + cloud

The pipeline is split across two runtimes because the Claude Code cloud sandbox (CCR) has two hard limits discovered by trial and error (on `media-briefing-bot`, same platform):

1. **Network egress is blocked for nearly all external domains** — even via the WebFetch tool, even Wikipedia as a control. Only `github.com` worked. No self-serve setting was found anywhere in claude.ai to allow-list domains; treat as a hard platform limit, not a misconfiguration.
2. **The GitHub connection available to CCR routines is read-only** — cloning/pulling a public repo works, but `git push` and GitHub MCP write tools (`push_files`, `create_or_update_file`) all return `403 Resource not accessible by integration`. No GitHub App with write scope was ever found installed for this account, despite reconnecting/revoking the OAuth connection multiple times.

Consequence: the repo must stay **public** (cloud can only read it, and only if public), and the split is:

- **Local (`scripts/run_daily.sh`, intended to run via macOS launchd at a dedicated plist, e.g. `~/Library/LaunchAgents/com.hangkrypton.press-scanning.plist` — use a label distinct from `com.hangkrypton.media-briefing-bot`, which already exists and runs a different project)**: runs `python -m scripts.main` — fetches RSS feeds for all `outlets:`, matches each topic's `keywords`, dedupes against `state/seen.json`, writes `new_items.json`, commits + pushes both files. This is the only part of the system that touches the open internet or writes to git.
- **Cloud routine (name TBD, e.g. "Press Scanning - Daily", claude.ai routines, cron TBD — pick a time after the local job's schedule so it has time to push)**: reads `new_items.json["topics"]` (no fetching, no git writes, **no Gmail connector needed**), and for each topic with new items writes a "Toàn cảnh: {tên chủ đề}" section — which outlet covered it and from what angle, then saves it as a Google Doc (one per day, titled "Toàn cảnh - YYYY-MM-DD") in a "Press Scanning" folder on Google Drive via the Google Drive connector — **this connector must be enabled on the routine**. See README.md for the exact routine prompt.

**Status: not yet deployed.** As of this writing, `press-scanning` has no git repo/remote, no LaunchAgent, and no cloud routine configured — the above describes the intended architecture, not something already running. See README.md's "Thiết lập lần đầu" for setup steps once you're ready to go live, including picking the actual daily run time.

Any future change that needs to fetch external content or commit to git from the cloud side will hit the same wall — do that work in `scripts/run_daily.sh` instead and have the cloud routine only read + use MCP connectors.

## Local environment gotchas

- System Python is 3.9.6 (`/usr/bin/python3`) — **no `X | None` union type syntax**; add `from __future__ import annotations` at the top of any new module using it (already done throughout `scripts/`).
- `git` on this machine uses `credential.helper=osxkeychain` with a cached PAT — non-interactive `git push` from launchd works as-is. If pushes start failing with an auth prompt, the PAT likely expired (fine-grained tokens were created with a short expiry) and needs regenerating at github.com/settings/tokens.
- Test the local job manually before trusting the schedule: `./scripts/run_daily.sh`. Once a LaunchAgent exists for this project, point its `StandardOutPath`/`StandardErrorPath` at `~/Library/Logs/press-scanning.log` / `.err.log` (not the `media-briefing-bot` log files, which belong to the other project).

## Topic tracking (multi-outlet coverage of one event)

This is the entire purpose of the bot, not an add-on. `scripts/main.py:process_topics()` does the name→feed_url lookup against `outlets:`, calls `fetch_outlet_items()` per outlet, filters by `matches_keywords()` (substring, case-insensitive, Unicode-NFC-normalized — handles outlets serving NFD-composed diacritics), then dedupes per topic via `filter_new_items()` using state keys `topic::<id>::<outlet name>`. Output goes into `new_items.json["topics"][topic_id]` as `{name, items: [...]}`.

## Known gaps

- Verified live (2026-07-17, from a machine with real network egress — this repo's CI/cloud sandbox has none, see top of file) and fixed in `sources.yaml`: 8 of the 21 `outlets:` feed_urls were dead (404, wrong domain, or empty feed). 6 fixed by finding the current URL — VOV → `https://vov.vn/rss.xml`; Báo Nhân Dân → `https://nhandan.vn/rss/home.rss`; VietnamPlus → `https://www.vietnamplus.vn/rss/home.rss`; Báo Điện tử Chính phủ → `https://baochinhphu.vn/home.rss`; Báo Công an Nhân dân → domain moved to `https://cand.vn/rss/home.rss`; Báo Xây dựng → domain moved to `https://baoxaydung.vn/rss/home.rss`. 2 more fixed afterward: SGGP → `https://www.sggp.org.vn/rss/home.rss`; VnEconomy → `https://vneconomy.vn/tin-moi.rss`. **`topics:` now actually scans 17/21 outlets** (up from 9/21 originally) — confirmed by a real run that surfaced 4 genuine matching articles from the newly-fixed outlets.
- **4 outlets remain genuinely broken — not fixable by swapping the URL, so don't spend more time guessing new paths for these** (each is flagged with an inline `# LỖI:` comment in `sources.yaml`):
  - **VietNamNet** — no working RSS found anywhere (checked the site's own `<link rel="alternate">` tags, its documented `/rss/tin-moi-nhat.rss`, its legacy `vnn.vietnamnet.vn/rss/` index, and several path guesses — all 404). RSS appears discontinued site-wide.
  - **Báo Lao Động** — every path (including the real feed URLs) returns a JS cookie-challenge page (`document.cookie=...; window.location.reload()`) instead of content, even with a browser User-Agent. `requests`/`feedparser` can't execute JS, so this outlet is unreachable with the current architecture regardless of URL.
  - **Báo Đầu Tư (baodautu.vn)** — feed *infrastructure* is alive (200 OK, valid RSS/XML envelope) but every category feed, including `/trang-chu.rss` and `/diem-tin-noi-bat.rss`, returns zero `<item>` entries. The site's RSS feature appears abandoned on their end.
  - **Báo Quân đội Nhân dân** — `www.qdnd.vn/rss` 302-redirects to itself in an infinite loop for a stateless request. The real feed (`/rss/cate/tin-tuc-moi-nhat.rss`, confirmed 50 entries) only returns content if a session cookie is primed by visiting `/rss` first with a `requests.Session()` — plain `feedparser.parse(url)` (used in `main.py`) has no cookie handling, so this needs a small code change (session-based fetch just for this outlet) if it's ever wanted. Deferred — user decided not to pursue this for now.
