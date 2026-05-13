'use client';

export default function ArticleSkeleton() {
  return (
    <div data-testid="article-skeleton" className="bg-[var(--surface-bg)] rounded-lg p-4">
      <div data-testid="skeleton-cover" className="w-full h-36 bg-gray-300 animate-pulse" />
      <div data-testid="skeleton-headline" className="mt-3 h-4 w-3/4 bg-gray-300 animate-pulse" />
    </div>
  );
}
