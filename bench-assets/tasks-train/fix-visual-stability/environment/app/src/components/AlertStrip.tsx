'use client';

import { useState, useEffect } from 'react';

const API_URL = '';

export default function AlertStrip() {
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    fetch(`${API_URL}/api/alert-strip`)
      .then(r => r.json())
      .then(data => setMessage(data.text));
  }, []);

  if (!message) return null;

  return (
    <div
      data-testid="alert-strip"
      className="bg-[#f59e0b] text-black py-28 px-4 text-center font-bold text-[26px]"
    >
      {message}
    </div>
  );
}
