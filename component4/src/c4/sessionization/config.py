"""Configuration for deterministic session reconstruction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionizationConfig:
    """Limits and policies applied during session and journey reconstruction."""

    gap_minutes: int = 30
    max_actions: int = 10
    keep_unknown: bool = False
    collapse_duplicates: bool = True
    min_actions_for_reproducible: int = 1
