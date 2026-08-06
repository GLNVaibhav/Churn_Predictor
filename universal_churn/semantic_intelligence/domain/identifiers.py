from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import re

_ONTOLOGY_PATTERN = re.compile(r"^ucif(?:\.[a-z][a-z0-9_]*)+$")


@dataclass(frozen=True, order=True)
class OntologyId:
    value: str
    def __post_init__(self) -> None:
        if not _ONTOLOGY_PATTERN.match(self.value):
            raise ValueError("OntologyId must be a lowercase dotted UCIF identifier.")
    def __str__(self) -> str: return self.value


@dataclass(frozen=True, order=True)
class SemanticVersion:
    value: str
    def __post_init__(self) -> None:
        if not re.match(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$", self.value):
            raise ValueError("SemanticVersion must use semantic versioning.")
    def __str__(self) -> str: return self.value


@dataclass(frozen=True)
class SemanticRunId:
    value: str
    @classmethod
    def from_fingerprint(cls, fingerprint: "DatasetFingerprint", nonce: str) -> "SemanticRunId":
        return cls(sha256(f"{fingerprint.value}:{nonce}".encode()).hexdigest()[:24])


@dataclass(frozen=True)
class DatasetFingerprint:
    value: str
    @classmethod
    def build(cls, columns: list[str], rows: int, metadata: dict | None = None) -> "DatasetFingerprint":
        payload = "|".join(columns) + f"|{rows}|" + repr(sorted((metadata or {}).items()))
        return cls(sha256(payload.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class ArtifactVersionSet:
    ontology: SemanticVersion = SemanticVersion("8.0.0")
    knowledge_packs: tuple[tuple[str, SemanticVersion], ...] = ()
    resolution_policy: SemanticVersion = SemanticVersion("8.0.0")
    calibration: SemanticVersion = SemanticVersion("8.0.0")
    feature_contract: SemanticVersion = SemanticVersion("8.0.0")
