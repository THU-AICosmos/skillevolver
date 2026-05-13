'use client';

import { useState, useEffect } from 'react';
import ArticleCard from './ArticleCard';
import ArticleSkeleton from './ArticleSkeleton';

const API_URL = '';

interface ArticleGridProps {
  pageNum: number;
  onArticlesLoaded: (count: number) => void;
}

export default function ArticleGrid({ pageNum, onArticlesLoaded }: ArticleGridProps) {
  const [articles, setArticles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const perPage = 12;

  useEffect(() => {
    fetch(`${API_URL}/api/articles`)
      .then(r => r.json())
      .then(data => {
        setArticles(data);
        setLoading(false);
        onArticlesLoaded(data.length);
      });
  }, []);

  const offset = (pageNum - 1) * perPage;
  const visibleArticles = articles.slice(offset, offset + perPage);

  return (
    <div data-testid="article-grid" className="p-5">
      <h2 className="mb-5">Latest Articles</h2>
      <div className="grid grid-cols-3 gap-5">
        {loading ? (
          <div data-testid="loading-indicator" className="p-2 text-gray-500 text-sm">Fetching articles...</div>
        ) : (
          visibleArticles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))
        )}
      </div>
    </div>
  );
}
