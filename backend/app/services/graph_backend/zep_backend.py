"""Zep Cloud implementation of the graph backend contract.

Everything specific to Zep lives here: the SDK client, transient-error retry,
cursor pagination, the Batch API with its reconciliation of lost replies,
ontology encoding as dynamic Pydantic classes, and NotFound translation.
"""

from __future__ import annotations

import functools
import hashlib
import time
import warnings
from typing import Any, Callable, List, Optional

from zep_cloud import BatchAddItem, EntityEdgeSourceTarget, NotFoundError
from zep_cloud.client import Zep

from ...utils.locale import t
from ...utils.zep import (
    ZEP_INGESTION_WAIT_TIMEOUT_SECONDS,
    call_zep_read_with_retry,
    get_zep_client,
    is_retryable_zep_error,
    normalize_zep_search_limit,
    normalize_zep_search_query,
)
from ...utils.zep_paging import fetch_all_edges, fetch_all_nodes
from .base import (
    GraphEdge,
    GraphNode,
    GraphNotFoundError,
    GraphSearchResults,
    IngestionSubmission,
    ProgressCallback,
    SubmissionCallback,
)
from .ontology import normalize_ontology

_MAX_BATCH_SIZE = 350
_MAX_BATCH_ITEMS = 50_000
_MAX_ITEM_CHARS = 10_000


def _translate_not_found(method: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(method)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except NotFoundError as error:
            raise GraphNotFoundError(str(error)) from error

    return wrapper


def _uuid_of(item: Any) -> str:
    return str(getattr(item, "uuid_", None) or getattr(item, "uuid", None) or "")


def _to_node(node: Any) -> GraphNode:
    return GraphNode(
        uuid=_uuid_of(node),
        name=getattr(node, "name", None) or "",
        labels=list(getattr(node, "labels", None) or []),
        summary=getattr(node, "summary", None) or "",
        attributes=dict(getattr(node, "attributes", None) or {}),
        created_at=getattr(node, "created_at", None),
    )


def _to_edge(edge: Any) -> GraphEdge:
    episodes = getattr(edge, "episodes", None) or getattr(edge, "episode_ids", None)
    if episodes and not isinstance(episodes, list):
        episodes = [str(episodes)]
    name = getattr(edge, "name", None) or ""
    return GraphEdge(
        uuid=_uuid_of(edge),
        name=name,
        fact=getattr(edge, "fact", None) or "",
        source_node_uuid=getattr(edge, "source_node_uuid", None) or "",
        target_node_uuid=getattr(edge, "target_node_uuid", None) or "",
        attributes=dict(getattr(edge, "attributes", None) or {}),
        fact_type=getattr(edge, "fact_type", None) or name,
        created_at=getattr(edge, "created_at", None),
        valid_at=getattr(edge, "valid_at", None),
        invalid_at=getattr(edge, "invalid_at", None),
        expired_at=getattr(edge, "expired_at", None),
        episodes=[str(e) for e in (episodes or [])],
    )


class ZepBackend:
    name = "zep"

    def __init__(self, client: Zep) -> None:
        self.client = client

    @classmethod
    def from_api_key(cls, api_key: Optional[str] = None) -> "ZepBackend":
        return cls(get_zep_client(api_key))

    def is_transient_error(self, error: BaseException) -> bool:
        return is_retryable_zep_error(error)

    # -- lifecycle -----------------------------------------------------
    def create_graph(
        self, graph_id: str, name: str, description: str = ""
    ) -> None:
        try:
            self.client.graph.create(
                graph_id=graph_id, name=name, description=description
            )
        except Exception as error:
            if not is_retryable_zep_error(error):
                raise
            # The POST is not idempotent; confirm with a safe GET whether the
            # graph exists instead of replaying it.
            reconciliation_error = None
            for attempt in range(3):
                try:
                    call_zep_read_with_retry(
                        lambda: self.client.graph.get(graph_id),
                        operation_name=f"reconcile graph create {graph_id}",
                    )
                    reconciliation_error = None
                    break
                except NotFoundError as not_found:
                    reconciliation_error = not_found
                    if attempt < 2:
                        time.sleep(attempt + 1)
                except Exception as read_error:
                    reconciliation_error = read_error
                    break
            if reconciliation_error is not None:
                raise error from reconciliation_error

    @_translate_not_found
    def delete_graph(self, graph_id: str) -> None:
        self.client.graph.delete(graph_id=graph_id)

    def set_ontology(self, graph_id: str, ontology: dict[str, Any]) -> None:
        from pydantic import Field
        from zep_cloud.external_clients.ontology import (
            EdgeModel,
            EntityModel,
            EntityText,
        )

        # Zep requires Field(default=None); the warning comes from dynamic
        # class creation and is safe to ignore.
        warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

        normalized = normalize_ontology(ontology)

        entity_types: dict[str, type] = {}
        for entity in normalized.entity_types:
            attrs: dict[str, Any] = {"__doc__": entity.description}
            annotations: dict[str, Any] = {}
            for attribute in entity.attributes:
                attrs[attribute.name] = Field(
                    description=attribute.description, default=None
                )
                annotations[attribute.name] = Optional[EntityText]
            attrs["__annotations__"] = annotations
            entity_class = type(entity.name, (EntityModel,), attrs)
            entity_class.__doc__ = entity.description
            entity_types[entity.name] = entity_class

        edge_definitions: dict[str, Any] = {}
        for edge in normalized.edge_types:
            attrs = {"__doc__": edge.description}
            annotations = {}
            for attribute in edge.attributes:
                attrs[attribute.name] = Field(
                    description=attribute.description, default=None
                )
                annotations[attribute.name] = Optional[str]
            attrs["__annotations__"] = annotations
            edge_class = type(edge.class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = edge.description

            # Zep rejects edge types without source/target pairs.
            source_targets = [
                EntityEdgeSourceTarget(source=source, target=target)
                for source, target in edge.source_targets
            ]
            if source_targets:
                edge_definitions[edge.name] = (edge_class, source_targets)

        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                # Zep iterates entities.items(), so edge-only ontologies must
                # pass an empty dictionary rather than None.
                entities=entity_types,
                edges=edge_definitions if edge_definitions else None,
            )

    # -- ingestion -----------------------------------------------------
    def validate_chunks(self, chunks: List[str], *, batch_size: int = 350) -> None:
        """Validate every Batch API limit before the first Cloud mutation."""

        if not chunks:
            raise ValueError("At least one text chunk is required")
        if not 1 <= batch_size <= _MAX_BATCH_SIZE:
            raise ValueError("batch_size must be between 1 and 350")
        if len(chunks) > _MAX_BATCH_ITEMS:
            raise ValueError("A Zep batch cannot contain more than 50,000 items")
        oversized = [
            index for index, chunk in enumerate(chunks) if len(chunk) > _MAX_ITEM_CHARS
        ]
        if oversized:
            raise ValueError(
                f"Zep batch item exceeds 10,000 characters at chunk {oversized[0]}"
            )

    def _find_batch_by_operation_id(
        self,
        graph_id: str,
        operation_id: str,
        *,
        max_attempts: int = 3,
    ) -> Any | None:
        """Find one server-created batch after an ambiguous create reply."""

        for attempt in range(1, max_attempts + 1):
            matches: List[Any] = []
            cursor: int | None = None
            seen_cursors: set[int] = set()
            while True:
                page = call_zep_read_with_retry(
                    lambda: self.client.batch.list(limit=100, cursor=cursor),
                    operation_name=f"reconcile batch create {operation_id}",
                )
                for batch in getattr(page, "batches", None) or []:
                    metadata = getattr(batch, "metadata", None) or {}
                    if (
                        metadata.get("mirofish_operation_id") == operation_id
                        and metadata.get("graph_id") == graph_id
                    ):
                        matches.append(batch)
                next_cursor = getattr(page, "next_cursor", None)
                if next_cursor is None:
                    break
                if next_cursor == cursor or next_cursor in seen_cursors:
                    raise RuntimeError("Zep batch list cursor did not advance")
                seen_cursors.add(next_cursor)
                cursor = next_cursor

            if len(matches) > 1:
                raise RuntimeError(
                    f"Multiple Zep batches match operation {operation_id}; refusing ambiguity"
                )
            if matches:
                return matches[0]
            if attempt < max_attempts:
                time.sleep(attempt)
        return None

    def _list_batch_items(self, batch_id: str) -> List[Any]:
        items: List[Any] = []
        cursor: int | None = None
        seen_cursors: set[int] = set()
        while True:
            page = call_zep_read_with_retry(
                lambda: self.client.batch.list_items(
                    batch_id=batch_id,
                    limit=100,
                    cursor=cursor,
                ),
                operation_name=f"list batch items {batch_id}",
            )
            items.extend(getattr(page, "items", None) or [])
            next_cursor = getattr(page, "next_cursor", None)
            if next_cursor is None:
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                raise RuntimeError(f"Zep batch {batch_id} item cursor did not advance")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        return items

    def _reconcile_batch_item_count(
        self,
        batch_id: str,
        expected_item_count: int,
        *,
        max_attempts: int = 3,
    ) -> List[Any]:
        """Allow a short propagation window after an ambiguous add reply."""

        items: List[Any] = []
        for attempt in range(1, max_attempts + 1):
            items = self._list_batch_items(batch_id)
            if len(items) >= expected_item_count:
                return items
            if attempt < max_attempts:
                time.sleep(attempt)
        return items

    def submit_chunks(
        self,
        graph_id: str,
        chunks: List[str],
        *,
        operation_id: str,
        batch_size: int = 350,
        progress_callback: ProgressCallback | None = None,
        submission_callback: SubmissionCallback | None = None,
    ) -> IngestionSubmission:
        """Submit chunks through Zep's Batch API.

        Mutating calls are deliberately not retried: create/add are not
        documented as idempotent, and an ambiguous replay can duplicate graph
        episodes. The returned identity lets callers persist and reconcile.
        """

        if not graph_id:
            raise ValueError("graph_id is required")
        self.validate_chunks(chunks, batch_size=batch_size)

        total_chunks = len(chunks)
        if submission_callback:
            # Journal the deterministic operation before the server-generated
            # batch ID POST, so a lost reply can still be diagnosed.
            submission_callback(None, operation_id)

        try:
            batch = self.client.batch.create(
                metadata={
                    "mirofish_operation_id": operation_id,
                    "graph_id": graph_id,
                    "chunk_count": total_chunks,
                }
            )
        except Exception as error:
            if not is_retryable_zep_error(error):
                raise
            batch = self._find_batch_by_operation_id(graph_id, operation_id)
            if batch is None:
                raise RuntimeError(
                    "Zep batch creation is unconfirmed and no matching operation was found"
                ) from error
        batch_id = getattr(batch, "batch_id", None)
        if not batch_id:
            raise RuntimeError("Zep Batch API returned no batch_id")
        if submission_callback:
            submission_callback(batch_id, operation_id)

        episode_uuids: List[str] = []
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    t(
                        'progress.sendingBatch',
                        current=batch_num,
                        total=total_batches,
                        chunks=len(batch_chunks),
                    ),
                    progress,
                )

            items = [
                BatchAddItem(
                    type="graph_episode",
                    graph_id=graph_id,
                    data=chunk,
                    data_type="text",
                    source_description="MiroFish source document chunk",
                    metadata={
                        "mirofish_operation_id": operation_id,
                        "chunk_index": i + offset,
                        "chunk_sha256": hashlib.sha256(
                            chunk.encode("utf-8")
                        ).hexdigest(),
                    },
                )
                for offset, chunk in enumerate(batch_chunks)
            ]

            expected_item_count = i + len(items)
            try:
                item_details = self.client.batch.add(
                    batch_id=batch_id,
                    items=items,
                )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        t('progress.batchFailed', batch=batch_num, error=str(e)), 0
                    )
                if is_retryable_zep_error(e):
                    recovered_items = self._reconcile_batch_item_count(
                        batch_id,
                        expected_item_count,
                    )
                    recovered_indexes = {
                        getattr(item, "sequence_index", None)
                        for item in recovered_items
                    }
                    if (
                        len(recovered_items) == expected_item_count
                        and recovered_indexes == set(range(expected_item_count))
                    ):
                        item_details = recovered_items[i:expected_item_count]
                    else:
                        raise RuntimeError(
                            f"Zep batch {batch_id} item submission is unconfirmed; "
                            "the draft was not processed or replayed"
                        ) from e
                else:
                    raise RuntimeError(
                        f"Zep batch {batch_id} item submission failed"
                    ) from e

            if len(item_details or []) != len(items):
                recovered_items = self._reconcile_batch_item_count(
                    batch_id,
                    expected_item_count,
                )
                recovered_indexes = {
                    getattr(item, "sequence_index", None)
                    for item in recovered_items
                }
                if (
                    len(recovered_items) == expected_item_count
                    and recovered_indexes == set(range(expected_item_count))
                ):
                    item_details = recovered_items[i:expected_item_count]
                else:
                    raise RuntimeError(
                        f"Zep batch {batch_id} acknowledged {len(item_details or [])} "
                        f"of {len(items)} items"
                    )
            for item in item_details:
                episode_uuid = getattr(item, "episode_uuid", None)
                if episode_uuid:
                    episode_uuids.append(episode_uuid)

        try:
            self.client.batch.process(batch_id=batch_id)
        except Exception as error:
            # A process response can be lost after the server accepted it.
            # Reconcile with a safe GET instead of issuing a second POST.
            summary = call_zep_read_with_retry(
                lambda: self.client.batch.get(batch_id=batch_id),
                operation_name=f"reconcile batch {batch_id}",
            )
            if getattr(summary, "status", None) in {None, "draft"}:
                raise RuntimeError(
                    f"Zep batch {batch_id} processing is unconfirmed"
                ) from error

        return IngestionSubmission(
            batch_id=batch_id,
            operation_id=operation_id,
            episode_uuids=episode_uuids,
            item_count=total_chunks,
        )

    def get_ingestion_status(self, batch_id: str) -> str | None:
        summary = call_zep_read_with_retry(
            lambda: self.client.batch.get(batch_id=batch_id),
            operation_name=f"get batch {batch_id}",
        )
        return getattr(summary, "status", None)

    def wait_for_ingestion(
        self,
        submission: IngestionSubmission,
        *,
        progress_callback: ProgressCallback | None = None,
        timeout: int | None = None,
    ) -> List[str]:
        """Wait for a Batch API terminal state and validate every item."""

        timeout = timeout or ZEP_INGESTION_WAIT_TIMEOUT_SECONDS
        start_time = time.time()
        terminal_states = {"succeeded", "partial", "failed", "invalid", "canceled"}

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Zep batch {submission.batch_id} did not finish within {timeout}s"
                )

            summary = call_zep_read_with_retry(
                lambda: self.client.batch.get(batch_id=submission.batch_id),
                operation_name=f"poll batch {submission.batch_id}",
            )
            status = getattr(summary, "status", None)
            progress = getattr(summary, "progress", None)
            percent = float(getattr(progress, "percent_complete", 0) or 0) / 100
            if progress_callback:
                completed = int(getattr(progress, "succeeded_items", 0) or 0)
                progress_callback(
                    t(
                        'progress.zepProcessing',
                        completed=completed,
                        total=submission.item_count,
                        pending=max(submission.item_count - completed, 0),
                        elapsed=int(time.time() - start_time),
                    ),
                    min(max(percent, 0.0), 1.0),
                )

            if status in terminal_states:
                break
            time.sleep(3)

        items = self._list_batch_items(submission.batch_id)
        if status != "succeeded":
            failed_items = [
                item for item in items
                if getattr(item, "status", None) not in {"succeeded", "skipped"}
            ]
            first_error = getattr(failed_items[0], "error", None) if failed_items else None
            raise RuntimeError(
                f"Zep batch {submission.batch_id} ended as {status}; "
                f"failed_items={len(failed_items)}; first_error={first_error}"
            )
        if len(items) != submission.item_count:
            raise RuntimeError(
                f"Zep batch {submission.batch_id} contains {len(items)} items, "
                f"expected {submission.item_count}"
            )

        ordered_items = sorted(
            items,
            key=lambda item: getattr(item, "sequence_index", 0) or 0,
        )
        episode_uuids: List[str] = []
        for item in ordered_items:
            item_status = getattr(item, "status", None)
            episode_uuid = getattr(item, "episode_uuid", None)
            source_uuid = getattr(item, "source_uuid", None)
            if item_status != "succeeded" or not episode_uuid:
                raise RuntimeError(
                    f"Zep batch {submission.batch_id} returned an incomplete item"
                )
            if source_uuid and source_uuid != episode_uuid:
                raise RuntimeError(
                    f"Zep batch {submission.batch_id} returned mismatched episode UUIDs"
                )
            episode_uuids.append(episode_uuid)

        if progress_callback:
            progress_callback(
                t(
                    'progress.processingComplete',
                    completed=len(episode_uuids),
                    total=submission.item_count,
                ),
                1.0,
            )
        return episode_uuids

    def add_text(
        self,
        graph_id: str,
        text: str,
        *,
        created_at: str | None = None,
        source_description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "graph_id": graph_id,
            "type": "text",
            "data": text,
            "source_description": source_description,
            "metadata": metadata,
        }
        if created_at is not None:
            kwargs["created_at"] = created_at
        episode = self.client.graph.add(**kwargs)
        episode_uuid = _uuid_of(episode)
        if not episode_uuid:
            raise RuntimeError("Zep graph.add returned no episode UUID")
        return episode_uuid

    @_translate_not_found
    def is_episode_processed(self, episode_uuid: str) -> bool:
        episode = call_zep_read_with_retry(
            lambda: self.client.graph.episode.get(uuid_=episode_uuid),
            operation_name=f"poll episode {episode_uuid}",
        )
        return bool(getattr(episode, "processed", False))

    # -- reads ---------------------------------------------------------
    @_translate_not_found
    def list_nodes(self, graph_id: str) -> List[GraphNode]:
        return [_to_node(node) for node in fetch_all_nodes(self.client, graph_id)]

    @_translate_not_found
    def list_edges(self, graph_id: str) -> List[GraphEdge]:
        return [_to_edge(edge) for edge in fetch_all_edges(self.client, graph_id)]

    def get_node(self, node_uuid: str) -> GraphNode | None:
        try:
            node = call_zep_read_with_retry(
                lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=f"get node {node_uuid[:8]}",
            )
        except NotFoundError:
            return None
        return _to_node(node) if node else None

    @_translate_not_found
    def get_node_edges(self, node_uuid: str) -> List[GraphEdge]:
        """Zep Cloud 3.25 returns only edges where the node is the source,
        despite documenting "all edges"; callers needing both directions must
        filter ``list_edges`` instead."""

        edges = call_zep_read_with_retry(
            lambda: self.client.graph.node.get_edges(node_uuid=node_uuid),
            operation_name=f"get node edges {node_uuid[:8]}",
        )
        return [_to_edge(edge) for edge in edges or []]

    @_translate_not_found
    def search(
        self,
        graph_id: str,
        query: str,
        *,
        limit: int = 10,
        scope: str = "edges",
        reranker: str | None = None,
    ) -> GraphSearchResults:
        kwargs: dict[str, Any] = {
            "graph_id": graph_id,
            "query": normalize_zep_search_query(query),
            "limit": normalize_zep_search_limit(limit),
            "scope": scope,
        }
        if reranker:
            kwargs["reranker"] = reranker
        response = call_zep_read_with_retry(
            lambda: self.client.graph.search(**kwargs),
            operation_name=f"graph search ({graph_id})",
        )
        return GraphSearchResults(
            edges=[_to_edge(e) for e in (getattr(response, "edges", None) or [])],
            nodes=[_to_node(n) for n in (getattr(response, "nodes", None) or [])],
        )
