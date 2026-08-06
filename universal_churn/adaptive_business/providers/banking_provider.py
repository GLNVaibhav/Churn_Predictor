from __future__ import annotations
from .generic_provider import GenericProvider


class BankingProvider(GenericProvider):
    provider_name = "banking_context"
    def supports(self, sector: str) -> bool:
        return sector.lower() == "banking"
