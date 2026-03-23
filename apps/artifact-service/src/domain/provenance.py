"""Artifact provenance domain model.

Implements the reproducibility tuple from doc 10, §4.
Enforces PP9 (model version not alias) and S5-G3 (completeness before ready).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from .errors import (
    DomainValidationError,
    IncompleteProvenanceError,
    ModelAliasError,
)

# Known model alias patterns that must NOT be stored as concrete identity.
# Matches: "latest", "default", "stable", aliases ending in "-latest", etc.
_ALIAS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(latest|default|stable|preview|nightly)$", re.IGNORECASE),
    re.compile(r"-(latest|default|stable|preview|nightly)$", re.IGNORECASE),
]


def _is_model_alias(value: str) -> bool:
    """Check if a model identifier looks like an alias rather than concrete version."""
    if not value:
        return False
    return any(p.search(value) for p in _ALIAS_PATTERNS)


@dataclass(frozen=False)
class ArtifactProvenance:
    """Reproducibility tuple for a generated artifact.

    Five components (doc 10, §4):
    1. input_snapshot — artifact_ids + checksums of inputs
    2. run_config — run_config_hash (SHA-256)
    3. tool_provenance — tool_name, tool_version, tool_config_hash
    4. model_provenance — model_provider, model_name_concrete, model_version_concrete,
                          temperature, system_prompt_hash
    5. lineage_chain — ordered edges from root

    Invariants:
    - model_name_concrete and model_version_concrete must NOT be aliases (PP9, DNB12).
    - All 5 components must be present before artifact can transition to ready (S5-G3).
    - Tool provenance is nullable when artifact is pure agent output (no tool involved).
    """

    artifact_id: UUID

    # Component 1: input_snapshot
    # List of {"artifact_id": str, "checksum": str} dicts
    input_snapshot: list[dict[str, str]] = field(default_factory=list)

    # Component 2: run_config
    run_config_hash: str | None = None

    # Component 3: tool_provenance (nullable — agent-only output has no tool)
    tool_name: str | None = None
    tool_version: str | None = None
    tool_config_hash: str | None = None

    # Component 4: model_provenance
    model_provider: str | None = None
    model_name_concrete: str | None = None
    model_version_concrete: str | None = None
    model_temperature: float | None = None
    model_max_tokens: int | None = None
    system_prompt_hash: str | None = None

    # Component 5: lineage_chain
    # Ordered list of edge_ids from root to this artifact
    lineage_chain: list[str] = field(default_factory=list)

    # Metadata
    correlation_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate model identity is concrete, not alias."""
        if self.model_name_concrete and _is_model_alias(self.model_name_concrete):
            raise ModelAliasError("model_name_concrete", self.model_name_concrete)
        if self.model_version_concrete and _is_model_alias(self.model_version_concrete):
            raise ModelAliasError("model_version_concrete", self.model_version_concrete)

    def validate_complete(self, artifact_id_str: str, *, root_type: str = "generated") -> None:
        """Validate reproducibility tuple components are present.

        Called by Artifact.finalize() before transition to ready (S5-G3).

        For generated artifacts: requires model provenance + run_config.
        For uploaded artifacts: model provenance not required.

        Raises IncompleteProvenanceError if any required component is missing.
        """
        missing: list[str] = []

        if root_type == "upload":
            # Uploaded artifacts don't require model/run provenance
            # but if tool_name is set, tool_version is required
            if self.tool_name and self.tool_name.strip() and (
                not self.tool_version or not self.tool_version.strip()
            ):
                missing.append("tool_version (tool_name is set)")
        else:
            # Generated artifacts: full reproducibility tuple required

            # Component 2: run_config
            if not self.run_config_hash or not self.run_config_hash.strip():
                missing.append("run_config_hash")

            # Component 3: tool_provenance — optional as a group
            if self.tool_name and self.tool_name.strip() and (
                not self.tool_version or not self.tool_version.strip()
            ):
                missing.append("tool_version (tool_name is set)")

            # Component 4: model_provenance — required for generated artifacts
            if not self.model_provider or not self.model_provider.strip():
                missing.append("model_provider")
            if not self.model_name_concrete or not self.model_name_concrete.strip():
                missing.append("model_name_concrete")
            if not self.model_version_concrete or not self.model_version_concrete.strip():
                missing.append("model_version_concrete")

        if missing:
            raise IncompleteProvenanceError(artifact_id_str, missing)

    def set_model_identity(
        self,
        *,
        provider: str,
        name: str,
        version: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt_hash: str | None = None,
    ) -> None:
        """Set model provenance with alias validation.

        Raises ModelAliasError if name or version is an alias.
        """
        if _is_model_alias(name):
            raise ModelAliasError("model_name_concrete", name)
        if _is_model_alias(version):
            raise ModelAliasError("model_version_concrete", version)

        self.model_provider = provider
        self.model_name_concrete = name
        self.model_version_concrete = version
        self.model_temperature = temperature
        self.model_max_tokens = max_tokens
        self.system_prompt_hash = system_prompt_hash

    def to_dict(self) -> dict[str, Any]:
        """Serialize provenance to dict for storage/API response."""
        return {
            "artifact_id": str(self.artifact_id),
            "input_snapshot": self.input_snapshot,
            "run_config_hash": self.run_config_hash,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "tool_config_hash": self.tool_config_hash,
            "model_provider": self.model_provider,
            "model_name_concrete": self.model_name_concrete,
            "model_version_concrete": self.model_version_concrete,
            "model_temperature": self.model_temperature,
            "model_max_tokens": self.model_max_tokens,
            "system_prompt_hash": self.system_prompt_hash,
            "lineage_chain": self.lineage_chain,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
        }
