from __future__ import annotations
from ..domain.identifiers import ArtifactVersionSet
class VersionRegistry:
    def current(self) -> ArtifactVersionSet: return ArtifactVersionSet()
