"""File-based order storage: one JSON file per order."""
import json
import os
from pathlib import Path
from typing import Any, Dict

from . import config


def data_dir() -> Path:
    path = Path(os.environ.get(config.DATA_DIR_ENV, "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_record(order_id: str, record: Dict[str, Any]) -> Path:
    target = data_dir() / f"{order_id}.json"
    target.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_record(order_id: str) -> Dict[str, Any]:
    return json.loads((data_dir() / f"{order_id}.json").read_text(encoding="utf-8"))
