from shipdesk.repos.customers import REPO


def test_put_get_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("k1", {"email": "Alpha", "n": 1})
    assert REPO.get("k1")["n"] == 1
    assert REPO.delete("k1") is True
    assert REPO.delete("k1") is False


def test_finder_is_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("k1", {"email": "Alpha"})
    assert REPO.find_by_email("aLPHA") == {"email": "Alpha"}
    assert REPO.find_by_email("missing") is None


def test_all_is_sorted_by_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    REPO.put("b", {"email": "b"})
    REPO.put("a", {"email": "a"})
    assert [row["email"] for row in REPO.all()] == ["a", "b"]
