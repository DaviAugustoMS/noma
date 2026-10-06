"""Knowledge-graph memory layer: backend-neutral contract plus implementations."""

from __future__ import annotations

from typing import Optional

from ...config import Config
from .base import (
    GraphBackend,
    GraphBackendError,
    GraphEdge,
    GraphNode,
    GraphNotFoundError,
    GraphSearchResults,
    IngestionSubmission,
)

SUPPORTED_GRAPH_BACKENDS = ("zep",)


def get_graph_backend(api_key: Optional[str] = None) -> GraphBackend:
    """Build the backend selected by ``GRAPH_BACKEND`` (default: ``zep``)."""

    kind = (Config.GRAPH_BACKEND or "zep").strip().lower()
    if kind == "zep":
        from .zep_backend import ZepBackend

        return ZepBackend.from_api_key(api_key)
    raise ValueError(
        f"Unsupported GRAPH_BACKEND {kind!r}; supported: "
        f"{', '.join(SUPPORTED_GRAPH_BACKENDS)}"
    )


__all__ = [
    "GraphBackend",
    "GraphBackendError",
    "GraphEdge",
    "GraphNode",
    "GraphNotFoundError",
    "GraphSearchResults",
    "IngestionSubmission",
    "SUPPORTED_GRAPH_BACKENDS",
    "get_graph_backend",
]
