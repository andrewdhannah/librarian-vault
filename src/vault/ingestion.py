"""
Knowledge Vault — Ingestion Receiver

Accepts IngestionResult from source extensions and feeds them into the vault.
The receiver is the entry point for all knowledge entering the vault.

Flow:
    Source Extension → IngestionResult → Receiver → Chunker → Embedder → Index
"""

import json
import hashlib
import sqlite3
from datetime import datetime, timezone


def receive_ingestion(conn: sqlite3.Connection, ingestion_result: dict,
                      source_extension: str, receipt_id: str = None) -> dict:
    """
    Accept an IngestionResult from a source extension.
    
    Args:
        conn: Database connection
        ingestion_result: The IngestionResult dict from the source
        source_extension: ID of the source extension
        receipt_id: Optional receipt ID from validation
    
    Returns:
        dict with ingestion summary
    """
    source_identity = ingestion_result.get("source_identity", {})
    document_metadata = ingestion_result.get("document_metadata", {})
    content_units = ingestion_result.get("content_units", [])
    
    source_hash = source_identity.get("source_hash", "")
    source_type = source_identity.get("source_type", "unknown")
    title = document_metadata.get("title", "Untitled")
    author = document_metadata.get("author", "Unknown")
    page_count = document_metadata.get("page_count", 0)
    
    # Generate artifact ID
    artifact_id = f"AV-{hashlib.sha256(source_hash.encode()).hexdigest()[:16]}"
    
    # Check if already indexed
    existing = conn.execute(
        "SELECT artifact_id FROM artifacts WHERE source_hash = ?",
        (source_hash,)
    ).fetchone()
    
    if existing:
        return {
            "status": "already_indexed",
            "artifact_id": existing["artifact_id"],
            "chunks_added": 0,
            "chunks_skipped": len(content_units),
        }
    
    # Insert artifact
    conn.execute(
        """INSERT INTO artifacts 
           (artifact_id, source_extension, source_receipt_id, source_reference,
            title, author, source_type, source_hash, page_count, chunk_count, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'indexed')""",
        (artifact_id, source_extension, receipt_id, source_hash,
         title, author, source_type, source_hash, page_count, len(content_units))
    )
    
    # Insert chunks
    chunks_added = 0
    chunks_skipped = 0
    
    for i, unit in enumerate(content_units):
        content = unit.get("text", "")
        content_hash = unit.get("content_hash", "")
        page_number = unit.get("page_number")
        location = unit.get("location")
        unit_id = unit.get("unit_id", f"{artifact_id}-chunk-{i:04d}")
        
        # Skip empty content
        if not content.strip():
            chunks_skipped += 1
            continue
        
        # Check for duplicate chunk
        existing_chunk = conn.execute(
            "SELECT chunk_id FROM chunks WHERE content_hash = ?",
            (content_hash,)
        ).fetchone()
        
        if existing_chunk:
            chunks_skipped += 1
            continue
        
        chunk_id = f"CK-{content_hash[:16]}"
        
        conn.execute(
            """INSERT INTO chunks 
               (chunk_id, artifact_id, chunk_index, content, content_hash,
                page_number, location, token_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, artifact_id, i, content, content_hash,
             page_number, location, len(content.split()))
        )
        
        # Insert provenance
        conn.execute(
            """INSERT INTO provenance
               (chunk_id, source_extension, source_receipt_id, source_content_hash,
                ingestion_receipt_id, verification_status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (chunk_id, source_extension, receipt_id, content_hash, receipt_id)
        )
        
        chunks_added += 1
    
    # Log ingestion
    log_id = f"LOG-{hashlib.sha256(receipt_id.encode()).hexdigest()[:16]}" if receipt_id else f"LOG-{hashlib.sha256(source_hash.encode()).hexdigest()[:16]}"
    conn.execute(
        """INSERT INTO ingestion_log
           (log_id, source_extension, source_receipt_id, artifact_id,
            chunks_added, chunks_skipped, status)
           VALUES (?, ?, ?, ?, ?, ?, 'success')""",
        (log_id, source_extension, receipt_id or "", artifact_id,
         chunks_added, chunks_skipped)
    )
    
    conn.commit()
    
    return {
        "status": "ingested",
        "artifact_id": artifact_id,
        "chunks_added": chunks_added,
        "chunks_skipped": chunks_skipped,
        "total_units": len(content_units),
    }


def list_artifacts(conn: sqlite3.Connection, limit: int = 50) -> list:
    """List indexed artifacts."""
    rows = conn.execute(
        """SELECT artifact_id, source_extension, title, author, source_type,
                  page_count, chunk_count, indexed_at, status
           FROM artifacts ORDER BY indexed_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_artifact(conn: sqlite3.Connection, artifact_id: str) -> dict:
    """Get artifact details including chunks."""
    artifact = conn.execute(
        "SELECT * FROM artifacts WHERE artifact_id = ?",
        (artifact_id,)
    ).fetchone()
    if not artifact:
        return None
    
    chunks = conn.execute(
        """SELECT chunk_id, chunk_index, content, page_number, location, token_count
           FROM chunks WHERE artifact_id = ? ORDER BY chunk_index""",
        (artifact_id,)
    ).fetchall()
    
    provenance = conn.execute(
        """SELECT chunk_id, source_extension, source_receipt_id,
                  verification_status, verified_at
           FROM provenance WHERE chunk_id IN 
           (SELECT chunk_id FROM chunks WHERE artifact_id = ?)""",
        (artifact_id,)
    ).fetchall()
    
    return {
        "artifact": dict(artifact),
        "chunks": [dict(c) for c in chunks],
        "provenance": [dict(p) for p in provenance],
    }
