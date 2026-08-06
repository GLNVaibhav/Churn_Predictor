from __future__ import annotations
from pathlib import Path
import yaml
from ..domain.identifiers import OntologyId, SemanticVersion
from .knowledge_pack_registry import KnowledgePack


class KnowledgePackLoader:
    def load(self, path: Path) -> KnowledgePack:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return KnowledgePack(str(data["pack_id"]), SemanticVersion(str(data.get("pack_version", "8.0.0"))), OntologyId(str(data["sector_id"])), tuple((str(k), str(v)) for k, v in (data.get("abbreviations") or {}).items()), tuple((str(k), OntologyId(str(v))) for k, v in (data.get("aliases") or {}).items()))
