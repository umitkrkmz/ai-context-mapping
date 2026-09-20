from shipdesk.repos.shipments import REPO


def test_put_get_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("k1", {"order_id": "Alpha", "n": 1})
    assert REPO.get("k1")["n"] == 1
    assert REPO.delete("k1") is True
    assert REPO.delete("k1") is False


def test_finder_is_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("k1", {"order_id": "Alpha"})
    assert REPO.find_by_order("aLPHA") == {"order_id": "Alpha"}
    assert REPO.find_by_order("missing") is None


def test_all_is_sorted_by_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("b", {"order_id": "b"})
    REPO.put("a", {"order_id": "a"})
    assert [row["order_id"] for row in REPO.all()] == ["a", "b"]
