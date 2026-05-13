'use client';

import { useState, useEffect } from 'react';

const API_URL = '';

interface BrowseBarProps {
  pageNum: number;
  articleCount: number;
  onPageChange: (p: number) => void;
}

export default function BrowseBar({ pageNum, articleCount, onPageChange }: BrowseBarProps) {
  const [ready, setReady] = useState(false);
  const perPage = 12;
  const lastPage = Math.ceil(articleCount / perPage) || 1;

  useEffect(() => {
    fetch(`${API_URL}/api/browse-bar`)
      .then(r => r.json())
      .then(data => setReady(data.ready));
  }, []);

  if (!ready || articleCount === 0) return null;

  const from = (pageNum - 1) * perPage + 1;
  const to = Math.min(pageNum * perPage, articleCount);

  return (
    <div
      data-testid="browse-bar"
      className="flex justify-between items-center bg-[var(--surface-bg)] py-4 px-5 mb-5 rounded-lg text-sm"
    >
      <span>Articles {from}-{to} of {articleCount}</span>
      <div data-testid="page-nav" className="flex items-center gap-3">
        <button
          data-testid="prev-page-btn"
          disabled={pageNum === 1}
          onClick={() => onPageChange(pageNum - 1)}
          className="px-4 py-2 rounded cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:opacity-80" style={{ backgroundColor: 'var(--surface-bg)', border: '1px solid var(--divider-color)' }}
        >
          Prev
        </button>
        <span>Page {pageNum} of {lastPage}</span>
        <button
          data-testid="next-page-btn"
          disabled={pageNum === lastPage}
          onClick={() => onPageChange(pageNum + 1)}
          className="px-4 py-2 rounded cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:opacity-80" style={{ backgroundColor: 'var(--surface-bg)', border: '1px solid var(--divider-color)' }}
        >
          Next
        </button>
      </div>
      <span>Sort: Newest</span>
    </div>
  );
}
