"""
Knowledge Vault — Context Assembly

Assembles retrieved chunks into cited context for agents.
Generates proper citations linking back to source artifacts.
"""

import sqlite3
from typing import List, Dict


def assemble_context(conn: sqlite3.Connection, search_results: List[Dict],
                     max_chunks: int = 5) -> Dict:
    """
    Assemble search results into cited context for an agent.
    
    Args:
        conn: Database connection
        search_results: Results from search.hybrid_search or search.retrieve_context
        max_chunks: Maximum chunks to include
    
    Returns:
        Dict with assembled context and citations
    """
    chunks = search_results[:max_chunks]
    
    context_parts = []
    citations = []
    
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "")
        citation_number = i + 1
        
        # Build citation
        citation = {
            "number": citation_number,
            "chunk_id": chunk.get("chunk_id"),
            "artifact_id": chunk.get("artifact_id"),
            "title": chunk.get("title", "Untitled"),
            "source_type": chunk.get("source_type", "unknown"),
            "source_extension": chunk.get("source_extension", "unknown"),
            "page_number": chunk.get("page_number"),
            "location": chunk.get("location"),
            "score": chunk.get("combined_score", chunk.get("similarity", 0)),
        }
        citations.append(citation)
        
        # Format context with citation marker
        context_parts.append(f"[{citation_number}] {content}")
    
    # Build citation summary
    source_summary = {}
    for c in citations:
        ext = c["source_extension"]
        if ext not in source_summary:
            source_summary[ext] = {"count": 0, "titles": set()}
        source_summary[ext]["count"] += 1
        source_summary[ext]["titles"].add(c["title"])
    
    # Convert sets to lists for JSON serialization
    for ext in source_summary:
        source_summary[ext]["titles"] = list(source_summary[ext]["titles"])
    
    return {
        "context": "\n\n".join(context_parts),
        "citations": citations,
        "source_summary": source_summary,
        "total_chunks": len(chunks),
        "has_provenance": all(
            c.get("provenance", {}).get("source_extension") is not None
            for c in chunks
        ),
    }


def format_context_for_agent(assembled: Dict, include_citations: bool = True) -> str:
    """
    Format assembled context as a string for agent consumption.
    
    Args:
        assembled: Output from assemble_context
        include_citations: Whether to include citation details
    
    Returns:
        Formatted context string
    """
    parts = []
    
    if assembled["context"]:
        parts.append("## Retrieved Context\n")
        parts.append(assembled["context"])
    
    if include_citations and assembled["citations"]:
        parts.append("\n## Sources\n")
        for c in assembled["citations"]:
            page_info = f", p. {c['page_number']}" if c.get("page_number") else ""
            loc_info = f" ({c['location']})" if c.get("location") else ""
            parts.append(
                f"[{c['number']}] {c['title']} — "
                f"{c['source_type']}{page_info}{loc_info} "
                f"(via {c['source_extension']}, score: {c['score']:.3f})"
            )
    
    return "\n".join(parts)


def generate_answer_with_citations(answer: str, assembled: Dict) -> Dict:
    """
    Package an answer with its supporting citations.
    
    Args:
        answer: The generated answer text
        assembled: Output from assemble_context
    
    Returns:
        Dict with answer and citation chain
    """
    return {
        "answer": answer,
        "citations": assembled.get("citations", []),
        "source_summary": assembled.get("source_summary", {}),
        "verification": {
            "has_provenance": assembled.get("has_provenance", False),
            "total_sources": len(assembled.get("citations", [])),
            "source_extensions": list(assembled.get("source_summary", {}).keys()),
        },
    }
