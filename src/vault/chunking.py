"""
Knowledge Vault — Chunking Layer

Splits documents into indexed units of knowledge.
Supports multiple chunking strategies: fixed-size, sentence, semantic.

The chunker operates on IngestionResult content_units and produces
vault-ready chunks with metadata.
"""

import re
import hashlib
from typing import List, Dict, Optional


def chunk_by_page(content_units: List[Dict]) -> List[Dict]:
    """
    Page-level chunking: each content unit becomes a chunk.
    Default strategy for PDFs and paged documents.
    
    Args:
        content_units: List of content unit dicts from IngestionResult
    
    Returns:
        List of chunk dicts
    """
    chunks = []
    for i, unit in enumerate(content_units):
        content = unit.get("text", "")
        if not content.strip():
            continue
        
        chunk = {
            "chunk_index": i,
            "content": content,
            "content_hash": unit.get("content_hash", _hash(content)),
            "page_number": unit.get("page_number"),
            "location": unit.get("location"),
            "token_count": len(content.split()),
            "strategy": "page",
            "metadata": {
                "unit_id": unit.get("unit_id"),
                "extraction_method": unit.get("extraction_method"),
            }
        }
        chunks.append(chunk)
    return chunks


def chunk_by_paragraph(content_units: List[Dict], 
                       max_tokens: int = 512,
                       overlap_tokens: int = 50) -> List[Dict]:
    """
    Paragraph-level chunking: splits content into paragraph-sized chunks.
    Good for markdown and structured text.
    
    Args:
        content_units: List of content unit dicts
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between chunks for context continuity
    
    Returns:
        List of chunk dicts
    """
    chunks = []
    chunk_index = 0
    
    for unit in content_units:
        content = unit.get("text", "")
        if not content.strip():
            continue
        
        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            current_tokens = len(current_chunk.split())
            para_tokens = len(para.split())
            
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Emit current chunk
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": current_chunk.strip(),
                    "content_hash": _hash(current_chunk.strip()),
                    "page_number": unit.get("page_number"),
                    "location": unit.get("location"),
                    "token_count": len(current_chunk.split()),
                    "strategy": "paragraph",
                    "metadata": {"unit_id": unit.get("unit_id")}
                })
                chunk_index += 1
                
                # Start new chunk with overlap
                words = current_chunk.split()
                if overlap_tokens > 0 and len(words) > overlap_tokens:
                    current_chunk = " ".join(words[-overlap_tokens:]) + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para
        
        # Emit remaining content
        if current_chunk.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "content": current_chunk.strip(),
                "content_hash": _hash(current_chunk.strip()),
                "page_number": unit.get("page_number"),
                "location": unit.get("location"),
                "token_count": len(current_chunk.split()),
                "strategy": "paragraph",
                "metadata": {"unit_id": unit.get("unit_id")}
            })
            chunk_index += 1
    
    return chunks


def chunk_by_sentence(content_units: List[Dict],
                      max_tokens: int = 256,
                      overlap_sentences: int = 2) -> List[Dict]:
    """
    Sentence-level chunking: splits into sentence-sized chunks.
    Good for conversational content and emails.
    
    Args:
        content_units: List of content unit dicts
        max_tokens: Maximum tokens per chunk
        overlap_sentences: Number of sentences to overlap
    
    Returns:
        List of chunk dicts
    """
    chunks = []
    chunk_index = 0
    
    for unit in content_units:
        content = unit.get("text", "")
        if not content.strip():
            continue
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        current_chunk = ""
        sentence_buffer = []
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            sentence_buffer.append(sent)
            current_chunk = current_chunk + " " + sent if current_chunk else sent
            current_tokens = len(current_chunk.split())
            
            if current_tokens >= max_tokens:
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": current_chunk.strip(),
                    "content_hash": _hash(current_chunk.strip()),
                    "page_number": unit.get("page_number"),
                    "location": unit.get("location"),
                    "token_count": len(current_chunk.split()),
                    "strategy": "sentence",
                    "metadata": {"unit_id": unit.get("unit_id")}
                })
                chunk_index += 1
                
                # Keep overlap sentences
                overlap_sents = sentence_buffer[-overlap_sentences:]
                current_chunk = " ".join(overlap_sents)
                sentence_buffer = overlap_sents
        
        # Emit remaining
        if current_chunk.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "content": current_chunk.strip(),
                "content_hash": _hash(current_chunk.strip()),
                "page_number": unit.get("page_number"),
                "location": unit.get("location"),
                "token_count": len(current_chunk.split()),
                "strategy": "sentence",
                "metadata": {"unit_id": unit.get("unit_id")}
            })
            chunk_index += 1
    
    return chunks


def auto_chunk(content_units: List[Dict], 
               source_type: str = "unknown") -> List[Dict]:
    """
    Automatically select chunking strategy based on source type.
    
    Args:
        content_units: List of content unit dicts
        source_type: Type of source (pdf, markdown, html, email, etc.)
    
    Returns:
        List of chunk dicts
    """
    strategy_map = {
        "pdf": chunk_by_page,
        "markdown": chunk_by_paragraph,
        "html": chunk_by_paragraph,
        "email": chunk_by_sentence,
        "text": chunk_by_paragraph,
    }
    
    strategy = strategy_map.get(source_type, chunk_by_page)
    return strategy(content_units)


def _hash(text: str) -> str:
    """Generate SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
