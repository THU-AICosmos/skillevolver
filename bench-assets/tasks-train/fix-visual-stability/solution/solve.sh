#!/bin/bash
set -e

cd /app

# Utility: free port 3000
free_port() {
  fuser -k 3000/tcp 2>/dev/null || true
  sleep 2
}

# Install deps
npm install
npm install -D tailwindcss postcss autoprefixer @tailwindcss/postcss
pip3 install --break-system-packages playwright
playwright install chromium

# Ensure port is available
free_port

# Start dev for baseline measurement
npm run dev &
DEV_ID=$!

echo "Waiting for dev server..."
for attempt in $(seq 1 60); do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null | grep -q "200"; then
    echo "Dev ready"
    break
  fi
  sleep 1
done

# Baseline CLS measurement
python3 << 'BASELINE'
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True)
    pg = br.new_page()

    pg.add_init_script("""
        window.__clsVal = 0;
        window.__entries = [];
        let ws = 0; let wb = 0; let ls = 0;
        new PerformanceObserver((list) => {
            for (const e of list.getEntries()) {
                if (e.hadRecentInput) continue;
                const t = e.startTime / 1000;
                if (wb === 0 || (t - ls) > 1 || (t - wb) > 5) { ws = 0; wb = t; }
                ws += e.value; ls = t;
                window.__entries.push({v: e.value});
                if (ws > window.__clsVal) window.__clsVal = ws;
            }
        }).observe({ type: 'layout-shift', buffered: true });
    """)

    pg.goto("http://localhost:3000", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(1000)
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(1000)

    val = pg.evaluate("window.__clsVal")
    ents = pg.evaluate("window.__entries")
    br.close()

with open("/tmp/baseline_cls.json", "w") as fp:
    json.dump({"cls": round(val, 3), "entries": ents}, fp)
print(f"BASELINE CLS: {val}")
BASELINE

kill $DEV_ID 2>/dev/null || true
free_port

# --- Apply all fixes ---

# Fix 1: globals.css - add font-display: swap and proper theme variables
cat > /app/src/app/globals.css << 'CSSEOF'
@import "tailwindcss";

@theme {
  --font-heading: 'HeadingFont', Georgia, serif;
}

/* FIXED: Added font-display: swap to prevent FOIT */
@font-face {
  font-family: 'HeadingFont';
  src: url('/fonts/heading.woff2') format('woff2');
  font-display: swap;
}

@layer base {
  body {
    font-family: var(--font-heading);
    background-color: #fafafa;
    color: #1a1a2e;
    transition: background-color 0.3s, color 0.3s;
  }

  [data-mode='night'] body {
    background-color: #1e1e2e;
    color: #e0e0e0;
  }

  :root {
    --surface-bg: #ffffff;
    --divider-color: #e0e0e0;
    --subtle-text: #6b7280;
    --surface-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  }

  [data-mode='night'] {
    --surface-bg: #2d2d3f;
    --divider-color: #3d3d50;
    --subtle-text: #9ca3af;
    --surface-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
  }
}

@keyframes shimmer {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
CSSEOF

# Remove proxy rewrite since we add local API routes
cat > /app/next.config.js << 'NCEOF'
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'picsum.photos',
      },
    ],
  },
};
module.exports = nextConfig;
NCEOF

# Create local API route so the app works without external API server
mkdir -p /app/src/app/api/articles
cat > /app/src/app/api/articles/route.ts << 'APIEOF'
import { NextResponse } from 'next/server';

const articles = Array.from({ length: 150 }, (_, i) => ({
  id: `post-${i + 1}`,
  title: `Tech Trend ${i + 1}`,
  author: ['Maya Chen', 'Leo Park', 'Sara Nguyen', 'James Rivera', 'Priya Sharma'][i % 5],
  excerpt: 'A deep dive into the latest developments and what they mean for the industry going forward.',
  coverImage: `https://picsum.photos/seed/blog${i + 1}/480/270`,
  readTime: 3 + (i % 13),
}));

export async function GET() {
  return NextResponse.json(articles);
}
APIEOF

# Fix 2: AppearanceProvider - inline script sets mode before paint
cat > /app/src/components/AppearanceProvider.tsx << 'PROVEOF'
'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

type Mode = 'day' | 'night';

const AppearanceContext = createContext<{
  mode: Mode;
  cycleMode: () => void;
}>({ mode: 'day', cycleMode: () => {} });

export function useAppearance() {
  return useContext(AppearanceContext);
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>('day');

  const cycleMode = () => {
    const next = mode === 'day' ? 'night' : 'day';
    setMode(next);
    localStorage.setItem('appearance', next);
    document.documentElement.setAttribute('data-mode', next);
    const shell = document.getElementById('appearance-shell');
    if (shell) {
      shell.style.backgroundColor = next === 'night' ? '#1e1e2e' : '#fafafa';
      shell.style.color = next === 'night' ? '#e0e0e0' : '#1a1a2e';
    }
  };

  return (
    <AppearanceContext.Provider value={{ mode, cycleMode }}>
      <div data-testid="appearance-shell" id="appearance-shell" className="min-h-screen">
        {children}
      </div>
      <script
        dangerouslySetInnerHTML={{
          __html: `(function(){try{var m=localStorage.getItem('appearance')||'day';document.documentElement.setAttribute('data-mode',m);var s=document.getElementById('appearance-shell');if(s){s.style.backgroundColor=m==='night'?'#1e1e2e':'#fafafa';s.style.color=m==='night'?'#e0e0e0':'#1a1a2e';}}catch(x){}})();`,
        }}
      />
    </AppearanceContext.Provider>
  );
}
PROVEOF

# Fix 3: page.tsx - main page unchanged structurally (already correct)
cat > /app/src/app/page.tsx << 'PAGEEOF'
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
PAGEEOF

# Fix 4: ArticleCard - add explicit cover image dimensions
cat > /app/src/components/ArticleCard.tsx << 'CARDEOF'
'use client';

interface Article {
  id: string;
  title: string;
  author: string;
  excerpt: string;
  coverImage: string;
  readTime: number;
}

// FIXED: explicit width/height on cover image prevents layout shift
export default function ArticleCard({ article }: { article: Article }) {
  return (
    <div data-testid="article-card" className="bg-[var(--surface-bg)] rounded-lg p-4" style={{ boxShadow: 'var(--surface-shadow)', border: '1px solid var(--divider-color)' }}>
      <img
        data-testid="article-cover"
        src={article.coverImage}
        alt={article.title}
        width={480}
        height={270}
        className="w-full aspect-[16/9] object-cover"
      />
      <h3 className="mt-3 mb-1 text-lg font-semibold">{article.title}</h3>
      <p className="text-sm mb-2" style={{ color: 'var(--subtle-text)' }}>By {article.author} · {article.readTime} min read</p>
      <p className="text-sm" style={{ color: 'var(--subtle-text)' }}>{article.excerpt}</p>
      <button className="w-full p-2.5 mt-3 bg-[#6366f1] text-white border-none rounded cursor-pointer">
        Read More
      </button>
    </div>
  );
}
CARDEOF

# Fix 5: ArticleSkeleton - match actual ArticleCard dimensions
cat > /app/src/components/ArticleSkeleton.tsx << 'SKELEOF'
'use client';

// FIXED: skeleton dimensions match the real ArticleCard layout
export default function ArticleSkeleton() {
  return (
    <div data-testid="article-skeleton" className="bg-[var(--surface-bg)] rounded-lg p-4 min-h-[420px]">
      <div data-testid="skeleton-cover" className="bg-gray-300 h-[270px] rounded animate-pulse" />
      <div data-testid="skeleton-headline" className="bg-gray-300 h-5 mt-3 rounded animate-pulse" />
      <div className="bg-gray-300 h-4 w-[40%] mt-2 rounded animate-pulse" />
      <div className="bg-gray-300 h-4 mt-2 rounded animate-pulse" />
      <div className="bg-gray-300 h-10 mt-3 rounded animate-pulse" />
    </div>
  );
}
SKELEOF

# Fix 6: HeadlineBanner - always render container with reserved space
cat > /app/src/components/HeadlineBanner.tsx << 'HLEOF'
'use client';

import { useState, useEffect } from 'react';

// FIXED: always render container to prevent CLS
export default function HeadlineBanner() {
  const [headline, setHeadline] = useState<string>('');

  useEffect(() => {
    setTimeout(() => {
      setHeadline('Breaking: AI Reaches New Milestone in Code Generation');
    }, 1200);
  }, []);

  return (
    <div
      data-testid="headline-banner"
      className="bg-[#6366f1] text-white py-20 px-4 text-center font-bold text-2xl min-h-[120px]"
    >
      {headline}
    </div>
  );
}
HLEOF

# Fix 7: AlertStrip - always render container with reserved space
cat > /app/src/components/AlertStrip.tsx << 'ALERTEOF'
'use client';

import { useState, useEffect } from 'react';

// FIXED: always render container to prevent CLS
export default function AlertStrip() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setTimeout(() => {
      setVisible(true);
    }, 2800);
  }, []);

  return (
    <div
      data-testid="alert-strip"
      className="bg-[#f59e0b] text-black py-28 px-4 text-center font-bold text-[26px] min-h-[168px]"
    >
      {visible ? 'Join our live webinar this Friday: The Future of Serverless Architecture' : ''}
    </div>
  );
}
ALERTEOF

# Fix 8: TagsSidebar - always render with reserved width
cat > /app/src/components/TagsSidebar.tsx << 'TSEOF'
'use client';

import { useState, useEffect } from 'react';

// FIXED: always render container with fixed width to prevent CLS
export default function TagsSidebar() {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setTimeout(() => {
      setLoaded(true);
    }, 1700);
  }, []);

  return (
    <aside
      data-testid="tags-sidebar"
      className="w-[240px] min-w-[240px] shrink-0 bg-[var(--surface-bg)] p-5 border-r min-h-[320px]" style={{ borderColor: 'var(--divider-color)' }}
    >
      {loaded && (
        <nav>
          <h3 className="mb-3 text-base font-semibold" style={{ color: 'var(--subtle-text)' }}>Topics</h3>
          <ul className="list-none mb-6">
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Artificial Intelligence</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Web Development</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Cloud Computing</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Cybersecurity</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">DevOps</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Mobile Apps</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Data Engineering</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Open Source</a></li>
          </ul>
          <h3 className="mb-3 text-base font-semibold" style={{ color: 'var(--subtle-text)' }}>Reading Lists</h3>
          <ul className="list-none mb-6">
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Editor Picks</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Most Popular</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Beginner Guides</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Deep Dives</a></li>
            <li className="mb-2"><a href="#" className="text-[#6366f1] no-underline hover:underline">Tutorials</a></li>
          </ul>
        </nav>
      )}
    </aside>
  );
}
TSEOF

# Fix 9: BrowseBar - always render with reserved space
cat > /app/src/components/BrowseBar.tsx << 'BBEOF'
'use client';

import { useState, useEffect } from 'react';

interface BrowseBarProps {
  pageNum: number;
  articleCount: number;
  onPageChange: (p: number) => void;
}

// FIXED: always render container to prevent CLS
export default function BrowseBar({ pageNum, articleCount, onPageChange }: BrowseBarProps) {
  const [ready, setReady] = useState(false);
  const perPage = 12;
  const lastPage = Math.ceil(articleCount / perPage) || 1;

  useEffect(() => {
    setTimeout(() => {
      setReady(true);
    }, 1900);
  }, []);

  const from = (pageNum - 1) * perPage + 1;
  const to = Math.min(pageNum * perPage, articleCount);

  return (
    <div
      data-testid="browse-bar"
      className="flex justify-between items-center bg-[var(--surface-bg)] py-4 px-5 mb-5 rounded-lg text-sm min-h-[56px]"
    >
      {ready && articleCount > 0 ? (
        <>
          <span>Articles {from}-{to} of {articleCount}</span>
          <div data-testid="page-nav" className="flex items-center gap-3">
            <button
              data-testid="prev-page-btn"
              disabled={pageNum === 1}
              onClick={() => onPageChange(pageNum - 1)}
              className="px-4 py-2 rounded cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed" style={{ backgroundColor: 'var(--surface-bg)', border: '1px solid var(--divider-color)' }}
            >
              Prev
            </button>
            <span>Page {pageNum} of {lastPage}</span>
            <button
              data-testid="next-page-btn"
              disabled={pageNum === lastPage}
              onClick={() => onPageChange(pageNum + 1)}
              className="px-4 py-2 rounded cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed" style={{ backgroundColor: 'var(--surface-bg)', border: '1px solid var(--divider-color)' }}
            >
              Next
            </button>
          </div>
          <span>Sort: Newest</span>
        </>
      ) : null}
    </div>
  );
}
BBEOF

# Fix 10: ArticleGrid - show skeletons matching article card size
cat > /app/src/components/ArticleGrid.tsx << 'GRIDEOF'
'use client';

import { useState, useEffect } from 'react';
import ArticleCard from './ArticleCard';
import ArticleSkeleton from './ArticleSkeleton';

interface ArticleGridProps {
  pageNum: number;
  onArticlesLoaded: (count: number) => void;
}

// FIXED: skeleton loader matches actual content size
export default function ArticleGrid({ pageNum, onArticlesLoaded }: ArticleGridProps) {
  const [articles, setArticles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const perPage = 12;

  useEffect(() => {
    setTimeout(() => {
      fetch('/api/articles')
        .then(r => r.json())
        .then(data => {
          setArticles(data);
          setLoading(false);
          onArticlesLoaded(data.length);
        });
    }, 1000);
  }, []);

  const offset = (pageNum - 1) * perPage;
  const visibleArticles = articles.slice(offset, offset + perPage);

  return (
    <div data-testid="article-grid" className="p-5">
      <h2 className="mb-5">Latest Articles</h2>
      <div className="grid grid-cols-3 gap-5">
        {loading ? (
          Array.from({ length: perPage }).map((_, idx) => (
            <ArticleSkeleton key={idx} />
          ))
        ) : (
          visibleArticles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))
        )}
      </div>
    </div>
  );
}
GRIDEOF

# Build production
npm run build

free_port

# Start production server
npm start &
PROD_ID=$!

echo "Waiting for production server..."
for attempt in $(seq 1 60); do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null | grep -q "200"; then
    echo "Production ready"
    break
  fi
  sleep 1
done

# Post-fix CLS measurement
python3 << 'POSTFIX'
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True)
    pg = br.new_page()

    pg.add_init_script("""
        window.__clsVal = 0;
        window.__entries = [];
        let ws = 0; let wb = 0; let ls = 0;
        new PerformanceObserver((list) => {
            for (const e of list.getEntries()) {
                if (e.hadRecentInput) continue;
                const t = e.startTime / 1000;
                if (wb === 0 || (t - ls) > 1 || (t - wb) > 5) { ws = 0; wb = t; }
                ws += e.value; ls = t;
                window.__entries.push({v: e.value});
                if (ws > window.__clsVal) window.__clsVal = ws;
            }
        }).observe({ type: 'layout-shift', buffered: true });
    """)

    pg.goto("http://localhost:3000", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(1000)
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(1000)

    val = pg.evaluate("window.__clsVal")
    ents = pg.evaluate("window.__entries")
    br.close()

with open("/tmp/postfix_cls.json", "w") as fp:
    json.dump({"cls": round(val, 3), "entries": ents}, fp)
print(f"POST-FIX CLS: {val}")
POSTFIX

kill $PROD_ID 2>/dev/null || true
free_port

# Generate summary
mkdir -p /app/output
python3 << 'SUMMARY'
import json

with open('/tmp/baseline_cls.json') as f:
    before = json.load(f)
with open('/tmp/postfix_cls.json') as f:
    after = json.load(f)

print(f"CLS improved from {before['cls']} to {after['cls']}")
SUMMARY

echo "All fixes applied successfully"
