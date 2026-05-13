// News Reader API Simulator - Simulates external microservices with realistic latency
// DO NOT MODIFY - This runs in a separate service that the agent cannot access

import express from 'express';

const app = express();
app.use(express.json());

const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

// Reader/auth service - 380ms latency
app.get('/api/reader', async (req, res) => {
  await delay(380);
  res.json({
    id: 'reader-1',
    name: 'Morgan Chen',
    email: 'morgan@readslow.app',
    plan: 'premium',
  });
});

// Article feed service - 480ms latency
app.get('/api/articles', async (req, res) => {
  await delay(480);
  res.json(Array.from({ length: 36 }, (_, i) => ({
    id: `art-${i + 1}`,
    headline: `Article Headline Number ${i + 1}`,
    minutesToRead: 3 + (i % 10),
    section: ['World', 'Tech', 'Science', 'Culture', 'Sports', 'Opinion'][i % 6],
    score: 3 + (i % 3),
    published: i % 7 !== 0,
  })));
});

// Comments service - 270ms latency
app.get('/api/comments', async (req, res) => {
  await delay(270);
  res.json([
    { id: 'cm1', articleId: 'art-1', body: 'Thought-provoking take', score: 14, author: 'Nina' },
    { id: 'cm2', articleId: 'art-2', body: 'Disagree with the framing', score: 7, author: 'Owen' },
    { id: 'cm3', articleId: 'art-1', body: 'Great follow-up piece', score: 22, author: 'Priya' },
    { id: 'cm4', articleId: 'art-3', body: 'Citations missing', score: 3, author: 'Quentin' },
    { id: 'cm5', articleId: 'art-5', body: 'Important context here', score: 18, author: 'Ravi' },
  ]);
});

// Preferences service - 560ms latency (slower)
app.get('/api/preferences', async (req, res) => {
  await delay(560);
  res.json({
    timezone: 'America/Los_Angeles',
    locale: 'en-US',
    features: { darkMode: true, audioNarration: true },
  });
});

// Reader digest service - 280ms latency
app.get('/api/reader-digest/:readerId', async (req, res) => {
  await delay(280);
  res.json({
    readerId: req.params.readerId,
    digest: 'weekly',
    topics: { tech: true, science: true, opinion: false },
  });
});

// Metrics/analytics service - 170ms latency
app.post('/api/metrics', async (req, res) => {
  await delay(170);
  console.log('Metrics logged:', req.body);
  res.json({ success: true });
});

// Health check endpoint (no delay)
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`News API Simulator running on port ${PORT}`);
});
