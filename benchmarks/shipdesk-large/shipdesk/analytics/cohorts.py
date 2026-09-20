"""Customer cohorts by first-order month."""
from collections import defaultdict
from typing import Dict, Iterable, List


def cohorts(first_orders: Iterable[Dict[str, str]]) -> Dict[str, List[str]]:
    """Group customer ids by the YYYY-MM prefix of their first order date."""
    groups: Dict[str, List[str]] = defaultdict(list)
    for row in first_orders:
        groups[row["date"][:7]].append(row["customer"])
    return {month: sorted(ids) for month, ids in sorted(groups.items())}
