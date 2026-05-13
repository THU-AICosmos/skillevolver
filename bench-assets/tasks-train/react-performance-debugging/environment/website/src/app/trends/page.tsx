// src/app/trends/page.tsx
'use client';

import { useState } from 'react';
import { groupBy, sortBy, meanBy, sumBy, maxBy, minBy } from 'lodash';
import { mean, std, median, quantileSeq, variance } from 'mathjs';

interface TrendingArticle {
  id: string;
  headline: string;
  section: string;
  minutesToRead: number;
  views: number;
  shares: number;
  published: boolean;
}

// Sample trending articles for analytics
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
  // Using lodash for data transformations
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

function DeepDiveStats({ articles }: { articles: TrendingArticle[] }) {
  // Using mathjs for statistical calculations
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

  // Calculate engagement score: shares / views * 100
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
            <button
              data-testid="tab-headlines"
              onClick={() => setActiveTab('headlines')}
              className={`py-3 px-4 font-medium border-b-2 transition-colors ${
                activeTab === 'headlines'
                  ? 'border-emerald-600 text-emerald-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Headlines
            </button>
            <button
              data-testid="tab-deepdive"
              onClick={() => setActiveTab('deepdive')}
              className={`py-3 px-4 font-medium border-b-2 transition-colors ${
                activeTab === 'deepdive'
                  ? 'border-emerald-600 text-emerald-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Deep Dive
            </button>
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
