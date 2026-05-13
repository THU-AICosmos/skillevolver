# Parallel BM25 Document Ranking Engine

In `/root/workspace/`, there is a BM25-based document ranking engine that is implemented in Python and executes on a single thread (i.e. sequentially). The core functions of this ranking engine include building an inverted index with BM25 statistics for a news article corpus and performing relevance ranking of articles against search queries.

To utilize all idle cores on a machine and accelerate the whole engine, you need to parallelize it and achieve speedup on multi-core systems. You should write your solution in this python file `/root/workspace/parallel_bm25.py`. Make sure that your code implements the following functions:

1. `build_bm25_index_parallel(articles, num_workers=None, chunk_size=400)` (return a `ParallelBuildResult` with the same `BM25Index` structure as the original version)

2. `batch_rank_parallel(queries, index, top_k=10, num_workers=None, articles=None)` (return `(List[List[RankResult]], elapsed_time)`)

Performance target: 1.3x speedup over sequential index building, and 1.8x speedup over sequential batch ranking with 4 workers.
You must also make sure your code can produce identical results as the original ranking engine.
