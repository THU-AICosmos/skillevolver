#!/usr/bin/env python3
"""
Tests for Parallel BM25 Implementation

Tests correctness and performance of the parallel implementation.
"""

import random
import sys
import time

import pytest

sys.path.insert(0, "/root/workspace")

from article_generator import generate_articles
from baseline import (
    batch_rank_sequential,
    build_bm25_index_sequential,
)


class TestParallelExists:
    """Test that parallel implementation exists and has correct interface."""

    def test_parallel_module_importable(self):
        """Test that parallel_bm25.py exists and can be imported."""
        try:
            from parallel_bm25 import (
                batch_rank_parallel,  # noqa: F401
                build_bm25_index_parallel,  # noqa: F401
            )
        except ImportError as e:
            pytest.fail(f"Could not import parallel_bm25: {e}")


class TestCorrectnessSmall:
    """Test correctness with small dataset."""

    @pytest.fixture(scope="class")
    def small_articles(self):
        """Generate small test corpus."""
        return generate_articles(800, seed=77)

    @pytest.fixture(scope="class")
    def seq_index(self, small_articles):
        """Build sequential index for comparison."""
        return build_bm25_index_sequential(small_articles)

    def test_idf_scores_match(self, small_articles, seq_index):
        """Test that BM25 IDF scores match between sequential and parallel."""
        from parallel_bm25 import build_bm25_index_parallel

        par_result = build_bm25_index_parallel(small_articles, num_workers=4)

        for term in seq_index.index.vocabulary:
            s_idf = seq_index.index.idf_scores.get(term, 0)
            p_idf = par_result.index.idf_scores.get(term, 0)
            assert abs(s_idf - p_idf) < 1e-6, (
                f"IDF mismatch for '{term}': {s_idf} vs {p_idf}"
            )

    def test_ranking_results_match(self, small_articles, seq_index):
        """Test that ranking results match between sequential and parallel."""
        from parallel_bm25 import batch_rank_parallel, build_bm25_index_parallel

        par_result = build_bm25_index_parallel(small_articles, num_workers=4)

        queries = [
            "championship tournament playoff victory",
            "election campaign vote legislation",
            "stock market investment portfolio",
        ]

        seq_results = batch_rank_sequential(
            queries, seq_index.index, top_k=10, articles=small_articles
        )
        par_results, _ = batch_rank_parallel(
            queries, par_result.index, top_k=10,
            num_workers=4, articles=small_articles,
        )

        for qi, (sr, pr) in enumerate(zip(seq_results, par_results)):
            assert len(sr) == len(pr), (
                f"Different result count for query {qi}"
            )
            for ri, (s, p) in enumerate(zip(sr, pr)):
                assert s.article_id == p.article_id, (
                    f"Article ID mismatch q={qi} r={ri}"
                )
                assert abs(s.score - p.score) < 1e-6, (
                    f"Score mismatch q={qi} r={ri}"
                )


class TestPerformanceIndexing:
    """Test index building performance."""

    @pytest.fixture(scope="class")
    def perf_articles(self):
        """Generate corpus for performance testing."""
        return generate_articles(4000, seed=303)

    def test_index_speedup(self, perf_articles):
        """Test that parallel indexing achieves speedup."""
        from parallel_bm25 import build_bm25_index_parallel

        # Sequential baseline
        start = time.perf_counter()
        build_bm25_index_sequential(perf_articles)
        seq_time = time.perf_counter() - start

        # Parallel with 4 workers
        start = time.perf_counter()
        build_bm25_index_parallel(perf_articles, num_workers=4)
        para_time = time.perf_counter() - start

        speedup = seq_time / para_time

        print("\nIndex Building Performance:")
        print(f"  Sequential: {seq_time:.2f}s")
        print(f"  Parallel (4 workers): {para_time:.2f}s")
        print(f"  Speedup: {speedup:.2f}x")

        assert speedup >= 1.3, (
            f"Insufficient speedup: {speedup:.2f}x (required: 1.3x)"
        )


class TestPerformanceRanking:
    """Test batch ranking performance."""

    @pytest.fixture(scope="class")
    def ranking_setup(self):
        """Set up corpus and index for ranking testing."""
        corpus = generate_articles(4000, seed=505)

        from parallel_bm25 import build_bm25_index_parallel

        build_res = build_bm25_index_parallel(corpus, num_workers=4)

        # Generate variable-length queries
        random.seed(606)
        seed_terms = [
            "championship", "election", "stock", "forecast",
            "tournament", "campaign", "investment", "storm",
            "player", "legislation", "trader", "hurricane",
            "score", "policy", "profit", "temperature",
            "movie", "actor", "concert", "streaming",
        ]

        queries = []
        for _ in range(800):
            length = random.randint(1, 15)
            q = " ".join(random.choices(seed_terms, k=length))
            queries.append(q)

        return corpus, build_res.index, queries

    def test_ranking_speedup(self, ranking_setup):
        """Test that parallel ranking achieves speedup."""
        from parallel_bm25 import batch_rank_parallel

        corpus, index, queries = ranking_setup

        # Sequential baseline
        start = time.perf_counter()
        batch_rank_sequential(queries, index, top_k=10, articles=corpus)
        seq_time = time.perf_counter() - start

        # Parallel with 4 workers
        start = time.perf_counter()
        batch_rank_parallel(
            queries, index, top_k=10, num_workers=4, articles=corpus,
        )
        para_time = time.perf_counter() - start

        speedup = seq_time / para_time

        print("\nBatch Ranking Performance (800 queries):")
        print(f"  Sequential: {seq_time:.2f}s")
        print(f"  Parallel (4 workers): {para_time:.2f}s")
        print(f"  Speedup: {speedup:.2f}x")

        assert speedup >= 1.8, (
            f"Insufficient speedup: {speedup:.2f}x (required: 1.8x)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
