"""Unit tests for ArtifactProvenance domain model.

Tests provenance completeness validation (S5-G3) and
model concrete identity enforcement (S5-G4, PP9, DNB12).
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.errors import IncompleteProvenanceError, ModelAliasError
from src.domain.provenance import ArtifactProvenance


def _make_provenance(**overrides) -> ArtifactProvenance:
    """Create a complete provenance with all required fields."""
    defaults = {
        "artifact_id": uuid.uuid4(),
        "input_snapshot": [],
        "run_config_hash": "a" * 64,
        "model_provider": "anthropic",
        "model_name_concrete": "claude-sonnet-4-20250514",
        "model_version_concrete": "claude-sonnet-4-20250514",
        "lineage_chain": [],
    }
    defaults.update(overrides)
    return ArtifactProvenance(**defaults)


# ── Completeness Validation (S5-G3) ─────────────────────────


class TestProvenanceCompleteness:
    def test_complete_provenance_passes(self):
        p = _make_provenance()
        p.validate_complete("test-artifact-id")  # should not raise

    def test_missing_run_config_hash(self):
        p = _make_provenance(run_config_hash=None)
        with pytest.raises(IncompleteProvenanceError, match="run_config_hash"):
            p.validate_complete("test-id")

    def test_missing_model_provider(self):
        p = _make_provenance(model_provider=None)
        with pytest.raises(IncompleteProvenanceError, match="model_provider"):
            p.validate_complete("test-id")

    def test_missing_model_name_concrete(self):
        p = _make_provenance(model_name_concrete=None)
        with pytest.raises(IncompleteProvenanceError, match="model_name_concrete"):
            p.validate_complete("test-id")

    def test_missing_model_version_concrete(self):
        p = _make_provenance(model_version_concrete=None)
        with pytest.raises(IncompleteProvenanceError, match="model_version_concrete"):
            p.validate_complete("test-id")

    def test_whitespace_only_model_provider_rejected(self):
        p = _make_provenance(model_provider="   ")
        with pytest.raises(IncompleteProvenanceError, match="model_provider"):
            p.validate_complete("test-id")

    def test_whitespace_only_run_config_hash_rejected(self):
        p = _make_provenance(run_config_hash="  ")
        with pytest.raises(IncompleteProvenanceError, match="run_config_hash"):
            p.validate_complete("test-id")

    def test_multiple_missing_fields(self):
        p = _make_provenance(
            run_config_hash=None,
            model_provider=None,
            model_name_concrete=None,
            model_version_concrete=None,
        )
        with pytest.raises(IncompleteProvenanceError) as exc_info:
            p.validate_complete("test-id")
        assert len(exc_info.value.missing_fields) == 4

    def test_tool_version_required_when_tool_name_set(self):
        p = _make_provenance(tool_name="bash", tool_version=None)
        with pytest.raises(IncompleteProvenanceError, match="tool_version"):
            p.validate_complete("test-id")

    def test_tool_provenance_optional_as_group(self):
        """When no tool is involved (agent-only output), tool fields are all None."""
        p = _make_provenance(
            tool_name=None,
            tool_version=None,
            tool_config_hash=None,
        )
        p.validate_complete("test-id")  # should not raise

    def test_empty_input_snapshot_allowed(self):
        """Root artifacts have no inputs — empty list is valid."""
        p = _make_provenance(input_snapshot=[])
        p.validate_complete("test-id")  # should not raise

    def test_empty_lineage_chain_allowed(self):
        """Root artifacts have no ancestors — empty list is valid."""
        p = _make_provenance(lineage_chain=[])
        p.validate_complete("test-id")  # should not raise


# ── Model Alias Rejection (S5-G4, PP9, DNB12) ────────────────


class TestModelAliasRejection:
    """model_name_concrete and model_version_concrete must be concrete versions."""

    @pytest.mark.parametrize("alias", [
        "latest",
        "Latest",
        "LATEST",
        "default",
        "stable",
        "preview",
        "nightly",
        "claude-latest",
        "gpt-4-latest",
        "claude-sonnet-default",
    ])
    def test_model_name_alias_rejected_at_construction(self, alias: str):
        with pytest.raises(ModelAliasError, match="model_name_concrete"):
            _make_provenance(model_name_concrete=alias)

    @pytest.mark.parametrize("alias", [
        "latest",
        "default",
        "stable",
        "v2-latest",
    ])
    def test_model_version_alias_rejected_at_construction(self, alias: str):
        with pytest.raises(ModelAliasError, match="model_version_concrete"):
            _make_provenance(model_version_concrete=alias)

    @pytest.mark.parametrize("concrete", [
        "claude-sonnet-4-20250514",
        "gpt-4o-2024-08-06",
        "claude-opus-4-20250514",
        "gemini-1.5-pro-002",
    ])
    def test_concrete_model_name_accepted(self, concrete: str):
        p = _make_provenance(model_name_concrete=concrete)
        assert p.model_name_concrete == concrete

    def test_set_model_identity_validates_alias(self):
        p = _make_provenance()
        with pytest.raises(ModelAliasError):
            p.set_model_identity(
                provider="anthropic",
                name="latest",
                version="claude-sonnet-4-20250514",
            )

    def test_set_model_identity_version_alias_rejected(self):
        p = _make_provenance()
        with pytest.raises(ModelAliasError):
            p.set_model_identity(
                provider="anthropic",
                name="claude-sonnet-4-20250514",
                version="default",
            )

    def test_set_model_identity_concrete_accepted(self):
        p = _make_provenance()
        p.set_model_identity(
            provider="openai",
            name="gpt-4o-2024-08-06",
            version="gpt-4o-2024-08-06",
            temperature=0.7,
            max_tokens=4096,
            system_prompt_hash="b" * 64,
        )
        assert p.model_provider == "openai"
        assert p.model_name_concrete == "gpt-4o-2024-08-06"
        assert p.model_temperature == 0.7


# ── Serialization ─────────────────────────────────────────────


class TestProvenanceSerialization:
    def test_to_dict_includes_all_fields(self):
        aid = uuid.uuid4()
        cid = uuid.uuid4()
        p = _make_provenance(artifact_id=aid, correlation_id=cid)
        d = p.to_dict()
        assert d["artifact_id"] == str(aid)
        assert d["correlation_id"] == str(cid)
        assert d["model_provider"] == "anthropic"
        assert d["model_name_concrete"] == "claude-sonnet-4-20250514"
        assert d["run_config_hash"] == "a" * 64

    def test_to_dict_null_correlation(self):
        p = _make_provenance(correlation_id=None)
        d = p.to_dict()
        assert d["correlation_id"] is None
