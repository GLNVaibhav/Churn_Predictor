from __future__ import annotations
from dataclasses import asdict, dataclass
import json
from ..domain.identifiers import ArtifactVersionSet, DatasetFingerprint

@dataclass(frozen=True)
class SemanticRunManifest:
    run_id: str; fingerprint: DatasetFingerprint; versions: ArtifactVersionSet; execution_mode: str
    def to_json(self) -> str:
        return json.dumps(asdict(self), default=lambda value: getattr(value, "value", str(value)), sort_keys=True)
