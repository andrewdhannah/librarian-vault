"""
Knowledge Vault — MCP Tool Implementations

Tools exposed via the MCP server:
- vault.ingest: Feed an IngestionResult into the vault
- vault.search: Search indexed knowledge
- vault.retrieve: Retrieve context for a query
- vault.verify: Verify provenance of a chunk or artifact
- vault.status: Get vault statistics
- vault.artifacts: List indexed artifacts
"""

import json
import sys
import os
import hashlib
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.vault.database import init_db, get_db_path, get_vault_stats
from src.vault.ingestion import receive_ingestion, list_artifacts, get_artifact
from src.vault.chunking import auto_chunk
from src.vault.embedding import embed_chunks, store_embeddings
from src.vault.search import hybrid_search, retrieve_context
from src.vault.provenance import verify_chunk_provenance, verify_artifact_provenance, get_verification_summary
from src.vault.context import assemble_context, format_context_for_agent


def _get_conn():
    """Get database connection."""
    return init_db()


def vault_ingest(arguments: dict) -> dict:
    """
    Feed an IngestionResult into the vault.
    
    Accepts:
    - ingestion_result: The IngestionResult dict from a source extension
    - source_extension: ID of the source extension
    - receipt_id: Optional receipt ID from validation
    
    Returns:
    - status: 'ingested', 'already_indexed', or 'error'
    - artifact_id: ID of the indexed artifact
    - chunks_added: Number of chunks added
    """
    ingestion_result = arguments.get("ingestion_result")
    source_extension = arguments.get("source_extension", "unknown")
    receipt_id = arguments.get("receipt_id")
    
    if not ingestion_result:
        return {"error": "Missing required field: ingestion_result"}
    
    conn = _get_conn()
    
    try:
        # Receive into vault
        result = receive_ingestion(conn, ingestion_result, source_extension, receipt_id)
        
        if result["status"] == "ingested" and result["chunks_added"] > 0:
            # Chunk the content
            content_units = ingestion_result.get("content_units", [])
            source_type = ingestion_result.get("source_identity", {}).get("source_type", "unknown")
            chunks = auto_chunk(content_units, source_type)
            
            # Generate embeddings
            if chunks:
                vectors = embed_chunks(chunks)
                chunk_ids = list(vectors.keys())
                vector_list = list(vectors.values())
                store_embeddings(conn, chunk_ids, vector_list)
        
        return result
    
    finally:
        conn.close()


def vault_search(arguments: dict) -> dict:
    """
    Search indexed knowledge.
    
    Accepts:
    - query: Search query string
    - limit: Maximum results (default: 10)
    - min_score: Minimum relevance score (default: 0.1)
    
    Returns:
    - results: List of search results with provenance
    """
    query = arguments.get("query")
    limit = arguments.get("limit", 10)
    min_score = arguments.get("min_score", 0.1)
    
    if not query:
        return {"error": "Missing required field: query"}
    
    conn = _get_conn()
    
    try:
        results = hybrid_search(conn, query, limit=limit, min_score=min_score)
        return {
            "query": query,
            "results": results,
            "total": len(results),
        }
    finally:
        conn.close()


def vault_retrieve(arguments: dict) -> dict:
    """
    Retrieve context for a query with full provenance.
    
    Accepts:
    - query: User query
    - max_chunks: Maximum chunks to retrieve (default: 5)
    - min_score: Minimum relevance score (default: 0.1)
    - include_citations: Whether to include citation details (default: true)
    
    Returns:
    - context: Assembled context string
    - citations: List of citations
    - source_summary: Summary of sources
    """
    query = arguments.get("query")
    max_chunks = arguments.get("max_chunks", 5)
    min_score = arguments.get("min_score", 0.1)
    include_citations = arguments.get("include_citations", True)
    
    if not query:
        return {"error": "Missing required field: query"}
    
    conn = _get_conn()
    
    try:
        # Retrieve relevant chunks
        retrieval = retrieve_context(conn, query, max_chunks=max_chunks, min_score=min_score)
        
        # Assemble context with citations
        assembled = assemble_context(conn, retrieval["sources"], max_chunks=max_chunks)
        
        # Format for agent
        formatted = format_context_for_agent(assembled, include_citations=include_citations)
        
        return {
            "query": query,
            "context": formatted,
            "citations": assembled["citations"],
            "source_summary": assembled["source_summary"],
            "total_chunks": retrieval["total_chunks"],
        }
    finally:
        conn.close()


def vault_verify(arguments: dict) -> dict:
    """
    Verify provenance of a chunk or artifact.
    
    Accepts:
    - chunk_id: Verify a specific chunk
    - artifact_id: Verify all chunks in an artifact
    
    Returns:
    - verification: Verification results
    """
    chunk_id = arguments.get("chunk_id")
    artifact_id = arguments.get("artifact_id")
    
    if not chunk_id and not artifact_id:
        return {"error": "Provide either chunk_id or artifact_id"}
    
    conn = _get_conn()
    
    try:
        if chunk_id:
            return verify_chunk_provenance(conn, chunk_id)
        else:
            return verify_artifact_provenance(conn, artifact_id)
    finally:
        conn.close()


def vault_status(arguments: dict) -> dict:
    """
    Get vault statistics.
    
    Accepts: (none)
    
    Returns:
    - schema_version: Database schema version
    - artifacts: Number of indexed artifacts
    - chunks: Number of indexed chunks
    - embeddings: Number of embedding vectors
    - verification: Verification statistics
    """
    conn = _get_conn()
    
    try:
        stats = get_vault_stats(conn)
        verification = get_verification_summary(conn)
        return {
            **stats,
            "verification": verification,
        }
    finally:
        conn.close()


def vault_artifacts(arguments: dict) -> dict:
    """
    List indexed artifacts.
    
    Accepts:
    - limit: Maximum artifacts to return (default: 50)
    
    Returns:
    - artifacts: List of artifacts
    """
    limit = arguments.get("limit", 50)
    
    conn = _get_conn()
    
    try:
        artifacts = list_artifacts(conn, limit=limit)
        return {
            "artifacts": artifacts,
            "total": len(artifacts),
        }
    finally:
        conn.close()


# ─── Tool Router ───────────────────────────────────────────────────

TOOLS = {
    "vault_ingest": vault_ingest,
    "vault_search": vault_search,
    "vault_retrieve": vault_retrieve,
    "vault_verify": vault_verify,
    "vault_status": vault_status,
    "vault_artifacts": vault_artifacts,
}


def call_tool(tool_name: str, arguments: dict) -> dict:
    """Route a tool call to the appropriate handler."""
    handler = TOOLS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    
    try:
        result = handler(arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": str(e)}, indent=2)}]
        }
