import scripts.main as main_module
from scripts.main import build_output, fetch_all_new_items


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


def test_build_output_flattens_multiple_outlets_and_items():
    new_items_by_outlet = {
        "VnExpress": [
            {"id": "a1", "title": "A1", "link": "https://a.vn/1", "published": "", "summary_raw": "tt a1"},
            {"id": "a2", "title": "A2", "link": "https://a.vn/2", "published": "", "summary_raw": "tt a2"},
        ],
        "Tuổi Trẻ": [
            {"id": "b1", "title": "B1", "link": "https://b.vn/1", "published": "", "summary_raw": "tt b1"},
        ],
    }

    index_items, detail_items = build_output(new_items_by_outlet)

    assert len(index_items) == 3
    assert len(detail_items) == 3
    outlets_by_id = {item["id"]: item["outlet"] for item in index_items}
    assert outlets_by_id == {"a1": "VnExpress", "a2": "VnExpress", "b1": "Tuổi Trẻ"}


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
