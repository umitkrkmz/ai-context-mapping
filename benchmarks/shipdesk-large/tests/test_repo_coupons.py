from shipdesk.repos.coupons import REPO


def test_put_get_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("k1", {"code": "Alpha", "n": 1})
    assert REPO.get("k1")["n"] == 1
    assert REPO.delete("k1") is True
    assert REPO.delete("k1") is False


def test_finder_is_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("k1", {"code": "Alpha"})
    assert REPO.find_by_code("aLPHA") == {"code": "Alpha"}
    assert REPO.find_by_code("missing") is None


def test_all_is_sorted_by_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("b", {"code": "b"})
    REPO.put("a", {"code": "a"})
    assert [row["code"] for row in REPO.all()] == ["a", "b"]
