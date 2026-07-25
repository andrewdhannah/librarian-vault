"""
Knowledge Vault — Search & Retrieval Layer

Provides vector search, full-text search, and hybrid search over indexed knowledge.
Every search result includes provenance information for governed retrieval.
"""

import re
import sqlite3
from typing import List, Dict, Optional
from .embedding import TFIDFEmbedder, vector_to_blob, blob_to_vector, cosine_similarity


def vector_search(conn: sqlite3.Connection, query: str, limit: int = 10,
                  model: str = "tfidf-v1", min_similarity: float = 0.1) -> List[Dict]:
    """
    Semantic search using vector embeddings.
    
    Args:
        conn: Database connection
        query: Search query string
        limit: Maximum results
        model: Embedding model name
        min_similarity: Minimum similarity threshold
    
    Returns:
        List of search results with provenance
    """
    # Get all embeddings
    rows = conn.execute(
        """SELECT e.chunk_id, e.vector, e.dimension, 
                  c.content, c.artifact_id, c.page_number, c.location,
                  a.title, a.source_type, a.source_extension
           FROM embeddings e
           JOIN chunks c ON e.chunk_id = c.chunk_id
           JOIN artifacts a ON c.artifact_id = a.artifact_id
           WHERE e.model = ?""",
        (model,)
    ).fetchall()
    
    if not rows:
        return []
    
    # Embed query
    embedder = TFIDFEmbedder(dimension=rows[0]["dimension"])
    
    # Fit on corpus
    corpus_texts = [r["content"] for r in rows]
    embedder.fit(corpus_texts)
    query_vector = embedder.embed(query)
    
    # Compute similarities
    results = []
    for row in rows:
        chunk_vector = blob_to_vector(row["vector"], row["dimension"])
        similarity = cosine_similarity(query_vector, chunk_vector)
        
        if similarity < min_similarity:
            continue
        
        # Get provenance
        provenance = conn.execute(
            """SELECT source_extension, source_receipt_id, 
                      source_content_hash, verification_status
               FROM provenance WHERE chunk_id = ?""",
            (row["chunk_id"],)
        ).fetchone()
        
        results.append({
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "artifact_id": row["artifact_id"],
            "page_number": row["page_number"],
            "location": row["location"],
            "title": row["title"],
            "source_type": row["source_type"],
            "source_extension": row["source_extension"],
            "similarity": round(similarity, 4),
            "provenance": {
                "source_extension": provenance["source_extension"] if provenance else None,
                "receipt_id": provenance["source_receipt_id"] if provenance else None,
                "content_hash": provenance["source_content_hash"] if provenance else None,
                "verified": provenance["verification_status"] == "verified" if provenance else False,
            }
        })
    
    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


def fulltext_search(conn: sqlite3.Connection, query: str, limit: int = 10) -> List[Dict]:
    """
    Full-text search over indexed chunks.
    
    Args:
        conn: Database connection
        query: Search query string
        limit: Maximum results
    
    Returns:
        List of search results
    """
    # Use SQLite FTS or LIKE for basic text search
    tokens = query.lower().split()
    
    # Build WHERE clause
    conditions = []
    params = []
    for token in tokens:
        conditions.append("LOWER(c.content) LIKE ?")
        params.append(f"%{token}%")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    rows = conn.execute(
        f"""SELECT c.chunk_id, c.content, c.artifact_id, c.page_number, c.location,
                   a.title, a.source_type, a.source_extension
            FROM chunks c
            JOIN artifacts a ON c.artifact_id = a.artifact_id
            WHERE {where_clause}
            LIMIT ?""",
        params + [limit]
    ).fetchall()
    
    results = []
    for row in rows:
        # Simple relevance score based on query term frequency
        content_lower = row["content"].lower()
        score = sum(1 for t in tokens if t in content_lower) / len(tokens) if tokens else 0
        
        results.append({
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "artifact_id": row["artifact_id"],
            "page_number": row["page_number"],
            "location": row["location"],
            "title": row["title"],
            "source_type": row["source_type"],
            "source_extension": row["source_extension"],
            "relevance": round(score, 4),
        })
    
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results


def hybrid_search(conn: sqlite3.Connection, query: str, limit: int = 10,
                  vector_weight: float = 0.7, text_weight: float = 0.3,
                  min_score: float = 0.0) -> List[Dict]:
    """
    Hybrid search combining vector similarity and full-text relevance.
    
    Args:
        conn: Database connection
        query: Search query string
        limit: Maximum results
        vector_weight: Weight for vector similarity
        text_weight: Weight for text relevance
        min_score: Minimum combined score threshold
    
    Returns:
        List of search results with combined scores
    """
    # Get results from both methods
    vector_results = vector_search(conn, query, limit=limit * 2)
    text_results = fulltext_search(conn, query, limit=limit * 2)
    
    # Merge by chunk_id
    combined = {}
    
    for r in vector_results:
        cid = r["chunk_id"]
        combined[cid] = {
            **r,
            "vector_score": r["similarity"],
            "text_score": 0.0,
        }
    
    for r in text_results:
        cid = r["chunk_id"]
        if cid in combined:
            combined[cid]["text_score"] = r["relevance"]
        else:
            combined[cid] = {
                **r,
                "vector_score": 0.0,
                "text_score": r["relevance"],
            }
    
    # Compute combined score
    results = []
    for cid, data in combined.items():
        combined_score = (
            vector_weight * data.get("vector_score", 0) +
            text_weight * data.get("text_score", 0)
        )
        if combined_score >= min_score:
            results.append({
                **data,
                "combined_score": round(combined_score, 4),
            })
    
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results[:limit]


def retrieve_context(conn: sqlite3.Connection, query: str, 
                     max_chunks: int = 5, min_score: float = 0.1) -> Dict:
    """
    Retrieve relevant context for a query with full provenance.
    This is the main retrieval interface for agents.
    
    Args:
        conn: Database connection
        query: User query
        max_chunks: Maximum chunks to retrieve
        min_score: Minimum relevance score
    
    Returns:
        Dict with context, sources, and verification status
    """
    results = hybrid_search(conn, query, limit=max_chunks)
    
    # Filter by minimum score
    results = [r for r in results if r.get("combined_score", 0) >= min_score]
    
    # Build context
    context_parts = []
    sources = []
    
    for i, r in enumerate(results):
        context_parts.append(f"[{i+1}] {r['content']}")
        
        source_info = {
            "chunk_id": r["chunk_id"],
            "artifact_id": r.get("artifact_id"),
            "title": r.get("title"),
            "source_type": r.get("source_type"),
            "source_extension": r.get("source_extension"),
            "page_number": r.get("page_number"),
            "score": r.get("combined_score"),
            "provenance": r.get("provenance", {}),
        }
        sources.append(source_info)
    
    return {
        "query": query,
        "context": "\n\n".join(context_parts),
        "sources": sources,
        "total_chunks": len(results),
        "max_chunks": max_chunks,
    }
