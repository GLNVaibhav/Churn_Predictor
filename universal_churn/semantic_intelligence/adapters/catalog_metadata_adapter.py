from __future__ import annotations
class CatalogMetadataAdapter:
    def normalize(self, metadata: dict | None) -> dict:
        return {str(k): v for k, v in (metadata or {}).items()}
