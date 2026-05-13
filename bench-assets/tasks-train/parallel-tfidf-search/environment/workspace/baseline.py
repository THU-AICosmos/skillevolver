#!/usr/bin/env python3
"""
Sequential BM25 Implementation - Baseline

This module provides a sequential implementation of:
1. BM25 index building (with document length normalization)
2. Inverted index construction for BM25
3. BM25 relevance scoring for document ranking

Serves as the baseline for correctness testing and performance comparison.

BM25 Formula:
  score(D, Q) = sum over q in Q of:
    IDF(q) * (f(q,D) * (k1 + 1)) / (f(q,D) + k1 * (1 - b + b * |D| / avgdl))

  where IDF(q) = log((N - n(q) + 0.5) / (n(q) + 0.5) + 1)
"""

import argparse
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from heapq import nlargest

from article_generator import Article, generate_articles, load_articles

# ============================================================================
# Text Processing
# ============================================================================

NOISE_WORDS = frozenset([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "the", "this", "but", "they",
    "have", "had", "what", "when", "where", "who", "which", "why",
    "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "so",
    "than", "too", "very", "just", "can", "should", "now", "or",
    "if", "then", "because", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "once", "here", "there", "any", "do", "does", "did",
    "doing", "would", "could", "might", "must", "shall", "may",
    "been", "being", "am",
])

WORD_RE = re.compile(r"\b[a-zA-Z]{2,}\b")


def extract_tokens(text: str) -> list[str]:
    """
    Extract tokens from text, lowercasing and filtering noise words.
    """
    raw = WORD_RE.findall(text.lower())
    return [w for w in raw if w not in NOISE_WORDS]


def count_terms(tokens: list[str]) -> dict[str, int]:
    """
    Count raw term occurrences in a token list.
    Returns raw counts (not normalized) for BM25.
    """
    counts = defaultdict(int)
    for t in tokens:
        counts[t] += 1
    return dict(counts)


# ============================================================================
# BM25 Index Data Structures
# ============================================================================

@dataclass
class BM25Index:
    """
    BM25 inverted index for relevance ranking.

    Attributes:
        total_articles: Total number of articles indexed
        vocabulary: Set of all unique terms
        doc_frequencies: term -> number of articles containing term
        idf_scores: term -> BM25 IDF score
        inverted_index: term -> list of (article_id, raw_term_count)
        doc_lengths: article_id -> number of tokens in article
        avg_doc_length: Average document length across corpus
        term_counts_per_doc: article_id -> {term: raw_count}
        k1: BM25 k1 parameter (term frequency saturation)
        b: BM25 b parameter (length normalization)
    """
    total_articles: int = 0
    vocabulary: set[str] = field(default_factory=set)
    doc_frequencies: dict[str, int] = field(default_factory=dict)
    idf_scores: dict[str, float] = field(default_factory=dict)
    inverted_index: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    doc_lengths: dict[int, int] = field(default_factory=dict)
    avg_doc_length: float = 0.0
    term_counts_per_doc: dict[int, dict[str, int]] = field(default_factory=dict)
    k1: float = 1.5
    b: float = 0.75


@dataclass
class RankResult:
    """Result from BM25 ranking."""
    article_id: int
    score: float
    headline: str = ""


@dataclass
class BuildResult:
    """Result from index building."""
    index: BM25Index
    elapsed_time: float
    num_articles: int
    vocabulary_size: int


# ============================================================================
# Sequential Index Building
# ============================================================================

def build_bm25_index_sequential(articles: list[Article],
                                 k1: float = 1.5,
                                 b: float = 0.75) -> BuildResult:
    """
    Build BM25 inverted index sequentially.

    Steps:
    1. Tokenize all articles and compute raw term counts
    2. Calculate document frequencies for each term
    3. Compute BM25 IDF scores
    4. Build inverted index with raw term counts
    5. Compute average document length

    Args:
        articles: List of Article objects to index
        k1: BM25 term frequency saturation parameter
        b: BM25 length normalization parameter

    Returns:
        BuildResult with the built index and timing info
    """
    tick = time.perf_counter()

    idx = BM25Index()
    idx.total_articles = len(articles)
    idx.k1 = k1
    idx.b = b

    # Step 1: Tokenize and count terms
    for art in articles:
        text = art.headline + " " + art.body
        tokens = extract_tokens(text)
        raw_counts = count_terms(tokens)
        idx.term_counts_per_doc[art.article_id] = raw_counts
        idx.doc_lengths[art.article_id] = len(tokens)
        idx.vocabulary.update(raw_counts.keys())

    # Step 2: Document frequencies
    for term in idx.vocabulary:
        df = sum(
            1 for aid in idx.term_counts_per_doc
            if term in idx.term_counts_per_doc[aid]
        )
        idx.doc_frequencies[term] = df

    # Step 3: BM25 IDF scores
    # IDF(q) = log((N - n(q) + 0.5) / (n(q) + 0.5) + 1)
    N = idx.total_articles
    for term, df in idx.doc_frequencies.items():
        idx.idf_scores[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    # Step 4: Build inverted index
    for term in idx.vocabulary:
        postings = []
        for aid, tc in idx.term_counts_per_doc.items():
            if term in tc:
                postings.append((aid, tc[term]))
        postings.sort(key=lambda x: x[1], reverse=True)
        idx.inverted_index[term] = postings

    # Step 5: Average document length
    if idx.doc_lengths:
        idx.avg_doc_length = sum(idx.doc_lengths.values()) / len(idx.doc_lengths)

    elapsed = time.perf_counter() - tick

    return BuildResult(
        index=idx,
        elapsed_time=elapsed,
        num_articles=len(articles),
        vocabulary_size=len(idx.vocabulary),
    )


# ============================================================================
# Search / Ranking Functions
# ============================================================================

def rank_articles_sequential(query: str, index: BM25Index,
                              top_k: int = 10,
                              articles: list[Article] = None) -> list[RankResult]:
    """
    Rank articles for a query using BM25 scoring.
    """
    qtokens = extract_tokens(query)
    if not qtokens:
        return []

    query_terms = count_terms(qtokens)

    # Find candidate articles (those containing at least one query term)
    candidates = set()
    for term in query_terms:
        if term in index.inverted_index:
            for aid, _ in index.inverted_index[term]:
                candidates.add(aid)

    if not candidates:
        return []

    k1 = index.k1
    b = index.b
    avgdl = index.avg_doc_length

    scores = []
    for aid in candidates:
        doc_tc = index.term_counts_per_doc.get(aid, {})
        dl = index.doc_lengths.get(aid, 0)
        if dl == 0:
            continue

        bm25_score = 0.0
        for qterm in query_terms:
            if qterm not in index.idf_scores:
                continue
            idf = index.idf_scores[qterm]
            tf = doc_tc.get(qterm, 0)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avgdl)
            bm25_score += idf * numerator / denominator

        scores.append((aid, bm25_score))

    top_results = nlargest(top_k, scores, key=lambda x: x[1])

    headline_map = {a.article_id: a.headline for a in articles} if articles else {}
    return [
        RankResult(
            article_id=aid,
            score=sc,
            headline=headline_map.get(aid, f"Article {aid}"),
        )
        for aid, sc in top_results
    ]


def batch_rank_sequential(queries: list[str], index: BM25Index,
                           top_k: int = 10,
                           articles: list[Article] = None) -> list[list[RankResult]]:
    """
    Rank articles for multiple queries sequentially.
    """
    return [rank_articles_sequential(q, index, top_k, articles) for q in queries]


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Sequential BM25 ranking")
    parser.add_argument("--num-articles", type=int, default=5000)
    parser.add_argument("--query", type=str, default="championship tournament victory")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    print("=" * 60)
    print("Sequential BM25 Ranking Engine")
    print("=" * 60)

    print(f"\nGenerating {args.num_articles} articles...")
    articles = generate_articles(args.num_articles, seed=42)

    print("\nBuilding BM25 index...")
    result = build_bm25_index_sequential(articles)
    print(f"Index built in {result.elapsed_time:.3f}s")
    print(f"Vocabulary size: {result.vocabulary_size:,} terms")

    print(f"\nSearching for: '{args.query}'")
    t0 = time.perf_counter()
    results = rank_articles_sequential(args.query, result.index, args.top_k, articles)
    t1 = time.perf_counter()
    print(f"Search completed in {(t1-t0)*1000:.2f} ms")
    print(f"\nTop {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r.score:.4f}] {r.headline} (id: {r.article_id})")


if __name__ == "__main__":
    main()
