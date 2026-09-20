"""A small in-memory keyword index over product names."""
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Set

from ..models import Item

_WORD = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset({"the", "a", "an", "of", "and", "for"})


def tokenize(text: str) -> List[str]:
    return [word for word in _WORD.findall(text.lower()) if word not in STOP_WORDS]


class Index:
    def __init__(self, items: Iterable[Item]) -> None:
        self._items: Dict[str, Item] = {}
        self._postings: Dict[str, Set[str]] = defaultdict(set)
        for item in items:
            self._items[item.sku] = item
            for token in tokenize(item.name) + tokenize(item.sku):
                self._postings[token].add(item.sku)

    def search(self, query: str, limit: int = 5) -> List[Item]:
        """Rank by number of matching query tokens, then by SKU; empty queries match nothing."""
        tokens = tokenize(query)
        if not tokens:
            return []
        scores: Dict[str, int] = defaultdict(int)
        for token in tokens:
            for sku in self._postings.get(token, ()):
                scores[sku] += 1
        ranked = sorted(scores, key=lambda sku: (-scores[sku], sku))
        return [self._items[sku] for sku in ranked[:limit]]
