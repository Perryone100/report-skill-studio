"""Deterministic, auditable transcript terminology normalization."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass

from .models import AppliedCorrection, NormalizationResult, Terminology


@dataclass(frozen=True, slots=True)
class _Replacement:
    variant: str
    canonical: str
    pattern: re.Pattern[str]
    order: int


def _replacement_rules(
    terminology: Terminology, *, confirmed_only: bool
) -> list[_Replacement]:
    replacements: list[_Replacement] = []
    order = 0
    for term in terminology.terms:
        if confirmed_only and not term.confirmed:
            continue
        flags = 0 if term.case_sensitive else re.IGNORECASE
        for variant in term.variants:
            replacements.append(
                _Replacement(
                    variant=variant,
                    canonical=term.canonical,
                    pattern=re.compile(re.escape(variant), flags),
                    order=order,
                )
            )
            order += 1

    # At the same source position, a phrase-specific correction must win over
    # a shorter prefix correction (for example "星云计划项目" before "星云计划").
    return sorted(replacements, key=lambda item: (-len(item.variant), item.order))


def normalize_transcript(
    text: str,
    terminology: Terminology,
    *,
    confirmed_only: bool = True,
) -> NormalizationResult:
    """Apply terminology corrections to ``text`` exactly once.

    Matching is performed only against the original input stream. Replacement
    output is appended directly and is never scanned again, so one rule cannot
    accidentally rewrite the canonical output of another rule.

    Corrections are grouped by the actual source spelling and canonical term in
    first-occurrence order. By default, unconfirmed terms are ignored.
    """

    rules = _replacement_rules(terminology, confirmed_only=confirmed_only)
    if not text or not rules:
        return NormalizationResult(text=text)

    output: list[str] = []
    counts: OrderedDict[tuple[str, str], int] = OrderedDict()
    position = 0

    while position < len(text):
        matched_rule: _Replacement | None = None
        matched_text: str | None = None
        match_end = position

        for rule in rules:
            match = rule.pattern.match(text, position)
            if match is not None:
                matched_rule = rule
                matched_text = match.group(0)
                match_end = match.end()
                break

        if matched_rule is None or matched_text is None:
            output.append(text[position])
            position += 1
            continue

        output.append(matched_rule.canonical)
        key = (matched_text, matched_rule.canonical)
        counts[key] = counts.get(key, 0) + 1
        position = match_end

    corrections = [
        AppliedCorrection(original=original, canonical=canonical, count=count)
        for (original, canonical), count in counts.items()
    ]
    return NormalizationResult(text="".join(output), corrections=corrections)
