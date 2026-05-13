#!/bin/bash
set -e
cd /app

# Helper to terminate any process on port 3000
stop_app() {
  pkill -f "next start" 2>/dev/null || true
  pkill -f "node.*next" 2>/dev/null || true
  if command -v lsof &> /dev/null; then
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
  fi
  if command -v fuser &> /dev/null; then
    fuser -k 3000/tcp 2>/dev/null || true
  fi
  sleep 2
}

# Measure BEFORE
npm run build
npm start &
APP_PID=$!
sleep 5
BEFORE_RESP=$(curl -s -o /dev/null -w '%{time_total}' http://localhost:3000)
BEFORE_MS=$(echo "$BEFORE_RESP * 1000" | bc | cut -d. -f1)
kill $APP_PID 2>/dev/null || true
stop_app

# Optimization 1: Parallel fetches on the homepage server component
cat > src/app/page.tsx << 'HOMEPAGE_EOF'
import { fetchReaderFromService, fetchArticlesFromService, fetchCommentsFromService } from '@/services/api-client';
import { ArticleFeed } from '@/components/ArticleFeed';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const [reader, articles, comments] = await Promise.all([
    fetchReaderFromService(),
    fetchArticlesFromService(),
    fetchCommentsFromService(),
  ]);

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <header className="mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Welcome back, {reader.name}!</h1>
            <p className="text-slate-600">Your feed has {articles.length} fresh articles today</p>
          </div>
          <a
            href="/trends"
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
          >
            View Trends
          </a>
        </div>
      </header>
      <ArticleFeed articles={articles} comments={comments} />
    </main>
  );
}
HOMEPAGE_EOF

# Optimization 2: Parallel fetches + fire-and-forget metrics logging in articles API
cat > src/app/api/articles/route.ts << 'ARTICLES_API_EOF'
import { NextRequest, NextResponse } from 'next/server';
import { fetchReaderFromService, fetchArticlesFromService, logMetricsToService } from '@/services/api-client';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const [reader, articles] = await Promise.all([
    fetchReaderFromService(),
    fetchArticlesFromService(),
  ]);

  // Fire-and-forget: don't await metrics logging (non-blocking)
  void logMetricsToService({ readerId: reader.id, action: 'view_feed', count: articles.length });

  return NextResponse.json({ articles });
}
ARTICLES_API_EOF

# Optimization 3: Parallel fetches in subscribe - start digest right after reader resolves
cat > src/app/api/subscribe/route.ts << 'SUBSCRIBE_API_EOF'
import { NextRequest, NextResponse } from 'next/server';
import { fetchReaderFromService, fetchPreferencesFromService, fetchReaderDigestFromService } from '@/services/api-client';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const readerPromise = fetchReaderFromService();
  const preferencesPromise = fetchPreferencesFromService();
  const digestPromise = readerPromise.then(r => fetchReaderDigestFromService(r.id));

  const [reader, preferences, digest] = await Promise.all([readerPromise, preferencesPromise, digestPromise]);

  return NextResponse.json({
    success: true,
    reader: { id: reader.id, name: reader.name },
    digest,
    preferences: { timezone: preferences.timezone },
  });
}
SUBSCRIBE_API_EOF

# Optimization 4: useMemo + useCallback in ArticleFeed to prevent unnecessary re-renders
cat > src/components/ArticleFeed.tsx << 'FEED_EOF'
'use client';
import { useState, useMemo, useCallback } from 'react';
import { ArticleCard } from './ArticleCard';

interface Article { id: string; headline: string; minutesToRead: number; section: string; score: number; published: boolean; }
interface Comment { id: string; articleId: string; body: string; score: number; author: string; }
interface Props { articles: Article[]; comments: Comment[]; }

export function ArticleFeed({ articles, comments }: Props) {
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [orderBy, setOrderBy] = useState<'minutesToRead' | 'score'>('minutesToRead');

  const filteredArticles = useMemo(() =>
    articles
      .filter(a => a.headline.toLowerCase().includes(query.toLowerCase()))
      .filter(a => a.published)
      .sort((a, b) => orderBy === 'minutesToRead' ? a.minutesToRead - b.minutesToRead : b.score - a.score),
    [articles, query, orderBy]
  );

  const handleBookmark = useCallback((articleId: string) => {
    setBookmarks(prev => [...prev, articleId]);
  }, []);

  const commentCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    comments.forEach(c => { counts[c.articleId] = (counts[c.articleId] || 0) + 1; });
    return counts;
  }, [comments]);

  return (
    <div>
      <div className="mb-6 flex flex-wrap gap-4 items-center">
        <input type="text" placeholder="Search articles..." value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent" />
        <select value={orderBy} onChange={(e) => setOrderBy(e.target.value as 'minutesToRead' | 'score')}
          className="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500">
          <option value="minutesToRead">Order by Length</option>
          <option value="score">Order by Score</option>
        </select>
        <div data-testid="bookmarks-count" className="ml-auto px-4 py-2 bg-emerald-100 text-emerald-800 rounded-lg font-medium">
          Bookmarks: {bookmarks.length} articles
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {filteredArticles.map(article => (
          <ArticleCard key={article.id} article={article} commentCount={commentCounts[article.id] || 0}
            onBookmark={handleBookmark} isBookmarked={bookmarks.includes(article.id)} />
        ))}
      </div>
    </div>
  );
}
FEED_EOF

# Optimization 5: React.memo on ArticleCard component
cat > src/components/ArticleCard.tsx << 'CARD_EOF'
'use client';
import { memo } from 'react';

interface Article { id: string; headline: string; minutesToRead: number; section: string; score: number; published: boolean; }
interface Props { article: Article; commentCount: number; onBookmark: (id: string) => void; isBookmarked: boolean; }

export const ArticleCard = memo(function ArticleCard({ article, commentCount, onBookmark, isBookmarked }: Props) {
  performance.mark(`ArticleCard-render-${article.id}`);
  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
      <div className="h-32 bg-gradient-to-br from-emerald-100 to-emerald-200 flex items-center justify-center">
        <span className="text-5xl">📰</span>
      </div>
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <h3 className="font-semibold text-lg text-slate-900">{article.headline}</h3>
          <span className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-full">{article.section}</span>
        </div>
        <div className="flex items-center gap-2 mb-2 text-sm text-slate-500">
          <span>⏱ {article.minutesToRead} min read</span>
          <span>•</span>
          <span>{commentCount} comments</span>
        </div>
        <div className="flex items-center gap-1 mb-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <span key={i} className={i < article.score ? 'text-amber-400' : 'text-slate-300'}>★</span>
          ))}
        </div>
        <div className="flex justify-between items-center mt-4">
          <span className="text-sm font-medium text-slate-600">Score {article.score}</span>
          <button data-testid={`bookmark-article-${article.id}`} onClick={() => onBookmark(article.id)} disabled={isBookmarked}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              isBookmarked ? 'bg-slate-200 text-slate-500 cursor-not-allowed' : 'bg-emerald-600 text-white hover:bg-emerald-700'
            }`}>
            {isBookmarked ? '✓ Bookmarked' : 'Bookmark'}
          </button>
        </div>
      </div>
    </div>
  );
});
CARD_EOF

# Optimization 6: Trends page - direct lodash imports + dynamic mathjs
cat > src/app/trends/page.tsx << 'TRENDS_EOF'
'use client';

import { useState, useCallback } from 'react';
// FIXED: Direct imports instead of barrel imports
import groupBy from 'lodash/groupBy';
import sortBy from 'lodash/sortBy';
import meanBy from 'lodash/meanBy';
import sumBy from 'lodash/sumBy';
import maxBy from 'lodash/maxBy';
import minBy from 'lodash/minBy';
import dynamic from 'next/dynamic';

interface TrendingArticle {
  id: string;
  headline: string;
  section: string;
  minutesToRead: number;
  views: number;
  shares: number;
  published: boolean;
}

const TRENDING_ARTICLES: TrendingArticle[] = [
  { id: '1', headline: 'AI Regulation Debate Heats Up', section: 'Tech', minutesToRead: 8, views: 42100, shares: 1820, published: true },
  { id: '2', headline: 'Deep-Sea Exploration Milestone', section: 'Science', minutesToRead: 6, views: 18500, shares: 720, published: true },
  { id: '3', headline: 'Championship Overtime Thriller', section: 'Sports', minutesToRead: 4, views: 67800, shares: 2450, published: true },
  { id: '4', headline: 'Indie Film Festival Winners', section: 'Culture', minutesToRead: 5, views: 9200, shares: 310, published: false },
  { id: '5', headline: 'Tax Reform Analysis', section: 'Opinion', minutesToRead: 11, views: 14700, shares: 980, published: true },
  { id: '6', headline: 'Quantum Chip Announcement', section: 'Tech', minutesToRead: 7, views: 33400, shares: 1530, published: true },
  { id: '7', headline: 'Climate Summit Coverage', section: 'World', minutesToRead: 9, views: 22800, shares: 1105, published: true },
];

function HeadlineDashboard({ articles }: { articles: TrendingArticle[] }) {
  const sorted = sortBy(articles, ['views']);
  const avgViews = meanBy(articles, 'views');
  const totalShares = sumBy(articles, 'shares');
  const mostRead = maxBy(articles, 'views');
  const quickestRead = minBy(articles, 'minutesToRead');

  return (
    <div className="bg-white rounded-xl shadow-md p-6">
      <h2 className="text-xl font-bold mb-4">Headline Performance</h2>
      <div className="grid grid-cols-4 gap-4 mb-6 text-center">
        <div className="bg-emerald-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-emerald-600">{Math.round(avgViews).toLocaleString()}</div>
          <div className="text-sm text-slate-600">Avg Views</div>
        </div>
        <div className="bg-sky-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-sky-600">{totalShares.toLocaleString()}</div>
          <div className="text-sm text-slate-600">Total Shares</div>
        </div>
        <div className="bg-amber-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-amber-600">{mostRead?.headline}</div>
          <div className="text-sm text-slate-600">Most Read</div>
        </div>
        <div className="bg-rose-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-rose-600">{quickestRead?.headline}</div>
          <div className="text-sm text-slate-600">Quickest Read</div>
        </div>
      </div>
      <table className="w-full">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left">Headline</th>
            <th className="px-4 py-3 text-right">Views</th>
            <th className="px-4 py-3 text-right">Shares</th>
            <th className="px-4 py-3 text-right">Length</th>
            <th className="px-4 py-3 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((article) => (
            <tr key={article.id} className="border-t">
              <td className="px-4 py-3 font-medium">{article.headline}</td>
              <td className="px-4 py-3 text-right">{article.views.toLocaleString()}</td>
              <td className="px-4 py-3 text-right">{article.shares.toLocaleString()}</td>
              <td className="px-4 py-3 text-right">{article.minutesToRead} min</td>
              <td className="px-4 py-3 text-center">
                <span className={`px-2 py-1 rounded-full text-xs ${article.published ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>
                  {article.published ? 'Live' : 'Draft'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// FIXED: Dynamic import - only load mathjs when Deep Dive tab is clicked
const DeepDiveStats = dynamic(() => import('@/components/DeepDiveStats'), {
  loading: () => <div className="bg-white rounded-xl shadow-md p-6 text-center">Loading deep-dive analytics...</div>,
});

export default function TrendsPage() {
  const [activeTab, setActiveTab] = useState<'headlines' | 'deepdive'>('headlines');
  const [selectedArticles] = useState(TRENDING_ARTICLES);

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Trending This Week</h1>
        <p className="text-slate-600">Tracking {selectedArticles.length} articles</p>
      </header>
      <div className="mb-6">
        <div className="border-b border-slate-200">
          <nav className="flex gap-4">
            <button data-testid="tab-headlines" onClick={() => setActiveTab('headlines')}
              className={`py-3 px-4 font-medium border-b-2 transition-colors ${
                activeTab === 'headlines' ? 'border-emerald-600 text-emerald-600' : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}>Headlines</button>
            <button data-testid="tab-deepdive" onClick={() => setActiveTab('deepdive')}
              className={`py-3 px-4 font-medium border-b-2 transition-colors ${
                activeTab === 'deepdive' ? 'border-emerald-600 text-emerald-600' : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}>Deep Dive</button>
          </nav>
        </div>
      </div>
      {activeTab === 'headlines' ? (
        <HeadlineDashboard articles={selectedArticles} />
      ) : (
        <DeepDiveStats articles={selectedArticles} />
      )}
      <div className="mt-6 text-center">
        <a href="/" className="text-emerald-600 hover:underline">← Back to Feed</a>
      </div>
    </main>
  );
}
TRENDS_EOF

# Optimization 7: Create separate DeepDiveStats component with mathjs (dynamically loaded)
cat > src/components/DeepDiveStats.tsx << 'DEEPDIVE_EOF'
'use client';

import { mean, std, median, quantileSeq, variance } from 'mathjs';
import sortBy from 'lodash/sortBy';

interface TrendingArticle {
  id: string;
  headline: string;
  section: string;
  minutesToRead: number;
  views: number;
  shares: number;
  published: boolean;
}

export default function DeepDiveStats({ articles }: { articles: TrendingArticle[] }) {
  const views = articles.map(a => a.views);
  const shares = articles.map(a => a.shares);
  const minutes = articles.map(a => a.minutesToRead);

  const viewStats = {
    mean: mean(views),
    median: median(views),
    std: std(views),
    variance: variance(views),
    q1: quantileSeq(views, 0.25),
    q3: quantileSeq(views, 0.75),
  };

  const shareStats = { mean: mean(shares), median: median(shares), std: std(shares) };
  const minuteStats = { mean: mean(minutes), median: median(minutes), std: std(minutes) };

  const engagementScores = articles.map(a => ({ headline: a.headline, score: (a.shares / a.views) * 100 }));
  const sortedByEngagement = sortBy(engagementScores, 'score').reverse();

  return (
    <div data-testid="deepdive-content" className="bg-white rounded-xl shadow-md p-6">
      <h2 className="text-xl font-bold mb-4">Deep-Dive Reader Analytics</h2>
      <div className="grid grid-cols-3 gap-6">
        <div>
          <h3 className="font-semibold mb-3 text-slate-700">Views Distribution</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>Mean:</span><span className="font-mono">{Number(viewStats.mean).toLocaleString()}</span></div>
            <div className="flex justify-between"><span>Median:</span><span className="font-mono">{Number(viewStats.median).toLocaleString()}</span></div>
            <div className="flex justify-between"><span>Std Dev:</span><span className="font-mono">{Number(viewStats.std).toLocaleString()}</span></div>
            <div className="flex justify-between"><span>Variance:</span><span className="font-mono">{Number(viewStats.variance).toLocaleString()}</span></div>
            <div className="flex justify-between"><span>Q1 (25%):</span><span className="font-mono">{Number(viewStats.q1).toLocaleString()}</span></div>
            <div className="flex justify-between"><span>Q3 (75%):</span><span className="font-mono">{Number(viewStats.q3).toLocaleString()}</span></div>
          </div>
        </div>
        <div>
          <h3 className="font-semibold mb-3 text-slate-700">Share Analysis</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>Mean:</span><span className="font-mono">{Number(shareStats.mean).toFixed(1)}</span></div>
            <div className="flex justify-between"><span>Median:</span><span className="font-mono">{Number(shareStats.median).toFixed(1)}</span></div>
            <div className="flex justify-between"><span>Std Dev:</span><span className="font-mono">{Number(shareStats.std).toFixed(1)}</span></div>
          </div>
        </div>
        <div>
          <h3 className="font-semibold mb-3 text-slate-700">Read-Time</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>Mean:</span><span className="font-mono">{Number(minuteStats.mean).toFixed(1)} min</span></div>
            <div className="flex justify-between"><span>Median:</span><span className="font-mono">{Number(minuteStats.median).toFixed(1)} min</span></div>
            <div className="flex justify-between"><span>Std Dev:</span><span className="font-mono">{Number(minuteStats.std).toFixed(1)} min</span></div>
          </div>
        </div>
      </div>
      <div className="mt-6">
        <h3 className="font-semibold mb-3 text-slate-700">Engagement Ranking (Shares/Views × 100)</h3>
        <div className="space-y-2">
          {sortedByEngagement.map((item, i) => (
            <div key={item.headline} className="flex items-center gap-3">
              <span className="w-6 h-6 rounded-full bg-emerald-600 text-white text-sm flex items-center justify-center">{i + 1}</span>
              <span className="flex-1">{item.headline}</span>
              <span className="font-mono text-emerald-600">{item.score.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
DEEPDIVE_EOF

# Rebuild and measure AFTER
npm run build
npm start &
APP_PID=$!
sleep 5
AFTER_RESP=$(curl -s -o /dev/null -w '%{time_total}' http://localhost:3000)
AFTER_MS=$(echo "$AFTER_RESP * 1000" | bc | cut -d. -f1)

# Measure API endpoints (after fix)
AFTER_ARTICLES=$(curl -s -o /dev/null -w '%{time_total}' http://localhost:3000/api/articles)
AFTER_ARTICLES_MS=$(echo "$AFTER_ARTICLES * 1000" | bc | cut -d. -f1)
# Measure subscribe
AFTER_SUB=$(curl -s -o /dev/null -w '%{time_total}' -X POST -H "Content-Type: application/json" -d '{}' http://localhost:3000/api/subscribe)
AFTER_SUB_MS=$(echo "$AFTER_SUB * 1000" | bc | cut -d. -f1)

kill $APP_PID 2>/dev/null || true
stop_app

echo "Oracle complete. Before: ${BEFORE_MS}ms, After: ${AFTER_MS}ms"
echo "Articles API: ${AFTER_ARTICLES_MS}ms, Subscribe API: ${AFTER_SUB_MS}ms"
