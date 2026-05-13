// src/services/api-client.ts
// HTTP client for external microservices
// The actual API runs in a separate service - optimize how you use these calls!

const API_BASE = process.env.EXTERNAL_API_URL || 'http://localhost:3001';

export async function fetchReaderFromService() {
  const res = await fetch(`${API_BASE}/api/reader`);
  if (!res.ok) throw new Error('Failed to fetch reader');
  return res.json();
}

export async function fetchArticlesFromService() {
  const res = await fetch(`${API_BASE}/api/articles`);
  if (!res.ok) throw new Error('Failed to fetch articles');
  return res.json();
}

export async function fetchCommentsFromService() {
  const res = await fetch(`${API_BASE}/api/comments`);
  if (!res.ok) throw new Error('Failed to fetch comments');
  return res.json();
}

export async function fetchPreferencesFromService() {
  const res = await fetch(`${API_BASE}/api/preferences`);
  if (!res.ok) throw new Error('Failed to fetch preferences');
  return res.json();
}

export async function fetchReaderDigestFromService(readerId: string) {
  const res = await fetch(`${API_BASE}/api/reader-digest/${readerId}`);
  if (!res.ok) throw new Error('Failed to fetch reader digest');
  return res.json();
}

export async function logMetricsToService(data: unknown) {
  const res = await fetch(`${API_BASE}/api/metrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to log metrics');
  return res.json();
}
