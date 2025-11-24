"""
Enhanced RAG Engine (Retrieval-Augmented Generation).

Features:
- BM25 ranking algorithm (Okapi BM25)
- Hybrid search (BM25 + TF-IDF ensemble)
- Smart chunking with overlap
- Query expansion
- Caching for performance
- Document metadata support
- Relevance scoring normalization
"""

import re
import math
import hashlib
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Set
from functools import lru_cache
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a document chunk with metadata."""
    content: str
    doc_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    chunk_index: int = 0

    def __hash__(self):
        return hash(self.doc_id)


@dataclass
class SearchResult:
    """Represents a search result with scoring details."""
    document: Document
    score: float
    bm25_score: float = 0.0
    tfidf_score: float = 0.0
    keyword_matches: int = 0

    def to_dict(self) -> Dict:
        return {
            "doc_id": self.document.doc_id,
            "content": self.document.content[:200] + "..." if len(self.document.content) > 200 else self.document.content,
            "score": round(self.score, 4),
            "bm25_score": round(self.bm25_score, 4),
            "tfidf_score": round(self.tfidf_score, 4),
            "keyword_matches": self.keyword_matches,
            "metadata": self.document.metadata
        }


@dataclass
class RAGConfig:
    """Configuration for RAG system."""
    # BM25 parameters
    bm25_k1: float = 1.5  # Term frequency saturation
    bm25_b: float = 0.75  # Length normalization

    # Chunking parameters
    chunk_size: int = 500  # Characters per chunk
    chunk_overlap: int = 100  # Overlap between chunks

    # Search parameters
    min_score_threshold: float = 0.05
    default_top_k: int = 3

    # Hybrid search weights
    bm25_weight: float = 0.6
    tfidf_weight: float = 0.4

    # Query expansion
    enable_query_expansion: bool = True
    max_expansion_terms: int = 3

    # Caching
    enable_cache: bool = True
    cache_size: int = 100


class BM25Index:
    """
    Okapi BM25 ranking implementation.

    BM25 formula:
    score(D,Q) = Σ IDF(qi) * (f(qi,D) * (k1 + 1)) / (f(qi,D) + k1 * (1 - b + b * |D|/avgdl))

    Where:
    - f(qi,D) = frequency of term qi in document D
    - |D| = length of document D
    - avgdl = average document length
    - k1, b = tuning parameters
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Document] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.doc_freqs: Dict[str, int] = defaultdict(int)  # Term -> doc count
        self.term_freqs: List[Counter] = []  # Doc index -> term frequencies
        self.corpus_size: int = 0
        self.vocabulary: Set[str] = set()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Convert to lowercase and extract words
        words = re.findall(r'\w+', text.lower())
        # Remove very short words and numbers-only
        return [w for w in words if len(w) > 1 and not w.isdigit()]

    def index_documents(self, documents: List[Document]):
        """Build BM25 index from documents."""
        self.documents = documents
        self.corpus_size = len(documents)

        # Calculate term frequencies for each document
        self.term_freqs = []
        self.doc_lengths = []

        for doc in documents:
            tokens = self._tokenize(doc.content)
            tf = Counter(tokens)
            self.term_freqs.append(tf)
            self.doc_lengths.append(len(tokens))

            # Update document frequencies
            for term in set(tokens):
                self.doc_freqs[term] += 1
                self.vocabulary.add(term)

        # Calculate average document length
        if self.corpus_size > 0:
            self.avg_doc_length = sum(self.doc_lengths) / self.corpus_size

        logger.info(f"BM25 index built: {self.corpus_size} documents, {len(self.vocabulary)} unique terms")

    def _idf(self, term: str) -> float:
        """Calculate IDF for a term."""
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0.0
        # IDF with smoothing
        return math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1)

    def score(self, query: str, doc_index: int) -> float:
        """Calculate BM25 score for a query-document pair."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.0

        tf = self.term_freqs[doc_index]
        doc_len = self.doc_lengths[doc_index]

        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue

            term_freq = tf[term]
            idf = self._idf(term)

            # BM25 formula
            numerator = term_freq * (self.k1 + 1)
            denominator = term_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
            score += idf * (numerator / denominator)

        return score

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search for top-k documents matching the query."""
        scores = []
        for i in range(self.corpus_size):
            score = self.score(query, i)
            if score > 0:
                scores.append((i, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class TFIDFIndex:
    """TF-IDF based search index."""

    def __init__(self):
        self.documents: List[Document] = []
        self.tfidf_vectors: List[Counter] = []
        self.idf_scores: Dict[str, float] = {}
        self.vocabulary: Set[str] = set()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        words = re.findall(r'\w+', text.lower())
        return [w for w in words if len(w) > 1 and not w.isdigit()]

    def index_documents(self, documents: List[Document]):
        """Build TF-IDF index from documents."""
        self.documents = documents
        corpus_size = len(documents)

        # Calculate term frequencies
        term_freqs = []
        doc_freqs = defaultdict(int)

        for doc in documents:
            tokens = self._tokenize(doc.content)
            tf = Counter(tokens)
            term_freqs.append(tf)

            for term in set(tokens):
                doc_freqs[term] += 1
                self.vocabulary.add(term)

        # Calculate IDF scores
        for term, df in doc_freqs.items():
            self.idf_scores[term] = math.log(corpus_size / (1 + df)) + 1

        # Calculate TF-IDF vectors
        self.tfidf_vectors = []
        for tf in term_freqs:
            tfidf = Counter()
            for term, freq in tf.items():
                tfidf[term] = freq * self.idf_scores.get(term, 0)
            self.tfidf_vectors.append(tfidf)

        logger.info(f"TF-IDF index built: {corpus_size} documents")

    def _cosine_similarity(self, vec1: Counter, vec2: Counter) -> float:
        """Calculate cosine similarity between two vectors."""
        intersection = set(vec1.keys()) & set(vec2.keys())
        if not intersection:
            return 0.0

        numerator = sum(vec1[x] * vec2[x] for x in intersection)
        sum1 = sum(v ** 2 for v in vec1.values())
        sum2 = sum(v ** 2 for v in vec2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        return numerator / denominator if denominator else 0.0

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search for top-k documents matching the query."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build query TF-IDF vector
        query_tf = Counter(query_tokens)
        query_tfidf = Counter()
        for term, freq in query_tf.items():
            query_tfidf[term] = freq * self.idf_scores.get(term, 1.0)

        scores = []
        for i, doc_tfidf in enumerate(self.tfidf_vectors):
            score = self._cosine_similarity(query_tfidf, doc_tfidf)
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class QueryExpander:
    """Expands queries with synonyms and related terms."""

    # Domain-specific synonyms for construction retail
    SYNONYMS = {
        # Russian synonyms
        "доставка": ["привезти", "привоз", "транспортировка"],
        "возврат": ["вернуть", "обмен", "сдать"],
        "цена": ["стоимость", "прайс", "сколько"],
        "скидка": ["акция", "распродажа", "дешевле"],
        "товар": ["продукт", "продукция", "изделие"],
        "покупка": ["заказ", "купить", "приобрести"],
        "оплата": ["платеж", "оплатить", "способ оплаты"],
        "магазин": ["склад", "точка", "филиал"],
        "гарантия": ["гарантийный", "warranty"],
        "бонус": ["баллы", "кэшбэк", "cashback"],

        # English synonyms (if needed)
        "delivery": ["shipping", "ship", "transport"],
        "return": ["refund", "exchange", "money back"],
        "price": ["cost", "pricing", "rate"],
        "discount": ["sale", "promo", "offer"],
    }

    def expand(self, query: str, max_terms: int = 3) -> str:
        """Expand query with synonyms."""
        words = re.findall(r'\w+', query.lower())
        expanded_terms = set()

        for word in words:
            if word in self.SYNONYMS:
                synonyms = self.SYNONYMS[word][:max_terms]
                expanded_terms.update(synonyms)

        if expanded_terms:
            return query + " " + " ".join(expanded_terms)
        return query


class RAGSystem:
    """
    Enhanced RAG Engine with BM25 and hybrid search.

    Features:
    - BM25 ranking (Okapi BM25)
    - TF-IDF fallback
    - Hybrid search combining both methods
    - Smart chunking with overlap
    - Query expansion
    - Result caching
    """

    def __init__(self, kb_path: str, config: Optional[RAGConfig] = None):
        self.kb_path = kb_path
        self.config = config or RAGConfig()

        self.documents: List[Document] = []
        self.bm25_index = BM25Index(k1=self.config.bm25_k1, b=self.config.bm25_b)
        self.tfidf_index = TFIDFIndex()
        self.query_expander = QueryExpander()

        # Cache for search results
        self._cache: Dict[str, List[SearchResult]] = {}

        # Legacy compatibility
        self.chunks: List[str] = []

        self.load_knowledge_base()
        logger.info(f"📚 RAG System initialized: {len(self.documents)} chunks loaded")
        print(f"📚 RAG System initialized: {len(self.documents)} chunks loaded.")

    def load_knowledge_base(self):
        """Load and chunk the knowledge base."""
        try:
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                text = f.read()

            # Smart chunking
            self.documents = self._smart_chunk(text)

            # Build indices
            if self.documents:
                self.bm25_index.index_documents(self.documents)
                self.tfidf_index.index_documents(self.documents)

            # Legacy compatibility
            self.chunks = [doc.content for doc in self.documents]

        except FileNotFoundError:
            logger.error(f"Knowledge base file not found: {self.kb_path}")
            print(f"❌ Knowledge base file not found: {self.kb_path}")
            self.documents = []
            self.chunks = []
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
            print(f"❌ Error loading Knowledge Base: {e}")
            self.documents = []
            self.chunks = []

    def _smart_chunk(self, text: str) -> List[Document]:
        """
        Smart chunking with section awareness and overlap.

        Strategy:
        1. First, try to split by section headers (##, ###)
        2. Then split by paragraphs
        3. If chunks are too long, split with overlap
        """
        documents = []

        # Split by section headers or double newlines
        sections = re.split(r'\n(?=##)|(?:\n\n)', text)

        chunk_index = 0
        current_section = ""

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Detect section header
            header_match = re.match(r'^(#{1,3})\s*(.+)$', section, re.MULTILINE)
            if header_match:
                current_section = header_match.group(2).strip()

            # If section is small enough, keep as single chunk
            if len(section) <= self.config.chunk_size:
                doc_id = self._generate_doc_id(section, chunk_index)
                documents.append(Document(
                    content=section,
                    doc_id=doc_id,
                    metadata={"section": current_section},
                    source=self.kb_path,
                    chunk_index=chunk_index
                ))
                chunk_index += 1
            else:
                # Split large sections with overlap
                sub_chunks = self._split_with_overlap(
                    section,
                    self.config.chunk_size,
                    self.config.chunk_overlap
                )
                for sub_chunk in sub_chunks:
                    doc_id = self._generate_doc_id(sub_chunk, chunk_index)
                    documents.append(Document(
                        content=sub_chunk,
                        doc_id=doc_id,
                        metadata={"section": current_section, "is_subchunk": True},
                        source=self.kb_path,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1

        return documents

    def _split_with_overlap(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to find a good break point (sentence end or paragraph)
            if end < len(text):
                # Look for sentence end
                for char in ['.', '!', '?', '\n']:
                    break_point = text.rfind(char, start + chunk_size // 2, end)
                    if break_point > start:
                        end = break_point + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    def _generate_doc_id(self, content: str, index: int) -> str:
        """Generate unique document ID."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"doc_{index}_{content_hash}"

    def _get_cache_key(self, query: str, top_k: int, method: str) -> str:
        """Generate cache key for query."""
        return f"{query}:{top_k}:{method}"

    def search_bm25(self, query: str, top_k: int = None) -> List[SearchResult]:
        """Search using BM25 algorithm."""
        top_k = top_k or self.config.default_top_k

        # Query expansion
        if self.config.enable_query_expansion:
            query = self.query_expander.expand(query, self.config.max_expansion_terms)

        results = []
        bm25_results = self.bm25_index.search(query, top_k * 2)  # Get more for filtering

        for doc_idx, score in bm25_results:
            if score >= self.config.min_score_threshold:
                results.append(SearchResult(
                    document=self.documents[doc_idx],
                    score=score,
                    bm25_score=score,
                    keyword_matches=self._count_keyword_matches(query, self.documents[doc_idx].content)
                ))

        return results[:top_k]

    def search_tfidf(self, query: str, top_k: int = None) -> List[SearchResult]:
        """Search using TF-IDF algorithm."""
        top_k = top_k or self.config.default_top_k

        results = []
        tfidf_results = self.tfidf_index.search(query, top_k * 2)

        for doc_idx, score in tfidf_results:
            if score >= self.config.min_score_threshold:
                results.append(SearchResult(
                    document=self.documents[doc_idx],
                    score=score,
                    tfidf_score=score,
                    keyword_matches=self._count_keyword_matches(query, self.documents[doc_idx].content)
                ))

        return results[:top_k]

    def search_hybrid(self, query: str, top_k: int = None) -> List[SearchResult]:
        """
        Hybrid search combining BM25 and TF-IDF.
        Uses weighted combination of both scores.
        """
        top_k = top_k or self.config.default_top_k

        # Check cache
        cache_key = self._get_cache_key(query, top_k, "hybrid")
        if self.config.enable_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # Expand query
        expanded_query = query
        if self.config.enable_query_expansion:
            expanded_query = self.query_expander.expand(query, self.config.max_expansion_terms)

        # Get results from both indices
        bm25_results = {idx: score for idx, score in self.bm25_index.search(expanded_query, top_k * 3)}
        tfidf_results = {idx: score for idx, score in self.tfidf_index.search(query, top_k * 3)}

        # Normalize scores
        max_bm25 = max(bm25_results.values()) if bm25_results else 1.0
        max_tfidf = max(tfidf_results.values()) if tfidf_results else 1.0

        # Combine results
        all_indices = set(bm25_results.keys()) | set(tfidf_results.keys())
        combined_scores = {}

        for idx in all_indices:
            bm25_score = bm25_results.get(idx, 0) / max_bm25 if max_bm25 > 0 else 0
            tfidf_score = tfidf_results.get(idx, 0) / max_tfidf if max_tfidf > 0 else 0

            combined = (
                self.config.bm25_weight * bm25_score +
                self.config.tfidf_weight * tfidf_score
            )
            combined_scores[idx] = (combined, bm25_score, tfidf_score)

        # Sort and create results
        sorted_indices = sorted(combined_scores.items(), key=lambda x: x[1][0], reverse=True)

        results = []
        for idx, (combined, bm25, tfidf) in sorted_indices:
            if combined >= self.config.min_score_threshold:
                results.append(SearchResult(
                    document=self.documents[idx],
                    score=combined,
                    bm25_score=bm25,
                    tfidf_score=tfidf,
                    keyword_matches=self._count_keyword_matches(query, self.documents[idx].content)
                ))

        results = results[:top_k]

        # Cache results
        if self.config.enable_cache:
            if len(self._cache) >= self.config.cache_size:
                # Simple LRU: remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[cache_key] = results

        return results

    def _count_keyword_matches(self, query: str, content: str) -> int:
        """Count how many query words appear in content."""
        query_words = set(re.findall(r'\w+', query.lower()))
        content_words = set(re.findall(r'\w+', content.lower()))
        return len(query_words & content_words)

    def retrieve(self, query: str, top_k: int = 2, method: str = "hybrid") -> str:
        """
        Main retrieval method.
        Returns concatenated context string for LLM.

        Args:
            query: Search query
            top_k: Number of results to return
            method: Search method ("hybrid", "bm25", "tfidf")

        Returns:
            String with concatenated context chunks
        """
        if not self.documents:
            return ""

        if method == "bm25":
            results = self.search_bm25(query, top_k)
        elif method == "tfidf":
            results = self.search_tfidf(query, top_k)
        else:  # hybrid (default)
            results = self.search_hybrid(query, top_k)

        if not results:
            return ""

        # Format context with metadata hints
        context_parts = []
        for i, result in enumerate(results):
            section = result.document.metadata.get("section", "")
            section_hint = f"[Раздел: {section}]\n" if section else ""
            context_parts.append(f"{section_hint}{result.document.content}")

        return "\n---\n".join(context_parts)

    def retrieve_with_scores(self, query: str, top_k: int = 2, method: str = "hybrid") -> List[SearchResult]:
        """
        Retrieve documents with full scoring information.
        Useful for debugging and analysis.
        """
        if method == "bm25":
            return self.search_bm25(query, top_k)
        elif method == "tfidf":
            return self.search_tfidf(query, top_k)
        else:
            return self.search_hybrid(query, top_k)

    def add_document(self, content: str, metadata: Optional[Dict] = None):
        """
        Add a new document to the index.
        Useful for dynamic knowledge base updates.
        """
        chunk_index = len(self.documents)
        doc_id = self._generate_doc_id(content, chunk_index)

        doc = Document(
            content=content,
            doc_id=doc_id,
            metadata=metadata or {},
            source="dynamic",
            chunk_index=chunk_index
        )

        self.documents.append(doc)
        self.chunks.append(content)

        # Rebuild indices (could be optimized for incremental updates)
        self.bm25_index.index_documents(self.documents)
        self.tfidf_index.index_documents(self.documents)

        # Clear cache
        self._cache.clear()

        logger.info(f"Added document {doc_id} to index")

    def clear_cache(self):
        """Clear the search cache."""
        self._cache.clear()

    def get_stats(self) -> Dict:
        """Get statistics about the RAG system."""
        return {
            "total_documents": len(self.documents),
            "vocabulary_size_bm25": len(self.bm25_index.vocabulary),
            "vocabulary_size_tfidf": len(self.tfidf_index.vocabulary),
            "avg_doc_length": round(self.bm25_index.avg_doc_length, 2),
            "cache_size": len(self._cache),
            "config": {
                "bm25_k1": self.config.bm25_k1,
                "bm25_b": self.config.bm25_b,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "hybrid_weights": f"BM25:{self.config.bm25_weight}, TF-IDF:{self.config.tfidf_weight}"
            }
        }


# Legacy compatibility function
def create_rag_system(kb_path: str, **kwargs) -> RAGSystem:
    """Factory function for creating RAG system with custom config."""
    config = RAGConfig(**kwargs) if kwargs else None
    return RAGSystem(kb_path, config)


def run_comparison_test():
    """Compare BM25 vs TF-IDF vs Hybrid search."""
    import os

    # Find knowledge base path
    paths = [
        "data/knowledge_base.txt",
        "ConstructionAI_System/data/knowledge_base.txt",
        "/home/ubuntu/ConstructionAI_System/data/knowledge_base.txt"
    ]

    kb_path = None
    for p in paths:
        if os.path.exists(p):
            kb_path = p
            break

    if not kb_path:
        print("❌ Knowledge base not found!")
        return

    print("=" * 60)
    print("RAG Engine Comparison Test")
    print("=" * 60)

    # Create RAG system
    rag = RAGSystem(kb_path)

    # Test queries
    test_queries = [
        "Сколько стоит доставка?",
        "Как вернуть товар?",
        "Программа лояльности бонусы",
        "Условия возврата денег",
        "Способы оплаты в магазине"
    ]

    # Compare methods
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("-" * 60)

        for method in ["bm25", "tfidf", "hybrid"]:
            results = rag.retrieve_with_scores(query, top_k=2, method=method)
            print(f"\n[{method.upper()}]")
            for i, r in enumerate(results):
                print(f"  {i+1}. Score: {r.score:.4f} | Keywords: {r.keyword_matches}")
                print(f"     {r.document.content[:100]}...")

    # Print stats
    print(f"\n{'='*60}")
    print("RAG System Statistics:")
    stats = rag.get_stats()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    run_comparison_test()
