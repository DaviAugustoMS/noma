"""Backend-neutral contract for the knowledge-graph memory layer.

Services depend on this module, never on a vendor SDK. A backend (Zep Cloud
today) translates vendor types and errors into the dataclasses and exceptions
defined here, and owns vendor-specific concerns such as retry policy,
pagination cursors, ingestion batching and ontology encoding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable


class GraphBackendError(Exception):
    """Base class for errors raised through the backend contract."""


class GraphNotFoundError(GraphBackendError):
    """The requested graph, node or episode does not exist."""


@dataclass(frozen=True)
class GraphNode:
    uuid: str
    name: str = ""
    labels: list[str] = field(default_factory=list)
    summary: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: Any = None


@dataclass(frozen=True)
class GraphEdge:
    uuid: str
    name: str = ""
    fact: str = ""
    source_node_uuid: str = ""
    target_node_uuid: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    fact_type: str = ""
    created_at: Any = None
    valid_at: Any = None
    invalid_at: Any = None
    expired_at: Any = None
    episodes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GraphSearchResults:
    edges: list[GraphEdge] = field(default_factory=list)
    nodes: list[GraphNode] = field(default_factory=list)


@dataclass(frozen=True)
class IngestionSubmission:
    """Durable identity of one asynchronous ingestion operation.

    ``batch_id`` and ``operation_id`` are persisted by callers so an interrupted
    build can be resumed or reconciled instead of replayed.
    """

    batch_id: str
    operation_id: str
    episode_uuids: list[str]
    item_count: int


# (message, progress ratio in [0, 1])
ProgressCallback = Callable[[str, float], None]
# (batch_id or None before the server assigned one, operation_id)
SubmissionCallback = Callable[[str | None, str], None]


@runtime_checkable
class GraphBackend(Protocol):
    """Operations the application needs from a knowledge-graph provider."""

    name: str

    # -- lifecycle -----------------------------------------------------
    def create_graph(
        self, graph_id: str, name: str, description: str = ""
    ) -> None:
        """Create a graph, reconciling an ambiguous reply (lost response)."""

    def delete_graph(self, graph_id: str) -> None:
        """Delete a graph. Raises ``GraphNotFoundError`` when already absent."""

    def set_ontology(self, graph_id: str, ontology: dict[str, Any]) -> None:
        """Apply the application ontology dict (see ``ontology.normalize_ontology``)."""

    # -- ingestion -----------------------------------------------------
    def validate_chunks(self, chunks: list[str], *, batch_size: int = 350) -> None:
        """Reject payloads the provider would refuse, before any mutation."""

    def submit_chunks(
        self,
        graph_id: str,
        chunks: list[str],
        *,
        operation_id: str,
        batch_size: int = 350,
        progress_callback: ProgressCallback | None = None,
        submission_callback: SubmissionCallback | None = None,
    ) -> IngestionSubmission:
        """Submit text chunks without replaying non-idempotent writes."""

    def get_ingestion_status(self, batch_id: str) -> str | None:
        """Return the provider status of a persisted submission."""

    def wait_for_ingestion(
        self,
        submission: IngestionSubmission,
        *,
        progress_callback: ProgressCallback | None = None,
        timeout: int | None = None,
    ) -> list[str]:
        """Block until the submission is fully processed; return episode UUIDs."""

    def add_text(
        self,
        graph_id: str,
        text: str,
        *,
        created_at: str | None = None,
        source_description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add one text episode (no retry: not idempotent). Return its UUID."""

    def is_episode_processed(self, episode_uuid: str) -> bool:
        ...

    def is_transient_error(self, error: BaseException) -> bool:
        """Whether ``error`` is a retryable transport/availability failure."""

    # -- reads (transient failures are retried inside the backend) ------
    def list_nodes(self, graph_id: str) -> list[GraphNode]:
        ...

    def list_edges(self, graph_id: str) -> list[GraphEdge]:
        ...

    def get_node(self, node_uuid: str) -> GraphNode | None:
        """Return the node, or ``None`` when it does not exist."""

    def get_node_edges(self, node_uuid: str) -> list[GraphEdge]:
        """Edges the provider attaches to a node (may be outgoing only)."""

    def search(
        self,
        graph_id: str,
        query: str,
        *,
        limit: int = 10,
        scope: str = "edges",
        reranker: str | None = None,
    ) -> GraphSearchResults:
        ...
