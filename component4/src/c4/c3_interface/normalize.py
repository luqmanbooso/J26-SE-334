"""Normalize Component 3 defect labels at the Component 4 boundary."""

from __future__ import annotations

import re

from c4.c3_interface.contract import C3Verdict


_DEFECT_KEYS = {
    "component_overlap",
    "text_truncation",
    "missing_component",
    "unrendered_asset",
    "functional_incongruence",
    "frozen_state",
    "other_defect",
}


def normalize_defect_type(value: object) -> str:
    """Return a canonical defect key for arbitrary Component 3 labels."""
    normalized = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
    return normalized if normalized in _DEFECT_KEYS else "other_defect"


def normalize_verdict(verdict: C3Verdict) -> C3Verdict:
    """Canonicalize a verdict while retaining the original defect label."""
    if verdict.defect_type is None:
        return verdict
    original = verdict.defect_type
    metadata = dict(verdict.metadata)
    evidence = dict(verdict.evidence)
    metadata.setdefault("original_defect_type", original)
    evidence.setdefault("original_defect_type", original)
    return verdict.model_copy(
        update={
            "defect_type": normalize_defect_type(original),
            "metadata": metadata,
            "evidence": evidence,
        }
    )
