// src/components/ArticleCard.tsx
'use client';

interface Article {
  id: string;
  headline: string;
  minutesToRead: number;
  section: string;
  score: number;
  published: boolean;
}

interface Props {
  article: Article;
  commentCount: number;
  onBookmark: (id: string) => void;
  isBookmarked: boolean;
}

export function ArticleCard({ article, commentCount, onBookmark, isBookmarked }: Props) {
  // Performance tracking: marks each render for debugging
  performance.mark(`ArticleCard-render-${article.id}`);

  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
      <div className="h-32 bg-gradient-to-br from-emerald-100 to-emerald-200 flex items-center justify-center">
        <span className="text-5xl">📰</span>
      </div>
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <h3 className="font-semibold text-lg text-slate-900">{article.headline}</h3>
          <span className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-full">
            {article.section}
          </span>
        </div>
        <div className="flex items-center gap-2 mb-2 text-sm text-slate-500">
          <span>⏱ {article.minutesToRead} min read</span>
          <span>•</span>
          <span>{commentCount} comments</span>
        </div>
        <div className="flex items-center gap-1 mb-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <span key={i} className={i < article.score ? 'text-amber-400' : 'text-slate-300'}>
              ★
            </span>
          ))}
        </div>
        <div className="flex justify-between items-center mt-4">
          <span className="text-sm font-medium text-slate-600">
            Score {article.score}
          </span>
          <button
            data-testid={`bookmark-article-${article.id}`}
            onClick={() => onBookmark(article.id)}
            disabled={isBookmarked}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              isBookmarked
                ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                : 'bg-emerald-600 text-white hover:bg-emerald-700'
            }`}
          >
            {isBookmarked ? '✓ Bookmarked' : 'Bookmark'}
          </button>
        </div>
      </div>
    </div>
  );
}
