# Thiết kế: Tự động phát hiện chủ đề nổi bật hàng ngày

Ngày: 2026-07-17
Trạng thái: Đã duyệt, chờ lên kế hoạch triển khai

## Bối cảnh

Kiến trúc hiện tại (`CLAUDE.md`, `README.md`) theo dõi các chủ đề **khai báo trước** trong
`config/sources.yaml:topics:` bằng cách so khớp từ khóa. Người dùng muốn thay đổi mục đích
cốt lõi của bot: thay vì theo dõi một sự kiện đã biết trước, bot phải **tự quét và phát hiện**
những chủ đề đang được nhiều báo cùng đưa tin trong ngày — không cần khai báo `topics:` trước.

Kiến trúc hiện tại cũng giả định phải tách local (fetch, có mạng) + cloud routine trên
claude.ai (đọc-only, không có mạng, không ghi được git — xem "Known gaps" trong `CLAUDE.md`).
Trong phiên brainstorming này, task định kỳ đang chạy thực tế lại có quyền mạng thật (đã kiểm
chứng bằng cách fetch trực tiếp 3 feed RSS) — khác giả định cũ. Vì vậy kiến trúc mới sẽ gộp
lại thành một task local duy nhất, bỏ hẳn sự tách biệt local/cloud.

## Quyết định thiết kế (chốt qua brainstorming)

1. **Bỏ hẳn theo dõi theo từ khóa khai báo trước** — không còn khái niệm `topics:` cố định.
2. **Tự động phát hiện chủ đề nổi bật mỗi ngày** bằng Claude đọc và tự cụm nhóm theo hiểu
   ngữ nghĩa (không phải thuật toán so khớp cục bộ) — vì tiêu đề báo VN diễn đạt rất khác
   nhau cho cùng một sự kiện (ví dụ đã biết: "sáp nhập tỉnh" vs "hợp nhất tỉnh").
3. **Ngưỡng "nổi bật": ≥3 báo khác nhau cùng đưa tin về một sự kiện** mới tính là một chủ đề
   của ngày hôm đó.
4. **Không giới hạn số lượng chủ đề hiển thị/ngày** — hiện tất cả chủ đề đạt ngưỡng.
5. **Kiến trúc gộp thành một scheduled task local duy nhất** — bỏ tách local (`run_daily.sh`
   + launchd) / cloud routine (claude.ai) như thiết kế cũ.
6. **Không dùng git cho `state/seen.json`** — chỉ lưu cục bộ trên máy, không auto-commit/push
   hàng ngày (đơn giản hóa, chấp nhận rủi ro mất lịch sử dedupe nếu file bị xóa — xem "Xử lý
   lỗi"). Repo vẫn giữ git cho code/config như bình thường, chỉ riêng state runtime bị loại
   khỏi version control.
7. **Chỉ lưu Google Doc trên Drive** (thư mục "Press Scanning"), không gửi thêm qua kênh nào
   khác (email, v.v.).
8. **Kỹ thuật "2 bước đọc" để tiết kiệm token**: tách 2 file output —
   - `new_items.json` (nhẹ: `id, outlet, title, snippet ~100-150 ký tự, link, published`) —
     Claude đọc file này để cụm nhóm (ước tính ~50-60K token/ngày).
   - `new_items_detail.json` (đầy đủ tóm tắt RSS, đánh chỉ mục theo `id`) — Claude chỉ tra
     cứu (Grep theo `id`) các bài thuộc chủ đề đã chọn khi viết "Toàn cảnh".

   Lý do tách 2 file thay vì Grep field trên 1 file: đảm bảo tiết kiệm token chắc chắn (không
   phụ thuộc việc "nhớ dùng đúng công cụ" mỗi lần chạy).

## Research notes

- Các hệ thống cụm nhóm tin tức quy mô lớn (Newscatcher, NewsBlur, Google News) phân biệt rõ
  **dedup** (loại bỏ bài trùng) và **clustering** (nhóm bài liên quan, vẫn giữ để thấy nhiều
  góc nhìn) — khớp đúng mục tiêu ở đây là clustering.
  [Newscatcher — Articles deduplication](https://www.newscatcherapi.com/docs/v3/documentation/guides-and-concepts/articles-deduplication),
  [NewsBlur — Story clustering](https://blog.newsblur.com/2026/03/18/story-clustering/)
- Cảnh báo quan trọng: các hệ thống production **không cụm nhóm chỉ dựa trên tiêu đề** — dùng
  embedding của toàn bộ nội dung/tóm tắt vì tiêu đề riêng lẻ dễ gây nhầm (bỏ sót khi diễn đạt
  khác hẳn nhau, hoặc nhóm nhầm các tiêu đề chung chung). Đây là lý do quyết định #8 ở trên
  đổi từ "chỉ tiêu đề" (~35-40K token) sang "tiêu đề + đoạn tóm tắt ngắn" (~50-60K token).
  [Hierarchical Level-Wise News Article Clustering via Multilingual Matryoshka Embeddings](https://arxiv.org/pdf/2506.00277)
- Approach kỹ thuật phổ biến ở quy mô lớn dùng cosine similarity + graph community detection
  (thuật toán Leiden) trên embedding — không áp dụng ở đây vì quy mô nhỏ (~450 bài/ngày) khiến
  Claude đọc trực tiếp khả thi hơn và cho hiểu ngữ cảnh/góc khai thác tốt hơn thuần embedding.
  [Clustering news articles — Newscatcher](https://www.newscatcherapi.com/docs/news-api/guides-and-concepts/clustering-news-articles)

## Kiến trúc & luồng dữ liệu

Một scheduled task local duy nhất (task "press-scanning" hiện có), chạy tuần tự mỗi ngày:

1. **Fetch & dedup** — `scripts/main.py` quét RSS toàn bộ 17 báo hoạt động trong `outlets:`,
   lọc bài mới so với `state/seen.json` (dedup theo từng báo, key dạng `outlet::<tên báo>`,
   không còn theo chủ đề). Ghi ra `new_items.json` (nhẹ) + `new_items_detail.json` (đầy đủ),
   cùng chia sẻ `id` để tra cứu chéo. Cập nhật `state/seen.json` cục bộ (không commit git).

2. **Cụm nhóm (bước đọc 1)** — Claude đọc `new_items.json`, tự nhận diện các bài viết về cùng
   một sự kiện theo hiểu ngữ nghĩa, giữ lại nhóm có ≥3 báo khác nhau đưa tin. Không giới hạn
   số nhóm.

3. **Viết tổng hợp (bước đọc 2)** — Với mỗi nhóm được chọn, Grep theo `id` trong
   `new_items_detail.json` để lấy chi tiết, viết mục "Toàn cảnh: {tên chủ đề tự đặt}" — báo
   nào khai thác góc nào, không trích nguyên văn quá 15 từ/nguồn, gộp câu nếu nhiều báo cùng
   góc.

4. **Lưu kết quả** — Có ≥1 chủ đề đạt ngưỡng: lưu 1 Google Doc "Toàn cảnh - YYYY-MM-DD" vào
   thư mục "Press Scanning" trên Drive. Không có chủ đề nào đạt ngưỡng: bỏ qua, không tạo file
   rỗng.

## Thay đổi từng thành phần

- **`config/sources.yaml`** — xóa hẳn `topics:`, chỉ giữ `outlets:`.
- **`scripts/main.py`** — bỏ `matches_keywords()`, `process_topics()`; thêm fetch-toàn-bộ +
  dedup theo outlet; xuất 2 file (`new_items.json`, `new_items_detail.json`) thay vì 1.
- **`scripts/dedup_store.py`** — đổi state key sang `outlet::<tên báo>` (từ
  `topic::<id>::<tên báo>`).
- **`.gitignore`** — thêm `state/seen.json`, `new_items.json`, `new_items_detail.json`.
- **`scripts/run_daily.sh`** — xóa (lỗi thời, không còn kiến trúc tách local/cloud). Người
  dùng tự gỡ LaunchAgent liên quan nếu đã tạo trước đó — Claude không tự đổi cấu hình hệ
  thống.
- **`CLAUDE.md` / `README.md`** — viết lại phần "Architecture: split local + cloud" và "Topic
  tracking", xóa hướng dẫn thiết lập claude.ai routine cũ.
- **`~/.claude/scheduled-tasks/press-scanning/SKILL.md`** — cập nhật mô tả theo đúng luồng 4
  bước ở trên.

## Xử lý lỗi

- Outlet fetch lỗi (feed chết, timeout...) → bỏ qua, log lại, các báo khác tiếp tục bình
  thường (giữ hành vi hiện tại).
- Google Drive connector lỗi lúc lưu Doc → báo lỗi rõ trong log của task, không âm thầm bỏ
  qua.
- `state/seen.json` bị mất/hỏng → chấp nhận coi như chạy lần đầu (mọi bài trong ngày là
  "mới"), không cần cơ chế khôi phục phức tạp (đánh đổi đã chấp nhận khi bỏ git cho state).

## Kiểm thử trước khi đưa vào lịch tự động

1. Chạy tay `python -m scripts.main` — kiểm tra `new_items.json`/`new_items_detail.json` sinh
   đúng cấu trúc, `id` khớp nhau giữa 2 file, `state/seen.json` cập nhật đúng.
2. Chạy thử toàn bộ task 1 lần thủ công để xem bước cụm nhóm có hợp lý không (đúng ngưỡng ≥3
   báo, không gộp nhầm sự kiện không liên quan), và Doc lưu đúng thư mục Drive.
3. Theo dõi vài ngày đầu, tinh chỉnh nếu cụm nhóm bị lệch (quá rộng hoặc quá hẹp).
