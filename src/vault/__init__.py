"""
Knowledge Vault

The searchable memory layer for governed knowledge.
Accepts ingestion results from source extensions, indexes them,
and provides verified retrieval with full provenance.
"""

from .database import init_db, get_db_path, get_vault_stats
from .ingestion import receive_ingestion, list_artifacts, get_artifact
from .chunking import auto_chunk
from .embedding import embed_chunks, TFIDFEmbedder
from .search import vector_search, fulltext_search, hybrid_search, retrieve_context
from .provenance import verify_chunk_provenance, verify_artifact_provenance, get_verification_summary
from .context import assemble_context, format_context_for_agent

__all__ = [
    "init_db", "get_db_path", "get_vault_stats",
    "receive_ingestion", "list_artifacts", "get_artifact",
    "auto_chunk",
    "embed_chunks", "TFIDFEmbedder",
    "vector_search", "fulltext_search", "hybrid_search", "retrieve_context",
    "verify_chunk_provenance", "verify_artifact_provenance", "get_verification_summary",
    "assemble_context", "format_context_for_agent",
]
