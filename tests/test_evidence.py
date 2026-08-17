from datetime import UTC, datetime, timedelta

import pytest

from sinergy_eurasian import (
    ModelInvariantError,
    ProjectEvidenceBundle,
    ProjectEvidenceItem,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _item(
    evidence_id: str,
    evidence_class: str,
    finality_level: str,
    *,
    observed_at: datetime = NOW,
) -> ProjectEvidenceItem:
    return ProjectEvidenceItem(
        evidence_id=evidence_id,
        evidence_class=evidence_class,
        source_system="marketplace-or-bank",
        reference=f"ref-{evidence_id}",
        observed_at=observed_at,
        finality_level=finality_level,
        evidence_digest=(evidence_id[0] if evidence_id[0] in "abcdef" else "a") * 64,
    )


def test_bundle_digest_is_deterministic_and_item_order_independent() -> None:
    a = _item("a1", "MARKETPLACE_ORDER", "OBSERVED")
    b = _item("b1", "BANK_SETTLEMENT", "SETTLED")
    first = ProjectEvidenceBundle("project-1", NOW, (b, a))
    second = ProjectEvidenceBundle("project-1", NOW, (a, b))
    assert first.digest == second.digest
    assert [item.evidence_id for item in first.items] == ["a1", "b1"]


def test_bundle_distinguishes_observed_settled_and_audited_evidence() -> None:
    bundle = ProjectEvidenceBundle(
        "project-1",
        NOW,
        (
            _item("a1", "PRODUCTION_TELEMETRY", "OBSERVED"),
            _item("b1", "BANK_SETTLEMENT", "SETTLED"),
            _item("c1", "AUDIT_REPORT", "AUDITED"),
        ),
    )
    assert bundle.minimum_finality_count("OBSERVED") == 3
    assert bundle.minimum_finality_count("SETTLED") == 2
    assert bundle.minimum_finality_count("AUDITED") == 1
    assert bundle.has_class("bank_settlement") is True


def test_duplicate_evidence_id_is_rejected() -> None:
    a = _item("a1", "MARKETPLACE_ORDER", "OBSERVED")
    with pytest.raises(ModelInvariantError):
        ProjectEvidenceBundle("project-1", NOW, (a, a))


def test_future_evidence_is_rejected() -> None:
    future = _item(
        "a1",
        "BANK_SETTLEMENT",
        "SETTLED",
        observed_at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(ModelInvariantError):
        ProjectEvidenceBundle("project-1", NOW, (future,))


def test_unknown_evidence_class_is_rejected() -> None:
    with pytest.raises(ModelInvariantError):
        _item("a1", "MADE_UP_PROOF", "OBSERVED")


def test_unknown_finality_level_is_rejected() -> None:
    with pytest.raises(ModelInvariantError):
        _item("a1", "BANK_SETTLEMENT", "TRUSTED")


def test_to_dict_binds_bundle_digest_without_hiding_source_item_digests() -> None:
    bundle = ProjectEvidenceBundle(
        "project-1",
        NOW,
        (_item("a1", "BANK_SETTLEMENT", "SETTLED"),),
    )
    payload = bundle.to_dict()
    assert payload["schema"] == "project.evidence/v1"
    assert payload["digest"] == bundle.digest
    assert payload["items"][0]["evidence_digest"] == "a" * 64
