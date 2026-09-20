"""A tiny repository: one JSON file per entity kind, a dict of id -> record."""
import json
from typing import Any, Dict, List, Optional

from ..storage import data_dir


class JsonRepo:
    kind = "entity"

    def _path(self):
        return data_dir() / f"{self.kind}.json"

    def _load(self) -> Dict[str, Dict[str, Any]]:
        path = self._path()
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _save(self, rows: Dict[str, Dict[str, Any]]) -> None:
        self._path().write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")

    def put(self, key: str, record: Dict[str, Any]) -> None:
        rows = self._load()
        rows[key] = record
        self._save(rows)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._load().get(key)

    def delete(self, key: str) -> bool:
        rows = self._load()
        removed = rows.pop(key, None) is not None
        self._save(rows)
        return removed

    def all(self) -> List[Dict[str, Any]]:
        return [row for _, row in sorted(self._load().items())]
