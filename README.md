# Press Scanning

Bot tự động phát hiện các chủ đề thời sự đang được nhiều báo điện tử Việt Nam
cùng đưa tin trong ngày, để thấy "bức tranh chung": cùng một sự kiện, báo nào
khai thác góc nào — không phải tự đọc từng trang. Chạy tự động qua **một
Claude Code scheduled task local duy nhất**.

Bot này **không có nguồn Gmail/newsletter nào** — toàn bộ dữ liệu đến từ RSS
feed của các báo VN trong `config/sources.yaml`. Nếu bạn muốn bản tin tổng hợp
tin tức ngành AI/báo chí (không phải phát hiện chủ đề), đó là việc của dự án
khác trên máy này (`media-briefing-bot`) — hai bot tách biệt hoàn toàn.

## Cấu trúc

```
press-scanning/
├── config/sources.yaml     <- outlets: (danh mục báo điện tử VN dùng chung)
├── scripts/
│   ├── discover_feed.py    <- tự dò URL feed RSS/Atom từ trang chủ
│   ├── dedup_store.py      <- quản lý "đã đọc tới đâu"
│   └── main.py             <- chạy toàn bộ, xuất new_items.json
├── state/seen.json         <- trạng thái đã đọc (được ghi đè sau mỗi lần chạy)
├── new_items.json          <- bản nhẹ (id/outlet/title/snippet/link) để Claude cụm nhóm
├── new_items_detail.json   <- bản đầy đủ, đánh chỉ mục theo id, để Claude tra cứu chi tiết
└── requirements.txt
```

## Thiết lập lần đầu

1. Cài thư viện và kiểm thử trước khi đưa vào lịch tự động:
   ```
   pip install -r requirements.txt
   python -m scripts.main
   ```
   Xem log: dòng nào báo "Không tìm được feed" nghĩa là nguồn đó cần bạn tự
   tìm `feed_url` và điền thẳng vào `sources.yaml`. 4 báo hiện đã biết là lỗi
   không sửa được bằng cách đổi URL — xem CLAUDE.md, mục "Known gaps".
2. Chạy `python -m pytest` để xác nhận bộ test đi kèm vẫn pass.
3. Task định kỳ "press-scanning" (Claude Code scheduled task, cấu hình tại
   `~/.claude/scheduled-tasks/press-scanning/SKILL.md`) chạy toàn bộ pipeline
   mỗi ngày: fetch RSS → cụm nhóm chủ đề (≥3 báo) → viết "Toàn cảnh" → lưu
   Google Doc. **Cần bật connector Google Drive** trên task này — không cần
   Gmail.
4. Chạy thử task thủ công một lần trước khi tin vào lịch tự động, để kiểm tra
   bước cụm nhóm có hợp lý và Google Doc lưu đúng thư mục "Press Scanning"
   trên Drive.

## Tự động phát hiện chủ đề nổi bật (bức tranh chung nhiều báo)

- **`outlets:`** — danh mục các báo VN dùng chung (hiện có 21 báo, 17 đang
  hoạt động — xem CLAUDE.md để biết 4 báo còn lỗi). Đây là thành phần cấu hình
  **duy nhất** còn lại trong `sources.yaml` — không còn khai báo `topics:`.
- Mỗi ngày, Claude tự đọc toàn bộ bài mới từ 17 báo, tự nhận diện các bài viết
  đang nói về cùng một sự kiện (dựa trên hiểu nội dung, không so khớp từ khóa
  cứng), và chỉ giữ lại các nhóm có **từ 3 báo khác nhau trở lên** cùng đưa
  tin làm "chủ đề nổi bật" của ngày. Không cần bạn khai báo chủ đề trước.
- Nếu không biết `feed_url` của một báo mới, chạy thử:
  `python -m scripts.discover_feed https://tenbao.vn` để tự dò.

## Thêm/bớt báo sau này

Chỉ cần sửa `config/sources.yaml` (thêm/bớt một khối trong `outlets:` theo
đúng định dạng có sẵn) và commit — không cần đụng vào code. Bạn có thể nhờ
Claude làm việc này giúp bằng cách nói "thêm báo X vào danh sách" trong bất kỳ
phiên chat nào có quyền truy cập repo.

## Giới hạn cần biết

- 4/21 báo hiện không lấy được tin (VietNamNet, Báo Lao Động, Báo Đầu Tư, Báo
  Quân đội Nhân dân) — nguyên nhân không phải sai URL mà là RSS đã ngừng
  hoạt động, bị chặn bot, hoặc cần cơ chế phiên đăng nhập phức tạp hơn. Chi
  tiết ở CLAUDE.md, mục "Known gaps".
- Không theo dõi được feed cá nhân trên X/Twitter, LinkedIn, Facebook.
- Một số báo có thể đổi domain hoặc cấu trúc feed theo thời gian (đã gặp với
  Báo Công an Nhân dân, Báo Xây dựng) — nếu một báo đột nhiên không còn ra
  tin, chạy lại `python -m scripts.discover_feed <trang chủ>` để kiểm tra.
