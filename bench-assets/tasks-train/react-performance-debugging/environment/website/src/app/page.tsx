// src/app/page.tsx
import { fetchReaderFromService, fetchArticlesFromService, fetchCommentsFromService } from '@/services/api-client';
import { ArticleFeed } from '@/components/ArticleFeed';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const reader = await fetchReaderFromService();
  const articles = await fetchArticlesFromService();
  const comments = await fetchCommentsFromService();

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
