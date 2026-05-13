#!/bin/bash
# Oracle solution for Parallel BM25 Ranking task
# Creates the parallel_bm25.py file with a working parallel implementation

cat > /root/workspace/parallel_bm25.py << 'PYEOF'
#!/usr/bin/env python3
"""
Parallel BM25 Ranking Engine

Parallelized implementations of:
1. BM25 index construction via chunked multiprocessing
2. Batch query ranking with worker-pool initializer pattern

Optimization highlights:
- Serialize only plain tuples to workers (avoid pickling complex objects)
- Compute IDF centrally after aggregating document frequencies
- Use pool initializer to load index data once per worker for search
"""

import math
import time
import multiprocessing as mp
from multiprocessing import Pool
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from heapq import nlargest

from article_generator import Article
from baseline import (
    extract_tokens,
    count_terms,
    BM25Index,
    RankResult,
    BuildResult,
    NOISE_WORDS,
)


# ============================================================================
# Worker helpers (module-level for pickling)
# ============================================================================

def _tokenize_chunk(chunk: List[Tuple[int, str, str]]) -> Dict:
    """Tokenize and count terms for a batch of articles.

    Args:
        chunk: list of (article_id, headline, body) tuples

    Returns:
        dict with per-doc term counts, doc lengths, and local vocab
    """
    tc_per_doc = {}
    lengths = {}
    local_vocab: Set[str] = set()

    for aid, headline, body in chunk:
        text = headline + " " + body
        tokens = extract_tokens(text)
        raw = count_terms(tokens)
        tc_per_doc[aid] = raw
        lengths[aid] = len(tokens)
        local_vocab.update(raw.keys())

    return {
        "tc_per_doc": tc_per_doc,
        "lengths": lengths,
        "vocab": local_vocab,
    }


def _build_postings_partition(args: Tuple[Dict, int]) -> Dict:
    """Build inverted-index postings for a subset of articles.

    Args:
        args: (subset of term_counts_per_doc, total_articles)

    Returns:
        dict with partial inverted_index
    """
    subset_tc, _total = args
    partial_inv: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

    for aid, tc in subset_tc.items():
        for term, cnt in tc.items():
            partial_inv[term].append((aid, cnt))

    return {"inverted_index": dict(partial_inv)}


# -- search worker globals --------------------------------------------------
_g_inv = None
_g_tc = None
_g_dl = None
_g_idf = None
_g_avgdl = None
_g_k1 = None
_g_b = None
_g_topk = None


def _init_ranker(inv, tc, dl, idf, avgdl, k1, b, topk):
    global _g_inv, _g_tc, _g_dl, _g_idf, _g_avgdl, _g_k1, _g_b, _g_topk
    _g_inv = inv
    _g_tc = tc
    _g_dl = dl
    _g_idf = idf
    _g_avgdl = avgdl
    _g_k1 = k1
    _g_b = b
    _g_topk = topk


def _rank_one_query(query: str) -> Tuple[str, List[Tuple[int, float]]]:
    """Rank articles for a single query using pre-loaded index."""
    qtokens = extract_tokens(query)
    if not qtokens:
        return (query, [])

    qterms = count_terms(qtokens)

    candidates: Set[int] = set()
    for t in qterms:
        if t in _g_inv:
            for aid, _ in _g_inv[t]:
                candidates.add(aid)

    if not candidates:
        return (query, [])

    k1 = _g_k1
    b = _g_b
    avgdl = _g_avgdl

    scored = []
    for aid in candidates:
        dtc = _g_tc.get(aid, {})
        dl = _g_dl.get(aid, 0)
        if dl == 0:
            continue

        total = 0.0
        for qt in qterms:
            idf_val = _g_idf.get(qt, 0.0)
            if idf_val == 0.0:
                continue
            tf = dtc.get(qt, 0)
            num = tf * (k1 + 1)
            den = tf + k1 * (1 - b + b * dl / avgdl)
            total += idf_val * num / den

        scored.append((aid, total))

    top = nlargest(_g_topk, scored, key=lambda x: x[1])
    return (query, top)


# ============================================================================
# Public API
# ============================================================================

@dataclass
class ParallelBuildResult:
    """Result from parallel BM25 index building."""
    index: BM25Index
    elapsed_time: float
    num_articles: int
    vocabulary_size: int
    num_workers: int
    strategy: str


def build_bm25_index_parallel(
    articles: List[Article],
    num_workers: Optional[int] = None,
    chunk_size: int = 400,
    k1: float = 1.5,
    b: float = 0.75,
) -> ParallelBuildResult:
    """Build BM25 index using parallel processing.

    Pipeline:
    1. Parallel tokenization + term counting (chunked)
    2. Sequential merge of partial results
    3. Sequential DF and IDF computation
    4. Parallel inverted-index construction
    5. Sequential merge of postings
    """
    if num_workers is None:
        num_workers = mp.cpu_count()

    t0 = time.perf_counter()

    # Prepare serializable data
    art_data = [(a.article_id, a.headline, a.body) for a in articles]
    N = len(articles)

    chunks = [art_data[i:i + chunk_size]
              for i in range(0, len(art_data), chunk_size)]

    # ---- Phase 1: parallel tokenization ----
    with Pool(processes=num_workers) as pool:
        chunk_results = pool.map(_tokenize_chunk, chunks)

    # ---- Phase 2: merge ----
    all_tc: Dict[int, Dict[str, int]] = {}
    all_dl: Dict[int, int] = {}
    full_vocab: Set[str] = set()

    for cr in chunk_results:
        all_tc.update(cr["tc_per_doc"])
        all_dl.update(cr["lengths"])
        full_vocab.update(cr["vocab"])

    # ---- Phase 3: DF + IDF ----
    df_map: Dict[str, int] = {}
    for term in full_vocab:
        df_map[term] = sum(1 for aid in all_tc if term in all_tc[aid])

    idf_map: Dict[str, float] = {}
    for term, df in df_map.items():
        idf_map[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    avgdl = sum(all_dl.values()) / len(all_dl) if all_dl else 0.0

    # ---- Phase 4: parallel postings ----
    aid_list = list(all_tc.keys())
    per_worker = max(1, len(aid_list) // num_workers)
    posting_batches = []
    for i in range(0, len(aid_list), per_worker):
        sub_ids = aid_list[i:i + per_worker]
        sub_tc = {aid: all_tc[aid] for aid in sub_ids}
        posting_batches.append((sub_tc, N))

    with Pool(processes=num_workers) as pool:
        posting_results = pool.map(_build_postings_partition, posting_batches)

    # ---- Phase 5: merge postings ----
    merged_inv: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for pr in posting_results:
        for term, posts in pr["inverted_index"].items():
            merged_inv[term].extend(posts)

    for term in merged_inv:
        merged_inv[term].sort(key=lambda x: x[1], reverse=True)

    # Assemble index
    idx = BM25Index()
    idx.total_articles = N
    idx.vocabulary = full_vocab
    idx.doc_frequencies = df_map
    idx.idf_scores = idf_map
    idx.inverted_index = dict(merged_inv)
    idx.doc_lengths = all_dl
    idx.avg_doc_length = avgdl
    idx.term_counts_per_doc = all_tc
    idx.k1 = k1
    idx.b = b

    elapsed = time.perf_counter() - t0

    return ParallelBuildResult(
        index=idx,
        elapsed_time=elapsed,
        num_articles=N,
        vocabulary_size=len(full_vocab),
        num_workers=num_workers,
        strategy="Chunked MapReduce BM25",
    )


def batch_rank_parallel(
    queries: List[str],
    index: BM25Index,
    top_k: int = 10,
    num_workers: Optional[int] = None,
    articles: List[Article] = None,
) -> Tuple[List[List[RankResult]], float]:
    """Rank articles for many queries in parallel.

    Uses pool initializer so index is loaded once per worker,
    minimizing per-query IPC overhead.
    """
    if num_workers is None:
        num_workers = mp.cpu_count()

    # Fall back to sequential for tiny batches
    if len(queries) < num_workers * 2:
        from baseline import batch_rank_sequential
        t0 = time.perf_counter()
        res = batch_rank_sequential(queries, index, top_k, articles)
        return res, time.perf_counter() - t0

    t0 = time.perf_counter()

    with Pool(
        processes=num_workers,
        initializer=_init_ranker,
        initargs=(
            index.inverted_index,
            index.term_counts_per_doc,
            index.doc_lengths,
            index.idf_scores,
            index.avg_doc_length,
            index.k1,
            index.b,
            top_k,
        ),
    ) as pool:
        raw = pool.map(
            _rank_one_query,
            queries,
            chunksize=max(1, len(queries) // (num_workers * 4)),
        )

    headline_map = {a.article_id: a.headline for a in articles} if articles else {}
    results = []
    for _q, scored in raw:
        results.append([
            RankResult(
                article_id=aid,
                score=sc,
                headline=headline_map.get(aid, f"Article {aid}"),
            )
            for aid, sc in scored
        ])

    elapsed = time.perf_counter() - t0
    return results, elapsed
PYEOF

echo "Parallel BM25 solution created successfully."
