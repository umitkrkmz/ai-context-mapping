"""Best-selling SKUs."""
from collections import Counter
from typing import Dict, Iterable, List, Tuple


def top_skus(records: Iterable[Dict[str, object]], limit: int = 3) -> List[Tuple[str, int]]:
    counts: Counter = Counter()
    for record in records:
        for sku, quantity in dict(record.get("lines", {})).items():
            counts[sku] += int(quantity)
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]
