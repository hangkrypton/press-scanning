# Press Scanning

Bot theo dõi một sự kiện/chủ đề thời sự cùng lúc qua nhiều báo điện tử Việt
Nam, để thấy "bức tranh chung": cùng một sự kiện, báo nào khai thác góc nào —
không phải tự đọc từng trang. Thiết kế để chạy tự động qua **Claude Code
cloud routine**.

Bot này **không có nguồn Gmail/newsletter nào** — toàn bộ dữ liệu đến từ RSS
feed của các báo VN trong `config/sources.yaml`. Nếu bạn muốn bản tin tổng
hợp tin tức ngành AI/báo chí (không phải theo dõi chủ đề), đó là việc của dự
án khác trên máy này (`media-briefing-bot`) — hai bot tách biệt hoàn toàn.

## Vì sao lại chia thành 2 phần (script + Claude)?

- **Script Python** (`scripts/main.py`) quét RSS của tất cả báo trong
  `outlets:`, so khớp với `keywords` của từng chủ đề trong `topics:`, so sánh
  với `state/seen.json` để chỉ giữ lại bài THẬT SỰ mới, rồi ghi ra
  `new_items.json`. Deterministic, rẻ, không cần mô hình AI để "đọc hiểu"
  trang web.
- **Claude** đọc `new_items.json["topics"]` và viết bản tổng hợp — với mỗi
  chủ đề có bài mới, một mục "Toàn cảnh: {tên chủ đề}" ghi rõ báo nào khai
  thác góc nào.

Nhờ vậy, mỗi lần chạy Claude chỉ phải "đọc và viết", không phải "tự mò từng
trang" — tiết kiệm token đáng kể.

## Cấu trúc

```
press-scanning/
├── config/sources.yaml     <- outlets: (danh mục báo VN) + topics: (chủ đề theo dõi)
├── scripts/
│   ├── discover_feed.py    <- tự dò URL feed RSS/Atom từ trang chủ
│   ├── dedup_store.py      <- quản lý "đã đọc tới đâu"
│   └── main.py             <- chạy toàn bộ, xuất new_items.json
├── state/seen.json         <- trạng thái đã đọc (được ghi đè sau mỗi lần chạy)
├── new_items.json          <- output của lần chạy gần nhất (Claude đọc file này)
└── requirements.txt
```

## Thiết lập lần đầu

1. Tạo một GitHub repo mới **public** (bắt buộc — xem lý do ở CLAUDE.md, mục
   "Architecture: split local + cloud"), đẩy toàn bộ thư mục này lên. Dùng tên
   repo riêng cho dự án này (ví dụ `press-scanning`), **không trùng** với
   repo `media-briefing-bot` đã có sẵn trên cùng máy — đó là một bot khác đang
   chạy thật hằng ngày.
2. Cài thư viện để tự kiểm thử trước khi đưa vào routine:
   ```
   pip install -r requirements.txt
   python -m scripts.main
   ```
   Xem log: dòng nào báo "Không tìm được feed" nghĩa là nguồn đó cần bạn tự
   tìm `feed_url` và điền thẳng vào `sources.yaml`. 4 báo hiện đã biết là lỗi
   không sửa được bằng cách đổi URL (VietNamNet, Báo Lao Động, Báo Đầu Tư, Báo
   Quân đội Nhân dân) — xem chi tiết ở CLAUDE.md, mục "Known gaps", không cần
   mất công tra lại các báo này.

## Thiết lập Claude Code routine

1. Vào `code.claude.com/routines` (hoặc gõ `/schedule` trong Claude Code),
   chọn repo vừa tạo, chọn "Remote" (chạy trên cloud, không cần máy bạn mở).
2. **Không cần bật connector Gmail** — bot này không dùng newsletter. **Cần
   bật connector Google Drive** — routine dùng nó để lưu bản tổng hợp mỗi
   ngày.
3. Đặt lịch: hằng ngày, giờ bạn muốn (sau giờ chạy của job local ít nhất
   15-30 phút, để job local kịp push code lên GitHub trước khi routine đọc).
4. Dán prompt sau vào phần "Prompt" của routine:

   ```
   Chạy `python -m scripts.main` trong repo này để quét tin mới theo các chủ
   đề đang theo dõi (kết quả ở new_items.json["topics"]). Với mỗi chủ đề có
   ít nhất 1 bài mới, viết một mục "Toàn cảnh: {tên chủ đề}": với mỗi bài, ghi
   rõ báo nào đăng và góc độ/khía cạnh bài đó khai thác (ví dụ: số liệu, câu
   chuyện con người, phản ứng chính quyền, phân tích chính sách...) — mục
   tiêu là để đọc xong biết ngay các báo đang khai thác khác nhau ở đâu,
   không cần đọc hết từng bài. Không trích dẫn nguyên văn quá 15 từ mỗi
   nguồn. Nếu nhiều báo cùng khai thác một góc giống hệt nhau, nói gộp một
   câu thay vì liệt kê lặp lại từng báo. Nếu một chủ đề không có bài mới, bỏ
   qua chủ đề đó (không cần ghi "không có cập nhật"). Sau khi viết xong,
   commit file new_items.json và state/seen.json đã cập nhật vào repo, rồi
   gửi bản tổng hợp qua kênh bạn chọn (email/OneDrive/...). Cuối cùng, lưu
   bản tổng hợp vào Google Drive: dùng connector Google Drive, tìm thư mục
   tên "Press Scanning" ở My Drive (tạo mới nếu chưa có), tạo một Google Doc
   mới trong thư mục đó với tiêu đề "Toàn cảnh - {ngày hôm nay, định dạng
   YYYY-MM-DD}" chứa toàn bộ nội dung bản tổng hợp vừa viết. Nếu một ngày
   không có chủ đề nào có bài mới, bỏ qua bước lưu Drive (không tạo file
   rỗng).
   ```

5. Lưu routine.

## Theo dõi chủ đề đa nguồn (bức tranh chung nhiều báo)

- **`outlets:`** — danh mục các báo VN dùng chung (hiện có 21 báo, 17 đang
  hoạt động — VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí, CafeF, BBC Tiếng
  Việt, Tiền Phong, VTV, VOV, Nhân Dân, VietnamPlus, Chính phủ, Công an Nhân
  dân, Sài Gòn Giải Phóng, Xây dựng, VnEconomy, Kênh 14; xem CLAUDE.md để
  biết 4 báo còn lỗi). Thêm/bớt báo ở đây — dùng chung cho mọi chủ đề, không
  phải khai báo lại mỗi lần thêm chủ đề mới.
- **`topics:`** — mỗi chủ đề có `id`, `name`, `keywords`, và (tuỳ chọn)
  `outlets:` là danh sách TÊN báo cần quét (phải khớp đúng chính tả với tên
  trong `outlets:` ở trên). **Không khai báo `outlets:` cho chủ đề = mặc định
  quét tất cả báo** trong danh mục.

**Thêm một chủ đề mới:** copy khối mẫu `quy_tap_hai_cot`, đổi `id`, `name`,
`keywords`. Không cần sửa code. Lưu ý:
- `id` là khoá lưu trạng thái dedupe — đặt xong thì đừng đổi, đổi sẽ làm mất
  lịch sử "đã thấy" của chủ đề đó (bot sẽ coi mọi bài cũ là "mới" lại lần đầu).
- `keywords` nên viết vài biến thể (có dấu, đúng cách báo hay dùng) — bot so
  khớp nguyên văn, không tự suy luận đồng nghĩa. Ví dụ với chủ đề khác: nếu
  theo dõi "sáp nhập tỉnh", nên có cả `"sáp nhập tỉnh"`, `"hợp nhất tỉnh"`,
  `"tinh gọn bộ máy"` vì báo có thể dùng từ khác nhau cho cùng sự kiện.
- Với chủ đề chuyên biệt (ví dụ chỉ liên quan kinh tế), nên giới hạn
  `outlets:` của topic đó lại thay vì để mặc định quét cả 21 báo — đỡ tốn thời
  gian quét những báo chắc chắn không đăng (ví dụ Báo Xây dựng khó đăng tin
  quy tập hài cốt liệt sĩ).
- Nếu không biết `feed_url` của một báo mới, chạy thử:
  `python -m scripts.discover_feed https://tenbao.vn` để tự dò.

## Thêm/bớt báo sau này

Chỉ cần sửa `config/sources.yaml` (thêm/bớt một khối trong `outlets:` hoặc
`topics:` theo đúng định dạng có sẵn) và commit — không cần đụng vào code.
Bạn có thể nhờ Claude làm việc này giúp bằng cách nói "thêm báo X vào danh
sách" hoặc "theo dõi thêm chủ đề Y" trong bất kỳ phiên chat nào có quyền truy
cập repo.

## Giới hạn cần biết

- 4/21 báo hiện không lấy được tin (VietNamNet, Báo Lao Động, Báo Đầu Tư, Báo
  Quân đội Nhân dân) — nguyên nhân không phải sai URL mà là RSS đã ngừng
  hoạt động, bị chặn bot, hoặc cần cơ chế phiên đăng nhập phức tạp hơn. Chi
  tiết ở CLAUDE.md, mục "Known gaps".
- Không theo dõi được feed cá nhân trên X/Twitter, LinkedIn, Facebook.
- Một số báo có thể đổi domain hoặc cấu trúc feed theo thời gian (đã gặp với
  Báo Công an Nhân dân, Báo Xây dựng) — nếu một báo đột nhiên không còn ra
  tin, chạy lại `python -m scripts.discover_feed <trang chủ>` để kiểm tra.
