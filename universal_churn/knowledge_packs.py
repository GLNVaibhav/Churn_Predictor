"""Read-only sector knowledge-pack lookup for Business Meaning Intelligence."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_")


@lru_cache(maxsize=1)
def _packs() -> tuple[dict[str, Any], ...]:
    """Load every sector directory without enumerating sectors in code."""
    directory = Path(__file__).resolve().parent.parent / "knowledge"
    packs = []
    for sector_dir in sorted(path for path in directory.iterdir() if path.is_dir()):
        concepts_file = sector_dir / "concepts.yaml"
        if not concepts_file.is_file():
            continue
        concepts = yaml.safe_load(concepts_file.read_text(encoding="utf-8")) or {}
        synonyms = yaml.safe_load((sector_dir / "synonyms.yaml").read_text(encoding="utf-8")) if (sector_dir / "synonyms.yaml").is_file() else {}
        canonical = yaml.safe_load((sector_dir / "canonical.yaml").read_text(encoding="utf-8")) if (sector_dir / "canonical.yaml").is_file() else {}
        relationships = yaml.safe_load((sector_dir / "relationships.yaml").read_text(encoding="utf-8")) if (sector_dir / "relationships.yaml").is_file() else {}
        for key, value in concepts.items():
            value = value or {}
            concept = value.get("concept", key)
            canonical_entry = canonical.get(concept, {}) if isinstance(canonical, dict) else {}
            packs.append({
                "key": key, "sector": sector_dir.name, **value,
                "canonical": value.get("canonical", canonical_entry.get("canonical")),
                "synonyms": (synonyms.get(concept, {}) or {}).get("aliases", []),
                "relationship_consistent": bool(relationships),
            })
    return tuple(packs)


def match_knowledge_pack(column_name: str) -> dict[str, Any] | None:
    normalized = _normalize(column_name)
    # Exact feature -> sector concept -> synonym -> feature alias.
    for entry in _packs():
        if normalized == _normalize(entry["key"]):
            return {**entry, "match_type": "exact"}
    for entry in _packs():
        if normalized in {_normalize(str(alias)) for alias in entry.get("synonyms", [])}:
            return {**entry, "match_type": "synonym"}
    for entry in _packs():
        if normalized in {_normalize(str(alias)) for alias in entry.get("aliases", [])}:
            return {**entry, "match_type": "alias"}
    return None
