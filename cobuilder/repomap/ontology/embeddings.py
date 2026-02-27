"""Vector embedding pipeline for feature ontology nodes.

Implements Task 2.1.3 of PRD-RPG-P2-001: batch-embeds FeatureNode objects
using the existing EmbeddingGenerator from the vectordb module, with rate
limiting, retry logic, and configurable batch sizes.

Example::

    embedder = FeatureEmbedder()
    nodes = [FeatureNode(id="ml", name="ML", level=0), ...]
    embedded = embedder.embed_nodes(nodes)
    # Each node now has its ``embedding`` field populated.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.vectordb.embeddings import EmbeddingGenerator
from cobuilder.repomap.vectordb.exceptions import EmbeddingError

logger = logging.getLogger(__name__)


class EmbedderConfig(BaseModel):
    """Configuration for the FeatureEmbedder pipeline."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformer model name for embedding generation",
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of nodes to embed per batch",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed batches",
    )
    retry_delay: float = Field(
        default=1.0,
        gt=0.0,
        description="Base delay in seconds between retries (exponential backoff)",
    )
    rate_limit_delay: float = Field(
        default=0.0,
        ge=0.0,
        description="Delay in seconds between batches for rate limiting (0 = no delay)",
    )


class EmbeddingResult(BaseModel):
    """Result of a batch embedding operation."""

    model_config = ConfigDict(frozen=True)

    total_nodes: int = Field(
        ..., ge=0, description="Total number of nodes processed"
    )
    embedded_count: int = Field(
        ..., ge=0, description="Number of nodes successfully embedded"
    )
    failed_count: int = Field(
        ..., ge=0, description="Number of nodes that failed to embed"
    )
    skipped_count: int = Field(
        ..., ge=0, description="Number of nodes skipped (already had embeddings)"
    )
    elapsed_seconds: float = Field(
        ..., ge=0.0, description="Total elapsed time in seconds"
    )
    model_name: str = Field(
        ..., description="Embedding model used"
    )

    @property
    def success_rate(self) -> float:
        """Return the fraction of nodes successfully embedded."""
        if self.total_nodes == 0:
            return 1.0
        return self.embedded_count / self.total_nodes

    def __repr__(self) -> str:
        return (
            f"EmbeddingResult(total={self.total_nodes}, "
            f"embedded={self.embedded_count}, "
            f"failed={self.failed_count}, "
            f"skipped={self.skipped_count}, "
            f"elapsed={self.elapsed_seconds:.2f}s)"
        )


class FeatureEmbedder:
    """Batch-embeds FeatureNode objects using sentence-transformers.

    Leverages the existing :class:`~zerorepo.vectordb.embeddings.EmbeddingGenerator`
    for the actual embedding computation, adding batch processing, retry logic,
    and rate limiting on top.

    Example::

        embedder = FeatureEmbedder()
        nodes = [FeatureNode(id="auth", name="Authentication", level=1), ...]
        result = embedder.embed_nodes(nodes)
        print(result)  # EmbeddingResult(total=5, embedded=5, ...)
    """

    def __init__(
        self,
        config: EmbedderConfig | None = None,
        generator: EmbeddingGenerator | None = None,
    ) -> None:
        """Initialize the FeatureEmbedder.

        Args:
            config: Optional configuration. Defaults to sensible values.
            generator: Optional pre-configured EmbeddingGenerator. If not
                provided, a new one is created using config.model_name.
        """
        self._config = config or EmbedderConfig()
        self._generator = generator or EmbeddingGenerator(
            model_name=self._config.model_name
        )

    @property
    def config(self) -> EmbedderConfig:
        """Return the embedder configuration."""
        return self._config

    @property
    def generator(self) -> EmbeddingGenerator:
        """Return the underlying EmbeddingGenerator."""
        return self._generator

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed. Must not be empty.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            ValueError: If text is empty or whitespace-only.
            EmbeddingError: If embedding generation fails.
        """
        return self._generator.embed(text)

    def embed_node(
        self,
        node: FeatureNode,
        overwrite: bool = False,
    ) -> FeatureNode:
        """Embed a single FeatureNode.

        Uses ``node.embedding_input()`` to generate the text for embedding.
        If the node already has an embedding and ``overwrite`` is False, the
        node is returned unchanged.

        Args:
            node: The feature node to embed.
            overwrite: If True, re-embed even if the node already has an
                embedding. Defaults to False.

        Returns:
            The node with its ``embedding`` field populated.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if node.embedding is not None and not overwrite:
            return node

        text = node.embedding_input()
        embedding = self._generator.embed(text)
        node.embedding = embedding
        return node

    def embed_nodes(
        self,
        nodes: list[FeatureNode],
        overwrite: bool = False,
    ) -> EmbeddingResult:
        """Batch-embed a list of FeatureNodes.

        Processes nodes in batches according to ``config.batch_size``, with
        retry logic and rate limiting between batches.

        Nodes that already have embeddings are skipped unless ``overwrite``
        is True.

        Args:
            nodes: The feature nodes to embed.
            overwrite: If True, re-embed all nodes. Defaults to False.

        Returns:
            An :class:`EmbeddingResult` summarising the operation.
        """
        if not nodes:
            return EmbeddingResult(
                total_nodes=0,
                embedded_count=0,
                failed_count=0,
                skipped_count=0,
                elapsed_seconds=0.0,
                model_name=self._generator.model_name,
            )

        start = time.monotonic()
        embedded_count = 0
        failed_count = 0
        skipped_count = 0

        # Separate nodes needing embedding from those to skip
        to_embed: list[FeatureNode] = []
        for node in nodes:
            if node.embedding is not None and not overwrite:
                skipped_count += 1
            else:
                to_embed.append(node)

        # Process in batches
        batch_size = self._config.batch_size
        for batch_start in range(0, len(to_embed), batch_size):
            batch = to_embed[batch_start : batch_start + batch_size]

            success = self._embed_batch_with_retry(batch)
            if success:
                embedded_count += len(batch)
            else:
                failed_count += len(batch)

            # Rate limiting between batches
            if (
                self._config.rate_limit_delay > 0
                and batch_start + batch_size < len(to_embed)
            ):
                time.sleep(self._config.rate_limit_delay)

        elapsed = time.monotonic() - start

        result = EmbeddingResult(
            total_nodes=len(nodes),
            embedded_count=embedded_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            elapsed_seconds=elapsed,
            model_name=self._generator.model_name,
        )

        logger.info(
            "Embedding complete: %d embedded, %d failed, %d skipped in %.2fs",
            embedded_count,
            failed_count,
            skipped_count,
            elapsed,
        )

        return result

    def _embed_batch_with_retry(self, batch: list[FeatureNode]) -> bool:
        """Embed a single batch of nodes with retry logic.

        Args:
            batch: A list of FeatureNodes to embed in this batch.

        Returns:
            True if all nodes in the batch were successfully embedded,
            False if all retries were exhausted.
        """
        texts = [node.embedding_input() for node in batch]

        for attempt in range(self._config.max_retries + 1):
            try:
                embeddings = self._generator.embed_batch(texts)

                # Assign embeddings back to nodes
                for node, embedding in zip(batch, embeddings):
                    node.embedding = embedding

                return True

            except EmbeddingError as exc:
                logger.warning(
                    "Batch embedding attempt %d/%d failed: %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )
                if attempt < self._config.max_retries:
                    delay = self._config.retry_delay * (2**attempt)
                    time.sleep(delay)

        logger.error(
            "Batch embedding failed after %d attempts for %d nodes",
            self._config.max_retries + 1,
            len(batch),
        )
        return False

    def get_embedding_texts(self, nodes: list[FeatureNode]) -> list[str]:
        """Extract embedding input texts from a list of nodes.

        Useful for inspecting what text will be embedded without actually
        generating embeddings.

        Args:
            nodes: The feature nodes to extract text from.

        Returns:
            A list of embedding input strings in the same order.
        """
        return [node.embedding_input() for node in nodes]
