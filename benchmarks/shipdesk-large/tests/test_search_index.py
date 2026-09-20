from shipdesk.catalog import CATALOG
from shipdesk.search.index import Index, tokenize


def test_tokenize_drops_stop_words():
    assert tokenize("The Enamel Mug of Joy") == ["enamel", "mug", "joy"]


def test_search_ranks_by_matches():
    index = Index(CATALOG.values())
    assert index.search("logo shirt")[0].sku == "TEE-02"
    assert [item.sku for item in index.search("mug")] == ["MUG-01"]


def test_empty_and_unknown_queries():
    index = Index(CATALOG.values())
    assert index.search("") == []
    assert index.search("zzzz") == []
