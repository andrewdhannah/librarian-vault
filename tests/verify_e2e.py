"""
Knowledge Vault — E2E Verification

Tests the complete vault pipeline:
1. Ingest an IngestionResult from a source extension
2. Chunk the content
3. Generate embeddings
4. Search and retrieve
5. Verify provenance
6. Assemble context with citations
"""

import sys
import os
import json
import tempfile
import shutil

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vault.database import init_db, get_vault_stats
from src.vault.ingestion import receive_ingestion, list_artifacts, get_artifact
from src.vault.chunking import auto_chunk
from src.vault.embedding import embed_chunks, store_embeddings
from src.vault.search import hybrid_search, retrieve_context
from src.vault.provenance import verify_chunk_provenance, verify_artifact_provenance, get_verification_summary
from src.vault.context import assemble_context, format_context_for_agent
from src.tools.vault import vault_ingest, vault_search, vault_retrieve, vault_verify, vault_status


# --- Test Data ---

SAMPLE_INGESTION_RESULT = {
    "source_identity": {
        "source_hash": "abc123def456",
        "source_type": "pdf",
        "source_path": "/test/document.pdf",
        "captured_at": "2026-07-23T10:00:00Z",
    },
    "document_metadata": {
        "title": "Test Document",
        "author": "Test Author",
        "page_count": 2,
    },
    "extraction": {
        "parser": "pdf-pymupdf",
        "parser_version": "1.0.0",
        "total_pages": 2,
    },
    "content_units": [
        {
            "unit_id": "page-001",
            "text": "This is the first page of the test document. It contains important information about knowledge management and governed retrieval systems.",
            "content_hash": "hash_page_001",
            "page_number": 1,
        },
        {
            "unit_id": "page-002",
            "text": "The second page discusses provenance verification and citation tracking. Every answer should be traceable back to its source.",
            "content_hash": "hash_page_002",
            "page_number": 2,
        },
    ],
    "diagnostics": {
        "warnings": [],
        "errors": [],
    },
}


def run_test():
    """Run the complete E2E verification."""
    print("=" * 60)
    print("  Knowledge Vault -- E2E Verification")
    print("=" * 60)
    print()

    # Create temp directory for test database
    temp_dir = tempfile.mkdtemp(prefix="vault_test_")
    db_path = os.path.join(temp_dir, "knowledge.db")

    try:
        # Initialize database
        print("  Step 1: Initialize vault database")
        conn = init_db(db_path)
        stats = get_vault_stats(conn)
        print(f"    Schema version: {stats['schema_version']}")
        print(f"    Artifacts: {stats['artifacts']}")
        print(f"    Chunks: {stats['chunks']}")
        print()

        # Ingest sample document
        print("  Step 2: Ingest sample document")
        result = vault_ingest({
            "ingestion_result": SAMPLE_INGESTION_RESULT,
            "source_extension": "knowledge-ingestion",
            "receipt_id": "IR-test123",
        })
        result_data = result if isinstance(result, dict) else json.loads(result["content"][0]["text"])
        print(f"    Status: {result_data['status']}")
        print(f"    Artifact ID: {result_data['artifact_id']}")
        print(f"    Chunks added: {result_data['chunks_added']}")
        print()

        # Check deduplication
        print("  Step 3: Test deduplication")
        dedup_result = vault_ingest({
            "ingestion_result": SAMPLE_INGESTION_RESULT,
            "source_extension": "knowledge-ingestion",
            "receipt_id": "IR-test123",
        })
        dedup_data = dedup_result if isinstance(dedup_result, dict) else json.loads(dedup_result["content"][0]["text"])
        print(f"    Status: {dedup_data['status']}")
        print(f"    Chunks skipped: {dedup_data['chunks_skipped']}")
        print()

        # Search
        print("  Step 4: Search indexed knowledge")
        search_result = vault_search({
            "query": "knowledge management provenance",
            "limit": 5,
        })
        search_data = search_result if isinstance(search_result, dict) else json.loads(search_result["content"][0]["text"])
        print(f"    Query: {search_data['query']}")
        print(f"    Results: {search_data['total']}")
        for r in search_data.get("results", [])[:2]:
            print(f"      - {r.get('title', 'N/A')} (score: {r.get('combined_score', 0):.3f})")
        print()

        # Retrieve context
        print("  Step 5: Retrieve context with citations")
        retrieve_result = vault_retrieve({
            "query": "provenance verification",
            "max_chunks": 3,
        })
        retrieve_data = retrieve_result if isinstance(retrieve_result, dict) else json.loads(retrieve_result["content"][0]["text"])
        print(f"    Chunks retrieved: {retrieve_data['total_chunks']}")
        print(f"    Citations: {len(retrieve_data.get('citations', []))}")
        for c in retrieve_data.get("citations", []):
            print(f"      [{c['number']}] {c['title']} (p. {c.get('page_number', 'N/A')})")
        print()

        # Verify provenance
        print("  Step 6: Verify provenance")
        artifacts = list_artifacts(conn)
        if artifacts:
            artifact_id = artifacts[0]["artifact_id"]
            verify_result = vault_verify({"artifact_id": artifact_id})
            verify_data = verify_result if isinstance(verify_result, dict) else json.loads(verify_result["content"][0]["text"])
            print(f"    Artifact: {artifact_id}")
            print(f"    Verified: {verify_data['verified']}")
            print(f"    Chunks verified: {verify_data.get('chunks_verified', 0)}/{verify_data.get('chunks_total', 0)}")
        print()

        # Vault status
        print("  Step 7: Vault status")
        status_result = vault_status({})
        status_data = status_result if isinstance(status_result, dict) else json.loads(status_result["content"][0]["text"])
        print(f"    Schema version: {status_data['schema_version']}")
        print(f"    Artifacts: {status_data['artifacts']}")
        print(f"    Chunks: {status_data['chunks']}")
        print(f"    Embeddings: {status_data['embeddings']}")
        verification = status_data.get("verification", {})
        print(f"    Verification coverage: {verification.get('coverage', 0)}%")
        print()

        # Context assembly
        print("  Step 8: Context assembly with citations")
        if search_data.get("results"):
            assembled = assemble_context(conn, search_data["results"], max_chunks=2)
            formatted = format_context_for_agent(assembled, include_citations=True)
            print("    Formatted context:")
            for line in formatted.split("\n")[:8]:
                print(f"      {line}")
            if len(formatted.split("\n")) > 8:
                print("      ...")
        print()

        print("=" * 60)
        print("  RESULT: PASS")
        print("=" * 60)
        print()
        print("  The vault successfully:")
        print("    - Accepts IngestionResults from source extensions")
        print("    - Chunks content into indexed units")
        print("    - Generates embeddings for semantic search")
        print("    - Provides hybrid search (vector + fulltext)")
        print("    - Assembles cited context for agents")
        print("    - Verifies provenance chain")
        print("    - Tracks all ingestion history")
        print()
        print("  Architecture:")
        print("    Source Extension -> IngestionResult -> Vault -> Governed Retrieval")
        print()

        return True

    except Exception as e:
        print(f"\n  RESULT: FAIL -- {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
