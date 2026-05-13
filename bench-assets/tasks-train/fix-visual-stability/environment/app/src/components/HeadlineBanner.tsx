'use client';

import { useState, useEffect } from 'react';

const API_URL = '';

export default function HeadlineBanner() {
  const [headline, setHeadline] = useState<string>('');

  useEffect(() => {
    fetch(`${API_URL}/api/headline`)
      .then(r => r.json())
      .then(data => setHeadline(data.text));
  }, []);

  if (!headline) return null;

  return (
    <div
      data-testid="headline-banner"
      className="bg-[#6366f1] text-white py-20 px-4 text-center font-bold text-2xl"
    >
      {headline}
    </div>
  );
}
