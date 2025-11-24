"""
Unit tests for RAG Engine.
Tests BM25, TF-IDF, and hybrid search.
"""

import pytest
import os
import sys
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag_engine import (
    RAGSystem, RAGConfig, BM25Index, TFIDFIndex,
    QueryExpander, Document, SearchResult, create_rag_system
)


@pytest.fixture
def sample_knowledge_base():
    """Create a temporary knowledge base file for testing."""
    content = """## Раздел: Доставка
Стоимость доставки: По городу (Екатеринбург, Тюмень) стандартная Газель (до 1.5т) — 1500 рублей.
Для грузов свыше 1.5 тонны — 3000 рублей.

## Раздел: Возврат
Возврат товара в течение 100 дней при сохранении товарного вида.
Деньги возвращаются на карту в течение 3 рабочих дней.

## Раздел: Программа лояльности
Уровни карты:
1. "Новичок" (оборот до 50к) - кешбэк 1%.
2. "Профи" (оборот 50-200к) - кешбэк 3%.
3. "Мастер" (оборот 200к+) - кешбэк 5%.
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name


@pytest.fixture
def rag_system(sample_knowledge_base):
    """Create a RAG system instance."""
    return RAGSystem(sample_knowledge_base)


class TestRAGConfig:
    """Test RAG configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RAGConfig()

        assert config.bm25_k1 == 1.5
        assert config.bm25_b == 0.75
        assert config.chunk_size == 500
        assert config.chunk_overlap == 100
        assert config.bm25_weight == 0.6
        assert config.tfidf_weight == 0.4

    def test_custom_config(self):
        """Test custom configuration."""
        config = RAGConfig(bm25_k1=2.0, chunk_size=1000)

        assert config.bm25_k1 == 2.0
        assert config.chunk_size == 1000


class TestBM25Index:
    """Test BM25 index."""

    def test_index_documents(self):
        """Test document indexing."""
        index = BM25Index()
        docs = [
            Document(content="доставка по городу", doc_id="1"),
            Document(content="возврат товара", doc_id="2"),
        ]

        index.index_documents(docs)

        assert index.corpus_size == 2
        assert len(index.vocabulary) > 0
        assert index.avg_doc_length > 0

    def test_search(self):
        """Test BM25 search."""
        index = BM25Index()
        docs = [
            Document(content="доставка по городу стоит 1500 рублей", doc_id="1"),
            Document(content="возврат товара в течение 100 дней", doc_id="2"),
            Document(content="программа лояльности и бонусы", doc_id="3"),
        ]

        index.index_documents(docs)
        results = index.search("доставка", top_k=2)

        assert len(results) > 0
        assert results[0][0] == 0  # First doc should match "доставка"
        assert results[0][1] > 0   # Score should be positive

    def test_empty_query(self):
        """Test search with empty query."""
        index = BM25Index()
        docs = [Document(content="тест", doc_id="1")]
        index.index_documents(docs)

        results = index.search("", top_k=2)
        assert len(results) == 0


class TestTFIDFIndex:
    """Test TF-IDF index."""

    def test_index_documents(self):
        """Test document indexing."""
        index = TFIDFIndex()
        docs = [
            Document(content="доставка по городу", doc_id="1"),
            Document(content="возврат товара", doc_id="2"),
        ]

        index.index_documents(docs)

        assert len(index.vocabulary) > 0
        assert len(index.idf_scores) > 0

    def test_search(self):
        """Test TF-IDF search."""
        index = TFIDFIndex()
        docs = [
            Document(content="доставка по городу стоит 1500 рублей", doc_id="1"),
            Document(content="возврат товара в течение 100 дней", doc_id="2"),
        ]

        index.index_documents(docs)
        results = index.search("доставка", top_k=2)

        assert len(results) > 0
        assert results[0][1] > 0  # Score should be positive


class TestQueryExpander:
    """Test query expansion."""

    def test_expand_with_synonym(self):
        """Test query expansion with known synonym."""
        expander = QueryExpander()

        expanded = expander.expand("доставка")

        assert "привезти" in expanded or "привоз" in expanded or "транспортировка" in expanded

    def test_expand_without_synonym(self):
        """Test query expansion without known synonym."""
        expander = QueryExpander()

        original = "неизвестноеслово"
        expanded = expander.expand(original)

        assert expanded == original


class TestRAGSystem:
    """Test RAG system."""

    def test_initialization(self, rag_system):
        """Test RAG system initialization."""
        assert len(rag_system.documents) > 0
        assert len(rag_system.chunks) > 0

    def test_retrieve_hybrid(self, rag_system):
        """Test hybrid search retrieval."""
        result = rag_system.retrieve("доставка", top_k=2, method="hybrid")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "доставка" in result.lower() or "1500" in result

    def test_retrieve_bm25(self, rag_system):
        """Test BM25 retrieval."""
        result = rag_system.retrieve("возврат", top_k=2, method="bm25")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_retrieve_tfidf(self, rag_system):
        """Test TF-IDF retrieval."""
        result = rag_system.retrieve("лояльность", top_k=2, method="tfidf")

        assert isinstance(result, str)

    def test_retrieve_with_scores(self, rag_system):
        """Test retrieval with scores."""
        results = rag_system.retrieve_with_scores("доставка", top_k=2)

        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], SearchResult)
            assert results[0].score > 0

    def test_get_stats(self, rag_system):
        """Test statistics retrieval."""
        stats = rag_system.get_stats()

        assert isinstance(stats, dict)
        assert "total_documents" in stats
        assert stats["total_documents"] > 0

    def test_caching(self, rag_system):
        """Test result caching."""
        # First query
        rag_system.retrieve("доставка", top_k=2)

        # Check cache
        assert len(rag_system._cache) > 0

        # Clear cache
        rag_system.clear_cache()
        assert len(rag_system._cache) == 0

    def test_add_document(self, rag_system):
        """Test dynamic document addition."""
        initial_count = len(rag_system.documents)

        rag_system.add_document("Новый документ о скидках и акциях")

        assert len(rag_system.documents) == initial_count + 1


class TestCreateRagSystem:
    """Test factory function."""

    def test_create_with_defaults(self, sample_knowledge_base):
        """Test creation with default config."""
        rag = create_rag_system(sample_knowledge_base)

        assert isinstance(rag, RAGSystem)
        assert len(rag.documents) > 0

    def test_create_with_custom_config(self, sample_knowledge_base):
        """Test creation with custom config."""
        rag = create_rag_system(sample_knowledge_base, bm25_k1=2.0, chunk_size=1000)

        assert isinstance(rag, RAGSystem)
        assert rag.config.bm25_k1 == 2.0
        assert rag.config.chunk_size == 1000
