"""
Knowledge Vault — Provenance Verification

Verifies the chain of custody from source extension to vault index.
Every answer can be traced back to its origin through provenance records.
"""

import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timezone


def verify_chunk_provenance(conn: sqlite3.Connection, chunk_id: str) -> Dict:
    """
    Verify provenance chain for a single chunk.
    
    Checks:
    1. Chunk exists in vault
    2. Provenance record exists
    3. Source extension is recorded
    4. Content hash matches
    5. Verification status
    
    Args:
        conn: Database connection
        chunk_id: Chunk to verify
    
    Returns:
        Dict with verification results
    """
    # Get chunk
    chunk = conn.execute(
        "SELECT * FROM chunks WHERE chunk_id = ?",
        (chunk_id,)
    ).fetchone()
    
    if not chunk:
        return {
            "status": "not_found",
            "chunk_id": chunk_id,
            "verified": False,
            "errors": ["Chunk not found in vault"],
        }
    
    # Get provenance
    provenance = conn.execute(
        "SELECT * FROM provenance WHERE chunk_id = ?",
        (chunk_id,)
    ).fetchone()
    
    if not provenance:
        return {
            "status": "no_provenance",
            "chunk_id": chunk_id,
            "verified": False,
            "errors": ["No provenance record for chunk"],
        }
    
    errors = []
    warnings = []
    
    # Check source extension
    if not provenance["source_extension"]:
        errors.append("Missing source extension")
    
    # Check content hash consistency
    if provenance["source_content_hash"] != chunk["content_hash"]:
        warnings.append("Content hash mismatch between provenance and chunk")
    
    # Check receipt reference
    if not provenance["source_receipt_id"]:
        warnings.append("No source receipt reference")
    
    # Check evidence path
    if not provenance["source_evidence_path"]:
        warnings.append("No evidence path recorded")
    
    # Determine verification status
    verified = len(errors) == 0
    status = "verified" if verified else "failed"
    
    # Update verification status in database
    conn.execute(
        """UPDATE provenance 
           SET verification_status = ?, verified_at = ?
           WHERE chunk_id = ?""",
        (status, datetime.now(timezone.utc).isoformat(), chunk_id)
    )
    conn.commit()
    
    return {
        "status": status,
        "chunk_id": chunk_id,
        "verified": verified,
        "source_extension": provenance["source_extension"],
        "source_receipt_id": provenance["source_receipt_id"],
        "source_evidence_path": provenance["source_evidence_path"],
        "content_hash": chunk["content_hash"],
        "errors": errors,
        "warnings": warnings,
    }


def verify_artifact_provenance(conn: sqlite3.Connection, artifact_id: str) -> Dict:
    """
    Verify provenance for all chunks in an artifact.
    
    Args:
        conn: Database connection
        artifact_id: Artifact to verify
    
    Returns:
        Dict with verification summary
    """
    # Get all chunks for artifact
    chunks = conn.execute(
        "SELECT chunk_id FROM chunks WHERE artifact_id = ?",
        (artifact_id,)
    ).fetchall()
    
    if not chunks:
        return {
            "status": "not_found",
            "artifact_id": artifact_id,
            "verified": False,
            "errors": ["Artifact not found or has no chunks"],
        }
    
    results = []
    all_verified = True
    total_errors = 0
    total_warnings = 0
    
    for chunk in chunks:
        result = verify_chunk_provenance(conn, chunk["chunk_id"])
        results.append(result)
        if not result["verified"]:
            all_verified = False
        total_errors += len(result.get("errors", []))
        total_warnings += len(result.get("warnings", []))
    
    return {
        "status": "verified" if all_verified else "partial",
        "artifact_id": artifact_id,
        "verified": all_verified,
        "chunks_verified": len(results),
        "chunks_total": len(chunks),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "details": results,
    }


def verify_search_result(conn: sqlite3.Connection, chunk_id: str) -> Dict:
    """
    Verify provenance for a search result before returning to agent.
    This is the verification step in governed retrieval.
    
    Args:
        conn: Database connection
        chunk_id: Chunk from search result
    
    Returns:
        Dict with verification and source chain
    """
    verification = verify_chunk_provenance(conn, chunk_id)
    
    # Get full source chain
    chunk = conn.execute(
        """SELECT c.*, a.title, a.source_type, a.source_extension, a.source_hash
           FROM chunks c
           JOIN artifacts a ON c.artifact_id = a.artifact_id
           WHERE c.chunk_id = ?""",
        (chunk_id,)
    ).fetchone()
    
    source_chain = None
    if chunk:
        source_chain = {
            "artifact_id": chunk["artifact_id"],
            "title": chunk["title"],
            "source_type": chunk["source_type"],
            "source_extension": chunk["source_extension"],
            "source_hash": chunk["source_hash"],
            "page_number": chunk["page_number"],
            "location": chunk["location"],
            "content_hash": chunk["content_hash"],
        }
    
    return {
        "verification": verification,
        "source_chain": source_chain,
    }


def get_verification_summary(conn: sqlite3.Connection) -> Dict:
    """
    Get overall verification status for the vault.
    
    Returns:
        Dict with verification statistics
    """
    total_chunks = conn.execute("SELECT COUNT(*) as n FROM chunks").fetchone()["n"]
    total_provenance = conn.execute("SELECT COUNT(*) as n FROM provenance").fetchone()["n"]
    verified = conn.execute(
        "SELECT COUNT(*) as n FROM provenance WHERE verification_status = 'verified'"
    ).fetchone()["n"]
    pending = conn.execute(
        "SELECT COUNT(*) as n FROM provenance WHERE verification_status = 'pending'"
    ).fetchone()["n"]
    failed = conn.execute(
        "SELECT COUNT(*) as n FROM provenance WHERE verification_status = 'failed'"
    ).fetchone()["n"]
    
    return {
        "total_chunks": total_chunks,
        "total_provenance": total_provenance,
        "verified": verified,
        "pending": pending,
        "failed": failed,
        "coverage": round(total_provenance / total_chunks * 100, 1) if total_chunks > 0 else 0,
        "verification_rate": round(verified / total_provenance * 100, 1) if total_provenance > 0 else 0,
    }
