# Tự động phát hiện chủ đề nổi bật hàng ngày Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superjawn:subagent-driven-development (recommended) or superjawn:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay thế cơ chế theo dõi chủ đề cố định theo từ khóa bằng tự động phát hiện chủ đề nổi bật mỗi ngày (≥3 báo cùng đưa tin), gộp kiến trúc local+cloud thành một scheduled task local duy nhất.

**Architecture:** `scripts/main.py` quét toàn bộ RSS các báo trong `outlets:`, dedupe theo từng báo (không còn theo chủ đề), xuất 2 file (`new_items.json` nhẹ + `new_items_detail.json` đầy đủ). Claude (trong chính phiên scheduled task) đọc file nhẹ để tự cụm nhóm sự kiện theo hiểu ngữ nghĩa, tra cứu chi tiết cho các nhóm ≥3 báo, viết "Toàn cảnh" rồi lưu Google Doc. Không còn git commit tự động cho dữ liệu runtime.

**Tech Stack:** Python 3.9.6, feedparser, PyYAML, pytest (mới thêm).

Xem spec đầy đủ tại [docs/superpowers/specs/2026-07-17-auto-topic-detection-design.md](../specs/2026-07-17-auto-topic-detection-design.md).

---

### Task 1: Thêm pytest + viết `build_output()` (TDD)

**Files:**
- Modify: `requirements.txt`
- Modify: `scripts/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Thêm pytest vào requirements.txt**

Thêm dòng vào cuối `requirements.txt`:

```
pytest>=7.4.0
```

Cài đặt:

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Viết test thất bại cho `build_output()`**

Tạo file `tests/test_main.py`:

```python
from scripts.main import build_output


def test_build_output_splits_index_and_detail_sharing_id():
    new_items_by_outlet = {
        "VnExpress": [
            {
                "id": "https://vnexpress.net/bai-1",
                "title": "Tiêu đề bài 1",
                "link": "https://vnexpress.net/bai-1",
                "published": "2026-07-17",
                "summary_raw": "Tóm tắt đầy đủ của bài viết số 1.",
            }
        ]
    }

    index_items, detail_items = build_output(new_items_by_outlet)

    assert len(index_items) == 1
    assert len(detail_items) == 1
    assert index_items[0]["id"] == detail_items[0]["id"] == "https://vnexpress.net/bai-1"
    assert index_items[0]["outlet"] == "VnExpress"
    assert index_items[0]["title"] == "Tiêu đề bài 1"
    assert "summary_raw" not in index_items[0]
    assert "snippet" not in detail_items[0]
    assert detail_items[0]["summary"] == "Tóm tắt đầy đủ của bài viết số 1."


def test_build_output_truncates_snippet_to_150_chars():
    new_items_by_outlet = {
        "VnExpress": [
            {
                "id": "id-1",
                "title": "Tiêu đề",
                "link": "https://example.com/1",
                "published": "2026-07-17",
                "summary_raw": "A" * 300,
            }
        ]
    }

    index_items, _ = build_output(new_items_by_outlet)

    assert len(index_items[0]["snippet"]) == 150


def test_build_output_empty_input_returns_empty_lists():
    assert build_output({}) == ([], [])
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_output' from 'scripts.main'`

- [ ] **Step 4: Viết `build_output()` trong scripts/main.py**

Thêm vào `scripts/main.py` (cạnh các hằng số đầu file, sau `MAX_ITEMS_PER_SOURCE`):

```python
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
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt scripts/main.py tests/test_main.py
git commit -m "Add build_output() to split fetched items into index + detail files"
```

---

### Task 2: Viết `fetch_all_new_items()` thay thế `process_topics()` (TDD)

**Files:**
- Modify: `scripts/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_main.py`:

```python
import scripts.main as main_module
from scripts.main import fetch_all_new_items


def test_fetch_all_new_items_dedupes_per_outlet_not_per_topic(monkeypatch):
    def fake_fetch_outlet_items(source):
        return [
            {"id": "a1", "title": "Bài A", "link": "https://x.vn/a1", "published": "", "summary_raw": "tóm tắt A"},
            {"id": "a2", "title": "Bài B", "link": "https://x.vn/a2", "published": "", "summary_raw": "tóm tắt B"},
        ]

    monkeypatch.setattr(main_module, "fetch_outlet_items", fake_fetch_outlet_items)

    outlets = [{"name": "Báo X", "feed_url": "https://x.vn/rss"}]
    state = {"Báo X": ["a1"]}  # a1 đã thấy từ trước

    result = fetch_all_new_items(outlets, state)

    assert [item["id"] for item in result["Báo X"]] == ["a2"]
    assert state["Báo X"] == ["a1", "a2"]
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_all_new_items' from 'scripts.main'`

- [ ] **Step 3: Viết `fetch_all_new_items()` trong scripts/main.py**

Thêm vào `scripts/main.py`, ngay sau `fetch_outlet_items()`:

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/main.py tests/test_main.py
git commit -m "Add fetch_all_new_items() with per-outlet dedup, replacing topic-based fetch"
```

---

### Task 3: Xóa code theo chủ đề cũ, viết lại `main()`, xuất 2 file output

**Files:**
- Modify: `scripts/main.py`

- [ ] **Step 1: Xóa các hàm/import không còn dùng**

Trong `scripts/main.py`, xóa:
- Import `unicodedata` (chỉ dùng trong `_normalize`/`matches_keywords`, sắp xóa)
- Hàm `_normalize()`
- Hàm `matches_keywords()`
- Hàm `process_topics()`

Trong `load_config()`, đổi:

```python
def load_config() -> dict:
    raw = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    return {
        "outlets": raw.get("outlets", []),
        "topics": raw.get("topics", []),
    }
```

thành:

```python
def load_config() -> dict:
    raw = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    return {"outlets": raw.get("outlets", [])}
```

- [ ] **Step 2: Đổi tên hằng số output path, thêm path cho file detail**

Đổi:

```python
OUTPUT_PATH = ROOT / "new_items.json"
```

thành:

```python
INDEX_OUTPUT_PATH = ROOT / "new_items.json"
DETAIL_OUTPUT_PATH = ROOT / "new_items_detail.json"
```

- [ ] **Step 3: Viết lại `main()`**

Thay toàn bộ hàm `main()` hiện tại bằng:

```python
def main():
    config = load_config()
    state = load_state()

    new_items_by_outlet = fetch_all_new_items(config["outlets"], state)
    index_items, detail_items = build_output(new_items_by_outlet)

    save_state(state)
    INDEX_OUTPUT_PATH.write_text(json.dumps(index_items, ensure_ascii=False, indent=2), encoding="utf-8")
    DETAIL_OUTPUT_PATH.write_text(json.dumps(detail_items, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nĐã ghi {len(index_items)} bài mới vào {INDEX_OUTPUT_PATH.name} và {DETAIL_OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy toàn bộ test suite, xác nhận vẫn pass**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (4 passed) — Task 1-2 không bị phá vỡ

- [ ] **Step 5: Chạy thử thủ công với mạng thật**

Run: `python -m scripts.main`

Kiểm tra file sinh ra hợp lệ:

```bash
python3 -c "
import json
index = json.load(open('new_items.json'))
detail = json.load(open('new_items_detail.json'))
print('index items:', len(index))
print('detail items:', len(detail))
assert {i['id'] for i in index} == {d['id'] for d in detail}, 'id không khớp giữa 2 file'
print('OK — id khớp nhau giữa 2 file')
"
```

Expected: chạy không lỗi, in ra số lượng bài + "OK — id khớp nhau giữa 2 file"

- [ ] **Step 6: Commit**

```bash
git add scripts/main.py
git commit -m "Rewrite main() to fetch all outlets and write index + detail files"
```

---

### Task 4: Xóa `topics:` khỏi config/sources.yaml

**Files:**
- Modify: `config/sources.yaml`

- [ ] **Step 1: Viết lại phần comment đầu file**

Thay toàn bộ khối comment từ dòng 1 đến dòng 29 (từ `# config/sources.yaml` đến trước `outlets:`) bằng:

```yaml
# config/sources.yaml
#
# Danh mục báo điện tử Việt Nam dùng để tự động phát hiện các chủ đề thời sự
# đang được nhiều báo cùng đưa tin trong ngày ("bức tranh chung"). Không khai
# báo chủ đề trước — việc cụm nhóm sự kiện do Claude tự làm khi đọc
# new_items.json trong scheduled task (xem
# ~/.claude/scheduled-tasks/press-scanning/SKILL.md).
#
# outlets: — danh mục báo VN dùng chung.
#   name      : tên hiển thị
#   feed_url  : URL feed RSS/Atom. Nếu không biết, chạy thử:
#               `python -m scripts.discover_feed https://tenbao.vn` để tự dò.
```

- [ ] **Step 2: Xóa khối `topics:`**

Xóa toàn bộ đoạn cuối file (dòng `topics:` và khối `quy_tap_hai_cot` bên dưới nó):

```yaml
topics:

- id: quy_tap_hai_cot
  name: "Chiến dịch 500 ngày quy tập hài cốt liệt sĩ"
  keywords:
    - "quy tập hài cốt"
    - "hài cốt liệt sĩ"
    - "500 ngày đêm"
    - "tìm kiếm, quy tập"
```

Phần `outlets:` (danh sách 21 báo) giữ nguyên, không đổi.

- [ ] **Step 3: Xác nhận script vẫn chạy đúng**

Run: `python -m scripts.main`
Expected: chạy không lỗi (giống Task 3 Step 5)

- [ ] **Step 4: Commit**

```bash
git add config/sources.yaml
git commit -m "Remove topics: from sources.yaml — topic detection is now automatic"
```

---

### Task 5: Dọn dẹp state runtime — .gitignore, reset state, xóa run_daily.sh

**Files:**
- Modify: `.gitignore`
- Modify: `state/seen.json`
- Delete: `scripts/run_daily.sh`

- [ ] **Step 1: Thêm dữ liệu runtime vào .gitignore**

Thêm vào cuối `.gitignore`:

```
state/seen.json
new_items.json
new_items_detail.json
```

- [ ] **Step 2: Bỏ theo dõi git các file đã commit trước đây**

`new_items.json` và `state/seen.json` hiện đang được git track từ commit trước (theo kiến trúc cũ). Bỏ theo dõi (giữ file trên đĩa):

```bash
git rm --cached new_items.json state/seen.json
```

- [ ] **Step 3: Reset state/seen.json về rỗng**

State cũ dùng key dạng `topic::quy_tap_hai_cot::<tên báo>` — không còn khớp với key mới (`<tên báo>` trực tiếp) nên là dữ liệu chết. Ghi đè `state/seen.json`:

```json
{}
```

- [ ] **Step 4: Xóa scripts/run_daily.sh**

File này chạy qua launchd để fetch + commit + push — không còn cần thiết vì đã gộp thành một scheduled task local duy nhất.

```bash
git rm scripts/run_daily.sh
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore state/seen.json
git commit -m "Stop tracking runtime state in git; remove obsolete run_daily.sh"
```

**Lưu ý cho người dùng (không phải bước tự động):** nếu đã tạo LaunchAgent `~/Library/LaunchAgents/com.hangkrypton.press-scanning.plist` trỏ tới `run_daily.sh`, tự gỡ nó thủ công (`launchctl unload` + xóa file plist) — plan này không tự sửa cấu hình hệ thống.

---

### Task 6: Cập nhật CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Thay dòng mở đầu và phần "Architecture"**

Thay:

```markdown
Theo dõi một sự kiện/chủ đề thời sự cùng lúc qua nhiều báo điện tử Việt Nam (`config/sources.yaml`: `outlets:` + `topics:`), để thấy "bức tranh chung" — cùng một sự kiện, báo nào khai thác góc nào. Repo: https://github.com/hangkrypton/press-scanning (phải luôn **public** — xem lý do bên dưới).
```

thành:

```markdown
Tự động phát hiện các chủ đề thời sự đang được nhiều báo điện tử Việt Nam cùng đưa tin trong ngày (`config/sources.yaml`: `outlets:`), để thấy "bức tranh chung" — cùng một sự kiện, báo nào khai thác góc nào. Repo: https://github.com/hangkrypton/press-scanning.
```

Thay toàn bộ section `## Architecture: split local + cloud` (từ tiêu đề đến hết đoạn "Any future change that needs to fetch external content...") bằng:

```markdown
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
```

- [ ] **Step 2: Cập nhật "Local environment gotchas"**

Thay dòng:

```markdown
- Test the local job manually before trusting the schedule: `./scripts/run_daily.sh`. Once a LaunchAgent exists for this project, point its `StandardOutPath`/`StandardErrorPath` at `~/Library/Logs/press-scanning.log` / `.err.log` (not the `media-briefing-bot` log files, which belong to the other project).
```

thành:

```markdown
- Test the pipeline manually before trusting the schedule: `python -m scripts.main`, then check `new_items.json`/`new_items_detail.json` have matching `id`s.
```

- [ ] **Step 3: Thay section "Topic tracking"**

Thay toàn bộ section `## Topic tracking (multi-outlet coverage of one event)` bằng:

```markdown
## Tự động phát hiện chủ đề nổi bật (multi-outlet coverage of one event)

Đây là mục đích cốt lõi của bot. `scripts/main.py:fetch_all_new_items()` quét
toàn bộ báo trong `outlets:`, dedupe theo từng báo qua `filter_new_items()`
(state key là tên báo, không còn theo chủ đề). `build_output()` xuất kết quả
thành 2 danh sách phẳng dùng chung `id`. Việc **cụm nhóm bài viết về cùng một
sự kiện** không nằm trong code — Claude tự làm khi đọc `new_items.json` trong
bước chạy scheduled task (chỉ dẫn chính xác nằm ở
`~/.claude/scheduled-tasks/press-scanning/SKILL.md`, không phải trong repo
này).
```

- [ ] **Step 4: Giữ nguyên "Known gaps"**

Không sửa gì — 4 báo lỗi (VietNamNet, Báo Lao Động, Báo Đầu Tư, Báo Quân đội Nhân dân) vẫn đúng, không liên quan đến thay đổi kiến trúc lần này.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "Rewrite CLAUDE.md for single-task architecture and auto topic detection"
```

---

### Task 7: Cập nhật README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Thay đoạn mở đầu**

Thay 2 đoạn đầu (dòng 1-11, từ "Bot theo dõi..." đến hết đoạn "hai bot tách biệt hoàn toàn.") bằng:

```markdown
Bot tự động phát hiện các chủ đề thời sự đang được nhiều báo điện tử Việt Nam
cùng đưa tin trong ngày, để thấy "bức tranh chung": cùng một sự kiện, báo nào
khai thác góc nào — không phải tự đọc từng trang. Chạy tự động qua **một
Claude Code scheduled task local duy nhất**.

Bot này **không có nguồn Gmail/newsletter nào** — toàn bộ dữ liệu đến từ RSS
feed của các báo VN trong `config/sources.yaml`. Nếu bạn muốn bản tin tổng hợp
tin tức ngành AI/báo chí (không phải phát hiện chủ đề), đó là việc của dự án
khác trên máy này (`media-briefing-bot`) — hai bot tách biệt hoàn toàn.
```

- [ ] **Step 2: Xóa section "Vì sao lại chia thành 2 phần"**

Xóa toàn bộ section `## Vì sao lại chia thành 2 phần (script + Claude)?` — không còn áp dụng vì đã gộp thành một task.

- [ ] **Step 3: Cập nhật "Cấu trúc"**

Thay:

```markdown
├── new_items.json          <- output của lần chạy gần nhất (Claude đọc file này)
```

thành:

```markdown
├── new_items.json          <- bản nhẹ (id/outlet/title/snippet/link) để Claude cụm nhóm
├── new_items_detail.json   <- bản đầy đủ, đánh chỉ mục theo id, để Claude tra cứu chi tiết
```

- [ ] **Step 4: Viết lại "Thiết lập lần đầu" và "Thiết lập Claude Code routine"**

Thay toàn bộ 2 section này (`## Thiết lập lần đầu` và `## Thiết lập Claude Code routine`, bao gồm cả prompt mẫu cũ) bằng:

```markdown
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
```

- [ ] **Step 5: Viết lại "Theo dõi chủ đề đa nguồn"**

Thay toàn bộ section `## Theo dõi chủ đề đa nguồn (bức tranh chung nhiều báo)` (bao gồm cả phần "Thêm một chủ đề mới") bằng:

```markdown
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
```

- [ ] **Step 6: Giữ nguyên "Thêm/bớt báo sau này" và "Giới hạn cần biết"**

Không sửa — cả hai section này vẫn đúng với kiến trúc mới (thêm/bớt báo vẫn chỉ sửa `outlets:`, và 4 báo lỗi vẫn như cũ).

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "Rewrite README.md for single-task architecture and auto topic detection"
```

---

### Task 8: Cập nhật scheduled task SKILL.md (ngoài repo)

**Files:**
- Modify: `/Users/nguyenthuhang/.claude/scheduled-tasks/press-scanning/SKILL.md` (không thuộc git repo này)

- [ ] **Step 1: Viết lại toàn bộ nội dung file**

Ghi đè `/Users/nguyenthuhang/.claude/scheduled-tasks/press-scanning/SKILL.md`:

```markdown
---
name: press-scanning
description: Điểm báo 6h hàng ngày
---

Chạy `python -m scripts.main` trong repo `press-scanning`
(`/Users/nguyenthuhang/Claude/press-scanning`) để quét RSS toàn bộ báo trong
`config/sources.yaml:outlets:`, lọc ra bài thật sự mới so với lần chạy trước.
Script ghi ra 2 file: `new_items.json` (bản nhẹ: id/outlet/title/snippet/
link/published) và `new_items_detail.json` (bản đầy đủ, đánh chỉ mục theo
`id`).

Đọc `new_items.json` và tự nhận diện các bài viết đang nói về cùng một sự
kiện, dựa trên hiểu nội dung (không so khớp từ khóa cứng) — nhiều báo có thể
diễn đạt cùng một sự kiện bằng tiêu đề rất khác nhau. Chỉ giữ lại các nhóm có
**từ 3 báo khác nhau trở lên** cùng đưa tin — đó là các chủ đề nổi bật của
ngày hôm nay. Không giới hạn số lượng chủ đề.

Với mỗi chủ đề được chọn, tra cứu (Grep theo `id`) phần chi tiết tương ứng
trong `new_items_detail.json`, rồi viết một mục "Toàn cảnh: {tên chủ đề tự
đặt, mô tả ngắn gọn sự kiện}": với mỗi bài, ghi rõ báo nào đăng và góc độ/khía
cạnh bài đó khai thác (ví dụ: số liệu, câu chuyện con người, phản ứng chính
quyền, phân tích chính sách...) — mục tiêu là đọc xong biết ngay các báo đang
khai thác khác nhau ở đâu, không cần đọc hết từng bài. Không trích dẫn nguyên
văn quá 15 từ mỗi nguồn. Nếu nhiều báo cùng khai thác một góc giống hệt nhau,
nói gộp một câu thay vì liệt kê lặp lại từng báo.

Nếu **không có chủ đề nào** đạt ngưỡng 3 báo trong ngày, dừng lại — không viết
gì thêm, không tạo file trên Drive.

Nếu có ít nhất 1 chủ đề đạt ngưỡng: lưu bản tổng hợp vào Google Drive — dùng
connector Google Drive, tìm thư mục tên "Press Scanning" ở My Drive (tạo mới
nếu chưa có), tạo một Google Doc mới trong thư mục đó với tiêu đề "Toàn cảnh -
{ngày hôm nay, định dạng YYYY-MM-DD}" chứa toàn bộ nội dung bản tổng hợp vừa
viết.

Không commit hay push gì lên git — `state/seen.json`, `new_items.json`,
`new_items_detail.json` chỉ là dữ liệu chạy cục bộ.
```

- [ ] **Step 2: Xác nhận file ghi đúng**

Run: `cat /Users/nguyenthuhang/.claude/scheduled-tasks/press-scanning/SKILL.md`
Expected: nội dung khớp với Step 1 (không phải bước git commit — file này nằm ngoài repo)

---

### Task 9: Kiểm thử thủ công toàn luồng

**Files:** không có file mới — bước xác minh thủ công, không tự động hóa được vì bước cụm nhóm do Claude tự suy luận, không phải code kiểm thử được bằng pytest.

- [ ] **Step 1: Chạy lại toàn bộ test suite**

Run: `python -m pytest -v`
Expected: tất cả pass (từ Task 1-2, 4 test)

- [ ] **Step 2: Chạy thử toàn bộ pipeline một lần thủ công**

Kích hoạt task "press-scanning" thủ công (không đợi lịch 6h) — ví dụ chạy lại prompt trong `SKILL.md` trực tiếp trong một phiên Claude Code có quyền truy cập repo và connector Google Drive.

- [ ] **Step 3: Kiểm tra kết quả**

- Nếu có chủ đề đạt ngưỡng ≥3 báo: mở thư mục "Press Scanning" trên Google Drive, xác nhận có Google Doc "Toàn cảnh - {hôm nay}" với nội dung hợp lý (đúng cấu trúc "Toàn cảnh: {tên chủ đề}", nêu rõ báo + góc khai thác cho từng bài).
- Nếu không có chủ đề nào đạt ngưỡng: xác nhận không có Doc rỗng nào được tạo.
- Đối chiếu thủ công vài chủ đề: chủ đề được chọn có thực sự do ≥3 báo khác nhau đưa tin không (tránh cụm nhóm quá rộng gộp nhầm sự kiện không liên quan, hoặc quá hẹp bỏ sót do diễn đạt khác nhau).

- [ ] **Step 4: Theo dõi vài ngày đầu**

Không phải bước kỹ thuật — chỉ cần bạn xem qua Doc vài ngày đầu tiên, báo lại nếu cụm nhóm bị lệch để tinh chỉnh ngưỡng hoặc cách viết.
