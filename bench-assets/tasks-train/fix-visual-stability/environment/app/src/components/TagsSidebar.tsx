'use client';

import { useState, useEffect } from 'react';

const API_URL = '';

export default function TagsSidebar() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/tags-sidebar`)
      .then(r => r.json())
      .then(setData);
  }, []);

  if (!data) return null;

  return (
    <aside
      data-testid="tags-sidebar"
      className="w-[240px] shrink-0 bg-[var(--surface-bg)] p-5 border-r" style={{ borderColor: 'var(--divider-color)' }}
    >
      <nav>
        <h3 className="mb-3 text-base font-semibold" style={{ color: 'var(--subtle-text)' }}>Topics</h3>
        <ul className="list-none mb-6">
          {data.topics.map((topic: any) => (
            <li key={topic.label} className="mb-2">
              <a href={topic.url} className="text-[#6366f1] no-underline hover:underline">{topic.label}</a>
            </li>
          ))}
        </ul>
        <h3 className="mb-3 text-base font-semibold" style={{ color: 'var(--subtle-text)' }}>Reading Lists</h3>
        <ul className="list-none mb-6">
          {data.readingLists.map((rl: any) => (
            <li key={rl.label} className="mb-2">
              <a href={rl.url} className="text-[#6366f1] no-underline hover:underline">{rl.label}</a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
