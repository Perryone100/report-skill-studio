"""Compatibility checks for the canonical v0.3 report workbench contract."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


CANONICAL_REPORT_FIELDS = frozenset(
    {"title", "meeting_date", "executive_summary", "summary_cards", "sections"}
)
SUPPORTED_BLOCK_TYPES = frozenset(
    {"paragraph", "bullet_list", "project_table", "status_cards", "callout"}
)


def _resolve_local_ref(schema: dict[str, Any], node: Any) -> Any:
    if not isinstance(node, dict) or set(node) != {"$ref"}:
        return node
    reference = node["$ref"]
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return node
    current: Any = schema
    for part in reference[2:].split("/"):
        if not isinstance(current, dict):
            return node
        current = current.get(part.replace("~1", "/").replace("~0", "~"))
    return current


def _walk(schema: dict[str, Any], node: Any, seen_refs: set[str]) -> Iterator[Any]:
    if isinstance(node, dict):
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/"):
            if reference in seen_refs:
                return
            seen_refs.add(reference)
            yield from _walk(schema, _resolve_local_ref(schema, node), seen_refs)
            return
        yield node
        for value in node.values():
            yield from _walk(schema, value, seen_refs)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(schema, value, seen_refs)


def workbench_compatibility_issues(schema: dict[str, Any]) -> list[str]:
    """Return reasons a schema cannot be edited by the current workbench.

    The workbench intentionally supports one stable top-level contract and five
    block types. Uploaded Skills may narrow that contract, choose their own
    sections, and use a subset of blocks, but they may not introduce a shape the
    editor and renderer cannot safely interpret.
    """

    issues: list[str] = []
    if schema.get("type") != "object":
        issues.append("top-level schema type must be object")
    if schema.get("additionalProperties") is not False:
        issues.append("top-level additionalProperties must be false")

    required = schema.get("required")
    if not isinstance(required, list) or not CANONICAL_REPORT_FIELDS.issubset(required):
        issues.append("top-level required must include the five canonical report fields")

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        issues.append("top-level properties must be an object")
        return issues
    missing = CANONICAL_REPORT_FIELDS.difference(properties)
    if missing:
        issues.append(f"top-level properties are missing: {', '.join(sorted(missing))}")
        return issues
    unexpected = set(properties).difference(CANONICAL_REPORT_FIELDS)
    if unexpected:
        issues.append(
            f"top-level properties are not editable by the workbench: "
            f"{', '.join(sorted(unexpected))}"
        )

    expected_types = {
        "title": "string",
        "meeting_date": "string",
        "executive_summary": "string",
        "summary_cards": "array",
        "sections": "array",
    }
    for field, expected_type in expected_types.items():
        node = _resolve_local_ref(schema, properties[field])
        if not isinstance(node, dict) or node.get("type") != expected_type:
            issues.append(f"{field} must have schema type {expected_type}")

    summary_cards = _resolve_local_ref(schema, properties["summary_cards"])
    card_items = _resolve_local_ref(
        schema,
        summary_cards.get("items", {}) if isinstance(summary_cards, dict) else {},
    )
    if not isinstance(card_items, dict):
        issues.append("summary_cards items must define canonical card objects")
    else:
        card_required = card_items.get("required", [])
        card_properties = card_items.get("properties", {})
        if not {"label", "value"}.issubset(card_required) or not {
            "label",
            "value",
        }.issubset(card_properties):
            issues.append("summary_cards items must require label and value")

    section_nodes = list(_walk(schema, properties["sections"], set()))
    has_section_contract = any(
        isinstance(node, dict)
        and {"id", "title", "blocks"}.issubset(node.get("required", []))
        and {"id", "title", "blocks"}.issubset(node.get("properties", {}))
        for node in section_nodes
    )
    if not has_section_contract:
        issues.append("sections must define items requiring id, title, and blocks")

    declared_block_types = {
        block_type
        for node in section_nodes
        if isinstance(node, dict)
        for block_type in [
            node.get("properties", {}).get("type", {}).get("const")
        ]
        if isinstance(block_type, str)
    }
    if not declared_block_types:
        issues.append("sections must declare at least one supported block type")
    unsupported = declared_block_types.difference(SUPPORTED_BLOCK_TYPES)
    if unsupported:
        issues.append(f"unsupported block types: {', '.join(sorted(unsupported))}")

    return issues


def ensure_workbench_compatible(schema: dict[str, Any]) -> None:
    issues = workbench_compatibility_issues(schema)
    if issues:
        raise ValueError("; ".join(issues))
