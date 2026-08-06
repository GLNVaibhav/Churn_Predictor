from __future__ import annotations
from .generic_provider import GenericProvider


class TelecomProvider(GenericProvider):
    provider_name = "telecom_context"
    def supports(self, sector: str) -> bool:
        return sector.lower() == "telecom"
