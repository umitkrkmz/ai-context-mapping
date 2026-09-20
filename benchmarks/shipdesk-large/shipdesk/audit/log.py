"""Audit log lines: a stable, sortable text format."""
from typing import Dict


def format_entry(timestamp: str, actor: str, action: str, details: Dict[str, object]) -> str:
    pairs = " ".join(f"{key}={details[key]}" for key in sorted(details))
    return f"{timestamp} {actor} {action}" + (f" {pairs}" if pairs else "")


def parse_entry(line: str) -> Dict[str, object]:
    head, _, rest = line.partition(" ")
    actor, _, remainder = rest.partition(" ")
    action, _, pairs = remainder.partition(" ")
    details = dict(pair.split("=", 1) for pair in pairs.split() if "=" in pair)
    return {"timestamp": head, "actor": actor, "action": action, "details": details}
