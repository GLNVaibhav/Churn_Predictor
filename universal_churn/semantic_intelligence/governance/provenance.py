from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class ProvenanceRecord: source: str; method: str; timestamp_utc: str; trust_level: str = "declared"
