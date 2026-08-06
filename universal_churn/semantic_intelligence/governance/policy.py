from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class GovernancePolicy: require_complete_trace: bool = True; allow_human_overrides: bool = True
