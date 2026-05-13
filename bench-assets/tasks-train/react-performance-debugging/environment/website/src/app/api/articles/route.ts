// src/app/api/articles/route.ts
import { NextRequest, NextResponse } from 'next/server';
import {
  fetchReaderFromService,
  fetchArticlesFromService,
  logMetricsToService,
} from '@/services/api-client';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const reader = await fetchReaderFromService();
  const articles = await fetchArticlesFromService();

  await logMetricsToService({ readerId: reader.id, action: 'view_feed', count: articles.length });

  return NextResponse.json({ articles });
}
