'use client';

import { useState } from 'react';
import { useAppearance } from '@/components/AppearanceProvider';
import HeadlineBanner from '@/components/HeadlineBanner';
import ArticleGrid from '@/components/ArticleGrid';
import AlertStrip from '@/components/AlertStrip';
import TagsSidebar from '@/components/TagsSidebar';
import BrowseBar from '@/components/BrowseBar';

export default function Home() {
  const { mode, cycleMode } = useAppearance();
  const [pageNum, setPageNum] = useState(1);
  const [articleCount, setArticleCount] = useState(0);

  return (
    <main>
      <header className="flex justify-between items-center p-5 border-b" style={{ borderColor: 'var(--divider-color)' }}>
        <h1 className="text-2xl">TechPulse Blog</h1>
        <button
          data-testid="mode-toggle"
          className="px-4 py-2 border-none rounded bg-[#6366f1] text-white cursor-pointer"
          onClick={cycleMode}
        >
          {mode === 'day' ? 'Night Mode' : 'Day Mode'}
        </button>
      </header>
      <HeadlineBanner />
      <AlertStrip />
      <div className="flex">
        <TagsSidebar />
        <div data-testid="content-area" className="flex-1">
          <BrowseBar
            pageNum={pageNum}
            articleCount={articleCount}
            onPageChange={setPageNum}
          />
          <ArticleGrid
            pageNum={pageNum}
            onArticlesLoaded={setArticleCount}
          />
        </div>
      </div>
    </main>
  );
}
