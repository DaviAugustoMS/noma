"""Vendor-neutral ontology model.

``normalize_ontology`` turns the LLM-generated ontology dict into a validated,
capped structure. Backends translate it into their own schema (for Zep, dynamic
Pydantic classes), so ontology rules live in one place regardless of provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...utils.ontology import (
    MAX_ONTOLOGY_TYPES,
    RESERVED_ONTOLOGY_ATTRIBUTE_NAMES,
    normalize_ontology_attributes,
    normalize_ontology_source_targets,
)


@dataclass(frozen=True)
class AttributeDef:
    name: str
    description: str


@dataclass(frozen=True)
class EntityTypeDef:
    name: str
    description: str
    attributes: tuple[AttributeDef, ...]


@dataclass(frozen=True)
class EdgeTypeDef:
    name: str
    # PascalCase form of ``name`` for providers that need a class identifier.
    class_name: str
    description: str
    attributes: tuple[AttributeDef, ...]
    source_targets: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Ontology:
    entity_types: tuple[EntityTypeDef, ...]
    edge_types: tuple[EdgeTypeDef, ...]


def safe_attribute_name(name: str) -> str:
    """Rename attributes that collide with provider-reserved node fields."""

    if name.lower() in RESERVED_ONTOLOGY_ATTRIBUTE_NAMES:
        return f"entity_{name}"
    return name


def _attributes(raw: Any) -> tuple[AttributeDef, ...]:
    return tuple(
        AttributeDef(
            name=safe_attribute_name(item["name"]),
            description=item["description"],
        )
        for item in normalize_ontology_attributes(raw)
    )


def normalize_ontology(ontology: dict[str, Any]) -> Ontology:
    entity_types = tuple(
        EntityTypeDef(
            name=entity["name"],
            description=entity.get("description", f"A {entity['name']} entity."),
            attributes=_attributes(entity.get("attributes", [])),
        )
        for entity in ontology.get("entity_types", [])[:MAX_ONTOLOGY_TYPES]
    )

    edge_types = []
    for edge in ontology.get("edge_types", [])[:MAX_ONTOLOGY_TYPES]:
        name = edge["name"]
        edge_types.append(
            EdgeTypeDef(
                name=name,
                class_name="".join(word.capitalize() for word in name.split("_")),
                description=edge.get("description", f"A {name} relationship."),
                attributes=_attributes(edge.get("attributes", [])),
                source_targets=tuple(
                    (st.get("source", "Entity"), st.get("target", "Entity"))
                    for st in normalize_ontology_source_targets(
                        edge.get("source_targets", [])
                    )
                ),
            )
        )
    return Ontology(entity_types=entity_types, edge_types=tuple(edge_types))
