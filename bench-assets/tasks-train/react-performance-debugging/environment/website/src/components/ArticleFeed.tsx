// src/components/ArticleFeed.tsx
'use client';

import { useState } from 'react';
import { ArticleCard } from './ArticleCard';

interface Article {
  id: string;
  headline: string;
  minutesToRead: number;
  section: string;
  score: number;
  published: boolean;
}

interface Comment {
  id: string;
  articleId: string;
  body: string;
  score: number;
  author: string;
}

interface Props {
  articles: Article[];
  comments: Comment[];
}

export function ArticleFeed({ articles, comments }: Props) {
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [orderBy, setOrderBy] = useState<'minutesToRead' | 'score'>('minutesToRead');

  const filteredArticles = articles
    .filter(a => a.headline.toLowerCase().includes(query.toLowerCase()))
    .filter(a => a.published)
    .sort((a, b) => orderBy === 'minutesToRead' ? a.minutesToRead - b.minutesToRead : b.score - a.score);

  const handleBookmark = (articleId: string) => {
    setBookmarks(prev => [...prev, articleId]);
  };

  const getCommentCount = (articleId: string) => {
    return comments.filter(c => c.articleId === articleId).length;
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap gap-4 items-center">
        <input
          type="text"
          placeholder="Search articles..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
        />
        <select
          value={orderBy}
          onChange={(e) => setOrderBy(e.target.value as 'minutesToRead' | 'score')}
          className="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
        >
          <option value="minutesToRead">Order by Length</option>
          <option value="score">Order by Score</option>
        </select>
        <div data-testid="bookmarks-count" className="ml-auto px-4 py-2 bg-emerald-100 text-emerald-800 rounded-lg font-medium">
          Bookmarks: {bookmarks.length} articles
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {filteredArticles.map(article => (
          <ArticleCard
            key={article.id}
            article={article}
            commentCount={getCommentCount(article.id)}
            onBookmark={handleBookmark}
            isBookmarked={bookmarks.includes(article.id)}
          />
        ))}
      </div>
    </div>
  );
}
