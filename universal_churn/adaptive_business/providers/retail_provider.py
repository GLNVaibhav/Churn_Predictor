from __future__ import annotations
from .generic_provider import GenericProvider


class RetailProvider(GenericProvider):
    provider_name = "retail_context"
    def supports(self, sector: str) -> bool:
        return sector.lower() in {"retail", "ecommerce"}
