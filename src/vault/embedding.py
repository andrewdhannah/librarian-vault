"""
Knowledge Vault — Embedding Layer

Generates vector embeddings for content chunks.
Supports multiple embedding strategies:
- TF-IDF (built-in, no external dependencies)
- Sentence Transformers (optional, requires torch)
- OpenAI embeddings (optional, requires API key)

The embedding layer produces vectors stored in the vault database.
"""

import hashlib
import struct
import re
import math
from typing import List, Dict, Optional
from collections import Counter


# ─── TF-IDF Embedding (Built-in) ──────────────────────────────────

class TFIDFEmbedder:
    """
    Lightweight TF-IDF embedding for semantic search.
    No external dependencies. Good enough for small-to-medium corpora.
    """
    
    def __init__(self, dimension: int = 256):
        self.dimension = dimension
        self.vocabulary = {}
        self.idf = {}
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        # Remove stopwords
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'can', 'shall',
                     'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                     'as', 'into', 'through', 'during', 'before', 'after', 'and',
                     'but', 'or', 'nor', 'not', 'so', 'if', 'then', 'than', 'that',
                     'this', 'these', 'those', 'it', 'its', 'their', 'they', 'them'}
        return [t for t in tokens if t not in stopwords and len(t) > 2]
    
    def _hash_token(self, token: str) -> int:
        """Hash token to a fixed dimension index."""
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        return h % self.dimension
    
    def fit(self, documents: List[str]):
        """Fit the embedder on a corpus to compute IDF."""
        doc_count = len(documents)
        df = Counter()
        
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                df[token] += 1
        
        self.idf = {}
        for token, freq in df.items():
            self.idf[token] = math.log(doc_count / (1 + freq))
    
    def embed(self, text: str) -> List[float]:
        """Generate TF-IDF vector for a text."""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimension
        
        # Compute TF
        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1
        
        # Build vector
        vector = [0.0] * self.dimension
        for token, count in tf.items():
            tfidf = (count / max_tf) * self.idf.get(token, 1.0)
            idx = self._hash_token(token)
            vector[idx] += tfidf
        
        # Normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        return [self.embed(text) for text in texts]


# ─── Vector Operations ─────────────────────────────────────────────

def vector_to_blob(vector: List[float]) -> bytes:
    """Serialize vector to binary blob."""
    return struct.pack(f'{len(vector)}f', *vector)


def blob_to_vector(blob: bytes, dimension: int) -> List[float]:
    """Deserialize binary blob to vector."""
    return list(struct.unpack(f'{dimension}f', blob))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


# ─── Embedding Storage ─────────────────────────────────────────────

def store_embeddings(conn, chunk_ids: List[str], vectors: List[List[float]],
                     model: str = "tfidf-v1"):
    """Store embedding vectors in the database."""
    import sqlite3
    
    for chunk_id, vector in zip(chunk_ids, vectors):
        blob = vector_to_blob(vector)
        dimension = len(vector)
        
        conn.execute(
            """INSERT OR REPLACE INTO embeddings (chunk_id, model, vector, dimension)
               VALUES (?, ?, ?, ?)""",
            (chunk_id, model, blob, dimension)
        )
    
    conn.commit()


def search_similar(conn, query_vector: List[float], model: str = "tfidf-v1",
                   limit: int = 10) -> List[Dict]:
    """Find chunks most similar to query vector."""
    import sqlite3
    
    rows = conn.execute(
        "SELECT chunk_id, vector, dimension FROM embeddings WHERE model = ?",
        (model,)
    ).fetchall()
    
    results = []
    for row in rows:
        chunk_vector = blob_to_vector(row["vector"], row["dimension"])
        similarity = cosine_similarity(query_vector, chunk_vector)
        results.append({
            "chunk_id": row["chunk_id"],
            "similarity": similarity,
        })
    
    # Sort by similarity descending
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


# ─── Convenience ───────────────────────────────────────────────────

def embed_chunks(chunks: List[Dict], model: str = "tfidf-v1") -> Dict:
    """
    Embed a list of chunks using the specified model.
    
    Returns:
        Dict mapping chunk_id to vector
    """
    embedder = TFIDFEmbedder()
    
    # Fit on all content
    texts = [c["content"] for c in chunks]
    embedder.fit(texts)
    
    # Embed each chunk
    results = {}
    for chunk in chunks:
        vector = embedder.embed(chunk["content"])
        # Use same chunk ID generation as ingestion layer
        content_hash = chunk.get("content_hash", "")
        chunk_id = f"CK-{content_hash[:16]}"
        results[chunk_id] = vector
    
    return results
