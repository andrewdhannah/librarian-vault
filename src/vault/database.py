"""
Knowledge Vault — Database Schema

SQLite schema for the governed knowledge layer.
Indexes artifacts, chunks, embeddings, provenance, and search results.

Schema version: 1.0.0
"""

import sqlite3
import os
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0.0"

SCHEMA_SQL = """
-- Vault metadata
CREATE TABLE IF NOT EXISTS vault_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexed artifacts (knowledge objects from source extensions)
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    source_extension TEXT NOT NULL,
    source_receipt_id TEXT,
    source_reference TEXT,
    title TEXT,
    author TEXT,
    source_type TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'indexed',
    UNIQUE(source_hash)
);

-- Content chunks (indexed units of knowledge)
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    page_number INTEGER,
    location TEXT,
    token_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

-- Embedding vectors
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id TEXT NOT NULL,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    dimension INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chunk_id, model),
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Provenance chain (tracks origin of every chunk)
CREATE TABLE IF NOT EXISTS provenance (
    chunk_id TEXT PRIMARY KEY,
    source_extension TEXT NOT NULL,
    source_receipt_id TEXT,
    source_evidence_path TEXT,
    source_content_hash TEXT NOT NULL,
    ingestion_receipt_id TEXT,
    verified_at TEXT,
    verification_status TEXT DEFAULT 'pending',
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Search index (full-text search over chunks)
CREATE TABLE IF NOT EXISTS search_index (
    chunk_id TEXT PRIMARY KEY,
    content_tokens TEXT NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Ingestion log (tracks what was fed into the vault)
CREATE TABLE IF NOT EXISTS ingestion_log (
    log_id TEXT PRIMARY KEY,
    source_extension TEXT NOT NULL,
    source_receipt_id TEXT NOT NULL,
    artifact_id TEXT,
    chunks_added INTEGER DEFAULT 0,
    chunks_skipped INTEGER DEFAULT 0,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'success'
);
"""


def get_db_path(storage_dir: str = None) -> str:
    """Get the path to the vault database."""
    if storage_dir is None:
        storage_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), "storage")
    os.makedirs(storage_dir, exist_ok=True)
    return os.path.join(storage_dir, "knowledge.db")


def init_db(db_path: str = None) -> sqlite3.Connection:
    """Initialize the vault database with schema."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    # Set schema version
    conn.execute(
        "INSERT OR REPLACE INTO vault_meta (key, value, updated_at) VALUES (?, ?, ?)",
        ("schema_version", SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    return conn


def get_schema_version(conn: sqlite3.Connection) -> str:
    """Get the current schema version."""
    row = conn.execute("SELECT value FROM vault_meta WHERE key = 'schema_version'").fetchone()
    return row["value"] if row else "unknown"


def get_vault_stats(conn: sqlite3.Connection) -> dict:
    """Get vault statistics."""
    artifacts = conn.execute("SELECT COUNT(*) as n FROM artifacts").fetchone()["n"]
    chunks = conn.execute("SELECT COUNT(*) as n FROM chunks").fetchone()["n"]
    embeddings = conn.execute("SELECT COUNT(*) as n FROM embeddings").fetchone()["n"]
    provenance = conn.execute("SELECT COUNT(*) as n FROM provenance").fetchone()["n"]
    indexed = conn.execute("SELECT COUNT(*) as n FROM artifacts WHERE status = 'indexed'").fetchone()["n"]
    return {
        "schema_version": get_schema_version(conn),
        "artifacts": artifacts,
        "indexed_artifacts": indexed,
        "chunks": chunks,
        "embeddings": embeddings,
        "provenance_records": provenance,
    }
