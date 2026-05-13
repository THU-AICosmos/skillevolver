'use client';

interface Article {
  id: string;
  title: string;
  author: string;
  excerpt: string;
  coverImage: string;
  readTime: number;
}

export default function ArticleCard({ article }: { article: Article }) {
  return (
    <div data-testid="article-card" className="bg-[var(--surface-bg)] rounded-lg p-4" style={{ boxShadow: 'var(--surface-shadow)', border: '1px solid var(--divider-color)' }}>
      <img
        data-testid="article-cover"
        src={article.coverImage}
        alt={article.title}
        className="w-full"
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
