"""US ZIP-prefix delivery zones (1 is closest to the warehouse, 8 is farthest).

Each row is (first_prefix, last_prefix, zone); both ends are inclusive and rows are sorted and gap-free.
"""
from typing import Optional

ZONE_RANGES = [
    (0, 9, 2),
    (10, 26, 3),
    (27, 50, 4),
    (51, 81, 5),
    (82, 96, 6),
    (97, 118, 7),
    (119, 147, 8),
    (148, 160, 5),
    (161, 180, 4),
    (181, 207, 3),
    (208, 218, 2),
    (219, 236, 3),
    (237, 261, 4),
    (262, 293, 5),
    (294, 309, 6),
    (310, 332, 7),
    (333, 362, 8),
    (363, 376, 5),
    (377, 397, 4),
    (398, 425, 3),
    (426, 437, 2),
    (438, 456, 3),
    (457, 482, 4),
    (483, 492, 5),
    (493, 509, 6),
    (510, 533, 7),
    (534, 564, 8),
    (565, 579, 5),
    (580, 601, 4),
    (602, 630, 3),
    (631, 643, 2),
    (644, 663, 3),
    (664, 690, 4),
    (691, 701, 5),
    (702, 719, 6),
    (720, 744, 7),
    (745, 776, 8),
    (777, 792, 5),
    (793, 815, 4),
    (816, 845, 3),
    (846, 859, 2),
    (860, 880, 3),
    (881, 908, 4),
    (909, 920, 5),
    (921, 939, 6),
    (940, 965, 7),
    (966, 975, 8),
    (976, 992, 5),
    (993, 999, 4),
]


def prefix_of(zip_code: str) -> Optional[int]:
    digits = "".join(ch for ch in zip_code if ch.isdigit())
    return int(digits[:3]) if len(digits) >= 3 else None


def zone_for_zip(zip_code: str) -> Optional[int]:
    prefix = prefix_of(zip_code)
    if prefix is None:
        return None
    for first, last, zone in ZONE_RANGES:
        if first <= prefix <= last:
            return zone
    return None


def surcharge_cents(zone: int) -> int:
    """Remote zones (7 and above) carry a fixed surcharge."""
    return 250 if zone >= 7 else 0
