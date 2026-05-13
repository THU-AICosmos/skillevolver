const express = require('express');
const cors = require('cors');
const articles = require('./articles.json');

const app = express();
app.use(cors());

const pause = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Articles - 1800ms delay
app.get('/api/articles', async (req, res) => {
  await pause(1800);
  res.json(articles);
});

// Headline banner - 1200ms delay
app.get('/api/headline', async (req, res) => {
  await pause(1200);
  res.json({ text: 'Breaking: AI Reaches New Milestone in Code Generation' });
});

// Alert strip - 2800ms delay (late, causes second shift)
app.get('/api/alert-strip', async (req, res) => {
  await pause(2800);
  res.json({ text: 'Join our live webinar this Friday: The Future of Serverless Architecture' });
});

// Tags sidebar - 1700ms delay
app.get('/api/tags-sidebar', async (req, res) => {
  await pause(1700);
  res.json({
    topics: [
      { label: 'Artificial Intelligence', url: '#' },
      { label: 'Web Development', url: '#' },
      { label: 'Cloud Computing', url: '#' },
      { label: 'Cybersecurity', url: '#' },
      { label: 'DevOps', url: '#' },
      { label: 'Mobile Apps', url: '#' },
      { label: 'Data Engineering', url: '#' },
      { label: 'Open Source', url: '#' }
    ],
    readingLists: [
      { label: 'Editor Picks', url: '#' },
      { label: 'Most Popular', url: '#' },
      { label: 'Beginner Guides', url: '#' },
      { label: 'Deep Dives', url: '#' },
      { label: 'Tutorials', url: '#' }
    ]
  });
});

// Browse bar - 1900ms delay
app.get('/api/browse-bar', async (req, res) => {
  await pause(1900);
  res.json({ ready: true });
});

const PORT = 4000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Blog API running on port ${PORT}`);
});
