from __future__ import annotations
from .knowledge_pack_registry import KnowledgePack


class KnowledgePackValidator:
    def validate(self, pack: KnowledgePack) -> tuple[str, ...]:
        errors = []
        if not pack.pack_id: errors.append("pack_id is required")
        if not pack.aliases and not pack.abbreviations: errors.append("pack must declare evidence vocabulary")
        return tuple(errors)
